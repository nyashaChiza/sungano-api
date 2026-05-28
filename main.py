from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.database import engine, Base
from app.routers import auth, users, rounds, goals

app = FastAPI(
    title="Sungano API",
    description="Backend API for the Sungano savings group app",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(rounds.router, prefix="/api/v1/rounds", tags=["Rounds"])
app.include_router(goals.router, prefix="/api/v1/goals", tags=["Goals"])


@app.get("/")
def root():
    return {"message": "Sungano API", "version": "1.0.0", "docs": "/docs"}
