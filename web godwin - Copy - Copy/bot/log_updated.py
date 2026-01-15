import sqlite3
import datetime
import json
import discord
from discord.ext import commands
import pytz
import asyncio

import os
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'audit_logs.db')
TZ_TH = pytz.timezone('Asia/Bangkok')

DEST_LOG_CHANNELS = {
    "voice": 1451493817386537042,
    "message": 1451493892812832860,
    "moderation": 1451493978976419953,
    "member": 1451494074229063680,
    "server": 1451494193490038875,
    "muteordeaf": 1451513234921226300
}

async def log_event(event_type, executor, target, details, category="GENERAL", guild_id=None):
    """Saves an event with category to the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        detail_str = json.dumps(details) if isinstance(details, (dict, list)) else str(details)
        cursor.execute('''
            INSERT INTO audit_logs (event_type, executor, target, details, category, timestamp, guild_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (event_type, str(executor), str(target), detail_str, category, datetime.datetime.now(), str(guild_id) if guild_id else None))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Log Error] {e}")

async def send_to_dest(bot, category, embed):
    channel_id = DEST_LOG_CHANNELS.get(category)
    if channel_id:
        channel = bot.get_channel(channel_id)
        if channel: await channel.send(embed=embed)

async def get_audit_log_user(member, action_type):
    if member.guild.me.guild_permissions.view_audit_log:
        try:
            async for entry in member.guild.audit_logs(limit=1, action=action_type):
                if entry.target and entry.target.id == member.id: return str(entry.user.id)
        except: pass
    return "Unknown"

def setup_log_events(bot):
    @bot.event
    async def on_member_update(before, after):
        if before.roles != after.roles:
            await asyncio.sleep(1.5)
            executor = await get_audit_log_user(after, discord.AuditLogAction.member_role_update)
            added = [r for r in after.roles if r not in before.roles]
            removed = [r for r in before.roles if r not in after.roles]
            if added or removed:
                details = {"added": [r.name for r in added], "removed": [r.name for r in removed]}
                await log_event("ROLE_UPDATE", executor, after.id, details, "MODERATION", guild_id=after.guild.id)

        if before.timed_out_until != after.timed_out_until:
            await asyncio.sleep(1)
            executor = await get_audit_log_user(after, discord.AuditLogAction.member_update)
            await log_event("TIMEOUT", executor, after.id, {"active": after.timed_out_until is not None}, "MODERATION", guild_id=after.guild.id)

    @bot.event
    async def on_guild_role_update(before, after):
        executor = await get_audit_log_user(after, discord.AuditLogAction.role_update)
        await log_event("GUILD_ROLE_UPDATE", executor, after.id, f"Role {after.name} modified", "SERVER", guild_id=after.guild.id)

    @bot.event
    async def on_message_delete(message):
        if message.author.bot: return
        await log_event("MESSAGE_DELETE", "User/Admin", message.author.id, {"content": message.content, "channel": message.channel.name}, "MESSAGES", guild_id=message.guild.id)

    @bot.event
    async def on_message_edit(before, after):
        if before.author.bot or before.content == after.content: return
        await log_event("MESSAGE_EDIT", before.author.id, before.author.id, {"before": before.content, "after": after.content}, "MESSAGES", guild_id=before.guild.id)

    @bot.event
    async def on_voice_state_update(member, before, after):
        if before.channel is None and after.channel:
            await log_event("VOICE_JOIN", member.id, after.channel.name, "Joined", "VOICE", guild_id=member.guild.id)
        elif before.channel and after.channel is None:
            await log_event("VOICE_LEAVE", member.id, before.channel.name, "Left", "VOICE", guild_id=member.guild.id)
        elif before.channel != after.channel:
            await log_event("VOICE_MOVE", member.id, f"{before.channel.name} -> {after.channel.name}", "Moved", "VOICE", guild_id=member.guild.id)

    @bot.event
    async def on_member_ban(guild, user):
        await log_event("BAN", "Moderator", user.id, "Banned from server", "MODERATION", guild_id=guild.id)

    @bot.event
    async def on_member_unban(guild, user):
        await log_event("UNBAN", "Moderator", user.id, "Unbanned", "MODERATION", guild_id=guild.id)

    @bot.event
    async def on_guild_channel_create(channel):
        await log_event("CHANNEL_CREATE", "Admin", channel.id, channel.name, "SERVER", guild_id=channel.guild.id)

    @bot.event
    async def on_guild_channel_delete(channel):
        await log_event("CHANNEL_DELETE", "Admin", channel.id, channel.name, "SERVER", guild_id=channel.guild.id)

async def send_to_mod(message):
    print(f"[ALERT] {message}")
