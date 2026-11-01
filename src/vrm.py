"""Leser ferske tall fra Victrons VRM-sky når Cerbo-en er online. Kun lesing.

VRM oppdateres omtrent hvert minutt så lenge hyttas ruter står på (målt 01.11.2026:
SOC-stempel 17 s gammelt, nytt punkt per minutt). Graph-endepunktet gir bare feltene
vi ber om, 1,6 kB for siste kvarter, mot 181 kB for hele diagnostikken.

Nøkkelen er en VRM-tilgangsnøkkel (ikke passordet), lagret i settings.toml på kortet.
Virker både i CircuitPython og CPython, slik at den kan testes på PC-en.
"""

URL = (
    "https://vrmapi.victronenergy.com/v2/installations/%s/widgets/Graph"
    "?attributeCodes[]=bs&attributeCodes[]=Pdc&attributeCodes[]=a1&start=%d&end=%d"
)
WINDOW_S = 900
# Eldre siste punkt enn dette betyr at Cerbo-en ikke rapporterer: ruteren er av.
ONLINE_MAX_AGE_S = 180
_CODES = {"bs": "soc", "Pdc": "pv_w", "a1": "load_w"}


def parse(reply, now_epoch):
    """Siste punkt per felt. `online` er False når noe mangler eller er gammelt."""
    records = reply.get("records") or {}
    meta = records.get("meta") or {}
    data = records.get("data") or {}
    out = {"soc": None, "pv_w": None, "load_w": None, "age_s": None, "online": False}
    newest = None
    for attr_id, series in data.items():
        code = (meta.get(str(attr_id)) or {}).get("code")
        name = _CODES.get(code)
        if name is None or not isinstance(series, list) or not series:
            continue
        stamp, value = series[-1][0], series[-1][1]
        if value is not None:
            out[name] = value
            newest = stamp if newest is None else max(newest, stamp)
    soc = out["soc"]
    # Utenfor 0-100 er trolig feil felt, og det skal aldri vises som SOC.
    if soc is not None and not 0 <= soc <= 100:
        out["soc"] = None
    if newest is not None:
        out["age_s"] = max(0, now_epoch - newest)
        out["online"] = out["age_s"] <= ONLINE_MAX_AGE_S and out["soc"] is not None
    return out


def fetch(session, token, site, now_epoch, user_agent):
    url = URL % (site, now_epoch - WINDOW_S, now_epoch)
    headers = {"X-Authorization": "Token " + token, "User-Agent": user_agent}
    with session.get(url, headers=headers, timeout=15) as response:
        if response.status_code != 200:
            raise OSError("VRM HTTP %d" % response.status_code)
        return parse(response.json(), now_epoch)


def merge(data, live):
    """Legger VRM-tallene inn i driftsbildet. True når de ble brukt.

    SOC, sol og forbruk blir inntil fem minutter ferskere enn Pi-rapporten.
    Resten (fukt, aggregat, bankeffekt) beholder Lovable-verdiene sine.
    """
    if not live["online"]:
        return False
    data["soc"] = int(live["soc"])
    if live["pv_w"] is not None:
        data["pv_w"] = live["pv_w"]
    if live["load_w"] is not None:
        data["load_w"] = live["load_w"]
    data["age_s"] = live["age_s"]
    data["stale"] = False
    return True
