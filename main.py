import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base
from app.routers import auth, users, rounds, cycles, payments, goals, disputes, contracts, notifications, activity, admin
from app.jobs.scheduler import start_scheduler, stop_scheduler
from contextlib import asynccontextmanager

if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Start background job scheduler
    start_scheduler()

    yield

    # Shutdown
    stop_scheduler()
    await engine.dispose()


app = FastAPI(
    title="Sungano API",
    description="Backend API for the Sungano savings group app",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - restrict to frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "http://localhost:8000", "exp://"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(rounds.router, prefix="/api/v1/rounds", tags=["Rounds"])
app.include_router(cycles.router, prefix="/api/v1/cycles", tags=["Cycles"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["Payments"])
app.include_router(goals.router, prefix="/api/v1/goals", tags=["Goals"])
app.include_router(disputes.router, prefix="/api/v1/disputes", tags=["Disputes"])
app.include_router(contracts.router, prefix="/api/v1/contracts", tags=["Contracts"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
app.include_router(activity.router, prefix="/api/v1/activity", tags=["Activity"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])


@app.get("/")
def root():
    return {"message": "Sungano API", "version": "1.0.0", "docs": "/docs"}
