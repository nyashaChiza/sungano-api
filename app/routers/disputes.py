from typing import Annotated, List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.dispute import Dispute
from pydantic import BaseModel

router = APIRouter()


class DisputeResponse(BaseModel):
    id: UUID
    raised_by: UUID
    against_user: Optional[UUID] = None
    payment_id: Optional[UUID] = None
    round_id: Optional[UUID] = None
    reason: str
    status: str
    resolved_by: Optional[UUID] = None
    resolution_note: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DisputeResolveRequest(BaseModel):
    status: str
    resolution_note: str


@router.get("/", response_model=List[DisputeResponse])
async def list_disputes(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List disputes for current user"""
    result = await db.execute(
        select(Dispute).where(
            (Dispute.raised_by == current_user.id) | (Dispute.against_user == current_user.id)
        )
        .order_by(Dispute.created_at.desc())
    )
    disputes = result.scalars().all()
    return disputes


@router.get("/{dispute_id}", response_model=DisputeResponse)
async def get_dispute(
    dispute_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get dispute detail"""
    result = await db.execute(
        select(Dispute).where(Dispute.id == dispute_id)
    )
    dispute = result.scalar_one_or_none()

    if not dispute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dispute not found",
        )

    # Check access
    if (dispute.raised_by != current_user.id and
        dispute.against_user != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return dispute


@router.put("/{dispute_id}/resolve", response_model=DisputeResponse)
async def resolve_dispute(
    dispute_id: UUID,
    resolve_data: DisputeResolveRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Resolve dispute (admin only)"""
    # TODO: Check admin role
    result = await db.execute(
        select(Dispute).where(Dispute.id == dispute_id)
    )
    dispute = result.scalar_one_or_none()

    if not dispute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dispute not found",
        )

    # Resolve
    dispute.status = resolve_data.status
    dispute.resolution_note = resolve_data.resolution_note
    dispute.resolved_at = datetime.utcnow()
    dispute.resolved_by = current_user.id

    db.add(dispute)
    await db.flush()

    return dispute
