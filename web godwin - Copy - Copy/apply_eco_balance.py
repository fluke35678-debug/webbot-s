import sqlite3
import json
import os

ECO_DB = os.path.join(os.getcwd(), 'economy.db')

def apply_eco_balance():
    if not os.path.exists(ECO_DB):
        print(f"Database not found at {ECO_DB}")
        return

    print(f"Checking Economy Config in {ECO_DB}...")
    conn = sqlite3.connect(ECO_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check if config exists
    try:
        row = cursor.execute("SELECT value FROM config WHERE key = 'activity_config'").fetchone()
        
        # New Balanced Config
        new_config = {
             "work": {"min": 100, "max": 300, "cooldown": 60, "fail_rate": 0.0, "emoji": "💼", "name": "Work", "msg_win": "You worked and earned ${reward}!", "msg_fail": "You failed."},
             "crime": {"min": 600, "max": 1800, "cooldown": 120, "fail_rate": 0.45, "fine_percent": 0.15, "emoji": "🔫", "name": "Crime", "msg_win": "You committed a crime and stole ${reward}!", "msg_fail": "You were caught and fined ${fine}!"},
             "slut": {"min": 300, "max": 700, "cooldown": 120, "fail_rate": 0.2, "fine_percent": 0.05, "emoji": "💋", "name": "Slut", "msg_win": "You worked the corner and got ${reward}!", "msg_fail": "Nobody wanted you today."}
        }
        
        json_val = json.dumps(new_config)
        
        if row:
            print("Updating existing activity_config...")
            cursor.execute("UPDATE config SET value = ? WHERE key = 'activity_config'", (json_val,))
        else:
            print("Inserting new activity_config...")
            # Ensure config table exists
            cursor.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
            cursor.execute("INSERT INTO config (key, value) VALUES (?, ?)", ('activity_config', json_val))
            
        conn.commit()
        print("Economy Balance Patch Applied!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    apply_eco_balance()
