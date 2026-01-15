import httpx
import anyio

async def test_pagination():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Test Users page with pagination
        print("Testing /users?page=1")
        res = await client.get("/users?page=1")
        print(f"Status: {res.status_code}")
        
        # Test Search
        print("Testing /users?search=test")
        res = await client.get("/users?search=test")
        print(f"Status: {res.status_code}")
        
        # Test Logs pagination
        print("Testing /logs?page=1")
        res = await client.get("/logs?page=1")
        print(f"Status: {res.status_code}")

if __name__ == "__main__":
    try:
        anyio.run(test_pagination)
    except Exception as e:
        print(f"Verification failed: {e}")
