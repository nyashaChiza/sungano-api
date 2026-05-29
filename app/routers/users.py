from typing import Annotated, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, TrustScore, DeviceToken, PayoutAccount
from app.schemas.user import (
    UserResponse,
    UserProfile,
    TrustScoreResponse,
    UserUpdate,
    DeviceTokenCreate,
    PayoutAccountCreate,
    PayoutAccountUpdate,
    PayoutAccountResponse,
)
from app.services import cloudinary_service
from app.services.trust_service import recalculate_and_save_trust_score

router = APIRouter()


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get current user profile with trust score and payout accounts"""
    # Load trust score
    result = await db.execute(
        select(TrustScore).where(TrustScore.user_id == current_user.id)
    )
    trust_score = result.scalar_one_or_none()

    # Load payout accounts
    accounts_result = await db.execute(
        select(PayoutAccount).where(PayoutAccount.user_id == current_user.id)
    )
    accounts = accounts_result.scalars().all()

    return UserProfile(
        **current_user.__dict__,
        trust_score=trust_score,
        payout_accounts=accounts,
    )


@router.put("/me", response_model=UserProfile)
async def update_user_profile(
    update_data: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update current user profile (name, phone, photo)"""
    if update_data.full_name:
        current_user.full_name = update_data.full_name
    if update_data.phone:
        # Check phone uniqueness
        result = await db.execute(
            select(User).where(
                User.phone == update_data.phone,
                User.id != current_user.id,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already in use",
            )
        current_user.phone = update_data.phone

    current_user.updated_at = __import__("datetime").datetime.utcnow()
    db.add(current_user)
    await db.flush()

    # Reload trust score and accounts
    result = await db.execute(
        select(TrustScore).where(TrustScore.user_id == current_user.id)
    )
    trust_score = result.scalar_one_or_none()

    accounts_result = await db.execute(
        select(PayoutAccount).where(PayoutAccount.user_id == current_user.id)
    )
    accounts = accounts_result.scalars().all()

    return UserProfile(
        **current_user.__dict__,
        trust_score=trust_score,
        payout_accounts=accounts,
    )


@router.post("/me/profile-photo", response_model=UserResponse)
async def update_profile_photo(
    file: UploadFile = File(...),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Upload profile photo (via Cloudinary)"""
    file_bytes = await file.read()

    # Upload to Cloudinary
    public_id = await cloudinary_service.upload_profile_photo(
        current_user.id, file_bytes
    )

    # Generate signed URL
    signed_url = cloudinary_service.get_signed_url(public_id)

    # Update user
    current_user.profile_photo_url = signed_url
    current_user.updated_at = __import__("datetime").datetime.utcnow()
    db.add(current_user)
    await db.flush()

    return UserResponse(**current_user.__dict__)


@router.get("/me/trust-score", response_model=TrustScoreResponse)
async def get_current_user_trust_score(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get current user's trust score with detailed breakdown"""
    result = await db.execute(
        select(TrustScore).where(TrustScore.user_id == current_user.id)
    )
    trust_score = result.scalar_one_or_none()

    if not trust_score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trust score not found",
        )

    return trust_score


@router.get("/{user_id}/trust-score", response_model=TrustScoreResponse)
async def get_user_trust_score(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Get another user's trust score (public)"""
    result = await db.execute(
        select(TrustScore).where(TrustScore.user_id == user_id)
    )
    trust_score = result.scalar_one_or_none()

    if not trust_score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trust score not found",
        )

    return trust_score


@router.post("/me/device-token", status_code=status.HTTP_201_CREATED)
async def register_device_token(
    token_data: DeviceTokenCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Register device token for push notifications"""
    # Check if token already exists
    result = await db.execute(
        select(DeviceToken).where(
            DeviceToken.user_id == current_user.id,
            DeviceToken.expo_token == token_data.expo_token,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.is_active = True
        db.add(existing)
    else:
        device_token = DeviceToken(
            user_id=current_user.id,
            expo_token=token_data.expo_token,
            device_type=token_data.device_type,
            is_active=True,
        )
        db.add(device_token)

    await db.flush()
    return {"message": "Device token registered"}


@router.get("/me/payout-accounts", response_model=List[PayoutAccountResponse])
async def list_payout_accounts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List payout accounts"""
    result = await db.execute(
        select(PayoutAccount).where(PayoutAccount.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("/me/payout-accounts", response_model=PayoutAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_payout_account(
    account_data: PayoutAccountCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Add payout account"""
    account = PayoutAccount(
        user_id=current_user.id,
        account_name=account_data.account_name,
        account_number=account_data.account_number,
        bank_name=account_data.bank_name,
        mobile_money=account_data.mobile_money,
        currency=account_data.currency or "USD",
    )
    db.add(account)
    await db.flush()
    return account


@router.put("/me/payout-accounts/{account_id}", response_model=PayoutAccountResponse)
async def update_payout_account(
    account_id: UUID,
    account_data: PayoutAccountUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update payout account"""
    result = await db.execute(
        select(PayoutAccount).where(
            PayoutAccount.id == account_id,
            PayoutAccount.user_id == current_user.id,
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    if account_data.account_name:
        account.account_name = account_data.account_name
    if account_data.account_number:
        account.account_number = account_data.account_number
    if account_data.bank_name:
        account.bank_name = account_data.bank_name
    if account_data.mobile_money:
        account.mobile_money = account_data.mobile_money
    if account_data.currency:
        account.currency = account_data.currency
    if account_data.is_default is not None:
        account.is_default = account_data.is_default

    db.add(account)
    await db.flush()
    return account


@router.delete("/me/payout-accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payout_account(
    account_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete payout account"""
    result = await db.execute(
        select(PayoutAccount).where(
            PayoutAccount.id == account_id,
            PayoutAccount.user_id == current_user.id,
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    await db.delete(account)
    await db.flush()
    return None
