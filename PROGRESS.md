# PROGRESS

Sist oppdatert: 2026-11-01, OTA fase 0, 1 og kode for fase 2 ferdig. Neste: benketest i lader (fase 2/3), se «OTA-benketest» under.

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
  Målt på kortet: hashlib sha256 og TLS mot raw.githubusercontent virker; med PC på USB svarer
  oppdatereren «skrivebeskyttet» (OSError 30). Tørrkjøring på PC mot ekte GitHub-URL-er hentet 0.2.1.
- Kjente begrensninger: en hengende (ikke krasjende) app gir ingen omstart; en god versjon kan
  rulles tilbake hvis Lovable er nede i over 4 min rett etter oppdatering (publiser da nytt versjonsnummer).
  Sikkerheten er GitHub-kontoen: slå på 2FA. Zone 1 over nett krever `tools\publish.py --allow-zone1`.

## OTA-benketest (kortet står på 0.2.0, manifestet på 0.2.1)
1. Kortet i lader uten datalinjer. Forventet: «Oppdaterer til v0.2.1», restart, og «Programvare v0.2.1» glir over bunnlinja.
2. Kortet tilbake i PC: sjekk `version.py`, `ota/state.json` (pending false), at `screen.py` er lik `src\`.
3. Publiser ødelagt 0.2.2 (syntaksfeil i `screen.py`): kortet i lader skal bli mørkt, starte på nytt tre ganger og
   komme tilbake på 0.2.1. Etterkontroll: `ota/state.json` har `bad: 0.2.2`.

## Plan
1. Koble kortet fra og til igjen, både i PC og lader, og se at konsollen ikke vises.
2. Test feil wifi-passord fra telefonen: skjerm og side skal si «Fikk ikke kontakt», og telefonen
   skal koble seg til igjen uten ny skanning.
3. Prøv den endelige skjermteksten med en bruker som ikke kjenner oppsettet, fra tomt kort.
4. Test på en Android-telefon.
5. Si «tøm kortet» rett før kortet gis bort, hvis det er satt opp på nytt. Da kjøres
   `tools\forget_wifi.py`, wifi-passordet forsvinner, og QR-koden kommer med en gang.
6. Commit og opprett repo på Nils' private GitHub-konto, når Nils sier fra. Sjekk først at
   token-filer ikke er med (`.gitignore` har `token.txt`/`vrm_token.txt`).
7. OTA-plan skrevet 01.11 (`docs/PLAN_ota.md`): kortet henter kode selv fra GitHub, risikosoner,
   automatisk tilbakerulling, alt maskinvaretestes på benken FØR kortet gis bort (Nils har ett
   kort). Venter på A1-beslutning (offentlig repo + brukernavn) før fase 0. Tailscale på kortet
   er umulig: ingen OS.
8. Vurder senere: så 24-timerskurven fra VRM-historikk ved oppstart, og VRM MQTT for sekundtall.
8. Før kortet gis bort: avgjør om VRM-nøkkelen skal bli med på kortet (den som har kortet, kan
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
