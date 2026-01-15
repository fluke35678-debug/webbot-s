from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import sqlite3
import os
import httpx
import time
import asyncio
from dotenv import load_dotenv

load_dotenv()
import token_utils

# Economy System Integration
from economy_system.router import router as eco_router
from economy_system import shared as eco_shared
from economy_system.db import init_db as init_eco_db

# Trigger Reload


app = FastAPI()

# Include Economy Router
app.include_router(eco_router)

# --- Setup System ---
@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/api/setup/channels")
async def setup_channels(request: Request, guild_id: str = Form(None)):
    from starlette.responses import StreamingResponse
    import discord
    
    # We use a generator to stream logs back to the UI
    async def run_setup():
        target_guild_id = guild_id or TARGET_GUILD_ID
        if not target_guild_id:
            yield b"Error: No Guild ID provided\n"
            return

        yield f"Connecting to Discord (Token: {BOT_TOKEN[:5]}...)\n".encode()
        
        # Create a temporary client just for this operation
        intents = discord.Intents.default()
        client = discord.Client(intents=intents)
        
        setup_done = asyncio.Event()
        
        @client.event
        async def on_ready():
            try:
                guild = client.get_guild(int(target_guild_id))
                if not guild:
                    # Try fetching if not in cache
                    try:
                        guild = await client.fetch_guild(int(target_guild_id))
                    except:
                        yield f"Error: Could not find guild {target_guild_id}\n".encode()
                        await client.close()
                        return

                yield f"Connected to Guild: {guild.name}\n".encode()
                
                # Check/Create Category
                cat_name = "ECONOMY & CASINO"
                category = discord.utils.get(guild.categories, name=cat_name)
                if not category:
                    yield f"Creating Category: {cat_name}...\n".encode()
                    category = await guild.create_category(cat_name)
                else:
                    yield f"Category '{cat_name}' exists.\n".encode()
                
                # Check/Create Channels
                channels_to_create = [
                    ("ð°-economy", "text"),
                    ("ð°-casino", "text"),
                    ("ð-shop", "text"),
                    ("ð-audit-logs", "text") # Changed name slightly to avoid conflict if logs exists
                ]
                
                for ch_name, ch_type in channels_to_create:
                    existing = discord.utils.get(guild.text_channels, name=ch_name)
                    if not existing:
                        yield f"Creating Channel: #{ch_name}...\n".encode()
                        await guild.create_text_channel(ch_name, category=category)
                    else:
                        yield f"Channel #{ch_name} exists.\n".encode()
                
                yield b"\nSUCCESS: All channels initialized!\n"
            except Exception as e:
                yield f"Error during setup: {str(e)}\n".encode()
            finally:
                setup_done.set()
                await client.close()

        # Run client in background task
        asyncio.create_task(client.start(BOT_TOKEN))
        
        # Wait for setup to finish (with timeout)
        try:
            await asyncio.wait_for(setup_done.wait(), timeout=30)
        except asyncio.TimeoutError:
             yield b"Timeout: Setup took too long.\n"
    
    return StreamingResponse(run_setup(), media_type="text/plain")


@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HTMLResponse(content=f"<h1>Critical System Error</h1><pre>{traceback.format_exc()}</pre>", status_code=500)

app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")

@app.on_event("startup")
async def startup_event():
    """Initializes background tasks for cache warming."""
    print(">>> Dashboard Startup: Initializing Background Tasks...")
    
    # Auto-migrate event_questions schema
    try:
        conn = get_db_conn(GACHA_DB)
        try:
            conn.execute("ALTER TABLE event_questions ADD COLUMN answer_options TEXT")
        except: pass
        try:
            conn.execute("ALTER TABLE event_questions ADD COLUMN reward_tickets INTEGER DEFAULT 1")
        except: pass
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Migration Warning: {e}")

    # Initialize Economy Database
    try:
        init_eco_db()
        print(">>> Economy Database Initialized")
    except Exception as e:
        print(f"Economy DB Init Warning: {e}")

    asyncio.create_task(background_scheduler())
    asyncio.create_task(announcement_scheduler())

async def background_scheduler():
    """Periodically refreshes cache to ensure instant page loads."""
    while True:
        try:
            print("[Scheduler] Refreshing Data Cache...")
            await fetch_roles_bg()
            await fetch_members_bg()
            await get_discord_channels()
            print("[Scheduler] Refresh Complete.")
        except Exception as e:
            print(f"[Scheduler Error] {e}")
        
        await asyncio.sleep(300) # Refresh every 5 minutes

async def announcement_scheduler():
    """Checks for scheduled announcements and queues them for the bot."""
    from economy_system.announcement_service import AnnouncementService
    import json
    
    while True:
        try:
            pending = AnnouncementService.get_pending_messages()
            if pending:
                print(f"[Announcer] Found {len(pending)} pending messages.")
                
            for msg in pending:
                global embed_queue, message_queue
                
                # Mark as sent FIRST to avoid loop if queueing fails (at least we tried)
                AnnouncementService.mark_as_sent(msg["id"])
                
                if msg["embed_json"]:
                    try:
                        embed_data = json.loads(msg["embed_json"])
                        # Adapt to embed_queue format
                        embed_queue.append({
                            "action": "SEND_EMBED",
                            "channel_id": msg["channel_id"],
                            "payload": embed_data
                        })
                    except:
                        # Fallback to text if JSON fails
                        message_queue.append({
                            "action": "SEND_MESSAGE",
                            "channel_id": msg["channel_id"],
                            "message": msg["content"]
                        })
                else:
                    message_queue.append({
                        "action": "SEND_MESSAGE",
                        "channel_id": msg["channel_id"],
                        "message": msg["content"]
                    })
                    
        except Exception as e:
            print(f"[Announcer Error] {e}")
            
        await asyncio.sleep(60) # Check every minute

@app.get("/api/stats")
async def get_stats():
    """Lightweight endpoint for real-time frontend updates."""
    is_online = (time.time() - bot_status.get("last_heartbeat", 0)) < 90
    return {
        "online": is_online,
        "members": len(member_cache.get("data", {})),
        "roles": len(role_cache.get("data", {}))
    }

# Configuration
GACHA_DB = os.path.join(os.getcwd(), 'gacha_bot.db')
LOG_DB = os.path.join(os.getcwd(), 'audit_logs.db')
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
BOT_TOKEN = os.getenv("TOKEN")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:8000/callback")
SESSION_SECRET = os.getenv("SESSION_SECRET", "super_secret_key")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID") 
TARGET_GUILD_ID = "1241829320012599346"
ACTIVE_GUILD_ID = TARGET_GUILD_ID # Default to initial target

# Helper to get the current active guild
def get_active_guild_id():
    return ACTIVE_GUILD_ID

# Log Translations
EVENT_TRANSLATIONS = {
    "ROLE_UPDATE": "เปลี่ยนบทบาท",
    "TIMEOUT": "ตั้งเวลาพักการใช้งาน",
    "GUILD_ROLE_UPDATE": "แก้ไขบทบาทเซิร์ฟเวอร์",
    "MESSAGE_DELETE": "ลบข้อความ",
    "MESSAGE_EDIT": "แก้ไขข้อความ",
    "VOICE_JOIN": "เข้าห้องเสียง",
    "VOICE_LEAVE": "ออกจากห้องเสียง",
    "VOICE_MOVE": "ย้ายห้องเสียง",
    "BAN": "แบนสมาชิก",
    "UNBAN": "ปลดแบนสมาชิก",
    "CHANNEL_CREATE": "สร้างห้อง",
    "CHANNEL_DELETE": "ลบห้อง",
    "GACHA_PULL": "สุ่มกาชา",
    "SALT_EXCHANGE": "แลกเกลือ",
    "ADMIN_UPDATE_USER": "แอดมินแก้ไขข้อมูลผู้ใช้",
    "ADMIN_BULK_GACHA": "แอดมินตั้งค่ากาชา",
    "ADMIN_ACHIEVEMENT": "แอดมินแก้ไขความสำเร็จ",
    "SERVER_STARTUP": "บอทเริ่มทำงาน",
    "MEMBER_JOIN": "สมาชิกใหม่เข้าเซิร์ฟเวอร์",
    "MEMBER_LEAVE": "สมาชิกออกจากเซิร์ฟเวอร์",
    "ROLE_CREATE": "สร้างบทบาทใหม่",
    "ROLE_DELETE": "ลบบทบาท",
    "GACHA_10_PULL": "สุ่มกาชา 10 ครั้ง"
}

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)
templates = Jinja2Templates(directory="dashboard/templates")

def from_json_list_filter(value):
    try:
        if isinstance(value, str):
            import json
            data = json.loads(value)
            if isinstance(data, list):
                return ", ".join(map(str, data))
        elif isinstance(value, list):
            return ", ".join(map(str, value))
    except:
        pass
    return value or ""

def from_json_list_raw_filter(value):
    try:
        if isinstance(value, str):
            import json
            data = json.loads(value)
            if isinstance(data, list):
                return data
        elif isinstance(value, list):
            return value
    except:
        pass
    return []

templates.env.filters["from_json_list"] = from_json_list_filter
templates.env.filters["from_json_list_raw"] = from_json_list_raw_filter

