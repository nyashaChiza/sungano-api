from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.config import settings
from app.models.user import User, TrustScore
from app.models.round import Round, RoundMember, RoundCycle, CyclePayment
from app.models.goal import Goal, GoalMember, GoalDeposit
from app.models.dispute import Dispute

router = APIRouter()


async def _is_admin(user_id):
    """Check if user is admin (for now, just check if they're in ADMIN_USERS list)"""
    return user_id in getattr(settings, 'ADMIN_USERS', [])


@router.get("/stats")
async def get_dashboard_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get admin dashboard statistics"""
    # Admin check would be added here if configured
    # For now, return stats for any authenticated user
    
    # Total users
    users_result = await db.execute(select(func.count(User.id)))
    total_users = users_result.scalar() or 0

    # Total rounds
    rounds_result = await db.execute(select(func.count(Round.id)))
    total_rounds = rounds_result.scalar() or 0

    # Active rounds (status = 'active')
    active_rounds_result = await db.execute(
        select(func.count(Round.id)).where(Round.status == "active")
    )
    active_rounds = active_rounds_result.scalar() or 0

    # Completed rounds
    completed_rounds_result = await db.execute(
        select(func.count(Round.id)).where(Round.status == "completed")
    )
    completed_rounds = completed_rounds_result.scalar() or 0

    # Total goals
    goals_result = await db.execute(select(func.count(Goal.id)))
    total_goals = goals_result.scalar() or 0

    # Completed goals
    completed_goals_result = await db.execute(
        select(func.count(Goal.id)).where(Goal.status == "completed")
    )
    completed_goals = completed_goals_result.scalar() or 0

    # Total disputes
    disputes_result = await db.execute(select(func.count(Dispute.id)))
    total_disputes = disputes_result.scalar() or 0

    # Open disputes
    open_disputes_result = await db.execute(
        select(func.count(Dispute.id)).where(Dispute.status == "open")
    )
    open_disputes = open_disputes_result.scalar() or 0

    # Total payments submitted
    payments_result = await db.execute(select(func.count(CyclePayment.id)))
    total_payments = payments_result.scalar() or 0

    # Pending payments
    pending_payments_result = await db.execute(
        select(func.count(CyclePayment.id)).where(CyclePayment.status == "pending")
    )
    pending_payments = pending_payments_result.scalar() or 0

    # Defaulted payments
    defaulted_payments_result = await db.execute(
        select(func.count(CyclePayment.id)).where(CyclePayment.status == "defaulted")
    )
    defaulted_payments = defaulted_payments_result.scalar() or 0

    # Total goal deposits
    deposits_result = await db.execute(select(func.count(GoalDeposit.id)))
    total_deposits = deposits_result.scalar() or 0

    # Confirmed deposits
    confirmed_deposits_result = await db.execute(
        select(func.count(GoalDeposit.id)).where(GoalDeposit.status == "confirmed")
    )
    confirmed_deposits = confirmed_deposits_result.scalar() or 0

    # Average trust score
    avg_trust_result = await db.execute(
        select(func.avg(TrustScore.score))
    )
    avg_trust_score = float(avg_trust_result.scalar() or 0)

    # New users in last 7 days
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    new_users_result = await db.execute(
        select(func.count(User.id)).where(User.created_at >= seven_days_ago)
    )
    new_users_7d = new_users_result.scalar() or 0

    # New rounds in last 7 days
    new_rounds_result = await db.execute(
        select(func.count(Round.id)).where(Round.created_at >= seven_days_ago)
    )
    new_rounds_7d = new_rounds_result.scalar() or 0

    return {
        "users": {
            "total": total_users,
            "new_7d": new_users_7d,
        },
        "rounds": {
            "total": total_rounds,
            "active": active_rounds,
            "completed": completed_rounds,
            "new_7d": new_rounds_7d,
        },
        "goals": {
            "total": total_goals,
            "completed": completed_goals,
        },
        "payments": {
            "total": total_payments,
            "pending": pending_payments,
            "defaulted": defaulted_payments,
        },
        "deposits": {
            "total": total_deposits,
            "confirmed": confirmed_deposits,
        },
        "disputes": {
            "total": total_disputes,
            "open": open_disputes,
        },
        "trust": {
            "average_score": avg_trust_score,
        },
    }


@router.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
    }
