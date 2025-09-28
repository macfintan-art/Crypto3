import time
from datetime import datetime
import database
import gecko_api
from telegram import Bot
import pytz
import os
from dotenv import load_dotenv
import logging
import asyncio
import psycopg2.errors

logger = logging.getLogger("CryptoBot.PriceCollector")

# Load .env variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")


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

import asyncio
from datetime import datetime
import psycopg2

async def fetch_and_store_prices(context):
    """Fetches coin data and stores it in the database."""
    print("Fetching prices for top 100 coins...")
    
    try:
        # fetch_top_coins() returns a dictionary {coin_id: data}
        top_coins_data = await asyncio.to_thread(gecko_api.fetch_top_coins)

        if not top_coins_data:
            print("API did not return any data.")
            return

        # Prepare a list of tuples for the bulk insert
        current_time = datetime.now()
        values_to_insert = [
            (coin_id, current_time, coin_info['current_price'])
            for coin_id, coin_info in top_coins_data.items()
        ]

        # Use a single database connection and transaction
        # The 'with' statement handles commit/rollback and closing
        conn = await asyncio.to_thread(database.get_db_connection)
        with conn:  # This acts as a transaction block, committing on success
            with conn.cursor() as cur:
                print(f"Attempting to store {len(values_to_insert)} prices...")
                try:
                    # Use ON CONFLICT DO NOTHING to handle duplicates cleanly
                    cur.executemany(
                        """
                        INSERT INTO coin_prices (coin_id, timestamp, price)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (coin_id, timestamp) DO NOTHING;
                        """,
                        values_to_insert
                    )
                    print(f"Stored prices for {cur.rowcount} coins at {current_time}")

                except Exception as e:
                    # If an error happens, the 'with' block will handle the rollback
                    print(f"Failed to insert prices into the database: {e}")
                    raise # Re-raise the exception to be caught by the outer try-except
            
    except Exception as e:
        print(f"An error occurred during fetch or store: {e}")

def format_price(price):
    """Format price with dynamic significant figures based on magnitude"""
    if price >= 1:
        return f"{price:,.2f}"      # 2 decimals for $1+
    elif price >= 0.01:
        return f"{price:,.4f}"      # 4 decimals for $0.01 - $1
    else:
        return f"{price:,.6f}"      # 6 decimals for tiny coins
    

async def send_daily_alerts(context):
    """Send alerts to users whose alarm time has arrived."""
    
    bot_instance = context.bot
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        
        # This will now return a list of tuples: [(user_id, alarm_time, timezone), ...]
        users_to_alert = await asyncio.to_thread(database.get_users_needing_alerts)
        
        if not users_to_alert:
            print("No users to alert at this time.")
            return
        
        print(f"Checking alerts for {len(users_to_alert)} users...")
    
        # Unpack the tuple directly in the for loop
        for user_id, alarm_time, timezone in users_to_alert:

            
            try:
                alert_key = f"{today}_{alarm_time}_{timezone}"
                
                # Check if alert was already sent
                if await asyncio.to_thread(database.was_alert_sent_for_alarm, user_id, alert_key):
                    continue
                
                # Get user's watchlist
                user_coins = await asyncio.to_thread(database.get_user_coins, user_id)
                
                if not user_coins:
                    continue
                
                # Get current prices and dip data
                coin_data = await asyncio.to_thread(database.get_coin_current_and_7d_high, user_coins)
                
                if not coin_data:
                    continue
                
                message = "🌅 **Daily Crypto Update**\n\n"
                
                for coin_id in user_coins:
                    if coin_id in coin_data:
                        data = coin_data[coin_id]
                        symbol = data['symbol']
                        price = data['current_price']
                        high = data['seven_day_high']
                        dip = data['dip_percentage']
                        
                        price_str = format_price(price)
                        high_str = format_price(high)
                        
                        if dip >= 20:
                            emoji = "🔴"
                            status = " - **DIP ALERT!**"
                        elif dip >= 10:
                            emoji = "🟡"
                            status = ""
                        else:
                            emoji = "🟢"
                            status = ""
                        
                        message += f"{emoji} **{symbol}**: ${price_str} (7d high: ${high_str}) - Down {dip:.1f}%{status}\n"


                # Add last updated time in user's timezone
                
                user_tz_str = tz_map.get(timezone, 'UTC')
                user_tz = pytz.timezone(user_tz_str)
                now_local = datetime.now(pytz.UTC).astimezone(user_tz)
                
                message += f"\n_Last updated: {now_local.strftime('%H:%M %Z')}_"
                
                footer = (
                    "\nTip: Use /donate to support the bot and keep the coffee flowing! ☕🚀"
                )
                
                await bot_instance.send_message(chat_id=user_id, text=message + footer, parse_mode='Markdown')
                
                await asyncio.to_thread(database.mark_alert_sent_for_alarm, user_id, alert_key)
                print(f"Sent daily alert to user {user_id} for alarm {alarm_time} {timezone}")
                
            except Exception as e:
                print(f"Failed to send alert to user {user_id}: {e}")

    except Exception as e:
        print(f"Error caught in send_daily_alerts: {e}")

async def cleanup_old_data(context):
    """Cleans up old price data in the database."""
    logger.info("Running database cleanup...")
    await asyncio.to_thread(database.cleanup_old_price_data, days_to_keep=7)
    logger.info("Database cleanup complete.")

