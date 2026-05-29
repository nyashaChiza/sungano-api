import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Numeric, Integer, Text, Date, ForeignKey, UniqueConstraint, Uuid, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Round(Base):
    __tablename__ = "rounds"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    created_by = Column(Uuid(), ForeignKey("users.id"), nullable=False)
    contribution_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="USD")
    cycle_frequency = Column(String(20), nullable=False)
    start_date = Column(Date, nullable=False)
    total_cycles = Column(Integer, nullable=False)
    payout_order_method = Column(String(20), nullable=False)
    grace_period_days = Column(Integer, default=3)
    late_penalty_amount = Column(Numeric(10, 2), default=0)
    default_penalty = Column(Text, nullable=True)
    collateral_required = Column(Boolean, default=False)
    contract_url = Column(Text, nullable=True)
    contract_mode = Column(String(10), default="simple")
    status = Column(String(20), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    creator = relationship("User", foreign_keys=[created_by])
    members = relationship("RoundMember", back_populates="round", cascade="all, delete-orphan")
    cycles = relationship("RoundCycle", back_populates="round", cascade="all, delete-orphan", order_by="RoundCycle.cycle_number")
    contracts = relationship("Contract", back_populates="round", cascade="all, delete-orphan")
    invite_links = relationship("InviteLink", back_populates="round", cascade="all, delete-orphan")


class RoundMember(Base):
    __tablename__ = "round_members"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    round_id = Column(Uuid(), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Uuid(), ForeignKey("users.id"), nullable=False)
    payout_position = Column(Integer, nullable=True)
    collateral_details = Column(Text, nullable=True)
    contract_signed_at = Column(DateTime(timezone=True), nullable=True)
    signature_data = Column(Text, nullable=True)
    invite_status = Column(String(20), default="pending")
    is_active = Column(Boolean, default=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("round_id", "user_id"),
        UniqueConstraint("round_id", "payout_position"),
    )
    round = relationship("Round", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])


class RoundCycle(Base):
    __tablename__ = "round_cycles"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    round_id = Column(Uuid(), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)
    cycle_number = Column(Integer, nullable=False)
    recipient_id = Column(Uuid(), ForeignKey("users.id"), nullable=True)
    due_date = Column(Date, nullable=False)
    payout_date = Column(Date, nullable=True)
    total_expected = Column(Numeric(12, 2), nullable=False)
    total_received = Column(Numeric(12, 2), default=0)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("round_id", "cycle_number"),)
    round = relationship("Round", back_populates="cycles")
    recipient = relationship("User", foreign_keys=[recipient_id])
    payments = relationship("CyclePayment", back_populates="cycle", cascade="all, delete-orphan")


class CyclePayment(Base):
    __tablename__ = "cycle_payments"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    cycle_id = Column(Uuid(), ForeignKey("round_cycles.id", ondelete="CASCADE"), nullable=False)
    round_id = Column(Uuid(), ForeignKey("rounds.id"), nullable=True)
    payer_id = Column(Uuid(), ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    due_date = Column(Date, nullable=False)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    proof_url = Column(Text, nullable=True)
    proof_type = Column(String(20), nullable=True)
    proof_metadata = Column(JSON, nullable=True)
    note = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_by = Column(Uuid(), ForeignKey("users.id"), nullable=True)
    auto_confirmed = Column(Boolean, default=False)
    dispute_window_ends = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("cycle_id", "payer_id"),)
    cycle = relationship("RoundCycle", back_populates="payments")
    payer = relationship("User", foreign_keys=[payer_id])
    confirmer = relationship("User", foreign_keys=[confirmed_by])


class InviteLink(Base):
    __tablename__ = "invite_links"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    round_id = Column(Uuid(), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)
    created_by = Column(Uuid(), ForeignKey("users.id"), nullable=False)
    token = Column(String(32), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    uses = Column(Integer, default=0)
    max_uses = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    round = relationship("Round", back_populates="invite_links")
