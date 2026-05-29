from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class TrustScoreResponse(BaseModel):
    score: Decimal
    total_rounds: int
    completed_rounds: int
    total_payments_due: int
    on_time_payments: int
    late_payments: int
    defaults: int
    disputes_raised: int
    disputes_against: int
    last_calculated_at: datetime

    model_config = {"from_attributes": True}


class PayoutAccountCreate(BaseModel):
    account_name: str
    account_number: Optional[str] = None
    bank_name: Optional[str] = None
    mobile_money: Optional[str] = None
    currency: Optional[str] = "USD"


class PayoutAccountUpdate(BaseModel):
    account_name: Optional[str] = None
    account_number: Optional[str] = None
    bank_name: Optional[str] = None
    mobile_money: Optional[str] = None
    currency: Optional[str] = None
    is_default: Optional[bool] = None


class PayoutAccountResponse(BaseModel):
    id: UUID
    account_name: str
    account_number: Optional[str] = None
    bank_name: Optional[str] = None
    mobile_money: Optional[str] = None
    currency: Optional[str] = None
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DeviceTokenCreate(BaseModel):
    expo_token: str
    device_type: Optional[str] = "android"


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    phone: str

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: str) -> str:
        if len(v.strip()) < 2:
            raise ValueError("Full name must be at least 2 characters")
        return v

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None


class UserResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    phone: str
    profile_photo_url: Optional[str] = None
    is_email_verified: bool
    is_phone_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserProfile(UserResponse):
    trust_score: Optional[TrustScoreResponse] = None
    payout_accounts: list[PayoutAccountResponse] = []

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None
