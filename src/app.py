"""Viser driftsbildet fra OD3-portalen på TFT-skjermen. Startes av code.py. Se docs\\portal.md."""

import board
import supervisor

from screen import Screen, show_splash
from version import VERSION

# PC-en kan røre disken når kortet kobles til, og det skal ikke stoppe driftsbildet.
# tools\deploy.ps1 starter kortet på nytt etter oppdatering.
supervisor.runtime.autoreload = False

# boot.py slo av lyset. Det tennes her, før de tunge importene, så konsollen aldri vises.
show_splash("Starter", "v" + VERSION)
board.DISPLAY.brightness = 1

import gc  # noqa: E402
import os  # noqa: E402
import ssl  # noqa: E402
import time  # noqa: E402

import adafruit_connection_manager  # noqa: E402
import adafruit_requests  # noqa: E402
import digitalio  # noqa: E402
import microcontroller  # noqa: E402
import wifi  # noqa: E402

import updater  # noqa: E402
from guard import Guarded  # noqa: E402
import netconfig  # noqa: E402
import portal  # noqa: E402
import vrm  # noqa: E402
from starwars import QUOTES  # noqa: E402

# Rapportene kommer ofte hvert 5. minutt. Hvert minutt gir maks ett minutts forsinkelse
# fra en ny rapport til den står på skjermen, uten å plage portalen.
POLL_S = 60
# Ett glipp i nettet skal ikke gi grått bilde: to forsøk per runde, og forrige
# bilde beholdes i inntil tre minutter før det grånes.
LOVABLE_TRIES = 2
RETRY_PAUSE_S = 2
KEEP_SHOWING_S = 180
# Går Lovable ned mens VRM lever, skal det synes at resten av bildet eldes.
PORTAL_WARN_S = 10 * 60
WIFI_TIMEOUT_S = 20
# Uten tilkobling etter dette antallet forsøk ved oppstart åpnes wifi-oppsettet.
# Forsøk feiler på sekunder når nettet ikke er synlig, og ruteren kan starte treigere
# enn kortet etter et strømbrudd, så det må gå et halvt minutt før QR-koden vises.
STARTUP_ATTEMPTS = 6
STARTUP_PAUSE_S = 5
SETUP_HOLD_S = 3
# 240 kolonner gir 24 timer SOC-kurve.
HISTORY_S = 6 * 60
# Hvert femte intervall, altså hvert 10. minutt, glir et Star Wars-sitat over bunnlinja.
QUOTE_EVERY_N_POLLS = 5
HEADERS = {"User-Agent": "feather-s3-tft"}
ROOT_CERT = "/portal_root.pem"
RESTART_AFTER_CRASH_S = 10
# Sjekker etter ny versjon etter første vellykkede runde, så hver time (docs/PLAN_ota.md).
UPDATE_EVERY_S = 60 * 60
# En ny versjon som ikke har kvittert etter dette, startes på nytt, så oppstartstelleren i
# boot.py rekker å rulle tilbake også når tegningen feiler uten at programmet krasjer.
ACK_DEADLINE_S = 4 * 60


def connect_wifi(ssid, password):
    if wifi.radio.connected:
        return True
    try:
        wifi.radio.connect(ssid, password, timeout=WIFI_TIMEOUT_S)
    except (ConnectionError, OSError) as exc:
        print("wifi feilet:", ssid, exc)
        return False
    return True


def run_setup(reason=None):
    show_splash("Starter oppsett")
    # Importeres bare her: QR og webtjener bruker minne driftsbildet trenger.
    import wifisetup

    wifisetup.run(reason)


