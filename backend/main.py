import os
import time

# Enforce China Standard Time (UTC+8) across backend runtime
os.environ["TZ"] = "Asia/Shanghai"
if hasattr(time, "tzset"):
    try:
        time.tzset()
    except Exception:
        pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from config import settings
from middleware.auth import SupabaseAuthMiddleware

from routers import auth, sync, coach, profile, science, team, miniapp, admin, organization, notifications
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
    title="万跑跑团助手 API",
    description="基于阿里云 + 多品牌手表直连 + 微信小程序与 Web 一体化的万跑跑团助手与 Canova 科学教练系统",
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

# 2.5 GZip Compression for JSON / API payloads >= 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 3. Static Files (Avatars & Race Photos)
from fastapi.staticfiles import StaticFiles
avatars_dir = os.path.join(os.path.dirname(__file__), "data", "avatars")
os.makedirs(avatars_dir, exist_ok=True)
app.mount("/api/avatars", StaticFiles(directory=avatars_dir), name="avatars")

race_photos_dir = os.path.join(os.path.dirname(__file__), "data", "race_photos")
os.makedirs(race_photos_dir, exist_ok=True)
app.mount("/api/race-photos", StaticFiles(directory=race_photos_dir), name="race_photos")

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
app.include_router(notifications.router, prefix="/api",     tags=["系统通知与消息推送"])

from fastapi import Header
from typing import Optional

@app.post("/api/garmin/connect", tags=["认证与佳明直连"])
def api_garmin_connect_alias(request: auth.GarminBindRequest, background_tasks: auth.BackgroundTasks):
    return auth.bind_garmin(request, background_tasks)

@app.post("/api/garmin/disconnect", tags=["认证与佳明直连"])
def api_garmin_disconnect_alias(request: auth.GarminUnbindRequest, authorization: Optional[str] = Header(None)):
    return auth.unbind_garmin(request, authorization)

@app.post("/api/coros/connect", tags=["认证与高驰直连"])
def api_coros_connect_alias(request: auth.CorosBindRequest, background_tasks: auth.BackgroundTasks):
    return auth.bind_coros(request, background_tasks)

@app.post("/api/coros/disconnect", tags=["认证与高驰直连"])
def api_coros_disconnect_alias(request: auth.CorosUnbindRequest, authorization: Optional[str] = Header(None)):
    return auth.unbind_coros(request, authorization)

@app.get("/")
def read_root():
    return {
        "name": "万跑跑团助手 API",
        "status": "online",
        "cloud": "Alibaba Cloud",
        "database": "SQLite WAL (LocalStore)",
        "source": "Garmin / COROS / Apple / Huawei / Suunto",
        "llm": "DashScope Qwen / DeepSeek"
    }

@app.get("/api/health")
def health_check():
    return {"status": "ok", "timestamp": "2026-08-16T08:50:00+08:00"}

from fastapi.responses import HTMLResponse

