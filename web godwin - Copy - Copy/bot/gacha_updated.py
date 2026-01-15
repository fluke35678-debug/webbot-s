import sqlite3
import random
import json
import os

# Base path for the database (root level)
GACHA_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'gacha_bot.db')

class GachaSystem:
    @staticmethod
    def get_config():
        """Fetches current gacha configuration from database including embed settings."""
        conn = sqlite3.connect(GACHA_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gacha_settings")
        rows = cursor.fetchall()
        conn.close()
        
        config = {}
        for row in rows:
            name = row['rank_name']
            try:
                roles = json.loads(row['reward_roles_json']) if row['reward_roles_json'] else []
            except:
                roles = []
            
            config[name] = {
                "percentage": row['percentage'],
                "roles": roles,
                "embed": {
                    "title": row['embed_title'],
                    "description": row['embed_description'],
                    "color": row['embed_color'],
                    "image": row['embed_image_url'],
                    "thumbnail": row['embed_thumbnail_url'],
                    "footer": row['embed_footer']
                }
            }
        return config

    @staticmethod
    def get_stats(user_id):
        conn = sqlite3.connect(GACHA_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT tickets, salt, total_rolls FROM users WHERE user_id = ?", (str(user_id),))
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT OR IGNORE INTO users (user_id, tickets, salt, total_rolls) VALUES (?, 0, 0, 0)", (str(user_id),))
            conn.commit()
            cursor.execute("SELECT tickets, salt, total_rolls FROM users WHERE user_id = ?", (str(user_id),))
            row = cursor.fetchone()
        conn.close()
        return {"tickets": row[0], "salt": row[1], "total_rolls": row[2]}

    @staticmethod
    async def pull_single(user_id):
        config = GachaSystem.get_config()
        rand = random.uniform(0, 100)
        cumulative = 0
        selected_rank = "Salt"
        
        # Sort by percentage to ensure correct logic (though usually sum is 100)
        # We'll just trust the order for now or sort manually
        sorted_ranks = sorted(config.keys(), key=lambda x: config[x]['percentage'])
        
        for rank in sorted_ranks:
            chance = config[rank]['percentage']
            cumulative += chance
            if rand <= cumulative:
                selected_rank = rank
                break
        
        reward_role_id = None
        if config[selected_rank]['roles']:
            reward_role_id = random.choice(config[selected_rank]['roles'])
            
        return selected_rank, reward_role_id, config[selected_rank]['embed']

    @staticmethod
    async def pull(user_id, count=1):
        results = []
        total_salt = 0
        
        for _ in range(count):
            rank, role_id, embed_data = await GachaSystem.pull_single(user_id)
            results.append((rank, role_id, embed_data))
            if rank == "Salt":
                total_salt += 1

        # Update Database
        conn = sqlite3.connect(GACHA_DB)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET total_rolls = total_rolls + ?,
                salt = salt + ?
            WHERE user_id = ?
        ''', (count, total_salt, str(user_id)))
        conn.commit()
        conn.close()

        return results

    @staticmethod
    async def exchange_salt(user_id):
        conn = sqlite3.connect(GACHA_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT salt FROM users WHERE user_id = ?", (str(user_id),))
        row = cursor.fetchone()
        if row and row[0] >= 10:
            cursor.execute("UPDATE users SET salt = salt - 10, tickets = tickets + 1 WHERE user_id = ?", (str(user_id),))
            conn.commit()
            conn.close()
            return True
        conn.close()
        return False