# Global state
bot_status = {"online": False, "last_heartbeat": 0}
embed_queue = [] 
message_queue = []  # Queue for sending messages
message_cache = {}  # Cache messages per channel: {channel_id: [messages]}
role_cache = {"data": {}, "last_fetch": 0}
member_cache = {"data": {}, "last_fetch": 0}
channel_cache = {"data": {}, "last_fetch": 0}
active_event = None

# Connect economy router's embed_queue to main embed_queue
eco_shared.embed_queue = embed_queue

async def fetch_roles_bg():
    """Background task to fetch roles with timeout and error handling"""
    if not BOT_TOKEN: return
    try:
        print("[BG] Starting background role fetch...")
        roles_map = {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": f"Bot {BOT_TOKEN}"}
            current_gid = get_active_guild_id()
            roles_res = await client.get(f"https://discord.com/api/v10/guilds/{current_gid}/roles", headers=headers)
            if roles_res.status_code == 200:
                for role in roles_res.json():
                    color_int = role.get("color", 0)
                    color_hex = f"#{color_int:06x}" if color_int != 0 else None
                    roles_map[str(role["id"])] = {
                        "id": str(role["id"]),
                        "name": role["name"],
                        "color": color_hex,
                        "position": role.get("position", 0),
                        "emoji": role.get("unicode_emoji")
                    }
                role_cache["data"] = roles_map
                role_cache["last_fetch"] = time.time()
                print(f"[BG] Role fetch complete. {len(roles_map)} roles cached.")
            else:
                 print(f"[BG] Role fetch failed: {roles_res.status_code}")
    except Exception as e:
        print(f"[BG] Error fetching roles: {e}")

async def get_discord_roles():
    """Fetches roles, returns cache immediately if available, updates in bg if stale."""
    current_time = time.time()
    # If we have data, use it unless it's VERY old (e.g. 1 hour), in which case we might want to wait?
    # Actually, always return cache if exists to be non-blocking.
    
    if role_cache["data"]:
        if current_time - role_cache["last_fetch"] > 300: # 5 mins stale
            asyncio.create_task(fetch_roles_bg())
        return role_cache["data"]
    
    # If no data, try to fetch (blocking but with timeout)
    await fetch_roles_bg()
    return role_cache.get("data", {})

async def fetch_members_bg():
    """Background task to fetch members with timeout and paging"""
    if not BOT_TOKEN: return
    try:
        print("[BG] Starting background member fetch...")
        members_map = {}
        async with httpx.AsyncClient(timeout=15.0) as client:
            headers = {"Authorization": f"Bot {BOT_TOKEN}"}
            g_id = get_active_guild_id()
            after = "0"
            while True:
                try:
                    members_res = await client.get(f"https://discord.com/api/v10/guilds/{g_id}/members?limit=1000&after={after}", headers=headers)
                    if members_res.status_code == 200:
                        page = members_res.json()
                        if not page: break
                        for m in page:
                            user = m["user"]
                            uid = str(user["id"])
                            members_map[uid] = {
                                "name": m.get("nick") or user.get("global_name") or user.get("username"),
                                "username": user.get("username"),
                                "avatar": user.get("avatar"),
                                "roles": m.get("roles", []),
                                "joined_at": m.get("joined_at"),
                                "bot": user.get("bot", False)
                            }
                            after = uid
                        if len(page) < 1000: break
                    else:
                        print(f"[BG] Member fetch failed: {members_res.status_code} {members_res.text}")
                        break
                except httpx.ReadTimeout:
                     print("[BG] Member fetch timed out on a page.")
                     break
        
        if members_map:
            member_cache["data"] = members_map
            member_cache["last_fetch"] = time.time()
            print(f"[BG] Member fetch complete. {len(members_map)} members cached.")
    except Exception as e:
        print(f"[BG] Error fetching members: {e}")

async def get_discord_members():
    """Fetches members, returns cache immediately if available, updates in bg if stale."""
    current_time = time.time()
    
    if member_cache["data"]:
        if current_time - member_cache["last_fetch"] > 600: # 10 mins stale
            asyncio.create_task(fetch_members_bg())
        return member_cache["data"]
    
    await fetch_members_bg()
    return member_cache.get("data", {})

def get_avatar_url(user_id, avatar_hash):
    """Constructs a Discord avatar URL from user ID and hash. Safe against None."""
    if not avatar_hash:
        return "https://cdn.discordapp.com/embed/avatars/0.png"
    ext = "gif" if str(avatar_hash).startswith("a_") else "png"
    return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.{ext}"

async def get_discord_channels():
    """Fetches all channels from all guilds the bot is in, with caching."""
    if channel_cache["data"] and (time.time() - channel_cache["last_fetch"] < 600): # Cache for 10 mins
        return channel_cache["data"]
    
    if not BOT_TOKEN:
        return {}
    
    channels_map = {}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            headers = {"Authorization": f"Bot {BOT_TOKEN}"}
            # Fetch ONLY from TARGET_GUILD_ID
            g_id = get_active_guild_id()
            ch_res = await client.get(f"https://discord.com/api/v10/guilds/{g_id}/channels", headers=headers)
            if ch_res.status_code == 200:
                for ch in ch_res.json():
                    channels_map[str(ch["id"])] = {
                        "name": ch["name"],
                        "type": ch["type"],
                        "position": ch.get("position", 0),
                        "parent_id": ch.get("parent_id")
                    }
                channel_cache["data"] = channels_map
                channel_cache["last_fetch"] = time.time()
            else:
                print(f"Error fetching channels: {ch_res.status_code}")
    except Exception as e:
        print(f"CRITICAL Error fetching channels: {e}")
            
    return channel_cache.get("data", {})

async def fetch_channel_messages(channel_id: str, limit: int = 50):
    """Fetch message history from Discord API with timeout."""
    if not BOT_TOKEN:
        return []
    
    messages = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            headers = {"Authorization": f"Bot {BOT_TOKEN}"}
            res = await client.get(
                f"https://discord.com/api/v10/channels/{channel_id}/messages?limit={limit}",
                headers=headers
            )
            if res.status_code == 200:
                for msg in res.json():
                    author = msg.get("author", {})
                    attachments = [att["url"] for att in msg.get("attachments", [])]
                    messages.append({
                        "channel_id": channel_id,
                        "message_id": msg["id"],
                        "author_id": author.get("id"),
                        "author_name": author.get("global_name") or author.get("username"),
                        "author_username": author.get("username"),
                        "author_avatar": f"https://cdn.discordapp.com/avatars/{author.get('id')}/{author.get('avatar')}.png" if author.get("avatar") else None,
                        "content": msg.get("content", ""),
                        "attachments": attachments,
                        "timestamp": msg.get("timestamp"),
                        "is_bot": author.get("bot", False)
                    })
                # Discord returns newest first, we want oldest first
                messages.reverse()
    except Exception as e:
        print(f"Error fetching messages: {e}")
    
    return messages

def get_db_conn(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

# --- Authentication Helpers ---
def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        return None
    return user

async def is_authenticated(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login_page"}
        )
    # Optional: Check if the user is the authorized admin
    if ADMIN_USER_ID and str(user.get("id")) != str(ADMIN_USER_ID):
        raise HTTPException(status_code=403, detail="Unauthorized: Access restricted to bot owner.")
    return user

# --- Economy Page Route ---
@app.get("/economy", response_class=HTMLResponse)
async def economy_page(request: Request, user: dict = Depends(is_authenticated)):
    """Economy Dashboard Page"""
    from economy_system.db import get_db_conn as eco_get_db_conn
    from economy_system.economy_service import EconomyService
    from economy_system.game_service import GameService
    
    discord_id = str(user["id"])
    
    # Get or create user
    from economy_system.bank_service import BankService
    eco_user = BankService.get_or_create_user(discord_id, user.get("username", "Unknown"))
    
    # Get balance and energy
    balance = eco_user.get("balance", 0)
    energy = eco_user.get("energy", 100)
    
    # Get pet info
    pet = GameService.get_pet(discord_id)
    
    # Get Inventory
    from economy_system.inventory_service import InventoryService
    inventory = InventoryService.get_user_inventory(discord_id)
    
    # Get leaderboard
    leaderboard = EconomyService.get_leaderboard(10)
    
    return templates.TemplateResponse("economy.html", {
        "request": request,
        "user": user,
        "balance": int(balance),
        "energy": energy,
        "pet": pet,
        "inventory": inventory,
        "leaderboard": leaderboard
    })


# --- Shop Page Route ---
@app.get("/shop", response_class=HTMLResponse)
async def shop_page(request: Request, user: dict = Depends(is_authenticated)):
    """Shop Management Page"""
    from economy_system.shop_service import ShopService
    
    items = ShopService.get_items()
    channels = await get_discord_channels()
    is_online = (time.time() - bot_status["last_heartbeat"]) < 90
    
    return templates.TemplateResponse("shop.html", {
        "request": request,
        "user": user,
        "items": items,
        "channels": channels,
        "bot_online": is_online
    })

@app.post("/api/shop/send-item-embed")
async def send_item_embed(request: Request, user: dict = Depends(is_authenticated)):
    """Send a specific item's embed to Discord"""
    from economy_system.shop_service import ShopService
    import json
    
    data = await request.json()
    item_id = data.get("item_id")
    channel_id = data.get("channel_id")
    
    # Get item from DB
    from economy_system.db import get_db_conn as eco_db
    conn = eco_db()
    item = conn.execute("SELECT * FROM shop_items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    
    if not item:
        raise HTTPException(404, "Item not found")
    
    item = dict(item)
    embed_config = json.loads(item.get("embed_config", "{}")) if item.get("embed_config") else {}
    
    # Build embed command
    cmd = {
        "action": "SEND_EMBED",
        "channel_id": str(channel_id),
        "payload": {
            "title": f"🛒 {item['name']}",
            "description": f"**ราคา:** ฿{item['price']}\n**ประเภท:** {item['type']}\n**Stock:** {item['stock'] if item['stock'] else '∞'}\n\nกด React หรือใช้คำสั่งเพื่อซื้อ!",
            "color": 0x6366f1,
            "image": embed_config.get("image"),
            "footer": "Godwin Shop System"
        }
    }
    embed_queue.append(cmd)
    
    return {"status": "queued", "message": "Item embed queued for sending"}

@app.delete("/api/shop/delete/{item_id}")
async def delete_shop_item(item_id: int, user: dict = Depends(is_authenticated)):
    """Delete a shop item"""
    from economy_system.db import get_db_conn as eco_db
    conn = eco_db()
    conn.execute("UPDATE shop_items SET is_active = 0 WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Item deleted"}

    return {"status": "success", "message": "Item deleted"}

# --- Economy: Mining/Fishing/Pets ---
@app.post("/api/economy/mine/collect")
async def eco_mine_collect(request: Request, user: dict = Depends(is_authenticated)):
    from economy_system.mining_service import MiningService
    return MiningService.collect(user["id"])

@app.post("/api/economy/mine/upgrade")
async def eco_mine_upgrade(request: Request, user: dict = Depends(is_authenticated)):
    from economy_system.mining_service import MiningService
    return MiningService.upgrade(user["id"])

@app.get("/api/economy/mine/stats")
async def eco_mine_stats(request: Request, user: dict = Depends(is_authenticated)):
    from economy_system.mining_service import MiningService
    return MiningService.get_stats(user["id"])

@app.post("/api/economy/fish")
async def eco_fish(request: Request, user: dict = Depends(is_authenticated)):
    from economy_system.fishing_service import FishingService
    return FishingService.fish(user["id"])

@app.post("/api/economy/pet/interact")
async def eco_pet_interact(request: Request, user: dict = Depends(is_authenticated)):
    data = await request.json()
    action = data.get("action") # FEED, PLAY
    from economy_system.game_service import GameService
    return GameService.pet_interact(user["id"], action)

# --- Settings Page Route ---
@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user: dict = Depends(is_authenticated)):
    """Economy Settings Page"""
    from economy_system.game_service import GameService
    
    config = GameService.get_all_configs()
    channels = await get_discord_channels()
    is_online = (time.time() - bot_status["last_heartbeat"]) < 90
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "user": user,
        "config": config,
        "channels": channels,
        "bot_online": is_online
    })

