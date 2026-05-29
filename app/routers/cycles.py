from typing import Annotated, List
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.round import Round, RoundCycle, CyclePayment, RoundMember
from app.schemas.round import RoundCycleResponse, CyclePaymentResponse

router = APIRouter()


@router.get("/{round_id}/cycles", response_model=List[RoundCycleResponse])
async def list_cycles(
    round_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get all cycles for a round"""
    # Verify user has access to round
    round_result = await db.execute(select(Round).where(Round.id == round_id))
    round_obj = round_result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Round not found",
        )

    is_creator = round_obj.created_by == current_user.id
    is_member = (
        await db.execute(
            select(RoundMember).where(
                and_(RoundMember.round_id == round_id, RoundMember.user_id == current_user.id)
            )
        )
    ).scalar_one_or_none()

    if not is_creator and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Get cycles
    cycles_result = await db.execute(
        select(RoundCycle)
        .where(RoundCycle.round_id == round_id)
        .options(selectinload(RoundCycle.payments))
        .order_by(RoundCycle.cycle_number)
    )
    cycles = cycles_result.scalars().all()

    return [
        RoundCycleResponse(
            id=c.id,
            round_id=c.round_id,
            cycle_number=c.cycle_number,
            recipient_id=c.recipient_id,
            due_date=c.due_date,
            payout_date=c.payout_date,
            total_expected=c.total_expected,
            total_received=c.total_received,
            status=c.status,
            payments=[
                CyclePaymentResponse(
                    id=p.id,
                    cycle_id=p.cycle_id,
                    payer_id=p.payer_id,
                    amount=p.amount,
                    due_date=p.due_date,
                    paid_at=p.paid_at,
                    proof_url=p.proof_url,
                    proof_type=p.proof_type,
                    note=p.note,
                    status=p.status,
                    confirmed_at=p.confirmed_at,
                    auto_confirmed=p.auto_confirmed,
                    created_at=p.created_at,
                )
                for p in c.payments
            ],
            created_at=c.created_at,
        )
        for c in cycles
    ]


@router.get("/{round_id}/cycles/current", response_model=RoundCycleResponse)
async def get_current_cycle(
    round_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get current active cycle for a round"""
    # Verify access
    round_result = await db.execute(select(Round).where(Round.id == round_id))
    round_obj = round_result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Round not found",
        )

    is_creator = round_obj.created_by == current_user.id
    is_member = (
        await db.execute(
            select(RoundMember).where(
                and_(RoundMember.round_id == round_id, RoundMember.user_id == current_user.id)
            )
        )
    ).scalar_one_or_none()

    if not is_creator and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Get current cycle (first non-completed)
    cycles_result = await db.execute(
        select(RoundCycle)
        .where(
            and_(
                RoundCycle.round_id == round_id,
                RoundCycle.status.in_(["pending", "in_progress"]),
            )
        )
        .options(selectinload(RoundCycle.payments))
        .order_by(RoundCycle.cycle_number)
        .limit(1)
    )
    cycle = cycles_result.scalar_one_or_none()

    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active cycle found",
        )

    return RoundCycleResponse(
        id=cycle.id,
        round_id=cycle.round_id,
        cycle_number=cycle.cycle_number,
        recipient_id=cycle.recipient_id,
        due_date=cycle.due_date,
        payout_date=cycle.payout_date,
        total_expected=cycle.total_expected,
        total_received=cycle.total_received,
        status=cycle.status,
        payments=[
            CyclePaymentResponse(
                id=p.id,
                cycle_id=p.cycle_id,
                payer_id=p.payer_id,
                amount=p.amount,
                due_date=p.due_date,
                paid_at=p.paid_at,
                proof_url=p.proof_url,
                proof_type=p.proof_type,
                note=p.note,
                status=p.status,
                confirmed_at=p.confirmed_at,
                auto_confirmed=p.auto_confirmed,
                created_at=p.created_at,
            )
            for p in cycle.payments
        ],
        created_at=cycle.created_at,
    )


@router.get("/{cycle_id}/payments", response_model=List[CyclePaymentResponse])
async def list_cycle_payments(
    cycle_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get payment board for a cycle"""
    # Get cycle and verify access
    cycle_result = await db.execute(
        select(RoundCycle)
        .where(RoundCycle.id == cycle_id)
        .options(selectinload(RoundCycle.round))
    )
    cycle = cycle_result.scalar_one_or_none()

    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cycle not found",
        )

    round_obj = cycle.round

    is_creator = round_obj.created_by == current_user.id
    is_member = (
        await db.execute(
            select(RoundMember).where(
                and_(
                    RoundMember.round_id == round_obj.id,
                    RoundMember.user_id == current_user.id,
                )
            )
        )
    ).scalar_one_or_none()

    if not is_creator and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Get payments
    payments_result = await db.execute(
        select(CyclePayment)
        .where(CyclePayment.cycle_id == cycle_id)
        .order_by(CyclePayment.created_at)
    )
    payments = payments_result.scalars().all()

    return [
        CyclePaymentResponse(
            id=p.id,
            cycle_id=p.cycle_id,
            payer_id=p.payer_id,
            amount=p.amount,
            due_date=p.due_date,
            paid_at=p.paid_at,
            proof_url=p.proof_url,
            proof_type=p.proof_type,
            note=p.note,
            status=p.status,
            confirmed_at=p.confirmed_at,
            auto_confirmed=p.auto_confirmed,
            created_at=p.created_at,
        )
        for p in payments
    ]
