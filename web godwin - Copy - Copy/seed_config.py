import sqlite3
import json
import os

DB_PATH = 'economy.db'
DEFAULT_CONFIGS = {
    "game_luck_config": {"win_rate": 0.45, "multiplier": 1.9},
    "game_dice_config": {"multi_lowhigh": 1.9, "multi_number": 5.0},
    "activity_config": {
        "work": {
            "min_reward": 50, "max_reward": 200, 
            "cooldown": 3600, "fail_rate": 0.1, "fine_percent": 0.05
        },
        "crime": {
            "min_reward": 100, "max_reward": 500, 
            "cooldown": 7200, "fail_rate": 0.4, "fine_percent": 0.2
        },
        "slut": {
            "min_reward": 20, "max_reward": 100, 
            "cooldown": 1800, "fail_rate": 0.05, "fine_percent": 0.0
        }
    },
    "bank_interest_rate": 0.01,
    "bank_daily_limit": 10000,
    "pet_death_penalty": 0.5
}

def seed():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Seeding configurations...")
    for key, value in DEFAULT_CONFIGS.items():
        # Check if exists
        cursor.execute("SELECT 1 FROM config WHERE key = ?", (key,))
        if not cursor.fetchone():
            print(f"Inserting missing config: {key}")
            val_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            cursor.execute("INSERT INTO config (key, value) VALUES (?, ?)", (key, val_str))
        else:
            print(f"Config {key} already exists.")
            
    conn.commit()
    conn.close()
    print("Seeding complete.")

if __name__ == "__main__":
    seed()
