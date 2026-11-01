"""Wifi-oppsett fra telefonen: nettet velges i Wifi-innstillingene, så kommer siden opp selv."""

import time

import adafruit_miniqr
import board
import displayio
import microcontroller
import socketpool
import terminalio
import wifi
from adafruit_display_text import label
from adafruit_httpserver import GET, POST, Redirect, Request, Response, Server

import captive
import netconfig
from screen import show_splash

AP_SSID = "Skjerm"
PORT = 80
DNS_PORT = 53
# Uten telefon går kortet tilbake og prøver det lagrede nettet, f.eks. etter strømbrudd.
TIMEOUT_S = 10 * 60
RESTART_DELAY_S = 2
QR_SCALE = 4
QR_QUIET = 4  # kravet i QR-standarden, og det kameraet trenger
QR_Y = 1
TEXT_X = 136
AMBER = 0xFFB000

PAGE = """<!doctype html><html lang="no"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hytteskjerm</title><style>
body{font:17px system-ui,sans-serif;margin:24px auto;max-width:420px;padding:0 16px}
label{display:block;margin:16px 0 4px}
select,input,button{box-sizing:border-box;font:inherit;padding:12px;width:100%%}
button{background:#176;border:0;border-radius:6px;color:#fff;margin-top:20px}
details{margin-top:16px}.feil{background:#fde8e8;border-radius:6px;padding:12px}
</style></head><body><h1>Siste steg</h1>%s
<p>Velg wifi-et du bruker til vanlig, og skriv passordet til det.
Skjermen bruker dette for å hente tallene fra hytta.</p>
<form method="post" action="/lagre">
<label for="ssid">Ditt wifi</label><select id="ssid" name="ssid">%s</select>
<details><summary>Står ikke nettet i lista?</summary>
<label for="other">Skriv navnet på nettet</label>
<input id="other" name="other" autocomplete="off" autocapitalize="none"></details>
<label for="password">Passord til ditt wifi</label>
<input id="password" name="password" type="text" autocomplete="off" autocapitalize="none">
<button type="submit">Koble til</button>
</form></body></html>"""

SAVED_PAGE = """<!doctype html><html lang="no"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hytteskjerm</title></head><body style="font:17px system-ui,sans-serif;margin:24px">
<h1>Takk!</h1><p>Skjermen kobler seg nå til %s. Følg med på skjermen: tallene fra hytta
kommer innen ett minutt.</p>
<p>Telefonen går tilbake til vanlig wifi av seg selv, og du kan lukke denne siden.</p>
<p>Står det «Fikk ikke kontakt» på skjermen, kobler telefonen seg til igjen. Da prøver du
passordet på nytt.</p></body></html>"""


class SetupServer(Server):
    # Serverens sjekk gjør et navneoppslag, som feiler uten vanlig wifi. Adressen er kjent.
    def _verify_can_start(self, host, port):
        pass


def scan_networks():
    best = {}
    for network in wifi.radio.start_scanning_networks():
        if network.ssid and network.rssi > best.get(network.ssid, -999):
            best[network.ssid] = network.rssi
    wifi.radio.stop_scanning_networks()
    return sorted(best, key=lambda ssid: best[ssid], reverse=True)


def _qr_group(text):
    qr = adafruit_miniqr.QRCode(error_correct=adafruit_miniqr.L)
    qr.add_data(text.encode("utf-8"))
    qr.make()
    matrix = qr.matrix
    size = matrix.width + 2 * QR_QUIET
    bitmap = displayio.Bitmap(size, size, 2)
    palette = displayio.Palette(2)
    palette[0] = 0xFFFFFF
    palette[1] = 0x000000
    for row in range(matrix.height):
        for col in range(matrix.width):
            if matrix[col, row]:
                bitmap[col + QR_QUIET, row + QR_QUIET] = 1
    group = displayio.Group(scale=QR_SCALE, x=0, y=QR_Y)
    group.append(displayio.TileGrid(bitmap, pixel_shader=palette))
    return group


def _line(root, y, scale, text, color=0xFFFFFF, x=TEXT_X):
    item = label.Label(terminalio.FONT, text=text, color=color, scale=scale)
    item.anchor_point = (0, 0)
    item.anchored_position = (x, y)
    root.append(item)


def show_wifi_step(password, reason=None):
    # Ingen wifi-kode her: fra iPhone-kameraet kommer ikke siden opp av seg selv,
    # det gjør den når nettet velges i Wifi-innstillingene.
    root = displayio.Group()
    _line(root, 4, 2, "1 Telefonens wifi", x=6)
    _line(root, 34, 2, "2 Velg %s" % AP_SSID, x=6)
    _line(root, 64, 2, "3 Passord %s" % password, x=6)
    note = "Fikk ikke kontakt. Prov igjen." if reason else "Da kommer siden opp av seg selv"
    _line(root, 106, 1, note, AMBER, x=6)
    board.DISPLAY.root_group = root


