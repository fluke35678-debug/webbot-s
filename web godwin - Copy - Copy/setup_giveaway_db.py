import sqlite3

GACHA_DB = "gacha_bot.db"

def init_giveaway_db():
    conn = sqlite3.connect(GACHA_DB)
    
    # Giveaways Table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS giveaways (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id TEXT,
        channel_id TEXT,
        title TEXT NOT NULL,
        description TEXT,
        prize_type TEXT NOT NULL, -- 'money', 'ticket', 'role', 'custom'
        prize_value TEXT NOT NULL, -- Amount or Role ID or Item Name
        start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        end_time DATETIME NOT NULL,
        winner_count INTEGER DEFAULT 1,
        requirements_json TEXT DEFAULT '{}', -- {"role_id": "...", "min_balance": 100}
        status TEXT DEFAULT 'active', -- active, ended, cancelled
        host_id TEXT
    )
    ''')
    
    # Entries Table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS giveaway_entries (
        giveaway_id INTEGER,
        user_id TEXT,
        entry_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (giveaway_id, user_id)
    )
    ''')
    
    conn.commit()
    conn.close()
    print("Giveaway database tables initialized.")

if __name__ == "__main__":
    init_giveaway_db()
