# 🧠 Discord Auction Bot — Veilingmeester Edition


###THIS BOT WAS AUTOMATICALLY GENERATED WITH CHATGPT IN ITS ENTIRETY AS AN EXPERIMENT. it was guided by me, but i did not type a single character manually. BE WARNED!


This Discord bot automatically scans messages for Dutch auction links (OnlineVeilingmeester.nl and DomeinenRZ.nl) and drops clean, image-rich embed previews with real-time data. It's async, it's snappy, it's got emojis. It's your auction butler in the chat.

---

## ⚙️ Features

- 🧠 Detects and parses auction listings from:
  - `onlineveilingmeester.nl/nl/veilingen/.../kavels/...`
  - `verkoop.domeinenrz.nl/...meerfotos=Kxxxx`
- 📦 Displays detailed info: title, description, condition, bids, shipping, close time, top bidders, etc.
- 🖼️ Combines up to 9 images into a grid preview.
- ⏳ Shows a loading emoji while processing, then ✅ or ❌ depending on success.
- 🕵️ Logs everything to `veilingmeester_log.txt` for debugging or just vibing on what it's doing.
- ⏱️ Shows how long it took to process the listing in each embed.

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone <your-repo>
cd your-repo
pip install -r requirements.txt
```

### 2. Add Your Bot Token

Create a file named `token.secret` (yes, literally that name) in the root directory.  
Put your bot token in that file — just the raw token string, nothing else.

```
MTAxMjM0NTY3ODkw.YZABCD.FakeTokenStringHere123456
```

Don't commit this. I swear.

### 3. Run It

```bash
python bot.py
```

You should see something like:

```
[2025-05-08 20:32:15] Bot ingelogd als VeilingBot#0420
```

### 4. Drop Auction Links in Discord

Paste any supported auction link into any channel the bot can read.  
You’ll see a nice embed with photos, status, and even the latest bids.

---

## 🔗 Requirements

You're good with the latest versions of these:

```
discord.py
aiohttp
Pillow
beautifulsoup4
humanize
```

Already included in the `requirements.txt`.

---

## 🛠️ Logging

All activity is saved in `veilingmeester_log.txt` — each line timestamped.  
You can tail it, grep it, or just read it like a novel about second-hand dishwashers and seized trailers.

---

## 💬 Support

Built by nerds for nerds. If it breaks, blame async.  
If it works, consider screaming “GEWELDIG BOD!” into the void.

---

## ✨ License

MIT. Do what you want, just don’t turn it into an NFT.
