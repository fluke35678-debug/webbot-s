import json
from .db import get_db_conn
from fastapi import HTTPException

class ShopService:
    @staticmethod
    def get_items():
        conn = get_db_conn()
        items = conn.execute("SELECT * FROM shop_items WHERE is_active = 1").fetchall()
        conn.close()
        return [dict(i) for i in items]

    @staticmethod
    def create_item(item_data: dict):
        # item_data matches ShopItemCreate schema
        conn = get_db_conn()
        try:
            conn.execute("""
                INSERT INTO shop_items (name, type, price, stock, conditions, embed_config)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                item_data["name"],
                item_data["type"],
                item_data["price"],
                item_data["stock"],
                json.dumps(item_data.get("conditions", {})),
                json.dumps(item_data.get("embed_config", {}))
            ))
            conn.commit()
            return True
        finally:
            conn.close()

    @staticmethod
    def purchase_item(discord_id: str, item_id: int, quantity: int = 1):
        if quantity <= 0: raise HTTPException(400, "Quantity must be positive")
        
        conn = get_db_conn()
        try:
            # 1. Fetch Item & User
            item = conn.execute("SELECT * FROM shop_items WHERE id = ? AND is_active = 1", (item_id,)).fetchone()
            if not item: raise HTTPException(404, "Item not found")
            
            user = conn.execute("SELECT id, balance FROM users WHERE discord_id = ?", (discord_id,)).fetchone()
            if not user: raise HTTPException(404, "User not found")
            
            # 2. Check Stock
            if item["stock"] is not None and item["stock"] < quantity:
                raise HTTPException(400, "Not enough stock")
            
            total_price = item["price"] * quantity
            
            # 3. Check Balance
            if user["balance"] < total_price:
                raise HTTPException(400, "Insufficient funds")
            
            # 4. Transact
            # Deduct Balance
            conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (total_price, user["id"]))
            
            # Deduct Stock (if applicable)
            if item["stock"] is not None:
                conn.execute("UPDATE shop_items SET stock = stock - ? WHERE id = ?", (quantity, item["id"]))
            
            # Record Purchase
            conn.execute("INSERT INTO purchases (user_id, item_id, quantity, total_price) VALUES (?, ?, ?, ?)", 
                         (user["id"], item_id, quantity, total_price))
            
            # Log Transaction
            log_desc = f"Bought {quantity}x {item['name']}"
            conn.execute("INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)", 
                         (user["id"], "shop_purchase", -total_price, log_desc))
            
            conn.commit()
            return {"message": f"Successfully purchased {quantity}x {item['name']}", "new_balance": user["balance"] - total_price}
        finally:
            conn.close()
