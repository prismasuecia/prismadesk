# Claude Review Brief: Prisma Desk

## Uppdrag

Gor en hard, konkret och redaktionellt intelligent review av Prisma Desk.

Prisma Desk ar ett manuellt styrt AI-newsroom-system for Prisma Suecia och ZUMA Press. Det ska inte publicera automatiskt och inte jobba i bakgrunden. Det ska bara analysera nar anvandaren trycker pa `UPPDATERA DESK`.

Målet ar att appen ska hjalpa en liten redaktion att inte missa:

- presstraffar
- pressinbjudningar
- ackrediteringsdeadlines
- viktiga nyhetslagen for spansktalande i Sverige
- Stockholm-baserade bildmojligheter for ZUMA Press
- stories som redan finns pa Prisma Suecia och darfor inte ska publiceras som nya

Var kritisk. Utga fran att varje missad presstraff, deadline eller stor visuell Stockholm-handelse ar ett allvarligt produktfel.

## Roller du ska granska utifran

Analysera appen fran tre perspektiv:

1. Nyhetschef for Prisma Suecia
2. Bildredaktor for ZUMA Press / Reuters-liknande bildbyralogik
3. Teknisk reviewer av Python/Flask-systemet

## Filer att lasa

Las framfor allt:

- `README.md`
- `AGENTS.md`
- `config/sources.yaml`
- `config/rules.yaml`
- `ai/classifier.py`
- `desk/scoring.py`
- `desk/update_runner.py`
- `feeds/rss_reader.py`
- `feeds/web_reader.py`
- `prisma_site/duplicate_checker.py`
- `templates/dashboard.html`
- `templates/item.html`
- `static/style.css`
- `tests/test_classifier.py`

## Viktig produktfilosofi

Prisma Desk ska vara en redaktionell radar, inte en automatisk publiceringsmaskin.

Systemet ska skrika nar nagot ar viktigt. Men det ska inte skrika for allt.

Det maste skilja mellan:

- akut pa-plats-lage
- bra Prisma-artikel
- bildide utan akut narvaro
- gammalt material
- bakgrundsmaterial
- redan publicerat
- ointressant brus

## Viktiga anvandarregler

Anvandaren finns i Stockholm och kan bara bevaka ZUMA pa plats inom Stockholms lan.

Det betyder:

- ZUMA pa-plats-lagen utanfor Stockholms lan ska normalt inte bli `AKUT NU`.
- Viktiga nationella nyheter utanfor Stockholm kan fortfarande vara relevanta for Prisma Suecia.
- Stockholm-handelser med internationellt bildvarde ska prioriteras mycket hogt.
- Gamla presstraffar, gamla RSS-poster och passerade events far aldrig visas som om de fortfarande ar akuta.

## Verkliga missar som maste analyseras

Analysera varfor Prisma Desk kunde missa eller felprioritera dessa:

### 1. Flygvapnet 100 ar over Stockholm

Den 1 juli 2026 firade Flygvapnet 100 ar med stor flyguppvisning over centrala Stockholm. Totalt deltog 54 luftfartyg, inklusive stridsflyg, transportflyg, helikoptrar och historiska flygplan.

Detta borde varit ett extremt starkt ZUMA-lage:

- Stockholm
- militart/forsvar
- unikt jubileum
- stark visuell händelse
- internationellt bildvarde
- tydlig publik synlighet

Fraga: vilka kallor, regler och datumlogik saknades for att faanga detta i tid?

### 2. Kungaparets brollopsdag / Stockholm-fest / ackreditering

Det fanns pressinbjudan/ackreditering kopplat till kungaparets brollopsdag och stor offentlig aktivitet i Stockholm.

Detta borde varit hogt:

- kungligt
- Stockholm city
- ackreditering
- foto/bildvarde
- ceremonier/offentlig fest

Fraga: varfor fangades inte ackrediteringsdeadline och bildpotential?

### 3. Liberalerna valmanifest i Stockholm

TT publicerade bild fran presstraff med Liberalernas partiledare Simona Mohamsson om valmanifest.

Detta borde ha varit ZUMA-relevant om platsen var Stockholm:

- valrorelse
- partiledare
- presstraff
- Stockholm
- bild pa partiledare/podie/pressuppbad

Fraga: vilka politiska källor saknas?

### 4. Presstraff om digitala miljeer / barns halsa

Socialminister Jakob Forssmed tog emot delbetankande om aldersgrans i digitala miljeer.

Detta har Prisma-varde:

- barn/familj
- socialminister
- digitala regler
- Sverige forklarat

Det kan ocksa ha ZUMA-feature-varde:

- barn och skarmar
- myndighetsbeslut
- polerade illustrationsbilder

Fraga: hur ska appen skilja mellan akut bildlage och bildforslag?

### 5. AI-ansiktsigenkanning i realtid

Riksdagsprocessen om polisens AI-ansiktsigenkanning ar relevant for Prisma Suecia och kan ge starka featurebilder for ZUMA.

