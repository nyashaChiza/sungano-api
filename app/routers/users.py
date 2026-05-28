from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, TrustScore
from app.schemas.user import UserResponse, UserProfile, TrustScoreResponse

router = APIRouter()


@router.get("/", response_model=List[UserResponse])
async def list_users(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 50,
):
    result = await db.execute(
        select(User).where(User.is_active == True).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{user_id}", response_model=UserProfile)
async def get_user(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    result = await db.execute(select(TrustScore).where(TrustScore.user_id == user_id))
    trust = result.scalar_one_or_none()
    user.trust_score = trust
    return user


@router.get("/{user_id}/trust-score", response_model=TrustScoreResponse)
async def get_trust_score(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(TrustScore).where(TrustScore.user_id == user_id))
    trust = result.scalar_one_or_none()
    if not trust:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trust score not found"
        )
    return trust
