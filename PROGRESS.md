# PROGRESS

Sist oppdatert: 2026-11-01. OTA er i drift på v0.2.4, se «OTA-status». Før kortet gis bort: se punktene i Plan.

## Status
Kortet virker og er nesten klart til å gis bort. Faren eller sønnen til Nils skal kunne sette i
USB-C, velge nettet `Skjerm` i Wifi-innstillingene, velge sitt wifi på siden som kommer opp og få
driftsbildet fra Lovable.

- Kortet kjører CircuitPython 10.3.1 med TinyUF2 0.35.0, på COM7 sist.
- Lovable er eneste datakilde. Kortet kobler seg ikke til Cerbo GX direkte.
- Kortet har TinnHytta lagret og henter data hvert 2. minutt.
- Første commit er gjort lokalt (`main`), remote `origin` peker på `git@github-nilsihlen:nilsihlen/feather-s3-tft.git`.
  Pushet 01.11 til https://github.com/nilsihlen/feather-s3-tft (offentlig). Raw-URL hentes uten innlogging (HTTP 200).

## Gjort
- Flashet kortet: dobbeltrykk på RST virket ikke med fabrikkprogrammet, så det gikk via
  ROM-bootloaderen. Fabrikkprogrammet er slettet.
- Bygde driftsbildet på ett skjermbilde: SOC, lader/tapper, bankeffekt, tid til neste grense,
  24-timerskurve, sol, last, aggregat, kjellerfukt, startbatteri og alder på rapporten.
- Gamle data blir grå, og inverterfeil gir rød skjerm.
- La inn wifi-oppsett fra telefonen: kortet lager nettet `Skjerm`, og oppsettsiden åpner seg selv
  etter én skanning. En reserve-QR vises etter 15 sekunder hvis siden ikke kommer.
- Testet på iPhone 01.11: wifi-QR fra kameraet åpnet aldri siden. Loggens «siden hentet» var
  telefonens bakgrunnssjekk, ikke at siden ble vist.
- Valgt løsning, testet kl. 05:53: `Skjerm` velges i Wifi-innstillingene. Siden kom opp selv etter
  7 sekunder, og TinnHytta var lagret 27 sekunder etter tilkobling, uten QR-kode.
- Wifi-QR er fjernet. En QR-kode til siden står igjen som reserve. Skjermen, nettsiden og
  tilkoblingsbildet forklarer hvert steg.
- VRM-kilde bygget og i drift 01.11: når Cerbo-en er online, hentes SOC, sol og AC-forbruk fra
  VRM-skyen hvert minutt (Graph-endepunktet, 1,6 kB), blå «Cerbo online»-etikett nederst, og
  automatisk tilbakefall til ren Lovable når Cerbo-en er borte. Målt på kortet: «vrm: brukt,
  60 s fersk». VRM godtar bare tilgangsnøkler; nøkkelen ligger i settings.toml på kortet og
  i C:\Get_SOC_VRM\vrm_token.txt. «Hvert 2. sekund» er ikke mulig over REST: kilden oppdateres
  hvert minutt, og sekundtall krever VRMs MQTT-kanal (ikke bygget).
- Henting hvert minutt (var hvert 2.). Nederst til høyre teller sekundene NED til neste
  henting («ny om 42 s», Nils-ønske 01.11: opptelling så død ut), og «henter» vises under
  selve hentingen. To Lovable-forsøk per runde, forrige bilde beholdes i inntil 3 min ved
  glipp, og VRM hentes uavhengig av Lovable-runden med klokke husket fra forrige portalsvar.
  Nye tall kommer uansett først når kildene oppdateres: VRM hvert minutt, Pi-en hvert 5.
- Star Wars-rulletekst: katalogen i `src/starwars.py` glir over bunnlinja hvert 10. minutt når
  dataene er ferske, tilfeldig startpunkt etter omstart. Sjekket på skjermbilde fra kortet.
- Konsollteksten skal ikke vises lenger: lyset er av til programmet har tegnet noe, og krasj gir
  en vanlig melding. Ikke sett på kortet ennå.
- Rotsertifikat for Lovable ligger i `src/portal_root.pem`, med kortets innebygde liste som reserve.
- Skrev skjermbilde-verktøy og tester: `tools/screenshot.py`, `tests/`.
- Slo av auto-reload etter at konsollen kom opp da kortet ble koblet til igjen. Skriving til
  disken stopper ikke lenger programmet.
- La inn krasj-vern: kortet starter på nytt etter 10 sekunder. Begge deler er testet på kortet.

