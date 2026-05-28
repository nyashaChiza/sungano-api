# Sungano API

FastAPI backend for Sungano — a savings group (mukando/rounds) app targeting Zimbabweans.

## Tech Stack

- Python 3.11
- FastAPI 0.115
- SQLAlchemy 2.0 (async)
- aiosqlite (development)
- Alembic (migrations)
- python-jose (JWT auth)
- passlib + bcrypt (password hashing)
- python-multipart (file uploads)

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Apply migrations
alembic upgrade head

# Run the development server
uvicorn main:app --reload
```

## Environment Variables

Optionally create a `.env` file:

```
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

## API Endpoints

Base URL: `/api/v1/`

### Auth (`/api/v1/auth/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register/` | Register a new user (returns JWT tokens) |
| POST | `/auth/login/` | Obtain JWT access + refresh tokens |
| POST | `/auth/token/refresh/` | Refresh access token |
| POST | `/auth/logout/` | Blacklist refresh token |
| GET/PATCH | `/auth/profile/` | Get or update authenticated user profile |
| POST | `/auth/change-password/` | Change password |
| GET | `/auth/users/?search=` | Search users by username |

### Rounds (`/api/v1/rounds/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/rounds/` | List rounds for authenticated user |
| POST | `/rounds/` | Create a new round |
| GET | `/rounds/{id}/` | Get round detail (with members + cycles) |
| PATCH | `/rounds/{id}/` | Update round |
| DELETE | `/rounds/{id}/` | Delete round |
| POST | `/rounds/{id}/activate/` | Activate round and generate cycles |
| POST | `/rounds/{id}/invite/` | Add a member to the round |
| GET | `/rounds/{id}/members/` | List round members |
| GET | `/rounds/{id}/cycles/` | List cycles |
| GET/POST | `/rounds/{id}/cycles/{cycle_id}/payments/` | List or create payments for a cycle |

### Payments (`/api/v1/payments/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/payments/` | List all payments visible to user |
| GET | `/payments/{id}/` | Get payment detail |
| POST | `/payments/{id}/submit_proof/` | Submit payment proof (file upload) |
| POST | `/payments/{id}/confirm/` | Confirm a submitted payment |

### Goals (`/api/v1/goals/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/goals/` | List goals for authenticated user |
| POST | `/goals/` | Create a new goal |
| GET | `/goals/{id}/` | Get goal detail (with members + deposits) |
| PATCH | `/goals/{id}/` | Update goal |
| DELETE | `/goals/{id}/` | Delete goal |
| POST | `/goals/{id}/cancel/` | Cancel a goal |
| GET/POST | `/goals/{id}/deposits/` | List or create deposits |
| GET/POST | `/goals/{id}/members/` | List or add members |

### Goal Deposits (`/api/v1/goal-deposits/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/goal-deposits/` | List all deposits visible to user |
| GET | `/goal-deposits/{id}/` | Get deposit detail |

## Authentication

All endpoints except `/auth/register/` and `/auth/login/` require a JWT Bearer token:

```
Authorization: Bearer <access_token>
```

## Round Lifecycle

1. **Create** a round (status: `pending`) — creator is auto-added as member at position 1
2. **Invite** members via `POST /rounds/{id}/invite/` with `user_id` and `payout_position`
3. **Activate** via `POST /rounds/{id}/activate/` — generates Cycle objects with due dates
4. Members **create payments** for each cycle
5. Members **submit proof** via `POST /payments/{id}/submit_proof/`
6. Another member **confirms** via `POST /payments/{id}/confirm/`
7. Trust scores update automatically on confirmation

## Goal Lifecycle

1. **Create** a goal (`solo` or `group`) — creator is auto-added as member
2. For group goals, **add members** via `POST /goals/{id}/members/`
3. Members **deposit** via `POST /goals/{id}/deposits/`
4. Goal status auto-transitions to `completed` when `current_amount >= target_amount`

## Admin

Visit `/docs` for the interactive Swagger UI or `/redoc` for ReDoc.
