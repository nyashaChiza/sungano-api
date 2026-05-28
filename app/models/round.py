from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime


class Round(Base):
    __tablename__ = "rounds"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    contribution_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    frequency = Column(String(20), nullable=False)  # weekly/biweekly/monthly
    total_cycles = Column(Integer, nullable=False)
    grace_period_days = Column(Integer, default=3)
    status = Column(
        String(20), nullable=False, default="pending"
    )  # pending/active/completed/dissolved
    start_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    creator = relationship(
        "User", back_populates="created_rounds", foreign_keys=[creator_id]
    )
    members = relationship(
        "RoundMember", back_populates="round", cascade="all, delete-orphan"
    )
    cycles = relationship(
        "Cycle",
        back_populates="round",
        cascade="all, delete-orphan",
        order_by="Cycle.cycle_number",
    )


class RoundMember(Base):
    __tablename__ = "round_members"

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    payout_position = Column(Integer, nullable=True)
    signed_at = Column(DateTime, nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow)

    round = relationship("Round", back_populates="members")
    user = relationship("User", back_populates="round_memberships")


class Cycle(Base):
    __tablename__ = "cycles"

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False)
    cycle_number = Column(Integer, nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    due_date = Column(DateTime, nullable=True)
    is_complete = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)

    round = relationship("Round", back_populates="cycles")
    recipient = relationship("User", foreign_keys=[recipient_id])
    payments = relationship(
        "Payment", back_populates="cycle", cascade="all, delete-orphan"
    )


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("cycles.id"), nullable=False)
    payer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(
        String(20), nullable=False, default="pending"
    )  # pending/submitted/confirmed/overdue/grace/defaulted
    proof_type = Column(String(50), nullable=True)
    proof_file_path = Column(String, nullable=True)
    note = Column(String, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    confirmed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cycle = relationship("Cycle", back_populates="payments")
    payer = relationship("User", foreign_keys=[payer_id])
    confirmed_by = relationship("User", foreign_keys=[confirmed_by_id])
