import sqlite3

DB_PATH = "gacha_bot.db"

def init_verification_db():
    conn = sqlite3.connect(DB_PATH)
    
    # Verification Config Table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS verification_config (
        guild_id TEXT PRIMARY KEY,
        channel_id TEXT,
        role_id TEXT,
        embed_title TEXT DEFAULT 'Verification',
        embed_description TEXT DEFAULT 'Click the button below to verify yourself.',
        embed_color TEXT DEFAULT '#10b981',
        button_label TEXT DEFAULT 'Verify ✅'
    )
    ''')
    
    conn.commit()
    conn.close()
    print("Verification config table initialized in gacha_bot.db.")

if __name__ == "__main__":
    init_verification_db()