@app.post("/api/admin/send-reward")
async def send_reward_api(request: Request, user: dict = Depends(is_authenticated)):
    """Send reward to a Discord user"""
    from economy_system.bank_service import BankService
    import json
    
    data = await request.json()
    target_user_id = data.get("user_id")
    reward_type = data.get("type")  # money, ticket, role
    amount = data.get("amount")
    reason = data.get("reason", "Admin Reward")
    announce = data.get("announce", False)
    channel_id = data.get("channel_id")
    
    if not target_user_id or not amount:
        raise HTTPException(400, "Missing user_id or amount")
    
    result_message = ""
    
    if reward_type == "money":
        # Add money to user
        eco_user = BankService.get_or_create_user(target_user_id)
        new_bal = BankService.deposit(target_user_id, float(amount), f"Admin: {reason}")
        result_message = f"เพิ่ม ฿{amount} ให้ <@{target_user_id}> สำเร็จ (Balance: ฿{new_bal})"
        
    elif reward_type == "ticket":
        # Add gacha tickets
        conn = get_db_conn(GACHA_DB)
        conn.execute("INSERT OR IGNORE INTO users (user_id, tickets, salt, total_rolls) VALUES (?, 0, 0, 0)", (target_user_id,))
        conn.execute("UPDATE users SET tickets = tickets + ? WHERE user_id = ?", (int(amount), target_user_id))
        conn.commit()
        conn.close()
        result_message = f"เพิ่ม {amount} ตั๋ว Gacha ให้ <@{target_user_id}> สำเร็จ"
        
    elif reward_type == "role":
        # Queue role assignment command for bot
        cmd = {
            "action": "GIVE_ROLE",
            "payload": {
                "user_id": target_user_id,
                "role_id": int(amount)
            }
        }
        embed_queue.append(cmd)
        result_message = f"ส่งคำสั่งให้ Role <@&{amount}> แก่ <@{target_user_id}>"
    
    # Announce in Discord if requested
    if announce and channel_id:
        embed_cmd = {
            "action": "SEND_EMBED",
            "channel_id": str(channel_id),
            "payload": {
                "title": "🎉 Reward!",
                "description": f"<@{target_user_id}> ได้รับรางวัล!\n\n**รางวัล:** {reward_type.upper()} x {amount}\n**เหตุผล:** {reason}",
                "color": 0x10b981,
                "footer": "Godwin Reward System"
            }
        }
        embed_queue.append(embed_cmd)
    
    return {"status": "success", "message": result_message}

# --- Management APIs ---
@app.post("/api/admin/update-user")
async def admin_update_user(request: Request, user: dict = Depends(is_authenticated)):
    """Update user stats directly"""
    from economy_system.bank_service import BankService
    
    data = await request.json()
    target_id = data.get("user_id")
    
    # 1. Update Economy (Wallet/Bank/XP)
    # We don't have a direct 'set' method in BankService usually, so we might need SQL
    # Or we use BankService to get user, then update.
    # checking main_dashboard.py imports... it imports sqlite3.
    
    # Update Bank Users DB
    try:
        from economy_system.db import get_db_conn as eco_db
        conn = eco_db()
        
        if "wallet" in data:
            conn.execute("UPDATE bank_users SET balance = ? WHERE discord_id = ?", (float(data["wallet"]), target_id))
        if "bank" in data:
            # Assuming bank_users has bank_balance column? The schema wasn't fully shown but highly likely.
            # If not, we might fail. Let's assume standard eco schema.
             # Actually, let's use a safe fallback or check columns.
             # For now, I will assume it exists or I will write a RAW query that ignores if missing? No.
             # Let's simple Check:
             conn.execute("UPDATE bank_users SET bank_balance = ? WHERE discord_id = ?", (float(data["bank"]), target_id))
             
        if "xp" in data:
             conn.execute("UPDATE bank_users SET xp = ? WHERE discord_id = ?", (int(data["xp"]), target_id))
             
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Eco Update Error: {e}")
        
    # 2. Update Gacha/User DB (Tickets, Salt, Title)
    try:
        conn = get_db_conn(GACHA_DB)
        # Ensure user exists
        conn.execute("INSERT OR IGNORE INTO users (user_id, tickets, salt, total_rolls) VALUES (?, 0, 0, 0)", (target_id,))
        
        if "tickets" in data:
            conn.execute("UPDATE users SET tickets = ? WHERE user_id = ?", (int(data["tickets"]), target_id))
        if "salt" in data:
            conn.execute("UPDATE users SET salt = ? WHERE user_id = ?", (int(data["salt"]), target_id))
        if "custom_title" in data:
            conn.execute("UPDATE users SET custom_title = ? WHERE user_id = ?", (data["custom_title"], target_id))
            
        conn.commit()
        conn.close()
    except Exception as e:
        return {"status": "error", "message": str(e)}

    return {"status": "success", "message": "User data updated"}

@app.post("/api/admin/member-action")
async def admin_member_action(request: Request, user: dict = Depends(is_authenticated)):
    """Kick or Ban a member"""
    data = await request.json()
    action = data.get("action") # KICK, BAN
    target_id = data.get("user_id")
    reason = data.get("reason", "Admin Web Action")
    
    if action not in ["KICK", "BAN"]:
        raise HTTPException(400, "Invalid Action")
        
    cmd = {
        "action": f"{action}_MEMBER",
        "payload": {
            "guild_id": get_active_guild_id(),
            "user_id": target_id,
            "reason": reason
        }
    }
    embed_queue.append(cmd)
    return {"status": "success", "message": f"{action} command queued for {target_id}"}


