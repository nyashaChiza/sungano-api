import uuid
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Uuid, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Reminder(Base):
    __tablename__ = "reminders"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False)
    channel = Column(String(20), default="both")
    reference_id = Column(Uuid(), nullable=True)
    reference_type = Column(String(20), nullable=True)
    payload = Column(JSON, nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User")


class ActivityLog(Base):
    __tablename__ = "activity_log"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(), ForeignKey("users.id"), nullable=True)
    actor_id = Column(Uuid(), ForeignKey("users.id"), nullable=True)
    type = Column(String(50), nullable=False)
    reference_id = Column(Uuid(), nullable=True)
    reference_type = Column(String(20), nullable=True)
    message = Column(String, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", foreign_keys=[user_id])
    actor = relationship("User", foreign_keys=[actor_id])
