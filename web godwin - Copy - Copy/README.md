# Discord Admin Backoffice - Quick Start Guide

## ขั้นตอนการติดตั้งและรัน

### 1. ติดตั้ง Dependencies
```bash
pip install fastapi uvicorn discord.py jinja2 aiohttp
```

### 2. สร้างฐานข้อมูล
```bash
python init_db.py
```

### 3. ตั้งค่า Bot Token
แก้ไขไฟล์ `bot/main.py` บรรทัดที่ 14:
```python
TOKEN = "ใส่ Discord Bot Token ของคุณที่นี่"
```

### 4. รัน Dashboard (Terminal 1)
```bash
python main_dashboard.py
```
เปิดเบราว์เซอร์ที่: http://localhost:8000

### 5. รัน Discord Bot (Terminal 2)
```bash
python bot/main.py
```

## หมายเหตุ
- Lint errors ใน HTML templates เป็น false positive จาก IDE (Jinja2 syntax ถูกต้อง)
- ระบบจะทำงานได้ปกติแม้มี lint warnings เหล่านั้น