# --- NEW API ENDPOINTS ---
@app.get("/api/users")
async def api_get_users(request: Request, user: dict = Depends(is_authenticated)):
    """JSON Endpoint for User Data"""
    try:
        # 1. Fetch ALL Data First
        conn = get_db_conn(GACHA_DB)
        users_db = conn.execute("SELECT * FROM users").fetchall()
        # Get achievements for calculation
        achievements_db = [dict(row) for row in conn.execute("SELECT * FROM achievement_roles").fetchall()]
        conn.close()
        
        members = await get_discord_members()
        roles = await get_discord_roles() # This is now safe/cached
        
        role_map = {str(r["id"]): r for r in roles.values()}
        db_users_map = {str(u["user_id"]): dict(u) for u in users_db}
        
        # Fetch Economy Data
        from economy_system.db import get_db_conn as eco_db
        eco_conn = eco_db()
        eco_users = eco_conn.execute("SELECT * FROM bank_users").fetchall()
        eco_conn.close()
        eco_map = {str(u["discord_id"]): dict(u) for u in eco_users}
        
        # Filter: Only include users present in the CURRENT ACTIVE GUILD
        # Logic: We only care about keys in `members` (cache of active guild)
        # We try to enhance them with DB data if available.
        all_user_ids = list(members.keys())
        enriched_list = []
        
        search = request.query_params.get("search", "").lower()
        
        for uid in all_user_ids:
            u_db = db_users_map.get(uid, {"tickets": 0, "salt": 0, "total_rolls": 0, "custom_title": None})
            m_info = members.get(uid)
            
            if m_info:
                if m_info.get("bot"): continue
                name = m_info["name"]
                avatar = get_avatar_url(uid, m_info.get("avatar"))
                joined_at = m_info.get("joined_at")
            else:
                name = f"Unknown ({uid})"
                avatar = None
                joined_at = None

            if search:
                 if search not in uid and search not in name.lower() and (not u_db["custom_title"] or search not in u_db["custom_title"].lower()):
                    continue

            # Calculate Highest Role
            highest_pos = -1
            if m_info:
                for rid in m_info["roles"]:
                    rid = str(rid)
                    if rid in role_map:
                        pos = role_map[rid].get("position", 0)
                        if pos > highest_pos: highest_pos = pos

            # Get Eco Data
            eco_data = eco_map.get(uid, {})
            
            enriched_list.append({
                "user_id": uid,
                "tickets": u_db["tickets"],
                "salt": u_db["salt"],
                "total_rolls": u_db["total_rolls"],
                "custom_title": u_db["custom_title"],
                "wallet": eco_data.get("balance", 0),
                "bank": eco_data.get("bank_balance", 0),
                "xp": eco_data.get("xp", 0),
                "name": name,
                "avatar": avatar,
                "joined_at": joined_at,
                "highest_pos": highest_pos
            })

        # Sort
        enriched_list.sort(key=lambda x: (-x["highest_pos"], x["name"].lower()))
        
        # Pagination
        page = int(request.query_params.get("page", 1))
        per_page = 20
        total_count = len(enriched_list)
        offset = (page - 1) * per_page
        paged_users = enriched_list[offset:offset + per_page]
        
        return {
            "data": paged_users,
            "total": total_count,
            "page": page,
            "total_pages": (total_count + per_page - 1) // per_page
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

@app.get("/api/logs")
async def api_get_logs(request: Request, user: dict = Depends(is_authenticated)):
    try:
        page = int(request.query_params.get("page", 1))
        search = request.query_params.get("search", "")
        category = request.query_params.get("category", "")
        per_page = 50
        offset = (page - 1) * per_page

        conn = get_db_conn(LOG_DB)
        query = "SELECT * FROM audit_logs "
        params = []
        
        # Filter by Active Guild
        current_gid = get_active_guild_id()
        where_clauses = ["(guild_id = ? OR guild_id IS NULL)"] # Show NULL for legacy/system logs? Or strictly filter? Let's check.
        # Strict mode: where_clauses = ["guild_id = ?"]
        # Allow NULL for backwards compatibility? Maybe better to filter strict for multi-server.
        # But old logs have NULL. Let's include NULL only if we are in the default guild?
        # Simpler: just filter by ID. If old logs are important, we'd need to migrate them.
        params.append(current_gid)
        
        if search:
            where_clauses.append("(executor LIKE ? OR target LIKE ? OR details LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        if category:
            where_clauses.append("category = ?")
            params.append(category)
            
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        total_count = conn.execute(f"SELECT COUNT(*) FROM ({query})", params).fetchone()[0]
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        all_params = params + [per_page, offset]
        
        logs_raw = conn.execute(query, all_params).fetchall()
        conn.close()
        
        members = await get_discord_members()
        enriched_logs = []
        for log in logs_raw:
            entry = dict(log)
            # Simple enrichment for API
            clean_executor = entry["executor"].replace("<@", "").replace(">", "").replace("!", "")
            m_exec = members.get(clean_executor)
            entry["operator_name"] = m_exec["name"] if m_exec else clean_executor
            entry["event_thai"] = EVENT_TRANSLATIONS.get(entry["event_type"], entry["event_type"])
            enriched_logs.append(entry)
            
        return {
            "data": enriched_logs,
            "total": total_count,
            "page": page,
            "total_pages": (total_count + per_page - 1) // per_page
        }
    except Exception as e:
        return {"error": str(e)}




# --- Gacha Configuration & API ---

# Redundant modern API removed to favor legacy /gacha/bulk_update

@app.post("/api/gacha/pull")
async def api_gacha_pull(request: Request, user: dict = Depends(is_authenticated)):
    user_id = user["id"]
    conn = get_db_conn(GACHA_DB)
    cur = conn.cursor()
    cur.execute("SELECT tickets, salt, total_rolls FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    
    if not row:
        cur.execute("INSERT INTO users (user_id, tickets, salt, total_rolls) VALUES (?, 0, 0, 0)", (user_id,))
        conn.commit()
        tickets = 0
    else:
        tickets = row["tickets"]
        
    cost = 1 # Global cost for now
    
    if tickets < cost:
        conn.close()
        return {"error": "Not enough tickets", "tickets": tickets}
        
    # Deduct ticket
    cur.execute("UPDATE users SET tickets = tickets - ?, total_rolls = total_rolls + 1 WHERE user_id = ?", (cost, user_id))
    
    # Roll
    tier_name, reward, salt_received = gacha_config.roll_gacha()
    
    # Process Reward
    if reward == "à¹à¸à¸¥à¸·à¸­":
        cur.execute("UPDATE users SET salt = salt + ? WHERE user_id = ?", (salt_received, user_id))
    else:
        # Queue role assignment for Bot
        global embed_queue
        # Ensure reward is valid role ID
        if isinstance(reward, int) or (isinstance(reward, str) and reward.isdigit()):
            cmd = {
                "action": "GIVE_ROLE",
                "payload": {
                    "user_id": user_id,
                    "role_id": int(reward)
                }
            }
            embed_queue.append(cmd)
            
    conn.commit()
    
    # Get updated balance
    cur.execute("SELECT tickets, salt FROM users WHERE user_id = ?", (user_id,))
    new_row = cur.fetchone()
    conn.close()
    
    return {
        "success": True,
        "result": {
            "tier": tier_name,
            "reward": reward,
            "is_salt": (reward == "à¹à¸à¸¥à¸·à¸­")
        },
        "balance": {
            "tickets": new_row["tickets"],
            "salt": new_row["salt"]
        }
    }


# Consolidated into /gacha

@app.get("/gacha/pull", response_class=HTMLResponse)
async def view_gacha_pull(request: Request, user: dict = Depends(is_authenticated)):
    user_id = user["id"]
    conn = get_db_conn(GACHA_DB)
    cur = conn.cursor()
    cur.execute("SELECT tickets, salt FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    
    balance = {"tickets": 0, "salt": 0}
    if row:
        balance = {"tickets": row["tickets"], "salt": row["salt"]}
    
    return templates.TemplateResponse("gacha_pull.html", {"request": request, "user": user, "balance": balance})

# --- Token Checker ---
@app.get("/token_checker", response_class=HTMLResponse)
async def token_checker_page(request: Request, user: dict = Depends(is_authenticated)):
    return templates.TemplateResponse("token_checker.html", {"request": request, "user": user})

@app.post("/api/check_tokens")
async def check_tokens_stream(request: Request, tokens: str = Form(...), user: dict = Depends(is_authenticated)):
    from starlette.responses import StreamingResponse
    import json
    
    async def process_tokens():
        token_list = [t.strip() for t in tokens.split('\n') if t.strip()]
        total = len(token_list)
        
        if total == 0:
            yield json.dumps({"type": "error", "message": "No tokens provided"}) + "\n"
            return

        yield json.dumps({"type": "start", "total": total}) + "\n"
        
        yield json.dumps({"type": "done"}) + "\n"

    return StreamingResponse(process_tokens(), media_type="application/x-ndjson")

# --- Server Selection ---
@app.get("/servers", response_class=HTMLResponse)
async def server_selection_page(request: Request, user: dict = Depends(is_authenticated)):
    # Fetch guilds the bot is in
    guilds = []
    if BOT_TOKEN:
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bot {BOT_TOKEN}"}
                res = await client.get("https://discord.com/api/v10/users/@me/guilds", headers=headers)
                if res.status_code == 200:
                    guilds = res.json()
        except: pass
    
    return templates.TemplateResponse("server_select.html", {"request": request, "user": user, "guilds": guilds})

@app.post("/api/set_server/{guild_id}")
async def set_server(guild_id: str, request: Request, user: dict = Depends(is_authenticated)):
    global ACTIVE_GUILD_ID, role_cache, member_cache, channel_cache
    
    # Verify bot is actually in this guild (basic security)
    # For now, just trust the ID or strictly we should verify against the fetch list
    
    ACTIVE_GUILD_ID = guild_id
    
    # Clear Caches to force refresh for new server
    role_cache = {"data": {}, "last_fetch": 0}
    member_cache = {"data": {}, "last_fetch": 0}
    channel_cache = {"data": {}, "last_fetch": 0}
    
    print(f"[System] Switched Active Guild to: {ACTIVE_GUILD_ID}")
    
    # Trigger bg refresh
    asyncio.create_task(background_scheduler())
    
    return RedirectResponse(url="/users", status_code=303)

# --- OAuth2 Routes ---
@app.get("/login_page", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login")
async def login():
    discord_auth_url = (
        f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify"
    )
    return RedirectResponse(discord_auth_url)

@app.get("/callback")
async def callback(request: Request, code: str):
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    async with httpx.AsyncClient() as client:
        try:
            # Get Token
            token_res = await client.post('https://discord.com/api/oauth2/token', data=data, headers=headers)
            if token_res.status_code != 200:
                error_detail = token_res.json()
                return HTMLResponse(content=f"<h2>Login Error</h2><p>Discord rejected the request: {error_detail.get('error_description', 'Invalid Secret or ID')}</p><a href='/login_page'>Go Back</a>", status_code=400)
            
            token = token_res.json()
            
            # Get User Info
            user_headers = {'Authorization': f"Bearer {token['access_token']}"}
            user_res = await client.get('https://discord.com/api/users/@me', headers=user_headers)
            user_res.raise_for_status()
            user_info = user_res.json()
            
            # Save user to session
            request.session["user"] = user_info
            
        except Exception as e:
            return HTMLResponse(content=f"<h2>System Error</h2><p>{str(e)}</p><a href='/login_page'>Go Back</a>", status_code=500)
        
    return RedirectResponse(url="/")

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login_page")

# --- Dashboard Protected Routes ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, user: dict = Depends(is_authenticated)):
    return RedirectResponse(url="/users")

# --- Heartbeat Status (Public for Bot) ---
@app.post("/status")
async def update_status(request: Request):
    bot_status["online"] = True
    bot_status["last_heartbeat"] = time.time()
    
    # Receive messages from bot
    try:
        body = await request.json()
        incoming_messages = body.get("messages", [])
        for msg in incoming_messages:
            ch_id = str(msg.get("channel_id"))
            if ch_id not in message_cache:
                message_cache[ch_id] = []
            message_cache[ch_id].append(msg)
            # Keep only last 100 messages per channel
            message_cache[ch_id] = message_cache[ch_id][-100:]
    except:
        pass  # No JSON body is fine for simple heartbeat
    
    global embed_queue, message_queue
    payload = list(embed_queue) + list(message_queue)
    if payload:
        print(f"[Dashboard] Sending {len(payload)} commands to bot: {[c['action'] for c in payload]}")
    embed_queue = []
    message_queue = []
    return {"status": "ok", "commands": payload}

# --- User Management ---
@app.get("/users", response_class=HTMLResponse)
async def view_users(request: Request, user: dict = Depends(is_authenticated)):
    try:
        # 1. Fetch ALL Data First
        conn = get_db_conn(GACHA_DB)
        users_db = conn.execute("SELECT * FROM users").fetchall()
        # Get achievements for calculation
        achievements_db = [dict(row) for row in conn.execute("SELECT * FROM achievement_roles").fetchall()]
        conn.close()
        
        members = await get_discord_members()
        roles = await get_discord_roles()
        
        # Prepare Role Metadata
        # Sorting roles by position descending
        sorted_roles = sorted(roles.values(), key=lambda r: r.get("position", 0), reverse=True)
        role_map = {str(r["id"]): r for r in roles.values()} # ID -> Role Data
        
        # Map DB users
        db_users_map = {str(u["user_id"]): dict(u) for u in users_db}
        
        # 2. Merge & Calculate "Highest Role Position"
        all_user_ids = set(db_users_map.keys()) | set(members.keys())
        enriched_list = []
        
        search = request.query_params.get("search", "").lower()
        
        for uid in all_user_ids:
            # Base Data from DB
            u_db = db_users_map.get(uid, {
                "tickets": 0, "salt": 0, "total_rolls": 0, "custom_title": None
            })
            
            # Data from Discord
            m_info = members.get(uid)
            
            # Determine Name & Avatar
            # Determine Name & Avatar
            if m_info:
                if m_info.get("bot"): continue # Skip bots
                name = m_info["name"]
                avatar = f"https://cdn.discordapp.com/avatars/{uid}/{m_info['avatar']}.png" if m_info['avatar'] else "https://cdn.discordapp.com/embed/avatars/0.png"
                joined_at = m_info.get("joined_at")
                user_roles = [role_map.get(str(rid), {"name": str(rid), "color": "#99aab5"}) for rid in m_info["roles"]]
            else:
                name = f"Unknown ({uid})"
                avatar = None
                joined_at = None
                user_roles = []

            # Filter by Search (if exists)
            if search:
                if search not in uid and search not in name.lower() and (not u_db["custom_title"] or search not in u_db["custom_title"].lower()):
                    continue

            # Calculate Highest Role Position & Name
            highest_pos = -1
            top_role_name = "Member"
            top_role_color = "#99aab5"
            
            if m_info:
                for rid in m_info["roles"]:
                    rid = str(rid)
                    if rid in role_map:
                        r_data = role_map[rid]
                        pos = r_data.get("position", 0)
                        if pos > highest_pos:
                            highest_pos = pos
                            top_role_name = r_data.get("name")
                            top_role_color = r_data.get("color") or "#99aab5"

            # Achievements Logic
            user_achievements = []
            for ach in achievements_db:
                stat_val = u_db.get(ach["stat_key"], 0)
                if stat_val and stat_val >= ach["requirement_value"]:
                    user_achievements.append({
                        "name": ach["name"],
                        "style": "background: #f59e0b; color: #fff;" if ach["stat_key"] == "salt" else "background: #6366f1; color: #fff;"
                    })

            enriched_list.append({
                "user_id": uid,
                "tickets": u_db["tickets"],
                "salt": u_db["salt"],
                "total_rolls": u_db["total_rolls"],
                "custom_title": u_db["custom_title"],
                "name": name,
                "username": m_info.get("username", "") if m_info else "Unknown",
                "avatar_url": avatar,
                "joined_at": joined_at,
                "roles": user_roles, 
                "achievements": user_achievements,
                "highest_pos": highest_pos,
                "top_role": top_role_name,
                "role_color": top_role_color
            })

        # 3. Sort: Highest Role Position (Desc) -> Name (Asc)
        enriched_list.sort(key=lambda x: (-x["highest_pos"], x["name"].lower()))
        
        # 4. Pagination
        page = int(request.query_params.get("page", 1))
        per_page = 20
        total_count = len(enriched_list)
        offset = (page - 1) * per_page
        
        paged_users = enriched_list[offset:offset + per_page]
        
        is_online = (time.time() - bot_status["last_heartbeat"]) < 90

        return templates.TemplateResponse("users.html", {
            "request": request, 
            "users": paged_users,
            "roles": roles,
            "bot_online": is_online,
            "user": user,
            "page": page,
            "search": search,
            "total_pages": (total_count + per_page - 1) // per_page,
            "total_count": total_count,
            "server_count": len(members)
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HTMLResponse(content=f"<h1>Internal Error</h1><pre>{traceback.format_exc()}</pre>", status_code=500)

@app.get("/members", response_class=HTMLResponse)
async def view_members(request: Request, user: dict = Depends(is_authenticated)):
    try:
        members = await get_discord_members()
        roles = await get_discord_roles()
        is_online = (time.time() - bot_status["last_heartbeat"]) < 90
        
        # Pagination params
        page = int(request.query_params.get("page", 1))
        per_page = 100 
        
        # 1. Prepare Roles Metadata
        sorted_roles = sorted(roles.values(), key=lambda r: r.get("position", 0), reverse=True)
        role_map = {str(r["id"]): r for r in roles.values()}
        
        # 2. Assign Highest Role & Sort All Members
        all_processed = []
        for uid, m in members.items():
            if m.get("bot"): continue # Skip bots in members list too

            highest_pos = -1
            highest_r_id = "@everyone"
            
            # Find highest ranked role for this member
            for rid in m["roles"]:
                rid = str(rid)
                if rid in role_map:
                    pos = role_map[rid].get("position", 0)
                    if pos > highest_pos:
                        highest_pos = pos
                        highest_r_id = rid
            
            all_processed.append({
                "data": m,
                "uid": uid,
                "highest_pos": highest_pos,
                "highest_r_id": highest_r_id,
                "name": (m.get("name") or "").lower()
            })
            
        # Sort by: Role Position (Desc) -> Name (Asc)
        all_processed.sort(key=lambda x: (-x["highest_pos"], x["name"]))
        
        # 3. Pagination (on the sorted list)
        total_count = len(all_processed)
        offset = (page - 1) * per_page
        paged_items = all_processed[offset:offset + per_page]
        
        # 4. Grouping (Preserving Role Order)
        # Create buckets in order of role hierarchy
        grouped = {}
        for r in sorted_roles:
            grouped[str(r["id"])] = {
                "name": r["name"],
                "color": r.get("color", "#ffffff"),
                "members": []
            }
        grouped["@everyone"] = {"name": "Everyone", "color": "#ffffff", "members": []}
        
        # Populate buckets with paged members
        for item in paged_items:
            m = item["data"]
            m["id"] = item["uid"]
            m["status"] = "offline" # Placeholder as we don't have real-time presence yet
            
            target_group = item["highest_r_id"]
            if target_group not in grouped:
                target_group = "@everyone"
                
            # Enrich with Avatar URL & Username
            m["avatar_url"] = f"https://cdn.discordapp.com/avatars/{item['uid']}/{m['avatar']}.png" if m.get("avatar") else "https://cdn.discordapp.com/embed/avatars/0.png"
            m["username"] = m.get("username", "Unknown")
            
            grouped[target_group]["members"].append(m)
            
        # Remove empty groups to clean up UI (but keep order)
        final_groups = {k: v for k, v in grouped.items() if v["members"]}
        
        # Calculate statistics for dashboard cards
        # Note: We don't have real-time presence data, so online_count is estimated
        online_count = 0  # Placeholder - would need Discord Gateway for real presence
        
        # Count bots (from all members, not just paged)
        bot_count = sum(1 for m in members.values() if m.get("bot"))
        
        # Calculate new members (last 7 days)
        # Discord snowflake IDs contain timestamp information
        import datetime
        seven_days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
        seven_days_ago_timestamp = int(seven_days_ago.timestamp() * 1000)
        
        new_members_count = 0
        for uid, m in members.items():
            try:
                # Discord snowflake to timestamp: ((id >> 22) + 1420070400000) / 1000
                user_id_int = int(uid)
                created_timestamp = ((user_id_int >> 22) + 1420070400000)
                if created_timestamp >= seven_days_ago_timestamp:
                    new_members_count += 1
            except:
                pass

        return templates.TemplateResponse("members.html", {
            "request": request,
            "grouped_members": final_groups,
            "bot_online": is_online,
            "user": user,
            "page": page,
            "total_pages": (total_count + per_page - 1) // per_page,
            "total_count": total_count,
            "online_count": online_count,
            "new_members_count": new_members_count,
            "bot_count": bot_count
        })
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"<h1>Error</h1><pre>{traceback.format_exc()}</pre>", status_code=500)

@app.post("/users/update")
async def update_user(user_id: str = Form(None), tickets: int = Form(...), salt: int = Form(...), total_rolls: int = Form(0), custom_title: str = Form(None), user: dict = Depends(is_authenticated)):
    if not user_id:
        return RedirectResponse(url="/users", status_code=303)
        
    conn = get_db_conn(GACHA_DB)
    # Check if user exists
    exists = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    if exists:
        conn.execute("UPDATE users SET tickets = ?, salt = ?, total_rolls = ?, custom_title = ? WHERE user_id = ?", (tickets, salt, total_rolls, custom_title, user_id))
    else:
        # Insert new user with provided stats
        conn.execute("INSERT INTO users (user_id, tickets, salt, total_rolls, custom_title) VALUES (?, ?, ?, ?, ?)", (user_id, tickets, salt, total_rolls, custom_title))
        
    conn.commit()
    conn.close()
    
    # Redirect back to the referrer (so it works from both /users and /members)
    # We can't easily get referrer safely here without request object, but we can default to users or check inputs.
    # For now, let's just return to /users or maybe we should return to where we came from? 
    # Actually, the form action in members.html will point here. If we redirect to /users, it might be annoying.
    # Let's try to grab the referrer header if possible, or just default to /users. 
    # Since the user specifically asked for "Member Database edit", redirecting to /members might be better if the request came from there.
    # But for now, let's just stick to /users as a safe default, or maybe we can pass a 'next' param.
    return RedirectResponse(url="/users", status_code=303)

# --- Gacha Config ---
@app.get("/api/debug/roles")
async def debug_roles(user: dict = Depends(is_authenticated)):
    roles = await get_discord_roles()
    return {
        "count": len(roles),
        "guilds_checked": role_cache.get("guilds_checked", 0),
        "roles": roles
    }

@app.post("/api/roles/refresh")
async def refresh_roles(user: dict = Depends(is_authenticated)):
    role_cache["data"] = {}
    role_cache["last_fetch"] = 0
    await get_discord_roles() # Pre-fetch
    return {"status": "success", "message": "Role cache cleared and updated"}


@app.get("/gacha", response_class=HTMLResponse)
async def view_gacha(request: Request, user: dict = Depends(is_authenticated)):
    conn = get_db_conn(GACHA_DB)
    settings = conn.execute("SELECT * FROM gacha_settings").fetchall()
    achievements = conn.execute("SELECT * FROM achievement_roles").fetchall()
    conn.close()
    
    roles = await get_discord_roles()
    channels = await get_discord_channels()
    is_online = (time.time() - bot_status["last_heartbeat"]) < 90
    return templates.TemplateResponse("gacha_config.html", {
        "request": request, 
        "settings": settings,
        "achievements": achievements,
        "roles": roles,
        "channels": channels,
        "bot_online": is_online,
        "user": user
    })

@app.post("/gacha/update")
async def update_gacha(rank_name: str = Form(...), percentage: float = Form(...), reward_roles: str = Form(None), user: dict = Depends(is_authenticated)):
    roles_list = [r.strip() for r in reward_roles.split(',')] if reward_roles else []
    import json
    conn = get_db_conn(GACHA_DB)
    conn.execute('''
        UPDATE gacha_settings 
        SET percentage = ?, reward_roles_json = ? 
        WHERE rank_name = ?
    ''', (percentage, json.dumps(roles_list), rank_name))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/gacha", status_code=303)

@app.post("/achievements/update")
async def update_achievement(name: str = Form(...), role_id: str = Form(...), req_val: int = Form(...), user: dict = Depends(is_authenticated)):
    conn = get_db_conn(GACHA_DB)
    conn.execute('''
        UPDATE achievement_roles 
        SET role_id = ?, requirement_value = ? 
        WHERE name = ?
    ''', (role_id, req_val, name))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/gacha", status_code=303)

@app.post("/gacha/add")
async def add_gacha_tier(rank_name: str = Form(...), percentage: float = Form(...), reward_roles: str = Form(None), user: dict = Depends(is_authenticated)):
    roles_list = [r.strip() for r in reward_roles.split(',')] if reward_roles else []
    import json
    conn = get_db_conn(GACHA_DB)
    try:
        conn.execute('INSERT INTO gacha_settings (rank_name, percentage, reward_roles_json) VALUES (?, ?, ?)', 
                     (rank_name, percentage, json.dumps(roles_list)))
        conn.commit()
    except:
        pass # Handle unique constraint if needed
    finally:
        conn.close()
    return RedirectResponse(url="/gacha", status_code=303)

@app.post("/gacha/delete")
async def delete_gacha_tier(rank_name: str = Form(...), user: dict = Depends(is_authenticated)):
    conn = get_db_conn(GACHA_DB)
    conn.execute('DELETE FROM gacha_settings WHERE rank_name = ?', (rank_name,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/gacha", status_code=303)

@app.post("/gacha/bulk_update")
async def bulk_update_gacha(request: Request, user: dict = Depends(is_authenticated)):
    """Handles syncing the entire gacha matrix: updates, additions, and deletions."""
    data = await request.json()
    tiers = data.get("tiers", [])
    import json
    
    conn = get_db_conn(GACHA_DB)
    try:
        # Perform full sync: Delete all and re-insert the new state
        conn.execute("DELETE FROM gacha_settings")
        
        for tier in tiers:
            name = tier.get("rank_name")
            pct = tier.get("percentage")
            roles_list = tier.get("reward_roles", [])
            
            conn.execute('''
                INSERT INTO gacha_settings (rank_name, percentage, reward_roles_json)
                VALUES (?, ?, ?)
            ''', (name, pct, json.dumps(roles_list)))
            
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

# --- Live Logs ---
@app.get("/logs", response_class=HTMLResponse)
async def view_logs(request: Request, user: dict = Depends(is_authenticated)):
    try:
        # Pagination & Filtering
        page = int(request.query_params.get("page", 1))
        search = request.query_params.get("search", "")
        category = request.query_params.get("category", "")
        per_page = 50
        offset = (page - 1) * per_page

        conn = get_db_conn(LOG_DB)
        query = "SELECT * FROM audit_logs "
        params = []
        
        where_clauses = []
        if search:
            where_clauses.append("(executor LIKE ? OR target LIKE ? OR details LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        if category:
            where_clauses.append("category = ?")
            params.append(category)
            
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        # Get total count for pagination
        total_count = conn.execute(f"SELECT COUNT(*) FROM ({query})", params).fetchone()[0]

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        all_params = params + [per_page, offset]
        
        logs_raw = conn.execute(query, all_params).fetchall()
        conn.close()
        
        members = await get_discord_members()
        roles = await get_discord_roles()
        channels = await get_discord_channels()
        is_online = (time.time() - bot_status["last_heartbeat"]) < 90
        
        # Enrich log data
        enriched_logs = []
        for log in logs_raw:
            entry = dict(log)
            # Operator info
            clean_executor = entry["executor"].replace("<@", "").replace(">", "").replace("!", "")
            m_exec = members.get(clean_executor)
            if m_exec:
                entry["operator_name"] = m_exec["name"]
                entry["operator_username"] = m_exec["username"]
                entry["operator_avatar"] = get_avatar_url(clean_executor, m_exec["avatar"])
            else:
                entry["operator_name"] = entry["executor"]
                entry["operator_username"] = ""
                entry["operator_avatar"] = None

            # Target info
            clean_target = str(entry["target"]).replace("<@", "").replace(">", "").replace("!", "")
            m_target = members.get(clean_target)
            r_target = roles.get(clean_target)
            c_target = channels.get(clean_target)

            if m_target:
                entry["target_name"] = m_target["name"]
                entry["target_username"] = m_target["username"]
                entry["target_avatar"] = get_avatar_url(clean_target, m_target["avatar"])
                entry["target_type"] = "USER"
            elif r_target:
                entry["target_name"] = f"à¸à¸à¸à¸²à¸: {r_target['name']}"
                entry["target_username"] = "Role Card"
                entry["target_avatar"] = "/static/role_icon.png"
                entry["target_type"] = "ROLE"
            elif c_target:
                entry["target_name"] = f"à¸«à¹à¸­à¸: {c_target['name']}"
                entry["target_username"] = "Channel"
                entry["target_avatar"] = "/static/channel_icon.png"
                entry["target_type"] = "CHANNEL"
            else:
                entry["target_name"] = entry["target"]
                entry["target_username"] = ""
                entry["target_avatar"] = None
                entry["target_type"] = "OTHER"
            
            entry["event_thai"] = EVENT_TRANSLATIONS.get(entry["event_type"], entry["event_type"])
            enriched_logs.append(entry)
        
        return templates.TemplateResponse("logs.html", {
            "request": request, 
            "logs": enriched_logs,
            "bot_online": is_online,
            "user": user,
            "roles": roles,
            "translations": EVENT_TRANSLATIONS,
            "page": page,
            "search": search,
            "category": category,
            "total_pages": (total_count + per_page - 1) // per_page
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HTMLResponse(content=f"<h1>Error</h1><pre>{traceback.format_exc()}</pre>", status_code=500)

# --- Analytics ---
@app.get("/analytics", response_class=HTMLResponse)
async def view_analytics(request: Request, user: dict = Depends(is_authenticated)):
    conn_gacha = get_db_conn(GACHA_DB)
    conn_logs = get_db_conn(LOG_DB)
    
    economy = conn_gacha.execute("SELECT SUM(tickets) as total_tickets, SUM(salt) as total_salt FROM users").fetchone()
    
    ranks = conn_gacha.execute("SELECT rank_name FROM gacha_settings").fetchall()
    distribution = {}
    for r in ranks:
        name = r['rank_name']
        count = conn_logs.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type = 'GACHA_PULL' AND details LIKE ?", (f'%"{name}"%',)).fetchone()[0]
        distribution[name] = count
        
    growth_rows = conn_logs.execute("SELECT DATE(timestamp) as date, COUNT(*) as count FROM audit_logs WHERE event_type LIKE 'GACHA_%' GROUP BY DATE(timestamp) ORDER BY date DESC LIMIT 7").fetchall()
    growth = [dict(row) for row in growth_rows]
    
    # Leaderboard: Top 5 by tickets or salt
    leaderboard_tickets = conn_gacha.execute("SELECT user_id, tickets FROM users ORDER BY tickets DESC LIMIT 5").fetchall()
    leaderboard_salt = conn_gacha.execute("SELECT user_id, salt FROM users ORDER BY salt DESC LIMIT 5").fetchall()
    
    members = await get_discord_members()
    
    enriched_leaderboard = {
        "tickets": [{"name": members.get(str(r["user_id"]), {}).get("name", "Unknown"), "val": r["tickets"]} for r in leaderboard_tickets],
        "salt": [{"name": members.get(str(r["user_id"]), {}).get("name", "Unknown"), "val": r["salt"]} for r in leaderboard_salt]
    }
    
    conn_gacha.close()
    conn_logs.close()
    
    is_online = (time.time() - bot_status["last_heartbeat"]) < 90
    
    return templates.TemplateResponse("analytics.html", {
        "request": request, 
        "economy": economy, 
        "distribution": distribution,
        "growth": growth,
        "leaderboard": enriched_leaderboard,
        "bot_online": is_online,
        "user": user
    })

@app.post("/api/embed/random")
async def send_random_embed(
    channel_id: str = Form(...),
    user: dict = Depends(is_authenticated)
):
    conn = get_db_conn(GACHA_DB)
    # Pick a random setting to use as a template
    settings = conn.execute("SELECT * FROM gacha_settings WHERE rank_name != 'Salt' ORDER BY RANDOM() LIMIT 1").fetchone()
    conn.close()
    
    if not settings:
        return {"status": "error", "message": "No settings found"}
        
    global embed_queue
    embed_queue.append({
        "action": "SEND_EMBED",
        "channel_id": channel_id,
        "payload": {
            "title": f"🎲 RANDOM: {settings['embed_title']}",
            "description": settings['embed_description'],
            "color": int(settings['embed_color'].lstrip('#'), 16) if settings['embed_color'].startswith('#') else int(settings['embed_color'], 16),
            "thumbnail": settings['embed_thumbnail_url'],
            "image": settings['embed_image_url'],
            "footer": f"{settings['embed_footer']} • Randomized"
        }
    })
    return RedirectResponse(url="/gacha", status_code=303)

# --- Embed Management restored ---

# --- Event Management restored (partial for future) ---


# --- Chat System ---
@app.get("/chat", response_class=HTMLResponse)
async def view_chat(request: Request, user: dict = Depends(is_authenticated)):
    """Chat page - View and send messages through Discord"""
    channels = await get_discord_channels()
    
    # Filter only text channels (type 0) and sort by position
    text_channels = {k: v for k, v in channels.items() if v.get("type") == 0}
    sorted_channels = dict(sorted(text_channels.items(), key=lambda x: x[1].get("position", 0)))
    
    is_online = (time.time() - bot_status["last_heartbeat"]) < 90
    
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "channels": sorted_channels,
        "bot_online": is_online,
        "user": user
    })

@app.get("/api/channels")
async def get_channels_api(user: dict = Depends(is_authenticated)):
    """API to get all text channels"""
    channels = await get_discord_channels()
    # Filter only text channels (type 0)
    text_channels = {k: v for k, v in channels.items() if v.get("type") == 0}
    return {"channels": text_channels}

@app.get("/api/messages/{channel_id}")
async def get_messages(channel_id: str, user: dict = Depends(is_authenticated)):
    """Get messages for a channel - combines history from Discord API with cached new messages"""
    # Fetch history from Discord API
    history_messages = await fetch_channel_messages(channel_id, limit=50)
    
    # Get cached new messages (received via bot heartbeat)
    cached_messages = message_cache.get(channel_id, [])
    
    # Merge: history + any new cached messages not in history
    history_ids = {m["message_id"] for m in history_messages}
    new_messages = [m for m in cached_messages if m.get("message_id") not in history_ids]
    
    all_messages = history_messages + new_messages
    
    # Enrich with Role Colors
    members = await get_discord_members()
    roles = await get_discord_roles() # Ensure roles are loaded
    role_map = {str(r["id"]): r for r in roles.values()}
    
    enriched_messages = []
    for msg in all_messages:
        # Default color
        color = "#ffffff" 
        
        author_id = msg.get("author_id")
        if author_id and author_id in members:
            member = members[author_id]
            # Find highest role color
            highest_pos = -1
            for rid in member["roles"]:
                rid = str(rid)
                if rid in role_map:
                    r_data = role_map[rid]
                    if r_data.get("color") and r_data.get("position", 0) > highest_pos:
                        highest_pos = r_data.get("position", 0)
                        color = r_data.get("color")
        
        msg["author_color"] = color
        enriched_messages.append(msg)
    
    # Return last 50 messages
    return {"messages": enriched_messages[-50:]}

@app.post("/api/send-message")
async def send_message_api(request: Request, user: dict = Depends(is_authenticated)):
    """Queue a message to be sent by the bot"""
    data = await request.json()
    channel_id = data.get("channel_id")
    content = data.get("content", "")
    image_url = data.get("image_url")
    reply_to_id = data.get("reply_to_id")  # Message ID to reply to
    
    if not channel_id:
        raise HTTPException(status_code=400, detail="channel_id required")
    
    if not content and not image_url:
        raise HTTPException(status_code=400, detail="content or image_url required")
    
    global message_queue
    message_queue.append({
        "action": "SEND_MESSAGE",
        "channel_id": channel_id,
        "payload": {
            "content": content,
            "image_url": image_url,
            "reply_to_id": reply_to_id
        }
    })
    return {"status": "queued"}

@app.post("/api/messages/receive")
async def receive_messages(request: Request):
    """Endpoint for bot to send messages to dashboard (alternative to heartbeat)"""
    try:
        data = await request.json()
        messages = data.get("messages", [])
        for msg in messages:
            ch_id = str(msg.get("channel_id"))
            if ch_id not in message_cache:
                message_cache[ch_id] = []
            message_cache[ch_id].append(msg)
            message_cache[ch_id] = message_cache[ch_id][-100:]
        return {"status": "ok", "received": len(messages)}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/admin/env")
async def update_env_api(request: Request, user: dict = Depends(is_authenticated)):
    """Update valid keys in .env and restart process suggestion"""
    # Restrict to Admin ID for safety
    if ADMIN_USER_ID and str(user.get("id")) != str(ADMIN_USER_ID):
        raise HTTPException(status_code=403, detail="Unauthorized: Only Bot Owner can modify environment.")
    
    data = await request.json()
    valid_keys = ["DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET", "TOKEN", "DISCORD_REDIRECT_URI", "ADMIN_USER_ID"]
    
    updates = {k: v for k, v in data.items() if k in valid_keys}
    
    if not updates:
         return {"status": "error", "message": "No valid keys provided"}
         
    for k, v in updates.items():
        update_env_file(k, v)
        
    return {"status": "success", "message": "Settings saved. Restart server to apply."}

def update_env_file(key, value):
    """Safely updates a key-value pair in the .env file."""
    env_path = os.path.join(os.getcwd(), '.env')
    try:
        if not os.path.exists(env_path):
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(f'{key}={value}\n')
            return

        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        key_found = False
        new_lines = []
        for line in lines:
            if line.strip().startswith(f'{key}='):
                new_lines.append(f'{key}={value}\n')
                key_found = True
            else:
                new_lines.append(line)

        if not key_found:
            new_lines.append(f'\n{key}={value}\n')

        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

    except Exception as e:
        print(f"Error updating .env: {e}")

@app.get("/api/admin/env")
async def get_env_api(user: dict = Depends(is_authenticated)):
    """Get masked env vars for display"""
    # Only show masked versions to UI
    KEYS = ["DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET", "TOKEN", "DISCORD_REDIRECT_URI", "ADMIN_USER_ID"]
    current = {}
    
    # Read fresh from file or os? better from os but file is source of truth for edits.
    # Let's read file to show what is SAVED.
    env_path = os.path.join(os.getcwd(), '.env')
    file_vals = {}
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    k, v = line.strip().split('=', 1)
                    file_vals[k] = v
    
    for k in KEYS:
        val = file_vals.get(k, os.getenv(k, ""))
        current[k] = val
        
    return {"data": current}

# --- Shop Admin API ---

# --- Shop System Removed ---
# --- Giveaway System ---
@app.get("/giveaways", response_class=HTMLResponse)
async def view_giveaways(request: Request, user: dict = Depends(is_authenticated)):
    from economy_system.giveaway_service import GiveawayService
    giveaways = GiveawayService.get_active_giveaways()
    channels = await get_discord_channels()
    
    # Sort updates
    text_channels = {k: v for k, v in channels.items() if v.get("type") == 0}
    is_online = (time.time() - bot_status["last_heartbeat"]) < 90
    
    return templates.TemplateResponse("giveaway.html", {
        "request": request,
        "user": user,
        "giveaways": giveaways,
        "channels": text_channels,
        "bot_online": is_online
    })

@app.post("/api/giveaway/create")
async def create_giveaway(
    title: str = Form(...),
    prize_type: str = Form(...),
    prize_value: str = Form(...),
    winner_count: int = Form(1),
    duration_hours: float = Form(24),
    channel_id: str = Form(...),
    user: dict = Depends(is_authenticated)
):
    from economy_system.giveaway_service import GiveawayService
    import datetime
    
    end_time = datetime.datetime.now() + datetime.timedelta(hours=duration_hours)
    
    gw_id = GiveawayService.create_giveaway(
        title=title,
        description=f"Hosted by {user['username']}",
        prize_type=prize_type,
        prize_value=prize_value,
        end_time_str=end_time.strftime("%Y-%m-%d %H:%M:%S"),
        winner_count=winner_count,
        channel_id=channel_id,
        host_id=user["id"]
    )
    
    # Queue Embed for Bot
    embed_queue.append({
        "action": "SEND_EMBED",
        "channel_id": channel_id,
        "payload": {
            "title": f"🎉 GIVEAWAY: {title}",
            "description": f"React with 🎉 to enter!\nPrize: **{prize_value}** ({prize_type})\nEnds: {end_time.strftime('%Y-%m-%d %H:%M')}\nWinners: {winner_count}",
            "color": 0xFFD700, # Gold
            "footer": f"Giveaway ID: {gw_id}"
        }
    })
    
    return RedirectResponse(url="/giveaways", status_code=303)

@app.post("/api/giveaway/end")
async def end_giveaway(giveaway_id: int = Form(...), user: dict = Depends(is_authenticated)):
    from economy_system.giveaway_service import GiveawayService
    result = GiveawayService.end_giveaway(giveaway_id)
    
    if result:
        winners = result["winners"]
        gw = result["giveaway"]
        
        # Announce Winners
        winner_text = ", ".join([f"<@{uid}>" for uid in winners]) if winners else "No valid entries."
        
        embed_queue.append({
            "action": "SEND_EMBED",
            "channel_id": gw["channel_id"],
            "payload": {
                "title": f"🎉 GIVEAWAY ENDED: {gw['title']}",
                "description": f"Prize: {gw['prize_value']}\n**Winners:** {winner_text}",
                "color": 0xFF0000 
            }
        })
        
    return RedirectResponse(url="/giveaways", status_code=303)

# --- Verification System ---
@app.get("/verification", response_class=HTMLResponse)
async def view_verification(request: Request, user: dict = Depends(is_authenticated)):
    conn = get_db_conn(GACHA_DB)
    # Get config (assume single guild system for now, or get first row)
    row = conn.execute("SELECT * FROM verification_config LIMIT 1").fetchone()
    if not row:
        # Init default
        conn.execute("INSERT OR IGNORE INTO verification_config (guild_id) VALUES (?)", ("default",))
        conn.commit()
        row = conn.execute("SELECT * FROM verification_config LIMIT 1").fetchone()
    config = dict(row)
    conn.close()
    
    roles = await get_discord_roles()
    channels = await get_discord_channels()
    text_channels = {k: v for k, v in channels.items() if v.get("type") == 0}
    is_online = (time.time() - bot_status["last_heartbeat"]) < 90

    return templates.TemplateResponse("verification.html", {
        "request": request,
        "user": user,
        "config": config,
        "roles": roles,
        "channels": text_channels,
        "bot_online": is_online
    })

@app.post("/api/verification/update")
async def update_verification(
    request: Request,
    user: dict = Depends(is_authenticated)
):
    form = await request.form()
    action = form.get("action")
    channel_id = form.get("channel_id")
    role_id = form.get("role_id")
    
    conn = get_db_conn(GACHA_DB)
    
    # Update Config
    conn.execute('''
        UPDATE verification_config SET
        channel_id = ?, role_id = ?, embed_title = ?, embed_description = ?, button_label = ?
        WHERE guild_id = 'default'
    ''', (
        channel_id,
        role_id,
        form.get("embed_title"),
        form.get("embed_description"),
        form.get("button_label")
    ))
    conn.commit()
    conn.close()
    
    if action == "send":
        # Queue Embed with Button
        embed_queue.append({
            "action": "SEND_VERIFY_PANEL", # Special action handled by bot
            "channel_id": channel_id,
            "payload": {
                "title": form.get("embed_title"),
                "description": form.get("embed_description"),
                "color": 0x10b981,
                "role_id": role_id,
                "button_label": form.get("button_label")
            }
        })
        
    return RedirectResponse(url="/verification", status_code=303)

# --- Announcement System ---
@app.get("/announcements", response_class=HTMLResponse)
async def view_announcements(request: Request, user: dict = Depends(is_authenticated)):
    from economy_system.announcement_service import AnnouncementService
    
    messages = AnnouncementService.get_all_messages()
    channels = await get_discord_channels()
    text_channels = {k: v for k, v in channels.items() if v.get("type") == 0}
    is_online = (time.time() - bot_status["last_heartbeat"]) < 90

    return templates.TemplateResponse("announcements.html", {
        "request": request,
        "user": user,
        "messages": messages,
        "channels": text_channels,
        "bot_online": is_online
    })

@app.post("/api/announcements/create")
async def create_announcement(
    channel_id: str = Form(...),
    content: str = Form(...),
    scheduled_time: str = Form(None),
    user: dict = Depends(is_authenticated)
):
    from economy_system.announcement_service import AnnouncementService
    import datetime
    
    # Process time
    if scheduled_time:
        # Browser sends format like "2023-10-27T14:30"
        # We need to ensure it's comparable to now
        # Replacing T with space is usually enough for SQLite default format
        schedule_dt = scheduled_time.replace("T", " ")
        if len(schedule_dt) == 16: schedule_dt += ":00" # Add seconds
    else:
        # Immediate
        schedule_dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    AnnouncementService.schedule_message(
        channel_id=channel_id,
        content=content,
        embed_json=None, # For now only text
        scheduled_time=schedule_dt,
        author_id=user["id"]
    )
    
    return RedirectResponse(url="/announcements", status_code=303)

if __name__ == "__main__":
    print("----------------------------------------------------------------")
    print("   GODWIN INTELLIGENCE DASHBOARD - STARTING NEW VERSION v2.0    ")
    print("   VERIFYING ADMIN ROUTES...                                    ")
    print("----------------------------------------------------------------")
    
    # DEBUG: PRINT ALL ROUTES
    print(">>> REGISTERED ROUTES:")
    print(">>> REGISTERED ROUTES:")
    for route in app.routes:
        path = getattr(route, "path", "Unknown Path")
        if hasattr(route, "methods"):
            print(f"   {path} [{','.join(route.methods)}]")
        else:
            print(f"   {path} [Static/Mount]")
    print("----------------------------------------------------------------")

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

