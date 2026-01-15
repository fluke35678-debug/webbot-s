import sqlite3

DB_PATH = "economy.db"

def init_inventory_db():
    conn = sqlite3.connect(DB_PATH)
    
    # Inventory Table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        quantity INTEGER DEFAULT 1,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, item_id)
    )
    ''')
    
    conn.commit()
    conn.close()
    print("Inventory table initialized in economy.db.")

if __name__ == "__main__":
    init_inventory_db()
