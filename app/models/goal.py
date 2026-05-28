from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    goal_type = Column(String(20), nullable=False, default="solo")  # solo/group
    target_amount = Column(Numeric(12, 2), nullable=False)
    current_amount = Column(Numeric(12, 2), default=0)
    currency = Column(String(10), nullable=False, default="USD")
    target_date = Column(DateTime, nullable=True)
    frequency = Column(String(20), nullable=True)  # weekly/biweekly/monthly
    deposit_amount = Column(Numeric(12, 2), nullable=True)
    status = Column(
        String(20), nullable=False, default="active"
    )  # active/completed/paused/cancelled
    account_name = Column(String, nullable=True)
    bank_name = Column(String, nullable=True)
    account_number_masked = Column(String, nullable=True)
    emoji = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = relationship(
        "User", back_populates="created_goals", foreign_keys=[creator_id]
    )
    members = relationship(
        "GoalMember", back_populates="goal", cascade="all, delete-orphan"
    )
    deposits = relationship(
        "GoalDeposit", back_populates="goal", cascade="all, delete-orphan"
    )


class GoalMember(Base):
    __tablename__ = "goal_members"

    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    split_percent = Column(Numeric(5, 2), nullable=True)
    target_amount = Column(Numeric(12, 2), nullable=True)
    contributed_amount = Column(Numeric(12, 2), default=0)
    joined_at = Column(DateTime, default=datetime.utcnow)

    goal = relationship("Goal", back_populates="members")
    user = relationship("User", back_populates="goal_memberships")


class GoalDeposit(Base):
    __tablename__ = "goal_deposits"

    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=False)
    depositor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    proof_type = Column(String(50), nullable=True)
    proof_file_path = Column(String, nullable=True)
    note = Column(String, nullable=True)
    deposited_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    goal = relationship("Goal", back_populates="deposits")
    depositor = relationship("User", foreign_keys=[depositor_id])
