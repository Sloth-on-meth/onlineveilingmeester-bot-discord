# Discord Veilingbot

## 🇳🇱 Beschrijving

Deze Discord-bot herkent links van OnlineVeilingmeester.nl en DomeinenRZ.nl en toont automatisch veilinginformatie in een nette embed met afbeeldingen.

### Functionaliteiten

- Ondersteunt:
  - https://www.onlineveilingmeester.nl/nl/veilingen/VEILINGID/kavels/VOLGNUMMER
  - https://verkoop.domeinenrz.nl/...meerfotos=KXXXX
- Reageert met een zandloper terwijl de gegevens worden opgehaald.
- Toont een ✅ bij succes of ❌ bij een fout.
- Laat verwerkingstijd zien in seconden.
- Combineert tot 9 afbeeldingen in een raster.
- Logt alle activiteiten naar `veilingmeester_log.txt`.

### Installatie

1. Zorg dat je Python 3.9+ hebt geïnstalleerd.
2. Installeer de vereiste pakketten:

```bash
pip install -r requirements.txt
```

3. Voeg je Discord bot-token toe aan `token.secret` (enkel de token-string).
4. Start de bot:

```bash
python bot.py
```

### Vereisten

```text
discord.py
aiohttp
Pillow
beautifulsoup4
humanize
```

## 🇬🇧 Description

This Discord bot detects links to OnlineVeilingmeester.nl and DomeinenRZ.nl auctions and automatically posts detailed auction info in an embed with photos.

### Features

- Supports:
  - https://www.onlineveilingmeester.nl/en/auctions/VEILINGID/lots/VOLGNUMMER
  - https://verkoop.domeinenrz.nl/...meerfotos=KXXXX
- Shows ⏳ while fetching, ✅ when done, ❌ on error.
- Displays auction title, description, condition, price, shipping status, top bidders, and more.
- Combines up to 9 photos into a single grid.
- Logs everything to `veilingmeester_log.txt`.

### Setup

1. Make sure you have Python 3.9+ installed.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Put your Discord bot token in `token.secret` (just the token string).
4. Run the bot:

```bash
python bot.py
```

### Requirements

```text
discord.py
aiohttp
Pillow
beautifulsoup4
humanize
```
