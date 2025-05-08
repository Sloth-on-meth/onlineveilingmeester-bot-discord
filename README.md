# 🧠 VeilingBot

Een Discord-bot die automatisch informatie ophaalt bij:

* [onlineveilingmeester.nl](https://www.onlineveilingmeester.nl)
* [verkoop.domeinenrz.nl](https://verkoop.domeinenrz.nl)

Wanneer iemand een link plaatst naar een kavel op een van deze sites, genereert de bot automatisch een mooie Discord embed met:

* Titel en beschrijving
* Sluitingsdatum en tijd
* Actueel bod + kostenoverzicht
* Biedhistorie (OVM)
* Belangrijke eigenschappen zoals verzendbaarheid, merk, staat
* Een 3x3 afbeeldingsgrid van de foto's

## 🔧 Features

* Automatische parsing van URLs in berichten
* Live data ophalen via REST of HTML scraping
* Realtime kostencalculatie (bod + veilingkosten + btw)
* Verwerkingstijdmeting
* Inline afbeeldingengrid (max 9 afbeeldingen)
* Logging van alle activiteiten naar `veilingmeester_log.txt`
* Schattige AI-reacties op het woord "skibidi" 🧻

## ⚙️ Installatie

1. Zorg dat je Python 3.10+ hebt.
2. Installeer dependencies:

   ```bash
   pip install -r requirements.txt
   ```
3. Maak een `token.secret` bestand aan met je Discord bot-token:

   ```
   echo "YOUR_BOT_TOKEN" > token.secret
   ```
4. Start de bot:

   ```bash
   python main.py
   ```

## 📦 Vereisten

* `discord.py`
* `aiohttp`
* `Pillow`
* `beautifulsoup4`
* `humanize`

Je kunt dit alles installeren met:

```bash
pip install discord.py aiohttp pillow beautifulsoup4 humanize
```

## 📝 Credits

**100% ChatGPT VibeCode™**

Ik (Sam) heb 0,0 zelf getypt aan deze bot, behalve dan `skibidi`.
De rest is AI-magic. 🌟
Spaghetti verzekerd, maar hij werkt. 🤘

## 📄 Licentie

Doe ermee wat je wil. Liever geen production-grade bots op draaien tenzij je weet wat je doet.
Of niet. Ik ben niet je moeder.
