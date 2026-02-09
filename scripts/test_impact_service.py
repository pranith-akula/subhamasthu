"""Test ImpactService locally."""
import asyncio
from app.services.impact_service import ImpactService
from app.database import get_db_context


async def test():
    async with get_db_context() as db:
        service = ImpactService(db)
        
        print("Testing get_global_impact...")
        try:
            result = await service.get_global_impact(use_cache=False)
            print(f"SUCCESS: {result}")
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test())
