import logging
import asyncio
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    MessageHandler, filters, ConversationHandler
)
import database
import re
from datetime import datetime, timedelta, time
import os
from dotenv import load_dotenv
from logging_config import setup_logging
import telegram

ASK_TIMEZONE = 1


# --- Logging Setup ---
setup_logging()
logger = logging.getLogger("CryptoBot")
logger.info("Bot starting up...")

# Load .env variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_PATH = os.getenv("DATABASE_PATH")

# Unified logger for all messages and commands
async def log_everything(update, context):
    """Logs all messages, including commands, with user info."""
    if update.message:
        user = update.effective_user
        user_id = user.id
        username = user.username or user.full_name
        text = update.message.text
        is_command = text.startswith("/")
        logger.info(
            f"{'Command' if is_command else 'Message'} from {username} ({user_id}): {text}"
        )

# --- Abuse Protection Config ---
COMMAND_COOLDOWN = 5   # seconds between commands
MAX_COINS_PER_USER = 20
MAX_MESSAGE_LENGTH = 500

# Track last command per user
user_last_command = {}

# --- Middleware: Rate limiting ---
async def rate_limit(update: Update) -> bool:
    """Check if user is sending commands too fast."""
    user_id = update.effective_user.id
    now = datetime.now()

    last_time = user_last_command.get(user_id)
    if last_time and (now - last_time).total_seconds() < COMMAND_COOLDOWN:
        await update.message.reply_text("⚠️ Slow down! Please wait a few seconds before sending another command.")
        logger.warning(f"User {user_id} hit rate limit.")
        return False

    user_last_command[user_id] = now
    return True


# --- Bot Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not database.user_exists(user_id):
        database.add_user_with_default_alarm(user_id)
    
    # Correctly unpack only two values
    alarm_info = database.get_user_alarm(user_id)
    
    # Check if a user has an alarm set at all
    if alarm_info and alarm_info[0] and alarm_info[1]:
        # Unpack only alarm_time and timezone
        alarm_time, timezone = alarm_info
        
        # Now you can use these variables to display the alert info
        display_time = alarm_time.strftime("%I:%M %p")
        alert_info = f"📅 Your daily alerts are set for <b>{display_time} {timezone}</b>."
            
    else:
        alert_info = "📅 No daily alerts set yet"

    # Rest of the welcome message...
    welcome_text = f"""
🤖 <b>Welcome to Crypto Dip Bot!</b>

I'll keep track of your favourite coins and send you <b>daily dip alerts</b> at your chosen time 🚀

📅 <b>Daily Alerts</b>
• Use <code>/setalarm &lt;time&gt; &lt;timezone&gt;</code> to schedule alerts  

💰 <b>Watchlist</b>
• <code>/add &lt;coin_symbol&gt;</code> - Add a coin  
• <code>/remove &lt;coin_symbol&gt;</code> - Remove a coin  
• <code>/list</code> - Show your tracked coins  

⚙️ <b>Other Commands</b>
• <code>/help</code> - Show this menu again  
• <code>/message &lt;your_message&gt;</code> - Send feedback to the admin  
• <code>/donate</code> - ☕ Buy me a coffee to support the bot  

{alert_info}

I'll send you daily crypto updates with dip percentages, 7-day highs, and more 🚀
"""
    await update.message.reply_html(welcome_text)


async def add_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await rate_limit(update): return
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("Please specify a coin! Example: /add bitcoin")
        return

    if len(database.get_user_coins(user_id)) >= MAX_COINS_PER_USER:
        await update.message.reply_text(f"⚠️ You can only track up to {MAX_COINS_PER_USER} coins.")
        return

    coin = context.args[0].lower()
    if not database.is_valid_coin(coin):
        await update.message.reply_text(f"❌ '{coin}' not recognized. Try common names like 'bitcoin', 'ethereum'.")
        return

    if database.add_coin_for_user(user_id, coin):
        await update.message.reply_text(f"✅ Added {coin} to your watchlist!")
        logger.info(f"User {user_id} added coin {coin}")
    else:
        await update.message.reply_text("⚠️ That coin is already in your watchlist.")


async def remove_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await rate_limit(update): return
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("Please specify a coin to remove! Example: /remove bitcoin")
        return

    coin = context.args[0].lower()
    if database.remove_coin_for_user(user_id, coin):
        await update.message.reply_text(f"✅ Removed {coin} from your watchlist.")
        logger.info(f"User {user_id} removed coin {coin}")
    else:
        await update.message.reply_text(f"❌ Could not remove {coin}. Maybe it’s not in your list?")

