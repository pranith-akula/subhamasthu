
import asyncio
from sqlalchemy import text
from app.database import engine

async def repair_schema():
    async with engine.begin() as conn:
        print("Checking/Repairing Schema...")
        
        # 1. Check Users Columns
        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'users';"
        ))
        columns = [row[0] for row in result.fetchall()]
        
        if 'dob' not in columns:
            print("Adding 'dob' column...")
            await conn.execute(text("ALTER TABLE users ADD COLUMN dob DATE"))
            
        if 'wedding_anniversary' not in columns:
            print("Adding 'wedding_anniversary' column...")
            await conn.execute(text("ALTER TABLE users ADD COLUMN wedding_anniversary DATE"))
            
        # 2. Check Temples Table
        result = await conn.execute(text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'temples';"
        ))
        if not result.scalar():
            print("Creating 'temples' table...")
            await conn.execute(text("""
                CREATE TABLE temples (
                    id UUID NOT NULL DEFAULT gen_random_uuid(), 
                    name VARCHAR(200) NOT NULL, 
                    name_telugu VARCHAR(200), 
                    location VARCHAR(200), 
                    city VARCHAR(100) DEFAULT 'Hyderabad', 
                    deity VARCHAR(100), 
                    photo_url VARCHAR(500), 
                    google_maps_url VARCHAR(500), 
                    is_active BOOLEAN DEFAULT true, 
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
                    PRIMARY KEY (id)
                );
            """))
            await conn.execute(text("CREATE INDEX idx_temples_deity ON temples (deity)"))
            await conn.execute(text("CREATE INDEX idx_temples_city ON temples (city)"))
            await conn.execute(text("CREATE INDEX idx_temples_active ON temples (is_active)"))
        else:
            print("'temples' table exists.")

    print("Schema Repair Complete.")

if __name__ == "__main__":
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    asyncio.run(repair_schema())
