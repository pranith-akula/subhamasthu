
import asyncio
import os
import sys

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

async def run_migration():
    print("Connecting to DB...")
    async with engine.begin() as conn:
        with open("migrations/003_seva_media.sql", "r", encoding="utf-8") as f:
            sql = f.read()
            
            # Split by semicolon to execute individually
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            
            print(f"Running {len(statements)} migration statements...")
            
            # Ensure pgcrypto for UUID generation
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            
            for stmt in statements:
                print(f"Executing: {stmt[:50]}...")
                await conn.execute(text(stmt))
                
            print("Mutation complete!")
            
    await engine.dispose()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_migration())
