import sqlite3
conn = sqlite3.connect('c:/test/audit_logs.db')
cursor = conn.cursor()
cursor.execute("DELETE FROM audit_logs")
conn.commit()
conn.close()
print("Audit logs cleared.")
