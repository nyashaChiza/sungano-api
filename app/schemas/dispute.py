from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class DisputeResponse(BaseModel):
    id: UUID
    raised_by: UUID
    against_user: UUID
    payment_id: UUID
    round_id: UUID
    reason: str
    evidence_urls: Optional[List[str]] = []
    status: str
    resolved_by: Optional[UUID] = None
    resolution_note: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DisputeCreate(BaseModel):
    payment_id: UUID
    reason: str
    evidence_urls: Optional[List[str]] = []


class DisputeResolve(BaseModel):
    resolution: str  # "paid" or "default"
    resolution_note: Optional[str] = None
