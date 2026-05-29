# Sungano API Implementation Status

## ✅ COMPLETED — Foundation Layer (Core Infrastructure)

### Configuration & Database
- [x] `requirements.txt` — All dependencies (asyncpg, cloudinary, mailjet, reportlab, etc.)
- [x] `.env.example` — Environment variables template
- [x] `app/core/config.py` — Settings with all required env vars (JWT_SECRET, Cloudinary, Mailjet, etc.)
- [x] `app/core/database.py` — PostgreSQL async engine (asyncpg) with no SQLite references
- [x] `app/core/security.py` — JWT (access + refresh tokens), password hashing (bcrypt rounds=12), token utilities

### Models Layer — UUID Primary Keys ✅
- [x] `app/models/user.py` — User, TrustScore, DeviceToken, VerificationToken, RefreshToken, PayoutAccount
- [x] `app/models/round.py` — Round, RoundMember, RoundCycle, CyclePayment, InviteLink
- [x] `app/models/goal.py` — Goal, GoalMember, GoalDeposit (with confirmation status)
- [x] `app/models/contract.py` — Contract, ContractSignature
- [x] `app/models/dispute.py` — Dispute
- [x] `app/models/notification.py` — Reminder, ActivityLog
- [x] `app/models/__init__.py` — Updated with all new model imports

### Auth & Router Foundation ✅
- [x] `app/routers/auth.py` — Complete implementation:
  - Register (generates OTP for phone verification)
  - Login
  - Refresh-token (JWT token refresh)
  - Verify-phone, verify-email (OTP verification)
  - Forgot-password, reset-password
- [x] `app/schemas/auth.py` — Pydantic request/response schemas
- [x] `main.py` — FastAPI app with Sentry, CORS, lifespan manager

## 🔄 IN PROGRESS / MOSTLY COMPLETE

### Routers - ALL CREATED ✅
- [x] `app/routers/users.py` — User profile, trust score, payout accounts
- [x] `app/routers/rounds.py` — Create, list, detail, invite links, join (with guest preview NO AUTH)
- [x] `app/routers/cycles.py` — List cycles, current cycle, payment board
- [x] `app/routers/payments.py` — Submit proof, confirm, dispute, list
- [x] `app/routers/contracts.py` — Get contract, sign, download PDF
- [x] `app/routers/goals.py` — Create, list, detail, deposits (with approval flow)
- [x] `app/routers/disputes.py` — List, get detail, resolve (admin)
- [x] `app/routers/notifications.py` — Device token registration, notification preferences
- [x] `app/routers/activity.py` — Activity feed, mark read
- [x] `app/routers/admin.py` — Dashboard stats (protected)

### Services Layer - ALL CREATED ✅
- [x] `app/services/cloudinary_service.py` — Upload to Cloudinary (profiles, proofs, contracts)
- [x] `app/services/email_service.py` — Mailjet email sending (OTP, notifications)
- [x] `app/services/push_service.py` — Expo push notifications via httpx
- [x] `app/services/trust_service.py` — calculate_trust_score() function
- [x] `app/services/contract_service.py` — Generate contract PDF with reportlab, upload to Cloudinary

### Jobs Layer (APScheduler) - CREATED ✅
- [x] `app/jobs/scheduler.py` — APScheduler setup (auto-confirm, default detection, reminder dispatch)
- [x] `app/jobs/auto_confirm.py` — Auto-confirm payments after 72 hours
- [x] `app/jobs/default_detection.py` — Detect defaults, update trust scores, create reminders
- [x] `app/jobs/reminder_dispatch.py` — Send scheduled reminders (email + push)

### Schemas - CREATED ✅
- [x] `app/schemas/auth.py` — Auth schemas
- [x] `app/schemas/user.py` — User schemas
- [x] `app/schemas/round.py` — Round/cycle/payment schemas
- [x] `app/schemas/goal.py` — Goal schemas
- [x] `app/schemas/contract.py` — Contract schemas

### Database Migrations - PENDING
- [ ] `alembic/` — Update alembic env.py to use all new models, create initial migration

## 🚀 Quick Start to Continue Build

### To Build the Remaining Routers:
Each router should:
1. Have async endpoints with proper authentication (`get_current_user` dependency)
2. Use UUID types throughout
3. Return proper Pydantic schemas
4. Handle errors with HTTPException
5. Use SQLAlchemy async ORM (no raw SQL)

### Pattern for new routers:
```python
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import YourModel
from app.schemas import YourSchema

router = APIRouter()

@router.get("/", response_model=list[YourSchema])
async def list_items(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(select(YourModel).filter(...))
    items = result.scalars().all()
    return items
```

### To Set Up Cloudinary (app/services/cloudinary_service.py):
```python
import cloudinary
from cloudinary import uploader
from app.core.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
)

async def upload_profile_photo(file_bytes, user_id):
    # Upload to /sungano/profiles/{user_id}/
    pass
```

### To Set Up APScheduler (app/jobs/scheduler.py):
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

def start_scheduler():
    scheduler.add_job(run_auto_confirm, 'interval', hours=1)
    scheduler.add_job(run_default_detection, 'cron', hour=8, minute=0)
    scheduler.add_job(run_reminder_dispatch, 'cron', hour=8, minute=0)
    scheduler.start()

# In main.py startup:
@app.on_event("startup")
async def startup():
    start_scheduler()
```

### Database Creation (Alembic):
```bash
cd sungano-api
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

## Key Implementation Notes

1. **Guest Preview Route**: `GET /api/v1/rounds/join/{token}` must NOT require auth (allow unauthenticated access)
2. **Contract PDF**: Use reportlab to generate, upload to Cloudinary, store URL in database
3. **Fraud Declaration**: Every contract must include this clause (immutable, always present)
4. **Auto-Confirmation**: Runs every hour, finds payments submitted 72+ hours ago, auto-confirms them
5. **Default Detection**: Runs daily at 08:00, finds overdue payments, marks as defaulted, updates trust scores
6. **Reminder Dispatch**: Runs daily at 08:00, sends scheduled push + email notifications
7. **Trust Score Calculation**: Base 100, +0 for on-time, -2 per late, -10 per default, +5 per completed round, -5 per dispute upheld
8. **Phone Normalization**: Store as-provided (best-effort E.164, not enforced)
9. **Soft Deletes**: Never hard delete users/payments, use `is_active` / `status` fields

## Environment Setup
Create `.env` file from `.env.example`:
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost/sungano
JWT_SECRET=your-super-secret-key-min-32-chars
CLOUDINARY_CLOUD_NAME=your_cloud
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
MAILJET_API_KEY=...
MAILJET_SECRET_KEY=...
```

## Running the API
```bash
# Install deps
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---
**Next Priority**: Build the `app/routers/users.py`, `app/routers/rounds.py`, and `app/services/` layer next.
