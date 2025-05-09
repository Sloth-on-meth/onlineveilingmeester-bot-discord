# Veilingmeester Discord Bot


# WARNING - THIS BOT WAS 100% VIBECODED USING GPT4.0. I HAVE NOT TYPED A SINGLE CHARACTER. 




Deze bot verwerkt automatisch veilinglinks van:

* [OnlineVeilingmeester.nl](https://www.onlineveilingmeester.nl/)
* [Domeinenrz.nl](https://verkoop.domeinenrz.nl)

Bij het plaatsen van een link in een Discord-kanaal, genereert de bot automatisch een embed met:

* Titel, sluitingsdatum, huidige bod, kosten en BTW
* Afbeeldingen in een nette 3x3 preview grid (1200×1200 px met zwarte rand)
* 🧠 **AI-samenvatting** van het object via OpenAI `gpt-4o`
* 📄 Volledige omschrijving (originele tekst van de aanbieder)

## Vereisten

Python 3.10+

Installeer dependencies:

```bash
pip install -r requirements.txt
```

## Secrets

Plaats je OpenAI- en Discord-token, en kanaal waar de bot in moet reageren in config.json


## Starten

```bash
python bot.py
```

De bot luistert automatisch op nieuwe berichten met veilinglinks.

## Features

* ✅ Ondersteuning voor OVM + DomeinenRZ
* ✅ Inline AI-samenvatting in het Nederlands (gpt-4o)
* ✅ Afbeeldingsgrid met 1px zwarte borders
* ✅ Netto veilingprijsberekening incl. 17% kosten en 21% btw
