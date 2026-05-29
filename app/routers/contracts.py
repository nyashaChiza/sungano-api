from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.round import Round, RoundMember
from app.models.contract import Contract, ContractSignature
from app.schemas.contract import (
    ContractResponse, ContractSignatureResponse, SignContractRequest
)

router = APIRouter()


async def _load_contract_with_relations(contract_id: UUID, db: AsyncSession) -> Contract:
    """Load contract with all signatures"""
    result = await db.execute(
        select(Contract)
        .options(selectinload(Contract.signatures))
        .where(Contract.id == contract_id)
    )
    return result.scalar_one_or_none()


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get contract details"""
    try:
        contract_uuid = UUID(contract_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid contract ID")

    contract = await _load_contract_with_relations(contract_uuid, db)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    # Verify user has access to this round
    result = await db.execute(
        select(Round).where(Round.id == contract.round_id)
    )
    round_obj = result.scalar_one_or_none()
    if not round_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")

    is_member = await db.execute(
        select(RoundMember).where(
            RoundMember.round_id == round_obj.id,
            RoundMember.user_id == current_user.id,
        )
    )
    if round_obj.created_by != current_user.id and not is_member.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return ContractResponse.from_orm(contract)


@router.get("/{contract_id}/pdf-url")
async def get_contract_pdf_url(
    contract_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get signed URL for contract PDF"""
    try:
        contract_uuid = UUID(contract_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid contract ID")

    result = await db.execute(
        select(Contract).where(Contract.id == contract_uuid)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    # Verify access
    result = await db.execute(
        select(Round).where(Round.id == contract.round_id)
    )
    round_obj = result.scalar_one_or_none()

    is_member = await db.execute(
        select(RoundMember).where(
            RoundMember.round_id == round_obj.id,
            RoundMember.user_id == current_user.id,
        )
    )
    if round_obj.created_by != current_user.id and not is_member.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if not contract.pdf_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF not yet generated")

    return {"pdf_url": contract.pdf_url}


@router.post("/{contract_id}/sign", response_model=ContractSignatureResponse, status_code=status.HTTP_201_CREATED)
async def sign_contract(
    contract_id: str,
    data: SignContractRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Sign a contract"""
    try:
        contract_uuid = UUID(contract_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid contract ID")

    # Load contract and verify round access
    result = await db.execute(
        select(Contract).where(Contract.id == contract_uuid)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    # Verify user is a round member
    result = await db.execute(
        select(RoundMember).where(
            RoundMember.round_id == contract.round_id,
            RoundMember.user_id == current_user.id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this round")

    # Check if already signed
    existing = await db.execute(
        select(ContractSignature).where(
            ContractSignature.contract_id == contract_uuid,
            ContractSignature.user_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already signed this contract")

    # Create signature
    signature = ContractSignature(
        contract_id=contract_uuid,
        user_id=current_user.id,
        signed_at=datetime.utcnow(),
        ip_address=data.ip_address,
        signature_data=data.signature_data,
    )
    db.add(signature)

    # Update member's contract_signed_at
    member.contract_signed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(signature)

    return ContractSignatureResponse.from_orm(signature)


@router.get("/{contract_id}/signatures", response_model=list[ContractSignatureResponse])
async def list_signatures(
    contract_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all signatures on a contract"""
    try:
        contract_uuid = UUID(contract_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid contract ID")

    result = await db.execute(
        select(Contract).where(Contract.id == contract_uuid)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    # Verify access
    result = await db.execute(
        select(Round).where(Round.id == contract.round_id)
    )
    round_obj = result.scalar_one_or_none()

    is_member = await db.execute(
        select(RoundMember).where(
            RoundMember.round_id == round_obj.id,
            RoundMember.user_id == current_user.id,
        )
    )
    if round_obj.created_by != current_user.id and not is_member.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(
        select(ContractSignature)
        .where(ContractSignature.contract_id == contract_uuid)
        .order_by(ContractSignature.signed_at)
    )
    return result.scalars().all()
