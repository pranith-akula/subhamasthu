"""
Apply devotional_cycle_number migration using sync psycopg2.
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

# Check if devotional_cycle_number column already exists
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'users' AND column_name = 'devotional_cycle_number'
""")
if cur.fetchone():
    print("devotional_cycle_number already exists!")
else:
    print("Adding devotional_cycle_number to users table...")
    cur.execute("ALTER TABLE users ADD COLUMN devotional_cycle_number INT DEFAULT 1 NOT NULL")
    print("  Added: devotional_cycle_number")

cur.close()
conn.close()

print("\nDevotional cycle migration complete!")
