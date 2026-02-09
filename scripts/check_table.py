"""Check if seva_executions table exists."""
import asyncio
from app.database import get_db_context
from sqlalchemy import text


async def check():
    async with get_db_context() as db:
        # Table already confirmed missing, create it
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS seva_executions (
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
            "CREATE INDEX IF NOT EXISTS ix_seva_executions_sankalp_id ON seva_executions(sankalp_id)"
        ))
        await db.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_seva_executions_temple_id ON seva_executions(temple_id)"
        ))
        await db.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_seva_executions_batch_id ON seva_executions(batch_id)"
        ))
        
        await db.commit()
        print("SUCCESS: seva_executions table created!")


if __name__ == "__main__":
    asyncio.run(check())
