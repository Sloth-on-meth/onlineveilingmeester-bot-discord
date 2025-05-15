import re
import discord
import aiohttp
import asyncio
import json
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, validator
from discord.ext import commands, tasks
from discord.ui import Button, View
from PIL import Image, ImageDraw, ImageOps
from io import BytesIO
from datetime import datetime, timezone
import humanize
from bs4 import BeautifulSoup
import openai
from functools import wraps
import time
import html
from openai import AsyncOpenAI

# --------------------------
# Configuration Setup
# --------------------------

class BotConfig(BaseModel):
    openai_api_key: str
    log_channel_id: int
    discord_token: str
    allowed_channel_id: int
    updates_channel_id: int
    allowed_role_id: int
    db_file: str = "veilingmeester.db"
    log_file: str = "veilingmeester.log"
    check_interval: int = 1 # minutes
    max_log_size: int = 5  # MB
    log_backup_count: int = 3
    max_concurrent_images: int = 5
    image_timeout: int = 10  # seconds
    http_timeout: int = 10  # seconds
    
    @validator('allowed_channel_id', 'updates_channel_id', 'allowed_role_id', pre=True)
    def convert_ids(cls, v):
        return int(v) if v else None

try:
    with open("config.json") as f:
        config = BotConfig(**json.load(f))
except Exception as e:
    print(f"CRITICAL: Failed to load config: {e}")
    raise
client = AsyncOpenAI(api_key=config.openai_api_key)

# --------------------------
# Logging Setup
# --------------------------

def setup_logging():
    """Configure logging to both file and console"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        config.log_file,
        maxBytes=config.max_log_size * 1024 * 1024,
        backupCount=config.log_backup_count,
        encoding='utf-8'
    )
    file_formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(name)s: %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(levelname)s - %(name)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

setup_logging()
logger = logging.getLogger(__name__)

# --------------------------
# Database Setup
# --------------------------

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(config.db_file, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}", exc_info=True)
        raise
    finally:
        conn.close()

@contextmanager
def get_db_cursor():
    """Context manager for database cursors"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

def init_db():
    """Initialize database tables"""
    with get_db_cursor() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS tracked_auctions (
            auction_id TEXT,
            lot_id TEXT,
            last_bid REAL,
            user_id TEXT,
            PRIMARY KEY (auction_id, lot_id, user_id)
        )
        """)
        logger.info("Database initialized")

init_db()

# --------------------------
# Discord Bot Setup
# --------------------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --------------------------
# Utility Functions
# --------------------------

def track_performance(func):
    """Logs duration and returns result with execution time"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            duration = time.perf_counter() - start
            logger.info(f"{func.__name__} executed in {duration:.2f}s")
            
            # If the original function returned a tuple already, don't double-wrap it
            if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], float):
                return result  # assume it's already (result, duration)
            return result, duration

        except Exception as e:
            duration = time.perf_counter() - start
            logger.error(f"{func.__name__} failed after {duration:.2f}s: {e}", exc_info=True)
            raise
    return wrapper



