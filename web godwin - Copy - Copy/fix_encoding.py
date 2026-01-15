# Fix encoding issue in main_dashboard.py
# The Thai text was triple-encoded (UTF-8 -> Latin-1 -> UTF-8 -> Latin-1)

# Correct EVENT_TRANSLATIONS dictionary
CORRECT_TRANSLATIONS = '''# Log Translations
EVENT_TRANSLATIONS = {
    "ROLE_UPDATE": "เปลี่ยนบทบาท",
    "TIMEOUT": "ตั้งเวลาพักการใช้งาน",
    "GUILD_ROLE_UPDATE": "แก้ไขบทบาทเซิร์ฟเวอร์",
    "MESSAGE_DELETE": "ลบข้อความ",
    "MESSAGE_EDIT": "แก้ไขข้อความ",
    "VOICE_JOIN": "เข้าห้องเสียง",
    "VOICE_LEAVE": "ออกจากห้องเสียง",
    "VOICE_MOVE": "ย้ายห้องเสียง",
    "BAN": "แบนสมาชิก",
    "UNBAN": "ปลดแบนสมาชิก",
    "CHANNEL_CREATE": "สร้างห้อง",
    "CHANNEL_DELETE": "ลบห้อง",
    "GACHA_PULL": "สุ่มกาชา",
    "SALT_EXCHANGE": "แลกเกลือ",
    "ADMIN_UPDATE_USER": "แอดมินแก้ไขข้อมูลผู้ใช้",
    "ADMIN_BULK_GACHA": "แอดมินตั้งค่ากาชา",
    "ADMIN_ACHIEVEMENT": "แอดมินแก้ไขความสำเร็จ",
    "SERVER_STARTUP": "บอทเริ่มทำงาน",
    "MEMBER_JOIN": "สมาชิกใหม่เข้าเซิร์ฟเวอร์",
    "MEMBER_LEAVE": "สมาชิกออกจากเซิร์ฟเวอร์",
    "ROLE_CREATE": "สร้างบทบาทใหม่",
    "ROLE_DELETE": "ลบบทบาท",
    "GACHA_10_PULL": "สุ่มกาชา 10 ครั้ง"
}
'''

def fix_file():
    filepath = r"c:\web godwin\main_dashboard.py"
    
    # Read file
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find and replace the EVENT_TRANSLATIONS section
    import re
    pattern = r'# Log Translations\nEVENT_TRANSLATIONS = \{.*?\}'
    
    # Use DOTALL to match across newlines
    match = re.search(pattern, content, re.DOTALL)
    if match:
        old_content = match.group(0)
        new_content = content.replace(old_content, CORRECT_TRANSLATIONS.strip())
        
        # Write back
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Successfully fixed EVENT_TRANSLATIONS!")
        return True
    else:
        print("Could not find pattern to replace")
        return False

if __name__ == "__main__":
    fix_file()