def show_page_step(address):
    root = displayio.Group()
    root.append(_qr_group("http://%s/" % address))
    _line(root, 2, 2, "Vent")
    _line(root, 22, 1, "Telefon tilkoblet", AMBER)
    _line(root, 40, 1, "Siden kommer opp")
    _line(root, 52, 1, "av seg selv")
    _line(root, 72, 1, "Ikke kommet?")
    _line(root, 84, 1, "Skann koden eller")
    _line(root, 96, 1, "Safari:")
    _line(root, 108, 1, address)
    board.DISPLAY.root_group = root


def _options(networks):
    if not networks:
        return '<option value="">Fant ingen nett</option>'
    return "".join(
        '<option value="%s">%s</option>'
        % (netconfig.escape(ssid), netconfig.escape(ssid))
        for ssid in networks
    )


def _banner(reason):
    return '<p class="feil">%s</p>' % netconfig.escape(reason) if reason else ""


def start_services(pool, address, networks, reason, state):
    """Webtjener og DNS. `state` får `saved_at` når nettet er lagret."""
    server = SetupServer(pool, debug=False)
    home = "http://%s/" % address

    @server.route("/", GET)
    def form(request: Request):
        # iPhone henter siden i bakgrunnen for å sjekke nettet. Det betyr ikke at noen ser den.
        print("oppsett: siden hentet av", request.headers.get("User-Agent", "?")[:60])
        body = PAGE % (_banner(reason), _options(networks))
        return Response(request, body, content_type="text/html")

    @server.route("/lagre", POST)
    def save(request: Request):
        fields = netconfig.parse_form(request.body)
        ssid = fields.get("other", "").strip() or fields.get("ssid", "")
        try:
            netconfig.save(ssid, fields.get("password", ""))
        except ValueError as exc:
            return Response(request, "Feil: %s" % exc, status=(400, "Bad Request"))
        state["saved_at"] = time.monotonic()
        show_splash("Kobler til", ssid)
        print("oppsett: lagret", ssid)
        return Response(
            request, SAVED_PAGE % netconfig.escape(ssid), content_type="text/html"
        )

    # Telefonenes internettsjekk og alt annet som ikke er oppsettsiden.
    @server.route("/<slug>", GET)
    def probe(request: Request, slug: str = None):
        print("oppsett: sjekk", request.path)
        return Redirect(request, home)

    @server.route("/library/test/success.html", GET)
    def apple_probe(request: Request):
        return Redirect(request, home)

    server.start(address, port=PORT)
    dns = pool.socket(pool.AF_INET, pool.SOCK_DGRAM)
    dns.bind((address, DNS_PORT))
    dns.setblocking(False)
    return server, dns


def answer_dns(dns, buffer, packed_address):
    try:
        size, sender = dns.recvfrom_into(buffer)
    except OSError:
        return
    reply = captive.dns_reply(buffer[:size], packed_address)
    if reply is not None:
        dns.sendto(reply, sender)


def run(reason=None):
    """Viser oppsettet og starter kortet på nytt når det er lagret eller tida er ute."""
    networks = scan_networks()
    password = netconfig.setup_password(microcontroller.cpu.uid)
    wifi.radio.stop_station()
    wifi.radio.start_ap(AP_SSID, password)
    address = str(wifi.radio.ipv4_address_ap)
    packed = wifi.radio.ipv4_address_ap.packed
    show_wifi_step(password, reason)
    print("oppsett:", AP_SSID, address, "nett funnet:", len(networks))

    pool = socketpool.SocketPool(wifi.radio)
    state = {"saved_at": None}
    server, dns = start_services(pool, address, networks, reason, state)
    dns_buffer = bytearray(512)

    started = time.monotonic()
    joined = False
    while time.monotonic() - started < TIMEOUT_S:
        server.poll()
        answer_dns(dns, dns_buffer, packed)
        now = time.monotonic()
        saved_at = state["saved_at"]
        if saved_at is not None and now - saved_at >= RESTART_DELAY_S:
            break

        connected = len(wifi.radio.stations_ap) > 0
        if connected and not joined:
            print("oppsett: telefon koblet til")
            joined = True
            # Koden blir stående til nettet er lagret, som reserve hvis siden ikke kommer opp.
            show_page_step(address)
        elif not connected and joined:
            print("oppsett: telefon koblet fra")
            joined = False
            show_wifi_step(password, reason)

        if joined:
            # Tida skal ikke løpe ut mens noen skriver passordet.
            started = now
        time.sleep(0.01)
    microcontroller.reset()
