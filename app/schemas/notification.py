from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class ReminderResponse(BaseModel):
    id: UUID
    user_id: UUID
    type: str
    channel: str
    reference_id: Optional[UUID] = None
    reference_type: Optional[str] = None
    payload: Optional[dict] = None
    scheduled_at: datetime
    sent_at: Optional[datetime] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ReminderCreate(BaseModel):
    type: str
    channel: str
    reference_id: Optional[UUID] = None
    reference_type: Optional[str] = None
    payload: Optional[dict] = None
    scheduled_at: datetime


class ActivityLogResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    actor_id: Optional[UUID] = None
    type: str
    reference_id: Optional[UUID] = None
    reference_type: Optional[str] = None
    message: Optional[str] = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DeviceTokenCreate(BaseModel):
    token: str
    platform: Optional[str] = None  # ios, android, web
