from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User, TrustScore
from app.models.round import Round, RoundMember, CyclePayment
from uuid import UUID


async def calculate_trust_score(user_id: UUID, db: AsyncSession) -> TrustScore:
    """
    Calculate trust score for a user based on their payment history.

    Base: 100
    Modifications:
      - completed_round: +5
      - on_time_payment: +0 (tracked but not directly added)
      - late_payment: -2
      - default: -10
      - dispute_against_upheld: -5

    Returns: Updated TrustScore object (not yet saved to DB)
    """
    # Get or create trust score
    result = await db.execute(select(TrustScore).where(TrustScore.user_id == user_id))
    trust_score = result.scalar_one_or_none()

    if not trust_score:
        trust_score = TrustScore(user_id=user_id)

    # Count user's round statistics
    # Total rounds (as member)
    member_result = await db.execute(
        select(RoundMember).where(RoundMember.user_id == user_id)
    )
    all_memberships = member_result.scalars().all()
    total_rounds = len(all_memberships)

    # Count completed rounds
    completed_rounds_count = 0
    for membership in all_memberships:
        round_result = await db.execute(
            select(Round).where(Round.id == membership.round_id)
        )
        round_obj = round_result.scalar_one()
        if round_obj.status == "completed":
            completed_rounds_count += 1

    # Count payments
    payments_result = await db.execute(
        select(CyclePayment).where(CyclePayment.payer_id == user_id)
    )
    all_payments = payments_result.scalars().all()

    total_payments_due = len(all_payments)
    on_time_payments = 0
    late_payments = 0
    defaults_count = 0

    for payment in all_payments:
        if payment.status == "defaulted":
            defaults_count += 1
        elif payment.status in ["confirmed", "auto_confirmed", "locked"]:
            # Check if on time
            if payment.paid_at and payment.paid_at.date() <= payment.due_date:
                on_time_payments += 1
            elif payment.paid_at:
                late_payments += 1

    # TODO: Count disputes_against when dispute resolution is implemented
    disputes_against_upheld = 0

    # Calculate score
    base_score = 100
    score = Decimal(base_score)

    # Add for completed rounds
    score += Decimal(completed_rounds_count * 5)

    # Subtract for late payments
    score -= Decimal(late_payments * 2)

    # Subtract for defaults
    score -= Decimal(defaults_count * 10)

    # Subtract for disputes upheld against user
    score -= Decimal(disputes_against_upheld * 5)

    # Ensure score doesn't go below 0
    score = max(score, Decimal("0"))

    # Update trust score object
    trust_score.score = str(score)
    trust_score.total_rounds = str(total_rounds)
    trust_score.completed_rounds = str(completed_rounds_count)
    trust_score.total_payments_due = str(total_payments_due)
    trust_score.on_time_payments = str(on_time_payments)
    trust_score.late_payments = str(late_payments)
    trust_score.defaults = str(defaults_count)
    trust_score.disputes_against = str(disputes_against_upheld)

    from datetime import datetime
    from sqlalchemy.sql import func
    from sqlalchemy import text

    trust_score.last_calculated_at = datetime.utcnow()

    return trust_score


async def ensure_trust_score_exists(user_id: UUID, db: AsyncSession) -> TrustScore:
    """
    Ensure a trust score exists for a user, creating one if needed.
    """
    result = await db.execute(select(TrustScore).where(TrustScore.user_id == user_id))
    trust_score = result.scalar_one_or_none()

    if not trust_score:
        trust_score = TrustScore(
            user_id=user_id,
            score="100",
            total_rounds="0",
            completed_rounds="0",
            total_payments_due="0",
            on_time_payments="0",
            late_payments="0",
            defaults="0",
            disputes_raised="0",
            disputes_against="0",
        )
        db.add(trust_score)
        await db.flush()

    return trust_score


async def recalculate_and_save_trust_score(user_id: UUID, db: AsyncSession) -> TrustScore:
    """
    Recalculate trust score and save to database
    """
    trust_score = await calculate_trust_score(user_id, db)
    db.add(trust_score)
    await db.flush()
    return trust_score
