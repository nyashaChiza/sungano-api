import uuid
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Uuid, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Dispute(Base):
    __tablename__ = "disputes"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    raised_by = Column(Uuid(), ForeignKey("users.id"), nullable=False)
    against_user = Column(Uuid(), ForeignKey("users.id"), nullable=True)
    payment_id = Column(Uuid(), ForeignKey("cycle_payments.id"), nullable=True)
    round_id = Column(Uuid(), ForeignKey("rounds.id"), nullable=True)
    reason = Column(Text, nullable=False)
    evidence_urls = Column(JSON, nullable=True)
    status = Column(String(20), default="open")
    resolved_by = Column(Uuid(), ForeignKey("users.id"), nullable=True)
    resolution_note = Column(Text, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    raiser = relationship("User", foreign_keys=[raised_by])
    accused = relationship("User", foreign_keys=[against_user])
    resolver = relationship("User", foreign_keys=[resolved_by])
