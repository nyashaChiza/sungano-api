"""
Detect defaults (overdue payments) and update trust scores
Runs daily at 8 AM
"""

from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import logging

from app.core.config import settings
from app.models.round import CyclePayment, RoundCycle, Round
from app.models.user import TrustScore, User
from app.models.notification import Reminder
from app.services.trust_service import calculate_trust_score

logger = logging.getLogger(__name__)


async def run_default_detection():
    """Detect defaults and update trust scores"""
    try:
        # Create async engine for this job
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with AsyncSessionLocal() as db:
            # Find overdue payments (due_date has passed, status is still pending/submitted)
            today = date.today()
            
            result = await db.execute(
                select(CyclePayment)
                .where(
                    CyclePayment.status.in_(["pending", "submitted"]),
                    CyclePayment.due_date < today,
                )
            )
            overdue_payments = result.scalars().all()
            
            defaulted_count = 0
            for payment in overdue_payments:
                # Mark as defaulted
                payment.status = "defaulted"
                
                # Load payer's trust score and update it
                payer_result = await db.execute(
                    select(TrustScore).where(TrustScore.user_id == payment.payer_id)
                )
                trust_score = payer_result.scalar_one_or_none()
                
                if trust_score:
                    # Deduct 10 points for default
                    trust_score.score = max(0, trust_score.score - 10)
                    trust_score.defaults += 1
                    
                    # Create default notice reminder
                    reminder = Reminder(
                        user_id=payment.payer_id,
                        type="default_notice",
                        channel="both",
                        reference_id=payment.id,
                        reference_type="payment",
                        payload={
                            "payment_id": str(payment.id),
                            "amount": str(payment.amount),
                        },
                        scheduled_at=datetime.utcnow(),
                        status="pending",
                    )
                    db.add(reminder)
                    
                defaulted_count += 1
            
            await db.commit()
            
            logger.info(f"Detected {defaulted_count} defaults and updated trust scores")
            
        await engine.dispose()
        
    except Exception as e:
        logger.error(f"Error in default_detection job: {str(e)}", exc_info=True)
