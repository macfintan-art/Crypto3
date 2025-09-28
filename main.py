import logging
import os
import price_collector
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from telegram import Update
import database
import asyncio
import datetime
import bot as bot
import gecko_api as gecko_api
import database as database
from logging_config import setup_logging

ASK_TIMEZONE = 1

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Load .env variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

def main() -> None:
    """Start the bot."""
    database.init_database()
    setup_logging()

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_error_handler(bot.error_handler)

    # on different commands - add handlers
    application.add_handler(CommandHandler("add", bot.add_coin))
    application.add_handler(CommandHandler("remove", bot.remove_coin))
    application.add_handler(CommandHandler("setalarm", bot.set_alarm))
    application.add_handler(CommandHandler("message", bot.message_admin))
    application.add_handler(CommandHandler("donate", bot.donate))
    application.add_handler(CommandHandler("list", bot.list_coins))
    application.add_handler(CommandHandler("help", bot.start))
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(MessageHandler(filters.Regex(r'^/set alarm'), bot.remind_correct_setalarm))

    # We use a job queue to schedule recurring tasks
    job_queue = application.job_queue

    # Schedule the price fetching job to run every 5 minutes
    job_queue.run_repeating(
        price_collector.fetch_and_store_prices, 
        interval=datetime.timedelta(minutes=2), 
        first=0
    )

    # Schedule the daily alerts job to run every 5 minutes
    # This task will check for users who need alerts and send them
    job_queue.run_repeating(
        price_collector.send_daily_alerts, 
        interval=datetime.timedelta(minutes=2), 
        first=0
    )

    # Schedule database cleanup to run once a day
    job_queue.run_daily(
        price_collector.cleanup_old_data, 
        time=datetime.time(hour=3, minute=0, tzinfo=datetime.timezone.utc)
    )

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

