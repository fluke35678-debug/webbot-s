import sqlite3
import os

LOG_DB = 'c:/test/audit_logs.db'
def get_db_conn(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def simulate_view_logs(executor=None, category=None):
    conn = get_db_conn(LOG_DB)
    query = "SELECT * FROM audit_logs "
    params = []
    
    where_clauses = []
    if executor:
        where_clauses.append("executor LIKE ?")
        params.append(f"%{executor}%")
    if category:
        where_clauses.append("category = ?")
        params.append(category)
        
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
        
    query += " ORDER BY timestamp DESC LIMIT 100"
    print(f"Executing query: {query} with params: {params}")
    logs_raw = conn.execute(query, params).fetchall()
    conn.close()
    
    print(f"Results found: {len(logs_raw)}")
    for r in logs_raw:
        print(dict(r))

if __name__ == "__main__":
    simulate_view_logs()
