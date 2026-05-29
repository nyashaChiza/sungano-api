from typing import Annotated, Optional
from uuid import UUID
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.round import RoundCycle, CyclePayment, Round, RoundMember
from app.models.dispute import Dispute
from app.schemas.round import CyclePaymentResponse, SubmitProofRequest, PaymentConfirmRequest, PaymentDisputeRequest
from app.services import cloudinary_service

router = APIRouter()


@router.post("/{cycle_id}/payments", response_model=CyclePaymentResponse, status_code=status.HTTP_201_CREATED)
async def submit_payment_proof(
    cycle_id: UUID,
    proof_type: str = Form(...),
    note: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Submit payment proof for a cycle"""
    # Get cycle
    cycle_result = await db.execute(
        select(RoundCycle)
        .where(RoundCycle.id == cycle_id)
        .options(selectinload(RoundCycle.round))
    )
    cycle = cycle_result.scalar_one_or_none()

    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cycle not found",
        )

    # Verify user is member
    round_obj = cycle.round
    is_member = (
        await db.execute(
            select(RoundMember).where(
                and_(
                    RoundMember.round_id == round_obj.id,
                    RoundMember.user_id == current_user.id,
                )
            )
        )
    ).scalar_one_or_none()

    if not is_member and round_obj.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this round",
        )

    # Check if payment exists
    payment_result = await db.execute(
        select(CyclePayment).where(
            and_(
                CyclePayment.cycle_id == cycle_id,
                CyclePayment.payer_id == current_user.id,
            )
        )
    )
    payment = payment_result.scalar_one_or_none()

    if not payment:
        # Create new payment
        payment = CyclePayment(
            cycle_id=cycle_id,
            round_id=round_obj.id,
            payer_id=current_user.id,
            amount=round_obj.contribution_amount,
            due_date=cycle.due_date,
            proof_type=proof_type,
            note=note,
            status="submitted",
            paid_at=datetime.utcnow(),
        )
    else:
        # Update existing
        payment.proof_type = proof_type
        payment.note = note
        payment.status = "submitted"
        payment.paid_at = datetime.utcnow()

    # Upload proof file if provided
    if file:
        file_bytes = await file.read()
        public_id = await cloudinary_service.upload_payment_proof(
            round_obj.id,
            cycle_id,
            current_user.id,
            file_bytes,
            proof_type,
        )
        proof_url = cloudinary_service.get_signed_url(public_id)
        payment.proof_url = proof_url

        # Store metadata
        import json
        payment.proof_metadata = {
            "upload_timestamp": datetime.utcnow().isoformat(),
            "file_size": len(file_bytes),
            "file_format": file.content_type or "unknown",
            "device_type": "mobile",
        }

    db.add(payment)
    await db.flush()

    return CyclePaymentResponse(
        id=payment.id,
        cycle_id=payment.cycle_id,
        payer_id=payment.payer_id,
        amount=payment.amount,
        due_date=payment.due_date,
        paid_at=payment.paid_at,
        proof_url=payment.proof_url,
        proof_type=payment.proof_type,
        note=payment.note,
        status=payment.status,
        confirmed_at=payment.confirmed_at,
        auto_confirmed=payment.auto_confirmed,
        created_at=payment.created_at,
    )


@router.put("/{payment_id}/confirm", response_model=CyclePaymentResponse)
async def confirm_payment(
    payment_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Recipient confirms payment"""
    # Get payment
    payment_result = await db.execute(
        select(CyclePayment)
        .where(CyclePayment.id == payment_id)
        .options(
            selectinload(CyclePayment.cycle).selectinload(RoundCycle.round),
        )
    )
    payment = payment_result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    cycle = payment.cycle
    round_obj = cycle.round

    # Verify current user is recipient or round creator
    is_recipient = cycle.recipient_id == current_user.id
    is_creator = round_obj.created_by == current_user.id

    if not is_recipient and not is_creator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to confirm this payment",
        )

    # Confirm payment
    payment.status = "confirmed"
    payment.confirmed_at = datetime.utcnow()
    payment.confirmed_by = current_user.id
    payment.dispute_window_ends = datetime.utcnow() + timedelta(hours=24)

    db.add(payment)
    await db.flush()

    return CyclePaymentResponse(
        id=payment.id,
        cycle_id=payment.cycle_id,
        payer_id=payment.payer_id,
        amount=payment.amount,
        due_date=payment.due_date,
        paid_at=payment.paid_at,
        proof_url=payment.proof_url,
        proof_type=payment.proof_type,
        note=payment.note,
        status=payment.status,
        confirmed_at=payment.confirmed_at,
        auto_confirmed=payment.auto_confirmed,
        created_at=payment.created_at,
    )


