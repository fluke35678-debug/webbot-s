import sqlite3
import datetime

db_path = 'c:/test/audit_logs.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

test_events = [
    ("MESSAGE_DELETE", "1342160394835329065", "1431206603012444171", "ห้อง: ทั่วไป | เนื้อหา: สวัสดีครับ นี่คือข้อความทดสอบแบบยาวๆ เพื่อดูว่ามันจะตัดคำหรือแสดงผลได้ครบถ้วนไหมในหน้า Dashboard ของเรา", "MESSAGES"),
    ("VOICE_MOVE", "1342160394835329065", "1451493817386537042", "ย้ายจากห้อง เกมเมอร์ ไปยังห้อง พักผ่อนหย่อนใจ (AFK)", "VOICE"),
    ("ROLE_UPDATE", "System", "1431206603012444171", "เพิ่ม: @VIP, @Active Member | ลบ: @Newbie", "MODERATION")
]

timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for event in test_events:
    cur.execute('''
        INSERT INTO audit_logs (event_type, executor, target, details, timestamp, category)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (event[0], event[1], event[2], event[3], timestamp, event[4]))

conn.commit()
conn.close()
print("Inserted test Thai logs.")
