"""
Auto-confirm payments after 72 hours
Runs every hour
"""

from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import logging

from app.core.config import settings
from app.models.round import CyclePayment
from app.services.push_service import send_push_notification

logger = logging.getLogger(__name__)


async def run_auto_confirm():
    """Auto-confirm payments that were submitted 72+ hours ago"""
    try:
        # Create async engine for this job
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with AsyncSessionLocal() as db:
            # Find payments submitted 72+ hours ago that are still pending
            cutoff_time = datetime.utcnow() - timedelta(hours=72)
            
            result = await db.execute(
                select(CyclePayment)
                .where(
                    CyclePayment.status == "submitted",
                    CyclePayment.paid_at <= cutoff_time,
                )
            )
            payments = result.scalars().all()
            
            for payment in payments:
                # Auto-confirm the payment
                payment.status = "confirmed"
                payment.auto_confirmed = True
                payment.confirmed_at = datetime.utcnow()
                
                # TODO: Send notification to payer and recipient
                # await send_push_notification(payment.payer_id, "payment_auto_confirmed")
                
            await db.commit()
            
            logger.info(f"Auto-confirmed {len(payments)} payments")
            
        await engine.dispose()
        
    except Exception as e:
        logger.error(f"Error in auto_confirm job: {str(e)}", exc_info=True)
