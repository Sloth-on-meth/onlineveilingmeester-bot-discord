# 🧾 OnlineVeilingmeester Discord Bot

Een Discord-bot die automatisch veilinglinks van [Onlineveilingmeester.nl](https://www.onlineveilingmeester.nl) herkent en daar een nette embed van maakt met info uit hun REST API.

## ⚙️ Features

- Entirely vibecoded - letterlijk geen karakter hieraan is zelf getypt. ja, misschien de token. fuck, ouwe
- Herkent veilinglinks automatisch in berichten
- Haalt data op via de officiële REST API
- Genereert een nette Discord embed met:
  - Titel en korte beschrijving
  - 💰 Hoogste bod
  - 📈 Startbod
  - 🔨 Aantal biedingen
  - ⏳ Tijd tot sluiting
  - 📅 Exacte sluitdatum (`DD/MM/YYYY HH:MM`)
- Downloadt tot 9 foto's en toont ze als een collage

## 📦 Installatie

```bash
git clone https://github.com/jouw-gebruikernaam/onlineveilingmeester-discord-bot.git
cd onlineveilingmeester-discord-bot
pip install -r requirements.txt
```

Maak vervolgens een bestand `token.secret` aan met daarin jouw Discord bot token:

```
MTA... <-- je echte token hier, zonder aanhalingstekens
```

Start de bot:

```bash
python bot.py
```

## 🧰 Vereisten

- Python 3.8+
- `discord.py`
- `aiohttp`
- `requests`
- `pillow`
- `humanize`

Installeer eventueel handmatig via:

```bash
pip install discord.py aiohttp pillow requests humanize
```

## 📜 Licentie

MIT — gebruik vrij, aanpassingen welkom.
