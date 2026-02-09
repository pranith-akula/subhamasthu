"""
Apply follow-up columns migration using sync psycopg2.
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

# Check if follow_up_day column already exists
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'sankalps' AND column_name = 'follow_up_day'
""")
if cur.fetchone():
    print("Follow-up columns already exist!")
else:
    print("Adding follow-up columns to sankalps table...")
    
    try:
        cur.execute("ALTER TABLE sankalps ADD COLUMN follow_up_day INT DEFAULT 0 NOT NULL")
        print("  Added: follow_up_day")
    except psycopg2.errors.DuplicateColumn:
        print("  Exists: follow_up_day")
        conn.rollback()
        conn.autocommit = True
    
    try:
        cur.execute("ALTER TABLE sankalps ADD COLUMN next_follow_up_at TIMESTAMP WITH TIME ZONE")
        print("  Added: next_follow_up_at")
    except psycopg2.errors.DuplicateColumn:
        print("  Exists: next_follow_up_at")
        conn.rollback()
        conn.autocommit = True
    
    try:
        cur.execute("CREATE INDEX ix_sankalps_next_follow_up_at ON sankalps(next_follow_up_at)")
        print("  Created index: ix_sankalps_next_follow_up_at")
    except:
        print("  Index already exists")
        conn.rollback()
        conn.autocommit = True

cur.close()
conn.close()

print("\nFollow-up columns migration complete!")
