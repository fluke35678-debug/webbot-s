import sqlite3
import datetime

def insert_test_logs():
    conn = sqlite3.connect('c:/test/audit_logs.db')
    cursor = conn.cursor()
    
    # We'll use a placeholder executor ID that likely exists in the bot's world
    # or just use a generic one to test the "Unknown" case as well.
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    logs = [
        ("GACHA_PULL", "123456789", "self", '{"rank": "Legendary"}', "ECONOMY", now),
        ("ADMIN_UPDATE_USER", "AdminPanel", "123456789", 'Tickets updated from 0 to 100', "MODERATION", now),
        ("ROLE_UPDATE", "987654321", "123456789", 'Added role: VIP', "MODERATION", now)
    ]
    
    cursor.executemany('''
        INSERT INTO audit_logs (event_type, executor, target, details, category, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', logs)
    
    conn.commit()
    conn.close()
    print("Test logs inserted successfully.")

if __name__ == "__main__":
    insert_test_logs()
