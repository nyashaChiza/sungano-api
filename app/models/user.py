from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    trust_score = relationship("TrustScore", back_populates="user", uselist=False)
    created_rounds = relationship(
        "Round", back_populates="creator", foreign_keys="Round.creator_id"
    )
    round_memberships = relationship("RoundMember", back_populates="user")
    created_goals = relationship(
        "Goal", back_populates="creator", foreign_keys="Goal.creator_id"
    )
    goal_memberships = relationship("GoalMember", back_populates="user")


class TrustScore(Base):
    __tablename__ = "trust_scores"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    score = Column(Integer, default=100)
    rounds_completed = Column(Integer, default=0)
    defaults = Column(Integer, default=0)
    payments_on_time = Column(Integer, default=0)
    payments_total = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="trust_score")
