# feather-s3-tft

Privat hobbyprosjekt, ikke jobb. Kortet viser driftsbildet for hytta på ett skjermbilde.
Nils skal kunne gi det til faren eller sønnen sin: de setter i USB-C, velger nettet `Skjerm` i
Wifi-innstillingene på telefonen, og siden for wifi-oppsett kommer opp selv. Lovable er eneste
datakilde. Ikke bruk wifi-QR: fra iPhone-kameraet kommer siden ikke opp.

Les `PROGRESS.md` først. Den har status, hva som er gjort og planen, og oppdateres ved slutten
av hver økt.

## Kort
- Adafruit ESP32-S3 TFT Feather, 4 MB flash, 2 MB PSRAM, koblet til via USB
- CircuitPython 10.3.1, TinyUF2 0.35.0
- USB-ID og COM-port endrer seg med modus. Sjekk porten før bruk.
  - CircuitPython: `VID_239A`, `PID_811E` (COM7 sist)
  - TinyUF2: `VID_239A`, `PID_011D`, disken `FTHRS3BOOT`
  - ROM-bootloader: `VID_303A`, `PID_1001`
- Inn i ROM-modus: hold BOOT, trykk og slipp RST, slipp BOOT. Etter esptool må du
  trykke RST selv. Dobbeltrykk på RST ga ingen `FTHRS3BOOT` med fabrikkprogrammet.
- `C:\ESP32_firmw\ESP32_GENERIC-*.bin` er for klassisk ESP32. Ikke flash den til dette kortet.

## Struktur
- `src\` er originalen. CIRCUITPY er bare en kopi, så endringer gjøres i `src\`.
- `src\lib\` har biblioteker fra bundle 10.x, 20261031.
- `code.py` er bare en launcher (sone 0); programmet ligger i `app.py`. Kortet oppdaterer seg selv fra GitHub,
  se `docs\PLAN_ota.md` og `tools\publish.py`.
- `tools\deploy.ps1` kopierer til kortet og starter det på nytt. Auto-reload er av i `code.py`,
  så filer lagret rett på CIRCUITPY virker først etter omstart. Skriptet sletter ikke filer
  som er fjernet fra `src\`.
- Wifi lagres i `microcontroller.nvm`. `settings.toml` på kortet har bare VRM-nøkkelen
  (`VRM_TOKEN`, `VRM_SITE`) og skal aldri inn i repoet. Nøkkelreserven ligger i
  `C:\Get_SOC_VRM\vrm_token.txt`. Les aldri nøkkelen inn i samtalen.
- `python -m unittest discover -s tests` tester portal- og wifi-koden på PC-en uten kort.
- `python tools\screenshot.py COM7 <mappe>` henter ekte skjermbilder fra kortet, med testbilder
  for aggregat, fukt, feil, gamle data og oppsett. Se på dem etter endringer i `src\screen.py`.

## Tøm kortet
Når Nils sier «tøm kortet», kjør `python tools\forget_wifi.py`. Det sletter lagret wifi og
wifi-passord, og kortet viser QR-koden med en gang. Si fra om resultatet.

## Portal, VRM og wifi
- Se `docs\portal.md`. Kilden for portalen er `C:\OD3-Github`, som har siste versjon.
- Kun lesing fra `/api/live`. Kortet skal aldri sende kommandoer til portalen.
- Når Cerbo-en er online, henter kortet SOC, sol og forbruk fra VRM-skyen hvert minutt og
  viser blå `Cerbo online`-etikett. Kun lesing der også.

## Git
- Ikke push til jobbkontoer eller jobbrepoer. Repoet skal ligge på Nils' private GitHub-konto.
