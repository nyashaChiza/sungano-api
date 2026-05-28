import os
import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.round import Round, RoundMember, Cycle, Payment
from app.schemas.round import (
    RoundCreate,
    RoundUpdate,
    RoundResponse,
    RoundMemberResponse,
    CycleResponse,
    PaymentCreate,
    PaymentResponse,
    SubmitProofRequest,
)
from app.schemas.user import UserResponse
from datetime import datetime

router = APIRouter()


async def _get_round_with_members(round_id: int, db: AsyncSession) -> Round:
    result = await db.execute(
        select(Round)
        .options(
            selectinload(Round.members).selectinload(RoundMember.user),
            selectinload(Round.cycles)
            .selectinload(Cycle.payments)
            .selectinload(Payment.payer),
            selectinload(Round.cycles).selectinload(Cycle.recipient),
        )
        .where(Round.id == round_id)
    )
    return result.scalar_one_or_none()


async def _build_round_response(round_obj: Round) -> dict:
    current_cycle = None
    for cycle in round_obj.cycles:
        if not cycle.is_complete:
            current_cycle = cycle
            break

    data = {
        "id": round_obj.id,
        "name": round_obj.name,
        "creator_id": round_obj.creator_id,
        "contribution_amount": round_obj.contribution_amount,
        "currency": round_obj.currency,
        "frequency": round_obj.frequency,
        "total_cycles": round_obj.total_cycles,
        "grace_period_days": round_obj.grace_period_days,
        "status": round_obj.status,
        "start_date": round_obj.start_date,
        "created_at": round_obj.created_at,
        "members": round_obj.members,
        "current_cycle": current_cycle,
    }
    return RoundResponse(**data)


@router.get("/", response_model=List[RoundResponse])
async def list_rounds(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    member_round_ids_result = await db.execute(
        select(RoundMember.round_id).where(RoundMember.user_id == current_user.id)
    )
    member_round_ids = [row[0] for row in member_round_ids_result.fetchall()]

    result = await db.execute(
        select(Round)
        .options(
            selectinload(Round.members).selectinload(RoundMember.user),
            selectinload(Round.cycles)
            .selectinload(Cycle.payments)
            .selectinload(Payment.payer),
            selectinload(Round.cycles).selectinload(Cycle.recipient),
        )
        .where(
            or_(
                Round.creator_id == current_user.id,
                Round.id.in_(member_round_ids),
            )
        )
    )
    rounds = result.scalars().all()
    return [await _build_round_response(r) for r in rounds]


@router.post("/", response_model=RoundResponse, status_code=status.HTTP_201_CREATED)
async def create_round(
    data: RoundCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    round_obj = Round(
        name=data.name,
        creator_id=current_user.id,
        contribution_amount=data.contribution_amount,
        currency=data.currency,
        frequency=data.frequency,
        total_cycles=data.total_cycles,
        grace_period_days=data.grace_period_days or 3,
        start_date=data.start_date,
        status="pending",
    )
    db.add(round_obj)
    await db.flush()

    # Add creator as a member
    member = RoundMember(
        round_id=round_obj.id,
        user_id=current_user.id,
        payout_position=1,
        signed_at=datetime.utcnow(),
    )
    db.add(member)
    await db.commit()

    full_round = await _get_round_with_members(round_obj.id, db)
    return await _build_round_response(full_round)


@router.get("/{round_id}", response_model=RoundResponse)
async def get_round(
    round_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    round_obj = await _get_round_with_members(round_id, db)
    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Round not found"
        )

    # Check access
    is_member = any(m.user_id == current_user.id for m in round_obj.members)
    if round_obj.creator_id != current_user.id and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    return await _build_round_response(round_obj)


@router.put("/{round_id}", response_model=RoundResponse)
async def update_round(
    round_id: int,
    data: RoundUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Round).where(Round.id == round_id))
    round_obj = result.scalar_one_or_none()
    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Round not found"
        )
    if round_obj.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creator can update round",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(round_obj, field, value)

    await db.commit()
    full_round = await _get_round_with_members(round_id, db)
    return await _build_round_response(full_round)


@router.delete("/{round_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_round(
    round_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Round).where(Round.id == round_id))
    round_obj = result.scalar_one_or_none()
    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Round not found"
        )
    if round_obj.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creator can delete round",
        )
    if round_obj.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending rounds can be deleted",
        )

    await db.delete(round_obj)
    await db.commit()


