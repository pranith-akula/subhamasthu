"""
Fix ritual_events metadata column name (reserved in SQLAlchemy).
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

# Check if ritual_events table exists and has metadata column
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'ritual_events' AND column_name = 'metadata'
""")
if cur.fetchone():
    print("Renaming metadata column to event_data...")
    cur.execute("ALTER TABLE ritual_events RENAME COLUMN metadata TO event_data")
    print("  Renamed: metadata -> event_data")
else:
    # Check if event_data already exists
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'ritual_events' AND column_name = 'event_data'
    """)
    if cur.fetchone():
        print("event_data column already exists!")
    else:
        print("Neither metadata nor event_data column found - table may not exist yet")

cur.close()
conn.close()

print("\nColumn rename complete!")
