import re
import discord
import aiohttp
import asyncio
from discord.ext import commands
from PIL import Image
from io import BytesIO
from datetime import datetime, timezone
import humanize
from bs4 import BeautifulSoup

# === Config ===
with open("token.secret", "r") as f:
    TOKEN = f.read().strip()

LOGFILE = "veilingmeester_log.txt"

def log(text):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {text}\n")

# === Bot Setup ===
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    log(f"Bot ingelogd als {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    start_time = datetime.now()
    try:
        await message.add_reaction("⏳")
        log(f"Bericht ontvangen: {message.content}")

        content = message.content

        ovm_match = re.search(
            r'onlineveilingmeester\.nl/(?:nl/veilingen|en/auctions)/(\d+)/(?:kavels|lots)/(\d+)',
            content
        )
        if ovm_match:
            await handle_ovm(message, ovm_match.group(1), ovm_match.group(2), start_time)
            return

        drz_match = re.search(
            r'verkoop\.domeinenrz\.nl/[^ ]*?meerfotos=(K\d+)',
            content
        )
        if drz_match:
            await handle_drz(message, drz_match.group(1), start_time)
            return

        await bot.process_commands(message)

    except Exception as e:
        log(f"❌ Onverwerkte fout in on_message: {e}")
        await message.clear_reaction("⏳")
        await message.add_reaction("❌")
        await message.reply("⚠️ Er ging iets mis bij het verwerken van je bericht.")

async def handle_ovm(message, veiling_id, volgnummer, start_time):
    api_url = f"https://www.onlineveilingmeester.nl/rest/nl/v2/veilingen/{veiling_id}/kavels/{volgnummer}"
    log(f"Verzoek naar OVM API: {api_url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    await message.reply("API request faalde.")
                    await message.clear_reaction("⏳")
                    await message.add_reaction("❌")
                    return
                data = await resp.json()

        kavel = data.get('kavelData', {})
        title = kavel.get('naam', 'Onbekende titel')
        description = strip_html(
            kavel.get('specificaties') or
            kavel.get('bijzonderheden') or
            kavel.get('product') or
            "Geen beschrijving beschikbaar."
        )

        price = f"€ {data.get('hoogsteBod', '??')},-"
        start_price = f"€ {data.get('openingsBod', '??')},-"
        bid_count = data.get('aantalBiedingen', '?')
        image_paths = data.get("imageList", [])
        image_urls = [f"https://www.onlineveilingmeester.nl/images/800x600/{path}" for path in image_paths]

        sluit_iso = data.get("sluitingsDatumISO")
        sluit_dt = datetime.fromisoformat(sluit_iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = sluit_dt - now
        sluiting_over = "Gesloten" if delta.total_seconds() <= 0 else f"over {humanize.naturaldelta(delta)}"
        sluiting_exact = sluit_dt.strftime("%d/%m/%Y %H:%M")

        categorie = data.get('categorie', {}).get('naam', 'Onbekend')
        conditie = kavel.get('conditie', 'Onbekend')
        verzendbaar = "Ja" if data.get('isShippable', False) else "Nee"
        bouwjaar = kavel.get('bouwjaar', 'Onbekend')
        merk = kavel.get('merk', 'Onbekend')

        extra_info = (
            f"📦 **Categorie:** {categorie}\n"
            f"🏷️ **Conditie:** {conditie}\n"
            f"🚚 **Verzendbaar:** {verzendbaar}\n"
            f"🛠️ **Bouwjaar:** {bouwjaar}\n"
            f"🔧 **Merk:** {merk}"
        )

        biedingen = data.get('biedingen', [])
        top_bieders = []
        for b in biedingen[:3]:
            naam = b.get('bieder', '???')
            bedrag = f"€ {b.get('bedrag', '?')},-"
            top_bieders.append(f"**{naam}**: {bedrag}")
        bieders_text = "\n".join(top_bieders) if top_bieders else "Geen biedingen gevonden."

        embed = discord.Embed(
            title=title,
            description=description[:2048],
            color=discord.Color.orange(),
            url=f"https://www.onlineveilingmeester.nl/nl/veilingen/{veiling_id}/kavels/{volgnummer}"
        )

        details_text = (
            f"💰 **Hoogste bod:** {price}\n"
            f"📈 **Startbod:** {start_price}\n"
            f"🔨 **Biedingen:** {bid_count}\n"
            f"⏳ **Sluit over:** {sluiting_over}\n"
            f"📅 **Sluit op:** {sluiting_exact}"
        )

        embed.add_field(name="Details", value=details_text, inline=False)
        embed.add_field(name="Extra info", value=extra_info, inline=False)
        embed.add_field(name="Laatste biedingen", value=bieders_text, inline=False)

        duration = (datetime.now() - start_time).total_seconds()
        embed.add_field(name="⏱️ Verwerkingstijd", value=f"{duration:.2f} seconden", inline=False)

        if image_urls:
            grid_img = await compose_image_grid(image_urls)
            if grid_img:
                file = discord.File(grid_img, filename="fotos.png")
                embed.set_image(url="attachment://fotos.png")
                await message.reply(embed=embed, file=file)
                await message.clear_reaction("⏳")
                await message.add_reaction("✅")
                return

        await message.reply(embed=embed)
        await message.clear_reaction("⏳")
        await message.add_reaction("✅")

    except Exception as e:
        log(f"❌ Fout OVM: {e}")
        await message.clear_reaction("⏳")
        await message.add_reaction("❌")
        await message.reply("⚠️ Kon OVM-details niet ophalen.")

async def handle_drz(message, kavelnummer, start_time):
    url = f"https://verkoop.domeinenrz.nl/verkoop_bij_inschrijving_2025-0009?meerfotos={kavelnummer}"
    log(f"Verzoek naar DRZ-pagina: {url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await message.reply("DRZ-pagina niet gevonden.")
                    await message.clear_reaction("⏳")
                    await message.add_reaction("❌")
                    return
                html = await resp.text(encoding="windows-1252")

        soup = BeautifulSoup(html, "html.parser")
        block = soup.find("div", class_="catalogusdetailitem")
        if not block:
            await message.reply("Kon DRZ-detail niet vinden.")
            await message.clear_reaction("⏳")
            await message.add_reaction("❌")
            return

        title = block.select_one("h4.title").get_text(strip=True) if block.select_one("h4.title") else "Geen titel"
        description = block.get_text(separator="\n", strip=True)
        description = strip_html(description)

        img_tags = block.select("img")
        image_urls = [
            f"https://verkoop.domeinenrz.nl{img.get('data-hresimg')}"
            for img in img_tags if img.get("data-hresimg")
        ]

        embed = discord.Embed(
            title=title,
            description=description[:2048],
            color=discord.Color.teal(),
            url=url
        )

        duration = (datetime.now() - start_time).total_seconds()
        embed.add_field(name="⏱️ Verwerkingstijd", value=f"{duration:.2f} seconden", inline=False)

        if image_urls:
            grid_img = await compose_image_grid(image_urls)
            if grid_img:
                file = discord.File(grid_img, filename="fotos.png")
                embed.set_image(url="attachment://fotos.png")
                await message.reply(embed=embed, file=file)
                await message.clear_reaction("⏳")
                await message.add_reaction("✅")
                return

        await message.reply(embed=embed)
        await message.clear_reaction("⏳")
        await message.add_reaction("✅")

    except Exception as e:
        log(f"❌ Fout DRZ: {e}")
        await message.clear_reaction("⏳")
        await message.add_reaction("❌")
        await message.reply("⚠️ Kon DRZ-pagina niet ophalen.")

def strip_html(html):
    if not html:
        return ""
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</p\s*>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<[^>]+>', '', html)
    html = re.sub(r'\n+', '\n', html)
    return html.strip()

async def compose_image_grid(image_urls, grid_cols=None):
    images = []

    async def fetch_image(session, url):
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    img = Image.open(BytesIO(data)).convert("RGB")
                    return img
        except Exception as e:
            log(f"Fout bij afbeelding {url}: {e}")
        return None

    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*(fetch_image(session, url) for url in image_urls[:9]))

    images = [img.resize((300, 300)) for img in results if img]

    if not images:
        return None

    count = len(images)
    grid_cols = grid_cols or (3 if count > 4 else 2)
    rows = (count + grid_cols - 1) // grid_cols

    grid_img = Image.new('RGB', (grid_cols * 300, rows * 300), color=(255, 255, 255))
    for idx, img in enumerate(images):
        x = (idx % grid_cols) * 300
        y = (idx // grid_cols) * 300
        grid_img.paste(img, (x, y))

    output = BytesIO()
    grid_img.save(output, format="PNG")
    output.seek(0)
    return output

# === Start Bot ===
bot.run(TOKEN)
