from typing import Annotated, List
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, DeviceToken
from app.models.notification import Reminder, ActivityLog
from app.schemas.user import DeviceTokenCreate
from pydantic import BaseModel

router = APIRouter()


class ReminderResponse(BaseModel):
    id: UUID
    user_id: UUID
    type: str
    channel: str
    reference_id: UUID | None = None
    reference_type: str | None = None
    payload: dict | None = None
    scheduled_at: datetime
    sent_at: datetime | None = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


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


@router.get("/notifications", response_model=List[ReminderResponse])
async def list_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 50,
):
    """List reminders/notifications (paginated, recent first)"""
    result = await db.execute(
        select(Reminder)
        .where(Reminder.user_id == current_user.id)
        .order_by(desc(Reminder.scheduled_at))
        .offset(skip)
        .limit(limit)
    )
    reminders = result.scalars().all()
    return reminders


@router.post("/device-token", status_code=status.HTTP_201_CREATED)
async def register_device_token(
    token_data: DeviceTokenCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Register device token for push notifications"""
    # Check if exists
    result = await db.execute(
        select(DeviceToken).where(
            DeviceToken.user_id == current_user.id,
            DeviceToken.expo_token == token_data.expo_token,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.is_active = True
        db.add(existing)
    else:
        device_token = DeviceToken(
            user_id=current_user.id,
            expo_token=token_data.expo_token,
            device_type=token_data.device_type,
            is_active=True,
        )
        db.add(device_token)

    await db.flush()
    return {"message": "Device token registered"}


@router.put("/{notification_id}/read", response_model=ReminderResponse)
async def mark_notification_read(
    notification_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Mark notification as read"""
    result = await db.execute(
        select(Reminder).where(
            Reminder.id == notification_id,
            Reminder.user_id == current_user.id,
        )
    )
    reminder = result.scalar_one_or_none()

    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    reminder.status = "read"
    db.add(reminder)
    await db.flush()

    return reminder


@router.put("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_notifications_read(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Mark all notifications as read"""
    result = await db.execute(
        select(Reminder).where(
            Reminder.user_id == current_user.id,
            Reminder.status != "read",
        )
    )
    reminders = result.scalars().all()

    for reminder in reminders:
        reminder.status = "read"
        db.add(reminder)

    await db.flush()
    return None
