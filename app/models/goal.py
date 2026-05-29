import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Numeric, Text, Date, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Goal(Base):
    __tablename__ = "goals"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    created_by = Column(Uuid(), ForeignKey("users.id"), nullable=False)
    target_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="USD")
    target_date = Column(Date, nullable=False)
    goal_type = Column(String(10), default="solo")
    suggested_frequency = Column(String(20), nullable=True)
    suggested_amount = Column(Numeric(12, 2), nullable=True)
    current_total = Column(Numeric(12, 2), default=0)
    target_account_id = Column(Uuid(), ForeignKey("payout_accounts.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    creator = relationship("User", foreign_keys=[created_by])
    members = relationship("GoalMember", back_populates="goal", cascade="all, delete-orphan")
    deposits = relationship("GoalDeposit", back_populates="goal", cascade="all, delete-orphan")


class GoalMember(Base):
    __tablename__ = "goal_members"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    goal_id = Column(Uuid(), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Uuid(), ForeignKey("users.id"), nullable=False)
    split_percent = Column(Numeric(5, 2), nullable=True)
    target_amount = Column(Numeric(12, 2), nullable=True)
    contributed = Column(Numeric(12, 2), default=0)
    invite_status = Column(String(20), default="pending")
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("goal_id", "user_id"),)
    goal = relationship("Goal", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])


class GoalDeposit(Base):
    __tablename__ = "goal_deposits"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    goal_id = Column(Uuid(), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Uuid(), ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    proof_url = Column(Text, nullable=True)
    proof_type = Column(String(20), nullable=True)
    note = Column(Text, nullable=True)
    deposited_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20), default="pending")
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_by = Column(Uuid(), ForeignKey("users.id"), nullable=True)
    rejection_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    goal = relationship("Goal", back_populates="deposits")
    depositor = relationship("User", foreign_keys=[user_id])
    confirmer = relationship("User", foreign_keys=[confirmed_by])
