from flask import Flask, render_template_string
import database
from datetime import datetime, timedelta
import sqlite3
import os
from dotenv import load_dotenv
load_dotenv()  # add this at the very top

DATABASE_PATH = os.getenv("DATABASE_PATH")

app = Flask(__name__)

# HTML Template with modern styling
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 Crypto Dip Bot Dashboard</title>
    <meta http-equiv="refresh" content="30">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'SF Pro Display', -apple-system, system-ui, sans-serif; 
            background: #0a0a0a;
            color: #ffffff;
            min-height: 100vh;
            padding: 20px;
        }
        .container { 
            max-width: 1400px; 
            margin: 0 auto; 
        }
        .header {
            text-align: center;
            margin-bottom: 40px;
        }
        .header h1 {
            font-size: 2.2em;
            margin-bottom: 10px;
            font-weight: 300;
            color: #ffffff;
        }
        .last-updated {
            background: #1a1a1a;
            padding: 8px 16px;
            border-radius: 6px;
            display: inline-block;
            color: #888;
            font-size: 0.9em;
            border: 1px solid #2a2a2a;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: #111111;
            border: 1px solid #2a2a2a;
            border-radius: 8px;
            padding: 24px;
            text-align: center;
            transition: border-color 0.2s ease;
        }
        .stat-card:hover {
            border-color: #444;
        }
        .stat-number {
            font-size: 2.2em;
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 6px;
        }
        .stat-label {
            color: #888;
            font-weight: 400;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-size: 0.8em;
        }
        .section {
            background: #111111;
            border: 1px solid #2a2a2a;
            border-radius: 8px;
            padding: 24px;
            margin-bottom: 20px;
        }
        .section h2 {
            color: #ffffff;
            margin-bottom: 20px;
            font-size: 1.3em;
            font-weight: 500;
            border-bottom: 1px solid #2a2a2a;
            padding-bottom: 12px;
        }
        .two-column {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        .coin-list {
            max-height: 400px;
            overflow-y: auto;
        }
        .coin-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #2a2a2a;
        }
        .coin-item:last-child {
            border-bottom: none;
        }
        .coin-name {
            font-weight: 500;
            color: #ffffff;
        }
        .coin-users {
            background: #2a2a2a;
            color: #ffffff;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: 500;
        }
        .activity-item {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #2a2a2a;
        }
        .activity-item:last-child {
            border-bottom: none;
        }
        .activity-date {
            color: #888;
            font-size: 0.9em;
        }
        .activity-count {
            font-weight: 500;
            color: #ffffff;
        }
        .status-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-good { background: #10b981; }
        .status-warning { background: #f59e0b; }
        .status-error { background: #ef4444; }
        
        .messages-list {
            max-height: 500px;
            overflow-y: auto;
        }
        .message-item {
            background: #1a1a1a;
            border: 1px solid #2a2a2a;
            border-radius: 6px;
            padding: 16px;
            margin-bottom: 12px;
        }
        .message-item.message-unread {
            border-left: 3px solid #f59e0b;
            background: #1f1a0a;
        }
        .message-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            font-size: 0.85em;
        }
        .message-user {
            font-weight: 500;
            color: #888;
        }
        .message-time {
            color: #666;
        }
        .message-text {
            color: #ffffff;
            line-height: 1.4;
            word-wrap: break-word;
        }
        .message-badge {
            background: #f59e0b;
            color: #000;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.7em;
            font-weight: 600;
            margin-left: 8px;
        }
        .no-messages {
            color: #666;
            text-align: center;
            padding: 40px 20px;
            font-style: italic;
        }
        
        @media (max-width: 768px) {
            .two-column {
                grid-template-columns: 1fr;
            }
            .stats-grid {
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Crypto Dip Bot Dashboard</h1>
            <div class="last-updated">
                <span class="status-indicator status-good"></span>
                Last updated: {{ last_updated }}
            </div>
        </div>

        <!-- Overview Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{{ stats.total_users }}</div>
                <div class="stat-label">Total Users</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.active_users }}</div>
                <div class="stat-label">Active Users</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.total_watchlist_entries }}</div>
                <div class="stat-label">Watchlist Items</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ "%.1f"|format(stats.avg_coins_per_user) }}</div>
                <div class="stat-label">Avg Coins/User</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.new_users_7d }}</div>
                <div class="stat-label">New Users (7d)</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.price_records|default(0)|int }}</div>
                <div class="stat-label">Price Records</div>
            </div>
        </div>

        <!-- Two Column Layout -->
        <div class="two-column">
            <!-- Popular Coins -->
            <div class="section">
                <h2>🔥 Most Popular Coins</h2>
                <div class="coin-list">
                    {% for coin in popular_coins %}
                    <div class="coin-item">
                        <div class="coin-name">{{ coin.symbol }} - {{ coin.name }}</div>
                        <div class="coin-users">{{ coin.user_count }} users</div>
                    </div>
                    {% endfor %}
                </div>
            </div>

            <!-- Recent Activity -->
            <div class="section">
                <h2>📈 Recent Signups</h2>
                <div class="activity-list">
                    {% for signup in recent_signups %}
                    <div class="activity-item">
                        <div class="activity-date">{{ signup.date }}</div>
                        <div class="activity-count">{{ signup.count }} users</div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>

        <!-- User Distribution -->
        <div class="section">
            <h2>👥 User Distribution by Coin Count</h2>
            <div class="stats-grid">
                {% for dist in user_distribution %}
                <div class="stat-card">
                    <div class="stat-number">{{ dist.count }}</div>
                    <div class="stat-label">{{ dist.range }}</div>
                </div>
                {% endfor %}
            </div>
        </div>

        <!-- User Messages -->
        <div class="section">
            <h2>💬 User Messages 
                {% if unread_count > 0 %}
                <span class="message-badge">{{ unread_count }} new</span>
                {% endif %}
            </h2>
            <div class="messages-list">
                {% if user_messages %}
                    {% for msg in user_messages %}
                    <div class="message-item {% if msg.status == 'unread' %}message-unread{% endif %}">
                        <div class="message-header">
                            <span class="message-user">User {{ msg.telegram_id }}</span>
                            <span class="message-time">{{ msg.timestamp }}</span>
                            {% if msg.status == 'unread' %}
                            <span class="status-indicator status-warning"></span>
                            {% endif %}
                        </div>
                        <div class="message-text">{{ msg.message }}</div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="no-messages">No messages yet. Users can send feedback with /message</div>
                {% endif %}
            </div>
        </div>

        <!-- System Status -->
        <div class="section">
            <h2>⚡ System Status</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number">{{ stats.tracked_coins }}</div>
                    <div class="stat-label">Coins Tracked</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{{ alerts_sent_today }}</div>
                    <div class="stat-label">Alerts Sent Today</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{{ active_alarms }}</div>
                    <div class="stat-label">Active Alarms</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">
                        {% if database_health == 'good' %}
                        <span class="status-indicator status-good"></span>Good
                        {% elif database_health == 'warning' %}
                        <span class="status-indicator status-warning"></span>Warning  
                        {% else %}
                        <span class="status-indicator status-error"></span>Error
                        {% endif %}
                    </div>
                    <div class="stat-label">Database Health</div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

