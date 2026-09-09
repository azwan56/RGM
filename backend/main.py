import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config import settings
from middleware.auth import SupabaseAuthMiddleware

from routers import auth, sync, coach, profile, science, team, miniapp, admin, organization
from scheduler.tasks import start_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        start_scheduler()
    except Exception as e:
        print(f"[startup] Scheduler start failed: {e}")
    yield
    # Shutdown

app = FastAPI(
    title="RGM 国内版 (Running Community Manager API)",
    description="基于阿里云 + Supabase + Garmin 直连 + 微信小程序的跑团管理与 Canova教练 系统",
    version="2.0.0-cn",
    lifespan=lifespan
)

# 1. Supabase Auth Middleware
app.add_middleware(SupabaseAuthMiddleware)

# 2. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Static Files (Avatars)
from fastapi.staticfiles import StaticFiles
avatars_dir = os.path.join(os.path.dirname(__file__), "data", "avatars")
os.makedirs(avatars_dir, exist_ok=True)
app.mount("/api/avatars", StaticFiles(directory=avatars_dir), name="avatars")

# 4. Include Routers
app.include_router(auth.router,     prefix="/api/auth",     tags=["认证与佳明直连"])
app.include_router(sync.router,     prefix="/api/sync",     tags=["Garmin 数据同步"])
app.include_router(coach.router,    prefix="/api/coach",    tags=["Canova教练"])
app.include_router(profile.router,  prefix="/api/profile",  tags=["跑者档案与目标"])
app.include_router(science.router,  prefix="/api/science",  tags=["跑步生理学与分析"])
app.include_router(team.router,     prefix="/api/team",     tags=["跑团与排行榜"])
app.include_router(organization.router, prefix="/api/org",  tags=["大群体与组织管理"])
app.include_router(miniapp.router,  prefix="/api/miniapp",  tags=["微信小程序专用接口"])
app.include_router(admin.router,    prefix="/api/admin",    tags=["平台超级管理员"])

@app.post("/api/garmin/connect", tags=["认证与佳明直连"])
def api_garmin_connect_alias(request: auth.GarminBindRequest, background_tasks: auth.BackgroundTasks):
    return auth.bind_garmin(request, background_tasks)

@app.post("/api/garmin/disconnect", tags=["认证与佳明直连"])
def api_garmin_disconnect_alias(request: auth.GarminUnbindRequest):
    return auth.unbind_garmin(request)

@app.post("/api/coros/connect", tags=["认证与高驰直连"])
def api_coros_connect_alias(request: auth.CorosBindRequest, background_tasks: auth.BackgroundTasks):
    return auth.bind_coros(request, background_tasks)

@app.post("/api/coros/disconnect", tags=["认证与高驰直连"])
def api_coros_disconnect_alias(request: auth.CorosUnbindRequest):
    return auth.unbind_coros(request)

@app.get("/")
def read_root():
    return {
        "name": "RGM 国内版 API",
        "status": "online",
        "cloud": "Alibaba Cloud",
        "database": "Supabase (PostgreSQL)",
        "source": "Garmin Direct",
        "llm": "DashScope Qwen / DeepSeek"
    }

@app.get("/api/health")
def health_check():
    return {"status": "ok", "timestamp": "2026-08-16T08:50:00+08:00"}
