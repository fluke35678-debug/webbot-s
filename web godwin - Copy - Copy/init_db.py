import sqlite3
import json

def init_db():
    # Initialize gacha_bot.db
    conn = sqlite3.connect('c:/test/gacha_bot.db')
    cursor = conn.cursor()
    
    # Gacha Settings Table
    cursor.execute('DROP TABLE IF EXISTS gacha_settings')
    cursor.execute('''
        CREATE TABLE gacha_settings (
            rank_name TEXT PRIMARY KEY,
            percentage REAL,
            reward_roles_json TEXT
        )
    ''')
    
    default_ranks = [
        ("Legendary", 0.5, [1241852340617613353, 1251534834178850886, 1250490235595259976, 1423659121584111676]),
        ("Epic", 4.5, [1242044634872418374, 1280817060623945738, 1251154733712932934, 1251155305547698276, 1396512008723234966, 1423651612504625245, 1371699372093603912]),
        ("Rare", 15.0, [1247797350789812255, 1247796948476493894, 1247797148461039678, 1242044634324204288, 1242044627633180702, 1242044631592472626]),
        ("Common", 50.0, [
            1241862032874143744, 1241862196309524571, 1241861482224943265, 1241862290307809362,
            1242043563534192670, 1275361758638506025, 1275361339241402431, 1275362401986019422,
            1275362368842366976, 1264874786157494282, 1264874350297878589, 1264873603175022662,
            1264874778007699537, 1264875239612092426, 1264875249304993813, 1250741913359880243,
            1250741910025408522, 1250741464153985074, 1250741917675819029, 1250741457023668277,
            1250741287775371316, 1250758274689536142, 1250740960036392993, 1250490170419974154,
            1248177030319706144, 1247941887864606761, 1247941646365229168, 1247942491362168873,
            1247941985621250140, 1247941747032588464, 1247942232145661993, 1242143933681635410,
            1242143944415121408, 1242143948026417173, 1242143951121678377, 1242143954561138740,
            1242133990337679370, 1242134006397403157, 1242134003377504286
        ]),
        ("Salt", 30.0, [])
    ]
    
    for name, chance, roles in default_ranks:
        cursor.execute('INSERT INTO gacha_settings VALUES (?, ?, ?)', (name, chance, json.dumps(roles)))

    # Achievement Roles Table
    cursor.execute('DROP TABLE IF EXISTS achievement_roles')
    cursor.execute('''
        CREATE TABLE achievement_roles (
            name TEXT PRIMARY KEY,
            role_id TEXT,
            requirement_value INTEGER,
            stat_key TEXT
        )
    ''')
    
    default_achievements = [
        ("ผีพนัน", "1358517639177048154", 30, "total_rolls"),
        ("ยอดนักสุ่ม", "1358517424596451380", 50, "total_rolls"),
        ("ราชาเกลือ", "1358517466099089692", 100, "salt")
    ]
    
    for name, rid, val, key in default_achievements:
        cursor.execute('INSERT INTO achievement_roles VALUES (?, ?, ?, ?)', (name, rid, val, key))
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            tickets INTEGER DEFAULT 0,
            salt INTEGER DEFAULT 0,
            total_rolls INTEGER DEFAULT 0,
            custom_title TEXT
        )
    ''')
    
    # Simple migration to add custom_title if it doesn't exist
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN custom_title TEXT")
    except sqlite3.OperationalError:
        pass # Column already exists
    
    # Event Questions Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # User Event Answers (to track who answered which question)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            question_id INTEGER NOT NULL,
            answered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, question_id)
        )
    ''')
    
    conn.commit()
    conn.close()

    # Initialize audit_logs.db
    conn = sqlite3.connect('c:/test/audit_logs.db')
    cursor = conn.cursor()
    
    # Check if category column exists, if not, add it (simple migration)
    try:
        cursor.execute('ALTER TABLE audit_logs ADD COLUMN category TEXT DEFAULT "GENERAL"')
    except:
        pass # Already exists
        
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            executor TEXT,
            target TEXT,
            details TEXT,
            category TEXT DEFAULT 'GENERAL',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("Databases fully re-initialized with dynamic gacha and achievements.")

if __name__ == "__main__":
    init_db()