@router.put("/{payment_id}/dispute", response_model=CyclePaymentResponse)
async def dispute_payment(
    payment_id: UUID,
    dispute_data: PaymentDisputeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Raise dispute on payment"""
    # Get payment
    payment_result = await db.execute(
        select(CyclePayment)
        .where(CyclePayment.id == payment_id)
        .options(
            selectinload(CyclePayment.cycle).selectinload(RoundCycle.round),
            selectinload(CyclePayment.payer),
        )
    )
    payment = payment_result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    cycle = payment.cycle
    round_obj = cycle.round

    # Verify user is round member (not payer)
    is_member = (
        await db.execute(
            select(RoundMember).where(
                and_(
                    RoundMember.round_id == round_obj.id,
                    RoundMember.user_id == current_user.id,
                )
            )
        )
    ).scalar_one_or_none()

    if not is_member or current_user.id == payment.payer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only other members can dispute payments",
        )

    # Check if within dispute window
    if payment.dispute_window_ends and datetime.utcnow() > payment.dispute_window_ends:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dispute window has closed",
        )

    # Create dispute
    dispute = Dispute(
        raised_by=current_user.id,
        against_user=payment.payer_id,
        payment_id=payment_id,
        round_id=round_obj.id,
        reason=dispute_data.reason,
        status="open",
    )
    db.add(dispute)

    # Mark payment as disputed
    payment.status = "disputed"
    db.add(payment)
    await db.flush()

    return CyclePaymentResponse(
        id=payment.id,
        cycle_id=payment.cycle_id,
        payer_id=payment.payer_id,
        amount=payment.amount,
        due_date=payment.due_date,
        paid_at=payment.paid_at,
        proof_url=payment.proof_url,
        proof_type=payment.proof_type,
        note=payment.note,
        status=payment.status,
        confirmed_at=payment.confirmed_at,
        auto_confirmed=payment.auto_confirmed,
        created_at=payment.created_at,
    )


@router.get("/{payment_id}", response_model=CyclePaymentResponse)
async def get_payment(
    payment_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get payment detail with signed URL"""
    payment_result = await db.execute(
        select(CyclePayment)
        .where(CyclePayment.id == payment_id)
        .options(
            selectinload(CyclePayment.cycle).selectinload(RoundCycle.round),
        )
    )
    payment = payment_result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    # Verify access
    round_obj = payment.cycle.round
    is_creator = round_obj.created_by == current_user.id
    is_member = (
        await db.execute(
            select(RoundMember).where(
                and_(
                    RoundMember.round_id == round_obj.id,
                    RoundMember.user_id == current_user.id,
                )
            )
        )
    ).scalar_one_or_none()

    if not is_creator and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Generate signed URL if proof exists
    proof_url = payment.proof_url
    if proof_url and "cloudinary" in proof_url:
        # Extract public_id and regenerate signed URL with 1 hour expiry
        # For now, use existing URL
        pass

    return CyclePaymentResponse(
        id=payment.id,
        cycle_id=payment.cycle_id,
        payer_id=payment.payer_id,
        amount=payment.amount,
        due_date=payment.due_date,
        paid_at=payment.paid_at,
        proof_url=proof_url,
        proof_type=payment.proof_type,
        note=payment.note,
        status=payment.status,
        confirmed_at=payment.confirmed_at,
        auto_confirmed=payment.auto_confirmed,
        created_at=payment.created_at,
    )
