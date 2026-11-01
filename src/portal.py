"""Tolker /api/live fra OD3-portalen. Bare lesing, og endepunktet krever ingen nøkkel.

Virker både i CircuitPython og CPython, slik at den kan testes på PC-en.
Felt som mangler, blir None: en bank som ikke svarer, er ikke en tom bank.
"""

URL = "https://od3-foundation.lovable.app/api/live"

AC_SOURCE_GENERATOR = 2
# 13 kWh effektivt (FAKTA.md i OD3), altså ca. 130 Wh per prosent.
WH_PER_PCT = 130
NOD_SOC_PCT = 5  # generator_nod_soc_pct
GENERATOR_STOP_SOC_PCT = 90  # generator_stop_soc_pct
# Under dette er bankeffekten for liten til at et tidsanslag betyr noe.
MIN_ETA_W = 30
# Margin etter lovet neste vekking før rapporten regnes som gammel.
REPORT_MARGIN_S = 10 * 60

OPERATIONS = {
    "circulate": "Sirkulasjon",
    "ventilate": "Ventilering",
    "dehumidify": "Avfukting",
    "dehumidify_generator": "Avfukting",
    "generator_charge": "Aggregatlading",
}


def parse_time(text):
    """ISO 8601 i UTC til sekunder siden 1970. Portalen sender bare UTC."""
    year = int(text[0:4])
    month = int(text[5:7])
    day = int(text[8:10])
    # days_from_civil: virker uten klokke og tidssonedata på kortet.
    if month <= 2:
        year -= 1
    era = year // 400
    yoe = year - era * 400
    doy = (153 * (month + (-3 if month > 2 else 9)) + 2) // 5 + day - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    days = era * 146097 + doe - 719468
    return (
        days * 86400
        + int(text[11:13]) * 3600
        + int(text[14:16]) * 60
        + int(text[17:19])
    )


def age_text(seconds):
    if seconds < 90:
        return "%d s" % seconds
    if seconds < 90 * 60:
        return "%d min" % (seconds // 60)
    if seconds < 48 * 3600:
        return "%d t" % (seconds // 3600)
    return "%d d" % (seconds // 86400)


def bank_w(pv_w, dc_v, dc_a, cabinet_w):
    """Netto bankeffekt, + er lading, som bankEffekt() i portalen.

    Anslag: små DC-laster er ikke med. Aldri `batt_w`: det viser bare ca. 2/3
    av strømmen (FAKTA.md i OD3). Reservekilden for spenning er `batt_v`, som
    var lik MultiPlusens `dc_v` da de ble sammenlignet 01.11.2026.
    """
    if pv_w is None or dc_v is None or dc_a is None:
        return None
    return pv_w + dc_v * dc_a - (cabinet_w or 0)


def target_pct(power_w, generator_on):
    if power_w < 0:
        return NOD_SOC_PCT
    return GENERATOR_STOP_SOC_PCT if generator_on else 100


def hours_to(soc, target, power_w):
    """Timer til `target`, eller None når banken ikke er på vei dit."""
    if abs(power_w) < MIN_ETA_W or (target - soc) * power_w <= 0:
        return None
    return abs(target - soc) * WH_PER_PCT / abs(power_w)


def _dict(value):
    return value if isinstance(value, dict) else {}


def _bank_source(sources):
    for source in sources.values():
        if _dict(source).get("soc_pct") is not None:
            return source
    return {}


def _humidity(rooms, room):
    return _dict(_dict(rooms.get(room)).get("doegntrend")).get("til_rh_pct")


def parse(live):
    """Kaster ValueError når svaret ikke har noen enhet. Resten kan mangle."""
    devices = live.get("devices")
    if not devices:
        raise ValueError("ingen enhet i svaret")
    device = devices[0]
    device_id = device.get("device_id")

    now_epoch = parse_time(live["now"])
    age_s = max(0, now_epoch - parse_time(device["last_report_at"]))
    wake_s = device.get("last_next_wake_in_s") or 0

    sources = _dict(_dict(_dict(live.get("energy")).get(device_id)).get("sources"))
    bank = _bank_source(sources)
    other = _dict(bank.get("ovrige"))
    aggregate = _dict(live.get("aggregat"))
    rooms = _dict(_dict(live.get("fukt")).get(device_id))
    operation = _dict(_dict(live.get("active_operation")).get(device_id)).get("operation")

    soc = bank.get("soc_pct")
    if soc is not None and not 0 <= soc <= 100:
        soc = None
    pv_w = bank.get("pv_w")
    generator_on = other.get("ac_source") == AC_SOURCE_GENERATOR
    power = bank_w(
        pv_w,
        bank.get("batt_v"),
        aggregate.get("dc_a"),
        _dict(sources.get("device")).get("p_w"),
    )

    target = None
    hours = None
    if soc is not None and power is not None:
        target = target_pct(power, generator_on)
        hours = hours_to(soc, target, power)

    return {
        # Portalens klokke: kortet har ingen egen, og VRM-vinduet trenger epoketid.
        "now_epoch": now_epoch,
        "age_s": age_s,
        "stale": soc is None or age_s > wake_s + REPORT_MARGIN_S,
        "report_at": device["last_report_at"],
        "soc": soc,
        "batt_state": other.get("batt_state"),
        "pv_w": pv_w,
        "load_w": other.get("ac_load_w"),
        "generator_on": generator_on,
        "ac_in_v": aggregate.get("ac_in_v"),
        "ac_in_hz": aggregate.get("ac_in_hz"),
        "ac_in_w": aggregate.get("ac_in_w"),
        "start_v": aggregate.get("genbat_v"),
        "vebus_error": aggregate.get("vebus_error"),
        "bank_w": power,
        "target_pct": target,
        "hours": hours,
        "cellar_rh": _humidity(rooms, "vinkjeller"),
        "tech_rh": _humidity(rooms, "teknisk"),
        "rh_limit": live.get("rh_grense_pct"),
        "operation": OPERATIONS.get(operation, operation),
    }
