import asyncio
from app.database import async_session_maker
from app.models.user import User
from sqlalchemy import select

async def dump_states():
    async with async_session_maker() as db:
        res = await db.execute(select(User.phone, User.state))
        print("DATABASE DUMP:")
        for r in res.all():
            print(f"Phone: {r[0]}, State: {r[1]}")

if __name__ == "__main__":
    asyncio.run(dump_states())
