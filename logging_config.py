import logging
from logging.handlers import RotatingFileHandler
import os


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,  # Change to DEBUG for more detail
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("bot.log", encoding="utf-8"),  # log to file
            logging.StreamHandler()  # also print to console
        ]
    )

def setup_logging():
    """Configures the logging for the application."""
    # Create the logs directory if it doesn't exist
    if not os.path.exists("logs"):
        os.makedirs("logs")

    # Set up basic configuration
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s,%(msecs)d %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            RotatingFileHandler("logs/cryptobot.log", maxBytes=5*1024*1024, backupCount=2),
            logging.StreamHandler()
        ]
    )

    # Set log levels for specific libraries to reduce noise
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)