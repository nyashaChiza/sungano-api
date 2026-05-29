import uuid
from typing import Annotated, List, Optional
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.goal import Goal, GoalMember, GoalDeposit
from app.schemas.goal import (
    GoalCreate,
    GoalUpdate,
    GoalResponse,
    GoalSummaryResponse,
    GoalMemberResponse,
    GoalDepositResponse,
    GoalDepositCreate,
    GoalDepositConfirmRequest,
    GoalInviteRequest,
)
from app.services import cloudinary_service

router = APIRouter()


async def _load_goal_with_relations(goal_id: UUID, db: AsyncSession) -> Optional[Goal]:
    """Load goal with all relations"""
    result = await db.execute(
        select(Goal)
        .where(Goal.id == goal_id)
        .options(
            selectinload(Goal.members).selectinload(GoalMember.user),
            selectinload(Goal.deposits),
        )
    )
    return result.scalar_one_or_none()


async def _build_goal_response(goal_obj: Goal) -> GoalResponse:
    """Convert goal to response model"""
    members_resp = [
        GoalMemberResponse(
            id=m.id,
            goal_id=m.goal_id,
            user_id=m.user_id,
            split_percent=m.split_percent,
            target_amount=m.target_amount,
            contributed=m.contributed,
            invite_status=m.invite_status,
            joined_at=m.joined_at,
        )
        for m in goal_obj.members
    ]

    deposits_resp = [
        GoalDepositResponse(
            id=d.id,
            goal_id=d.goal_id,
            user_id=d.user_id,
            amount=d.amount,
            proof_url=d.proof_url,
            proof_type=d.proof_type,
            note=d.note,
            deposited_at=d.deposited_at,
            status=d.status,
            confirmed_at=d.confirmed_at,
            confirmed_by=d.confirmed_by,
            rejection_note=d.rejection_note,
            created_at=d.created_at,
        )
        for d in goal_obj.deposits
    ]

    return GoalResponse(
        id=goal_obj.id,
        name=goal_obj.name,
        created_by=goal_obj.created_by,
        target_amount=goal_obj.target_amount,
        currency=goal_obj.currency,
        target_date=goal_obj.target_date,
        goal_type=goal_obj.goal_type,
        suggested_frequency=goal_obj.suggested_frequency,
        suggested_amount=goal_obj.suggested_amount,
        current_total=goal_obj.current_total,
        target_account_id=goal_obj.target_account_id,
        status=goal_obj.status,
        created_at=goal_obj.created_at,
        updated_at=goal_obj.updated_at,
        members=members_resp,
        deposits=deposits_resp,
    )


@router.post("/", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    data: GoalCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new goal"""
    goal = Goal(
        name=data.name,
        created_by=current_user.id,
        target_amount=data.target_amount,
        currency=data.currency,
        target_date=data.target_date,
        goal_type=data.goal_type,
        suggested_frequency=data.suggested_frequency,
        suggested_amount=data.suggested_amount,
        target_account_id=data.target_account_id,
        status="active",
    )
    db.add(goal)
    await db.flush()

    # Add creator as a member
    creator_member = GoalMember(
        goal_id=goal.id,
        user_id=current_user.id,
        invite_status="accepted",
    )
    db.add(creator_member)
    await db.flush()

    # Load full goal
    full_goal = await _load_goal_with_relations(goal.id, db)
    return await _build_goal_response(full_goal)


@router.get("/", response_model=List[GoalSummaryResponse])
async def list_goals(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List goals where user is creator or member"""
    member_goal_ids_result = await db.execute(
        select(GoalMember.goal_id).where(GoalMember.user_id == current_user.id)
    )
    member_goal_ids = [row[0] for row in member_goal_ids_result.fetchall()]

    result = await db.execute(
        select(Goal)
        .where(
            or_(
                Goal.created_by == current_user.id,
                Goal.id.in_(member_goal_ids) if member_goal_ids else False,
            )
        )
        .options(selectinload(Goal.members))
    )
    goals = result.scalars().all()

    return [
        GoalSummaryResponse(
            id=g.id,
            name=g.name,
            created_by=g.created_by,
            target_amount=g.target_amount,
            currency=g.currency,
            target_date=g.target_date,
            current_total=g.current_total,
            status=g.status,
            members_count=len(g.members),
            created_at=g.created_at,
        )
        for g in goals
    ]


@router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(
    goal_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get goal detail"""
    goal = await _load_goal_with_relations(goal_id, db)

    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )

    # Check access
    is_creator = goal.created_by == current_user.id
    is_member = any(m.user_id == current_user.id for m in goal.members)

    if not is_creator and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return await _build_goal_response(goal)


@router.put("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: UUID,
    data: GoalUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update goal (creator only)"""
    goal = await _load_goal_with_relations(goal_id, db)

    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )

    if goal.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creator can update goal",
        )

    if data.name:
        goal.name = data.name
    if data.target_amount:
        goal.target_amount = data.target_amount
    if data.target_date:
        goal.target_date = data.target_date

    goal.updated_at = datetime.utcnow()
    db.add(goal)
    await db.flush()

    # Reload
    full_goal = await _load_goal_with_relations(goal_id, db)
    return await _build_goal_response(full_goal)


