from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class ContractSignatureResponse(BaseModel):
    id: UUID
    contract_id: UUID
    user_id: UUID
    signed_at: datetime
    ip_address: Optional[str] = None
    signature_data: Optional[str] = None

    model_config = {"from_attributes": True}


class ContractResponse(BaseModel):
    id: UUID
    round_id: UUID
    version: int
    content_json: Optional[dict] = None
    pdf_url: Optional[str] = None
    generated_at: datetime
    signatures: list[ContractSignatureResponse] = []

    model_config = {"from_attributes": True}


class SignContractRequest(BaseModel):
    ip_address: Optional[str] = None
    signature_data: Optional[str] = None