@router.post(
    "/{round_id}/invite",
    response_model=RoundMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    round_id: int,
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Round).where(Round.id == round_id))
    round_obj = result.scalar_one_or_none()
    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Round not found"
        )
    if round_obj.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creator can invite members",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    invited_user = result.scalar_one_or_none()
    if not invited_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    existing = await db.execute(
        select(RoundMember).where(
            RoundMember.round_id == round_id, RoundMember.user_id == user_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User already a member"
        )

    members_count_result = await db.execute(
        select(RoundMember).where(RoundMember.round_id == round_id)
    )
    position = len(members_count_result.scalars().all()) + 1

    member = RoundMember(
        round_id=round_id,
        user_id=user_id,
        payout_position=position,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    result = await db.execute(
        select(RoundMember)
        .options(selectinload(RoundMember.user))
        .where(RoundMember.id == member.id)
    )
    return result.scalar_one()


@router.post("/{round_id}/sign", response_model=RoundMemberResponse)
async def sign_contract(
    round_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(RoundMember)
        .options(selectinload(RoundMember.user))
        .where(RoundMember.round_id == round_id, RoundMember.user_id == current_user.id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not a member of this round"
        )
    if member.signed_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Already signed"
        )

    member.signed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(member)
    return member


@router.post("/{round_id}/activate", response_model=RoundResponse)
async def activate_round(
    round_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Round).where(Round.id == round_id))
    round_obj = result.scalar_one_or_none()
    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Round not found"
        )
    if round_obj.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creator can activate round",
        )
    if round_obj.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Round is not in pending state",
        )

    members_result = await db.execute(
        select(RoundMember).where(RoundMember.round_id == round_id)
    )
    members = members_result.scalars().all()
    unsigned = [m for m in members if not m.signed_at]
    if unsigned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{len(unsigned)} member(s) have not signed yet",
        )

    round_obj.status = "active"
    if not round_obj.start_date:
        round_obj.start_date = datetime.utcnow()

    # Create cycles for each member based on payout position
    sorted_members = sorted(members, key=lambda m: m.payout_position or 0)
    for i, member in enumerate(sorted_members):
        cycle = Cycle(
            round_id=round_id,
            cycle_number=i + 1,
            recipient_id=member.user_id,
        )
        db.add(cycle)

    await db.commit()
    full_round = await _get_round_with_members(round_id, db)
    return await _build_round_response(full_round)


@router.get("/{round_id}/cycles", response_model=List[CycleResponse])
async def list_cycles(
    round_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Cycle)
        .options(
            selectinload(Cycle.payments).selectinload(Payment.payer),
            selectinload(Cycle.recipient),
        )
        .where(Cycle.round_id == round_id)
        .order_by(Cycle.cycle_number)
    )
    return result.scalars().all()


@router.get("/{round_id}/cycles/current", response_model=CycleResponse)
async def get_current_cycle(
    round_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Cycle)
        .options(
            selectinload(Cycle.payments).selectinload(Payment.payer),
            selectinload(Cycle.recipient),
        )
        .where(Cycle.round_id == round_id, Cycle.is_complete == False)
        .order_by(Cycle.cycle_number)
    )
    cycle = result.scalars().first()
    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No active cycle found"
        )
    return cycle


@router.post(
    "/{round_id}/cycles/{cycle_id}/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment(
    round_id: int,
    cycle_id: int,
    data: PaymentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Cycle).where(Cycle.id == cycle_id, Cycle.round_id == round_id)
    )
    cycle = result.scalar_one_or_none()
    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cycle not found"
        )

    existing = await db.execute(
        select(Payment).where(
            Payment.cycle_id == cycle_id, Payment.payer_id == current_user.id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment already exists for this cycle",
        )

    payment = Payment(
        cycle_id=cycle_id,
        payer_id=current_user.id,
        amount=data.amount,
        proof_type=data.proof_type,
        status="pending",
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.payer))
        .where(Payment.id == payment.id)
    )
    return result.scalar_one()


@router.post("/payments/{payment_id}/submit-proof", response_model=PaymentResponse)
async def submit_proof(
    payment_id: int,
    proof_type: Annotated[str, Form()],
    note: Annotated[str, Form()] = "",
    proof_file: Annotated[UploadFile | None, File()] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.payer))
        .where(Payment.id == payment_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found"
        )
    if payment.payer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your payment"
        )

    payment.proof_type = proof_type
    payment.note = note
    payment.status = "submitted"
    payment.submitted_at = datetime.utcnow()

    if proof_file:
        ext = (
            os.path.splitext(proof_file.filename)[1] if proof_file.filename else ".jpg"
        )
        filename = f"{uuid.uuid4()}{ext}"
        proof_dir = os.path.join(settings.UPLOAD_DIR, "proofs")
        os.makedirs(proof_dir, exist_ok=True)
        file_path = os.path.join(proof_dir, filename)
        content = await proof_file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        payment.proof_file_path = f"/uploads/proofs/{filename}"

    await db.commit()
    await db.refresh(payment)

    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.payer))
        .where(Payment.id == payment_id)
    )
    return result.scalar_one()


@router.post("/payments/{payment_id}/confirm", response_model=PaymentResponse)
async def confirm_payment(
    payment_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.payer))
        .where(Payment.id == payment_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found"
        )

    # Check that current user is the recipient of the cycle
    cycle_result = await db.execute(select(Cycle).where(Cycle.id == payment.cycle_id))
    cycle = cycle_result.scalar_one_or_none()
    if cycle.recipient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the cycle recipient can confirm payments",
        )

    payment.status = "confirmed"
    payment.confirmed_at = datetime.utcnow()
    payment.confirmed_by_id = current_user.id

    await db.commit()

    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.payer))
        .where(Payment.id == payment_id)
    )
    return result.scalar_one()
