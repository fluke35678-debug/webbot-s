import httpx
import asyncio

async def check_token(token: str):
    """
    Checks a Discord token's validity and properties.
    Returns a dictionary with status details.
    """
    token = token.strip()
    if not token:
        return {"valid": False, "reason": "Empty Token"}

    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("https://discord.com/api/v9/users/@me", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check Verification
                email_verified = data.get("verified", False)
                phone_verified = data.get("phone") is not None
                
                # Check Nitro
                premium_type = data.get("premium_type", 0)
                nitro_status = "None"
                if premium_type == 1:
                    nitro_status = "Nitro Classic"
                elif premium_type == 2:
                    nitro_status = "Nitro"
                elif premium_type == 3:
                    nitro_status = "Nitro Basic"

                # Check Flags (optional, for more detailed debug)
                flags = data.get("flags", 0)

                return {
                    "valid": True,
                    "token": token,
                    "id": data.get("id"),
                    "username": data.get("username"),
                    "discriminator": data.get("discriminator"),
                    "email": data.get("email"),
                    "phone": data.get("phone"),
                    "verified": email_verified,
                    "phone_verified": phone_verified,
                    "nitro": nitro_status,
                    "avatar_url": f"https://cdn.discordapp.com/avatars/{data.get('id')}/{data.get('avatar')}.png" if data.get('avatar') else None
                }
            
            elif response.status_code == 401 or response.status_code == 403:
                return {"valid": False, "token": token, "reason": "Invalid or Locked"}
            
            elif response.status_code == 429:
                return {"valid": False, "token": token, "reason": "Rate Limited"}
            
            else:
                return {"valid": False, "token": token, "reason": f"HTTP Error {response.status_code}"}

    except Exception as e:
        return {"valid": False, "token": token, "reason": f"Connection Error: {str(e)}"}
