import sqlite3
conn = sqlite3.connect('c:/test/audit_logs.db')
conn.row_factory = sqlite3.Row
logs = conn.execute("SELECT * FROM audit_logs").fetchall()
print(f"Total logs in DB: {len(logs)}")
for l in logs[:5]:
    print(dict(l))
conn.close()
