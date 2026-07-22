# Prisma Desk

Prisma Desk är en lokal, manuellt styrd redaktionell radar för Prisma Suecia och ZUMA Press.

Systemet kör ingenting i bakgrunden. Det hämtar, analyserar och sparar fynd först när användaren trycker på `UPPDATERA DESK`.

## MVP

- Flask-dashboard med tydlig uppdateringsknapp.
- Källor i `config/sources.yaml`.
- RSS används där säkra flöden finns: Regeringen, Via TT, Stockholms stad via TT, Trafikverket, Riksdagen, Försvarsmakten/Mynewsdesk, MCF/Mynewsdesk och Polisen Stockholm.
- Stora mediehus ligger som `media_signal`-källor via RSS och ska ses som signaler, inte primärkällor.
- Prisma-profilerade webbsök via Google News RSS finns som manuella signalkällor för migration, arbete/ekonomi, lagar, myndighetsvardag och latino/kultur. De ska alltid kontrolleras mot primärkälla innan publicering.
- Riksdagens kammarkalender läses som iCalendar från `https://data.riksdagen.se/kalender/?org=kamm&utformat=icalendar`.
- Regelbaserad klassificering i `ai/classifier.py`.
- SQLite-lagring i `data/prisma_desk.sqlite3`.
- Dubblettspärr via item-hash.
- Prisma Suecia-kontroll mot senaste rubriker på `PRISMA_SITE_URL`.
- Förberett one.com IMAP-stöd, inaktivt tills `.env` aktiverar det.
- OpenAI-prompt för framtida klassificering, men MVP kör regler först.

## Starta lokalt

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Öppna:

http://127.0.0.1:5050

## Privat online-version

Prisma Desk kan köras online bakom lösenord så att du kan öppna den från mobilen ibland. Sätt alltid lösenord i hostingmiljön:

```bash
PRISMA_DESK_PASSWORD=ett-långt-eget-lösenord
PRISMA_DESK_SECRET_KEY=en-lång-slumpad-hemlighet
PRISMA_SITE_URL=https://www.prismasuecia.se
ENABLE_MAIL=false
ENABLE_OPENAI=false
```

När `PRISMA_DESK_PASSWORD` är satt kräver dashboarden inloggning. Appen skickar även `noindex`-headers och meta-taggar så sökmotorer inte ska indexera sidan.

### Render

Repo:t innehåller `render.yaml`, så Render kan skapa en webbtjänst direkt från GitHub.

1. Skapa **New Web Service** på Render.
2. Koppla `prismasuecia/prismadesk`.
3. Sätt `PRISMA_DESK_PASSWORD` under **Environment**.
4. Deploya.

Startkommandot är:

```bash
gunicorn app:app
```

Obs: gratisplaner kan ha temporärt filsystem. SQLite-databasen kan därför nollställas vid omstart eller ny deploy. För längre drift bör appen senare få persistent disk eller Postgres.

## Gammal MacBook som Prisma Desk-skärm

Det rekommenderade lokala upplägget är att låta en gammal MacBook köra Prisma Desk självständigt:

- servern startar automatiskt vid inloggning
- sidan öppnas i webbläsaren
- MacBooken står på skrivbordet som newsroom-monitor
- systemet uppdateras bara när du trycker på `UPPDATERA DESK`

### Installera på MacBooken

1. Klona eller ladda ner GitHub-repot på MacBooken.
2. Gå in i projektmappen.
3. Kör:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
./scripts/install_mac_autostart.sh
```

4. Öppna dashboarden:

```bash
./scripts/open_prisma_desk.command
```

Efter installation startar servern automatiskt vid inloggning och hålls igång av macOS `launchd`.

### Kontrollera servern

```bash
launchctl list | grep prismadesk
curl -I http://127.0.0.1:5050/
```

Loggar finns här:

```bash
logs/prisma-desk.out.log
logs/prisma-desk.err.log
```

### Stoppa autostart

```bash
launchctl unload ~/Library/LaunchAgents/se.prismasuecia.prismadesk.plist
```

### Starta igen

```bash
launchctl load ~/Library/LaunchAgents/se.prismasuecia.prismadesk.plist
```

### Mac-inställningar för desk-skärm

- Ha laddaren inkopplad.
- Stäng av viloläge när datorn har ström.
- Lägg `scripts/open_prisma_desk.command` i **System Settings → General → Login Items**.
- Sätt Safari/Chrome i helskärm med Prisma Desk öppet.
- Stäng av störande notiser eller använd Fokus-läge.
- Aktivera automatisk inloggning om MacBooken bara ska vara desk-skärm.
- Starta om MacBooken en gång och kontrollera att sidan kommer upp igen.

## Testa reglerna

```bash
python -m unittest discover -s tests
```

## Konfiguration

Känsliga uppgifter ska ligga i `.env`, aldrig i koden.

```bash
OPENAI_API_KEY=
PRISMA_MAIL_HOST=imap.one.com
PRISMA_MAIL_PORT=993
PRISMA_MAIL_USER=
PRISMA_MAIL_PASSWORD=
PRISMA_SITE_URL=https://www.prismasuecia.se
ENABLE_MAIL=false
ENABLE_OPENAI=false
```

Första versionen använder inte OpenAI automatiskt. Sätt inte `ENABLE_MAIL=true` förrän mailuppgifterna finns på plats.

## Manuell körordning

När `UPPDATERA DESK` trycks gör systemet detta:

1. Hämtar senaste publicerade artiklar från prismasuecia.se.
2. Skapar intern lista över redan publicerade ämnen.
3. Hämtar alla definierade källor i `sources.yaml`.
4. Läser eventuella nya mail från one.com IMAP om mail är aktiverat.
5. Extraherar rubrik, datum, URL, källa och snippet.
6. Tar bort exakta dubletter.
7. Klassificerar varje fynd.
8. Kontrollerar mot Prisma-dubbletter.
9. Räknar prioritetspoäng.
10. Sparar fynd i SQLite.
11. Visar dashboard.

## Viktigt

Prisma Desk får bara föreslå åtgärder. Det ska inte publicera, skicka mail, ansöka om ackreditering eller köra autonomt i bakgrunden.

## Framtida versioner

- Telegram alerts.
- Automatisk briefing-export.
- Kalender för ackrediteringar.
- PDF/Markdown-export.
- Artikelutkast på spanska.
- ZUMA-caption-generator.
- WordPress-integration.
- Bättre semantisk dubblettkontroll.
