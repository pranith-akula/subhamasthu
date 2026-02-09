"""
Trigger weekly impact summary for a specific user.
"""
import asyncio
from app.services.impact_service import ImpactService
from app.services.meta_whatsapp_service import MetaWhatsappService
from app.database import get_db_context


async def send_summary():
    async with get_db_context() as db:
        # Get impact data
        service = ImpactService(db)
        weekly = await service.get_weekly_summary_data()
        
        devotees = weekly["devotees"]
        meals = weekly["meals"]
        cities = weekly["cities"]
        
        print(f"Weekly data: {devotees} devotees, {meals} meals, {cities} cities")
        
        # Get personal impact for the user
        target_phone = "917680065131"  # The user's phone
        
        from app.services.user_service import UserService
        user_service = UserService(db)
        user = await user_service.get_or_create_user(target_phone)
        
        personal = await service.get_user_impact(user.id)
        personal_meals = personal["lifetime_meals"]
        
        print(f"Personal impact: {personal_meals} meals")
        
        # Send template message
        whatsapp = MetaWhatsappService()
        await whatsapp.send_template_message(
            phone=target_phone,
            template_id="weekly_impact_summary",
            params=[
                str(devotees),
                str(meals),
                str(cities),
                str(personal_meals),
            ]
        )
        print(f"SUCCESS: Weekly summary sent to {target_phone}")


if __name__ == "__main__":
    asyncio.run(send_summary())
