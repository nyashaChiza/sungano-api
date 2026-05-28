from pydantic import BaseModel, computed_field
from typing import Optional, List
from datetime import datetime, timezone
from decimal import Decimal
from app.schemas.user import UserResponse


class GoalCreate(BaseModel):
    name: str
    goal_type: str = "solo"  # solo/group
    target_amount: Decimal
    currency: str = "USD"
    target_date: Optional[datetime] = None
    frequency: Optional[str] = None
    deposit_amount: Optional[Decimal] = None
    account_name: Optional[str] = None
    bank_name: Optional[str] = None
    account_number_masked: Optional[str] = None
    emoji: Optional[str] = None


class GoalUpdate(BaseModel):
    name: Optional[str] = None
    goal_type: Optional[str] = None
    target_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    target_date: Optional[datetime] = None
    frequency: Optional[str] = None
    deposit_amount: Optional[Decimal] = None
    status: Optional[str] = None
    account_name: Optional[str] = None
    bank_name: Optional[str] = None
    account_number_masked: Optional[str] = None
    emoji: Optional[str] = None


class GoalMemberResponse(BaseModel):
    id: int
    goal_id: int
    user_id: int
    split_percent: Optional[Decimal] = None
    target_amount: Optional[Decimal] = None
    contributed_amount: Decimal = Decimal("0")
    joined_at: datetime
    user: Optional[UserResponse] = None

    model_config = {"from_attributes": True}


class GoalDepositCreate(BaseModel):
    amount: Decimal
    proof_type: Optional[str] = None
    deposited_at: Optional[datetime] = None
    note: Optional[str] = None


class GoalDepositResponse(BaseModel):
    id: int
    goal_id: int
    depositor_id: int
    amount: Decimal
    proof_type: Optional[str] = None
    proof_file_path: Optional[str] = None
    note: Optional[str] = None
    deposited_at: Optional[datetime] = None
    created_at: datetime
    depositor: Optional[UserResponse] = None

    model_config = {"from_attributes": True}


class GoalResponse(BaseModel):
    id: int
    creator_id: int
    name: str
    goal_type: str
    target_amount: Decimal
    current_amount: Decimal
    currency: str
    target_date: Optional[datetime] = None
    frequency: Optional[str] = None
    deposit_amount: Optional[Decimal] = None
    status: str
    account_name: Optional[str] = None
    bank_name: Optional[str] = None
    account_number_masked: Optional[str] = None
    emoji: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    members: List[GoalMemberResponse] = []

    @computed_field
    @property
    def progress_pct(self) -> float:
        if self.target_amount and self.target_amount > 0:
            return round(
                float(self.current_amount) / float(self.target_amount) * 100, 2
            )
        return 0.0

    @computed_field
    @property
    def days_left(self) -> Optional[int]:
        if self.target_date:
            now = datetime.now(timezone.utc)
            target = self.target_date
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            delta = target - now
            return max(0, delta.days)
        return None

    @computed_field
    @property
    def deposits_completed(self) -> int:
        if self.deposit_amount and self.deposit_amount > 0:
            return int(float(self.current_amount) // float(self.deposit_amount))
        return 0

    @computed_field
    @property
    def deposits_remaining(self) -> Optional[int]:
        if self.deposit_amount and self.deposit_amount > 0 and self.target_amount:
            total_deposits = int(
                float(self.target_amount) // float(self.deposit_amount)
            )
            return max(0, total_deposits - self.deposits_completed)
        return None

    model_config = {"from_attributes": True}
