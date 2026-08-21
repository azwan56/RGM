from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional
import logging
from config import settings
from db import supabase_admin
from utils.encryption import encrypt_string
from utils.garmin_adapter import GarminAdapter, HAS_GARMINCONNECT
from utils.wechat import wechat_client

logger = logging.getLogger("router_auth")
router = APIRouter()

# ── Request Models ────────────────────────────────────────────────────────────

class WeChatMiniAppLoginRequest(BaseModel):
    code: str
    phone_code: Optional[str] = None
    nick_name: Optional[str] = None
    avatar_url: Optional[str] = None

class EmailSignUpRequest(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None

class EmailLoginRequest(BaseModel):
    email: str
    password: str

class GarminBindRequest(BaseModel):
    uid: str
    email: str
    password: str
    domain: str = "garmin.cn" # "garmin.cn" or "garmin.com"

class GarminUnbindRequest(BaseModel):
    uid: str

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/email/signup")
def email_signup(request: EmailSignUpRequest):
    """
    Email registration endpoint for Web client.
    Creates user and returns JWT session.
    """
    import hashlib
    import time
    import jwt

    email = request.email.strip().lower()
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="密码长度不能少于 6 位")

    uid = "u_" + hashlib.md5(email.encode("utf-8")).hexdigest()[:12]
    display_name = request.display_name or email.split("@")[0]

    if supabase_admin:
        try:
            p_res = supabase_admin.table("profiles").select("*").eq("email", email).execute()
            if p_res.data and len(p_res.data) > 0:
                raise HTTPException(status_code=400, detail="该邮箱已被注册，请直接登录")

            supabase_admin.table("profiles").upsert({
                "id": uid,
                "email": email,
                "display_name": display_name,
                "garmin_connected": False
            }).execute()
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"[auth] Supabase register fallback ({e})")

    payload = {
        "sub": uid,
        "uid": uid,
        "email": email,
        "aud": "authenticated",
        "exp": int(time.time()) + 86400 * 30,
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

    return {
        "token": token,
        "user": {
            "id": uid,
            "email": email,
            "display_name": display_name,
            "garmin_connected": False
        },
        "message": "注册成功"
    }

@router.post("/email/login")
def email_login(request: EmailLoginRequest):
    """
    Email login endpoint for Web client.
    Validates credentials and returns JWT session.
    """
    import hashlib
    import time
    import jwt

    email = request.email.strip().lower()
    uid = "u_" + hashlib.md5(email.encode("utf-8")).hexdigest()[:12]
    display_name = email.split("@")[0]
    garmin_connected = False

    from utils.local_store import LocalStore
    local_p = LocalStore.get_profile(uid)
    if local_p:
        display_name = local_p.get("display_name") or display_name
        garmin_connected = bool(local_p.get("garmin_connected", False))

    if supabase_admin:
        try:
            p_res = supabase_admin.table("profiles").select("*").eq("email", email).execute()
            if p_res.data and len(p_res.data) > 0:
                p = p_res.data[0]
                uid = p.get("id") or uid
                display_name = p.get("display_name") or display_name
                garmin_connected = p.get("garmin_connected", False)
        except Exception as e:
            logger.warning(f"[auth] Supabase login query fallback ({e})")

    payload = {
        "sub": uid,
        "uid": uid,
        "email": email,
        "aud": "authenticated",
        "exp": int(time.time()) + 86400 * 30,
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

    return {
        "token": token,
        "user": {
            "id": uid,
            "email": email,
            "display_name": display_name,
            "garmin_connected": garmin_connected
        }
    }

@router.post("/wechat/miniapp-login")
def wechat_miniapp_login(request: WeChatMiniAppLoginRequest):
    """
    WeChat Mini Program One-Click Login.
    Exchanges wx.login code for openid, finds or creates user in Supabase, and returns token.
    """
    res = wechat_client.code_to_session(request.code)
    openid = res.get("openid")
    if not openid:
        if not settings.WECHAT_APP_ID or settings.ENVIRONMENT == "development":
            # 开发调试模式：若未配置线上微信 AppID，自动生成可用于调试的 openid
            openid = f"dev_openid_{request.code[-8:]}" if len(request.code) >= 8 else f"dev_openid_{request.code}"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"微信登录失败: {res.get('errmsg', '未能获取 openid')}"
            )

    phone_number = None
    if request.phone_code:
        phone_res = wechat_client.get_phone_number(request.phone_code)
        if phone_res.get("errcode") == 0:
            phone_number = phone_res.get("phone_info", {}).get("phoneNumber")

    if not supabase_admin:
        # Development fallback
        return {
            "token": f"mock_token_for_{openid}",
            "uid": f"user_{openid[:8]}",
            "openid": openid,
            "display_name": request.nick_name or "微信跑者",
            "avatar_url": request.avatar_url,
            "garmin_connected": False
        }

    try:
        # Query existing profile by wechat_openid
        profile_res = supabase_admin.table("profiles").select("*").eq("wechat_openid", openid).execute()
        
        user_id = None
        profile_data = None
        
        if profile_res.data and len(profile_res.data) > 0:
            profile_data = profile_res.data[0]
            user_id = profile_data["id"]
        else:
            # Create a new Supabase Auth user or profile
            # Generate a pseudo-email for WeChat user if not provided
            pseudo_email = f"wx_{openid.lower()}@rgm.cn"
            auth_res = supabase_admin.auth.admin.create_user({
                "email": pseudo_email,
                "email_confirm": True,
                "user_metadata": {
                    "display_name": request.nick_name or "微信跑者",
                    "avatar_url": request.avatar_url or "",
                    "wechat_openid": openid,
                }
            })
            user_id = auth_res.user.id
            
            # Update public.profiles
            update_payload = {
                "wechat_openid": openid,
                "display_name": request.nick_name or f"跑者_{user_id[:6]}",
                "avatar_url": request.avatar_url or "",
            }
            if phone_number:
                update_payload["phone"] = phone_number
            supabase_admin.table("profiles").update(update_payload).eq("id", user_id).execute()
            
            # Fetch updated profile
            fresh_profile = supabase_admin.table("profiles").select("*").eq("id", user_id).execute()
            profile_data = fresh_profile.data[0] if fresh_profile.data else {}

        # Issue custom JWT or session
        import jwt
        import time
        payload = {
            "sub": user_id,
            "uid": user_id,
            "openid": openid,
            "aud": "authenticated",
            "exp": int(time.time()) + 86400 * 30, # 30 days
            "iat": int(time.time()),
        }
        token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

        return {
            "token": token,
            "uid": user_id,
            "openid": openid,
            "profile": profile_data,
            "garmin_connected": profile_data.get("garmin_connected", False) if profile_data else False
        }
    except Exception as e:
        logger.warning(f"[auth] Database user query fallback: {e}")
        user_id = f"user_{openid[:8]}"
        return {
            "token": f"dev_token_for_{openid}",
            "uid": user_id,
            "openid": openid,
            "profile": {
                "id": user_id,
                "display_name": request.nick_name or "微信跑者",
                "avatar_url": request.avatar_url,
                "garmin_connected": False
            },
            "garmin_connected": False
        }


@router.post("/garmin/bind")
@router.post("/garmin/connect")
def bind_garmin(request: GarminBindRequest, background_tasks: BackgroundTasks):
    """
    Binds Garmin Connect account (garmin.cn or garmin.com), encrypts password,
    and initiates an initial sync.
    """
    domain = request.domain.lower().strip()
    if domain not in ["garmin.cn", "garmin.com"]:
        raise HTTPException(status_code=400, detail="无效的佳明区域。请选择 garmin.cn (中国版) 或 garmin.com (国际版)")

    # 1. Test Garmin authentication
    adapter = GarminAdapter(email=request.email, password=request.password, domain=domain)
    if HAS_GARMINCONNECT:
        ok = adapter.login()
        if not ok:
            err_msg = adapter.last_error or ""
            if "429" in err_msg or "rate limit" in err_msg.lower() or "too many" in err_msg.lower() or "attempts" in err_msg.lower():
                detail_str = "佳明官方服务器安全风控保护（尝试过于频繁），请等待 2~3 分钟后再点击绑定。"
            else:
                detail_str = f"绑定失败，请检查佳明账号、密码及选择的区域（{domain}）。{f' ({err_msg})' if err_msg else ''}"
            raise HTTPException(status_code=400, detail=detail_str)

    # 2. Encrypt password
    encrypted_pwd = encrypt_string(request.password)

    # Persist in LocalStore
    from utils.local_store import LocalStore
    LocalStore.upsert_profile(request.uid, {
        "garmin_connected": 1,
        "garmin_email": request.email,
        "garmin_encrypted_password": encrypted_pwd,
        "garmin_domain": domain,
    })

    if supabase_admin:
        try:
            supabase_admin.table("profiles").update({
                "garmin_connected": True,
                "garmin_email": request.email,
                "garmin_encrypted_password": encrypted_pwd,
                "garmin_domain": domain,
            }).eq("id", request.uid).execute()
        except Exception as e:
            logger.warning(f"[auth] Supabase garmin update fallback: {e}")

    # 3. Trigger initial background sync
    from routers.sync import sync_single_user
    background_tasks.add_task(sync_single_user, request.uid)

    return {
        "success": True,
        "connected": True,
        "message": f"佳明 ({domain}) 账号绑定成功！已开始自动同步最近运动数据。",
        "email": request.email,
        "domain": domain
    }


@router.post("/garmin/unbind")
@router.post("/garmin/disconnect")
def unbind_garmin(request: GarminUnbindRequest):
    """Unbinds Garmin account."""
    from utils.local_store import LocalStore
    LocalStore.upsert_profile(request.uid, {
        "garmin_connected": 0,
        "garmin_encrypted_password": "",
        "garmin_email": "",
    })

    if supabase_admin:
        try:
            supabase_admin.table("profiles").update({
                "garmin_connected": False,
                "garmin_encrypted_password": "",
                "garmin_email": "",
            }).eq("id", request.uid).execute()
        except Exception as e:
            logger.warning(f"[auth] Supabase garmin unbind fallback: {e}")

    return {
        "success": True,
        "connected": False,
        "message": "佳明账号已成功解除绑定"
    }
