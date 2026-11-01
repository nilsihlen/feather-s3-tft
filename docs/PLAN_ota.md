# PLAN – Fjernoppdatering (OTA)

- **Status:** utkast 01.11.2026 (Claude). Eier: Nils. Ingenting er bygget.
- **Kort fortalt:** kortet henter ny kode selv fra GitHub når Nils har publisert. Ingen
  åpne porter, ingen innlogging på kortet. Tailscale er umulig på en mikrokontroller, så
  retningen snus: kortet henter, Nils publiserer. Nils har ETT fysisk kort, så all
  maskinvaretesting skjer på benken før kortet gis bort.

## 1. Behov
- **B1:** Ny kode fra Nils' PC til kortet hos mottakeren, uten fysisk tilgang.
- **B2:** Bare utgående HTTPS fra kortet. Ingen åpne porter, ingenting å logge inn på.
- **B3:** Ingenting endres på kortet uten at Nils har sagt ja og publisert.
- **B4:** En feilslått oppdatering skal kunne reddes med «trekk ut støpselet og sett det inn
  igjen» hos mottakeren.
- **B5:** Ett kort: etter overleveringen finnes ingen maskinvare å teste på.

## 2. Målsetning
- **M1:** En publisert endring står på kortet innen en time, eller ved neste strømsyklus.
- **M2:** Automatisk tilbakerulling er BEVIST på benken: en bevisst ødelagt utgivelse ruller
  tilbake av seg selv, uten hjelp.
- **M3:** Kjernen (`boot.py` og oppdatereren) oppdateres aldri over nett.
- **M4:** Versjonsnummeret kan leses på skjermen, så det kan sjekkes over telefon.
- **M5:** Publisering er git push pluss manifest. Ingen nye tjenester.

## 3. Risikosoner
| Sone | Filer | Politikk |
|---|---|---|
| 0 Kjerne | `boot.py`, `updater.py` | Aldri over nett. Endres bare med kortet i USB her |
| 1 Drift | `code.py`, `netconfig.py`, `wifisetup.py` | Over nett bare i nødsfall etter overleveringen, se §7 |
| 2 Datatolking | `portal.py`, `vrm.py` | Over nett. Feil fanges allerede i drift |
| 3 Presentasjon | `screen.py`, `starwars.py` | Over nett, fritt og hyppig. Tegnefeil skal ikke kunne krasje kortet (fase 1) |

## 4. Utenfor planen
- Tailscale, SSH og CircuitPythons Web Workflow.
- Telemetri fra kortet og tilbake (kan vurderes senere).
- VRM MQTT og sanntid.
- To-kort-modellen. Gjenåpnes hvis Nils kjøper et kort til.

## 5. Beslutninger som trengs fra Nils
- **A1:** Offentlig GitHub-repo på Nils' private konto (anbefalt: koden har ingen
  hemmeligheter, de bor på kortet). Alternativet privat repo krever GitHub-nøkkel på kortet
  og frarådes. → Brukernavn og ja trengs før fase 0.
- **A2:** Sjekkfrekvens. Forslag: ved hver oppstart, og deretter hver time.
- **A3:** Hva som skjer med VRM-nøkkel og wifi før overleveringen (står også i PROGRESS §5 og §8).

## 6. Faser

### Fase 0 – Repo (Nils' ja først)
**Gjøres:** opprett offentlig repo, første commit, push. `.gitignore` nekter allerede
token-filer; sjekkes igjen før push.
**Sjekk:** raw-URL-en til en versjonsfil kan hentes uten innlogging.

### Fase 1 – Soneherding (på benken, i USB)
**Gjøres:** feilfangst rundt all tegning, slik at en tegnefeil viser reservetekst og logger,
mens henteløkka går videre. Versjonsnummer i `version.py`, synlig ved oppstart og i
oppsettbildet.
**Sjekk:** en bevisst tegnefeil på benken stopper ikke hentingen. Alle PC-tester passerer.

### Fase 2 – Oppdaterer (på benken, i lader)
**Gjøres:** `updater.py` + manifest `update.json` (versjon, soner, filer med sha256).
Kjøres fra oppstarten FØR hovedprogrammet, bare når kortet står i lader: CircuitPython kan
kun skrive til egen lagring når ingen PC holder USB-disken. Nedlasting verifiseres mot
sjekksum, forrige versjon beholdes, og et «uverifisert»-flagg settes. `code.py` kvitterer
flagget etter første vellykkede runde med henting og tegning. Oppstart med ukvittert flagg
ruller tilbake til forrige versjon. `boot.py` og `updater.py` står aldri i manifestet.
**Sjekk:** NB: i lader finnes ingen serielogg, så benketesten går med lader pluss skjermen,
og etterkontroll av filene med kortet i PC etterpå.

### Fase 3 – Generalprøve (på benken, i lader)
**Gjøres:** 1) publiser en ekte liten endring (et nytt sitat) og se den komme av seg selv.
2) publiser en bevisst ødelagt sone 3-utgivelse og se tilbakerullingen ta den.
**Sjekk:** M1 og M2 målt. Ikke før begge er sett, er OTA godkjent.

### Fase 4 – Overlevering
**Gjøres:** A3-beslutningene (VRM-nøkkel, wifi, «tøm kortet»), så gis kortet bort.
**Sjekk:** mottakeren ser driftsbildet, og versjonsnummeret stemmer over telefon.

## 7. Drift etter overleveringen, uten maskinvare
- Sone 2 og 3 publiseres etter PC-tester og kodegjennomgang. Tilbakerullingen er nettet.
- Sone 1 endres helst bare når kortet er på besøk hos Nils. Må det likevel skje over nett,
  aksepteres risikoen eksplisitt av Nils i forkant.
- Sone 0 endres aldri over nett. Punktum.
- Kan vurderes senere: skjermforhåndsvisning på PC (Blinka/pygame) for sone 3, og en enkel
  helsekanal ut fra kortet.