Fraga: hur ska appen faanga riksdagssteg korrekt utan att visa gamla dokument som nya?

### 6. Gamla datum visas som aktuella

Appen har visat gamla presstraffar och gamla riksdagsdokument som `CURRENT` eller `UPCOMING`.

Exempel:

- gamla regeringspresstraffar fran april/maj
- gamla riksdagsdokument fran januari/februari
- presstraffar dar publiceringsdatum misstolkats som eventdatum

Fraga: hur ska datumlogiken for publiceringsdatum, eventdatum, deadline och "idag" forbattras?

## Svara pa dessa fragor

Ge en strukturerad review med rubrikerna nedan.

### 1. Storsta produktbristerna

Lista de viktigaste bristerna som gor att appen missar nyheter eller skriker pa fel saker.

### 2. Kallor som saknas

Ge konkret lista pa kallor som bor laggas till.

Prioritera sarskilt:

- regeringskalendrar
- kungahuset/royal calendar/press
- Forsvarsmakten events/press
- partiernas pressrum
- riksdagens kalender och pressrum
- Stockholm stad
- polis/aklagare/MSB
- sport och stora evenemang i Stockholm
- kultur och demonstrationer
- sociala medier-signaler som kan overvakas manuellt eller via RSS/externa sidor

For varje kalla: ange varfor den ar viktig och om den ar for ZUMA, Prisma eller bada.

### 3. ZUMA-bildlogik

Bedöm om appen tanker som en internationell bildbyra.

Den ska hoja:

- Stockholm + internationell person/organisation
- kungligt
- NATO/forsvar/militar
- valrorelse/partiledare
- demonstrationer
- kriser/stora olyckor med internationellt varde
- flyg, fartyg, militara uppvisningar
- stora sport- och kulturevenemang
- tydliga offentliga visuella miljoer

Den ska inte hoja:

- lokal olycka utan internationellt varde
- generiska utrikesnyheter utan svensk/Stockholm-koppling
- riksdagsdokument utan aktuell handelse
- webbartiklar som bara ar bakgrund

Foresla battre regler.

### 4. Prisma Suecia-logik

Bedöm om appen hittar ratt stories for spansktalande i Sverige.

Den ska hoja:

- migration
- arbetskraftsinvandring
- medborgarskap
- socialforsakring
- barnbidrag/bostadsbidrag
- skola/vard/1177
- polis/overvakning/rattigheter
- arbetsmarknad
- bostad/transport/vardagsekonomi
- latino-community och spansksprakig kultur i Sverige

Den ska krava forklarande vinkel, inte bara "det handlar om Sverige".

Foresla battre regler.

### 5. Datum- och tidslogik

Ge konkret forslag for hur appen ska skilja mellan:

- publiceringsdatum
- eventdatum
- deadline
- starttid
- passerad handelse
- gammal bakgrund
- ny utveckling i gammalt arende

Foresla hur gamla items ska degraderas eller doljas.

### 6. Ackreditering och tillstand

Hur ska appen hitta och prioritera:

- `ackreditering`
- `foranmalan`
- `RSVP`
- `anmälan senast`
- `presskort`
- `fototillfalle`
- `sista dag`

Foresla regler for nar `SOK_ACKREDITERING` ska visas.

### 7. UI och arbetsflode

Granska dashboarden som ett verktyg i en stressig redaktion.

Foresla:

- vilka kort som ska ligga overst
- vad som ska vara tydligare
- hur gamla saker ska markas
- hur bildforslag ska visas
- hur anvandaren snabbt ser "vad maste jag gora nu?"

### 8. Tester som saknas

Foresla konkreta testfall, till exempel:

- Stockholm + flyguppvisning + Forsvarsmakten = RED/ZUMA
- kungligt + ackreditering + Stockholm = RED/ZUMA
- partiledare + presstraff + Stockholm = ORANGE/RED ZUMA
- migration + riksdagsbeslut + idag = ORANGE/PRISMA
- gammal presstraff = inte CURRENT
- gammalt dokument med framtida amnesdatum = inte AKUT
- olycka utan internationellt varde = inte ZUMA

### 9. Teknisk risk

Bedöm:

- scraping-kvalitet
- RSS-kvalitet
- deduplicering
- SQLite-modell
- modulstruktur
- felhantering
- logging
- testbarhet
- risk for brus
- risk for missade deadlines

### 10. Prioriterad handlingsplan

Avsluta med en konkret handlingsplan:

- AKUT: maste fixas nu
- VIKTIGT: nasta iteration
- SENARE: bra men inte nodvandigt

Varje punkt ska vara sa konkret att en utvecklare kan implementera den.

## Format

Svara pa svenska.

Var hard men konstruktiv.

Ge hellre 20 konkreta forbattringar an 5 allmanna observationer.

Undvik fluff.

Målet ar att Prisma Desk ska bli mycket battre pa att aldrig missa stora Stockholm-bildlagen, presstraffar, ackrediteringsdeadlines eller viktiga Prisma Suecia-nyheter.