@router.post("/{goal_id}/deposits", response_model=GoalDepositResponse, status_code=status.HTTP_201_CREATED)
async def record_deposit(
    goal_id: UUID,
    amount: Decimal,
    proof_type: Optional[str] = None,
    note: Optional[str] = None,
    file: Optional[UploadFile] = File(None),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Record deposit for goal"""
    goal = await _load_goal_with_relations(goal_id, db)

    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )

    # Check if member
    is_creator = goal.created_by == current_user.id
    is_member = any(m.user_id == current_user.id for m in goal.members)

    if not is_creator and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this goal",
        )

    # Upload proof if provided
    proof_url = None
    if file:
        file_bytes = await file.read()
        public_id = await cloudinary_service.upload_goal_proof(
            goal_id, current_user.id, file_bytes, proof_type or "receipt"
        )
        proof_url = cloudinary_service.get_signed_url(public_id)

    # Create deposit
    deposit = GoalDeposit(
        goal_id=goal_id,
        user_id=current_user.id,
        amount=amount,
        proof_url=proof_url,
        proof_type=proof_type,
        note=note,
        deposited_at=datetime.utcnow(),
        status="pending",
    )
    db.add(deposit)
    await db.flush()

    return GoalDepositResponse(
        id=deposit.id,
        goal_id=deposit.goal_id,
        user_id=deposit.user_id,
        amount=deposit.amount,
        proof_url=deposit.proof_url,
        proof_type=deposit.proof_type,
        note=deposit.note,
        deposited_at=deposit.deposited_at,
        status=deposit.status,
        confirmed_at=deposit.confirmed_at,
        confirmed_by=deposit.confirmed_by,
        rejection_note=deposit.rejection_note,
        created_at=deposit.created_at,
    )


@router.get("/{goal_id}/deposits", response_model=List[GoalDepositResponse])
async def list_deposits(
    goal_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get deposit history for goal"""
    goal = await _load_goal_with_relations(goal_id, db)

    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )

    # Check access
    is_creator = goal.created_by == current_user.id
    is_member = any(m.user_id == current_user.id for m in goal.members)

    if not is_creator and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return [
        GoalDepositResponse(
            id=d.id,
            goal_id=d.goal_id,
            user_id=d.user_id,
            amount=d.amount,
            proof_url=d.proof_url,
            proof_type=d.proof_type,
            note=d.note,
            deposited_at=d.deposited_at,
            status=d.status,
            confirmed_at=d.confirmed_at,
            confirmed_by=d.confirmed_by,
            rejection_note=d.rejection_note,
            created_at=d.created_at,
        )
        for d in goal.deposits
    ]


