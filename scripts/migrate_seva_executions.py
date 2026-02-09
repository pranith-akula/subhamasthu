"""
Migrate seva_executions table manually.
Run this if Alembic migration fails due to partial state.
"""
import asyncio
from app.database import get_db_context
from sqlalchemy import text


async def migrate():
    async with get_db_context() as db:
        # Check if table exists
        result = await db.execute(text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'seva_executions'"
        ))
        if result.fetchone():
            print("seva_executions table already exists!")
            return
        
        # Create table
        await db.execute(text("""
            CREATE TABLE seva_executions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                sankalp_id UUID NOT NULL REFERENCES sankalps(id) ON DELETE CASCADE,
                temple_id UUID REFERENCES temples(id) ON DELETE SET NULL,
                meals_served INTEGER NOT NULL DEFAULT 0,
                status seva_execution_status NOT NULL DEFAULT 'pending',
                executed_at TIMESTAMP WITH TIME ZONE,
                verified_at TIMESTAMP WITH TIME ZONE,
                photo_url TEXT,
                verified_by VARCHAR(100),
                notes TEXT,
                batch_id VARCHAR(100),
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """))
        
        # Create indexes
        await db.execute(text(
            "CREATE INDEX ix_seva_executions_sankalp_id ON seva_executions(sankalp_id)"
        ))
        await db.execute(text(
            "CREATE INDEX ix_seva_executions_temple_id ON seva_executions(temple_id)"
        ))
        await db.execute(text(
            "CREATE INDEX ix_seva_executions_batch_id ON seva_executions(batch_id)"
        ))
        
        await db.commit()
        print("seva_executions table created successfully!")


if __name__ == "__main__":
    asyncio.run(migrate())