def idle_wait(button, screen, seconds, status_prefix=None):
    """Venter i `seconds`, driver rulleteksten og teller ned til neste henting.

    Nedtellingen («ny om 42 s») viser at skjermen lever og nøyaktig når neste
    oppdatering kommer. Med `status_prefix` vises feilen foran nedtellingen.
    True hvis BOOT holdes inne i SETUP_HOLD_S.
    BOOT kan ikke brukes ved omstart: BOOT + RST sender kortet til ROM-bootloaderen.
    """
    end = time.monotonic() + seconds
    next_tick = 0
    while True:
        now = time.monotonic()
        remaining = end - now
        if remaining <= 0:
            return False
        if not button.value:
            pressed = now
            while not button.value:
                if time.monotonic() - pressed >= SETUP_HOLD_S:
                    return True
                time.sleep(0.05)
        if now >= next_tick:
            if status_prefix is None:
                screen.show_age("ny om %d s" % remaining)
            else:
                screen.show_message("%s - %d" % (status_prefix, remaining))
            next_tick = now + 1
        screen.step_ticker()
        time.sleep(0.05)


def fetch(session):
    gc.collect()
    with session.get(portal.URL, headers=HEADERS, timeout=20) as response:
        if response.status_code != 200:
            raise OSError("HTTP %d" % response.status_code)
        return portal.parse(response.json())


def add_vrm(data, session):
    """Ferskere SOC, sol og forbruk fra VRM når Cerbo-en er online. Kaster aldri."""
    token = os.getenv("VRM_TOKEN")
    site = os.getenv("VRM_SITE")
    if not (token and site):
        return False
    try:
        live = vrm.fetch(session, token, site, data["now_epoch"], HEADERS["User-Agent"])
        used = vrm.merge(data, live)
        print("vrm:", "brukt, %d s fersk" % live["age_s"] if used else "offline")
        return used
    except Exception as exc:
        print("vrm feilet:", repr(exc))
        return False


def fetch_any(sessions):
    """Prøver neste sertifikatliste hvis Lovable har byttet utsteder."""
    for session in sessions[:-1]:
        try:
            return fetch(session)
        except OSError as exc:
            print("prøver neste sertifikatliste:", repr(exc))
    return fetch(sessions[-1])


def draw_failed(name, exc):
    """Reservetekst når tegningen feiler. Henteløkka går videre og prøver igjen."""
    show_splash("Tegnefeil", "%s v%s" % (type(exc).__name__, VERSION))


def check_update(session):
    """Henter ny versjon hvis Nils har publisert. Startes på nytt når noe er byttet inn."""

    def progress(version):
        try:
            show_splash("Oppdaterer", "til v" + version)
        except Exception as exc:
            print("splash feilet:", repr(exc))

    status = updater.check(session, VERSION, progress=progress)
    print("oppdatering:", status)
    if status == "oppdatert":
        time.sleep(2)
        microcontroller.reset()


def failure_text(reason, last_ok):
    if last_ok is None:
        return reason
    return "%s, %s" % (reason, portal.age_text(time.monotonic() - last_ok))


