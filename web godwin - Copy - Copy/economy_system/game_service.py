import secrets
import json
import time
from datetime import datetime, timedelta
from .db import get_db_conn
from fastapi import HTTPException

class GameService:
    @staticmethod
    def get_config(key: str, default: dict):
        conn = get_db_conn()
        try:
            row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
            return json.loads(row["value"]) if row else default
        finally:
            conn.close()

    @staticmethod
    def set_config(key: str, value: dict):
        conn = get_db_conn()
        try:
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, json.dumps(value)))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_all_configs():
        conn = get_db_conn()
        try:
            rows = conn.execute("SELECT key, value FROM config").fetchall()
            db_configs = {row["key"]: json.loads(row["value"]) for row in rows}
            
            # Defaults
            defaults = {
                "activity_config": {
                    "work": {"min": 100, "max": 300, "cooldown": 60, "fail_rate": 0.0, "emoji": "💼", "name": "Work", "msg_win": "You worked and earned ${reward}!", "msg_fail": "You failed."},
                    "crime": {"min": 500, "max": 1500, "cooldown": 120, "fail_rate": 0.4, "fine_percent": 0.1, "emoji": "🔫", "name": "Crime", "msg_win": "You committed a crime and stole ${reward}!", "msg_fail": "You were caught and fined ${fine}!"},
                    "slut": {"min": 200, "max": 600, "cooldown": 120, "fail_rate": 0.2, "fine_percent": 0.05, "emoji": "💋", "name": "Slut", "msg_win": "You worked the corner and got ${reward}!", "msg_fail": "Nobody wanted you today."}
                },
                "game_luck_config": {"win_rate": 0.5, "reward": 100, "energy_cost": 5},
                "game_dice_config": {"multi_lowhigh": 1.9, "multi_number": 5.0}
            }
            
            # Merge: DB overrides defaults
            for key, val in defaults.items():
                if key not in db_configs:
                    db_configs[key] = val
                    
            return db_configs
        finally:
            conn.close()

    @staticmethod
    def play_luck_game(discord_id: str):
        conn = get_db_conn()
        try:
            # 1. Get Config
            config_row = conn.execute("SELECT value FROM config WHERE key = 'game_luck_config'").fetchone()
            config = json.loads(config_row["value"]) if config_row else {"win_rate": 0.5, "reward": 100, "energy_cost": 5}
            
            user = conn.execute("SELECT id, balance, energy FROM users WHERE discord_id = ?", (discord_id,)).fetchone()
            if not user: raise HTTPException(404, "User not found")
            
            if user["energy"] < config["energy_cost"]:
                raise HTTPException(400, "Not enough energy")
                
            # 2. RNG
            # secure random float 0.0 <= x < 1.0
            roll = secrets.randbelow(1000) / 1000.0
            is_win = roll < config["win_rate"]
            
            # 3. Update State
            new_energy = user["energy"] - config["energy_cost"]
            amount_won = config["reward"] if is_win else 0
            new_balance = user["balance"] + amount_won
            
            # Transaction
            conn.execute("UPDATE users SET balance = ?, energy = ? WHERE id = ?", (new_balance, new_energy, user["id"]))
            
            log_desc = f"Luck Game: {'WIN' if is_win else 'LOSE'} (Roll: {roll:.3f})"
            conn.execute("INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)", 
                         (user["id"], "game_luck", amount_won, log_desc))
            
            conn.commit()
            
            return {
                "win": is_win,
                "amount_won": amount_won,
                "new_balance": new_balance,
                "energy_remaining": new_energy,
                "message": "You won!" if is_win else "You lost!"
            }
        finally:
            conn.close()

    @staticmethod
    def play_dice(discord_id: str, bet: float, prediction: str):
        # prediction: "low" (1-3), "high" (4-6), or specific number "1"-"6"
        conn = get_db_conn()
        try:
            user = conn.execute("SELECT id, balance FROM users WHERE discord_id = ?", (discord_id,)).fetchone()
            if not user: raise HTTPException(404, "User not found")
            if user["balance"] < bet: raise HTTPException(400, "Not enough money")
            if bet <= 0: raise HTTPException(400, "Bet must be positive")

            # Config
            config = GameService.get_config('game_dice_config', {"multi_lowhigh": 1.9, "multi_number": 5.0})
            
            # Logic
            roll = secrets.randbelow(6) + 1 # 1-6
            is_win = False
            multiplier = 0
            
            if prediction in ["low", "high"]:
                is_win = (prediction == "low" and roll <= 3) or (prediction == "high" and roll >= 4)
                multiplier = config["multi_lowhigh"]
            elif prediction.isdigit() and 1 <= int(prediction) <= 6:
                is_win = roll == int(prediction)
                multiplier = config["multi_number"]
            else:
                raise HTTPException(400, "Invalid prediction")

            winnings = bet * multiplier if is_win else 0
            profit = winnings - bet # Profit can be negative
            # Actually, typically "winnings" includes the bet back. 
            # If I bet 100 and win with 2x multiplier, I get 200 total (100 profit).
            # So new balance = old - bet + winnings.
            
            # wait, if bet is deducted, then winnings is purely the payout.
            # let's assume 'bet' is deducted first.
            new_balance_after_bet = user["balance"] - bet
            new_balance = new_balance_after_bet + winnings
            
            # Update DB
            conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user["id"]))
            
            desc = f"Dice: {'WIN' if is_win else 'LOSE'} | Bet: {bet} | Rolled: {roll} | Pred: {prediction}"
            conn.execute("INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)",
                         (user["id"], "game_dice", profit, desc))
            conn.commit()
            
            return {
                "win": is_win,
                "roll": roll,
                "profit": profit,
                "new_balance": new_balance,
                "multiplier": multiplier
            }
        finally:
            conn.close()

    @staticmethod
    def perform_activity(discord_id: str, activity_type: str):
        # activity_type: "work", "crime", "rob"
        conn = get_db_conn()
        try:
            user = conn.execute("SELECT id, balance FROM users WHERE discord_id = ?", (discord_id,)).fetchone()
            if not user: raise HTTPException(404, "User not found")
            
            config = GameService.get_config('activity_config', {
                "work": {"min": 100, "max": 300, "cooldown": 60, "fail_rate": 0.0},
                "crime": {"min": 500, "max": 1500, "cooldown": 120, "fail_rate": 0.4, "fine_percent": 0.1},
                "slut": {"min": 200, "max": 600, "cooldown": 120, "fail_rate": 0.2, "fine_percent": 0.05}
            })
            
            act_conf = config.get(activity_type)
            if not act_conf: raise HTTPException(400, "Invalid activity")
            
            # Check Cooldown
            cd_row = conn.execute("SELECT expires_at FROM cooldowns WHERE user_id = ? AND activity_type = ?", 
                                  (user["id"], activity_type)).fetchone()
            if cd_row and cd_row["expires_at"]:
                expires = datetime.fromisoformat(cd_row["expires_at"])
                if datetime.now() < expires:
                    wait_sec = int((expires - datetime.now()).total_seconds())
                    raise HTTPException(400, f"Cooldown! Wait {wait_sec}s")

            # Logic
            roll = secrets.randbelow(1000) / 1000.0
            is_success = roll >= act_conf.get("fail_rate", 0)
            
            amount = 0
            message = ""
            
            if is_success:
                amount = secrets.randbelow(act_conf["max"] - act_conf["min"] + 1) + act_conf["min"]
                message = f"You performed {activity_type} and earned ${amount}!"
            else:
                fine = int(user["balance"] * act_conf.get("fine_percent", 0))
                amount = -fine
                message = f"You failed at {activity_type} and paid a fine of ${fine}!"

            # Update DB
            new_balance = user["balance"] + amount
            conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user["id"]))
            
            # Set Cooldown
            new_expires = datetime.now() + timedelta(seconds=act_conf["cooldown"])
            conn.execute("INSERT OR REPLACE INTO cooldowns (user_id, activity_type, expires_at) VALUES (?, ?, ?)",
                         (user["id"], activity_type, new_expires.isoformat()))
            
            conn.execute("INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)",
                         (user["id"], f"activity_{activity_type}", amount, message))
            conn.commit()
            
            return {
                "success": is_success,
                "amount": amount,
                "new_balance": new_balance,
                "message": message,
                "cooldown_until": new_expires.isoformat()
            }
        finally:
            conn.close()

    @staticmethod
    def get_pet(discord_id: str):
        conn = get_db_conn()
        user = conn.execute("SELECT id FROM users WHERE discord_id = ?", (discord_id,)).fetchone()
        if not user: return None
        
        pet = conn.execute("SELECT * FROM pets WHERE user_id = ? AND is_alive = 1", (user["id"],)).fetchone()
        conn.close()
        return dict(pet) if pet else None
    
    @staticmethod
    def adopt_pet(discord_id: str, pet_name: str, species: str = "Cat"):
        conn = get_db_conn()
        try:
            user = conn.execute("SELECT id, balance FROM users WHERE discord_id = ?", (discord_id,)).fetchone()
            if not user: raise HTTPException(404, "User not found")
            
            # Check existing pet
            existing = conn.execute("SELECT 1 FROM pets WHERE user_id = ? AND is_alive = 1", (user["id"],)).fetchone()
            if existing: raise HTTPException(400, "You already have a pet")
            
            cost = 1000 # Configurable
            if user["balance"] < cost: raise HTTPException(400, f"Not enough money (Cost: {cost})")
            
            # Purchase
            conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (cost, user["id"]))
            conn.execute("INSERT INTO pets (user_id, species, name) VALUES (?, ?, ?)", (user["id"], species, pet_name))
            conn.execute("INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)", 
                         (user["id"], "pet_adoption", -cost, f"Adopted {species}: {pet_name}"))
            
            conn.commit()
            return True
        finally:
            conn.close()

    @staticmethod
    def pet_interact(discord_id: str, action: str):
        conn = get_db_conn()
        try:
            user = conn.execute("SELECT id, balance FROM users WHERE discord_id = ?", (discord_id,)).fetchone()
            if not user: raise HTTPException(404, "User not found")
            pet = conn.execute("SELECT * FROM pets WHERE user_id = ? AND is_alive = 1", (user["id"],)).fetchone()
            
            if not pet: return {"success": False, "message": "No active pet"}
            
            if action == "FEED":
                cost = 50
                if user["balance"] < cost: return {"success": False, "message": "Not enough money ($50)"}
                
                new_hunger = min(100, (pet["hunger"] or 0) + 20)
                conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (cost, user["id"]))
                conn.execute("UPDATE pets SET hunger = ? WHERE id = ?", (new_hunger, pet["id"]))
                conn.commit()
                return {"success": True, "message": f"Fed pet! Hunger: {new_hunger}%"}
                
            elif action == "PLAY":
                # Play might cost energy or be free but cooldown?
                # Let's make it free but restores happiness
                new_happy = min(100, (pet["happiness"] or 0) + 15)
                # Maybe decrease hunger slightly?
                new_hunger = max(0, (pet["hunger"] or 0) - 5)
                
                conn.execute("UPDATE pets SET happiness = ?, hunger = ? WHERE id = ?", (new_happy, new_hunger, pet["id"]))
                conn.commit()
                return {"success": True, "message": f"Played with pet! Happiness: {new_happy}%"}
                
            return {"success": False, "message": "Invalid action"}
        finally:
            conn.close()
