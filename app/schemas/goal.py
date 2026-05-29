from pydantic import BaseModel, computed_field
from typing import Optional, List
from datetime import datetime, timezone, date
from decimal import Decimal
from uuid import UUID


class GoalMemberResponse(BaseModel):
    id: UUID
    goal_id: UUID
    user_id: UUID
    split_percent: Optional[Decimal] = None
    target_amount: Optional[Decimal] = None
    contributed: Decimal = Decimal("0")
    invite_status: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class GoalDepositResponse(BaseModel):
    id: UUID
    goal_id: UUID
    user_id: UUID
    amount: Decimal
    proof_url: Optional[str] = None
    proof_type: Optional[str] = None
    note: Optional[str] = None
    deposited_at: datetime
    status: str
    confirmed_at: Optional[datetime] = None
    confirmed_by: Optional[UUID] = None
    rejection_note: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class GoalCreate(BaseModel):
    name: str
    target_amount: Decimal
    currency: Optional[str] = "USD"
    target_date: date
    goal_type: Optional[str] = "solo"
    suggested_frequency: Optional[str] = None
    suggested_amount: Optional[Decimal] = None
    target_account_id: Optional[UUID] = None


class GoalUpdate(BaseModel):
    name: Optional[str] = None
    target_amount: Optional[Decimal] = None
    target_date: Optional[date] = None


class GoalDepositCreate(BaseModel):
    amount: Decimal
    proof_type: Optional[str] = None
    note: Optional[str] = None


class GoalDepositConfirmRequest(BaseModel):
    confirmed: bool


class GoalInviteRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    split_percent: Optional[Decimal] = None
    target_amount: Optional[Decimal] = None


class GoalResponse(BaseModel):
    id: UUID
    name: str
    created_by: UUID
    target_amount: Decimal
    currency: str
    target_date: date
    goal_type: str
    suggested_frequency: Optional[str] = None
    suggested_amount: Optional[Decimal] = None
    current_total: Decimal
    target_account_id: Optional[UUID] = None
    status: str
    created_at: datetime
    updated_at: datetime
    members: List[GoalMemberResponse] = []
    deposits: List[GoalDepositResponse] = []

    @computed_field
    @property
    def progress_percent(self) -> Decimal:
        if self.target_amount and self.target_amount > 0:
            return (self.current_total / self.target_amount * 100).quantize(Decimal("0.01"))
        return Decimal("0")

    @computed_field
    @property
    def days_remaining(self) -> int:
        today = date.today()
        delta = self.target_date - today
        return max(0, delta.days)

    model_config = {"from_attributes": True}


class GoalSummaryResponse(BaseModel):
    id: UUID
    name: str
    created_by: UUID
    target_amount: Decimal
    currency: str
    target_date: date
    current_total: Decimal
    status: str
    members_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
