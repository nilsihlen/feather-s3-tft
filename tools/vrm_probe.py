"""Måler hva VRM-skyen faktisk kan gi kortet. Kjøres av Nils, ikke av Claude.

VRM godtar ikke lenger passord i API-et, bare tilgangsnøkler. Nøkkelen lages på
vrm.victronenergy.com under Preferences -> Integrations -> Access tokens, og legges i
fila C:\\Get_SOC_VRM\\vrm_token.txt (bare nøkkelen, én linje). Den skrives aldri ut.

Bruk: python tools\\vrm_probe.py
Skriver ut: om nøkkelen virker, hvor ferske tallene er, hvor mye som endrer
seg på 30 sekunder, svarstørrelse, eventuelle fartsgrense-hoder og TLS-utsteder.
"""

import json
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request

KILDE = r"C:\Get_SOC_VRM\get_soc.py"
NOKKELFIL = r"C:\Get_SOC_VRM\vrm_token.txt"
API = "https://vrmapi.victronenergy.com/v2"
FELT = ("bs", "Pdc", "SV", "SI", "S", "CL", "a1", "P")


def les_konto():
    tekst = open(KILDE, encoding="utf-8").read()
    site = re.search(r"SITE_ID\s*=\s*'([^']+)'", tekst).group(1)
    try:
        nokkel = open(NOKKELFIL, encoding="utf-8").read().strip()
    except OSError:
        sys.exit("Fant ikke %s. Lag en tilgangsnøkkel på vrm.victronenergy.com under\n"
                 "Preferences -> Integrations -> Access tokens, og lagre den i den fila." % NOKKELFIL)
    return nokkel, site


def hent(url, data=None, hoder=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers={"Content-Type": "application/json", "User-Agent": "feather-s3-tft", **(hoder or {})},
    )
    return urllib.request.urlopen(req, timeout=30)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    nokkel, site = les_konto()
    print("site: %s  nøkkellengde: %d" % (site, len(nokkel)))
    hode = {"X-Authorization": "Token " + nokkel}
    try:
        hent(API + "/users/me", hoder=hode).read()
    except urllib.error.HTTPError as feil:
        print("nøkkelen FEILET:", feil.code, feil.read()[:200])
        return
    print("nøkkelen virker")

    def diagnostikk():
        r = hent(API + "/installations/%s/diagnostics?count=1000" % site, hoder=hode)
        grense = {k: v for k, v in r.headers.items() if "ratelimit" in k.lower() or k.lower() == "retry-after"}
        data = json.loads(r.read())
        return data.get("records") or [], len(json.dumps(data)), grense

    rader, stor, grense = diagnostikk()
    naa = time.time()
    print("records: %d  svar: %d byte  fartsgrense-hoder: %s" % (len(rader), stor, grense or "ingen"))
    for rad in rader:
        if rad.get("code") in FELT:
            print("  %-4s %-30.30s %-12s alder %5.0f s"
                  % (rad["code"], rad.get("description"), rad.get("formattedValue"),
                     naa - (rad.get("timestamp") or 0)))

    print("venter 30 s og måler hva som endret seg ...")
    foer = {r["code"]: (r.get("timestamp"), r.get("rawValue")) for r in rader if r.get("code")}
    time.sleep(30)
    rader2, _, _ = diagnostikk()
    endret = [r["code"] for r in rader2
              if r.get("code") in foer and (r.get("timestamp"), r.get("rawValue")) != foer[r["code"]]]
    print("felt med nytt stempel etter 30 s: %d  eksempler: %s" % (len(endret), endret[:12]))
    soc = next((r for r in rader2 if r.get("code") == "bs"), None)
    if soc:
        print("SOC nå: %s  alder: %.0f s" % (soc.get("formattedValue"), time.time() - soc["timestamp"]))

    ctx = ssl.create_default_context()
    with socket.create_connection(("vrmapi.victronenergy.com", 443), timeout=10) as raa:
        with ctx.wrap_socket(raa, server_hostname="vrmapi.victronenergy.com") as s:
            utsteder = dict(x[0] for x in s.getpeercert()["issuer"])
            print("TLS-utsteder:", utsteder.get("organizationName"), "/", utsteder.get("commonName"))


main()
