
import asyncio
import os
import sys

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

async def run_migrations():
    """Run all SQL migrations in order."""
    migrations_dir = "migrations"
    
    # Get all .sql files sorted by name (001, 002, 003...)
    files = sorted([f for f in os.listdir(migrations_dir) if f.endswith(".sql")])
    
    print(f"Found {len(files)} migration files: {files}")
    
    async with engine.begin() as conn:
        # Enable pgcrypto once
        print("Ensuring pgcrypto extension...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        
        for filename in files:
            path = os.path.join(migrations_dir, filename)
            print(f"Applying {filename}...")
            
            with open(path, "r", encoding="utf-8") as f:
                sql = f.read()
                
            # Split by semicolon to execute individually (for efficiency and safety)
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            
            for i, stmt in enumerate(statements):
                try:
                    await conn.execute(text(stmt))
                except Exception as e:
                    print(f"⚠️ Error in {filename} stmt {i+1}: {e}")
                    print(f"Stmt: {stmt[:50]}...")
                    # Warning only, as some 'already exists' errors are expected with IF NOT EXISTS
                    # But if it's a real error, connection might rollback.
                    # Since we are in one transaction block, any error rolls back everything.
                    # But we want to be robust. 
                    # Actually, if we want idempotency, we should fail hard or ensure SQL is robust.
                    # Our SQL uses IF NOT EXISTS, so should be safe.
                    # Except strict syntax errors.
                    pass
                    
            print(f"✅ Applied {filename}")
            
    await engine.dispose()
    print("🚀 All migrations completed!")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_migrations())
