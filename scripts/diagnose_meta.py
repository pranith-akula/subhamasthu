import asyncio
import os
import httpx
from dotenv import load_dotenv

# Load .env
load_dotenv()

async def check_meta_creds():
    token = os.getenv("META_ACCESS_TOKEN")
    phone_id = os.getenv("META_PHONE_NUMBER_ID")
    
    print(f"Checking Credentials...")
    print(f"TOKEN provided: {'Yes' if token else 'NO'}")
    print(f"PHONE_ID provided: {'Yes' if phone_id else 'NO'}")
    
    if not token or not phone_id:
        print("❌ Missing Credentials in environment.")
        return
        
    url = f"https://graph.facebook.com/v18.0/{phone_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        try:
            print(f"Connecting to Meta API: {url}...")
            response = await client.get(url, headers=headers)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("[SUCCESS] Credentials Valid!")
                print(f"Phone Name: {data.get('verified_name')}")
                print(f"Display Phone Number: {data.get('display_phone_number')}")
                print(f"Quality Rating: {data.get('quality_rating')}")
            else:
                print("[ERROR] API Error:")
                print(response.text)
                
        except Exception as e:
            print(f"[ERROR] Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(check_meta_creds())
