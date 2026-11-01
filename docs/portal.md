# Portaldata og wifi-oppsett

Kortet henter driftsbildet fra OD3-portalen over wifi. Det kobler seg aldri til Cerbo-en
direkte, og det sender aldri kommandoer. `/api/live` krever ingen nøkkel, så det ligger
ingen hemmelighet til portalen på kortet.

## Portalen
| Hva | Verdi |
|---|---|
| Adresse | `https://od3-foundation.lovable.app/api/live` |
| Størrelse | Ca. 13 kB. Tok 3,3 s på kortet, med ca. 1,9 MB ledig minne etterpå (01.11.2026) |
| Henting | Hvert minutt, Lovable og VRM i samme runde. Nederst til høyre teller sekundene ned til neste henting («ny om 42 s»), og «henter» står der mens den pågår |
| Robusthet | To forsøk mot Lovable per runde. Ved glipp beholdes forrige bilde i inntil 3 minutter («nytt forsok - 42»), så grånes det. VRM hentes uavhengig av Lovable-runden: klokka huskes fra forrige portalsvar. Er portalen nede over 10 minutter mens VRM lever, viser bunnlinja «portal 12 min» |
| Rotsertifikat | GTS Root R4, gyldig til 2036, i `src/portal_root.pem` |

Verifiseringen er alltid på. CircuitPython 10.3.1 godtar ikke Lovables rot med sin innebygde
liste, så kortet prøver `portal_root.pem` først. Feiler det, prøver det den innebygde lista,
som ble målt å virke for Let's Encrypt, Amazon og DigiCert (01.11.2026), men ikke for Google
Trust Services. Bytter Lovable til en utsteder ingen av dem kjenner, viser skjermen
`ingen portal`, og da må `src/portal_root.pem` byttes.

## VRM: ferskere tall når Cerbo-en er online
Når hyttas ruter står på, rapporterer Cerbo-en til Victrons VRM-sky omtrent hvert minutt.
Kortet henter da SOC, sol og AC-forbruk derfra i tillegg til Lovable, og viser en blå
`Cerbo online`-etikett nederst til venstre. Resten (fukt, aggregat, bankeffekt, operasjon)
kommer fortsatt fra Lovable og kan være opptil fem minutter eldre. Om vinteren er ruteren av,
Cerbo-en blir borte fra VRM, og kortet går selv tilbake til ren Lovable-visning uten etikett.

| Hva | Verdi |
|---|---|
| Endepunkt | `/v2/installations/<site>/widgets/Graph` med `attributeCodes[]` `bs`, `Pdc`, `a1`, siste kvarter. Ca. 1,6 kB |
| Takt | Hvert minutt, sammen med Lovable-hentingen. Kilden oppdateres uansett bare hvert minutt (målt 01.11.2026), så hyppigere spørring gir ingenting |
| Online-grense | Siste punkt yngre enn 180 s, ellers regnes Cerbo-en som offline |
| Klokke | Kortet har ingen egen klokke og bruker portalens `now` som epoketid for VRM-vinduet |
| Innlogging | VRM-tilgangsnøkkel i `settings.toml` på kortet (`VRM_TOKEN`, `VRM_SITE`). Passord godtas ikke lenger av VRM-API-et. Uten nøkkel er VRM-delen helt av, og kortet går på ren Lovable |
| TLS | VRM bruker Let's Encrypt, som kortets innebygde liste godtar |
| Sikkerhet | Nøkkelen kan leses av den som har kortet. Lag den i VRM-portalen under Preferences → Integrations → Access tokens, og trekk den tilbake der om kortet kommer på avveie. Reserven ligger i `C:\Get_SOC_VRM\vrm_token.txt`, utenfor repoet |

Ekte sekundtall finnes bare på VRMs MQTT-kanal og er ikke bygget. Et mulig neste steg er også å
så 24-timerskurven fra VRM-historikken ved oppstart, så den ikke starter tom.

