import sys
import os
import sqlite3
# Ensure the bot directory is in the path for local imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) 

from log_updated import log_event, setup_log_events
from gacha_updated import GachaSystem
import discord
from discord.ext import commands
import aiohttp
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Configuration
TOKEN = os.getenv("TOKEN")
STATUS_URL = os.getenv("DASHBOARD_URL", "http://localhost:8000/status")
GACHA_CHANNEL_ID = 1356600375238594610 
RESULT_CHANNEL_ID = 1356600474857377904

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Register high-detail events from log_updated
setup_log_events(bot)

# Message buffer for sending to dashboard
pending_messages = []

async def heartbeat():
    """Background task to notify dashboard that bot is alive and fetch commands."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Send pending messages to dashboard
                global pending_messages
                messages_to_send = list(pending_messages)
                pending_messages = []
                
                async with session.post(
                    STATUS_URL, 
                    json={"messages": messages_to_send}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        commands = data.get("commands", [])
                        
                        for cmd in commands:
                            action = cmd.get("action")
                            
                            if action == "SEND_EMBED":
                                try:
                                    payload = cmd["payload"]
                                    channel_id = int(cmd["channel_id"])
                                    channel = bot.get_channel(channel_id)
                                    
                                    if not channel:
                                        try:
                                            channel = await bot.fetch_channel(channel_id)
                                        except:
                                            pass
                                    
                                    if channel:
                                        embed = discord.Embed(
                                            title=payload.get("title"),
                                            description=payload.get("description"),
                                            color=discord.Color(payload.get("color", 0x6366f1))
                                        )
                                        
                                        if payload.get("author_name"):
                                            embed.set_author(name=payload["author_name"], icon_url=payload.get("author_icon"))

                                        if payload.get("thumbnail"):
                                            embed.set_thumbnail(url=payload["thumbnail"])

                                        if payload.get("image"):
                                            embed.set_image(url=payload["image"])
                                            
                                        if payload.get("footer"):
                                            embed.set_footer(text=payload["footer"])
                                            
                                        await channel.send(embed=embed)
                                    else:
                                        print(f"[Dashboard Error] Channel {channel_id} not found/cached.")
                                except Exception as e:
                                    print(f"[Dashboard Error] Failed to execute SEND_EMBED: {e}")

                            elif action == "SEND_VERIFY_PANEL":
                                try:
                                    payload = cmd["payload"]
                                    channel_id = int(cmd["channel_id"])
                                    channel = bot.get_channel(channel_id)
                                    if not channel:
                                        try: channel = await bot.fetch_channel(channel_id)
                                        except: pass
                                    
                                    if channel:
                                        embed = discord.Embed(
                                            title=payload.get("title"),
                                            description=payload.get("description"),
                                            color=discord.Color(payload.get("color", 0x10b981))
                                        )
                                        
                                        view = discord.ui.View(timeout=None)
                                        button = discord.ui.Button(
                                            label=payload.get("button_label", "Verify"),
                                            style=discord.ButtonStyle.green,
                                            custom_id="verify_me"
                                        )
                                        view.add_item(button)
                                        
                                        await channel.send(embed=embed, view=view)
                                    else:
                                        print(f"[Dashboard Error] Channel {channel_id} not found.")
                                except Exception as e:
                                    print(f"[Dashboard Error] Failed to execute SEND_VERIFY_PANEL: {e}")
                            
                            elif action == "SEND_MESSAGE":
                                try:
                                    payload = cmd["payload"]
                                    channel_id = int(cmd["channel_id"])
                                    channel = bot.get_channel(channel_id)
                                    
                                    if not channel:
                                        try:
                                            channel = await bot.fetch_channel(channel_id)
                                        except:
                                            pass
                                    
                                    if channel:
                                        content = payload.get("content", "")
                                        image_url = payload.get("image_url")
                                        reply_to_id = payload.get("reply_to_id")
                                        
                                        reference = None
                                        if reply_to_id:
                                            try:
                                                reference = discord.MessageReference(
                                                    message_id=int(reply_to_id),
                                                    channel_id=channel_id
                                                )
                                            except:
                                                pass
                                        
                                        if image_url:
                                            embed = discord.Embed()
                                            embed.set_image(url=image_url)
                                            if content:
                                                await channel.send(content=content, embed=embed, reference=reference)
                                            else:
                                                await channel.send(embed=embed, reference=reference)
                                        elif content:
                                            await channel.send(content=content, reference=reference)
                                    else:
                                        print(f"[Dashboard Error] Channel {channel_id} not found.")
                                except Exception as e:
                                    print(f"[Dashboard Error] Failed to execute SEND_MESSAGE: {e}")

                            elif action == "KICK_MEMBER":
                                try:
                                    payload = cmd["payload"]
                                    guild_id = payload.get("guild_id")
                                    user_id = int(payload["user_id"])
                                    reason = payload.get("reason", "Admin Action")
                                    
                                    guild = bot.get_guild(int(guild_id)) if guild_id else interaction.guild # Fallback might fail if no interaction context
                                    # Better: Use fetch_guild if ID provided, or iterate
                                    if not guild and guild_id:
                                         try: guild = await bot.fetch_guild(int(guild_id))
                                         except: pass
                                    
                                    if guild:
                                        mem = guild.get_member(user_id)
                                        if not mem: mem = await guild.fetch_member(user_id)
                                        
                                        if mem:
                                            await mem.kick(reason=reason)
                                            print(f"[Action] Kicked {mem.name}")
                                    else:
                                        print("[Action Error] Guild not found for kick")
                                except Exception as e:
                                    print(f"[Action Error] Kick failed: {e}")

                            elif action == "BAN_MEMBER":
                                try:
                                    payload = cmd["payload"]
                                    guild_id = payload.get("guild_id")
                                    user_id = int(payload["user_id"])
                                    reason = payload.get("reason", "Admin Action")
                                    
                                    guild = bot.get_guild(int(guild_id)) if guild_id else None
                                    if guild:
                                        # Ban supports user_id even if not member
                                        user_obj = discord.Object(id=user_id)
                                        await guild.ban(user_obj, reason=reason)
                                        print(f"[Action] Banned {user_id}")
                                except Exception as e:
                                    print(f"[Action Error] Ban failed: {e}")
                                    
        except Exception as e:
            print(f"[Heartbeat Error] {e}")
        await asyncio.sleep(3)

@bot.event
async def on_ready():
    print(f'>>> Logged in as {bot.user.name}')
    print('>>> Audit Log System Ready.')
    print('>>> Chat Dashboard Integration Active.')
    
    try:
        synced = await bot.tree.sync()
        print(f'>>> Synced {len(synced)} slash command(s)')
    except Exception as e:
        print(f'>>> Failed to sync commands: {e}')
    
    bot.loop.create_task(heartbeat())

@bot.event
async def on_message(message):
    """Capture messages and process commands."""
    
    if not message.author.bot: 
        global pending_messages
        attachments = [att.url for att in message.attachments] if message.attachments else []
        
        msg_data = {
            "channel_id": str(message.channel.id),
            "message_id": str(message.id),
            "author_id": str(message.author.id),
            "author_name": message.author.display_name,
            "author_username": message.author.name,
            "author_avatar": str(message.author.display_avatar.url) if message.author.display_avatar else None,
            "content": message.content,
            "attachments": attachments,
            "timestamp": message.created_at.isoformat(),
            "is_bot": message.author.bot
        }
        
        pending_messages.append(msg_data)
        if len(pending_messages) > 200:
            pending_messages = pending_messages[-100:]

    if message.author.bot: return
    await bot.process_commands(message)

# --- Admin Controls for Testing ---
@bot.command(name="addtix")
@commands.has_permissions(administrator=True)
async def add_tickets(ctx, member: discord.Member, amount: int):
    from gacha_updated import GACHA_DB
    import sqlite3
    conn = sqlite3.connect(GACHA_DB)
    conn.execute("UPDATE users SET tickets = tickets + ? WHERE user_id = ?", (amount, str(member.id)))
    conn.commit()
    conn.close()
    await ctx.send(f"✅ Added {amount} tickets to {member.mention}")

@bot.command(name="addsalt")
@commands.has_permissions(administrator=True)
async def add_salt(ctx, member: discord.Member, amount: int):
    from gacha_updated import GACHA_DB
    import sqlite3
    conn = sqlite3.connect(GACHA_DB)
    conn.execute("UPDATE users SET salt = salt + ? WHERE user_id = ?", (amount, str(member.id)))
    conn.commit()
    conn.close()
    await ctx.send(f"✅ Added {amount} salt to {member.mention}")

def get_discord_color(hex_color):
    try:
        return discord.Color(int(hex_color.lstrip('#'), 16))
    except:
        return discord.Color.blue()

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.data or "custom_id" not in interaction.data: return
    custom_id = interaction.data["custom_id"]
    
    # Verification Button
    if custom_id == "verify_me":
        from gacha_updated import GACHA_DB
        import sqlite3
        conn = sqlite3.connect(GACHA_DB)
        row = conn.execute("SELECT role_id FROM verification_config LIMIT 1").fetchone()
        conn.close()
        
        if row and row[0]:
             try:
                 role_id = int(row[0])
                 role = interaction.guild.get_role(role_id)
                 if role:
                     await interaction.user.add_roles(role)
                     await interaction.response.send_message("✅ You have been verified!", ephemeral=True)
                 else:
                     await interaction.response.send_message("❌ Verification role not found. Please contact admin.", ephemeral=True)
             except Exception as e:
                 await interaction.response.send_message(f"❌ Error during verification: {e}", ephemeral=True)
        else:
             await interaction.response.send_message("❌ Verification not configured.", ephemeral=True)
        return
    
    # Gacha related interactions
    gacha_ids = ["gacha_1", "gacha_10", "gacha_salt", "check_tickets"]
    if custom_id not in gacha_ids: return

    # Channel Restriction (optional, can be improved with DB check)
    if interaction.channel_id != GACHA_CHANNEL_ID:
        await interaction.response.send_message(f"❌ This command is only allowed in <#{GACHA_CHANNEL_ID}>", ephemeral=True)
        return

    user_id = interaction.user.id
    await interaction.response.defer(ephemeral=True)

    if custom_id == "gacha_1":
        stats = GachaSystem.get_stats(user_id)
        if stats["tickets"] < 1:
            return await interaction.followup.send("❌ You don't have enough tickets!", ephemeral=True)
        
        # Deduct ticket
        from gacha_updated import GACHA_DB
        import sqlite3
        conn = sqlite3.connect(GACHA_DB)
        conn.execute("UPDATE users SET tickets = tickets - 1 WHERE user_id = ?", (str(user_id),))
        conn.commit()
        conn.close()

        results = await GachaSystem.pull(user_id, count=1)
        rank, reward_id, embed_data = results[0]
        
        # Build customizable embed
        embed = discord.Embed(
            title=embed_data['title'].replace("{user}", interaction.user.display_name),
            description=embed_data['description'].replace("{user}", interaction.user.mention),
            color=get_discord_color(embed_data['color'])
        )
        if embed_data['image']: embed.set_image(url=embed_data['image'])
        if embed_data['thumbnail']: embed.set_thumbnail(url=embed_data['thumbnail'])
        if embed_data['footer']: embed.set_footer(text=embed_data['footer'])
        
        if reward_id:
            embed.add_field(name="Reward", value=f"You received <@&{reward_id}>!")
            # Add role to user
            try:
                role = interaction.guild.get_role(int(reward_id))
                if role: await interaction.user.add_roles(role)
            except: pass
        elif rank == "Salt":
             embed.add_field(name="Result", value="Got Salt 🧂 (+1)")

        res_channel = bot.get_channel(RESULT_CHANNEL_ID)
        if res_channel: await res_channel.send(content=interaction.user.mention, embed=embed)
        await interaction.followup.send("✅ Gacha pulled! Check the result channel.", ephemeral=True)

    elif custom_id == "gacha_10":
        stats = GachaSystem.get_stats(user_id)
        if stats["tickets"] < 10:
            return await interaction.followup.send("❌ You need 10 tickets for a 10x pull!", ephemeral=True)
        
        from gacha_updated import GACHA_DB
        import sqlite3
        conn = sqlite3.connect(GACHA_DB)
        conn.execute("UPDATE users SET tickets = tickets - 10 WHERE user_id = ?", (str(user_id),))
        conn.commit()
        conn.close()

        results = await GachaSystem.pull(user_id, count=10)
        
        res_channel = bot.get_channel(RESULT_CHANNEL_ID)
        await interaction.followup.send("✅ Gacha 10x pulled! Results are being sent to the result channel.", ephemeral=True)

        for rank, reward_id, embed_data in results:
            embed = discord.Embed(
                title=embed_data['title'].replace("{user}", interaction.user.display_name),
                description=embed_data['description'].replace("{user}", interaction.user.mention),
                color=get_discord_color(embed_data['color'])
            )
            if embed_data['image']: embed.set_image(url=embed_data['image'])
            if embed_data['thumbnail']: embed.set_thumbnail(url=embed_data['thumbnail'])
            if embed_data['footer']: embed.set_footer(text=embed_data['footer'])
            
            if reward_id:
                embed.add_field(name="Reward", value=f"You received <@&{reward_id}>!")
                try:
                    role = interaction.guild.get_role(int(reward_id))
                    if role: await interaction.user.add_roles(role)
                except: pass
            elif rank == "Salt":
                 embed.add_field(name="Result", value="Got Salt 🧂 (+1)")
            
            if res_channel: await res_channel.send(embed=embed)
            await asyncio.sleep(1) # Small delay to avoid rate limits and make it feel sequential

    elif custom_id == "gacha_salt":
        from gacha_updated import GachaSystem
        success = await GachaSystem.exchange_salt(user_id) # Need to implement in gacha_updated
        if success:
            await interaction.followup.send("✅ Exchanged 10 Salt for 1 Ticket!", ephemeral=True)
        else:
            await interaction.followup.send("❌ Not enough salt (need 10).", ephemeral=True)

    elif custom_id == "check_tickets":
        stats = GachaSystem.get_stats(user_id)
        await interaction.followup.send(f"🎟️ Tickets: {stats['tickets']} | 🧂 Salt: {stats['salt']}", ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)
