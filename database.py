import psycopg2
import os
import logging
from urllib.parse import urlparse
import sys
from datetime import datetime, time, timezone

logger = logging.getLogger("CryptoBot.Database")

def get_db_connection():
    try:
        url = urlparse(os.getenv("DATABASE_URL"))
        conn = psycopg2.connect(
            dbname=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port,
            sslmode='require'
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)

def init_database():
    """Initializes the tables if they don't exist."""
    conn = get_db_connection()
    with conn.cursor() as cur:
        # Recreate users table without the extra columns
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                timezone TEXT,
                alarm_time TIME,
                last_alert_sent_at DATE
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_coins (
                user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                coin_id TEXT,
                PRIMARY KEY (user_id, coin_id)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS coin_prices (
                coin_id TEXT,
                price FLOAT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (coin_id, timestamp)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admin_messages (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                message TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS coin_mapping (
                coin_id TEXT PRIMARY KEY,
                name TEXT,
                symbol TEXT
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sent_alerts (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                alert_key TEXT UNIQUE,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    conn.commit()
    conn.close()
    logger.info("Database tables initialized successfully.")

def user_exists(user_id):
    """Checks if a user exists in the database."""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE user_id = %s;", (user_id,))
        result = cur.fetchone()
    conn.close()
    return result is not None

def add_user_with_default_alarm(user_id):
    """Adds a new user to the database and sets a default 8 PM UTC alarm."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            default_time = time(20, 0)
            default_timezone = 'UTC'
            cur.execute(
                """
                INSERT INTO users (user_id, alarm_time, timezone) 
                VALUES (%s, %s, %s) 
                ON CONFLICT (user_id) DO NOTHING;
                """,
                (user_id, default_time, default_timezone)
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to add user {user_id} with default alarm: {e}")
        conn.rollback()
    finally:
        conn.close()

def set_user_alarm(user_id, alarm_time, timezone):
    """Sets a user's daily alarm time and timezone."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET alarm_time = %s, timezone = %s, last_alert_sent_at = NULL WHERE user_id = %s;",
                (alarm_time, timezone, user_id)
            )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to set alarm for user {user_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def mark_alert_sent_for_alarm(user_id, alert_key):
    """Marks a specific user alert as sent with a full timestamp."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET last_alert_sent_at = NOW() WHERE user_id = %s;",
                (user_id,)
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to mark alert as sent for user {user_id}: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_user_alarm(user_id):
    """Returns the alarm time and timezone for a user."""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT alarm_time, timezone FROM users WHERE user_id = %s;", (user_id,))
        result = cur.fetchone()
    conn.close()
    return result

def get_users_needing_alerts():
    """
    Returns a list of tuples (user_id, alarm_time, timezone)
    for users whose alarm time is within the next 5 minutes.
    """
    conn = get_db_connection()
    user_data = []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, alarm_time, timezone
                FROM users
                WHERE
                    alarm_time IS NOT NULL AND
                    (
                        -- Check if alarm timestamp is in the future but within 5 minutes
                        (
                            ((NOW() AT TIME ZONE timezone)::DATE + alarm_time) > (NOW() AT TIME ZONE timezone) AND
                            ((NOW() AT TIME ZONE timezone)::DATE + alarm_time) <= ((NOW() AT TIME ZONE timezone) + INTERVAL '5 minutes')
                        )
                    )
                    AND
                    (last_alert_sent_at IS NULL OR (last_alert_sent_at AT TIME ZONE timezone)::DATE < (NOW() AT TIME ZONE timezone)::DATE)
            """)
            user_data = cur.fetchall()
            logger.info(f"Found {len(user_data)} users needing alerts.")
    except Exception as e:
        logger.error(f"Failed to get users needing alerts: {e}")
    finally:
        if conn:
            conn.close()
    return user_data

def remove_coin_for_user(user_id, coin_id):
    """Removes a coin from a user's watchlist."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_coins WHERE user_id = %s AND coin_id = %s;", (user_id, coin_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to remove coin {coin_id} for user {user_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
        
def get_user_coins(user_id):
    """Returns a list of coin IDs for a given user."""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT coin_id FROM user_coins WHERE user_id = %s;", (user_id,))
        coins = [row[0] for row in cur.fetchall()]
    conn.close()
    return coins

def is_valid_coin(coin_id):
    """Checks if a coin ID exists in the database."""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM coin_mapping WHERE coin_id = %s;", (coin_id,))
        result = cur.fetchone()
    conn.close()
    return result is not None

def get_all_coin_ids():
    """Fetches a list of all unique coin IDs from the coin_mapping table."""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT coin_id FROM coin_mapping;")
        coins = [row[0] for row in cur.fetchall()]
    conn.close()
    return coins
    
def add_user_message(user_id, message):
    """Records a user's feedback message to the database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO admin_messages (user_id, message) VALUES (%s, %s);",
                (user_id, message)
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to add message for user {user_id}: {e}")
        conn.rollback()
    finally:
        conn.close()
        
def store_price_data(coin_data):
    """Stores a batch of coin prices into the database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            for coin_id, data in coin_data.items():
                cur.execute(
                    "INSERT INTO coin_mapping (coin_id, name, symbol) VALUES (%s, %s, %s) ON CONFLICT (coin_id) DO UPDATE SET name = EXCLUDED.name, symbol = EXCLUDED.symbol;",
                    (coin_id, data['name'], data['symbol'])
                )
                cur.execute(
                    "INSERT INTO coin_prices (coin_id, price, timestamp) VALUES (%s, %s, CURRENT_TIMESTAMP);",
                    (coin_id, data['current_price'])
                )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to store price data: {e}")
        conn.rollback()
    finally:
        conn.close()

def was_alert_sent_for_alarm(user_id, alert_key):
    """
    Checks if an alert with a specific key was already sent today.
    The key should combine date and alarm time (e.g., '2025-09-21_14:30:00_EST').
    """
    conn = get_db_connection()
    result = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM sent_alerts WHERE user_id = %s AND alert_key = %s;",
                (user_id, alert_key)
            )
            result = cur.fetchone() is not None
    except Exception as e:
        logger.error(f"Failed to check for alert status for user {user_id}: {e}")
    finally:
        if conn:
            conn.close()
    return result

def mark_alert_sent_for_alarm(user_id, alert_key):
    """Marks a specific alert as sent by storing a record in the database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sent_alerts (user_id, alert_key) VALUES (%s, %s) ON CONFLICT (alert_key) DO NOTHING;",
                (user_id, alert_key)
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to mark alert as sent for user {user_id}: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_coin_current_and_7d_high(coin_ids):
    """Fetches current price and 7-day high for a list of coins."""
    conn = get_db_connection()
    coin_data = {}
    try:
        with conn.cursor() as cur:
            for coin_id in coin_ids:
                cur.execute(
                    "SELECT price FROM coin_prices WHERE coin_id = %s ORDER BY timestamp DESC LIMIT 1;",
                    (coin_id,)
                )
                current_price_row = cur.fetchone()
                
                cur.execute(
                    "SELECT MAX(price) FROM coin_prices WHERE coin_id = %s AND timestamp > NOW() - INTERVAL '7 days';",
                    (coin_id,)
                )
                seven_day_high_row = cur.fetchone()

                if current_price_row and seven_day_high_row and seven_day_high_row[0] is not None:
                    current_price = current_price_row[0]
                    seven_day_high = seven_day_high_row[0]
                    dip_percentage = ((seven_day_high - current_price) / seven_day_high) * 100
                    
                    cur.execute("SELECT symbol FROM coin_mapping WHERE coin_id = %s;", (coin_id,))
                    symbol = cur.fetchone()[0]
                    
                    coin_data[coin_id] = {
                        'current_price': current_price,
                        'seven_day_high': seven_day_high,
                        'dip_percentage': dip_percentage,
                        'symbol': symbol
                    }
    except Exception as e:
        logger.error(f"Failed to get coin data: {e}")
    finally:
        conn.close()
    return coin_data

def cleanup_old_price_data(days_to_keep=7):
    """Deletes price data older than a specified number of days."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM coin_prices WHERE timestamp < NOW() - INTERVAL '%s days';",
                (days_to_keep,)
            )
        conn.commit()
        logger.info(f"Cleaned up price data older than {days_to_keep} days.")
    except Exception as e:
        logger.error(f"Failed to cleanup old data: {e}")
        conn.rollback()
    finally:
        conn.close()