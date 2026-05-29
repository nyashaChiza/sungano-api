import secrets
import uuid
from typing import Annotated, List, Optional
from uuid import UUID
from datetime import datetime, date, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.config import settings
from app.models.user import User, TrustScore
from app.models.round import Round, RoundMember, RoundCycle, CyclePayment, InviteLink
from app.models.contract import Contract
from app.schemas.round import (
    RoundCreate,
    RoundUpdate,
    RoundResponse,
    RoundSummaryResponse,
    RoundMemberResponse,
    RoundMemberDetailResponse,
    RoundCycleResponse,
    CyclePaymentResponse,
    RoundPreviewResponse,
    InviteLinkResponse,
    PayoutPositionRequest,
    RoundLedgerEntry,
    SubmitProofRequest,
    PaymentConfirmRequest,
    PaymentDisputeRequest,
)
from app.services import cloudinary_service, email_service, push_service
from app.services.contract_service import generate_and_upload_contract
from app.services.trust_service import ensure_trust_score_exists

router = APIRouter()


def _calculate_due_date(start_date: date, cycle_number: int, frequency: str) -> date:
    """Calculate due date for a cycle based on frequency"""
    if frequency == "weekly":
        return start_date + timedelta(weeks=cycle_number)
    elif frequency == "biweekly":
        return start_date + timedelta(weeks=cycle_number * 2)
    elif frequency == "monthly":
        # Approximate for simplicity
        days = cycle_number * 30
        return start_date + timedelta(days=days)
    return start_date


async def _load_round_with_relations(round_id: UUID, db: AsyncSession) -> Optional[Round]:
    """Load round with all relations"""
    result = await db.execute(
        select(Round)
        .where(Round.id == round_id)
        .options(
            selectinload(Round.members).selectinload(RoundMember.user),
            selectinload(Round.cycles).selectinload(RoundCycle.payments),
            selectinload(Round.contracts),
            selectinload(Round.invite_links),
        )
    )
    return result.scalar_one_or_none()


async def _build_round_response(round_obj: Round) -> RoundResponse:
    """Convert round to response model"""
    members_resp = [
        RoundMemberResponse(
            id=m.id,
            user_id=m.user_id,
            round_id=m.round_id,
            payout_position=m.payout_position,
            contract_signed_at=m.contract_signed_at,
            invite_status=m.invite_status,
            is_active=m.is_active,
            joined_at=m.joined_at,
        )
        for m in round_obj.members
    ]

    cycles_resp = [
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
        for c in round_obj.cycles
    ]

    return RoundResponse(
        id=round_obj.id,
        name=round_obj.name,
        created_by=round_obj.created_by,
        contribution_amount=round_obj.contribution_amount,
        currency=round_obj.currency,
        cycle_frequency=round_obj.cycle_frequency,
        start_date=round_obj.start_date,
        total_cycles=round_obj.total_cycles,
        payout_order_method=round_obj.payout_order_method,
        grace_period_days=round_obj.grace_period_days,
        late_penalty_amount=round_obj.late_penalty_amount,
        default_penalty=round_obj.default_penalty,
        collateral_required=round_obj.collateral_required,
        contract_url=round_obj.contract_url,
        contract_mode=round_obj.contract_mode,
        status=round_obj.status,
        created_at=round_obj.created_at,
        updated_at=round_obj.updated_at,
        members=members_resp,
        cycles=cycles_resp,
    )


