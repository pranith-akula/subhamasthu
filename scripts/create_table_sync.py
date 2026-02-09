"""Create seva_executions table using sync psycopg2."""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Convert async URL to sync
db_url = os.getenv("DATABASE_URL")
# postgresql+asyncpg://... -> postgresql://...
sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

conn = psycopg2.connect(sync_url)
conn.autocommit = True
cur = conn.cursor()

# Check if ENUM exists
cur.execute("SELECT 1 FROM pg_type WHERE typname = 'seva_execution_status'")
if not cur.fetchone():
    print("Creating ENUM type...")
    cur.execute("CREATE TYPE seva_execution_status AS ENUM ('pending', 'executed', 'verified')")
else:
    print("ENUM already exists")

# Check if table exists
cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'seva_executions'")
if cur.fetchone():
    print("seva_executions table already exists!")
else:
    # Create table
    cur.execute("""
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
    """)
    
    # Create indexes
    cur.execute("CREATE INDEX ix_seva_executions_sankalp_id ON seva_executions(sankalp_id)")
    cur.execute("CREATE INDEX ix_seva_executions_temple_id ON seva_executions(temple_id)")
    cur.execute("CREATE INDEX ix_seva_executions_batch_id ON seva_executions(batch_id)")
    
    print("SUCCESS: seva_executions table created!")

cur.close()
conn.close()
