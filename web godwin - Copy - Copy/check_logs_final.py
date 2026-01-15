import sqlite3
import os

LOG_DB = 'c:/test/audit_logs.db'
def get_db_conn(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def check():
    print(f"Checking DB: {LOG_DB}")
    if not os.path.exists(LOG_DB):
        print("DB File does NOT exist!")
        return
    
    conn = get_db_conn(LOG_DB)
    try:
        rows = conn.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC").fetchall()
        print(f"Total rows found: {len(rows)}")
        for r in rows:
            print(dict(r))
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check()
