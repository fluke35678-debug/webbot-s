import sqlite3
import json
from .db import get_db_conn
from fastapi import HTTPException

class BankService:
    @staticmethod
    def get_user(discord_id: str):
        conn = get_db_conn()
        user = conn.execute("SELECT * FROM users WHERE discord_id = ?", (discord_id,)).fetchone()
        conn.close()
        return dict(user) if user else None

    @staticmethod
    def create_user(discord_id: str, username: str = "Unknown"):
        conn = get_db_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (discord_id, username) VALUES (?, ?)", (discord_id, username))
            conn.commit()
            new_user = cursor.execute("SELECT * FROM users WHERE discord_id = ?", (discord_id,)).fetchone()
            return dict(new_user)
        except sqlite3.IntegrityError:
            return BankService.get_user(discord_id)
        finally:
            conn.close()

    @staticmethod
    def get_or_create_user(discord_id: str, username: str = "Unknown"):
        u = BankService.get_user(discord_id)
        if not u:
            u = BankService.create_user(discord_id, username)
        return u

    @staticmethod
    def deposit(discord_id: str, amount: float, description: str = "Deposit"):
        if amount <= 0: raise HTTPException(400, "Amount must be positive")
        
        conn = get_db_conn()
        try:
            user = conn.execute("SELECT id, balance FROM users WHERE discord_id = ?", (discord_id,)).fetchone()
            if not user: raise HTTPException(404, "User not found")
            
            new_bal = user["balance"] + amount
            conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_bal, user["id"]))
            conn.execute("INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)", 
                         (user["id"], "deposit", amount, description))
            conn.commit()
            return new_bal
        finally:
            conn.close()

    @staticmethod
    def withdraw(discord_id: str, amount: float, description: str = "Withdraw"):
        if amount <= 0: raise HTTPException(400, "Amount must be positive")
        
        conn = get_db_conn()
        try:
            user = conn.execute("SELECT id, balance FROM users WHERE discord_id = ?", (discord_id,)).fetchone()
            if not user: raise HTTPException(404, "User not found")
            
            if user["balance"] < amount:
                raise HTTPException(400, "Insufficient funds")
            
            new_bal = user["balance"] - amount
            conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_bal, user["id"]))
            conn.execute("INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)", 
                         (user["id"], "withdraw", amount, description))
            conn.commit()
            return new_bal
        finally:
            conn.close()

    @staticmethod
    def transfer(sender_id: str, recipient_id: str, amount: float, description: str = "Transfer"):
        if amount <= 0: raise HTTPException(400, "Amount must be positive")
        if sender_id == recipient_id: raise HTTPException(400, "Cannot transfer to self")
        
        conn = get_db_conn()
        try:
            sender = conn.execute("SELECT id, balance FROM users WHERE discord_id = ?", (sender_id,)).fetchone()
            recipient = conn.execute("SELECT id, balance FROM users WHERE discord_id = ?", (recipient_id,)).fetchone()
            
            if not sender: raise HTTPException(404, "Sender not found")
            if not recipient: raise HTTPException(404, "Recipient not found")
            
            if sender["balance"] < amount:
                raise HTTPException(400, "Insufficient funds")
                
            # Perform Transfer Transactionally
            conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, sender["id"]))
            conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, recipient["id"]))
            
            conn.execute("INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)", 
                         (sender["id"], "transfer_out", -amount, f"To {recipient_id}: {description}"))
            conn.execute("INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)", 
                         (recipient["id"], "transfer_in", amount, f"From {sender_id}: {description}"))
            
            conn.commit()
            return True
        finally:
            conn.close()
