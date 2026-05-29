"""
Dispatch scheduled reminders via email and push notifications
Runs daily at 8 AM
"""

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import logging

from app.core.config import settings
from app.models.notification import Reminder
from app.models.user import User, DeviceToken
from app.services.email_service import send_reminder
from app.services.push_service import send_push_notification

logger = logging.getLogger(__name__)


async def run_reminder_dispatch():
    """Dispatch pending reminders via email and push"""
    try:
        # Create async engine for this job
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with AsyncSessionLocal() as db:
            # Find pending reminders that are scheduled to be sent now
            result = await db.execute(
                select(Reminder)
                .where(
                    Reminder.status == "pending",
                    Reminder.scheduled_at <= datetime.utcnow(),
                )
            )
            reminders = result.scalars().all()
            
            dispatched_count = 0
            for reminder in reminders:
                try:
                    # Load user
                    user_result = await db.execute(
                        select(User).where(User.id == reminder.user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    if not user:
                        logger.warning(f"User not found for reminder {reminder.id}")
                        continue
                    
                    # Send email if channel is email or both
                    if reminder.channel in ["email", "both"]:
                        await send_reminder(user.email, user.full_name, reminder.type, reminder.payload or {})
                    
                    # Send push if channel is push or both
                    if reminder.channel in ["push", "both"]:
                        # Get user's device tokens
                        device_result = await db.execute(
                            select(DeviceToken).where(
                                DeviceToken.user_id == reminder.user_id,
                                DeviceToken.is_active == True,
                            )
                        )
                        devices = device_result.scalars().all()
                        
                        for device in devices:
                            await send_push_notification(
                                device.token,
                                reminder.type,
                                reminder.payload,
                            )
                    
                    # Mark reminder as sent
                    reminder.status = "sent"
                    reminder.sent_at = datetime.utcnow()
                    dispatched_count += 1
                    
                except Exception as e:
                    logger.error(f"Error dispatching reminder {reminder.id}: {str(e)}")
                    reminder.status = "pending"  # Keep as pending to retry
            
            await db.commit()
            
            logger.info(f"Dispatched {dispatched_count} reminders")
            
        await engine.dispose()
        
    except Exception as e:
        logger.error(f"Error in reminder_dispatch job: {str(e)}", exc_info=True)
