import sqlite3
import json

DB_PATH = "economy.db"

class InventoryService:
    @staticmethod
    def get_conn():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def add_item(user_id, item_id, quantity=1):
        conn = InventoryService.get_conn()
        try:
            # Check if exists
            exists = conn.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id)).fetchone()
            if exists:
                conn.execute("UPDATE inventory SET quantity = quantity + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND item_id = ?", (quantity, user_id, item_id))
            else:
                conn.execute("INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, ?)", (user_id, item_id, quantity))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding item: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def remove_item(user_id, item_id, quantity=1):
        conn = InventoryService.get_conn()
        try:
            row = conn.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id)).fetchone()
            if not row or row['quantity'] < quantity:
                return False
            
            new_qty = row['quantity'] - quantity
            if new_qty > 0:
                conn.execute("UPDATE inventory SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND item_id = ?", (new_qty, user_id, item_id))
            else:
                conn.execute("DELETE FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id))
                
            conn.commit()
            return True
        except Exception as e:
            print(f"Error removing item: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def get_user_inventory(user_id):
        conn = InventoryService.get_conn()
        # Join with shop_items to get item details
        query = '''
            SELECT i.item_id, i.quantity, s.name, s.type, s.price, s.embed_config
            FROM inventory i
            JOIN shop_items s ON i.item_id = s.id
            WHERE i.user_id = ?
        '''
        rows = conn.execute(query, (user_id,)).fetchall()
        conn.close()
        
        inventory = []
        for row in rows:
            item = dict(row)
            # Parse embed config if useful for image
            try:
                if item['embed_config']:
                    config = json.loads(item['embed_config'])
                    item['image'] = config.get('thumbnail') or config.get('image')
            except:
                pass
            inventory.append(item)
            
        return inventory
