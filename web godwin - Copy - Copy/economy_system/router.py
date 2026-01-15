from fastapi import APIRouter, HTTPException, Depends
from .schemas import *
from .bank_service import BankService
from .game_service import GameService
from .shop_service import ShopService
from .economy_service import EconomyService

router = APIRouter(prefix="/api/eco", tags=["Economy"])

# --- User & Bank ---
@router.post("/users/{discord_id}/init")
async def init_user(discord_id: str, user_data: UserCreate):
    return BankService.get_or_create_user(discord_id, user_data.username)

@router.get("/users/{discord_id}")
async def get_user(discord_id: str):
    user = BankService.get_user(discord_id)
    if not user: raise HTTPException(404, "User not found")
    return user

@router.post("/users/{discord_id}/deposit")
async def deposit(discord_id: str, req: DepositRequest):
    new_bal = BankService.deposit(discord_id, req.amount, req.description)
    return {"status": "success", "new_balance": new_bal}

@router.post("/users/{discord_id}/withdraw")
async def withdraw(discord_id: str, req: WithdrawRequest):
    new_bal = BankService.withdraw(discord_id, req.amount, req.description)
    return {"status": "success", "new_balance": new_bal}

@router.post("/users/{discord_id}/transfer")
async def transfer(discord_id: str, req: TransferRequest):
    BankService.transfer(discord_id, req.recipient_discord_id, req.amount, req.description)
    return {"status": "success", "message": "Transfer complete"}

# --- Games ---
@router.post("/games/luck/play")
async def play_luck_game(discord_id: str):
    # In real app, discord_id should come from Auth token
    return GameService.play_luck_game(discord_id)

@router.get("/pets/{discord_id}")
async def get_pet(discord_id: str):
    pet = GameService.get_pet(discord_id)
    if not pet: raise HTTPException(404, "No pet found")
    return pet

@router.post("/pets/{discord_id}/adopt")
async def adopt_pet(discord_id: str, name: str, species: str = "Cat"):
    GameService.adopt_pet(discord_id, name, species)
    return {"status": "success", "message": f"Adopted {name}"}

@router.post("/pets/{discord_id}/feed")
async def feed_pet(discord_id: str):
    return GameService.feed_pet(discord_id)

@router.post("/games/dice/play")
async def play_dice(discord_id: str, bet: float, prediction: str):
    return GameService.play_dice(discord_id, bet, prediction)

@router.post("/activities/{activity_type}")
async def perform_activity(discord_id: str, activity_type: str):
    return GameService.perform_activity(discord_id, activity_type)

@router.get("/config")
async def get_all_configs():
    return GameService.get_all_configs()

@router.post("/config")
async def update_config(payload: dict):
    # payload: { "key": "game_luck_config", "value": {...} }
    key = payload.get("key")
    value = payload.get("value")
    if not key or value is None:
        raise HTTPException(400, "Missing key/value")
    GameService.set_config(key, value)
    return {"status": "success"}

# --- Shop ---
@router.get("/shop/items")
async def get_shop_items():
    return ShopService.get_items()

@router.post("/shop/items")
async def create_shop_item(item: ShopItemCreate):
    ShopService.create_item(item.dict())
    return {"status": "success", "message": "Item created"}

@router.post("/shop/purchase")
async def purchase_item(discord_id: str, req: PurchaseRequest):
    return ShopService.purchase_item(discord_id, req.item_id, req.quantity)

# --- Economy (UnbelievaBoat Style) ---
@router.get("/balance/{discord_id}")
async def get_balance(discord_id: str):
    return {"balance": EconomyService.get_balance(discord_id)}

@router.post("/daily/{discord_id}")
async def claim_daily(discord_id: str):
    reward = EconomyService.claim_daily(discord_id)
    return {"status": "success", "reward": reward}

@router.get("/jobs")
async def list_jobs():
    return EconomyService.get_jobs()

@router.post("/jobs/{discord_id}/{job_name}")
async def perform_job(discord_id: str, job_name: str):
    result = EconomyService.perform_job(discord_id, job_name)
    return result


# --- Admin Shop ---
from .shared import embed_queue
import json

@router.post("/admin/shop/embed")
async def send_shop_embed(payload: dict):
    # payload: { channel_id, title, description, color, image_url, ... }
    channel_id = payload.get("channel_id")
    color_hex = payload.get("color", "#6366f1")
    try:
        color_int = int(color_hex.replace("#", ""), 16)
    except:
        color_int = 0x6366f1
        
    cmd = {
        "action": "SEND_EMBED",
        "channel_id": str(channel_id),
        "payload": {
            "title": payload.get("title", "Shop Item"),
            "description": payload.get("description", ""),
            "color": color_int,
            "image": payload.get("image_url"),
            "footer": "Shop System • Powered by Control Center"
        }
    }
    embed_queue.append(cmd)
    return {"status": "queued"}

@router.post("/admin/shop/items")
async def create_shop_item(data: dict):
    # Logic extracted from main_dashboard.py
    item_type = data.get("type", "Role")
    name = data.get("name")
    price = float(data.get("price", 0))
    stock = int(data.get("stock", -1))
    
    conditions = {}
    if item_type == "Role":
        role_id = data.get("value")
        if role_id: conditions["role_id"] = role_id
            
    elif item_type == "Ticket":
        ticket_amount = int(data.get("value", 1))
        conditions["ticket_amount"] = ticket_amount
        
    embed_config = { "image": data.get("image_url") }
    
    item_payload = {
        "name": name,
        "type": item_type,
        "price": price,
        "stock": stock if stock >= 0 else 999999,
        "conditions": conditions,
        "embed_config": embed_config
    }
    
    ShopService.create_item(item_payload)
    return {"status": "success", "message": f"Created {item_type}: {name}"}
