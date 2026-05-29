from typing import Annotated, List
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.notification import ActivityLog
from pydantic import BaseModel

router = APIRouter()


class ActivityResponse(BaseModel):
    id: UUID
    user_id: UUID | None = None
    actor_id: UUID | None = None
    type: str
    reference_id: UUID | None = None
    reference_type: str | None = None
    message: str | None = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=List[ActivityResponse])
async def list_activity(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 50,
):
    """List activity feed (paginated, most recent first)"""
    result = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.user_id == current_user.id)
        .order_by(desc(ActivityLog.created_at))
        .offset(skip)
        .limit(limit)
    )
    activities = result.scalars().all()
    return activities


@router.put("/{activity_id}/read", response_model=ActivityResponse)
async def mark_activity_read(
    activity_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Mark activity as read"""
    result = await db.execute(
        select(ActivityLog).where(
            ActivityLog.id == activity_id,
            ActivityLog.user_id == current_user.id,
        )
    )
    activity = result.scalar_one_or_none()

    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )

    activity.is_read = True
    db.add(activity)
    await db.flush()

    return activity