@router.post("/", response_model=RoundResponse, status_code=status.HTTP_201_CREATED)
async def create_round(
    data: RoundCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new round with auto-generated cycles and contract"""
    # Create round
    round_obj = Round(
        name=data.name,
        created_by=current_user.id,
        contribution_amount=data.contribution_amount,
        currency=data.currency,
        cycle_frequency=data.cycle_frequency,
        start_date=data.start_date,
        total_cycles=data.total_cycles,
        payout_order_method=data.payout_order_method,
        grace_period_days=data.grace_period_days or 3,
        late_penalty_amount=data.late_penalty_amount or Decimal("0"),
        default_penalty=data.default_penalty,
        collateral_required=data.collateral_required or False,
        contract_mode=data.contract_mode or "simple",
        status="pending",
    )
    db.add(round_obj)
    await db.flush()

    # Add creator as a member
    creator_member = RoundMember(
        round_id=round_obj.id,
        user_id=current_user.id,
        payout_position=1,
        invite_status="accepted",
        is_active=True,
    )
    db.add(creator_member)
    await db.flush()

    # Generate all cycles
    for cycle_num in range(1, data.total_cycles + 1):
        due_date = _calculate_due_date(data.start_date, cycle_num, data.cycle_frequency)
        cycle = RoundCycle(
            round_id=round_obj.id,
            cycle_number=cycle_num,
            due_date=due_date,
            total_expected=data.contribution_amount * (data.total_cycles - 1),  # All members except recipient
            status="pending",
        )
        db.add(cycle)
    await db.flush()

    # Generate contract (will upload PDF to Cloudinary)
    contract_public_id = await generate_and_upload_contract(
        round_obj.id, round_obj, db
    )
    signed_url = cloudinary_service.get_signed_url(contract_public_id)

    round_obj.contract_url = signed_url
    db.add(round_obj)
    await db.flush()

    # Create Contract record
    contract = Contract(
        round_id=round_obj.id,
        version=1,
        content_json={"generated": True},
        pdf_url=signed_url,
    )
    db.add(contract)
    await db.flush()

    # Load full round
    full_round = await _load_round_with_relations(round_obj.id, db)
    return await _build_round_response(full_round)


@router.get("/", response_model=List[RoundSummaryResponse])
async def list_rounds(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List rounds where user is creator or member"""
    member_round_ids_result = await db.execute(
        select(RoundMember.round_id).where(RoundMember.user_id == current_user.id)
    )
    member_round_ids = [row[0] for row in member_round_ids_result.fetchall()]

    result = await db.execute(
        select(Round)
        .where(
            or_(
                Round.created_by == current_user.id,
                Round.id.in_(member_round_ids) if member_round_ids else False,
            )
        )
        .options(selectinload(Round.members))
    )
    rounds = result.scalars().all()

    return [
        RoundSummaryResponse(
            id=r.id,
            name=r.name,
            created_by=r.created_by,
            contribution_amount=r.contribution_amount,
            currency=r.currency,
            cycle_frequency=r.cycle_frequency,
            total_cycles=r.total_cycles,
            status=r.status,
            members_count=len(r.members),
            created_at=r.created_at,
        )
        for r in rounds
    ]


@router.get("/{round_id}", response_model=RoundResponse)
async def get_round(
    round_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get round detail"""
    round_obj = await _load_round_with_relations(round_id, db)
    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Round not found",
        )

    # Check access
    is_creator = round_obj.created_by == current_user.id
    is_member = any(m.user_id == current_user.id for m in round_obj.members)

    if not is_creator and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return await _build_round_response(round_obj)


@router.get("/{round_id}/members", response_model=List[RoundMemberDetailResponse])
async def get_round_members(
    round_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get round members with trust scores"""
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

    # Get members
    members_result = await db.execute(
        select(RoundMember)
        .where(RoundMember.round_id == round_id)
        .options(selectinload(RoundMember.user))
    )
    members = members_result.scalars().all()

    # Get trust scores
    response = []
    for member in members:
        trust_result = await db.execute(
            select(TrustScore).where(TrustScore.user_id == member.user_id)
        )
        trust = trust_result.scalar_one_or_none()

        response.append(
            RoundMemberDetailResponse(
                id=member.id,
                user_id=member.user_id,
                round_id=member.round_id,
                payout_position=member.payout_position,
                contract_signed_at=member.contract_signed_at,
                invite_status=member.invite_status,
                is_active=member.is_active,
                joined_at=member.joined_at,
                trust_score=Decimal(trust.score) if trust else Decimal("100"),
            )
        )

    return response


@router.get("/{round_id}/ledger", response_model=List[RoundLedgerEntry])
async def get_round_ledger(
    round_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get full payment history for round"""
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

    # Get all payments for round
    payments_result = await db.execute(
        select(CyclePayment, RoundCycle)
        .join(RoundCycle, CyclePayment.cycle_id == RoundCycle.id)
        .where(RoundCycle.round_id == round_id)
        .order_by(RoundCycle.cycle_number, CyclePayment.created_at)
    )

    ledger = []
    for payment, cycle in payments_result:
        ledger.append(
            RoundLedgerEntry(
                payment_id=payment.id,
                cycle_number=cycle.cycle_number,
                payer_id=payment.payer_id,
                amount=payment.amount,
                status=payment.status,
                paid_at=payment.paid_at,
                confirmed_at=payment.confirmed_at,
                proof_type=payment.proof_type,
            )
        )

    return ledger


@router.post("/{round_id}/invite-link", response_model=InviteLinkResponse)
async def generate_invite_link(
    round_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate invite link for round"""
    round_result = await db.execute(select(Round).where(Round.id == round_id))
    round_obj = round_result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Round not found",
        )

    if round_obj.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creator can generate invite links",
        )

    # Generate random token
    token = secrets.token_urlsafe(32)[:32]

    invite_link = InviteLink(
        round_id=round_id,
        created_by=current_user.id,
        token=token,
        is_active=True,
    )
    db.add(invite_link)
    await db.flush()

    return InviteLinkResponse(
        token=token,
        created_at=invite_link.created_at,
        expires_at=invite_link.expires_at,
        uses=invite_link.uses,
        max_uses=invite_link.max_uses,
    )


@router.get("/join/{token}", response_model=RoundPreviewResponse, dependencies=[])
async def preview_round(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Preview round before joining (NO AUTH REQUIRED)"""
    invite_result = await db.execute(
        select(InviteLink).where(InviteLink.token == token)
    )
    invite = invite_result.scalar_one_or_none()

    if not invite or not invite.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite link",
        )

    if invite.expires_at and invite.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite link expired",
        )

    # Get round
    round_result = await db.execute(
        select(Round)
        .where(Round.id == invite.round_id)
        .options(
            selectinload(Round.members),
            selectinload(Round.creator),
        )
    )
    round_obj = round_result.scalar_one_or_none()

    return RoundPreviewResponse(
        id=round_obj.id,
        name=round_obj.name,
        creator_name=round_obj.creator.full_name,
        contribution_amount=round_obj.contribution_amount,
        currency=round_obj.currency,
        cycle_frequency=round_obj.cycle_frequency,
        total_cycles=round_obj.total_cycles,
        status=round_obj.status,
        members_count=len(round_obj.members),
        start_date=round_obj.start_date,
        created_at=round_obj.created_at,
    )


@router.post("/join/{token}", response_model=RoundResponse)
async def join_round(
    token: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Join a round via invite link"""
    invite_result = await db.execute(
        select(InviteLink).where(InviteLink.token == token)
    )
    invite = invite_result.scalar_one_or_none()

    if not invite or not invite.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite link",
        )

    if invite.expires_at and invite.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite link expired",
        )

    if invite.max_uses and invite.uses >= invite.max_uses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite link has reached max uses",
        )

    # Get round
    round_result = await db.execute(select(Round).where(Round.id == invite.round_id))
    round_obj = round_result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Round not found",
        )

    # Check if already member
    existing_result = await db.execute(
        select(RoundMember).where(
            and_(
                RoundMember.round_id == invite.round_id,
                RoundMember.user_id == current_user.id,
            )
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already a member of this round",
        )

    # Add as member
    new_member = RoundMember(
        round_id=invite.round_id,
        user_id=current_user.id,
        invite_status="pending",
        is_active=True,
    )
    db.add(new_member)

    # Update invite uses
    invite.uses += 1
    db.add(invite)
    await db.flush()

    # Load full round
    full_round = await _load_round_with_relations(invite.round_id, db)
    return await _build_round_response(full_round)


@router.post("/{round_id}/payout-order", response_model=RoundResponse)
async def set_payout_order(
    round_id: UUID,
    order_data: PayoutPositionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Set payout positions for members"""
    round_result = await db.execute(select(Round).where(Round.id == round_id))
    round_obj = round_result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Round not found",
        )

    if round_obj.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creator can set payout order",
        )

    # Update positions
    for user_id, position in order_data.payout_order.items():
        member_result = await db.execute(
            select(RoundMember).where(
                and_(
                    RoundMember.round_id == round_id,
                    RoundMember.user_id == user_id,
                )
            )
        )
        member = member_result.scalar_one_or_none()

        if member:
            member.payout_position = position
            db.add(member)

    await db.flush()

    # Load full round
    full_round = await _load_round_with_relations(round_id, db)
    return await _build_round_response(full_round)


@router.delete("/{round_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dissolve_round(
    round_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Dissolve round (creator only, only if pending)"""
    round_result = await db.execute(select(Round).where(Round.id == round_id))
    round_obj = round_result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Round not found",
        )

    if round_obj.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creator can dissolve round",
        )

    if round_obj.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only dissolve pending rounds",
        )

    # Soft delete by changing status
    round_obj.status = "dissolved"
    db.add(round_obj)
    await db.flush()
    return None
