import re
import discord
import aiohttp
import asyncio
import json
import sqlite3
from discord.ext import commands, tasks
from discord.ui import Button, View
from PIL import Image, ImageDraw, ImageOps
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
UPDATES_CHANNEL_ID = config["updates_channel_id"]

LOGFILE = "veilingmeester_log.txt"
DBFILE = "veilingmeester.db"

# Database setup
conn = sqlite3.connect(DBFILE)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS tracked_auctions (
    auction_id TEXT,
    lot_id TEXT,
    last_bid REAL,
    user_id TEXT
)
""")
conn.commit()
conn.close()

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
    check_auction_updates.start()

class FollowView(View):
    def __init__(self, auction_id, lot_id, bid_amount):
        super().__init__(timeout=None)
        self.auction_id = auction_id
        self.lot_id = lot_id
        self.bid_amount = bid_amount

    @discord.ui.button(label="🔨 Volg", style=discord.ButtonStyle.success)
    async def follow_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DBFILE)
        c = conn.cursor()
        c.execute("INSERT INTO tracked_auctions (auction_id, lot_id, last_bid, user_id) VALUES (?, ?, ?, ?)",
                  (self.auction_id, self.lot_id, self.bid_amount, str(interaction.user.id)))
        conn.commit()
        conn.close()
        await interaction.response.send_message("Je volgt dit kavel nu.", ephemeral=True)

    @discord.ui.button(label="❌ Stop Volgen", style=discord.ButtonStyle.danger)
    async def unfollow_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DBFILE)
        c = conn.cursor()
        c.execute("DELETE FROM tracked_auctions WHERE auction_id=? AND lot_id=? AND user_id=?",
                  (self.auction_id, self.lot_id, str(interaction.user.id)))
        conn.commit()
        conn.close()
        await interaction.response.send_message("Je volgt dit kavel niet meer.", ephemeral=True)

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

        deleted = await message.channel.purge(limit=amount + 1)
        confirm = await message.channel.send(f"🧻 Skibidi-purge uitgevoerd: {len(deleted)-1} berichten verwijderd.")
        await confirm.delete(delay=3)
    if "skibidi" in message.content.lower():
        await message.reply('toilet https://www.youtube.com/watch?v=WePNs-G7puA')
        await message.add_reaction("🚽")
        return

    if message.channel.id != ALLOWED_CHANNEL_ID:
        return

    start = datetime.now()
    log(f"Bericht ontvangen: {message.content}")

    try:
        if match := re.search(r'onlineveilingmeester\.nl/(?:nl/veilingen|en/auctions)/(\d+)/(?:kavels|lots)/(\d+)', message.content):
            await handle_ovm(message, match.group(1), match.group(2), start)
        else:
            await bot.process_commands(message)
    except Exception as e:
        log(f"❌ Onverwerkte fout: {e}")
        await message.reply("⚠️ Er ging iets mis bij het verwerken van je bericht.")

@tasks.loop(minutes=5)
async def check_auction_updates():
    conn = sqlite3.connect(DBFILE)
    c = conn.cursor()
    c.execute("SELECT DISTINCT auction_id, lot_id, last_bid FROM tracked_auctions")
    tracked = c.fetchall()
    for auction_id, lot_id, last_bid in tracked:
        url = f"https://www.onlineveilingmeester.nl/rest/nl/v2/veilingen/{auction_id}/kavels/{lot_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json()
        new_bid = float(data.get("hoogsteBod") or data.get("openingsBod") or 0)
        if new_bid > last_bid:
            c.execute("SELECT user_id FROM tracked_auctions WHERE auction_id=? AND lot_id=?", (auction_id, lot_id))
            users = c.fetchall()
            mentions = " ".join([f"<@{user[0]}>" for user in users])
            embed = discord.Embed(title="Nieuw bod geplaatst!",
                                  url=f"https://www.onlineveilingmeester.nl/nl/veilingen/{auction_id}/kavels/{lot_id}",
                                  description=f"Nieuw bod: € {new_bid:.2f}",
                                  color=discord.Color.green())
            channel = bot.get_channel(UPDATES_CHANNEL_ID)
            await channel.send(content=mentions, embed=embed)
            c.execute("UPDATE tracked_auctions SET last_bid=? WHERE auction_id=? AND lot_id=?",
                      (new_bid, auction_id, lot_id))
            conn.commit()
    conn.close()

# The rest of the functions like handle_ovm, compose_image_grid, strip_html, genereer_samenvatting should be added below as per the base implementation you provided
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

        bod = float(data.get("hoogsteBod") or data.get("openingsBod") or 0)
        veilingkosten = round(bod * (data.get("opgeldPercentage", 17) / 100), 2)
        handelingskosten = float(data.get("handelingskosten", 0) or 0)
        kosten_totaal = veilingkosten + handelingskosten
        btw = round((bod + kosten_totaal) * (data.get("btwPercentage", 21) / 100), 2)
        totaal = round(bod + kosten_totaal + btw, 2)

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
            f"🗓 **Sluit op:** {sluiting.strftime('%d/%m/%Y %H:%M')}"
        ]), inline=False)

        embed.add_field(name="💸 Kostenoverzicht", value="\n".join([
            f"💰 Bod: € {bod:.2f}",
            f"🧾 Veilingkosten ({data.get('opgeldPercentage', 17)}%): € {veilingkosten:.2f}",
            f"📦 Handelingskosten: € {handelingskosten:.2f}",
            f"🧾 BTW ({data.get('btwPercentage', 21)}%): € {btw:.2f}",
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

        view = FollowView(auction_id, lot_id, bod)
        
        if image_urls and (grid := await compose_image_grid(image_urls)):
            file = discord.File(grid, filename="preview.png")
            embed.set_image(url="attachment://preview.png")
            await message.reply(embed=embed, file=file, view=view)
        else:
            await message.reply(embed=embed, view=view)


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
    from PIL import ImageOps

    CANVAS_SIZE = 1200
    MAX_IMAGES = 9
    urls = urls[:MAX_IMAGES]

    async def fetch(session, url):
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    return Image.open(BytesIO(await resp.read())).convert("RGB")
        except Exception as e:
            log(f"Image error ({url}): {e}")
        return None

    async with aiohttp.ClientSession() as session:
        images = await asyncio.gather(*(fetch(session, url) for url in urls))

    images = [img for img in images if img]
    if not images:
        return None

    count = len(images)
    cols = 2 if count <= 4 else 3
    rows = (count + cols - 1) // cols

    tile_width = CANVAS_SIZE // cols
    tile_height = CANVAS_SIZE // rows

    grid = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), (255, 255, 255))

    for idx, img in enumerate(images):
        img.thumbnail((tile_width, tile_height), Image.LANCZOS)
        padded = ImageOps.pad(img, (tile_width, tile_height), color=(255, 255, 255), centering=(0.5, 0.5))
        x = (idx % cols) * tile_width
        y = (idx // cols) * tile_height
        grid.paste(padded, (x, y))

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
if __name__ == '__main__':
    bot.run(TOKEN)
