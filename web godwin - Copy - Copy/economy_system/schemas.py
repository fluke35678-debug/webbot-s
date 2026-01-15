from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# --- User Schemas ---
class UserBase(BaseModel):
    username: Optional[str] = None
    
class UserCreate(UserBase):
    discord_id: str

class UserResponse(UserBase):
    id: int
    discord_id: str
    balance: float
    energy: int
    is_banned: bool
    created_at: str # simplistic handling for datetime string from sqlite

# --- Bank Schemas ---
class DepositRequest(BaseModel):
    amount: float
    description: Optional[str] = "Deposit"

class WithdrawRequest(BaseModel):
    amount: float
    description: Optional[str] = "Withdraw"

class TransferRequest(BaseModel):
    recipient_discord_id: str
    amount: float
    description: Optional[str] = "Transfer"

class AdminAdjustBalanceRequest(BaseModel):
    amount: float
    type: str # 'add', 'remove', 'set'
    description: Optional[str] = "Admin Adjustment"

class TransactionResponse(BaseModel):
    id: int
    user_id: int
    type: str
    amount: float
    description: Optional[str]
    created_at: str

# --- Game Schemas ---
class PlayLuckGameRequest(BaseModel):
    pass # No params needed per se, maybe user_id from auth

class GameResultResponse(BaseModel):
    win: bool
    amount_won: float
    new_balance: float
    energy_remaining: int
    message: str

# --- Shop Schemas ---
class ShopItemCreate(BaseModel):
    name: str
    type: str
    price: float
    stock: int
    conditions: Optional[dict] = {}
    embed_config: Optional[dict] = {}

class PurchaseRequest(BaseModel):
    item_id: int
    quantity: int = 1

