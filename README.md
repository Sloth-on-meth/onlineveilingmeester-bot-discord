# Veilingmeester Discord Bot

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

Plaats je OpenAI- en Discord-token in de volgende bestanden:

```
token.secret         # Discord bot token
openai.secret        # OpenAI API key (v1-stijl, géén legacy)
```

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
