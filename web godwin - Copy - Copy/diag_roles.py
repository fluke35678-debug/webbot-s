import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def diag():
    token = os.getenv("TOKEN")
    if not token:
        print("NO TOKEN FOUND IN .ENV")
        return

    with open("c:/test/diag_output.txt", "w", encoding="utf-8") as f:
        f.write(f"Using Token: {token[:10]}...\n")
        headers = {"Authorization": f"Bot {token}"}
        
        async with httpx.AsyncClient() as client:
            try:
                # 1. Check Bot Info
                me_res = await client.get("https://discord.com/api/v10/users/@me", headers=headers)
                f.write(f"Bot Info: {me_res.status_code} - {me_res.text}\n")
                
                # 2. Check Guilds
                guilds_res = await client.get("https://discord.com/api/v10/users/@me/guilds", headers=headers)
                f.write(f"Guilds Status: {guilds_res.status_code}\n")
                if guilds_res.status_code == 200:
                    guilds = guilds_res.json()
                    f.write(f"Bot is in {len(guilds)} guilds.\n")
                    for g in guilds:
                        f.write(f" - Guild: {g['name']} ({g['id']})\n")
                        
                        # 3. Check Roles for each guild
                        roles_res = await client.get(f"https://discord.com/api/v10/guilds/{g['id']}/roles", headers=headers)
                        if roles_res.status_code == 200:
                            roles = roles_res.json()
                            f.write(f"   Found {len(roles)} roles.\n")
                            for r in roles:
                                f.write(f"     * {r['name']} ({r['id']})\n")
                        else:
                            f.write(f"   FAILED to get roles for guild {g['id']}: {roles_res.status_code} - {roles_res.text}\n")
                else:
                    f.write(f"FAILED to get guilds: {guilds_res.status_code} - {guilds_res.text}\n")
                    
            except Exception as e:
                f.write(f"CRITICAL ERROR: {e}\n")

if __name__ == "__main__":
    asyncio.run(diag())