- OTA fase 1 (01.11, versjon 0.1.0): `src/version.py`, `src/guard.py` (tegnevakt, 5 tester) og
  versjon synlig ved oppstart og i oppsettbildet. Benketest på kortet: en bevisst feil i `Screen.show`
  ga «tegning feilet» i loggen, og hentingen (VRM, minne) gikk videre i to runder. Rullet tilbake
  med ny deploy; `screen.py` på kortet er identisk med `src\`. «Tegnefeil»-reservebildet er ikke
  sett på skjermen, bare logget. 39 PC-tester passerer.

- OTA fase 2, koden (01.11, 61 PC-tester): `src/updater.py` (sone 0), `tools/publish.py`, `update.json`.
  `code.py` er nå en liten launcher (sone 0) og selve programmet ligger i `src/app.py`, slik at en
  syntaksfeil i en ny versjon gir omstart og dermed tilbakerulling (ellers står kortet stille).
  Kortet sjekker etter første vellykkede runde og så hver time; ved ny versjon lastes filer ned og
  sha256-sjekkes, forrige versjon legges i `ota/prev/`, tilstanden i `ota/state.json`. Ukvittert etter
  3 starter eller 4 min uten kvittering gir tilbakerulling, og versjonen merkes «bad» og hoppes over.
  Målt på kortet: hashlib sha256 og TLS mot raw.githubusercontent virker.
- Første lader-test 01.11 feilet: «Oppdaterer» kom aldri, og `ota/` fantes ikke etterpå. Årsak: planens
  premiss var feil. CircuitPython er skrivebeskyttet for kode som standard, også uten PC
  (`main.c` i 10.3.1). PC-testene kunne ikke se dette. Rettet: `updater.py` ber om skrivetilgang med
  `storage.remount` og låser igjen etterpå. I `boot.py` virker det alltid (USB har ikke startet); under
  kjøring nekter CircuitPython med PC tilkoblet (RuntimeError, målt), og oppdatereren hopper over seg selv.
- Testet på ekte kort med PC tilkoblet: `boot_check` talte opp i `boot.py`. Ekte nedlasting av 0.2.1
  (13,9 s) og tilbakerulling på tredje start i testmappa `/ot/`, med midlertidig remount. IKKE testet på
  ekte kort: `remount` under kjøring uten PC. Det sier bare kildekoden, så lader-testen må bekrefte det.
- Status vises nå på skjermen («Oppdatering: ...»), og grunnen til siste resultat ligger i `ota/last.txt`.
- Kjente begrensninger: en hengende (ikke krasjende) app gir ingen omstart; en god versjon kan
  rulles tilbake hvis Lovable er nede i over 4 min rett etter oppdatering (publiser da nytt versjonsnummer).
  Sikkerheten er GitHub-kontoen: slå på 2FA. Zone 1 over nett krever `tools\publish.py --allow-zone1`.

## Neste økt: start her
Les denne seksjonen og «OTA-status». `docs/HANDOVER_20261101.md` er utdatert: fase 0 til 3 er kjørt, og
dens påstand om at kortet kan skrive når det står i lader, er feil.

Tilstand ved øktslutt 01.11: kortet står i PC-en på COM7 med v0.2.4, lik `src\` og lik `update.json` på
`main`. Wifi TinnHytta og VRM-nøkkelen ligger fortsatt på kortet. Alt er committet og pushet.

Venter på Nils:
1. Skal VRM-nøkkelen bli med på kortet? (A3)
2. Skal kortet tømmes («tøm kortet») før det gis bort?
3. 2FA på GitHub-kontoen `nilsihlen`. Ikke bekreftet at det er på.
4. Vil Nils likevel se hele tilbakerullingen i lader før kortet gis bort? Publiser da en ødelagt versjon
   (0.2.5 eller høyere), og en ren versjon rett etterpå. Kortet må ikke stå i lader mens den ødelagte ligger ute,
   med mindre det er selve testen.

Slik publiserer du over nett:
1. Øk `src/version.py`, commit `src\`.
2. `python tools\publish.py` (`--allow-zone1` bare hvis Nils har godtatt risikoen). Commit og push `update.json`.
3. Vent til raw-URL-en viser ny versjon (tok ca. 10 s sist). Kortet sjekker ved oppstart og hver time, og bare
   når det ikke står i PC. Sone 0 (`boot.py`, `code.py`, `updater.py`) kan bare endres over USB.

Lært denne økta:
- Kortet er skrivebeskyttet for kode som standard, også i lader. `storage.remount` virker i `boot.py`, og under
  kjøring bare uten PC. PC-tester sier ingenting om dette: test skriving på ekte kort FØR Nils flytter det.
- Skriveløypa kan testes med PC tilkoblet: legg midlertidig `storage.remount("/", readonly=False)` sist i
  `boot.py`, overstyr `updater._usb_connected` og `updater._remount` fra REPL, og bruk `root="/ot/"`. Rydd etterpå.
- Hard omstart (`microcontroller.reset()`) trengs for å kjøre `boot.py`. Ctrl-D kjører den ikke.
- Lader gir ingen logg. Filtidene på kortet er tid siden strøm på (2000-01-01 00:00:00) og overlever omstart, så
  `os.stat` gir tidslinjen. `ota/last.txt` har siste resultat, og rulleteksten «Oppdatering: ...» viser det på skjermen.
- `tools\repl.py` sender kode linje for linje. Sendes alt i ett, mister kortet tegn.
- En testkjøring kan legge igjen `bad` i `ota/state.json`. Da avvises den versjonen, så bruk neste nummer.
- Slett ikke `/d/ota` med `rm -rf`: sikkerhetssjekken stopper det. Det kreves heller ikke.
- `gh` står aktivt på jobbkontoen `nilsihlen10n`. Push går med ren git via `github-nilsihlen`.

Åpent: hvorfor første runde tok 56 s i lader mot 17 s i PC. Mistanken er kald wifi eller et Lovable-forsøk som
tidsavbrøt, men det er ikke målt. Sammenlign `ota/last.txt`-tiden i lader med en kaldstart i PC.

## OTA-status 01.11: v0.2.4 på kortet og på GitHub
Nils stoppet testingen 01.11 og godtok risikoen: «Legg inn endelig versjon, så satser vi på at alt er bra.»
Planens port i fase 3 er derfor ikke fullt oppfylt.
- Sett i lader: kortet hentet v0.2.1 selv, byttet filene og kvitterte (`ota/state.json`). M1 er vist.
- Sett på ekte kort med PC tilkoblet: ødelagt `screen.py` med ukvittert flagg rullet tilbake på ca. 38 s med
  ekte omstarter. Ekte nedlasting og tilbakerulling er også kjørt i en testmappe.
- IKKE sett: hele løpet i lader, altså at kortet selv henter en ødelagt versjon og ruller tilbake. M2 er ikke
  bevist i lader. v0.2.3 var den planlagte testen, ble aldri hentet av kortet, og ble avløst av v0.2.4.
- Første oppstart i lader tok 56 s til første runde, mot 17 s i PC. Årsaken er ukjent. Ufarlig for oppdateringen.
- Versjonene 0.2.2 og 0.2.3 er brukt opp. Neste publisering må være 0.2.5 eller høyere.
- `ota/state.json` på kortet har en rest (`bad: 0.2.2`) fra USB-testen. Den er ufarlig.

## Plan
1. Koble kortet fra og til igjen, både i PC og lader, og se at konsollen ikke vises.
2. Test feil wifi-passord fra telefonen: skjerm og side skal si «Fikk ikke kontakt», og telefonen
   skal koble seg til igjen uten ny skanning.
3. Prøv den endelige skjermteksten med en bruker som ikke kjenner oppsettet, fra tomt kort.
4. Test på en Android-telefon.
5. Si «tøm kortet» rett før kortet gis bort, hvis det er satt opp på nytt. Da kjøres
   `tools\forget_wifi.py`, wifi-passordet forsvinner, og QR-koden kommer med en gang.
6. Repo og OTA er ferdig, se «OTA-status».
7. Andre åpne tester står i punkt 1 til 4.
8. Vurder senere: så 24-timerskurven fra VRM-historikk ved oppstart, og VRM MQTT for sekundtall.
9. Før kortet gis bort: avgjør om VRM-nøkkelen skal bli med på kortet (den som har kortet, kan
   lese den) eller fjernes fra settings.toml. Den kan alltid trekkes tilbake i VRM-portalen.

## Funn fra nettet 01.11
- iPhone viser ikke innloggingssiden etter wifi-kobling fra kameraet før Innstillinger > Wifi åpnes.
  Rapportert til Apple, ingen støttet løsning: developer.apple.com/forums/thread/852321
- To QR-koder, først wifi og så adressen, er et kjent mønster: robmiles.com/journal/2021/2/21/
- DHCP-valg 114 er ikke tilgjengelig i CircuitPython, og det finnes rapporter om at det ikke virket alene.
- Bluetooth uten app virker ikke i Safari på iPhone, så det krever en egen app.
- Skjemaet lagrer uten å teste nettet, så wifi hos mottakeren kan legges inn på forhånd.

## Åpne spørsmål
- Hvorfor koblet telefonen seg fra samme sekund som siden ble hentet 05:36:17?
- Hva gjorde at første lagring ga «No network with that ssid»? Valgt nett logges nå.
- Reservelista for sertifikat er ikke testet ende til ende, fordi Lovable ikke har byttet utsteder.
- Reserve-QR-en har ikke vært i bruk på ekte telefon.
- Grensene for SOC-farger er forslag: gul under 40 %, rød under 20 %.
- Hvorfor Windows-tilkoblingen utløste auto-reload er ikke bekreftet.
