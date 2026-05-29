import secrets
from typing import Annotated
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, hash_token, decode_access_token
)
from app.core.config import settings
from app.models.user import User, TrustScore, VerificationToken, RefreshToken
from app.schemas.auth import (
    UserRegisterRequest, UserLoginRequest, Token, VerifyOTPRequest,
    ForgotPasswordRequest, ResetPasswordRequest, RefreshTokenRequest
)
from app.services.email_service import send_otp_email

router = APIRouter()


def generate_otp() -> str:
    """Generate 6-digit OTP"""
    return str(secrets.randbelow(1000000)).zfill(6)


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    # Check email uniqueness
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Check phone uniqueness
    result = await db.execute(select(User).where(User.phone == user_data.phone))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered"
        )

    # Create user
    user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        phone=user_data.phone,
        password_hash=hash_password(user_data.password),
    )
    db.add(user)
    await db.flush()

    # Create trust score
    trust_score = TrustScore(user_id=user.id)
    db.add(trust_score)

    # Generate phone verification OTP
    otp_token = generate_otp()
    verification_token = VerificationToken(
        user_id=user.id,
        token=otp_token,
        type="phone_verify",
        expires_at=datetime.utcnow() + timedelta(minutes=10)
    )
    db.add(verification_token)

    await db.commit()

    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token()
    refresh_token_hash = hash_token(refresh_token)

    refresh_token_db = RefreshToken(
        user_id=user.id,
        token_hash=refresh_token_hash,
        expires_at=datetime.utcnow() + timedelta(days=30)
    )
    db.add(refresh_token_db)
    await db.commit()

    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    # Find user by email
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive"
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token()
    refresh_token_hash = hash_token(refresh_token)

    refresh_token_db = RefreshToken(
        user_id=user.id,
        token_hash=refresh_token_hash,
        expires_at=datetime.utcnow() + timedelta(days=30)
    )
    db.add(refresh_token_db)
    await db.commit()

    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh-token", response_model=Token)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    token_hash = hash_token(request.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at == None
        )
    )
    refresh_token_record = result.scalar_one_or_none()

    if not refresh_token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Create new access token
    access_token = create_access_token(data={"sub": str(refresh_token_record.user_id)})
    return Token(access_token=access_token, token_type="bearer")


@router.post("/verify-phone")
async def verify_phone(
    request: VerifyOTPRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    # Find verification token
    result = await db.execute(
        select(VerificationToken).where(
            VerificationToken.type == "phone_verify",
            VerificationToken.token == request.token,
            VerificationToken.used_at == None
        )
    )
    token = result.scalar_one_or_none()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )

    # Update user
    result = await db.execute(select(User).where(User.id == token.user_id))
    user = result.scalar_one_or_none()
    user.is_phone_verified = True
    token.used_at = True

    await db.commit()

    return {"status": "success", "message": "Phone verified"}


@router.post("/verify-email")
async def verify_email(
    request: VerifyOTPRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    # Similar to verify-phone
    result = await db.execute(
        select(VerificationToken).where(
            VerificationToken.type == "email_verify",
            VerificationToken.token == request.token,
            VerificationToken.used_at == None
        )
    )
    token = result.scalar_one_or_none()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )

    result = await db.execute(select(User).where(User.id == token.user_id))
    user = result.scalar_one_or_none()
    user.is_email_verified = True
    token.used_at = True

    await db.commit()

    return {"status": "success", "message": "Email verified"}


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    # Find user
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user:
        # Don't reveal if email exists
        return {"status": "success", "message": "If email exists, reset code has been sent"}

    # Generate reset token
    reset_token = secrets.token_urlsafe(32)
    verification_token = VerificationToken(
        user_id=user.id,
        token=reset_token[:10],
        type="password_reset",
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )
    db.add(verification_token)
    await db.commit()

    await send_otp_email(user.email, reset_token[:10], "reset_password", user.full_name)
    return {"status": "success", "message": "If email exists, reset code has been sent"}


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    # Find verification token
    result = await db.execute(
        select(VerificationToken).where(
            VerificationToken.type == "password_reset",
            VerificationToken.token == request.token,
            VerificationToken.used_at == None
        )
    )
    token = result.scalar_one_or_none()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    # Update user password
    result = await db.execute(select(User).where(User.id == token.user_id))
    user = result.scalar_one_or_none()
    user.password_hash = hash_password(request.new_password)
    token.used_at = True

    await db.commit()

    return {"status": "success", "message": "Password reset successful"}
