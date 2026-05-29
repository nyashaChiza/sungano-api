import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    profile_photo_url = Column(Text, nullable=True)
    is_email_verified = Column(Boolean, default=False)
    is_phone_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    trust_score = relationship("TrustScore", back_populates="user", uselist=False)
    device_tokens = relationship("DeviceToken", back_populates="user", cascade="all, delete-orphan")
    payout_accounts = relationship("PayoutAccount", back_populates="user", cascade="all, delete-orphan")
    verification_tokens = relationship("VerificationToken", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class VerificationToken(Base):
    __tablename__ = "verification_tokens"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(10), nullable=False)
    type = Column(String(30), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="verification_tokens")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="refresh_tokens")


class DeviceToken(Base):
    __tablename__ = "device_tokens"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expo_token = Column(Text, nullable=False)
    device_type = Column(String(20), default="android")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="device_tokens")


class TrustScore(Base):
    __tablename__ = "trust_scores"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    score = Column(String, default="100.00")
    total_rounds = Column(String, default="0")
    completed_rounds = Column(String, default="0")
    total_payments_due = Column(String, default="0")
    on_time_payments = Column(String, default="0")
    late_payments = Column(String, default="0")
    defaults = Column(String, default="0")
    disputes_raised = Column(String, default="0")
    disputes_against = Column(String, default="0")
    last_calculated_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="trust_score")


class PayoutAccount(Base):
    __tablename__ = "payout_accounts"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(), ForeignKey("users.id"), nullable=False)
    account_name = Column(String(100), nullable=False)
    account_number = Column(String(50), nullable=True)
    bank_name = Column(String(100), nullable=True)
    mobile_money = Column(String(50), nullable=True)
    currency = Column(String(10), nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="payout_accounts")