@router.post("/{goal_id}/invite", status_code=status.HTTP_201_CREATED)
async def invite_member(
    goal_id: UUID,
    invite_data: GoalInviteRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Invite member to goal (creator only)"""
    goal = await _load_goal_with_relations(goal_id, db)

    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )

    if goal.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creator can invite members",
        )

    # Find user by email or phone
    user_result = None
    if invite_data.email:
        user_result = await db.execute(
            select(User).where(User.email == invite_data.email)
        )
    elif invite_data.phone:
        user_result = await db.execute(
            select(User).where(User.phone == invite_data.phone)
        )

    user = user_result.scalar_one_or_none() if user_result else None

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if already member
    existing_result = await db.execute(
        select(GoalMember).where(
            and_(
                GoalMember.goal_id == goal_id,
                GoalMember.user_id == user.id,
            )
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member",
        )

    # Add member
    member = GoalMember(
        goal_id=goal_id,
        user_id=user.id,
        split_percent=invite_data.split_percent,
        target_amount=invite_data.target_amount,
        invite_status="pending",
    )
    db.add(member)
    await db.flush()

    return {"message": "Member invited"}


@router.put("/{goal_id}/deposits/{deposit_id}/confirm", response_model=GoalDepositResponse)
async def confirm_deposit(
    goal_id: UUID,
    deposit_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Confirm deposit (goal creator only)"""
    goal = await _load_goal_with_relations(goal_id, db)

    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )

    if goal.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creator can confirm deposits",
        )

    deposit_result = await db.execute(
        select(GoalDeposit).where(
            and_(
                GoalDeposit.id == deposit_id,
                GoalDeposit.goal_id == goal_id,
            )
        )
    )
    deposit = deposit_result.scalar_one_or_none()

    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deposit not found",
        )

    # Confirm deposit
    deposit.status = "confirmed"
    deposit.confirmed_at = datetime.utcnow()
    deposit.confirmed_by = current_user.id

    # Update goal current_total and member contributed
    goal.current_total += deposit.amount

    member_result = await db.execute(
        select(GoalMember).where(
            and_(
                GoalMember.goal_id == goal_id,
                GoalMember.user_id == deposit.user_id,
            )
        )
    )
    member = member_result.scalar_one_or_none()
    if member:
        member.contributed += deposit.amount
        db.add(member)

    goal.updated_at = datetime.utcnow()
    db.add(goal)
    db.add(deposit)
    await db.flush()

    return GoalDepositResponse(
        id=deposit.id,
        goal_id=deposit.goal_id,
        user_id=deposit.user_id,
        amount=deposit.amount,
        proof_url=deposit.proof_url,
        proof_type=deposit.proof_type,
        note=deposit.note,
        deposited_at=deposit.deposited_at,
        status=deposit.status,
        confirmed_at=deposit.confirmed_at,
        confirmed_by=deposit.confirmed_by,
        rejection_note=deposit.rejection_note,
        created_at=deposit.created_at,
    )


@router.put("/{goal_id}/deposits/{deposit_id}/reject", response_model=GoalDepositResponse)
async def reject_deposit(
    goal_id: UUID,
    deposit_id: UUID,
    rejection_note: Optional[str] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Reject deposit (goal creator only)"""
    goal = await _load_goal_with_relations(goal_id, db)

    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )

    if goal.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creator can reject deposits",
        )

    deposit_result = await db.execute(
        select(GoalDeposit).where(
            and_(
                GoalDeposit.id == deposit_id,
                GoalDeposit.goal_id == goal_id,
            )
        )
    )
    deposit = deposit_result.scalar_one_or_none()

    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deposit not found",
        )

    # Reject deposit
    deposit.status = "rejected"
    deposit.rejection_note = rejection_note
    db.add(deposit)
    await db.flush()

    return GoalDepositResponse(
        id=deposit.id,
        goal_id=deposit.goal_id,
        user_id=deposit.user_id,
        amount=deposit.amount,
        proof_url=deposit.proof_url,
        proof_type=deposit.proof_type,
        note=deposit.note,
        deposited_at=deposit.deposited_at,
        status=deposit.status,
        confirmed_at=deposit.confirmed_at,
        confirmed_by=deposit.confirmed_by,
        rejection_note=deposit.rejection_note,
        created_at=deposit.created_at,
    )
