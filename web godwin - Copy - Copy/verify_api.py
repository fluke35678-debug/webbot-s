import requests
import json

BASE_URL = "http://localhost:8000"

def check(endpoint):
    print(f"--- Checking {endpoint} ---")
    try:
        res = requests.get(f"{BASE_URL}{endpoint}")
        print(f"Status: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            print(json.dumps(data, indent=2))
            return data
        else:
            print(f"Error: {res.text}")
    except Exception as e:
        print(f"Exception: {e}")

check("/api/eco/config")
check("/api/eco/jobs")
