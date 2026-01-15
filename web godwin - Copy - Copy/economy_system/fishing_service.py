import random
import time
from .db import get_db_conn
from .inventory_service import InventoryService

class FishingService:
    # Fish: (Name, Value, Chance Weight, Icon)
    LOOT_TABLE = [
        ("Trash", 0, 30, "👢"),
        ("Seaweed", 1, 20, "🌿"),
        ("Sardine", 5, 25, "🐟"),
        ("Clownfish", 15, 10, "🐠"),
        ("Pufferfish", 50, 5, "🐡"),
        ("Shark", 200, 2, "🦈"),
        ("Golden Koi", 500, 1, "👑"),
        ("Treasure Chest", 1000, 0.5, "💎")
    ]
    
    COOLDOWN = 60 # Seconds

    @staticmethod
    def fish(user_id):
        return FishingService._perform_fishing(user_id)

    @staticmethod
    def _perform_fishing(user_id):
        # 1. Check Cooldown (using last_fished in mining_stats or new table? Let's make new table)
        conn = get_db_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fishing_stats (
                user_id TEXT PRIMARY KEY,
                last_fished TIMESTAMP DEFAULT 0,
                best_catch TEXT,
                total_caught INTEGER DEFAULT 0
            )
        """)
        
        row = conn.execute("SELECT last_fished FROM fishing_stats WHERE user_id = ?", (str(user_id),)).fetchone()
        last_fished = row[0] if row else 0
        now = time.time()
        
        if now - last_fished < FishingService.COOLDOWN:
            wait = int(FishingService.COOLDOWN - (now - last_fished))
            conn.close()
            return {"success": False, "message": f"Fish are scared! Wait {wait}s."}
            
        # 2. RNG Logic
        weights = [item[2] for item in FishingService.LOOT_TABLE]
        catch = random.choices(FishingService.LOOT_TABLE, weights=weights, k=1)[0]
        name, value, weight, icon = catch
        
        # 3. Update DB
        conn.execute("INSERT OR REPLACE INTO fishing_stats (user_id, last_fished, best_catch, total_caught) VALUES (?, ?, ?, COALESCE((SELECT total_caught FROM fishing_stats WHERE user_id=?), 0) + 1)", 
                     (str(user_id), now, name if value > 100 else (row[1] if row and len(row)>1 else None), str(user_id)))
        
        # 4. Give Reward (Money + XP? Or Item?)
        # Let's give Money directly for simplicity, or add item to inventory?
        # User requested "Inventory" in economy page earlier. Let's add to Inventory if Value > 0
        
        message = f"You caught a {icon} **{name}**!"
        
        if value > 0:
            # Add to Inventory (Assuming InventoryService exists and works)
            try:
                InventoryService.add_item(user_id, name, 1, "common" if value < 50 else "rare")
                # Also give XP or small money?
                # Let's direct sell for now to keep it simple money loop
                conn.execute("UPDATE bank_users SET balance = balance + ? WHERE discord_id = ?", (value, str(user_id)))
                message += f" Sold for ฿{value}."
            except Exception as e:
                print(f"Inventory Error: {e}")
        else:
            message += " Worth nothing."

        conn.commit()
        conn.close()
        
        return {
            "success": True, 
            "message": message, 
            "catch": {"name": name, "icon": icon, "value": value}
        }
