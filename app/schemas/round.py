from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID


class RoundMemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    round_id: UUID
    payout_position: Optional[int] = None
    contract_signed_at: Optional[datetime] = None
    invite_status: str
    is_active: bool
    joined_at: datetime

    model_config = {"from_attributes": True}


class RoundMemberDetailResponse(RoundMemberResponse):
    trust_score: Optional[Decimal] = None


class RoundCreate(BaseModel):
    name: str
    contribution_amount: Decimal
    currency: Optional[str] = "USD"
    cycle_frequency: str  # weekly/biweekly/monthly
    total_cycles: int
    start_date: date
    payout_order_method: str  # random/custom
    grace_period_days: Optional[int] = 3
    late_penalty_amount: Optional[Decimal] = 0
    default_penalty: Optional[str] = None
    collateral_required: Optional[bool] = False
    contract_mode: Optional[str] = "simple"


class RoundUpdate(BaseModel):
    name: Optional[str] = None
    contribution_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    grace_period_days: Optional[int] = None


class CyclePaymentResponse(BaseModel):
    id: UUID
    cycle_id: UUID
    payer_id: UUID
    amount: Decimal
    due_date: date
    paid_at: Optional[datetime] = None
    proof_url: Optional[str] = None
    proof_type: Optional[str] = None
    note: Optional[str] = None
    status: str
    confirmed_at: Optional[datetime] = None
    auto_confirmed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SubmitProofRequest(BaseModel):
    proof_type: str
    note: Optional[str] = None


class PaymentConfirmRequest(BaseModel):
    confirmed: bool


class PaymentDisputeRequest(BaseModel):
    reason: str


class RoundCycleResponse(BaseModel):
    id: UUID
    round_id: UUID
    cycle_number: int
    recipient_id: Optional[UUID] = None
    due_date: date
    payout_date: Optional[date] = None
    total_expected: Decimal
    total_received: Decimal
    status: str
    payments: List[CyclePaymentResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class RoundLedgerEntry(BaseModel):
    payment_id: UUID
    cycle_number: int
    payer_id: UUID
    amount: Decimal
    status: str
    paid_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    proof_type: Optional[str] = None


class RoundResponse(BaseModel):
    id: UUID
    name: str
    created_by: UUID
    contribution_amount: Decimal
    currency: str
    cycle_frequency: str
    start_date: date
    total_cycles: int
    payout_order_method: str
    grace_period_days: int
    late_penalty_amount: Decimal
    default_penalty: Optional[str] = None
    collateral_required: bool
    contract_url: Optional[str] = None
    contract_mode: str
    status: str
    created_at: datetime
    updated_at: datetime
    members: List[RoundMemberResponse] = []
    cycles: List[RoundCycleResponse] = []

    model_config = {"from_attributes": True}


class RoundSummaryResponse(BaseModel):
    id: UUID
    name: str
    created_by: UUID
    contribution_amount: Decimal
    currency: str
    cycle_frequency: str
    total_cycles: int
    status: str
    members_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteLinkResponse(BaseModel):
    token: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    uses: int
    max_uses: Optional[int] = None


class PayoutPositionRequest(BaseModel):
    payout_order: dict[UUID, int]  # user_id -> position mapping


class RoundPreviewResponse(BaseModel):
    id: UUID
    name: str
    creator_name: str
    contribution_amount: Decimal
    currency: str
    cycle_frequency: str
    total_cycles: int
    status: str
    members_count: int
    start_date: date
    created_at: datetime

    model_config = {"from_attributes": True}
