from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from app.schemas.user import UserResponse


class RoundCreate(BaseModel):
    name: str
    contribution_amount: Decimal
    currency: str = "USD"
    frequency: str  # weekly/biweekly/monthly
    total_cycles: int
    grace_period_days: Optional[int] = 3
    start_date: Optional[datetime] = None


class RoundUpdate(BaseModel):
    name: Optional[str] = None
    contribution_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    frequency: Optional[str] = None
    total_cycles: Optional[int] = None
    grace_period_days: Optional[int] = None
    start_date: Optional[datetime] = None


class RoundMemberResponse(BaseModel):
    id: int
    user_id: int
    round_id: int
    payout_position: Optional[int] = None
    signed_at: Optional[datetime] = None
    joined_at: datetime
    user: Optional[UserResponse] = None

    model_config = {"from_attributes": True}


class PaymentCreate(BaseModel):
    amount: Decimal
    proof_type: Optional[str] = None


class SubmitProofRequest(BaseModel):
    proof_type: str
    note: str = ""


class PaymentResponse(BaseModel):
    id: int
    cycle_id: int
    payer_id: int
    amount: Decimal
    status: str
    proof_type: Optional[str] = None
    proof_file_path: Optional[str] = None
    note: Optional[str] = None
    submitted_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    confirmed_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    payer: Optional[UserResponse] = None

    model_config = {"from_attributes": True}


class CycleResponse(BaseModel):
    id: int
    round_id: int
    cycle_number: int
    recipient_id: Optional[int] = None
    due_date: Optional[datetime] = None
    is_complete: bool
    completed_at: Optional[datetime] = None
    payments: List[PaymentResponse] = []
    recipient: Optional[UserResponse] = None

    model_config = {"from_attributes": True}


class RoundResponse(BaseModel):
    id: int
    name: str
    creator_id: int
    contribution_amount: Decimal
    currency: str
    frequency: str
    total_cycles: int
    grace_period_days: int
    status: str
    start_date: Optional[datetime] = None
    created_at: datetime
    members: List[RoundMemberResponse] = []
    current_cycle: Optional[CycleResponse] = None

    model_config = {"from_attributes": True}
