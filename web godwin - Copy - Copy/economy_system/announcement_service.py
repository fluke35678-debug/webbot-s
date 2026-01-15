import sqlite3
import datetime
import json

DB_PATH = "gacha_bot.db"

class AnnouncementService:
    @staticmethod
    def get_conn():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def schedule_message(channel_id, content, embed_json, scheduled_time, author_id):
        conn = AnnouncementService.get_conn()
        conn.execute('''
            INSERT INTO scheduled_messages (channel_id, content, embed_json, scheduled_time, author_id, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        ''', (channel_id, content, json.dumps(embed_json) if embed_json else None, scheduled_time, author_id))
        conn.commit()
        conn.close()

    @staticmethod
    def get_pending_messages():
        conn = AnnouncementService.get_conn()
        # Get messages scheduled for now or past
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = conn.execute("SELECT * FROM scheduled_messages WHERE status = 'pending' AND scheduled_time <= ?", (now,)).fetchall()
        messages = [dict(row) for row in rows]
        
        # Mark as processing (or sent after processing)
        # We'll rely on the caller to mark as sent
        conn.close()
        return messages

    @staticmethod
    def mark_as_sent(msg_id):
        conn = AnnouncementService.get_conn()
        conn.execute("UPDATE scheduled_messages SET status = 'sent' WHERE id = ?", (msg_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_all_messages():
        conn = AnnouncementService.get_conn()
        rows = conn.execute("SELECT * FROM scheduled_messages ORDER BY scheduled_time DESC").fetchall()
        conn.close()
        return [dict(row) for row in rows]
