import time
import sqlite3
import math
from .db import get_db_conn

class MiningService:
    # Config: {gpu_level: (cost, rate_per_hour)}
    GPU_TIERS = {
        1: {"name": "GTX 1050", "cost": 500, "rate": 10},
        2: {"name": "RTX 3060", "cost": 2000, "rate": 50},
        3: {"name": "RTX 4090", "cost": 10000, "rate": 300},
        4: {"name": "Quantum Chip", "cost": 50000, "rate": 1500}
    }

    @staticmethod
    def get_stats(user_id):
        conn = get_db_conn()
        conn.row_factory = sqlite3.Row
        
        # Ensure table exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mining_stats (
                user_id TEXT PRIMARY KEY,
                gpu_level INTEGER DEFAULT 0,
                last_collected TIMESTAMP,
                mining_balance REAL DEFAULT 0
            )
        """)
        
        row = conn.execute("SELECT * FROM mining_stats WHERE user_id = ?", (str(user_id),)).fetchone()
        
        if not row:
            conn.execute("INSERT INTO mining_stats (user_id, gpu_level, last_collected, mining_balance) VALUES (?, 0, ?, 0)", (str(user_id), time.time()))
            conn.commit()
            row = {"gpu_level": 0, "last_collected": time.time(), "mining_balance": 0}
        else:
            row = dict(row)
            
        # Calculate pending
        current_time = time.time()
        last_time = row["last_collected"]
        level = row["gpu_level"]
        rate = MiningService.GPU_TIERS.get(level, {"rate": 0})["rate"]
        
        # Earn rate per second = rate / 3600
        elapsed = current_time - last_time
        pending = (rate / 3600) * elapsed
        
        row["pending_rewards"] = pending
        row["rate_per_hour"] = rate
        row["next_upgrade"] = MiningService.GPU_TIERS.get(level + 1)
        row["current_gpu"] = MiningService.GPU_TIERS.get(level, {"name": "None"})
        
        conn.close()
        return row

    @staticmethod
    def collect(user_id):
        stats = MiningService.get_stats(user_id)
        pending = stats["pending_rewards"]
        
        if pending <= 0.1:
            return {"success": False, "message": "Nothing to collect yet (Min 0.1)"}
            
        conn = get_db_conn()
        # Add to bank balance (using main bank table)
        # Note: We need to import BankService helper or do raw SQL update to bank_users
        conn.execute("UPDATE bank_users SET balance = balance + ? WHERE discord_id = ?", (pending, str(user_id)))
        
        # Reset timer
        conn.execute("UPDATE mining_stats SET last_collected = ? WHERE user_id = ?", (time.time(), str(user_id)))
        conn.commit()
        conn.close()
        
        return {"success": True, "message": f"Collected {pending:.2f} coins!", "amount": pending}

    @staticmethod
    def upgrade(user_id):
        stats = MiningService.get_stats(user_id)
        current_level = stats["gpu_level"]
        next_tier = MiningService.GPU_TIERS.get(current_level + 1)
        
        if not next_tier:
            return {"success": False, "message": "Max level reached!"}
            
        cost = next_tier["cost"]
        
        # Check balance
        conn = get_db_conn()
        user = conn.execute("SELECT balance FROM bank_users WHERE discord_id = ?", (str(user_id),)).fetchone()
        
        if not user or user[0] < cost:
            conn.close()
            return {"success": False, "message": f"Insufficient funds! Need {cost} coins."}
            
        # Deduct cost & Upgrade
        conn.execute("UPDATE bank_users SET balance = balance - ? WHERE discord_id = ?", (cost, str(user_id)))
        conn.execute("UPDATE mining_stats SET gpu_level = gpu_level + 1 WHERE user_id = ?", (str(user_id),))
        conn.commit()
        conn.close()
        
        return {"success": True, "message": f"Upgraded to {next_tier['name']}!"}
