"""
Create a test SevaExecution record and trigger weekly summary.
"""
import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

# Connect to database
db_url = os.getenv("DATABASE_URL").replace("postgresql+asyncpg://", "postgresql://")
conn = psycopg2.connect(db_url)
conn.autocommit = True
cur = conn.cursor()

# Get a paid sankalp to link to
cur.execute("""
    SELECT s.id, s.user_id, s.tier, u.phone 
    FROM sankalps s 
    JOIN users u ON s.user_id = u.id
    WHERE s.status IN ('PAID', 'RECEIPT_SENT', 'CLOSED')
    ORDER BY s.created_at DESC 
    LIMIT 1
""")
sankalp = cur.fetchone()

if not sankalp:
    print("No paid sankalps found. Creating a dummy test...")
    # Get any user
    cur.execute("SELECT id, phone FROM users LIMIT 1")
    user = cur.fetchone()
    if not user:
        print("ERROR: No users in database")
        exit(1)
    
    # Create a test sankalp
    cur.execute("""
        INSERT INTO sankalps (id, user_id, category, tier, amount, currency, status, created_at, updated_at)
        VALUES (gen_random_uuid(), %s, 'KUTUMBA_KSHEMAM', 'TIER_S30', 51.00, 'USD', 'PAID', NOW(), NOW())
        RETURNING id
    """, (user[0],))
    sankalp_id = cur.fetchone()[0]
    user_phone = user[1]
    tier = 'TIER_S30'
else:
    sankalp_id = sankalp[0]
    user_phone = sankalp[3]
    tier = sankalp[2]

# Get a temple
cur.execute("SELECT id, name, city FROM temples LIMIT 1")
temple = cur.fetchone()
temple_id = temple[0] if temple else None
temple_name = temple[1] if temple else "Test Temple"
temple_city = temple[2] if temple else "Vijayawada"

# Map tier to meals
tier_meals = {
    'TIER_S15': 10,
    'TIER_S30': 25,
    'TIER_S81': 40,
    'TIER_S50': 50,
}
meals = tier_meals.get(tier, 25)

# Create SevaExecution record
cur.execute("""
    INSERT INTO seva_executions (
        id, sankalp_id, temple_id, meals_served, status, 
        executed_at, verified_at, photo_url, verified_by, notes, created_at, updated_at
    )
    VALUES (
        gen_random_uuid(), %s, %s, %s, 'verified',
        NOW(), NOW(), 'https://example.com/test-photo.jpg', 'Test Admin', 'Test seva execution', NOW(), NOW()
    )
    RETURNING id
""", (sankalp_id, temple_id, meals))

seva_id = cur.fetchone()[0]
print(f"SUCCESS: Created SevaExecution record:")
print(f"   ID: {seva_id}")
print(f"   Meals: {meals}")
print(f"   Temple: {temple_name} ({temple_city})")
print(f"   User Phone: {user_phone}")

cur.close()
conn.close()

print(f"\nCheck API: https://web-production-b998a.up.railway.app/api/impact")
print(f"User phone for weekly summary: {user_phone}")
