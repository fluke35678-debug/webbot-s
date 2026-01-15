# วิธีรันระบบ Discord Admin Backoffice

## ⚠️ ข้อกำหนดเบื้องต้น

คุณต้องติดตั้ง Python จริงๆ ก่อนครับ (ไม่ใช่ Windows Store stub)

### ติดตั้ง Python:
1. ดาวน์โหลดจาก: https://www.python.org/downloads/
2. เลือก "Add Python to PATH" ตอนติดตั้ง
3. ตรวจสอบว่าติดตั้งสำเร็จ: `python --version`

---

## 🚀 ขั้นตอนการรัน (หลังติดตั้ง Python แล้ว)

### 1. ติดตั้ง Dependencies
```powershell
cd c:\test
pip install fastapi uvicorn discord.py jinja2 aiohttp python-multipart
```

### 2. สร้างฐานข้อมูล
```powershell
python init_db.py
```

### 3. ตั้งค่า Discord Bot Token
แก้ไขไฟล์ `bot/main.py` บรรทัดที่ 14:
```python
TOKEN = "ใส่ Bot Token ของคุณที่นี่"
```

### 4. รัน Web Dashboard (Terminal หน้าต่างที่ 1)
```powershell
python main_dashboard.py
```
เปิดเบราว์เซอร์: http://localhost:8000

### 5. รัน Discord Bot (Terminal หน้าต่างที่ 2)
```powershell
python bot/main.py
```

---

## 📋 หน้าเว็บที่มีให้ใช้งาน

- **User Management** (`/users`) - จัดการ Tickets และ Salt ของผู้เล่น
- **Gacha Config** (`/gacha`) - ปรับเรทการสุ่มแบบ Real-time
- **Live Logs** (`/logs`) - ดูประวัติกิจกรรมทั้งหมด
- **Analytics** (`/analytics`) - กราฟสถิติและเศรษฐศาสตร์
- **Embed Creator** (`/embed`) - สร้างประกาศ Discord แบบมืออาชีพ

---

## 🎮 คำสั่งบอทที่ใช้ได้

- `!gacha` - สุ่มกาชา (ไม่มี Cooldown)
- `!work` - ทำงาน (ไม่มี Cooldown)
- `!trade` - เทรด (ไม่มี Cooldown)
- `!ipo` - ตลาดหุ้น (ไม่มี Cooldown)

---

## 💡 Tips

- ระบบจะแสดง "BOT_STATUS: ONLINE" เมื่อบอทเชื่อมต่อสำเร็จ
- Heartbeat จะอัปเดตทุก 60 วินาที
- ข้อมูลทั้งหมดเก็บใน `gacha_bot.db` และ `audit_logs.db`
