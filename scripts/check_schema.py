
import asyncio
from sqlalchemy import text
from app.database import engine

async def check_schema():
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'users';"
        ))
        columns = [row[0] for row in result.fetchall()]
        print(f"Users columns: {columns}")
        
        missing = []
        if 'dob' not in columns:
            missing.append('dob')
        if 'wedding_anniversary' not in columns:
            missing.append('wedding_anniversary')
            
        if missing:
            print(f"MISSING COLUMNS: {missing}")
            # Optional: Add them manually if missing?
            # await conn.execute(text("ALTER TABLE users ADD COLUMN dob DATE"))
            # await conn.execute(text("ALTER TABLE users ADD COLUMN wedding_anniversary DATE"))
            # await conn.commit()
        else:
            print("ALL COLUMNS PRESENT.")

if __name__ == "__main__":
    import sys
    import os
    # Append project root explicitly
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    asyncio.run(check_schema())
