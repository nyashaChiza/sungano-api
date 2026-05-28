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
from app.models.goal import Goal, GoalMember, GoalDeposit
from app.schemas.goal import (
    GoalCreate,
    GoalUpdate,
    GoalResponse,
    GoalMemberResponse,
    GoalDepositCreate,
    GoalDepositResponse,
)
from datetime import datetime
from decimal import Decimal

router = APIRouter()


async def _get_goal_with_relations(goal_id: int, db: AsyncSession) -> Goal:
    result = await db.execute(
        select(Goal)
        .options(
            selectinload(Goal.members).selectinload(GoalMember.user),
            selectinload(Goal.deposits).selectinload(GoalDeposit.depositor),
        )
        .where(Goal.id == goal_id)
    )
    return result.scalar_one_or_none()


@router.get("/", response_model=List[GoalResponse])
async def list_goals(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    member_goal_ids_result = await db.execute(
        select(GoalMember.goal_id).where(GoalMember.user_id == current_user.id)
    )
    member_goal_ids = [row[0] for row in member_goal_ids_result.fetchall()]

    result = await db.execute(
        select(Goal)
        .options(
            selectinload(Goal.members).selectinload(GoalMember.user),
            selectinload(Goal.deposits).selectinload(GoalDeposit.depositor),
        )
        .where(
            or_(
                Goal.creator_id == current_user.id,
                Goal.id.in_(member_goal_ids),
            )
        )
    )
    return result.scalars().all()


@router.post("/", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    data: GoalCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    goal = Goal(
        creator_id=current_user.id,
        name=data.name,
        goal_type=data.goal_type,
        target_amount=data.target_amount,
        currency=data.currency,
        target_date=data.target_date,
        frequency=data.frequency,
        deposit_amount=data.deposit_amount,
        account_name=data.account_name,
        bank_name=data.bank_name,
        account_number_masked=data.account_number_masked,
        emoji=data.emoji,
        status="active",
        current_amount=Decimal("0"),
    )
    db.add(goal)
    await db.flush()

    # Add creator as member
    member = GoalMember(
        goal_id=goal.id,
        user_id=current_user.id,
        split_percent=Decimal("100") if data.goal_type == "solo" else None,
        target_amount=data.target_amount if data.goal_type == "solo" else None,
    )
    db.add(member)
    await db.commit()

    return await _get_goal_with_relations(goal.id, db)


@router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(
    goal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    goal = await _get_goal_with_relations(goal_id, db)
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found"
        )

    is_member = any(m.user_id == current_user.id for m in goal.members)
    if goal.creator_id != current_user.id and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    return goal


@router.put("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: int,
    data: GoalUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Goal).where(Goal.id == goal_id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found"
        )
    if goal.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only creator can update goal"
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(goal, field, value)
    goal.updated_at = datetime.utcnow()

    await db.commit()
    return await _get_goal_with_relations(goal_id, db)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Goal).where(Goal.id == goal_id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found"
        )
    if goal.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only creator can delete goal"
        )

    await db.delete(goal)
    await db.commit()


@router.post(
    "/{goal_id}/invite",
    response_model=GoalMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    goal_id: int,
    user_id: int,
    split_percent: float = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    result = await db.execute(select(Goal).where(Goal.id == goal_id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found"
        )
    if goal.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creator can invite members",
        )
    if goal.goal_type != "group":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only invite to group goals",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    invited_user = result.scalar_one_or_none()
    if not invited_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    existing = await db.execute(
        select(GoalMember).where(
            GoalMember.goal_id == goal_id, GoalMember.user_id == user_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User already a member"
        )

    member = GoalMember(
        goal_id=goal_id,
        user_id=user_id,
        split_percent=Decimal(str(split_percent)) if split_percent else None,
        target_amount=(
            (goal.target_amount * Decimal(str(split_percent)) / 100)
            if split_percent
            else None
        ),
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    result = await db.execute(
        select(GoalMember)
        .options(selectinload(GoalMember.user))
        .where(GoalMember.id == member.id)
    )
    return result.scalar_one()


@router.get("/{goal_id}/members", response_model=List[GoalMemberResponse])
async def list_members(
    goal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(GoalMember)
        .options(selectinload(GoalMember.user))
        .where(GoalMember.goal_id == goal_id)
    )
    return result.scalars().all()


@router.get("/{goal_id}/deposits", response_model=List[GoalDepositResponse])
async def list_deposits(
    goal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(GoalDeposit)
        .options(selectinload(GoalDeposit.depositor))
        .where(GoalDeposit.goal_id == goal_id)
        .order_by(GoalDeposit.created_at.desc())
    )
    return result.scalars().all()


@router.post(
    "/{goal_id}/deposits",
    response_model=GoalDepositResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_deposit(
    goal_id: int,
    amount: Annotated[str, Form()],
    proof_type: Annotated[str | None, Form()] = None,
    note: Annotated[str | None, Form()] = None,
    deposited_at: Annotated[str | None, Form()] = None,
    proof_file: Annotated[UploadFile | None, File()] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    result = await db.execute(select(Goal).where(Goal.id == goal_id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found"
        )

    # Check membership
    member_check = await db.execute(
        select(GoalMember).where(
            GoalMember.goal_id == goal_id, GoalMember.user_id == current_user.id
        )
    )
    if not member_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this goal"
        )

    deposit_amount = Decimal(amount)
    proof_file_path = None

    if proof_file:
        ext = (
            os.path.splitext(proof_file.filename)[1] if proof_file.filename else ".jpg"
        )
        filename = f"{uuid.uuid4()}{ext}"
        proof_dir = os.path.join(settings.UPLOAD_DIR, "goal_proofs")
        os.makedirs(proof_dir, exist_ok=True)
        file_path = os.path.join(proof_dir, filename)
        content = await proof_file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        proof_file_path = f"/uploads/goal_proofs/{filename}"

    parsed_deposited_at = None
    if deposited_at:
        try:
            parsed_deposited_at = datetime.fromisoformat(deposited_at)
        except ValueError:
            parsed_deposited_at = datetime.utcnow()

    deposit = GoalDeposit(
        goal_id=goal_id,
        depositor_id=current_user.id,
        amount=deposit_amount,
        proof_type=proof_type,
        proof_file_path=proof_file_path,
        note=note,
        deposited_at=parsed_deposited_at or datetime.utcnow(),
    )
    db.add(deposit)

    # Update goal current_amount
    goal.current_amount = (goal.current_amount or Decimal("0")) + deposit_amount
    if goal.current_amount >= goal.target_amount:
        goal.status = "completed"
    goal.updated_at = datetime.utcnow()

    # Update member contributed_amount
    member_result = await db.execute(
        select(GoalMember).where(
            GoalMember.goal_id == goal_id, GoalMember.user_id == current_user.id
        )
    )
    member = member_result.scalar_one_or_none()
    if member:
        member.contributed_amount = (
            member.contributed_amount or Decimal("0")
        ) + deposit_amount

    await db.commit()
    await db.refresh(deposit)

    result = await db.execute(
        select(GoalDeposit)
        .options(selectinload(GoalDeposit.depositor))
        .where(GoalDeposit.id == deposit.id)
    )
    return result.scalar_one()