async def list_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await rate_limit(update): return
    user_id = update.effective_user.id
    coins = database.get_user_coins(user_id)

    if not coins:
        await update.message.reply_text("📭 You aren’t tracking any coins yet.\nUse `/add bitcoin` to start!")
        return

    coin_list = "\n".join([f"• {c.capitalize()}" for c in coins])
    await update.message.reply_text(
        f"📊 You’re currently tracking {len(coins)} coin(s):\n\n{coin_list}"
    )
    logger.info(f"User {user_id} listed {len(coins)} coins.")
   


async def set_alarm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    user_id = update.effective_user.id
    args = context.args

    if len(args) != 2:
        await update.message.reply_text("❌ Incorrect number of arguments.\n\nUsage: `/setalarm <time> <timezone>`\nExample: `/setalarm 14:30 EST` or `/setalarm 14.30 EST`")
        return

    alarm_time_str = args[0]
    timezone_str = args[1].upper()

    # The most common issue is using a static timezone string.
    # We must map to the full, dynamic timezone string that accounts for DST.
    tz_map = {
        'EST': 'US/Eastern',
        'PST': 'US/Pacific',
        'CST': 'US/Central',
        'MST': 'US/Mountain',
        'UTC': 'UTC',
        'GMT': 'GMT',
        'CET': 'CET',
        'JST': 'Japan',
        'NZT': 'Pacific/Auckland'
    }

    if timezone_str not in tz_map:
        await update.message.reply_text(f"❌ Invalid timezone. Please use one of the following: {', '.join(tz_map.keys())}")
        return

    # Use the correct timezone string for the database
    database_timezone_str = tz_map[timezone_str]

    try:
        # Replace dot with colon to handle both formats
        formatted_time_str = alarm_time_str.replace('.', ':')
        
        # Check if the time is in HH:MM format
        alarm_time = datetime.strptime(formatted_time_str, '%H:%M').time()
    except ValueError:
        await update.message.reply_text("❌ Invalid time format. Please use HH:MM or HH.MM (e.g., 14:30 or 14.30).")
        return

    if database.set_user_alarm(user_id, alarm_time, database_timezone_str):
        await update.message.reply_text(f"✅ Your daily alarm has been set for {formatted_time_str} {timezone_str}.")
        logger.error(f"User {user_id} set alarm for {formatted_time_str} {timezone_str}")
    else:
        await update.message.reply_text("❌ Failed to set the alarm. Please try again later.")


async def message_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await rate_limit(update): return
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("Usage: /message Your message here")
        return

    msg = " ".join(context.args)
    if len(msg) > MAX_MESSAGE_LENGTH:
        await update.message.reply_text("⚠️ Message too long! Keep it under 500 chars.")
        return

    database.add_user_message(user_id, msg)
    await update.message.reply_text("✅ Message sent to admin!")
    logger.info(f"User {user_id} sent feedback: {msg}")


async def donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await rate_limit(update): return
    await update.message.reply_text(
        "☕ Support Crypto Dip Bot!\n"
        "👉 [Buy Me a Coffee](buymeacoffee.com/wizardward)",
        parse_mode="Markdown"
    )

async def remind_correct_setalarm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remind user to remove the space in /setalarm command."""
    if update.message.text.lower().startswith("/set alarm"):
        await update.message.reply_text(
            "😄 Oops! I think you meant `/setalarm` (no space)!\n\n"
            "Example: `/setalarm 9:00 AM NZT`",
            parse_mode="Markdown"
        )


# --- Utils ---
def parse_time_and_timezone(time_str):
    """Parse formats like '9:30 AM EST' or '21:30 UTC'"""
    time_str = time_str.replace(".", ":").upper()
    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?\s*([A-Z]{2,4})?", time_str)
    if not match:
        return None, None, None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    ampm = match.group(3)
    tz = match.group(4)
    if ampm == "PM" and hour != 12:
        hour += 12
    if ampm == "AM" and hour == 12:
        hour = 0
    return hour, minute, tz


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log the error and send a message to the developer."""
    logger.error("An error occurred during an update:", exc_info=context.error)

    # Get the user ID of the developer from an environment variable
    dev_chat_id = os.getenv("DEVELOPER_TELEGRAM_ID")
    
    # Try to inform the developer about the error
    if dev_chat_id:
        try:
            await context.bot.send_message(
                chat_id=dev_chat_id,
                text=f"An error occurred: {context.error}"
            )
        except telegram.error.TelegramError as e:
            logger.error(f"Failed to send error message to developer: {e}")


# --- Main ---
def main():
    database.init_database()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_everything), group=0)
    app.add_handler(CommandHandler("add", add_coin))
    app.add_handler(CommandHandler("remove", remove_coin))
    app.add_handler(CommandHandler("setalarm", set_alarm))
    app.add_handler(CommandHandler("message", message_admin))
    app.add_handler(CommandHandler("donate", donate))
    app.add_handler(CommandHandler("list", list_coins))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(MessageHandler(filters.Regex(r'^/set alarm'), remind_correct_setalarm))


    logger.info("Bot running...")
    app.run_polling()

