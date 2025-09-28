import database
from datetime import datetime

def simulate_daily_alerts():
    """Simulate sending daily alerts for all users without Telegram"""
    today = datetime.now().strftime('%Y-%m-%d')
    users_to_alert = database.get_users_needing_alerts()
    
    if not users_to_alert:
        print("No users need alerts right now.")
        return
    
    print(f"Simulating alerts for {len(users_to_alert)} users...\n")
    
    for user_id in users_to_alert:
        alarm_info = database.get_user_alarm(user_id)
        if not alarm_info:
            continue
        
        alarm_time, timezone = alarm_info
        alert_key = f"{today}_{alarm_time}_{timezone}"
        
        # Skip if already "sent" today
        if database.was_alert_sent_for_alarm(user_id, alert_key):
            print(f"[User {user_id}] Alert already sent today at {alarm_time} {timezone}")
            continue
        
        user_coins = database.get_user_coins(user_id)
        if not user_coins:
            print(f"[User {user_id}] No coins in watchlist")
            continue
        
        coin_data = database.get_coin_current_and_7d_high(user_coins)
        if not coin_data:
            print(f"[User {user_id}] No coin data available")
            continue
        
        # Build alert message
        message = f"🌅 **Daily Crypto Update for User {user_id}**\n\n"
        for coin_id in user_coins:
            if coin_id in coin_data:
                data = coin_data[coin_id]
                symbol = data['symbol']
                price = data['current_price']
                dip = data['dip_percentage']
                
                if dip >= 20:
                    emoji = "🔴"
                    status = " - **DIP ALERT!**"
                elif dip >= 10:
                    emoji = "🟡"
                    status = ""
                else:
                    emoji = "🟢"
                    status = ""
                
                message += f"{emoji} {symbol}: ${price:,.4f} (-{dip:.1f}%){status}\n"
        
        message += f"\n_Last updated: {datetime.now().strftime('%H:%M UTC')}_"
        
        print(message)
        print("-" * 50)
        
        # Mark as sent so next run won't duplicate
        database.mark_alert_sent_for_alarm(user_id, alert_key)

if __name__ == "__main__":
    database.init_database()
    
    # Optional: Add a fake user for testing
    fake_user_id = 999999
    database.add_user(fake_user_id)
    database.set_user_timezone(fake_user_id, 'UTC')
    database.set_user_alarm(fake_user_id, '12:00', 'UTC')
    database.add_coin_for_user(fake_user_id, 'bitcoin')
    
    simulate_daily_alerts()