def get_dashboard_data():
    """Get all dashboard data"""
    try:
        # Basic stats
        stats = database.get_admin_stats()
        
        # Popular coins with proper formatting
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                uc.coin_id,
                COALESCE(ci.symbol, UPPER(uc.coin_id)) as symbol,
                COALESCE(ci.name, uc.coin_id) as name,
                COUNT(uc.telegram_id) as user_count
            FROM user_coins uc
            LEFT JOIN coin_info ci ON uc.coin_id = ci.coin_id
            GROUP BY uc.coin_id
            ORDER BY user_count DESC
            LIMIT 15
        ''')
        
        popular_coins = []
        for row in cursor.fetchall():
            popular_coins.append({
                'coin_id': row[0],
                'symbol': row[1],
                'name': row[2],
                'user_count': row[3]
            })
        
        # Recent signups
        cursor.execute('''
            SELECT DATE(created_at) as signup_date, COUNT(*) as signups
            FROM users 
            WHERE created_at >= datetime('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY signup_date DESC
        ''')
        
        recent_signups = []
        for row in cursor.fetchall():
            recent_signups.append({
                'date': row[0],
                'count': row[1]
            })
        
        # User distribution
        cursor.execute('''
            SELECT 
                CASE 
                    WHEN coin_count = 0 THEN '0 coins'
                    WHEN coin_count BETWEEN 1 AND 3 THEN '1-3 coins'
                    WHEN coin_count BETWEEN 4 AND 7 THEN '4-7 coins'
                    WHEN coin_count BETWEEN 8 AND 15 THEN '8-15 coins'
                    ELSE '15+ coins'
                END as range_group,
                COUNT(*) as user_count
            FROM (
                SELECT u.telegram_id, COUNT(uc.coin_id) as coin_count
                FROM users u
                LEFT JOIN user_coins uc ON u.telegram_id = uc.telegram_id
                GROUP BY u.telegram_id
            )
            GROUP BY range_group
        ''')
        
        user_distribution = []
        for row in cursor.fetchall():
            user_distribution.append({
                'range': row[0],
                'count': row[1]
            })
        
        # Alerts sent today
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('SELECT COUNT(DISTINCT telegram_id) FROM alerts_sent WHERE date_sent = ?', (today,))
        alerts_sent_today = cursor.fetchone()[0]
        
        # Active alarms (users with alarm_time set)
        cursor.execute('SELECT COUNT(*) FROM users WHERE alarm_time IS NOT NULL AND alarm_time != ""')
        active_alarms = cursor.fetchone()[0]
        
        # User messages
        cursor.execute('SELECT telegram_id, message, timestamp, status FROM user_messages ORDER BY timestamp DESC LIMIT 20')
        user_messages = []
        for row in cursor.fetchall():
            user_messages.append({
                'telegram_id': row[0],
                'message': row[1],
                'timestamp': row[2],
                'status': row[3]
            })
        
        # Count unread messages
        cursor.execute('SELECT COUNT(*) FROM user_messages WHERE status = "unread"')
        unread_count = cursor.fetchone()[0]
        
        conn.close()
        
        # Database health check
        database_health = 'good'
        if stats['price_records'] < 100:
            database_health = 'warning'
        if stats['total_users'] == 0:
            database_health = 'error'
        
        return {
            'stats': stats,
            'popular_coins': popular_coins,
            'recent_signups': recent_signups,
            'user_distribution': user_distribution,
            'alerts_sent_today': alerts_sent_today,
            'active_alarms': active_alarms,
            'user_messages': user_messages,
            'unread_count': unread_count,
            'database_health': database_health,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
        
    except Exception as e:
        print(f"Dashboard error: {e}")
        return {
            'stats': {'total_users': 0, 'active_users': 0, 'total_watchlist_entries': 0, 
                     'avg_coins_per_user': 0, 'new_users_7d': 0, 'price_records': 0, 'tracked_coins': 0},
            'popular_coins': [],
            'recent_signups': [],
            'user_distribution': [],
            'alerts_sent_today': 0,
            'active_alarms': 0,
            'user_messages': [],
            'unread_count': 0,
            'database_health': 'error',
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }

@app.route('/')
def dashboard():
    data = get_dashboard_data()
    return render_template_string(DASHBOARD_HTML, **data)

@app.route('/health')
def health_check():
    """Simple health check endpoint"""
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}

if __name__ == '__main__':
    database.init_database()  # Make sure database is ready
    print("🚀 Starting Crypto Bot Dashboard...")
    print("📊 Dashboard will be available at: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)