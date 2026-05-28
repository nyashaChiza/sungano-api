import os
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user
from app.core.config import settings
from app.models.user import User, TrustScore
from app.schemas.user import UserCreate, UserResponse, UserProfile, Token, UserUpdate

router = APIRouter()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    # Check email uniqueness
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Check username uniqueness
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    user = User(
        email=user_data.email,
        username=user_data.username,
        phone=user_data.phone,
        hashed_password=hash_password(user_data.password),
    )
    db.add(user)
    await db.flush()

    trust_score = TrustScore(user_id=user.id)
    db.add(trust_score)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=access_token)


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=access_token)


@router.get("/me", response_model=UserProfile)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    result = await db.execute(
        select(TrustScore).where(TrustScore.user_id == current_user.id)
    )
    trust = result.scalar_one_or_none()
    user.trust_score = trust
    return user


@router.put("/me", response_model=UserProfile)
async def update_me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    username: Annotated[str | None, Form()] = None,
    phone: Annotated[str | None, Form()] = None,
    avatar: Annotated[UploadFile | None, File()] = None,
):
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    if username is not None:
        # Check uniqueness
        check = await db.execute(
            select(User).where(User.username == username, User.id != current_user.id)
        )
        if check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )
        user.username = username

    if phone is not None:
        user.phone = phone

    if avatar is not None:
        ext = os.path.splitext(avatar.filename)[1] if avatar.filename else ".jpg"
        filename = f"{uuid.uuid4()}{ext}"
        avatar_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
        os.makedirs(avatar_dir, exist_ok=True)
        file_path = os.path.join(avatar_dir, filename)
        content = await avatar.read()
        with open(file_path, "wb") as f:
            f.write(content)
        user.avatar_url = f"/uploads/avatars/{filename}"

    await db.commit()
    await db.refresh(user)

    result = await db.execute(
        select(TrustScore).where(TrustScore.user_id == current_user.id)
    )
    trust = result.scalar_one_or_none()
    user.trust_score = trust
    return user
