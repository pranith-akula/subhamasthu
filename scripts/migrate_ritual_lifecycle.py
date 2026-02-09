"""
Apply ritual lifecycle migration using sync psycopg2.
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Connect to database
db_url = os.getenv("DATABASE_URL").replace("postgresql+asyncpg://", "postgresql://")
conn = psycopg2.connect(db_url)
conn.autocommit = True
cur = conn.cursor()

# Check if ritual_cycle_day column already exists
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'users' AND column_name = 'ritual_cycle_day'
""")
if cur.fetchone():
    print("Ritual columns already exist!")
else:
    print("Adding ritual columns to users table...")
    
    # Add columns one by one (some may already exist from previous runs)
    columns = [
        ("ritual_cycle_day", "INT DEFAULT 1 NOT NULL"),
        ("ritual_cycle_started_at", "TIMESTAMP WITH TIME ZONE"),
        ("last_sankalp_prompt_at", "TIMESTAMP WITH TIME ZONE"),
        ("ritual_phase", "VARCHAR(20) DEFAULT 'INITIATION' NOT NULL"),
        ("ritual_intensity_score", "INT DEFAULT 0 NOT NULL"),
        ("last_chinta_category", "VARCHAR(50)"),
        ("sankalp_prompts_this_month", "INT DEFAULT 0 NOT NULL"),
    ]
    
    for col_name, col_def in columns:
        try:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
            print(f"  Added: {col_name}")
        except psycopg2.errors.DuplicateColumn:
            print(f"  Exists: {col_name}")
            conn.rollback()
            conn.autocommit = True

# Create ritual_events table
cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'ritual_events'")
if cur.fetchone():
    print("ritual_events table already exists!")
else:
    print("Creating ritual_events table...")
    cur.execute("""
        CREATE TABLE ritual_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            event_type VARCHAR(50) NOT NULL,
            ritual_phase VARCHAR(20),
            conversion_flag BOOLEAN DEFAULT FALSE NOT NULL,
            metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
        )
    """)
    cur.execute("CREATE INDEX ix_ritual_events_user_id ON ritual_events(user_id)")
    cur.execute("CREATE INDEX ix_ritual_events_event_type ON ritual_events(event_type)")
    cur.execute("CREATE INDEX ix_ritual_events_created_at ON ritual_events(created_at)")
    print("SUCCESS: ritual_events table created!")

cur.close()
conn.close()

print("\nRitual lifecycle migration complete!")
