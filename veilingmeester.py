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

# Load bot token from a secret file
with open("token.secret", "r") as f:
    TOKEN = f.read().strip()

# Log file path
LOGFILE = "veilingmeester_log.txt"

def log(message: str):
    """Append a timestamped log entry to the log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

# Initialize Discord bot with appropriate intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    log(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    start = datetime.now()
    await message.add_reaction("⏳")
    log(f"Received message: {message.content}")

    try:
        # Match OnlineVeilingmeester URL
        if match := re.search(r'onlineveilingmeester\.nl/(?:nl/veilingen|en/auctions)/(\d+)/(?:kavels|lots)/(\d+)', message.content):
            await handle_ovm(message, match.group(1), match.group(2), start)
        # Match DomeinenRZ URL
        elif match := re.search(r'verkoop\.domeinenrz\.nl/[^ ]*?meerfotos=(K\d+)', message.content):
            await handle_drz(message, match.group(1), start)
        else:
            await bot.process_commands(message)

    except Exception as e:
        log(f"❌ Unhandled error: {e}")
        await message.clear_reaction("⏳")
        await message.add_reaction("❌")
        await message.reply("⚠️ Something went wrong while processing your message.")

async def handle_ovm(message, auction_id, lot_id, start):
    url = f"https://www.onlineveilingmeester.nl/rest/nl/v2/veilingen/{auction_id}/kavels/{lot_id}"
    log(f"Fetching OVM data from {url}")

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                await message.reply("❌ Failed to retrieve OVM data.")
                await message.clear_reaction("⏳")
                await message.add_reaction("❌")
                return
            data = await resp.json()

    try:
        item = data.get("kavelData", {})
        title = item.get("naam", "(No title)")
        description = strip_html(item.get("specificaties") or item.get("bijzonderheden") or item.get("product") or "No description.")

        image_urls = [f"https://www.onlineveilingmeester.nl/images/800x600/{path}" for path in data.get("imageList", [])]
        sluiting = datetime.fromisoformat(data["sluitingsDatumISO"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = sluiting - now

        embed = discord.Embed(
            title=title,
            description=description[:2048],
            color=discord.Color.orange(),
            url=f"https://www.onlineveilingmeester.nl/nl/veilingen/{auction_id}/kavels/{lot_id}"
        )

        embed.add_field(name="Details", value="\n".join([
            f"💰 **Current Bid:** € {data.get('hoogsteBod', '??')},-",
            f"📈 **Start Price:** € {data.get('openingsBod', '??')},-",
            f"🔨 **Bids:** {data.get('aantalBiedingen', '?')}",
            f"⏳ **Closes In:** {'Closed' if delta.total_seconds() <= 0 else humanize.naturaldelta(delta)}",
            f"📅 **Closes On:** {sluiting.strftime('%d/%m/%Y %H:%M')}"
        ]), inline=False)

        embed.add_field(name="Extra Info", value="\n".join([
            f"📦 **Category:** {data.get('categorie', {}).get('naam', 'Unknown')}",
            f"🏷️ **Condition:** {item.get('conditie', 'Unknown')}",
            f"🚚 **Shippable:** {'Yes' if data.get('isShippable', False) else 'No'}",
            f"🛠️ **Year:** {item.get('bouwjaar', 'Unknown')}",
            f"🔧 **Brand:** {item.get('merk', 'Unknown')}"
        ]), inline=False)

        bids = data.get("biedingen", [])
        top_bids = "\n".join([f"**{b.get('bieder', '?')}**: € {b.get('bedrag', '?')},-" for b in bids[:3]]) or "No bids yet."
        embed.add_field(name="Top Bidders", value=top_bids, inline=False)

        embed.add_field(name="⏱️ Processing Time", value=f"{(datetime.now() - start).total_seconds():.2f}s", inline=False)

        if image_urls and (grid := await compose_image_grid(image_urls)):
            file = discord.File(grid, filename="preview.png")
            embed.set_image(url="attachment://preview.png")
            await message.reply(embed=embed, file=file)
        else:
            await message.reply(embed=embed)

        await message.clear_reaction("⏳")
        await message.add_reaction("✅")

    except Exception as e:
        log(f"❌ OVM error: {e}")
        await message.clear_reaction("⏳")
        await message.add_reaction("❌")
        await message.reply("⚠️ Error fetching auction details.")

async def handle_drz(message, lot_code, start):
    url = f"https://verkoop.domeinenrz.nl/verkoop_bij_inschrijving_2025-0009?meerfotos={lot_code}"
    log(f"Fetching DRZ page: {url}")

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                await message.reply("❌ DRZ page not found.")
                await message.clear_reaction("⏳")
                await message.add_reaction("❌")
                return
            html = await resp.text(encoding="windows-1252")

    try:
        soup = BeautifulSoup(html, "html.parser")
        item = soup.find("div", class_="catalogusdetailitem")
        if not item:
            await message.reply("❌ DRZ detail block not found.")
            await message.clear_reaction("⏳")
            await message.add_reaction("❌")
            return

        title = item.select_one("h4.title")
        description = strip_html(item.get_text(separator="\n", strip=True))
        images = [f"https://verkoop.domeinenrz.nl{img.get('data-hresimg')}" for img in item.select("img") if img.get("data-hresimg")]

        embed = discord.Embed(
            title=title.text.strip() if title else "(No Title)",
            description=description[:2048],
            color=discord.Color.teal(),
            url=url
        )

        embed.add_field(name="⏱️ Processing Time", value=f"{(datetime.now() - start).total_seconds():.2f}s", inline=False)

        if images and (grid := await compose_image_grid(images)):
            file = discord.File(grid, filename="preview.png")
            embed.set_image(url="attachment://preview.png")
            await message.reply(embed=embed, file=file)
        else:
            await message.reply(embed=embed)

        await message.clear_reaction("⏳")
        await message.add_reaction("✅")

    except Exception as e:
        log(f"❌ DRZ error: {e}")
        await message.clear_reaction("⏳")
        await message.add_reaction("❌")
        await message.reply("⚠️ Error fetching DRZ details.")

def strip_html(html: str) -> str:
    """Remove HTML tags and convert breaks to newlines."""
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</p\s*>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<[^>]+>', '', html)
    return re.sub(r'\n+', '\n', html).strip()

async def compose_image_grid(urls: list[str], grid_cols: int | None = None):
    """Download up to 9 images and compose a grid preview."""
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

    images = [img.resize((300, 300)) for img in images if img]
    if not images:
        return None

    cols = grid_cols or (3 if len(images) > 4 else 2)
    rows = (len(images) + cols - 1) // cols

    grid = Image.new("RGB", (cols * 300, rows * 300), (255, 255, 255))
    for i, img in enumerate(images):
        grid.paste(img, ((i % cols) * 300, (i // cols) * 300))

    output = BytesIO()
    grid.save(output, format="PNG")
    output.seek(0)
    return output

# Start the bot
bot.run(TOKEN)
