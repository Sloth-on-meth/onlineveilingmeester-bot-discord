import re
import discord
import aiohttp
import asyncio
import json
from discord.ext import commands
from PIL import Image, ImageDraw
from io import BytesIO
from datetime import datetime, timezone
import humanize
from bs4 import BeautifulSoup
import openai

# Laad config
with open("config.json") as f:
    config = json.load(f)

openai.api_key = config["openai_api_key"]
TOKEN = config["discord_token"]
ALLOWED_CHANNEL_ID = config["allowed_channel_id"]

LOGFILE = "veilingmeester_log.txt"

def log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    log(f"Aangemeld als {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.content.startswith("!purge"):
        parts = message.content.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.channel.send("Gebruik: `!purge <aantal>` (max 100)")
            return

        amount = int(parts[1])
        if amount < 1 or amount > 100:
            await message.channel.send("Geef een getal tussen 1 en 100.")
            return

        deleted = await message.channel.purge(limit=amount + 1)  # +1 om ook het commando zelf te verwijderen
        confirm = await message.channel.send(f"🧻 Skibidi-purge uitgevoerd: {len(deleted)-1} berichten verwijderd.")
        await confirm.delete(delay=3)
    if "skibidi" in message.content.lower():
        await message.reply('toilet https://www.youtube.com/watch?v=WePNs-G7puA')
        await message.add_reaction("🚽")  # Voeg hier de gewenste emoji toe
        return

    
    if message.channel.id != ALLOWED_CHANNEL_ID:
        return



    start = datetime.now()
    log(f"Bericht ontvangen: {message.content}")

    try:
        if match := re.search(r'onlineveilingmeester\.nl/(?:nl/veilingen|en/auctions)/(\d+)/(?:kavels|lots)/(\d+)', message.content):
            await handle_ovm(message, match.group(1), match.group(2), start)
        elif match := re.search(r'verkoop\.domeinenrz\.nl/[^ ]*?meerfotos=(K\d+)', message.content):
            await handle_drz(message, match.group(1), start)
        else:
            await bot.process_commands(message)
    except Exception as e:
        log(f"❌ Onverwerkte fout: {e}")
        await message.reply("⚠️ Er ging iets mis bij het verwerken van je bericht.")

async def handle_ovm(message, auction_id, lot_id, start):
    url = f"https://www.onlineveilingmeester.nl/rest/nl/v2/veilingen/{auction_id}/kavels/{lot_id}"
    log(f"OVM-data ophalen van {url}")

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                await message.reply("❌ Kan OVM-data niet ophalen.")
                return
            data = await resp.json()

    try:
        item = data.get("kavelData", {})
        title = item.get("naam", "(Geen titel)")
        description = strip_html(item.get("specificaties") or item.get("bijzonderheden") or item.get("product") or "Geen beschrijving.")
        image_urls = [f"https://www.onlineveilingmeester.nl/images/800x600/{path}" for path in data.get("imageList", [])]
        sluiting = datetime.fromisoformat(data["sluitingsDatumISO"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = sluiting - now

        try:
            bod = float(data.get("hoogsteBod") or data.get("openingsBod") or 0)
            kosten = round(bod * 0.17, 2)
            btw = round((bod + kosten) * 0.21, 2)
            totaal = round(bod + kosten + btw, 2)
        except Exception as e:
            log(f"❌ Fout bij bodberekening: {e}")
            bod = kosten = btw = totaal = 0.0

        topbieders = data.get("biedingen", [])[:3]
        samenvatting = await genereer_samenvatting(
            titel=title,
            beschrijving=description,
            fotos=image_urls,
            bod=bod,
            btw=btw,
            totaal=totaal,
            sluiting=sluiting.strftime('%d/%m/%Y %H:%M'),
            categorie=data.get("categorie", {}).get("naam", "Onbekend"),
            staat=item.get("conditie", "Onbekend"),
            verzendbaar="Ja" if data.get("isShippable", False) else "Nee",
            bouwjaar=item.get("bouwjaar", "Onbekend"),
            merk=item.get("merk", "Onbekend"),
            startbod=data.get("openingsBod", "??"),
            topbieders=topbieders
        )

        embed = discord.Embed(
            title=title,
            description=description[:2048],
            color=discord.Color.orange(),
            url=f"https://www.onlineveilingmeester.nl/nl/veilingen/{auction_id}/kavels/{lot_id}"
        )
        embed.add_field(name="🧠 AI Samenvatting", value=samenvatting, inline=False)

        embed.add_field(name="📋 Details", value="\n".join([
            f"💰 **Huidig bod:** € {bod:.2f},-",
            f"📈 **Startbod:** € {data.get('openingsBod', '??')},-",
            f"🔨 **Aantal biedingen:** {data.get('aantalBiedingen', '?')}",
            f"⏳ **Sluit over:** {'Gesloten' if delta.total_seconds() <= 0 else humanize.naturaldelta(delta)}",
            f"📅 **Sluit op:** {sluiting.strftime('%d/%m/%Y %H:%M')}"
        ]), inline=False)

        embed.add_field(name="💸 Kostenoverzicht", value="\n".join([
            f"💰 Bod: € {bod:.2f}",
            f"🧾 Veilingkosten (17%): € {kosten:.2f}",
            f"🧾 BTW (21%): € {btw:.2f}",
            f"💳 **Totaal te betalen:** € {totaal:.2f}"
        ]), inline=False)

        embed.add_field(name="📦 Extra informatie", value="\n".join([
            f"📂 **Categorie:** {data.get('categorie', {}).get('naam', 'Onbekend')}",
            f"🏷️ **Staat:** {item.get('conditie', 'Onbekend')}",
            f"🚚 **Verzendbaar:** {'Ja' if data.get('isShippable', False) else 'Nee'}",
            f"🛠️ **Bouwjaar:** {item.get('bouwjaar', 'Onbekend')}",
            f"🔧 **Merk:** {item.get('merk', 'Onbekend')}"
        ]), inline=False)

        top_bids = "\n".join([f"**{b.get('bieder', '?')}**: € {b.get('bedrag', '?')},-" for b in topbieders]) or "Nog geen biedingen."
        embed.add_field(name="👑 Topbieders", value=top_bids, inline=False)

        embed.add_field(name="⏱️ Verwerkingstijd", value=f"{(datetime.now() - start).total_seconds():.2f}s", inline=False)

        if image_urls and (grid := await compose_image_grid(image_urls)):
            file = discord.File(grid, filename="preview.png")
            embed.set_image(url="attachment://preview.png")
            await message.reply(embed=embed, file=file)
        else:
            await message.reply(embed=embed)

    except Exception as e:
        log(f"❌ OVM-fout: {e}")
        await message.reply("⚠️ Fout bij ophalen veilingdetails.")

async def handle_drz(message, lot_code, start):
    url = f"https://verkoop.domeinenrz.nl/verkoop_bij_inschrijving_2025-0009?meerfotos={lot_code}"
    log(f"DRZ-pagina ophalen: {url}")

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                await message.reply("❌ DRZ-pagina niet gevonden.")
                return
            html = await resp.text(encoding="windows-1252")

    try:
        soup = BeautifulSoup(html, "html.parser")
        item = soup.find("div", class_="catalogusdetailitem")
        if not item:
            await message.reply("❌ Geen details gevonden op DRZ.")
            return

        title = item.select_one("h4.title")
        description = strip_html(item.get_text(separator="\n", strip=True))
        images = [f"https://verkoop.domeinenrz.nl{img.get('data-hresimg')}" for img in item.select("img") if img.get("data-hresimg")]

        samenvatting = await genereer_samenvatting(
            titel=title.text.strip() if title else "(Geen titel)",
            beschrijving=description,
            fotos=images,
            bod=0.0,
            btw=0.0,
            totaal=0.0,
            sluiting="Onbekend",
            categorie="Onbekend",
            staat="Onbekend",
            verzendbaar="Onbekend",
            bouwjaar="Onbekend",
            merk="Onbekend",
            startbod="Onbekend",
            topbieders=[]
        )

        embed = discord.Embed(
            title=title.text.strip() if title else "(Geen titel)",
            description=("🧠 AI Samenvatting\n" + samenvatting),
            color=discord.Color.teal(),
            url=url
        )
        embed.add_field(name="Originele beschrijving", value=description[:2048])
        embed.add_field(name="⏱️ Verwerkingstijd", value=f"{(datetime.now() - start).total_seconds():.2f}s", inline=False)

        if images and (grid := await compose_image_grid(images)):
            file = discord.File(grid, filename="preview.png")
            embed.set_image(url="attachment://preview.png")
            await message.reply(embed=embed, file=file)
        else:
            await message.reply(embed=embed)

    except Exception as e:
        log(f"❌ DRZ-fout: {e}")
        await message.reply("⚠️ Fout bij ophalen DRZ-details.")

def strip_html(html: str) -> str:
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</p\s*>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<[^>]+>', '', html)
    return re.sub(r'\n+', '\n', html).strip()

async def compose_image_grid(urls: list[str]):
    TILE_SIZE = 400
    GRID_SIZE = 3
    CANVAS_SIZE = TILE_SIZE * GRID_SIZE

    async def fetch(session, url):
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    return Image.open(BytesIO(await resp.read())).convert("RGB")
        except Exception as e:
            log(f"Image error ({url}): {e}")
        return None

    async with aiohttp.ClientSession() as session:
        images = await asyncio.gather(*(fetch(session, url) for url in urls[:9]))

    images = [img.resize((TILE_SIZE, TILE_SIZE)) for img in images if img]
    if not images:
        return None

    grid = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), (255, 255, 255))
    draw = ImageDraw.Draw(grid)

    for i, img in enumerate(images):
        x = (i % GRID_SIZE) * TILE_SIZE
        y = (i // GRID_SIZE) * TILE_SIZE
        grid.paste(img, (x, y))
        draw.rectangle([x, y, x + TILE_SIZE - 1, y + TILE_SIZE - 1], outline="black", width=1)

    output = BytesIO()
    grid.save(output, format="PNG")
    output.seek(0)
    return output

async def genereer_samenvatting(titel, beschrijving, fotos, bod, btw, totaal, sluiting, categorie, staat, verzendbaar, bouwjaar, merk, startbod, topbieders):
    topbieders_str = "\n".join([f"{b.get('bieder', '?')}: € {b.get('bedrag', '?')},-" for b in topbieders]) or "Geen bieders"
    prompt = (
        f"Vat dit veilingobject samen in maximaal 50 woorden, in het Nederlands.\n"
        f"Titel: {titel}\n"
        f"Beschrijving: {beschrijving[:500]}\n"
        f"Aantal foto's: {len(fotos)}\n"
        f"Huidig bod: € {bod:.2f}\n"
        f"BTW: € {btw:.2f}\n"
        f"Totaal: € {totaal:.2f}\n"
        f"Sluit op: {sluiting}\n"
        f"Categorie: {categorie}\n"
        f"Staat: {staat}\n"
        f"Verzendbaar: {verzendbaar}\n"
        f"Bouwjaar: {bouwjaar}\n"
        f"Merk: {merk}\n"
        f"Startbod: {startbod}\n"
        f"Topbieders:\n{topbieders_str}"
    )

    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        log(f"❌ OpenAI-fout bij samenvatting: {e}")
        return "Samenvatting kon niet worden gegenereerd."

# Start de bot
bot.run(TOKEN)