@app.get("/privacy", response_class=HTMLResponse, tags=["合规与政策"])
def get_privacy_policy():
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>万跑跑团助手 - 用户隐私政策</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 24px; color: #222; background: #fafafa; }
        .card { background: #fff; padding: 32px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
        h1 { color: #111; font-size: 24px; border-bottom: 2px solid #eee; padding-bottom: 12px; }
        h2 { color: #333; font-size: 18px; margin-top: 24px; }
        p, li { color: #555; font-size: 15px; }
        .footer { margin-top: 32px; font-size: 13px; color: #999; text-align: center; }
    </style>
</head>
<body>
    <div class="card">
        <h1>万跑跑团助手 · 隐私政策</h1>
        <p>更新日期：2026年10月1日</p>
        <p>欢迎使用万跑跑团助手（以下简称“本应用”）。我们高度重视用户的隐私保护与个人信息安全。本隐私政策旨在向您说明我们如何收集、使用、存储及保护您的个人信息。</p>
        
        <h2>1. 我们收集的信息</h2>
        <ul>
            <li><strong>账号与联系信息：</strong>用户注册与登录时提供的手机号、昵称、头像。</li>
            <li><strong>健康与运动数据：</strong>为提供跑步训练与团队跑量统计，我们会记录您的跑步里程、配速、步频、心率、时长等运动记录。</li>
            <li><strong>用户发布内容：</strong>您在跑团圈子或活动中主动发布的打卡照片、跑步心得与互动评论。</li>
        </ul>

        <h2>2. 信息的使用目的</h2>
        <p>我们收集的数据仅用于实现本应用的核心功能，包括跑团跑量统计、Canova AI 训练指导复盘、团队排行榜与赛事报名，绝不会将您的个人数据出售给任何第三方，亦不用于跨平台广告追踪。</p>

        <h2>3. 数据的存储与安全</h2>
        <p>我们采用业界标准的高强度加密措施（包括传输层 SSL/TLS 加密与存储层加密），保障您的数据安全。您可以随时在应用内联系管理员申请注销账号并永久清除全部个人数据。</p>

        <h2>4. 联系我们</h2>
        <p>如对本隐私政策有任何疑问或反馈，请通过应用内客服或发送邮件至：support@vanpower.net 联系我们。</p>

        <div class="footer">
            &copy; 2026 万跑跑团助手. All rights reserved.
        </div>
    </div>
</body>
</html>"""


@app.get("/citations", response_class=HTMLResponse, tags=["合规与政策"])
def get_scientific_citations():
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>万跑跑团助手 - 运动生理学理论来源、文献引用与健康免责声明</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; max-width: 820px; margin: 0 auto; padding: 24px; color: #222; background: #f8fafc; }
        .card { background: #fff; padding: 32px; border-radius: 14px; box-shadow: 0 2px 10px rgba(0,0,0,0.06); }
        h1 { color: #0f172a; font-size: 22px; border-bottom: 2px solid #e2e8f0; padding-bottom: 14px; margin-bottom: 20px; }
        h2 { color: #1e293b; font-size: 17px; margin-top: 28px; display: flex; align-items: center; }
        .disclaimer-box { background: #fff1f2; border-left: 4px solid #f43f5e; padding: 16px 20px; border-radius: 8px; margin-bottom: 24px; color: #9f1239; font-size: 14px; }
        .disclaimer-box strong { font-size: 15px; display: block; margin-bottom: 6px; }
        .citation-item { background: #f1f5f9; padding: 16px; border-radius: 10px; margin-top: 10px; font-size: 14px; color: #334155; }
        .citation-title { font-weight: bold; color: #0f172a; margin-bottom: 4px; }
        .citation-meta { font-style: italic; color: #475569; margin-bottom: 8px; }
        a { color: #2563eb; text-decoration: none; font-weight: 500; }
        a:hover { text-decoration: underline; }
        .footer { margin-top: 36px; font-size: 13px; color: #94a3b8; text-align: center; }
    </style>
</head>
<body>
    <div class="card">
        <h1>运动生理学理论依据、文献引用与健康免责声明</h1>

        <div class="disclaimer-box">
            <strong>⚠️ 运动健康与医学免责声明 (Medical & Health Disclaimer)</strong>
            万跑跑团助手所展示的体能与疲劳模型（CTL/ATL/TSB）、心率区间划分（Karvonen）、跑力与完赛预测（Daniels VDOT）以及 Canova AI 教练的训练建议，均基于公开发表的运动生理学经典数学模型与耐力训练学术理论。上述计算模型与分析建议仅作为耐力跑者与教练日常科学训练的参考依据，<strong>不构成任何临床诊断、医疗健康处方或医学治疗方案</strong>。在开始任何高强度耐力跑步训练或备战马拉松前，请务必咨询专业医疗机构及执业医师。
        </div>

        <h2>1. Banister 冲动-响应体能与疲劳模型 (CTL / ATL / TSB)</h2>
        <div class="citation-item">
            <div class="citation-title">Modeling Human Performance: Impulse-Response Systems</div>
            <div class="citation-meta">Banister, E. W., Calvert, T. W., Savage, M. V., & Bach, T. (1975). A systems model of training for athletic performance. Australian Journal of Sports Medicine, 7, 57–61.</div>
            <p>应用场景：用于量化每日训练负荷（TRIMP / Training Stress），计算体能底座（CTL 42天指数移动平均）、急性疲劳（ATL 7天指数移动平均）及竞技就绪度（TSB = CTL - ATL），预防过度训练与伤病。</p>
            <div>PubMed 检索文献：<a href="https://pubmed.ncbi.nlm.nih.gov/11797825/" target="_blank" rel="noopener">PubMed ID: 11797825 (Validation of Banister Training Impulse)</a></div>
        </div>

        <h2>2. Jack Daniels VDOT 跑力公式与最大摄氧量估算</h2>
        <div class="citation-item">
            <div class="citation-title">Daniels' Running Formula & Oxygen Power Tables</div>
            <div class="citation-meta">Daniels, J., & Gilbert, J. (1979). Oxygen Power: Performance Tables for Distance Runners. / Daniels, J. (2013). Daniels' Running Formula (3rd ed.). Human Kinetics.</div>
            <p>应用场景：依据跑者 5K、10K、半马或全马历史最佳战绩，利用耗氧动力学方程式反推有效最大摄氧量（VDOT 跑力值），并用于推导各训练阶段配速与预测完赛时间。</p>
            <div>官方权威标准：<a href="https://vdoto2.com" target="_blank" rel="noopener">Jack Daniels' VDOT O2 Official Tables</a></div>
        </div>

        <h2>3. Karvonen 储备心率 (HRR) 训练区间模型</h2>
        <div class="citation-item">
            <div class="citation-title">The Effects of Training on Heart Rate: A Longitudinal Study</div>
            <div class="citation-meta">Karvonen, M. J., Kentala, E., & Mustala, O. (1957). Annales Medicinae Experimentalis et Biologiae Fenniae, 35(3), 307–315.</div>
            <p>应用场景：结合跑者静息心率与最大心率，采用储备心率百分比公式 Target HR = ((MaxHR − RestHR) × %Intensity) + RestHR，精确划分有氧基础区（Z1/Z2）、马拉松配速区（Z3）、乳酸阈值区（Z4）与无氧间歇区（Z5）。</p>
            <div>PubMed 经典检索：<a href="https://pubmed.ncbi.nlm.nih.gov/13470504/" target="_blank" rel="noopener">PubMed ID: 13470504 (Karvonen et al.)</a></div>
        </div>

        <h2>4. Renato Canova 马拉松特异性训练与周期化理论</h2>
        <div class="citation-item">
            <div class="citation-title">Marathon Training: A Scientific Approach</div>
            <div class="citation-meta">Canova, R. (1999). New Studies in Athletics, International Association of Athletics Federations (IAAF), 14(4), 27–42.</div>
            <p>应用场景：Canova AI 教练的专项化配速矩阵（基础期、预备期、专项期、特异期）构建、长距离阻断期（Special Block）课表设计与马拉松特异耐力发展指导。</p>
            <div>学术引文索引：<a href="https://worldathletics.org" target="_blank" rel="noopener">World Athletics (IAAF) Coaching Literature</a></div>
        </div>

        <div class="footer">
            &copy; 2026 万跑跑团助手. All rights reserved.
        </div>
    </div>
</body>
</html>"""


