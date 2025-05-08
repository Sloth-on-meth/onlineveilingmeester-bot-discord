import re
import discord
import aiohttp
from discord.ext import commands
from PIL import Image
from io import BytesIO
import requests
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

            # Data extractie
            title = data['kavelData']['naam']

            # Fallback voor beschrijving
            description = strip_html(
                data['kavelData'].get('specificaties') or
                data['kavelData'].get('bijzonderheden') or
                data['kavelData'].get('product') or
                "Geen beschrijving beschikbaar."
            )

            price = f"€ {data['hoogsteBod']},-"
            start_price = f"€ {data['openingsBod']},-"
            bid_count = data['aantalBiedingen']
            image_paths = data.get("imageList", [])
            image_urls = [f"https://www.onlineveilingmeester.nl/images/800x600/{path}" for path in image_paths]

            # Sluitingstijd berekening
            sluit_iso = data.get("sluitingsDatumISO")
            sluit_dt = datetime.fromisoformat(sluit_iso.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = sluit_dt - now

            if delta.total_seconds() <= 0:
                sluiting_over = "Gesloten"
            else:
                sluiting_over = f"over {humanize.naturaldelta(delta, minimum_unit='seconds')}"

            sluiting_exact = sluit_dt.strftime("%d/%m/%Y %H:%M")

            # Embed bouwen
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

            # Collage maken
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
    for url in image_urls[:9]:  # max 9 afbeeldingen
        try:
            response = requests.get(url, timeout=10)
            img = Image.open(BytesIO(response.content)).convert("RGB")
            images.append(img)
        except Exception as e:
            print(f"Fout bij afbeelding {url}: {e}")

    if not images:
        return None

    size = (300, 300)
    images = [img.resize(size) for img in images]

    count = len(images)
    if not grid_cols:
        grid_cols = 3 if count > 4 else 2
    rows = (count + grid_cols - 1) // grid_cols

    grid_img = Image.new('RGB', (grid_cols * size[0], rows * size[1]), color=(255, 255, 255))
    for idx, img in enumerate(images):
        x = (idx % grid_cols) * size[0]
        y = (idx // grid_cols) * size[1]
        grid_img.paste(img, (x, y))

    output = BytesIO()
    grid_img.save(output, format="PNG")
    output.seek(0)
    return output

# === Start Bot ===
bot.run(TOKEN)
