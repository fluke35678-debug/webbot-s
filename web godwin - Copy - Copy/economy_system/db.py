import sqlite3
import json
import os
import time

DB_PATH = os.path.join(os.getcwd(), 'economy.db')

def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_conn()
    cur = conn.cursor()
    
    # 1. Users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discord_id TEXT UNIQUE NOT NULL,
        username TEXT,
        balance REAL DEFAULT 0,
        energy INTEGER DEFAULT 100,
        daily_tx_count INTEGER DEFAULT 0,
        is_banned BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 2. Transactions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        amount REAL,
        description TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    # 3. Pets
    cur.execute("""
    CREATE TABLE IF NOT EXISTS pets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        species TEXT,
        name TEXT,
        level INTEGER DEFAULT 1,
        hunger INTEGER DEFAULT 100,
        health INTEGER DEFAULT 100,
        is_alive BOOLEAN DEFAULT 1,
        last_fed DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    # 4. Shop Items
    cur.execute("""
    CREATE TABLE IF NOT EXISTS shop_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        type TEXT,
        price REAL,
        stock INTEGER,
        conditions TEXT, -- JSON
        embed_config TEXT, -- JSON
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 5. Purchases
    cur.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        item_id INTEGER,
        quantity INTEGER DEFAULT 1,
        total_price REAL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(item_id) REFERENCES shop_items(id)
    )
    """)

    # 6. Logs
    cur.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        action TEXT,
        user_id INTEGER,
        details TEXT, -- JSON
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 7. Config
    cur.execute("""
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT, -- JSON
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 8. Cooldowns
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cooldowns (
        user_id INTEGER,
        activity_type TEXT,
        expires_at DATETIME,
        PRIMARY KEY (user_id, activity_type),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    # Seed Default Config if not exists
    # Seed Default Config if not exists
    default_configs = {
        "bank_interest_rate": 0.01,
        "bank_daily_limit": 10000,
        "game_luck_config": {"win_rate": 0.45, "multiplier": 1.9},
        "game_dice_config": {"multi_lowhigh": 1.9, "multi_number": 5.0},
        "activity_config": {
            "work": {
                "name": "Work", "emoji": "👷", "min_reward": 50, "max_reward": 200, "cooldown": 3600, 
                "fail_rate": 0.1, "fine_percent": 0.05, 
                "success_message": "You went to work and earned ${reward}!", 
                "fail_message": "You messed up at work and were fined ${fine}."
            },
            "crime": {
                "name": "Crime", "emoji": "🦹", "min_reward": 200, "max_reward": 800, "cooldown": 7200, 
                "fail_rate": 0.45, "fine_percent": 0.25, 
                "success_message": "You committed a crime and stole ${reward}!", 
                "fail_message": "You were caught by police and fined ${fine}."
            },
            "slut": {
                "name": "Slut", "emoji": "💋", "min_reward": 100, "max_reward": 400, "cooldown": 1800, 
                "fail_rate": 0.15, "fine_percent": 0.0, 
                "success_message": "You worked the corner and made ${reward}.", 
                "fail_message": "No customers today..."
            }
        },
        "pet_death_penalty": 500
    }
    
    for k, v in default_configs.items():
        try:
            val_str = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
            cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (k, val_str))
        except:
            pass

    conn.commit()
    conn.close()
    print(f"[Economy] Database initialized at {DB_PATH}")

if __name__ == "__main__":
    init_db()
