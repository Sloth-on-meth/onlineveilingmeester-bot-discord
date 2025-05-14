# 🧠 Discord Auction Bot
![Python](https://img.shields.io/badge/python-3.10+-blue?logo=python)
![GPT-4o Vibe Coded](https://img.shields.io/badge/vibe--coded-GPT--4o-ff69b4?logo=openai)
![Discord Bot](https://img.shields.io/badge/discord-bot-5865F2?logo=discord)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

> **WARNING** ⚠️  
> THIS BOT WAS 100% VIBECODED USING GPT-4o. I HAVE NOT TYPED A SINGLE CHARACTER.

---

A Discord bot that watches for auction links, fetches relevant data from APIs or scraped pages, summarizes them using GPT-4o, and drops detailed embeds with cost breakdowns, live countdowns, and image grids. It also supports bid tracking with real-time ping notifications.

---

## 🔍 Supported Sources

- 🔹 **OnlineVeilingmeester.nl**
- 🔹 **Domeinenrz.nl**
- 🟡 *(Marktplaats support planned)*

---

## ✨ Features

- 🔗 **Auto-parses auction links in chat** (no slash commands)
- 🧠 **GPT-4o summaries** — concise descriptions in natural Dutch
- 🖼️ **Image grid previews** — maintains aspect ratio, max 9 images
- 💸 **Cost breakdowns** — bid, fees, VAT, total
- ⏳ **Closing time + countdown** — always in human-friendly format
- 🔘 **Follow/Unfollow buttons** — users can opt-in to ping alerts
- 🔔 **Bid tracking** — every 5 minutes the bot checks for updates
- 👥 **Per-user mentions** — no global spam
- 📤 **Logs sent to Discord** — errors and info go to your logchannel
- 🚽 **Skibidi filter** — meme auto-response with reaction

---

## 🛠️ Setup

### 1. Clone the repo
```bash
git clone https://github.com/yourname/discord-auction-bot.git
cd discord-auction-bot
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure `config.json`
```json
{
  "discord_token": "YOUR_DISCORD_BOT_TOKEN",
  "openai_api_key": "YOUR_OPENAI_API_KEY",
  "allowed_channel_id": 1234567890,
  "updates_channel_id": 1234567890,
  "log_channel_id": 1234567890,
  "allowed_role_id": 1234567890
}
```

### 4. Run the bot
```bash
python3 veilingmeester.py
```

---

## 🔨 Bid Tracking

Click the 🔨 **"Volg"** button on any auction embed to follow it.  
If a new bid is placed, you’ll get pinged in the **updates channel**.  
Click ❌ **"Stop Volgen"** to unfollow.  
Updates run every 5 minutes.

---

## 📸 Example Output

![embed-example](https://github.com/user-attachments/assets/c47911ae-9bdf-47d9-a072-701c6299fdb5)

---

## ⏱️ Performance Logs

Each summary is timed and displayed inside the embed:
```
🧠 AI: 5.98s  
🖼️ Image grid: 0.99s  
📦 Total: 8.18s  
```
All durations are logged to both file and Discord log channel.

---

## 🧪 Debug Tools

- `!testbid` — simulate a bid notification
- `!purge 10` — delete last 10 messages (admin-only)

---

## ❗ License & Disclaimer

- MIT licensed.
- This bot scrapes public pages and uses official APIs where available.
- Use responsibly. Not affiliated with any auction platform.

---

## 💡 Need More?

Want to add more sites? Get summaries in English? Integrate with webhooks?  
Fork it. Hack it. Or just vibe harder.

```
