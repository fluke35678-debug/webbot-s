import sqlite3

DB_PATH = "gacha_bot.db"

def init_announcement_db():
    conn = sqlite3.connect(DB_PATH)
    
    # Scheduled Messages Table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS scheduled_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT NOT NULL,
        content TEXT,
        embed_json TEXT, -- Optional JSON for embed
        scheduled_time DATETIME NOT NULL,
        status TEXT DEFAULT 'pending', -- pending, sent, failed
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        author_id TEXT
    )
    ''')
    
    conn.commit()
    conn.close()
    print("Announcement table initialized in gacha_bot.db.")

if __name__ == "__main__":
    init_announcement_db()