## Kilder for tallene
| På skjermen | Felt i `/api/live` |
|---|---|
| SOC | `energy.<enhet>.sources.victron.soc_pct` |
| HVILE, LADER, TAPPER | `ovrige.batt_state` |
| `~-378 W` | `pv_w` + `batt_v` × `aggregat.dc_a` − `sources.device.p_w`, som `bankEffekt()` i portalen. Anslag: små DC-laster er ikke med |
| `5% om ca 17 t` | Avstand til neste grense × 130 Wh per prosent / bankeffekten. Grensene er nødlading 5 %, aggregatstopp 90 % og ellers 100 % |
| SOL W, LAST W | `pv_w`, `ovrige.ac_load_w` |
| AGGR W | `aggregat.ac_in_w` når `ovrige.ac_source` er 2, ellers `AV` |
| KJELLER % | `fukt.<enhet>.vinkjeller.doegntrend.til_rh_pct`. Rødt over `rh_grense_pct` |
| Detaljlinjen | Operasjon som kjører eller teknisk rom, og startbatteriet. Med aggregat: AC inn |
| Tid nederst til høyre | Alder på siste rapport, `now` − `last_report_at` |

`batt_w` og `batt_v` vises ikke som banktall, se FAKTA.md i OD3.
Fukten er siste verdi i døgntrenden, fordi rommålingen ofte er tom. Den kan være litt eldre
enn rapporten.
24-timerskurven ligger bare i RAM, så den starter tom etter omstart.

## Alarmer
`open_alerts` brukes ikke som friskmelding: vakta har vært av siden 19.10.2026, så lista er
tom uansett. Skjermen bygger på alderen på rapporten og verdiene selv.

## Skjermen
| Visning | Betydning |
|---|---|
| Farget bilde, grønn tid | Ferske data |
| SOC-tallet gult eller rødt | Under 40 % eller under 20 %. Grensene står i `src/screen.py` |
| Grått bilde, `rapport 3 t` | Portalen svarer, men Pi-en har ikke rapportert. Fristen er lovet neste vekking + 10 minutter |
| Grått bilde, `ingen portal, 5 min` | Wifi virker, men portalen svarer ikke |
| Grått bilde, `ingen wifi, 5 min` | Ikke på wifi |
| Rød skjerm, `INVERTER FEIL 17` | `vebus_error` er ikke 0 |
| Gul tekst glir over bunnlinja | Star Wars-sitat fra `src/starwars.py`, hvert 10. minutt når dataene er ferske. Driftslinjene kommer tilbake etterpå |

## Wifi-oppsett
1. Oppsettet åpnes selv når kortet får strøm uten lagret nett, eller ikke får kontakt i løpet
   av et drøyt halvt minutt ved oppstart. Ellers: hold BOOT inne i 3 sekunder mens
   driftsbildet vises.
2. På telefonen: åpne Wifi-innstillingene, velg `Skjerm` og skriv passordet fra skjermen.
   Passordet til dette nettet er fast for kortet, så telefonen kobler seg til igjen selv.
3. Siden kommer opp av seg selv. Kommer den ikke, viser skjermen en QR-kode og adressen.
4. Velg nett, skriv wifi-passordet og trykk Koble til. Kortet starter på nytt.

Kortet svarer på alle navneoppslag med sin egen adresse og sender telefonens internettsjekk til
siden, så telefonen viser den som en innloggingsside.

Wifi-QR brukes ikke: fra iPhone-kameraet kom siden aldri opp, også om telefonen hentet den i
bakgrunnen (`CaptiveNetworkSupport`). Det samme er meldt til Apple
(developer.apple.com/forums/thread/852321). Fra Wifi-innstillingene virket den på iPhone med
iOS 18.7, testet 01.11.2026: siden kom opp 7 sekunder etter tilkobling, og `Mozilla` i loggen
viser at den ble vist. En henting i loggen betyr ellers ikke at noen ser siden.
Android er ikke testet.
Får kortet ikke kontakt med nettet etter lagring, kommer oppsettet tilbake med feilmelding.
Konsollen logger hvert steg med `oppsett:`, så det går an å se hvor det stopper.

Hold aldri BOOT inne samtidig med RST: det sender kortet til ROM-bootloaderen.
Uten telefon går kortet tilbake etter 10 minutter og prøver det lagrede nettet.
Wifi-navn og wifi-passord ligger ukryptert i `microcontroller.nvm`. `settings.toml` brukes ikke.
