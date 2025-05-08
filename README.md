# Auction discord bot

A Discord bot that automatically parses and responds to auction links from:

- [OnlineVeilingmeester.nl](https://www.onlineveilingmeester.nl)
- [verkoop.domeinenrz.nl](https://verkoop.domeinenrz.nl)

## ✨ Features

- Detects Dutch *and* English auction links
- Automatically fetches auction data via REST or scraping
- Parses title, description, bids, dates, and extra metadata
- Builds image grids (max 9 thumbnails) and includes them in an embed
- Responds to the original message as a threaded reply
- Reacts to the source message with ✅ when processed

## 🧠 Tech Stack

- `discord.py`
- `aiohttp`
- `Pillow`
- `BeautifulSoup`
- `humanize`

## ⚠️ Important

Every single character in this bot was generated via ChatGPT.  
No hand-typed code. No human debugging. Just pure `vibecoded`.

## 🚀 Usage

1. Clone this repo
2. Add your bot token in a file named `token.secret`
3. Run:

```bash
pip install -r requirements.txt
python bot.py