def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent injection"""
    text = html.escape(text)
    text = text.replace('\0', '')  # Remove null bytes
    return text[:2000]  # Limit length

def strip_html(html_text: str) -> str:
    """Strip HTML tags from text"""
    html_text = re.sub(r'<br\s*/?>', '\n', html_text, flags=re.IGNORECASE)
    html_text = re.sub(r'</p\s*>', '\n', html_text, flags=re.IGNORECASE)
    html_text = re.sub(r'<[^>]+>', '', html_text)
    return re.sub(r'\n+', '\n', html_text).strip()

async def send_to_log_channel(message: str, level: str = "info"):
    """Send log message to Discord log channel"""
    try:
        color = discord.Color.green() if level == "info" else discord.Color.red()
        embed = discord.Embed(
            description=f"```{message[:2000]}```",
            color=color
        )
        embed.set_footer(text=f"Log Level: {level.upper()}")

        log_channel = bot.get_channel(config.log_channel_id)
        if log_channel:
            await log_channel.send(embed=embed)
        else:
            logger.warning("Log channel not found")

    except Exception as e:
        logger.error(f"Failed to send to log channel: {e}", exc_info=True)

# --------------------------
# Image Handling
# --------------------------

@track_performance
async def compose_image_grid(urls: List[str]) -> Optional[BytesIO]:
    start_time = time.perf_counter()

    """Create a grid image from multiple URLs"""
    CANVAS_SIZE = 1200
    MAX_IMAGES = 9
    
    async def fetch_image(session, url):
        """Fetch and process a single image"""
        try:
            async with session.get(url, timeout=config.image_timeout) as resp:
                if resp.status == 200:
                    img_data = await resp.read()
                    return Image.open(BytesIO(img_data)).convert("RGB")
        except Exception as e:
            logger.warning(f"Failed to fetch image {url}: {e}")
        return None

    semaphore = asyncio.Semaphore(config.max_concurrent_images)
    
    async def fetch_with_semaphore(session, url):
        async with semaphore:
            return await fetch_image(session, url)

    async with aiohttp.ClientSession() as session:
        images = await asyncio.gather(
            *(fetch_with_semaphore(session, url) for url in urls[:MAX_IMAGES])
        )
    
    images = [img for img in images if img is not None]
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

    duration = time.perf_counter() - start_time  # manually time it
    return output, duration

# --------------------------
# AI Summary Generation
# --------------------------

@track_performance
async def generate_summary(**kwargs) -> str:
    """Generate AI summary of auction item"""
    prompt = (
        f"Vat dit veilingobject samen in maximaal 50 woorden, in het Nederlands.\n"
        f"Titel: {kwargs.get('titel', 'Onbekend')}\n"
        f"Beschrijving: {kwargs.get('beschrijving', '')[:500]}\n"
        f"Aantal foto's: {len(kwargs.get('fotos', []))}\n"
        f"Huidig bod: € {kwargs.get('bod', 0):.2f}\n"
        f"BTW: € {kwargs.get('btw', 0):.2f}\n"
        f"Totaal: € {kwargs.get('totaal', 0):.2f}\n"
        f"Sluit op: {kwargs.get('sluiting', 'Onbekend')}\n"
        f"Categorie: {kwargs.get('categorie', 'Onbekend')}\n"
        f"Staat: {kwargs.get('staat', 'Onbekend')}\n"
        f"Verzendbaar: {kwargs.get('verzendbaar', 'Onbekend')}\n"
        f"Bouwjaar: {kwargs.get('bouwjaar', 'Onbekend')}\n"
        f"Merk: {kwargs.get('merk', 'Onbekend')}\n"
        f"Startbod: {kwargs.get('startbod', 'Onbekend')}\n"
        f"Topbieders:\n{kwargs.get('topbieders_str', 'Geen bieders')}"
    )

    try:
        client = openai.AsyncOpenAI(api_key=config.openai_api_key)

        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.7
        )

        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI error: {e}", exc_info=True)
        return "⚠️ Kon geen samenvatting genereren wegens een fout."


# --------------------------
# Discord Views
# --------------------------

class FollowView(View):
    """View for tracking/untracking auctions"""
    def __init__(self, auction_id: str, lot_id: str, bid_amount: float):
        super().__init__(timeout=None)
        self.auction_id = auction_id
        self.lot_id = lot_id
        self.bid_amount = bid_amount

    @discord.ui.button(label="🔨 Volg", style=discord.ButtonStyle.success)
    async def follow_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Track this auction lot"""
        try:
            with get_db_cursor() as c:
                c.execute("""
                INSERT OR REPLACE INTO tracked_auctions 
                (auction_id, lot_id, last_bid, user_id) 
                VALUES (?, ?, ?, ?)
                """, (self.auction_id, self.lot_id, self.bid_amount, str(interaction.user.id)))
            
            logger.info(f"User {interaction.user.id} started tracking {self.auction_id}/{self.lot_id}")
            await interaction.response.send_message("✅ Je volgt dit kavel nu.", ephemeral=True)
        except Exception as e:
            logger.error(f"Follow error: {e}", exc_info=True)
            await interaction.response.send_message("❌ Fout bij volgen van kavel.", ephemeral=True)

    @discord.ui.button(label="❌ Stop Volgen", style=discord.ButtonStyle.danger)
    async def unfollow_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Stop tracking this auction lot"""
        try:
            with get_db_cursor() as c:
                c.execute("""
                DELETE FROM tracked_auctions 
                WHERE auction_id=? AND lot_id=? AND user_id=?
                """, (self.auction_id, self.lot_id, str(interaction.user.id)))
            
            logger.info(f"User {interaction.user.id} stopped tracking {self.auction_id}/{self.lot_id}")
            await interaction.response.send_message("✅ Je volgt dit kavel niet meer.", ephemeral=True)
        except Exception as e:
            logger.error(f"Unfollow error: {e}", exc_info=True)
            await interaction.response.send_message("❌ Fout bij stoppen met volgen.", ephemeral=True)

# --------------------------
# Auction Handlers
# --------------------------

class AuctionData(BaseModel):
    """Model for auction data validation"""
    kavelData: Dict[str, Any]
    hoogsteBod: Optional[float] = 0.0
    openingsBod: Optional[float] = 0.0
    opgeldPercentage: float = 17.0
    btwPercentage: float = 21.0
    handelingskosten: float = 0.0
    sluitingsDatumISO: str
    imageList: List[str] = []
    aantalBiedingen: Optional[int] = 0
    biedingen: List[Dict[str, Any]] = []
    categorie: Dict[str, Any] = {}
    isShippable: bool = False

@track_performance

async def handle_ovm(message: discord.Message, auction_id: str, lot_id: str, start_time: datetime):
    """Handle OVM auction links"""
    url = f"https://www.onlineveilingmeester.nl/rest/nl/v2/veilingen/{auction_id}/kavels/{lot_id}"
    logger.info(f"Fetching OVM data from {url}")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=config.http_timeout)) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.warning(f"OVM API returned {resp.status} for {url}")
                    await message.reply("❌ Kan veilinggegevens niet ophalen (API fout).")
                    return
                
                try:
                    data = AuctionData(**await resp.json())
                except Exception as e:
                    logger.error(f"Invalid OVM API response: {e}", exc_info=True)
                    await message.reply("⚠️ Ongeldige gegevens ontvangen van veilingplatform.")
                    return

        item = data.kavelData
        title = item.get("naam", "(Geen titel)")
        description = strip_html(item.get("specificaties") or item.get("bijzonderheden") or item.get("product") or "Geen beschrijving.")
        image_urls = [f"https://www.onlineveilingmeester.nl/images/800x600/{path}" for path in data.imageList]
        
        try:
            sluiting = datetime.fromisoformat(data.sluitingsDatumISO.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = sluiting - now
            sluit_over = "Gesloten" if delta.total_seconds() <= 0 else humanize.naturaldelta(delta)
        except Exception as e:
            logger.warning(f"Error parsing closing date: {e}")
            sluit_over = "Onbekend"
        grid_duration = 0.0
        summary_duration = 0.0

        bod = float(data.hoogsteBod or data.openingsBod or 0)
        veilingkosten = round(bod * (data.opgeldPercentage / 100), 2)
        handelingskosten = float(data.handelingskosten or 0)
        kosten_totaal = veilingkosten + handelingskosten
        btw = round((bod + kosten_totaal) * (data.btwPercentage / 100), 2)
        totaal = round(bod + kosten_totaal + btw, 2)

        topbieders = data.biedingen[:3]
        topbieders_str = "\n".join([f"{b.get('bieder', '?')}: € {b.get('bedrag', '?')},-" for b in topbieders]) or "Geen bieders"

        # Generate AI summary
        samenvatting, summary_duration = await generate_summary(
            titel=title,
            beschrijving=description,
            fotos=image_urls,
            bod=bod,
            btw=btw,
            totaal=totaal,
            sluiting=sluiting.strftime('%d/%m/%Y %H:%M'),
            categorie=data.categorie.get("naam", "Onbekend"),
            staat=item.get("conditie", "Onbekend"),
            verzendbaar="Ja" if data.isShippable else "Nee",
            bouwjaar=item.get("bouwjaar", "Onbekend"),
            merk=item.get("merk", "Onbekend"),
            startbod=data.openingsBod or "Onbekend",
            topbieders_str=topbieders_str
        )

        # Build embed
        embed = discord.Embed(
            title=title,
            description=description[:2048],
            color=discord.Color.orange(),
            url=f"https://www.onlineveilingmeester.nl/nl/veilingen/{auction_id}/kavels/{lot_id}"
        )
        
        # Add fields to embed
        embed.add_field(name="🧠 AI Samenvatting", value=samenvatting, inline=False)
        
        embed.add_field(name="📋 Details", value="\n".join([
            f"💰 **Huidig bod:** € {bod:.2f},-",
            f"📈 **Startbod:** € {data.openingsBod or '??'},-",
            f"🔨 **Aantal biedingen:** {data.aantalBiedingen or '?'}",
            f"⏳ **Sluit over:** {sluit_over}",
            f"🗓 **Sluit op:** {sluiting.strftime('%d/%m/%Y %H:%M')}"
        ]), inline=False)

        embed.add_field(name="💸 Kostenoverzicht", value="\n".join([
            f"💰 Bod: € {bod:.2f}",
            f"🧾 Veilingkosten ({data.opgeldPercentage}%): € {veilingkosten:.2f}",
            f"📦 Handelingskosten: € {handelingskosten:.2f}",
            f"🧾 BTW ({data.btwPercentage}%): € {btw:.2f}",
            f"💳 **Totaal te betalen:** € {totaal:.2f}"
        ]), inline=False)

        embed.add_field(name="📦 Extra informatie", value="\n".join([
            f"📂 **Categorie:** {data.categorie.get('naam', 'Onbekend')}",
            f"🏷️ **Staat:** {item.get('conditie', 'Onbekend')}",
            f"🚚 **Verzendbaar:** {'Ja' if data.isShippable else 'Nee'}",
            f"🛠️ **Bouwjaar:** {item.get('bouwjaar', 'Onbekend')}",
            f"🔧 **Merk:** {item.get('merk', 'Onbekend')}"
        ]), inline=False)

        embed.add_field(name="👑 Topbieders", value=topbieders_str, inline=False)
        embed.add_field(name="⏱️ Verwerkingstijd", value=f"{(datetime.now() - start_time).total_seconds():.2f}s", inline=False)


        view = FollowView(auction_id, lot_id, bod)
        
        # Handle images


        if image_urls:
            try:
                grid_result = await compose_image_grid(image_urls)
                print(f'grid result: {grid_result}')
                grid, grid_duration = grid_result if isinstance(grid_result, tuple) else (grid_result, 0.0)
                print(grid_duration)
                if grid:
                    file = discord.File(grid, filename="preview.png")
                    embed.set_image(url="attachment://preview.png")
                    embed.add_field(
                        name="🕒 Verwerktijden",
                        value="\n".join([
                            f"🧠 AI: {summary_duration:.2f}s",
                            f"🖼️ Afbeeldingen: {grid_duration:.2f}s",
                            f"📦 Totaal: {(datetime.now() - start_time).total_seconds():.2f}s"
                        ]),
                        inline=False
                    )
                    await message.reply(embed=embed, file=file, view=view) 
                    return

            except Exception as e:
                logger.error(f"Image processing error: {e}", exc_info=True)
        embed.add_field(
            name="🕒 Verwerktijden",
            value="\n".join([
                f"🧠 AI: {summary_duration:.2f}s",
                f"🖼️ Afbeeldingen: {grid_duration:.2f}s",
                f"📦 Totaal: {(datetime.now() - start_time).total_seconds():.2f}s"
            ]),
            inline=False
        )
        await message.reply(embed=embed, view=view) 

    except Exception as e:
        logger.error(f"Error in handle_ovm: {e}", exc_info=True)
        await message.reply("⚠️ Er ging iets mis bij het verwerken van dit veilingkavel.")

# --------------------------
# Background Tasks
# --------------------------

@tasks.loop(minutes=config.check_interval)
async def check_auction_updates():
    """Check for updates on tracked auctions"""
    logger.info("Starting auction update check")
    
    try:
        with get_db_cursor() as c:
            c.execute("SELECT DISTINCT auction_id, lot_id, last_bid FROM tracked_auctions")
            tracked = c.fetchall()

        if not tracked:
            logger.info("No auctions being tracked")
            return

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=config.http_timeout)) as session:
            for row in tracked:
                auction_id, lot_id, last_bid = row
                url = f"https://www.onlineveilingmeester.nl/rest/nl/v2/veilingen/{auction_id}/kavels/{lot_id}"
                
                try:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            logger.warning(f"API error for {url}: {resp.status}")
                            continue
                        
                        try:
                            data = AuctionData(**await resp.json())
                        except Exception as e:
                            logger.error(f"Invalid API response for {url}: {e}")
                            continue

                    new_bid = float(data.hoogsteBod or data.openingsBod or 0)
                    if new_bid > last_bid:
                        with get_db_cursor() as c:
                            c.execute("""
                            SELECT user_id FROM tracked_auctions 
                            WHERE auction_id=? AND lot_id=?
                            """, (auction_id, lot_id))
                            users = c.fetchall()

                        if not users:
                            continue

                        mentions = " ".join([f"<@{user['user_id']}>" for user in users])
                        title = data.kavelData.get("naam", "Kavel")
                        image = data.imageList[0] if data.imageList else None
                        veilingkosten = round(new_bid * (data.opgeldPercentage / 100), 2)
                        handelingskosten = float(data.handelingskosten or 0)
                        kosten_totaal = veilingkosten + handelingskosten
                        btw = round((new_bid + kosten_totaal) * (data.btwPercentage / 100), 2)
                        totaal = round(new_bid + kosten_totaal + btw, 2)
                        
                        try:
                            sluiting = datetime.fromisoformat(data.sluitingsDatumISO.replace("Z", "+00:00"))
                            now = datetime.now(timezone.utc)
                            delta = sluiting - now
                            sluit_over = humanize.naturaldelta(delta) if delta.total_seconds() > 0 else "Gesloten"
                        except Exception:
                            sluit_over = "Onbekend"

                        # Build notification embed
                        embed = discord.Embed(
                            title="Nieuw bod geplaatst!",
                            url=f"https://www.onlineveilingmeester.nl/nl/veilingen/{auction_id}/kavels/{lot_id}",
                            description=f"**{title}**\n\n💰 Nieuw bod: € {new_bid:.2f}\n💸 Totaal incl. kosten: € {totaal:.2f}",
                            color=discord.Color.green()
                        )
                        
                        if image and isinstance(image, str) and image.strip():
                            embed.set_image(url=f"https://www.onlineveilingmeester.nl/images/800x600/{image.strip()}")


                        embed.add_field(name="💶 Bod", value=f"€ {new_bid:.2f}", inline=True)
                        embed.add_field(name="📦 Veilingkosten", value=f"€ {veilingkosten:.2f}", inline=True)
                        embed.add_field(name="🧾 Handelingskosten", value=f"€ {handelingskosten:.2f}", inline=True)
                        embed.add_field(name="🧾 BTW", value=f"€ {btw:.2f}", inline=True)
                        embed.add_field(name="💳 Totaal", value=f"€ {totaal:.2f}", inline=True)
                        embed.add_field(name="📈 Aantal biedingen", value=str(data.aantalBiedingen), inline=True)
                        embed.add_field(name="⏳ Sluit over", value=sluit_over, inline=True)


                        # Send notification
                        try:
                            channel = bot.get_channel(config.updates_channel_id)
                            if channel:
                                await channel.send(content=mentions, embed=embed)
                                logger.info(f"Sent update for {auction_id}/{lot_id}: €{new_bid:.2f}")
                            else:
                                logger.warning("Updates channel not found")
                        except Exception as e:
                            logger.error(f"Failed to send update: {e}", exc_info=True)

                        # Update database
                        with get_db_cursor() as c:
                            c.execute("""
                            UPDATE tracked_auctions SET last_bid=? 
                            WHERE auction_id=? AND lot_id=?
                            """, (new_bid, auction_id, lot_id))

                except Exception as e:
                    logger.error(f"Error checking auction {auction_id}/{lot_id}: {e}", exc_info=True)
                    continue

    except Exception as e:
        logger.error(f"Error in auction update task: {e}", exc_info=True)
    finally:
        logger.info("Completed auction update check")

# --------------------------
# Bot Events
# --------------------------

@bot.event
async def on_ready():
    """Initialize bot when ready"""
    try:
        # Validate configuration
        if not all([config.discord_token, config.openai_api_key, config.allowed_channel_id, config.updates_channel_id]):
            raise ValueError("Missing required configuration values")
        
        # Set up updates channel
        bot.updates_channel = bot.get_channel(config.updates_channel_id)
        if not bot.updates_channel:
            logger.warning("Updates channel not found")
        
        logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
        logger.info(f"Guilds: {len(bot.guilds)}")
        
        # Start background tasks
        check_auction_updates.start()
        await send_to_log_channel("🤖 Bot is online and ready!")
        
    except Exception as e:
        logger.critical(f"Startup error: {e}", exc_info=True)
        raise

@bot.event
async def on_disconnect():
    """Clean up on disconnect"""
    logger.info("Bot disconnecting - cleaning up")
    check_auction_updates.stop()
    await send_to_log_channel("🔌 Bot is disconnecting...")

@bot.event
async def on_message(message: discord.Message):
    """Handle incoming messages"""
    if message.author.bot:
        return

    # Log message
    logger.info(f"Message from {message.author}: {message.content[:50]}...")

    # Skibidi toilet meme response
    if "skibidi" in message.content.lower():
        await message.reply('toilet https://www.youtube.com/watch?v=WePNs-G7puA')
        await message.add_reaction("🚽")
        return

    # Check permissions
    if message.guild:
        role_ids = [r.id for r in message.author.roles]
        if config.allowed_role_id not in role_ids:
            return

    # Handle commands
    if message.content.startswith("!purge"):
        await handle_purge(message)
        return
    elif message.content.startswith("!testbid"):
        await simulate_bid_notification(message)
        return

    # Only process auction links in allowed channel
    if message.channel.id != config.allowed_channel_id:
        return

    start_time = datetime.now()
    
    try:
        if match := re.search(r'onlineveilingmeester\.nl/(?:nl/veilingen|en/auctions)/(\d+)/(?:kavels|lots)/(\d+)', message.content):
            await handle_ovm(message, match.group(1), match.group(2), start_time)
        else:
            await bot.process_commands(message)
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await message.reply("⚠️ Er ging iets mis bij het verwerken van je bericht.")

# --------------------------
# Commands
# --------------------------

async def handle_purge(message: discord.Message):
    """Purge messages from channel"""
    if not message.author.guild_permissions.manage_messages:
        await message.reply("❌ Je hebt geen toestemming om berichten te verwijderen.")
        return

    parts = message.content.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.reply("Gebruik: `!purge <aantal>` (max 100)")
        return

    amount = int(parts[1])
    if amount < 1 or amount > 100:
        await message.reply("Geef een getal tussen 1 en 100.")
        return

    try:
        deleted = await message.channel.purge(limit=amount + 1)
        confirm = await message.channel.send(f"🧻 {len(deleted)-1} berichten verwijderd.")
        await confirm.delete(delay=3)
        logger.info(f"Purged {len(deleted)-1} messages in {message.channel}")
    except Exception as e:
        logger.error(f"Purge error: {e}", exc_info=True)
        await message.reply("❌ Fout bij verwijderen van berichten.")

@track_performance
async def simulate_bid_notification(message: discord.Message):
    """Simulate a bid notification for testing"""
    try:
        auction_id = "1234"
        lot_id = "5678"
        new_bid = 123.45
        title = "Test Kavel"
        image = "https://via.placeholder.com/800x600.png?text=Preview"

        embed = discord.Embed(
            title="TEST: Nieuw bod geplaatst! @here",
            url=f"https://www.onlineveilingmeester.nl/nl/veilingen/{auction_id}/kavels/{lot_id}",
            description=f"Nieuw bod: € {new_bid:.2f}",
            color=discord.Color.green()
        )
        embed.set_image(url=image)
        embed.add_field(name="Titel", value=title, inline=False)
        embed.add_field(name="Bod", value=f"€ {new_bid:.2f}", inline=True)

        await message.channel.send(content=f"<@{message.author.id}>", embed=embed)
        logger.info(f"Sent test bid notification for {message.author}")
    except Exception as e:
        logger.error(f"Test bid error: {e}", exc_info=True)
        await message.reply("❌ Fout bij testmelding.")

# --------------------------
# Startup
# --------------------------

if __name__ == '__main__':
    try:
        openai.api_key = config.openai_api_key
        bot.run(config.discord_token)
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        raise
