import uuid
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, Uuid, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Contract(Base):
    __tablename__ = "contracts"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    round_id = Column(Uuid(), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, default=1)
    content_json = Column(JSON, nullable=False)
    pdf_url = Column(Text, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    round = relationship("Round", back_populates="contracts")
    signatures = relationship("ContractSignature", back_populates="contract", cascade="all, delete-orphan")


class ContractSignature(Base):
    __tablename__ = "contract_signatures"
    id = Column(Uuid(), primary_key=True, default=uuid.uuid4)
    contract_id = Column(Uuid(), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Uuid(), ForeignKey("users.id"), nullable=False)
    signed_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45), nullable=True)
    signature_data = Column(Text, nullable=True)
    contract = relationship("Contract", back_populates="signatures")
    user = relationship("User")
