import cloudinary
import cloudinary.uploader
import cloudinary.utils
from app.core.config import settings
from uuid import UUID
from typing import Optional
import io
from datetime import datetime, timedelta

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
)


async def upload_profile_photo(user_id: UUID, file_bytes: bytes) -> str:
    """
    Upload profile photo to Cloudinary
    Returns: public_id for use in signed URLs
    """
    file_obj = io.BytesIO(file_bytes)
    result = cloudinary.uploader.upload(
        file_obj,
        folder=f"sungano/profile-photos/{user_id}",
        resource_type="auto",
        quality="auto",
        fetch_format="auto",
        public_id=f"{user_id}-profile",
        overwrite=True,
    )
    return result.get("public_id")


async def upload_payment_proof(
    round_id: UUID,
    cycle_id: UUID,
    user_id: UUID,
    file_bytes: bytes,
    proof_type: str,
) -> str:
    """
    Upload payment proof document to Cloudinary
    Returns: public_id
    """
    file_obj = io.BytesIO(file_bytes)
    result = cloudinary.uploader.upload(
        file_obj,
        folder=f"sungano/payment-proofs/{round_id}/{cycle_id}",
        resource_type="auto",
        public_id=f"{user_id}-{proof_type}-{datetime.utcnow().timestamp()}",
    )
    return result.get("public_id")


async def upload_goal_proof(
    goal_id: UUID,
    user_id: UUID,
    file_bytes: bytes,
    proof_type: str,
) -> str:
    """
    Upload goal deposit proof to Cloudinary
    Returns: public_id
    """
    file_obj = io.BytesIO(file_bytes)
    result = cloudinary.uploader.upload(
        file_obj,
        folder=f"sungano/goal-proofs/{goal_id}",
        resource_type="auto",
        public_id=f"{user_id}-{proof_type}-{datetime.utcnow().timestamp()}",
    )
    return result.get("public_id")


async def upload_contract_pdf(round_id: UUID, pdf_bytes: bytes) -> str:
    """
    Upload contract PDF to Cloudinary
    Returns: public_id
    """
    file_obj = io.BytesIO(pdf_bytes)
    result = cloudinary.uploader.upload(
        file_obj,
        folder=f"sungano/contracts",
        resource_type="raw",
        format="pdf",
        public_id=f"round-{round_id}-contract",
        overwrite=True,
    )
    return result.get("public_id")


def get_signed_url(public_id: str, expires_in_seconds: int = 3600) -> str:
    """
    Generate a signed URL for a Cloudinary asset
    Default expiry: 1 hour
    """
    expiration = datetime.utcnow() + timedelta(seconds=expires_in_seconds)
    signed_url = cloudinary.utils.cloudinary_url(
        public_id,
        sign_url=True,
        expires_at=int(expiration.timestamp()),
        resource_type="auto",
    )[0]
    return signed_url


def delete_asset(public_id: str, resource_type: str = "auto") -> bool:
    """
    Delete an asset from Cloudinary
    """
    try:
        cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        return True
    except Exception:
        return False
