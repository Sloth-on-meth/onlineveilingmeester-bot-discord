import re
import discord
import aiohttp
import asyncio
from discord.ext import commands
from PIL import Image
from io import BytesIO
from datetime import datetime, timezone
import humanize

# === Config ===
with open("token.secret", "r") as f:
    TOKEN = f.read().strip()

# === Bot Setup ===
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot ingelogd als {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    match = re.search(r'onlineveilingmeester\.nl/nl/veilingen/(\d+)/kavels/(\d+)', message.content)
    if match:
        veiling_id = match.group(1)
        volgnummer = match.group(2)
        api_url = f"https://www.onlineveilingmeester.nl/rest/nl/v2/veilingen/{veiling_id}/kavels/{volgnummer}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    if resp.status != 200:
                        await message.channel.send("API request faalde.")
                        return
                    data = await resp.json()

            # === Data extractie ===
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

            # === Sluitingstijd ===
            sluit_iso = data.get("sluitingsDatumISO")
            sluit_dt = datetime.fromisoformat(sluit_iso.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = sluit_dt - now

            sluiting_over = "Gesloten" if delta.total_seconds() <= 0 else f"over {humanize.naturaldelta(delta, minimum_unit='seconds')}"
            sluiting_exact = sluit_dt.strftime("%d/%m/%Y %H:%M")

            # === Extra info ===
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

            # === Laatste bieders ===
            biedingen = data.get('biedingen', [])
            top_bieders = []
            for b in biedingen[:3]:
                naam = b.get('bieder', '???')
                bedrag = f"€ {b.get('bedrag', '?')},-"
                top_bieders.append(f"**{naam}**: {bedrag}")
            bieders_text = "\n".join(top_bieders) if top_bieders else "Geen biedingen gevonden."

            # === Embed opbouw ===
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

            # === Collage ===
            if image_urls:
                grid_img = await compose_image_grid(image_urls)
                if grid_img:
                    file = discord.File(grid_img, filename="fotos.png")
                    embed.set_image(url="attachment://fotos.png")
                    await message.channel.send(embed=embed, file=file)
                    return

            await message.channel.send(embed=embed)

        except Exception as e:
            print("Fout:", e)
            await message.channel.send("Fout bij ophalen van veilingdetails.")

    await bot.process_commands(message)

def strip_html(html):
    return re.sub(r'<[^>]+>', '', html or "").strip()

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
            print(f"Fout bij afbeelding {url}: {e}")
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