def main():
    button = digitalio.DigitalInOut(board.BUTTON)
    button.switch_to_input(pull=digitalio.Pull.UP)

    credentials = netconfig.load()
    if credentials is None:
        run_setup()
    ssid, password = credentials

    show_splash("Kobler til", ssid)
    for _ in range(STARTUP_ATTEMPTS):
        if connect_wifi(ssid, password):
            break
        time.sleep(STARTUP_PAUSE_S)
    else:
        run_setup("Fikk ikke kontakt med %s. Sjekk nett og passord." % ssid)

    show_splash("Henter tall", "fra hytta")
    pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
    # CircuitPython 10.3.1 godtar ikke Lovables rot med sin innebygde liste, men
    # den lista er reserven hvis Lovable bytter til en utsteder den kjenner.
    pinned = ssl.create_default_context()
    with open(ROOT_CERT) as cert:
        pinned.load_verify_locations(cadata=cert.read())
    sessions = (
        adafruit_requests.Session(pool, pinned),
        adafruit_requests.Session(pool, ssl.create_default_context()),
    )

    screen = Guarded(Screen(), draw_failed)
    first_pass = True
    last_ok = None  # sist noe ferskt ble vist, fra Lovable eller VRM
    last_lovable = None
    last_history = None
    last_report = None
    last_data = None  # forrige vellykkede Lovable-bilde
    epoch_ref = None  # (epoketid, monotonic) fra siste Lovable-svar
    polls = 0
    started = time.monotonic()
    next_update = 0
    # Tilfeldig startpunkt, så det ikke blir samme sitat etter hvert strømbrudd.
    quote_index = os.urandom(1)[0] % len(QUOTES)

    while True:
        screen.show_age("henter")
        connected = connect_wifi(ssid, password)
        fetched = None
        if connected:
            # Ett glipp i nettet skal ikke gi grått bilde: flere forsøk per runde.
            for attempt in range(LOVABLE_TRIES):
                try:
                    fetched = fetch_any(sessions)
                    break
                except Exception as exc:
                    print("portal feilet (%d/%d):" % (attempt + 1, LOVABLE_TRIES), repr(exc))
                    time.sleep(RETRY_PAUSE_S)
        now = time.monotonic()
        if fetched is not None:
            epoch_ref = (fetched["now_epoch"], now)
            last_data = fetched
            last_lovable = now

        # VRM prøves ALLTID når den kan: klokka huskes fra forrige portalsvar,
        # så Cerbo-tallene kommer selv i runder der Lovable glapp.
        cerbo = False
        if connected and last_data is not None and epoch_ref is not None:
            last_data["now_epoch"] = epoch_ref[0] + int(now - epoch_ref[1])
            cerbo = add_vrm(last_data, sessions[-1])
        screen.set_cerbo(cerbo)

        fresh = False
        prefix = None
        if (fetched is not None or cerbo) and last_data is not None:
            data = last_data
            if data["stale"]:
                screen.show(data, "")
                prefix = "rapport %s" % portal.age_text(data["age_s"])
                screen.show_stale(prefix)
            else:
                screen.show(data, portal.age_text(data["age_s"]))
                fresh = True
                last_ok = now
                if fetched is None and now - last_lovable > PORTAL_WARN_S:
                    prefix = "portal %s" % portal.age_text(now - last_lovable)
                new_report = data["report_at"] != last_report
                due = last_history is None or now - last_history >= HISTORY_S
                if (new_report or cerbo) and due and data["soc"] is not None:
                    screen.add_soc(data["soc"])
                    last_history = now
            last_report = data["report_at"]
        elif last_ok is not None and now - last_ok <= KEEP_SHOWING_S:
            # Kort glipp: behold bildet, og la nedtellingen vise at den prøver igjen.
            prefix = "nytt forsok"
        else:
            prefix = failure_text("ingen wifi" if not connected else "ingen portal", last_ok)
            screen.show_stale(prefix)

        if first_pass:
            first_pass = False
            screen.activate()
        got = fetched is not None or cerbo
        if updater.pending():
            # Uten nett er det ikke noe å vente på: koden har kommet seg hit og tegnet.
            if not screen.broken and (got or not connected):
                updater.acknowledge()
            elif connected and now - started > ACK_DEADLINE_S:
                print("ikke kvittert, starter på nytt")
                microcontroller.reset()
        elif got and now >= next_update:
            next_update = now + UPDATE_EVERY_S
            check_update(sessions[-1])
        polls += 1
        # Bare når bildet er ferskt: ved feil eier bunnlinja feilmeldingen.
        if fresh and prefix is None and polls % QUOTE_EVERY_N_POLLS == 0:
            screen.start_ticker(QUOTES[quote_index])
            quote_index = (quote_index + 1) % len(QUOTES)
        print("minne ledig:", gc.mem_free())
        if idle_wait(button, screen, POLL_S, prefix):
            run_setup()


try:
    main()
except Exception as exc:
    # Ingen skal bli stående med konsollen på skjermen. Ctrl-C er ikke en Exception.
    print("krasj:", repr(exc))
    show_splash("Starter igjen")
    time.sleep(RESTART_AFTER_CRASH_S)
    microcontroller.reset()
