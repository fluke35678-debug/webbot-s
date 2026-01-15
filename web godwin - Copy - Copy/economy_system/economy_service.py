import random
import json
from datetime import datetime, timedelta

from .db import get_db_conn
from .bank_service import BankService
from .schemas import *

class EconomyService:
    """Core business logic for the economy system."""

    @staticmethod
    def get_balance(discord_id: str) -> float:
        user = BankService.get_user(discord_id)
        if not user:
            raise Exception("User not found")
        return user.get("balance", 0.0)

    @staticmethod
    def deposit(discord_id: str, amount: float, description: str = "Deposit") -> float:
        return BankService.deposit(discord_id, amount, description)

    @staticmethod
    def withdraw(discord_id: str, amount: float, description: str = "Withdraw") -> float:
        return BankService.withdraw(discord_id, amount, description)

    @staticmethod
    def transfer(sender_id: str, recipient_id: str, amount: float, description: str = "Transfer") -> bool:
        return BankService.transfer(sender_id, recipient_id, amount, description)

    @staticmethod
    def claim_daily(discord_id: str) -> float:
        """User can claim a daily reward once every 24h. Reward amount is random between 100 and 500."""
        conn = get_db_conn()
        try:
            user = conn.execute("SELECT id, balance FROM users WHERE discord_id = ?", (discord_id,)).fetchone()
            if not user:
                raise Exception("User not found")
            # Check cooldown table
            now = datetime.utcnow()
            row = conn.execute(
                "SELECT expires_at FROM cooldowns WHERE user_id = ? AND activity_type = 'daily'",
                (user["id"],)
            ).fetchone()
            if row and datetime.fromisoformat(row["expires_at"]) > now:
                raise Exception("Daily reward already claimed. Try later.")
            reward = random.randint(100, 500)
            new_bal = user["balance"] + reward
            conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_bal, user["id"]))
            conn.execute(
                "INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)",
                (user["id"], "daily_reward", reward, "Daily reward claim"),
            )
            # Set next cooldown (24h)
            expires = now + timedelta(hours=24)
            conn.execute(
                "INSERT OR REPLACE INTO cooldowns (user_id, activity_type, expires_at) VALUES (?, ?, ?)",
                (user["id"], "daily", expires.isoformat()),
            )
            conn.commit()
            return reward
        finally:
            conn.close()

    @staticmethod
    def get_jobs() -> list:
        conn = get_db_conn()
        try:
            row = conn.execute("SELECT value FROM config WHERE key = 'activity_config'").fetchone()
            print(f"[DEBUG] DB Row: {dict(row) if row else 'None'}")
            if row:
                config = json.loads(row["value"])
                print(f"[DEBUG] Loaded Config: {config.keys() if isinstance(config, dict) else type(config)}")
            else:
                # Fallback Defaults
                config = {
                    "work": {"min": 100, "max": 300, "cooldown": 60, "fail_rate": 0.0, "emoji": "💼", "name": "Work", "msg_win": "You worked and earned ${reward}!", "msg_fail": "You failed."},
                    "crime": {"min": 600, "max": 1800, "cooldown": 120, "fail_rate": 0.45, "fine_percent": 0.15, "emoji": "🔫", "name": "Crime", "msg_win": "You committed a crime and stole ${reward}!", "msg_fail": "You were caught and fined ${fine}!"},
                    "slut": {"min": 300, "max": 700, "cooldown": 120, "fail_rate": 0.2, "fine_percent": 0.05, "emoji": "💋", "name": "Slut", "msg_win": "You worked the corner and got ${reward}!", "msg_fail": "Nobody wanted you today."}
                }
            
            # Convert dict to list for frontend
            jobs = []
            if isinstance(config, dict):
                for key, val in config.items():
                    if isinstance(val, dict):
                         val["id"] = key 
                         val.setdefault("name", key.title())
                         jobs.append(val)
            return jobs
        finally:
            conn.close()

    @staticmethod
    def perform_job(discord_id: str, job_id: str) -> dict:
        conn = get_db_conn()
        try:
            user = conn.execute("SELECT id, balance FROM users WHERE discord_id = ?", (discord_id,)).fetchone()
            if not user:
                raise Exception("User not found")
                
            # Fetch Config
            row = conn.execute("SELECT value FROM config WHERE key = 'activity_config'").fetchone()
            if not row: raise Exception("System config missing")
            
            config = json.loads(row["value"])
            if job_id not in config:
                raise Exception("Invalid job")
                
            job = config[job_id]
            job_name = job.get("name", job_id.title())
            
            # Cooldown check
            now = datetime.utcnow()
            cd = conn.execute(
                "SELECT expires_at FROM cooldowns WHERE user_id = ? AND activity_type = ?",
                (user["id"], job_id.lower()),
            ).fetchone()
            
            if cd and cd["expires_at"]:
                expires = datetime.fromisoformat(cd["expires_at"])
                if expires > now:
                    wait_s = int((expires - now).total_seconds())
                    raise Exception(f"Cooldown! Wait {wait_s}s")
            
            # Determine success/failure
            fail_rate = job.get("fail_rate", 0.0)
            
            # Message Processing Helper
            def format_msg(msg, **kwargs):
                for k, v in kwargs.items():
                    msg = msg.replace(f"{{{k}}}", str(v))
                return msg

            if random.random() < fail_rate:
                # Failure: apply fine
                fine_pct = job.get("fine_percent", 0.0)
                fine = int(user["balance"] * fine_pct)
                new_bal = max(user["balance"] - fine, 0)
                
                conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_bal, user["id"]))
                
                raw_msg = job.get("fail_message", f"Failed to {job_name} and paid ${fine} fine.")
                fail_msg = format_msg(raw_msg, fine=fine, balance=new_bal, name=job_name)
                
                conn.execute(
                    "INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)",
                    (user["id"], "job_fine", -fine, f"Failed: {job_name}"),
                )
                result = {
                    "success": False, "fine": fine, "new_balance": new_bal, "message": fail_msg,
                    "embed_title": f"❌ {job_name} Failed", 
                    "embed_color": job.get("embed_color", "#ef4444"),
                    "use_embed": job.get("use_embed", True)
                }
            else:
                min_r = job.get("min_reward", 10)
                max_r = job.get("max_reward", 100)
                reward = random.randint(min_r, max_r)
                new_bal = user["balance"] + reward
                
                conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_bal, user["id"]))
                
                raw_msg = job.get("success_message", f"You worked as {job_name} and earned ${reward}.")
                success_msg = format_msg(raw_msg, reward=reward, balance=new_bal, name=job_name)
                
                conn.execute(
                    "INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)",
                    (user["id"], "job_reward", reward, f"Completed: {job_name}"),
                )
                result = {
                    "success": True, "reward": reward, "new_balance": new_bal, "message": success_msg,
                    "embed_title": job.get("embed_title", f"✅ {job_name} Success"),
                    "embed_color": job.get("embed_color", "#10b981"),
                    "use_embed": job.get("use_embed", True)
                }
            
            # Set cooldown
            cooldown_sec = job.get("cooldown", 3600)
            expires = now + timedelta(seconds=cooldown_sec)
            conn.execute(
                "INSERT OR REPLACE INTO cooldowns (user_id, activity_type, expires_at) VALUES (?, ?, ?)",
                (user["id"], job_id.lower(), expires.isoformat()),
            )
            conn.commit()
            return result
        finally:
            conn.close()

    @staticmethod
    def get_leaderboard(limit: int = 10) -> list:
        conn = get_db_conn()
        try:
            rows = conn.execute(
                "SELECT discord_id, username, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,)
            ).fetchall()
            return [{"discord_id": r["discord_id"], "username": r["username"], "balance": r["balance"]} for r in rows]
        finally:
            conn.close()
