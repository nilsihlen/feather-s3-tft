"""Henter skjermbilder fra kortet over serieporten og lagrer dem som PNG.

Bruk: python tools/screenshot.py COM7 utmappe [oppsett]
Med `oppsett` tas bare bildene av wifi-oppsettet.
Stopper programmet på kortet mens det tegner testbilder, og starter det igjen til slutt.
"""

import binascii
import pathlib
import struct
import sys
import time
import zlib

import serial

SCALE = 4
WIDTH = 240
HEIGHT = 135

IMPORTS = """
import adafruit_requests, binascii, board, netconfig, portal, screen, socketpool, ssl, wifi, wifisetup
"""

SETUP = """
n = netconfig.load()
wifi.radio.connected or wifi.radio.connect(n[0], n[1], timeout=20)
c = ssl.create_default_context()
c.load_verify_locations(cadata=open('/portal_root.pem').read())
r = adafruit_requests.Session(socketpool.SocketPool(wifi.radio), c)
x = r.get(portal.URL, headers={'User-Agent': 'feather-s3-tft'}, timeout=25)
d = portal.parse(x.json())
x.close()
s = screen.Screen()
s.activate()
s._history = [min(100, 40 + abs(120 - i) // 3) for i in range(239)]
s.add_soc(d['soc'])
"""

DUMP = """
board.DISPLAY.refresh()
b = bytearray(WIDTH * 2)
print('BILDE')
z = bytes(WIDTH * 2)
for y in range(HEIGHT):
    b[:] = z
    board.DISPLAY.fill_row(y, b)
    print('R' + binascii.hexlify(b).decode())
print('SLUTT')
""".replace("WIDTH", str(WIDTH)).replace("HEIGHT", str(HEIGHT))

SCENES = {
    "normal": "s.show(d, portal.age_text(d['age_s']))\n",
    "cerbo": "s.set_cerbo(True)\ns.show(d, '42 s')\n",
    "aggregat": (
        "g = dict(d)\n"
        "g.update(soc=38, batt_state=1, pv_w=420, generator_on=True, ac_in_v=228.0,"
        " ac_in_hz=50.1, ac_in_w=2300, bank_w=1480.0, target_pct=90, hours=3.4)\n"
        "s.show(g, '3 min')\n"
    ),
    "fukt": (
        "f = dict(d)\n"
        "f.update(cellar_rh=91, operation='Avfukting', batt_state=0, bank_w=12.0, hours=None)\n"
        "s.show(f, '4 min')\n"
    ),
    "feil": "f = dict(d)\nf.update(vebus_error=17)\ns.show(f, '3 min')\n",
    "gammel": "s.show(d, '')\ns.show_stale('rapport 3 t')\n",
    "sitat": (
        "s.show(d, portal.age_text(d['age_s']))\n"
        "s.start_ticker('Never tell me the odds (Han Solo)')\n"
        "for _ in range(55):\n"
        "    s.step_ticker()\n"
    ),
}
SETUP_SCENES = {
    "oppsett": "wifisetup.show_wifi_step('abcd2345')\n",
    "oppsett_feil": "wifisetup.show_wifi_step('abcd2345', 'x')\n",
    "side": "wifisetup.show_page_step('192.168.4.1')\n",
    "kobler": "screen.show_splash('Kobler til', 'TinnHytta')\n",
}


def png(path, rows):
    raw = bytearray()
    for row in rows:
        line = bytearray([0])
        for r, g, b in row:
            line += bytes((r, g, b)) * SCALE
        raw += bytes(line) * SCALE

    def chunk(kind, data):
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    head = struct.pack(">IIBBBBB", WIDTH * SCALE, HEIGHT * SCALE, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", head)
        + chunk(b"IDAT", zlib.compress(bytes(raw)))
        + chunk(b"IEND", b"")
    )


def pixels(hex_row):
    data = binascii.unhexlify(hex_row)
    row = []
    for x in range(WIDTH):
        value = struct.unpack(">H", data[2 * x:2 * x + 2])[0]
        row.append(((value >> 8) & 0xF8, (value >> 3) & 0xFC, (value << 3) & 0xF8))
    return row


def run(port, code):
    port.write(b"\x05")
    time.sleep(0.2)
    port.write(code.replace("\n", "\r").encode())
    port.write(b"\x04")


def read_until(port, marker, timeout_s):
    end = time.monotonic() + timeout_s
    text = b""
    while time.monotonic() < end:
        text += port.read(8192)
        if text.count(marker) and text.rstrip().endswith(b">>>"):
            break
    return text.decode("utf-8", "replace")


def capture(port, out, name, scene):
    run(port, scene + DUMP)
    text = read_until(port, b"SLUTT\r\n", 30)
    rows = [line.strip()[1:] for line in text.splitlines() if line.startswith("R")]
    rows = [row for row in rows if len(row) == WIDTH * 4]
    if len(rows) != HEIGHT:
        print(name, "fikk bare", len(rows), "rader:", text[-300:])
        return
    png(out / (name + ".png"), [pixels(row) for row in rows])
    print(out / (name + ".png"))


def main():
    out = pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    port = serial.Serial(sys.argv[1], 115200, timeout=0.2)
    port.dtr = True
    port.write(b"\x03")
    time.sleep(0.5)
    port.write(b"\x03")
    time.sleep(1.2)
    port.write(b"\r")
    time.sleep(1)
    port.read(8192)

    run(port, IMPORTS + "print('KLAR')\n")
    read_until(port, b"KLAR\r\n", 20)
    for name, scene in SETUP_SCENES.items():
        capture(port, out, name, scene)

    if "oppsett" not in sys.argv[3:]:
        run(port, SETUP + "print('KLAR')\n")
        text = read_until(port, b"KLAR\r\n", 40)
        if "Error" in text:
            print("uten nett: bare oppsettbildene er tatt")
        else:
            for name, scene in SCENES.items():
                capture(port, out, name, scene)

    port.write(b"\x04")
    time.sleep(0.5)
    port.close()


main()
