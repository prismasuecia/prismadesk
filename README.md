# Prisma Desk

Prisma Desk är en lokal, manuellt styrd redaktionell radar för Prisma Suecia och ZUMA Press.

Systemet kör ingenting i bakgrunden. Det hämtar, analyserar och sparar fynd först när användaren trycker på `UPPDATERA DESK`.

## MVP

- Flask-dashboard med tydlig uppdateringsknapp.
- Källor i `config/sources.yaml`.
- RSS används där säkra flöden finns: Regeringen, Via TT, Stockholms stad via TT, Trafikverket och Riksdagen.
- Stora mediehus ligger som `media_signal`-källor via RSS och ska ses som signaler, inte primärkällor.
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

## Publicera på Render

1. Gå till Render och välj **New Web Service**.
2. Koppla GitHub-repot `prismasuecia/prismadesk`.
3. Render kan läsa `render.yaml` automatiskt.
4. Kontrollera att startkommandot är:

```bash
gunicorn app:app
```

5. Lägg in miljövariabler under **Environment** om de behövs.

```bash
PRISMA_SITE_URL=https://www.prismasuecia.se
ENABLE_MAIL=false
ENABLE_OPENAI=false
```

Första deployen använder SQLite på serverns filsystem. På gratisplaner kan databasen nollställas vid omstart eller ny deploy. För permanent drift bör Prisma Desk senare få Render Disk, Postgres eller annan persistent lagring.

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
