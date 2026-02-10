import asyncio
from app.database import async_session_maker
from app.api.admin.dashboard import get_dashboard_stats
from app.fsm.states import SankalpStatus

async def verify_hardcore_sync():
    print("Verifying Hardcore Data Integrity...")
    async with async_session_maker() as db:
        # We call the function directly (dependency injection mock)
        stats = await get_dashboard_stats(db=db, admin_key="mock")
        
        # 1. Verify Recent Cashflow is strictly confirmed
        recent = stats.get("recent_sankalps", [])
        paid_statuses = [SankalpStatus.PAID, SankalpStatus.RECEIPT_SENT, SankalpStatus.CLOSED]
        
        invalid_items = [item for item in recent if item["status"] not in paid_statuses]
        
        if invalid_items:
            print(f"FAILED: Found {len(invalid_items)} pending items in cashflow!")
            for item in invalid_items:
                print(f" - ID: {item['id']}, Status: {item['status']}")
        else:
            print("SUCCESS: Recent Cashflow is 100% confirmed payments.")

        # 2. Verify State Sequence
        states = list(stats["business"]["distribution"]["states"].keys())
        print(f"Pipeline Sequence: {states[:5]} ...")
        
        if states[0] == "NEW" and "ONBOARDED" in states:
            print("SUCCESS: Pipeline is logically sequenced.")
        else:
            print("WARNING: Pipeline sequence might be unexpected.")

        # 3. Verify Sync Metadata
        if stats.get("debug", {}).get("now"):
            print(f"SUCCESS: Sync timestamp found: {stats['debug']['now']}")

if __name__ == "__main__":
    asyncio.run(verify_hardcore_sync())
