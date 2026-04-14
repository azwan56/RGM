from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

load_dotenv()

from routers import auth, sync, coach, science, profile
from middleware.auth import FirebaseAuthMiddleware

app = FastAPI(title="Running Community Manager API")

# Firebase auth middleware — validates Bearer tokens on protected routes
app.add_middleware(FirebaseAuthMiddleware)

# Configure CORS — read allowed origins from env, default to localhost for dev
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,     prefix="/api/auth",    tags=["auth"])
app.include_router(sync.router,     prefix="/api/sync",    tags=["sync"])
app.include_router(coach.router,    prefix="/api/coach",   tags=["coach"])
app.include_router(science.router,  prefix="/api/science", tags=["science"])
app.include_router(profile.router,  prefix="/api/profile", tags=["profile"])

# Webhook router (loaded lazily to avoid import errors during initial setup)
try:
    from routers import webhook
    app.include_router(webhook.router, prefix="/api/webhook", tags=["webhook"])
except ImportError:
    pass

# Team router
try:
    from routers import team
    app.include_router(team.router, prefix="/api/team", tags=["team"])
except ImportError:
    pass

@app.get("/")
def read_root():
    return {"message": "Welcome to Running Community Manager API"}

@app.get("/api/health")
def health_check():
    return {"status": "ok"}
