# 🧠 Discord Auction Bot
![Python](https://img.shields.io/badge/python-3.10+-blue?logo=python)
![GPT-4o Vibe Coded](https://img.shields.io/badge/vibe--coded-GPT--4o-ff69b4?logo=openai)
![Discord Bot](https://img.shields.io/badge/discord-bot-5865F2?logo=discord)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

> **WARNING** ⚠️  
> THIS BOT WAS 100% VIBECODED USING GPT-4o. I HAVE NOT TYPED A SINGLE CHARACTER.

---

A Discord bot that watches for auction links, fetches relevant data from APIs or scraped pages, summarizes them using GPT-4o, and drops detailed embeds with costs, timers, and image grids.

---

## 🔍 Supported Sources

- 🔹 **OnlineVeilingmeester.nl**
- 🔹 **Domeinenrz.nl**

---

## ✨ Features

- 🔗 **Auto-parses auction links in chat**
- 🧠 **AI-generated summaries via GPT-4o**
- 🖼️ **Image grid previews** (maintains aspect ratios)
- 💸 **Automatic cost breakdown** (bid + fees + VAT)
- 🗓️ **Live countdown until closing time**
- ✅ **Follow/Unfollow buttons per auction**
- 🔔 **Bid tracking with user pinging**
- 🔐 **Channel-restricted replies**
- 🚽 **Built-in skibidi protection**

---

## 🛠️ Setup

### 1. Clone the repo
```bash
git clone https://github.com/yourname/discord-auction-bot.git
cd discord-auction-bot
```

### 2. install depedencies
```
pip install -r requirements.txt
```

### 3. configure your config.json
```
{
  "discord_token": "YOUR_DISCORD_BOT_TOKEN",
  "openai_api_key": "YOUR_OPENAI_API_KEY",
  "allowed_channel_id": YOUR_CHANNEL_ID,
  "updates_channel_id": YOUR_UPDATES_CHANNEL_ID,
  "logchannel": YOUR_LOG_CHANNEL_ID
}
```
### 4. run the bot
```
python3 veilingmeester.py
```



### bid tracking
Click the 🔨 "Volg" button on any auction embed to follow it.
If a new bid comes in, you’ll get pinged in the updates channel.
Click ❌ "Stop Volgen" to unfollow.


### 📸 Example Output
![embed-example](https://github.com/user-attachments/assets/c47911ae-9bdf-47d9-a072-701c6299fdb5)

