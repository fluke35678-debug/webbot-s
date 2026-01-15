import sqlite3
import datetime
import json
import random

GACHA_DB = "gacha_bot.db"

class GiveawayService:
    @staticmethod
    def get_conn():
        conn = sqlite3.connect(GACHA_DB)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def create_giveaway(title, description, prize_type, prize_value, end_time_str, winner_count, channel_id, host_id, requirements=None):
        conn = GiveawayService.get_conn()
        cursor = conn.cursor()
        
        req_json = json.dumps(requirements or {})
        
        cursor.execute('''
            INSERT INTO giveaways (title, description, prize_type, prize_value, end_time, winner_count, channel_id, host_id, requirements_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
        ''', (title, description, prize_type, prize_value, end_time_str, winner_count, channel_id, host_id, req_json))
        
        giveaway_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return giveaway_id

    @staticmethod
    def get_active_giveaways():
        conn = GiveawayService.get_conn()
        rows = conn.execute("SELECT * FROM giveaways WHERE status = 'active' ORDER BY end_time ASC").fetchall()
        conn.close()
        return [dict(row) for row in rows]
        
    @staticmethod
    def get_giveaway(giveaway_id):
        conn = GiveawayService.get_conn()
        row = conn.execute("SELECT * FROM giveaways WHERE id = ?", (giveaway_id,)).fetchone()
        conn.close()
        return dict(row) if row else None
        
    @staticmethod
    def enter_giveaway(giveaway_id, user_id):
        conn = GiveawayService.get_conn()
        try:
            conn.execute("INSERT INTO giveaway_entries (giveaway_id, user_id) VALUES (?, ?)", (giveaway_id, user_id))
            conn.commit()
            return True, "Entered successfully"
        except sqlite3.IntegrityError:
            return False, "Already entered"
        finally:
            conn.close()
            
    @staticmethod
    def end_giveaway(giveaway_id):
        conn = GiveawayService.get_conn()
        giveaway = conn.execute("SELECT * FROM giveaways WHERE id = ?", (giveaway_id,)).fetchone()
        
        if not giveaway or giveaway['status'] != 'active':
            conn.close()
            return None
            
        entries = conn.execute("SELECT user_id FROM giveaway_entries WHERE giveaway_id = ?", (giveaway_id,)).fetchall()
        participant_ids = [row['user_id'] for row in entries]
        
        winner_count = giveaway['winner_count']
        winners = []
        
        if len(participant_ids) > 0:
            if len(participant_ids) <= winner_count:
                winners = participant_ids
            else:
                winners = random.sample(participant_ids, winner_count)
                
        # Update status
        conn.execute("UPDATE giveaways SET status = 'ended', winner_id = ? WHERE id = ?", (json.dumps(winners), giveaway_id))
        conn.commit()
        conn.close()
        
        return {
            "giveaway": dict(giveaway),
            "winners": winners
        }
