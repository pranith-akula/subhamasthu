import asyncio
import json
from app.database import async_session_maker
from app.api.admin.dashboard import get_dashboard_stats

async def final_verify():
    async with async_session_maker() as db:
        res = await get_dashboard_stats(db=db, admin_key="mock")
        print("JSON STRUCTURE CHECK:")
        print(f"Revenue: {res.get('revenue')}")
        print(f"Stats States Type: {type(res['business']['distribution']['states'])}")
        print(f"First State Item: {res['business']['distribution']['states'][0] if res['business']['distribution']['states'] else 'EMPTY'}")
        
        # Check if DAILY_PASSIVE and COOLDOWN are in the list
        state_names = [s['state'] for s in res['business']['distribution']['states']]
        print(f"State Names in List: {state_names}")
        
        if 'DAILY_PASSIVE' in state_names and 'COOLDOWN' in state_names:
            print("VERIFICATION SUCCESS: All states present in list format.")
        else:
            print("VERIFICATION FAILED: Missing states in list format.")

if __name__ == "__main__":
    asyncio.run(final_verify())
