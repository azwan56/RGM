from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
import hashlib
import logging
from config import settings
from db import supabase_admin
from utils.encryption import encrypt_string, decrypt_string
from utils.garmin_adapter import GarminAdapter, HAS_GARMINCONNECT, remove_cached_garmin_tokens
from utils.coros_adapter import CorosAdapter, remove_cached_coros_tokens
from utils.security import hash_password, verify_password
from utils.wechat import wechat_client

logger = logging.getLogger("router_auth")
router = APIRouter()

# ── Request Models ────────────────────────────────────────────────────────────

class WeChatMiniAppLoginRequest(BaseModel):
    code: str
    client_uuid: Optional[str] = None
    phone_code: Optional[str] = None
    nick_name: Optional[str] = None
    avatar_url: Optional[str] = None
    inviter_uid: Optional[str] = None
    check_only: Optional[bool] = False

class WeChatAppLoginRequest(BaseModel):
    code: Optional[str] = None
    unionid: Optional[str] = None
    openid: Optional[str] = None
    access_token: Optional[str] = None
    nick_name: Optional[str] = None
    avatar_url: Optional[str] = None
    client_uuid: Optional[str] = None
    inviter_uid: Optional[str] = None

class AppleLoginRequest(BaseModel):
    apple_user_id: str
    identity_token: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    client_uuid: Optional[str] = None

class WeChatConfirmLoginRequest(BaseModel):
    uid: Optional[str] = None
    wechat_id: Optional[str] = None
    agree_terms: bool = True

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
    mfa_code: Optional[str] = None
    inviter_uid: Optional[str] = None

class GarminUnbindRequest(BaseModel):
    uid: str

class CorosBindRequest(BaseModel):
    uid: str
    account: str
    password: Optional[str] = ""
    domain: str = "teamcnapi.coros.com" # "teamcnapi.coros.com" or "teamapi.coros.com"
    code: Optional[str] = None
    mfa_code: Optional[str] = None
    inviter_uid: Optional[str] = None

class CorosUnbindRequest(BaseModel):
    uid: str

class DeviceLoginRequest(BaseModel):
    brand: str = "garmin" # "garmin" or "coros"
    account: str
    password: str
    domain: Optional[str] = None
    mfa_code: Optional[str] = None
    client_uuid: Optional[str] = None
    code: Optional[str] = None
    uid: Optional[str] = None

class SwitchAccountRequest(BaseModel):
    target_uid: str
    client_uuid: Optional[str] = None
    code: Optional[str] = None

PENDING_MFA_ADAPTERS: Dict[str, Any] = {}
PENDING_COROS_2FA_ADAPTERS: Dict[str, Any] = {}

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/email/signup")
def email_signup(request: EmailSignUpRequest):
    """
    Email registration endpoint for Web client.
    Hashes password with PBKDF2-SHA256, persists profile in LocalStore, and returns JWT session.
    """
    import hashlib
    import time
    import jwt
    from datetime import datetime
    from utils.local_store import LocalStore, sqlite3, DB_PATH

    email = request.email.strip().lower()
    if "@" not in email or len(email) < 5:
        raise HTTPException(status_code=400, detail="请输入有效的邮箱地址")
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="密码长度不能少于 6 位")

    uid = "u_" + hashlib.md5(email.encode("utf-8")).hexdigest()[:12]
    display_name = (request.display_name or email.split("@")[0]).strip()

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        existing = conn.execute(
            "SELECT id, email, garmin_email, password_hash FROM profiles WHERE id = ? OR LOWER(COALESCE(email, '')) = ? OR LOWER(COALESCE(garmin_email, '')) = ?",
            (uid, email, email),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="该邮箱已被注册或已关联运动手表，请直接登录")

    pw_hash = hash_password(request.password)
    LocalStore.upsert_profile(uid, {
        "id": uid,
        "email": email,
        "display_name": display_name,
        "password_hash": pw_hash,
        "garmin_connected": 0,
        "created_at": datetime.utcnow().isoformat() + "Z",
    })

    if supabase_admin:
        try:
            supabase_admin.table("profiles").upsert({
                "id": uid,
                "email": email,
                "display_name": display_name,
                "garmin_connected": False
            }).execute()
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
            "garmin_connected": False,
            "is_coach_or_owner": LocalStore.is_user_coach_or_owner(uid),
            "is_admin": LocalStore.is_super_admin(uid),
        },
        "message": "注册成功"
    }

@router.post("/email/login")
def email_login(request: EmailLoginRequest):
    """
    Email / Account login endpoint for Web client.
    Supports email, bound Garmin email/phone, bound COROS account (phone/email), or registered phone number.
    Strictly verifies PBKDF2 password_hash or bound watch password on every login.
    """
    import hashlib
    import hmac
    import time
    import jwt

    account_input = request.email.strip()
    if account_input.startswith("+86"):
        account_input = account_input[3:].lstrip("- ").strip()
    email = account_input.lower()
    pwd = (request.password or "").strip()
    if not account_input or not pwd:
        raise HTTPException(status_code=400, detail="请输入登录账号和密码")

    # Also support phone@coros.com or phone@rgm.run convenience format
    alt_account = email.split("@")[0] if email.endswith(("@coros.com", "@rgm.run", "@garmin.cn")) else email

    uid = "u_" + hashlib.md5(email.encode("utf-8")).hexdigest()[:12]
    display_name = account_input.split("@")[0]
    garmin_connected = False
    coros_connected = False

    from utils.local_store import LocalStore, sqlite3, DB_PATH
    from utils.encryption import decrypt_pii
    local_p = LocalStore.get_profile(uid)
    if not local_p:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT * FROM profiles
                    WHERE LOWER(COALESCE(email, '')) IN (?, ?)
                       OR LOWER(COALESCE(garmin_email, '')) IN (?, ?)
                       OR LOWER(COALESCE(coros_account, '')) IN (?, ?)
                    """,
                    (email, alt_account, email, alt_account, email, alt_account),
                ).fetchall()
                matched_row = rows[0] if rows else None
                if not matched_row:
                    phone_rows = conn.execute("SELECT * FROM profiles WHERE phone IS NOT NULL AND phone != ''").fetchall()
                    for r in phone_rows:
                        dec_phone = decrypt_pii(r["phone"] or "")
                        if dec_phone in (account_input, alt_account):
                            matched_row = r
                            break
                if matched_row:
                    local_p = dict(matched_row)
                    uid = local_p.get("id") or uid
        except Exception as e:
            logger.warning(f"[auth] LocalStore account lookup fallback ({e})")

    if not local_p:
        if "@" not in account_input:
            raise HTTPException(
                status_code=400,
                detail="未找到该手机号关联的跑者档案。若您使用高驰或佳明手表，请切换至「高驰 / 佳明直登」直接使用手表账号密码登录",
            )
        raise HTTPException(
            status_code=401,
            detail="该邮箱尚未注册，请先注册账号或使用「高驰 / 佳明直登」",
        )

    stored_pw_hash = local_p.get("password_hash") or ""
    saved_coros_pwd = decrypt_string(local_p.get("coros_encrypted_password") or "") if local_p.get("coros_encrypted_password") else ""
    saved_garmin_pwd = decrypt_string(local_p.get("garmin_encrypted_password") or "") if local_p.get("garmin_encrypted_password") else ""

    pwd_ok = False
    if stored_pw_hash and verify_password(pwd, stored_pw_hash):
        pwd_ok = True
    elif saved_coros_pwd and hmac.compare_digest(pwd.encode("utf-8"), saved_coros_pwd.encode("utf-8")):
        pwd_ok = True
    elif saved_garmin_pwd and hmac.compare_digest(pwd.encode("utf-8"), saved_garmin_pwd.encode("utf-8")):
        pwd_ok = True

    if not pwd_ok and local_p.get("coros_account"):
        c_dom = local_p.get("coros_domain") or "teamcnapi.coros.com"
        c_adp = CorosAdapter(account=local_p["coros_account"], password=pwd, domain=c_dom)
        if c_adp.login(force=True, trigger_2fa_sms=False):
            pwd_ok = True
            LocalStore.upsert_profile(uid, {"coros_encrypted_password": encrypt_string(pwd)})
        elif c_adp.needs_2fa:
            raise HTTPException(
                status_code=400,
                detail="该高驰账号已开启手机短信二次验证，请切换至上方「高驰 / 佳明直登」标签页完成验证码登录",
            )
    if not pwd_ok and local_p.get("garmin_email") and HAS_GARMINCONNECT:
        g_dom = local_p.get("garmin_domain") or "garmin.cn"
        g_adp = GarminAdapter(email=local_p["garmin_email"], password=pwd, domain=g_dom)
        if g_adp.login(use_token=False):
            pwd_ok = True
            LocalStore.upsert_profile(uid, {"garmin_encrypted_password": encrypt_string(pwd)})

    if not pwd_ok:
        raise HTTPException(status_code=401, detail="登录密码不正确，请核对您的账号密码或绑定的高驰/佳明密码")

    if not stored_pw_hash:
        LocalStore.upsert_profile(uid, {"password_hash": hash_password(pwd)})

    display_name = local_p.get("display_name") or display_name
    garmin_connected = bool(local_p.get("garmin_connected", False))
    coros_connected = bool(local_p.get("coros_connected", False))
    if not local_p.get("email"):
        email = local_p.get("garmin_email") or local_p.get("coros_account") or email

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
            "avatar_url": (local_p or {}).get("avatar_url") or "",
            "garmin_connected": garmin_connected or coros_connected,
            "coros_connected": coros_connected,
            "is_coach_or_owner": LocalStore.is_user_coach_or_owner(uid),
            "is_admin": LocalStore.is_super_admin(uid),
        }
    }

@router.post("/wechat/miniapp-login")
def wechat_miniapp_login(request: WeChatMiniAppLoginRequest):
    """
    WeChat Mini Program Login.
    Resolves openid from WeChat or stable client_uuid, ensures unique user profile
    in LocalStore, auto-joins flagship club as regular member, and issues JWT token.
    """
    import hashlib
    import time
    import jwt
    from datetime import datetime
    from utils.local_store import LocalStore

    openid = None
    unionid = None
    res = wechat_client.code_to_session(request.code)
    if res and res.get("openid"):
        openid = res["openid"]
        unionid = (res.get("unionid") or "").strip() or None
    elif settings.ENVIRONMENT.lower() == "production":
        raise HTTPException(status_code=401, detail="微信登录凭证无效或已过期，请重新进入小程序重试")
    elif request.client_uuid:
        openid = f"wx_{hashlib.md5(request.client_uuid.encode('utf-8')).hexdigest()[:20]}"
    else:
        openid = f"wx_{hashlib.md5(request.code.encode('utf-8')).hexdigest()[:20]}"

    phone_number = None
    if request.phone_code:
        phone_res = wechat_client.get_phone_number(request.phone_code)
        if phone_res.get("errcode") == 0:
            phone_number = phone_res.get("phone_info", {}).get("phoneNumber")

    # 1. Lookup existing user by unionid first, then openid in LocalStore
    profile_data = LocalStore.get_profile_by_unionid(unionid) if unionid else None
    if not profile_data:
        profile_data = LocalStore.get_profile_by_openid(openid)
    is_new_user = False
    referral_recorded = False
    if profile_data:
        user_id = profile_data["id"]
        update_dict = {}
        if openid and not profile_data.get("wechat_openid"):
            update_dict["wechat_openid"] = openid
        if unionid and profile_data.get("wechat_unionid") != unionid:
            update_dict["wechat_unionid"] = unionid
        cur_name = str(profile_data.get("display_name") or "").strip()
        clean_nick = (request.nick_name or "").strip()
        if clean_nick and clean_nick not in ("微信跑者", "微信用户") and (
            cur_name in ("", "微信跑者", "微信用户", "跑者")
            or cur_name.startswith(("跑者_", "新跑友", "Apple跑者_"))
        ):
            update_dict["display_name"] = clean_nick
        clean_avatar = (request.avatar_url or "").strip()
        if clean_avatar and not clean_avatar.endswith("/logo-square.png") and (
            not profile_data.get("avatar_url") or clean_nick
        ):
            update_dict["avatar_url"] = clean_avatar
        if phone_number and not profile_data.get("phone"):
            update_dict["phone"] = phone_number
        if update_dict:
            LocalStore.upsert_profile(user_id, update_dict)
            profile_data.update(update_dict)

        # If this user was created recently or has not bound any watch yet and has no inviter yet
        if request.inviter_uid and not profile_data.get("invited_by"):
            has_any_watch = bool(
                profile_data.get("garmin_connected")
                or profile_data.get("coros_connected")
                or profile_data.get("apple_watch_connected")
                or profile_data.get("huawei_connected")
                or profile_data.get("suunto_connected")
            )
            created_at_str = profile_data.get("created_at") or ""
            within_window = False
            try:
                clean_dt = created_at_str.replace("Z", "")
                created_dt = datetime.fromisoformat(clean_dt)
                if (datetime.utcnow() - created_dt).total_seconds() < 86400 * 7:
                    within_window = True
            except Exception:
                pass
            if not has_any_watch or within_window:
                referral_recorded = LocalStore.record_referral(request.inviter_uid, user_id)
    else:
        if request.check_only:
            return {
                "found_existing": False,
                "is_new_user": True,
                "uid": None,
                "token": None,
            }
        # 2. Create brand new unique user
        is_new_user = True
        user_id = f"u_wx_{hashlib.md5(openid.encode('utf-8')).hexdigest()[:10]}"
        display_name = request.nick_name or f"跑者_{user_id[-4:]}"
        profile_data = {
            "id": user_id,
            "wechat_openid": openid,
            "wechat_unionid": unionid,
            "display_name": display_name,
            "avatar_url": request.avatar_url or "",
            "phone": phone_number,
            "garmin_connected": 0,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
        LocalStore.upsert_profile(user_id, profile_data)
        if request.inviter_uid:
            referral_recorded = LocalStore.record_referral(request.inviter_uid, user_id)

    LocalStore.bind_user_identity(user_id, "wechat_openid", openid)
    if unionid:
        LocalStore.bind_user_identity(user_id, "wechat_unionid", unionid)

    # 3. Issue standard JWT token
    payload = {
        "sub": user_id,
        "uid": user_id,
        "openid": openid,
        "aud": "authenticated",
        "exp": int(time.time()) + 86400 * 30,  # 30 days
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

    return {
        "token": token,
        "uid": user_id,
        "openid": openid,
        "display_name": profile_data.get("display_name") or "微信跑者",
        "avatar_url": profile_data.get("avatar_url") or "",
        "garmin_connected": bool(profile_data.get("garmin_connected", False)),
        "garmin_email": profile_data.get("garmin_email") or "",
        "garmin_domain": profile_data.get("garmin_domain") or "garmin.cn",
        "coros_connected": bool(profile_data.get("coros_connected", False)),
        "coros_account": profile_data.get("coros_account") or "",
        "coros_domain": profile_data.get("coros_domain") or "teamcnapi.coros.com",
        "apple_watch_connected": bool(profile_data.get("apple_watch_connected", False)),
        "huawei_connected": bool(profile_data.get("huawei_connected", False)),
        "huawei_account": profile_data.get("huawei_account") or "",
        "suunto_connected": bool(profile_data.get("suunto_connected", False)),
        "suunto_account": profile_data.get("suunto_account") or "",
        "role": "coach" if LocalStore.is_user_coach_or_owner(user_id) else "member",
        "is_coach_or_owner": LocalStore.is_user_coach_or_owner(user_id),
        "is_admin": LocalStore.is_super_admin(user_id),
        "is_new_user": is_new_user,
        "found_existing": not is_new_user,
        "referral_recorded": referral_recorded
    }


@router.post("/app/wechat-login")
def wechat_app_login(request: WeChatAppLoginRequest):
    """
    iOS / Android App Native WeChat Login.
    Matches user profile via wechat_unionid or openid across WeChat Mini Program and App,
    ensuring 100% data consistency.
    """
    import hashlib
    import time
    import jwt
    from datetime import datetime
    from utils.local_store import LocalStore

    is_prod = settings.ENVIRONMENT.lower() == "production"
    unionid = None if is_prod else request.unionid
    openid = None if is_prod else request.openid

    if request.code and (not openid or not unionid):
        try:
            import urllib.request
            import json
            app_id = getattr(settings, "WECHAT_APP_ID", None) or getattr(settings, "WECHAT_MINIAPP_APPID", "")
            app_secret = getattr(settings, "WECHAT_APP_SECRET", None) or getattr(settings, "WECHAT_MINIAPP_SECRET", "")
            if app_id and app_secret:
                url = f"https://api.weixin.qq.com/sns/oauth2/access_token?appid={app_id}&secret={app_secret}&code={request.code}&grant_type=authorization_code"
                req = urllib.request.Request(url, headers={"User-Agent": "RGM-Backend"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    token_data = json.loads(resp.read().decode())
                    if token_data.get("openid"):
                        openid = token_data.get("openid")
                    if token_data.get("unionid"):
                        unionid = token_data.get("unionid")
        except Exception as e:
            logger.warning(f"[wechat_app_login] code exchange notice: {e}")

    if is_prod and not openid:
        raise HTTPException(status_code=401, detail="缺少或无效的微信授权 code")
    if not unionid and not openid and not request.client_uuid:
        raise HTTPException(status_code=400, detail="缺少微信授权凭证 (openid/unionid/code)")

    profile_data = None
    # 1. First priority: match by unionid (Cross-platform unified identity between Mini Program & App)
    if unionid:
        profile_data = LocalStore.get_profile_by_unionid(unionid)

    # 2. Second priority: match by openid
    if not profile_data and openid:
        profile_data = LocalStore.get_profile_by_openid(openid)

    if profile_data:
        user_id = profile_data["id"]
        update_dict = {}
        if unionid and not profile_data.get("wechat_unionid"):
            update_dict["wechat_unionid"] = unionid
        if openid and not profile_data.get("wechat_openid"):
            update_dict["wechat_openid"] = openid
        cur_app_name = str(profile_data.get("display_name") or "").strip()
        if request.nick_name and (
            cur_app_name in ("", "微信跑者", "微信用户", "跑者")
            or cur_app_name.startswith(("跑者_", "新跑友", "Apple跑者_"))
        ):
            update_dict["display_name"] = request.nick_name
        if request.avatar_url and not profile_data.get("avatar_url"):
            update_dict["avatar_url"] = request.avatar_url
        if update_dict:
            LocalStore.upsert_profile(user_id, update_dict)
            profile_data.update(update_dict)
    else:
        # Create brand new user
        key_seed = unionid or openid or request.client_uuid or str(time.time())
        user_id = f"u_app_{hashlib.md5(key_seed.encode('utf-8')).hexdigest()[:10]}"
        display_name = request.nick_name or f"跑者_{user_id[-4:]}"
        profile_data = {
            "id": user_id,
            "wechat_unionid": unionid,
            "wechat_openid": openid,
            "display_name": display_name,
            "avatar_url": request.avatar_url or "",
            "garmin_connected": 0,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
        LocalStore.upsert_profile(user_id, profile_data)

    # Issue standard JWT token
    payload = {
        "sub": user_id,
        "uid": user_id,
        "aud": "authenticated",
        "exp": int(time.time()) + 86400 * 30,  # 30 days
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

    return {
        "token": token,
        "uid": user_id,
        "openid": openid or "",
        "unionid": unionid or "",
        "display_name": profile_data.get("display_name") or "跑者",
        "avatar_url": profile_data.get("avatar_url") or "",
        "garmin_connected": bool(profile_data.get("garmin_connected", False)),
        "garmin_email": profile_data.get("garmin_email") or "",
        "garmin_domain": profile_data.get("garmin_domain") or "garmin.cn",
        "coros_connected": bool(profile_data.get("coros_connected", False)),
        "coros_account": profile_data.get("coros_account") or "",
        "coros_domain": profile_data.get("coros_domain") or "teamcnapi.coros.com",
        "apple_watch_connected": bool(profile_data.get("apple_watch_connected", False)),
        "huawei_connected": bool(profile_data.get("huawei_connected", False)),
        "huawei_account": profile_data.get("huawei_account") or "",
        "suunto_connected": bool(profile_data.get("suunto_connected", False)),
        "suunto_account": profile_data.get("suunto_account") or "",
        "role": "member"
    }


@router.post("/apple/login")
def apple_login(request: AppleLoginRequest):
    """
    Sign in with Apple (Mandatory for iOS App Store).
    Identifies or creates user by apple_user_id or email, maintaining consistency with web/miniapp.
    """
    import hashlib
    import time
    import jwt
    from datetime import datetime
    from utils.local_store import LocalStore

    if not request.apple_user_id:
        raise HTTPException(status_code=400, detail="缺少 Apple 用户凭证 (apple_user_id)")

    profile_data = LocalStore.get_profile_by_apple_id(request.apple_user_id)

    if not profile_data:
        user_id = f"u_apl_{hashlib.md5(request.apple_user_id.encode('utf-8')).hexdigest()[:10]}"
        display_name = request.full_name or f"Apple跑者_{user_id[-4:]}"
        profile_data = {
            "id": user_id,
            "apple_user_id": request.apple_user_id,
            "email": request.email or "",
            "display_name": display_name,
            "avatar_url": "",
            "garmin_connected": 0,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
        LocalStore.upsert_profile(user_id, profile_data)
    else:
        user_id = profile_data["id"]
        update_dict = {}
        if not profile_data.get("apple_user_id"):
            update_dict["apple_user_id"] = request.apple_user_id
        cur_apl_name = str(profile_data.get("display_name") or "").strip()
        if request.full_name and (
            cur_apl_name in ("", "跑者", "微信跑者", "微信用户")
            or cur_apl_name.startswith(("跑者_", "Apple跑者_", "新跑友"))
        ):
            update_dict["display_name"] = request.full_name
        if update_dict:
            LocalStore.upsert_profile(user_id, update_dict)
            profile_data.update(update_dict)

    # Issue standard JWT token
    payload = {
        "sub": user_id,
        "uid": user_id,
        "aud": "authenticated",
        "exp": int(time.time()) + 86400 * 30,  # 30 days
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

    return {
        "token": token,
        "uid": user_id,
        "display_name": profile_data.get("display_name") or "Apple跑者",
        "avatar_url": profile_data.get("avatar_url") or "",
        "garmin_connected": bool(profile_data.get("garmin_connected", False)),
        "garmin_email": profile_data.get("garmin_email") or "",
        "garmin_domain": profile_data.get("garmin_domain") or "garmin.cn",
        "coros_connected": bool(profile_data.get("coros_connected", False)),
        "coros_account": profile_data.get("coros_account") or "",
        "coros_domain": profile_data.get("coros_domain") or "teamcnapi.coros.com",
        "apple_watch_connected": bool(profile_data.get("apple_watch_connected", False)),
        "huawei_connected": bool(profile_data.get("huawei_connected", False)),
        "huawei_account": profile_data.get("huawei_account") or "",
        "suunto_connected": bool(profile_data.get("suunto_connected", False)),
        "suunto_account": profile_data.get("suunto_account") or "",
        "role": "member"
    }


@router.post("/demo-login")
def demo_login():
    """
    Demo account login for App Store reviewers / product demos.
    Always signs into a dedicated synthetic account (no real user data),
    seeding / topping up its synthetic activities, health and races.
    """
    import time
    import jwt
    from utils.demo_seed import ensure_demo_account, DEMO_UID

    profile_data = ensure_demo_account()
    payload = {
        "sub": DEMO_UID,
        "uid": DEMO_UID,
        "aud": "authenticated",
        "exp": int(time.time()) + 86400 * 7,
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
    return {
        "token": token,
        "uid": DEMO_UID,
        "display_name": profile_data.get("display_name") or "演示跑者",
        "avatar_url": profile_data.get("avatar_url") or "",
        "garmin_connected": False,
        "garmin_email": "",
        "garmin_domain": "garmin.cn",
        "coros_connected": False,
        "coros_account": "",
        "coros_domain": "teamcnapi.coros.com",
        "role": "member",
        "is_demo": True
    }


@router.get("/available-users")
@router.get("/wechat/available-users")
def get_available_users():
    """
    Strict security protection: do not leak existing user identities.
    """
    return {"users": []}


@router.post("/wechat/switch-account")
@router.post("/switch-account")
def switch_account(request: SwitchAccountRequest):
    """
    Strict security protection: forbid arbitrary switching into other runners' accounts.
    Users must authenticate through their own WeChat OpenID or bind Garmin/COROS
    with their own credentials.
    """
    raise HTTPException(
        status_code=403,
        detail="安全保护：非本人微信授权不可进入他人账号。如需同步历史运动数据，请在个人中心通过账号密码绑定您的佳明或高驰设备。"
    )


@router.post("/device-login")
def device_login(request: DeviceLoginRequest, background_tasks: BackgroundTasks):
    """
    Direct Watch Device Authentication (Garmin / COROS).
    Authenticates directly with official Garmin or COROS servers using user's credentials.
    If valid:
    - Finds or links their existing runner profile in LocalStore (e.g. u_df65d9a588c9 for azwan56@hotmail.com)
    - Updates wechat_openid to link their current WeChat session
    - Issues authenticated JWT session
    - Triggers background sync
    Provides 100% secure, password-verified account login and recovery.
    """
    import hashlib
    import time
    import jwt
    from datetime import datetime
    from utils.local_store import LocalStore, DB_PATH
    from utils.encryption import encrypt_string, decrypt_string
    import sqlite3

    brand = (request.brand or "garmin").lower().strip()
    account = (request.account or "").strip()
    if account.startswith("+86"):
        account = account[3:].lstrip("- ").strip()
    pwd = (request.password or "").strip()

    if not account or not pwd:
        raise HTTPException(status_code=400, detail="请输入账号和密码")

    openid = None
    if request.code:
        res = wechat_client.code_to_session(request.code)
        if res and res.get("openid"):
            openid = res["openid"]
    if not openid and request.client_uuid:
        openid = f"wx_{hashlib.md5(request.client_uuid.encode('utf-8')).hexdigest()[:20]}"

    encrypted_pwd = encrypt_string(pwd)

    if brand == "garmin":
        domain = (request.domain or "garmin.cn").lower().strip()
        if "garmin.com" in domain or domain in ("global", "us"):
            domain = "garmin.com"
        else:
            domain = "garmin.cn"

        email_key = f"{account.lower()}::{domain}"
        existing_p = LocalStore.get_profile_by_garmin_email(account)
        password_verified = False
        if request.mfa_code and email_key in PENDING_MFA_ADAPTERS:
            adapter = PENDING_MFA_ADAPTERS[email_key]
            if not adapter.client:
                adapter.login()
            ok = adapter.complete_mfa(request.mfa_code)
            if not ok:
                raise HTTPException(status_code=400, detail=adapter.last_error or "验证码错误或已失效")
            PENDING_MFA_ADAPTERS.pop(email_key, None)
            password_verified = True
        elif existing_p:
            saved_pwd = decrypt_string(existing_p.get("garmin_encrypted_password", ""))
            if saved_pwd and saved_pwd == pwd:
                password_verified = True

        if not password_verified:
            adapter = GarminAdapter(email=account, password=pwd, domain=domain)
            if HAS_GARMINCONNECT:
                ok = adapter.login(use_token=False)
                if not ok:
                    if adapter.needs_mfa:
                        PENDING_MFA_ADAPTERS[email_key] = adapter
                        return {
                            "success": False,
                            "needs_mfa": True,
                            "message": "佳明官方已向您的注册邮箱或手机发送安全验证码，请输入验证码完成登录",
                            "email": account,
                            "domain": domain
                        }
                    raise HTTPException(status_code=400, detail=adapter.last_error or f"佳明账号或密码错误（区域：{domain}）")
        if existing_p:
            user_id = existing_p["id"]
            update_data = {
                "garmin_connected": 1,
                "garmin_email": account,
                "garmin_encrypted_password": encrypted_pwd,
                "garmin_domain": domain,
            }
            if openid and (not openid.startswith("wx_") or not existing_p.get("wechat_openid")):
                old_wx_p = LocalStore.get_profile_by_openid(openid)
                if old_wx_p and old_wx_p["id"] != user_id:
                    if str(old_wx_p["id"]).startswith("u_wx_") and not old_wx_p.get("garmin_connected") and not old_wx_p.get("coros_connected"):
                        LocalStore.merge_user_profiles(old_wx_p["id"], user_id, drop_transient_watch_activities=True)
                    else:
                        with sqlite3.connect(DB_PATH) as conn:
                            conn.execute("UPDATE profiles SET wechat_openid = NULL WHERE id = ?", (old_wx_p["id"],))
                            conn.commit()
                update_data["wechat_openid"] = openid
            LocalStore.upsert_profile(user_id, update_data)
            LocalStore.bind_user_identity(user_id, "garmin", account.lower())
            if openid:
                LocalStore.bind_user_identity(user_id, "wechat_openid", openid)
            profile = LocalStore.get_profile(user_id)
        else:
            user_id = f"u_garmin_{hashlib.md5(account.lower().encode('utf-8')).hexdigest()[:10]}"
            name = account.split("@")[0]
            profile = {
                "id": user_id,
                "email": account,
                "display_name": name,
                "garmin_connected": 1,
                "garmin_email": account,
                "garmin_encrypted_password": encrypted_pwd,
                "garmin_domain": domain,
                "created_at": datetime.utcnow().isoformat() + "Z"
            }
            LocalStore.upsert_profile(user_id, profile)
            if openid:
                old_wx_p = LocalStore.get_profile_by_openid(openid)
                if old_wx_p and old_wx_p["id"] != user_id:
                    if str(old_wx_p["id"]).startswith("u_wx_") and not old_wx_p.get("garmin_connected") and not old_wx_p.get("coros_connected"):
                        LocalStore.merge_user_profiles(old_wx_p["id"], user_id, profile_updates={"wechat_openid": openid}, drop_transient_watch_activities=True)
                    else:
                        with sqlite3.connect(DB_PATH) as conn:
                            conn.execute("UPDATE profiles SET wechat_openid = NULL WHERE id = ?", (old_wx_p["id"],))
                            conn.commit()
                        LocalStore.upsert_profile(user_id, {"wechat_openid": openid})
                else:
                    LocalStore.upsert_profile(user_id, {"wechat_openid": openid})
                LocalStore.bind_user_identity(user_id, "wechat_openid", openid)
            LocalStore.bind_user_identity(user_id, "garmin", account.lower())
            profile = LocalStore.get_profile(user_id) or profile

    elif brand == "coros":
        domain = (request.domain or "teamcnapi.coros.com").lower().strip()
        if "teamapi" not in domain and "teamcnapi" not in domain:
            domain = "teamcnapi.coros.com"

        account_key = f"{account.lower()}::{domain}"
        code = (request.mfa_code or request.code or "").strip()

        existing_p = LocalStore.get_profile_by_coros_account(account)
        if code and account_key in PENDING_COROS_2FA_ADAPTERS:
            adapter = PENDING_COROS_2FA_ADAPTERS[account_key]
            ok = adapter.complete_2fa(code)
            if not ok:
                raise HTTPException(status_code=400, detail=adapter.last_error or "高驰验证码错误或已失效")
            PENDING_COROS_2FA_ADAPTERS.pop(account_key, None)
        else:
            password_verified = False
            if existing_p:
                saved_pwd = decrypt_string(existing_p.get("coros_encrypted_password", ""))
                c_state = CorosAdapter.get_cached_auth_state(account, domain)
                if saved_pwd and saved_pwd == pwd and not c_state.get("needs_reauth") and c_state.get("has_token"):
                    password_verified = True

            if not password_verified:
                adapter = CorosAdapter(account=account, password=pwd, domain=domain)
                ok = adapter.login(force=True, trigger_2fa_sms=True)
                if not ok:
                    if adapter.needs_2fa:
                        PENDING_COROS_2FA_ADAPTERS[account_key] = adapter
                        return {
                            "success": False,
                            "needs_mfa": True,
                            "needs_2fa": True,
                            "message": adapter.last_error or "高驰官方已向您的注册手机发送安全验证码，请输入验证码完成登录",
                            "account": account,
                            "domain": domain
                        }
                    raise HTTPException(status_code=400, detail=adapter.last_error or f"高驰账号或密码错误（区域：{domain}）")
        if existing_p:
            user_id = existing_p["id"]
            update_data = {
                "coros_connected": 1,
                "coros_account": account,
                "coros_encrypted_password": encrypted_pwd,
                "coros_domain": domain,
            }
            if openid and (not openid.startswith("wx_") or not existing_p.get("wechat_openid")):
                old_wx_p = LocalStore.get_profile_by_openid(openid)
                if old_wx_p and old_wx_p["id"] != user_id:
                    if str(old_wx_p["id"]).startswith("u_wx_") and not old_wx_p.get("garmin_connected") and not old_wx_p.get("coros_connected"):
                        LocalStore.merge_user_profiles(old_wx_p["id"], user_id, drop_transient_watch_activities=True)
                    else:
                        with sqlite3.connect(DB_PATH) as conn:
                            conn.execute("UPDATE profiles SET wechat_openid = NULL WHERE id = ?", (old_wx_p["id"],))
                            conn.commit()
                update_data["wechat_openid"] = openid
            LocalStore.upsert_profile(user_id, update_data)
            LocalStore.bind_user_identity(user_id, "coros", account.lower())
            if openid:
                LocalStore.bind_user_identity(user_id, "wechat_openid", openid)
            profile = LocalStore.get_profile(user_id)
        else:
            user_id = f"u_coros_{hashlib.md5(account.lower().encode('utf-8')).hexdigest()[:10]}"
            profile = {
                "id": user_id,
                "display_name": account,
                "coros_connected": 1,
                "coros_account": account,
                "coros_encrypted_password": encrypted_pwd,
                "coros_domain": domain,
                "created_at": datetime.utcnow().isoformat() + "Z"
            }
            LocalStore.upsert_profile(user_id, profile)
            if openid:
                old_wx_p = LocalStore.get_profile_by_openid(openid)
                if old_wx_p and old_wx_p["id"] != user_id:
                    if str(old_wx_p["id"]).startswith("u_wx_") and not old_wx_p.get("garmin_connected") and not old_wx_p.get("coros_connected"):
                        LocalStore.merge_user_profiles(old_wx_p["id"], user_id, profile_updates={"wechat_openid": openid}, drop_transient_watch_activities=True)
                    else:
                        with sqlite3.connect(DB_PATH) as conn:
                            conn.execute("UPDATE profiles SET wechat_openid = NULL WHERE id = ?", (old_wx_p["id"],))
                            conn.commit()
                        LocalStore.upsert_profile(user_id, {"wechat_openid": openid})
                else:
                    LocalStore.upsert_profile(user_id, {"wechat_openid": openid})
                LocalStore.bind_user_identity(user_id, "wechat_openid", openid)
            LocalStore.bind_user_identity(user_id, "coros", account.lower())
            profile = LocalStore.get_profile(user_id) or profile
    else:
        raise HTTPException(status_code=400, detail="不支持的设备品牌")

    from routers.sync import sync_single_user
    background_tasks.add_task(sync_single_user, user_id)

    payload = {
        "sub": user_id,
        "uid": user_id,
        "aud": "authenticated",
        "exp": int(time.time()) + 86400 * 30,
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

    user_email_val = profile.get("email") or profile.get("garmin_email") or profile.get("coros_account") or account
    is_coach_owner = LocalStore.is_user_coach_or_owner(user_id)
    return {
        "success": True,
        "token": token,
        "uid": user_id,
        "display_name": profile.get("display_name", "微信跑者"),
        "avatar_url": profile.get("avatar_url", ""),
        "garmin_connected": bool(profile.get("garmin_connected")),
        "garmin_email": profile.get("garmin_email", ""),
        "garmin_domain": profile.get("garmin_domain", "garmin.cn"),
        "coros_connected": bool(profile.get("coros_connected")),
        "coros_account": profile.get("coros_account", ""),
        "coros_domain": profile.get("coros_domain", "teamcnapi.coros.com"),
        "apple_watch_connected": bool(profile.get("apple_watch_connected", False)),
        "huawei_connected": bool(profile.get("huawei_connected", False)),
        "huawei_account": profile.get("huawei_account", ""),
        "suunto_connected": bool(profile.get("suunto_connected", False)),
        "suunto_account": profile.get("suunto_account", ""),
        "is_coach_or_owner": is_coach_owner,
        "user": {
            "id": user_id,
            "email": user_email_val,
            "display_name": profile.get("display_name") or account,
            "avatar_url": profile.get("avatar_url") or "",
            "garmin_connected": bool(profile.get("garmin_connected") or profile.get("coros_connected")),
            "coros_connected": bool(profile.get("coros_connected")),
            "is_coach_or_owner": is_coach_owner,
            "is_admin": LocalStore.is_super_admin(user_id),
        },
        "message": "运动手表验证通过，已成功进入跑者档案！"
    }


@router.post("/wechat/confirm-login")
def wechat_confirm_login(request: WeChatConfirmLoginRequest):
    """
    Explicit login flow:
    - Sets user display name / custom identity
    - Strictly blocks hijacking of ALL existing accounts
    - Must agree to terms
    - Issues JWT session and sets profile
    """
    if not request.agree_terms:
        raise HTTPException(status_code=400, detail="必须同意用户条款与隐私政策")

    import hashlib
    import time
    import jwt
    from datetime import datetime
    from utils.local_store import LocalStore

    wechat_id = (request.wechat_id or "").strip()
    uid = (request.uid or "").strip()

    if not uid and not wechat_id:
        raise HTTPException(status_code=400, detail="请输入您的微信号或跑者昵称")

    if not uid:
        uid = f"u_wx_{hashlib.md5(wechat_id.encode('utf-8')).hexdigest()[:10]}"

    existing_profile = LocalStore.get_profile(uid)
    if existing_profile:
        raise HTTPException(
            status_code=403,
            detail="安全保护：该跑者档案已存在，不可无凭证选定登录。请通过微信授权、邮箱密码或运动手表账号验证登录。",
        )

    profile = {
        "id": uid,
        "display_name": wechat_id or f"跑者_{uid[-4:]}",
        "avatar_url": "",
        "garmin_connected": 0,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    LocalStore.upsert_profile(uid, profile)
    LocalStore.join_club_by_code(uid, "RGM888")

    payload = {
        "sub": uid,
        "uid": uid,
        "aud": "authenticated",
        "exp": int(time.time()) + 86400 * 30,
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

    return {
        "token": token,
        "user": {
            "id": uid,
            "display_name": profile.get("display_name") or "微信跑者",
            "avatar_url": profile.get("avatar_url") or "",
            "garmin_connected": bool(profile.get("garmin_connected", False)),
            "garmin_email": profile.get("garmin_email") or "",
            "garmin_domain": profile.get("garmin_domain") or "garmin.cn",
            "coros_connected": bool(profile.get("coros_connected", False)),
            "coros_account": profile.get("coros_account") or "",
            "coros_domain": profile.get("coros_domain") or "teamcnapi.coros.com",
            "apple_watch_connected": bool(profile.get("apple_watch_connected", False)),
            "huawei_connected": bool(profile.get("huawei_connected", False)),
            "huawei_account": profile.get("huawei_account") or "",
        }
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

    from utils.local_store import LocalStore, DB_PATH
    import sqlite3

    email_key = request.email.strip().lower()
    existing_p = LocalStore.get_profile_by_garmin_email(request.email)
    password_verified = False
    if existing_p and not request.mfa_code:
        saved_pwd = decrypt_string(existing_p.get("garmin_encrypted_password", ""))
        if saved_pwd and saved_pwd == request.password:
            password_verified = True

    if request.mfa_code:
        # MFA submission path
        adapter = PENDING_MFA_ADAPTERS.get(email_key)
        if not adapter or not adapter.client:
            adapter = GarminAdapter(email=request.email, password=request.password, domain=domain)
            adapter.login()
        ok = adapter.complete_mfa(request.mfa_code)
        if not ok:
            raise HTTPException(status_code=400, detail=adapter.last_error or "验证码错误或已失效，请重新输入邮件/短信中的 6 位验证码")
        PENDING_MFA_ADAPTERS.pop(email_key, None)
    elif not password_verified:
        # Initial login path
        adapter = GarminAdapter(email=request.email, password=request.password, domain=domain)
        # Clear any stale token file on disk so binding always tests fresh credentials
        if os.path.exists(adapter.token_path):
            try:
                os.remove(adapter.token_path)
            except Exception:
                pass
        if HAS_GARMINCONNECT:
            ok = adapter.login(use_token=False)
            if not ok:
                if adapter.needs_mfa:
                    PENDING_MFA_ADAPTERS[email_key] = adapter
                    return {
                        "success": False,
                        "connected": False,
                        "needs_mfa": True,
                        "message": "佳明官方已向您的注册邮箱或手机发送了 6 位安全验证码，请输入验证码完成绑定。",
                        "email": request.email,
                        "domain": domain
                    }
                err_msg = adapter.last_error or ""
                raise HTTPException(status_code=400, detail=err_msg or f"绑定失败，请检查佳明账号、密码及选择的区域（{domain}）。")

    # 2. Encrypt password
    encrypted_pwd = encrypt_string(request.password)
    effective_uid = request.uid

    # Check if this Garmin email is already associated with an existing profile (e.g. u_df65d9a588c9 for Zhong Wan)
    if existing_p and existing_p["id"] != request.uid:
        effective_uid = existing_p["id"]
        # Link current user's wechat openid and apple_user_id to this existing account losslessly
        curr_p = LocalStore.get_profile(request.uid)
        oid = curr_p.get("wechat_openid") if curr_p else None
        apl_id = curr_p.get("apple_user_id") if curr_p else None
        update_data = {
            "garmin_connected": 1,
            "garmin_email": request.email,
            "garmin_encrypted_password": encrypted_pwd,
            "garmin_domain": domain,
            "coros_connected": 0,
            "apple_watch_connected": 0,
            "huawei_connected": 0,
        }
        if oid and (not oid.startswith("wx_") or not existing_p.get("wechat_openid")):
            update_data["wechat_openid"] = oid
        if apl_id:
            update_data["apple_user_id"] = apl_id
        old_inviter = curr_p.get("invited_by") if curr_p else None
        if old_inviter and not existing_p.get("invited_by"):
            update_data["invited_by"] = old_inviter
        LocalStore.merge_user_profiles(
            request.uid,
            effective_uid,
            profile_updates=update_data,
            drop_transient_watch_activities=True,
        )
    else:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM activities WHERE user_id = ? AND (id LIKE 'hk_%' OR id LIKE 'aw_%' OR id LIKE 'hw_%')", (effective_uid,))
            conn.commit()
        LocalStore.upsert_profile(effective_uid, {
            "garmin_connected": 1,
            "garmin_email": request.email,
            "garmin_encrypted_password": encrypted_pwd,
            "garmin_domain": domain,
            "coros_connected": 0,
            "apple_watch_connected": 0,
            "huawei_connected": 0,
        })
    LocalStore.bind_user_identity(effective_uid, "garmin", request.email.strip().lower())

    if request.inviter_uid:
        LocalStore.record_referral(request.inviter_uid, effective_uid)

    if supabase_admin:
        try:
            supabase_admin.table("profiles").update({
                "garmin_connected": True,
                "garmin_email": request.email,
                "garmin_encrypted_password": encrypted_pwd,
                "garmin_domain": domain,
            }).eq("id", effective_uid).execute()
        except Exception as e:
            logger.warning(f"[auth] Supabase garmin update fallback: {e}")

    # 3. Trigger initial background sync
    from routers.sync import sync_single_user
    background_tasks.add_task(sync_single_user, effective_uid)

    import time
    import jwt
    payload = {
        "sub": effective_uid,
        "uid": effective_uid,
        "aud": "authenticated",
        "exp": int(time.time()) + 86400 * 30,
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

    final_p = LocalStore.get_profile(effective_uid) or {}
    return {
        "success": True,
        "connected": True,
        "uid": effective_uid,
        "token": token,
        "display_name": final_p.get("display_name") or request.email.split("@")[0],
        "avatar_url": final_p.get("avatar_url") or "",
        "garmin_connected": True,
        "garmin_email": request.email,
        "garmin_domain": domain,
        "coros_connected": bool(final_p.get("coros_connected")),
        "coros_account": final_p.get("coros_account") or "",
        "coros_domain": final_p.get("coros_domain") or "teamcnapi.coros.com",
        "apple_watch_connected": bool(final_p.get("apple_watch_connected")),
        "huawei_connected": bool(final_p.get("huawei_connected")),
        "huawei_account": final_p.get("huawei_account") or "",
        "message": f"佳明 ({domain}) 账号绑定成功！已开始自动同步最近运动数据。",
        "email": request.email,
        "domain": domain
    }


@router.post("/garmin/unbind")
@router.post("/garmin/disconnect")
def unbind_garmin(request: GarminUnbindRequest, authorization: Optional[str] = Header(None)):
    """Unbinds Garmin account with caller ownership verification."""
    from utils.local_store import LocalStore

    if not request.uid or not request.uid.strip():
        raise HTTPException(status_code=400, detail="缺少用户标识")

    target_p = LocalStore.get_profile(request.uid)
    if not target_p:
        raise HTTPException(status_code=404, detail="未找到对应的跑者档案")

    # Require valid bearer token in production; verify caller ownership whenever token is supplied
    if settings.ENVIRONMENT.lower() == "production" and (not authorization or not authorization.startswith("Bearer ")):
        raise HTTPException(status_code=401, detail="安全拦截：解绑手表必须提供有效的登录令牌")

    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            import jwt
            payload = jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
            caller_uid = payload.get("uid") or payload.get("sub")
            is_admin = payload.get("is_super_admin", False) or LocalStore.is_super_admin(caller_uid)
            if not is_admin and caller_uid and caller_uid != request.uid:
                caller_p = LocalStore.get_profile(caller_uid)
                c_oid = caller_p.get("wechat_openid") if caller_p else None
                t_oid = target_p.get("wechat_openid") if target_p else None
                c_email = caller_p.get("email") if caller_p else None
                t_email = target_p.get("email") if target_p else None
                if (not c_oid or c_oid != t_oid) and (not c_email or c_email != t_email):
                    raise HTTPException(status_code=403, detail="安全拦截：无权操作其他用户的佳明账号绑定")
        except jwt.PyJWTError as e:
            logger.debug(f"[unbind_garmin] Token expired or invalid: {e}")
            raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录后再解绑")

    try:
        remove_cached_garmin_tokens(target_p.get("garmin_email"))
    except Exception as te:
        logger.warning(f"[auth] Failed removing cached Garmin token file: {te}")

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


@router.post("/coros/bind")
@router.post("/coros/connect")
def bind_coros(request: CorosBindRequest, background_tasks: BackgroundTasks):
    """
    Binds COROS (高驰) account (China: teamcnapi.coros.com or Global: teamapi.coros.com),
    encrypts password, and initiates an initial sync.
    Supports 2FA (手机二次安全验证) and passwordless 1-click SMS re-authorization for already-bound owners.
    """
    from utils.local_store import LocalStore, DB_PATH
    import sqlite3

    domain = (request.domain or "teamcnapi.coros.com").lower().strip()
    if "teamapi" not in domain and "teamcnapi" not in domain and domain not in ["cn", "global"]:
        domain = "teamcnapi.coros.com"
    elif domain == "cn":
        domain = "teamcnapi.coros.com"
    elif domain == "global":
        domain = "teamapi.coros.com"

    clean_account = (request.account or "").strip()
    if clean_account.startswith("+86"):
        clean_account = clean_account[3:].lstrip("- ").strip()

    effective_pwd = (request.password or "").strip()
    if not effective_pwd and request.uid:
        curr_owner = LocalStore.get_profile(request.uid)
        if curr_owner and (curr_owner.get("coros_account") or "").strip().lower() == clean_account.lower():
            saved_enc = curr_owner.get("coros_encrypted_password") or ""
            if saved_enc:
                effective_pwd = decrypt_string(saved_enc) or ""

    if not clean_account or not effective_pwd:
        raise HTTPException(status_code=400, detail="请输入高驰账号与登录密码")

    account_key = f"{clean_account.lower()}::{domain}"
    code = (request.code or request.mfa_code or "").strip()

    if code:
        # 2FA code submission path
        adapter = PENDING_COROS_2FA_ADAPTERS.get(account_key)
        if not adapter or not adapter.login_ticket:
            adapter = CorosAdapter(account=clean_account, password=effective_pwd, domain=domain)
            # Re-initiate login to acquire loginTicket if adapter state was lost
            adapter.login(force=True, trigger_2fa_sms=False)
        ok = adapter.complete_2fa(code)
        if not ok:
            raise HTTPException(status_code=400, detail=adapter.last_error or "验证码错误或已失效，请重新输入手机短信中的 6 位验证码")
        PENDING_COROS_2FA_ADAPTERS.pop(account_key, None)
    else:
        # Initial login attempt (force=True ignores cache while preserving needs_2fa circuit-breaker until verified)
        adapter = CorosAdapter(account=clean_account, password=effective_pwd, domain=domain)
        ok = adapter.login(force=True, trigger_2fa_sms=True)
        if not ok:
            if adapter.needs_2fa:
                PENDING_COROS_2FA_ADAPTERS[account_key] = adapter
                return {
                    "success": False,
                    "connected": False,
                    "needs_2fa": True,
                    "message": adapter.last_error or "高驰官方已向您的注册手机发送了 6 位安全验证码，请输入验证码完成绑定。",
                    "account": clean_account,
                    "domain": domain
                }
            err_msg = adapter.last_error or "高驰绑定失败，请检查高驰账号、密码及选择的区域。"
            raise HTTPException(status_code=400, detail=err_msg)

    # 2. Encrypt password
    encrypted_pwd = encrypt_string(effective_pwd)
    effective_uid = request.uid

    # Check if this COROS account is already associated with an existing profile
    existing_p = LocalStore.get_profile_by_coros_account(clean_account)
    if existing_p and existing_p["id"] != request.uid:
        effective_uid = existing_p["id"]
        # Link current user's wechat openid and apple_user_id to this existing account losslessly
        curr_p = LocalStore.get_profile(request.uid)
        oid = curr_p.get("wechat_openid") if curr_p else None
        apl_id = curr_p.get("apple_user_id") if curr_p else None
        update_data = {
            "coros_connected": 1,
            "coros_account": clean_account,
            "coros_encrypted_password": encrypted_pwd,
            "coros_domain": domain,
            "garmin_connected": 0,
            "apple_watch_connected": 0,
            "huawei_connected": 0,
        }
        if oid and (not oid.startswith("wx_") or not existing_p.get("wechat_openid")):
            update_data["wechat_openid"] = oid
        if apl_id:
            update_data["apple_user_id"] = apl_id
        old_inviter = curr_p.get("invited_by") if curr_p else None
        if old_inviter and not existing_p.get("invited_by"):
            update_data["invited_by"] = old_inviter
        LocalStore.merge_user_profiles(
            request.uid,
            effective_uid,
            profile_updates=update_data,
            drop_transient_watch_activities=True,
        )
    else:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM activities WHERE user_id = ? AND (id LIKE 'hk_%' OR id LIKE 'aw_%' OR id LIKE 'hw_%')", (effective_uid,))
            conn.commit()
        LocalStore.upsert_profile(effective_uid, {
            "coros_connected": 1,
            "coros_account": clean_account,
            "coros_encrypted_password": encrypted_pwd,
            "coros_domain": domain,
            "garmin_connected": 0,
            "apple_watch_connected": 0,
            "huawei_connected": 0,
        })
    LocalStore.bind_user_identity(effective_uid, "coros", clean_account.lower())

    if request.inviter_uid:
        LocalStore.record_referral(request.inviter_uid, effective_uid)

    if supabase_admin:
        try:
            supabase_admin.table("profiles").update({
                "coros_connected": True,
                "coros_account": clean_account,
                "coros_encrypted_password": encrypted_pwd,
                "coros_domain": domain,
            }).eq("id", effective_uid).execute()
        except Exception as e:
            logger.warning(f"[auth] Supabase coros update fallback: {e}")

    # 3. Trigger initial background sync
    from routers.sync import sync_single_user
    background_tasks.add_task(sync_single_user, effective_uid)

    import time
    import jwt
    payload = {
        "sub": effective_uid,
        "uid": effective_uid,
        "aud": "authenticated",
        "exp": int(time.time()) + 86400 * 30,
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

    final_p = LocalStore.get_profile(effective_uid) or {}
    return {
        "success": True,
        "connected": True,
        "uid": effective_uid,
        "token": token,
        "display_name": final_p.get("display_name") or request.account,
        "avatar_url": final_p.get("avatar_url") or "",
        "garmin_connected": bool(final_p.get("garmin_connected")),
        "garmin_email": final_p.get("garmin_email") or "",
        "garmin_domain": final_p.get("garmin_domain") or "garmin.cn",
        "coros_connected": True,
        "coros_account": request.account,
        "coros_domain": domain,
        "apple_watch_connected": bool(final_p.get("apple_watch_connected")),
        "huawei_connected": bool(final_p.get("huawei_connected")),
        "huawei_account": final_p.get("huawei_account") or "",
        "message": f"高驰 ({domain}) 账号绑定成功！已开始自动同步最近运动数据。",
        "account": request.account,
        "domain": domain
    }


@router.post("/coros/resend-code")
def resend_coros_code(request: CorosBindRequest):
    """
    Resends 2FA SMS verification code for COROS account.
    """
    domain = request.domain.lower().strip()
    if "teamapi" not in domain and "teamcnapi" not in domain and domain not in ["cn", "global"]:
        domain = "teamcnapi.coros.com"
    account_key = f"{request.account.strip().lower()}::{domain}"
    adapter = PENDING_COROS_2FA_ADAPTERS.get(account_key)
    if not adapter or not adapter.two_fa_account:
        adapter = CorosAdapter(account=request.account, password=request.password, domain=domain)
        adapter.login(force=True, trigger_2fa_sms=True)
        if adapter.needs_2fa:
            PENDING_COROS_2FA_ADAPTERS[account_key] = adapter
            return {"success": True, "message": "已重新发送高驰安全验证码"}
        raise HTTPException(status_code=400, detail=adapter.last_error or "重新发送验证码失败")

    ok = adapter.send_2fa_code()
    if not ok:
        raise HTTPException(status_code=400, detail=adapter.last_error or "重发验证码失败，请稍后重试")
    return {"success": True, "message": "已重新向您的手机发送 6 位验证码"}


@router.post("/coros/unbind")
@router.post("/coros/disconnect")
def unbind_coros(request: CorosUnbindRequest, authorization: Optional[str] = Header(None)):
    """Unbinds COROS account with caller ownership verification."""
    from utils.local_store import LocalStore

    if not request.uid or not request.uid.strip():
        raise HTTPException(status_code=400, detail="缺少用户标识")

    target_p = LocalStore.get_profile(request.uid)
    if not target_p:
        raise HTTPException(status_code=404, detail="未找到对应的跑者档案")

    # Require valid bearer token in production; verify caller ownership whenever token is supplied
    if settings.ENVIRONMENT.lower() == "production" and (not authorization or not authorization.startswith("Bearer ")):
        raise HTTPException(status_code=401, detail="安全拦截：解绑手表必须提供有效的登录令牌")

    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            import jwt
            payload = jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
            caller_uid = payload.get("uid") or payload.get("sub")
            is_admin = payload.get("is_super_admin", False) or LocalStore.is_super_admin(caller_uid)
            if not is_admin and caller_uid and caller_uid != request.uid:
                caller_p = LocalStore.get_profile(caller_uid)
                c_oid = caller_p.get("wechat_openid") if caller_p else None
                t_oid = target_p.get("wechat_openid") if target_p else None
                c_email = caller_p.get("email") if caller_p else None
                t_email = target_p.get("email") if target_p else None
                if (not c_oid or c_oid != t_oid) and (not c_email or c_email != t_email):
                    raise HTTPException(status_code=403, detail="安全拦截：无权操作其他用户的高驰账号绑定")
        except jwt.PyJWTError as e:
            logger.debug(f"[unbind_coros] Token expired or invalid: {e}")
            raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录后再解绑")

    # Remove any cached token files on disk
    try:
        remove_cached_coros_tokens(target_p.get("coros_account"))
    except Exception as te:
        logger.warning(f"[auth] Failed removing cached token file: {te}")

    LocalStore.upsert_profile(request.uid, {
        "coros_connected": 0,
        "coros_encrypted_password": "",
        "coros_account": "",
    })

    if supabase_admin:
        try:
            supabase_admin.table("profiles").update({
                "coros_connected": False,
                "coros_encrypted_password": "",
                "coros_account": "",
            }).eq("id", request.uid).execute()
        except Exception as e:
            logger.warning(f"[auth] Supabase coros unbind fallback: {e}")

    return {
        "success": True,
        "connected": False,
        "message": "高驰账号已成功解除绑定"
    }


class WatchStatusBindRequest(BaseModel):
    uid: str
    account: Optional[str] = None
    inviter_uid: Optional[str] = None


def _get_other_connected_watch_label(profile: Dict[str, Any], target_brand: str) -> Optional[str]:
    if not profile:
        return None
    if target_brand != "garmin" and profile.get("garmin_connected"):
        return "佳明 Garmin"
    if target_brand != "coros" and profile.get("coros_connected"):
        return "高驰 COROS"
    if target_brand != "apple_watch" and profile.get("apple_watch_connected"):
        return "Apple Watch"
    if target_brand != "huawei" and profile.get("huawei_connected"):
        return "华为手表"
    if target_brand != "suunto" and profile.get("suunto_connected"):
        return "颂拓 Suunto"
    return None


@router.post("/apple-watch/bind")
def bind_apple_watch(request: WatchStatusBindRequest):
    """Marks Apple Watch (HealthKit / screenshot / track sync) as bound on the user's profile."""
    from datetime import datetime
    from utils.local_store import LocalStore

    if not request.uid or not request.uid.strip():
        raise HTTPException(status_code=400, detail="缺少用户标识")

    curr_p = LocalStore.get_profile(request.uid) or {}
    if curr_p.get("garmin_connected"):
        raise HTTPException(
            status_code=400,
            detail="您当前已连接【佳明 Garmin】，每个账号仅限连接一个运动手表。如需切换为 Apple Watch，请先解绑佳明账号。"
        )
    if curr_p.get("coros_connected"):
        raise HTTPException(
            status_code=400,
            detail="您当前已连接【高驰 COROS】，每个账号仅限连接一个运动手表。如需切换为 Apple Watch，请先解绑高驰账号。"
        )

    now_iso = datetime.utcnow().isoformat() + "Z"
    LocalStore.upsert_profile(request.uid, {
        "apple_watch_connected": 1,
        "huawei_connected": 0,
        "suunto_connected": 0,
        "apple_watch_last_sync_at": now_iso,
    })
    if request.inviter_uid:
        LocalStore.record_referral(request.inviter_uid, request.uid)
    final_p = LocalStore.get_profile(request.uid) or {}
    return {
        "success": True,
        "connected": True,
        "uid": request.uid,
        "display_name": final_p.get("display_name") or "跑者",
        "avatar_url": final_p.get("avatar_url") or "",
        "garmin_connected": bool(final_p.get("garmin_connected")),
        "garmin_email": final_p.get("garmin_email") or "",
        "garmin_domain": final_p.get("garmin_domain") or "garmin.cn",
        "coros_connected": bool(final_p.get("coros_connected")),
        "coros_account": final_p.get("coros_account") or "",
        "coros_domain": final_p.get("coros_domain") or "teamcnapi.coros.com",
        "apple_watch_connected": True,
        "huawei_connected": False,
        "huawei_account": final_p.get("huawei_account") or "",
        "suunto_connected": False,
        "suunto_account": final_p.get("suunto_account") or "",
        "message": "Apple Watch 已成功连接 ✓ 可点击【选运动截图导入】或【导入 GPX/TCX】同步跑步记录"
    }


@router.post("/apple-watch/unbind")
def unbind_apple_watch(request: WatchStatusBindRequest):
    """Unbinds Apple Watch from the user's profile."""
    from utils.local_store import LocalStore

    if not request.uid or not request.uid.strip():
        raise HTTPException(status_code=400, detail="缺少用户标识")

    LocalStore.upsert_profile(request.uid, {
        "apple_watch_connected": 0,
    })
    return {
        "success": True,
        "connected": False,
        "removed_activities": 0,
        "message": "Apple Watch 已解除连接"
    }


@router.post("/huawei/bind")
def bind_huawei_watch(request: WatchStatusBindRequest):
    """Marks Huawei Watch (via screenshot / track file / Apple Health bridge) as bound."""
    from datetime import datetime
    from utils.local_store import LocalStore

    if not request.uid or not request.uid.strip():
        raise HTTPException(status_code=400, detail="缺少用户标识")

    curr_p = LocalStore.get_profile(request.uid) or {}
    if curr_p.get("garmin_connected"):
        raise HTTPException(
            status_code=400,
            detail="您当前已连接【佳明 Garmin】，每个账号仅限连接一个运动手表。如需切换为华为手表，请先解绑佳明账号。"
        )
    if curr_p.get("coros_connected"):
        raise HTTPException(
            status_code=400,
            detail="您当前已连接【高驰 COROS】，每个账号仅限连接一个运动手表。如需切换为华为手表，请先解绑高驰账号。"
        )

    now_iso = datetime.utcnow().isoformat() + "Z"
    acc = (request.account or "华为运动健康 App").strip()
    LocalStore.upsert_profile(request.uid, {
        "huawei_connected": 1,
        "apple_watch_connected": 0,
        "suunto_connected": 0,
        "huawei_account": acc,
        "huawei_last_sync_at": now_iso,
    })
    if request.inviter_uid:
        LocalStore.record_referral(request.inviter_uid, request.uid)
    final_p = LocalStore.get_profile(request.uid) or {}
    return {
        "success": True,
        "connected": True,
        "uid": request.uid,
        "display_name": final_p.get("display_name") or "跑者",
        "avatar_url": final_p.get("avatar_url") or "",
        "garmin_connected": bool(final_p.get("garmin_connected")),
        "garmin_email": final_p.get("garmin_email") or "",
        "garmin_domain": final_p.get("garmin_domain") or "garmin.cn",
        "coros_connected": bool(final_p.get("coros_connected")),
        "coros_account": final_p.get("coros_account") or "",
        "coros_domain": final_p.get("coros_domain") or "teamcnapi.coros.com",
        "apple_watch_connected": False,
        "huawei_connected": True,
        "huawei_account": acc,
        "suunto_connected": False,
        "suunto_account": final_p.get("suunto_account") or "",
        "message": "华为手表已成功连接 ✓ 可点击【选运动截图导入】或【导入 GPX/TCX】同步跑步记录"
    }


@router.post("/huawei/unbind")
def unbind_huawei_watch(request: WatchStatusBindRequest):
    """Unbinds Huawei Watch from the user's profile (preserving imported activities)."""
    from utils.local_store import LocalStore

    if not request.uid or not request.uid.strip():
        raise HTTPException(status_code=400, detail="缺少用户标识")

    LocalStore.upsert_profile(request.uid, {
        "huawei_connected": 0,
    })
    return {
        "success": True,
        "connected": False,
        "removed_activities": 0,
        "message": "华为手表已解除连接"
    }


@router.post("/suunto/bind")
def bind_suunto_watch(request: WatchStatusBindRequest):
    """Marks Suunto Watch (via screenshot / FIT/GPX track file / Apple Health bridge) as bound."""
    from datetime import datetime
    from utils.local_store import LocalStore

    if not request.uid or not request.uid.strip():
        raise HTTPException(status_code=400, detail="缺少用户标识")

    curr_p = LocalStore.get_profile(request.uid) or {}
    if curr_p.get("garmin_connected"):
        raise HTTPException(
            status_code=400,
            detail="您当前已连接【佳明 Garmin】，每个账号仅限连接一个运动手表。如需切换为颂拓 Suunto，请先解绑佳明账号。"
        )
    if curr_p.get("coros_connected"):
        raise HTTPException(
            status_code=400,
            detail="您当前已连接【高驰 COROS】，每个账号仅限连接一个运动手表。如需切换为颂拓 Suunto，请先解绑高驰账号。"
        )

    now_iso = datetime.utcnow().isoformat() + "Z"
    acc = (request.account or "Suunto App").strip()
    LocalStore.upsert_profile(request.uid, {
        "suunto_connected": 1,
        "apple_watch_connected": 0,
        "huawei_connected": 0,
        "suunto_account": acc,
        "suunto_last_sync_at": now_iso,
    })
    if request.inviter_uid:
        LocalStore.record_referral(request.inviter_uid, request.uid)
    final_p = LocalStore.get_profile(request.uid) or {}
    return {
        "success": True,
        "connected": True,
        "uid": request.uid,
        "display_name": final_p.get("display_name") or "跑者",
        "avatar_url": final_p.get("avatar_url") or "",
        "garmin_connected": bool(final_p.get("garmin_connected")),
        "garmin_email": final_p.get("garmin_email") or "",
        "garmin_domain": final_p.get("garmin_domain") or "garmin.cn",
        "coros_connected": bool(final_p.get("coros_connected")),
        "coros_account": final_p.get("coros_account") or "",
        "coros_domain": final_p.get("coros_domain") or "teamcnapi.coros.com",
        "apple_watch_connected": False,
        "huawei_connected": False,
        "huawei_account": final_p.get("huawei_account") or "",
        "suunto_connected": True,
        "suunto_account": acc,
        "message": "颂拓 Suunto 手表已成功连接 ✓ 可点击【选运动截图导入】或【导入 FIT/GPX】同步跑步记录"
    }


@router.post("/suunto/unbind")
def unbind_suunto_watch(request: WatchStatusBindRequest):
    """Unbinds Suunto Watch from the user's profile (preserving imported activities)."""
    from utils.local_store import LocalStore

    if not request.uid or not request.uid.strip():
        raise HTTPException(status_code=400, detail="缺少用户标识")

    LocalStore.upsert_profile(request.uid, {
        "suunto_connected": 0,
    })
    return {
        "success": True,
        "connected": False,
        "removed_activities": 0,
        "message": "颂拓 Suunto 手表已解除连接"
    }


# ── Dynamic WeChat Mini-Program QR Scan Login for Web (wxacode.getUnlimited) ──

class WebQrScanRequest(BaseModel):
    scene_id: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


class WebQrConfirmRequest(BaseModel):
    scene_id: str
    code: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


@router.post("/wechat/web-qr/create")
def create_wechat_web_qr_login():
    """
    Creates a 5-minute dynamic WeChat Mini-Program QR login session for Web.
    Generates an official `wxacode.getUnlimited` code pointing to `pages/share/share?scene=wlogin_<hex>`.
    """
    import base64
    import secrets
    from utils.local_store import LocalStore

    scene_id = f"wlogin_{secrets.token_hex(8)}"  # 23 chars (<= 32 WeChat scene limit)
    sess = LocalStore.create_web_qr_session(scene_id, ttl_seconds=300)

    raw_state = (getattr(settings, "WECHAT_MINIPROGRAM_STATE", "formal") or "formal").lower()
    env_map = {"formal": "release", "release": "release", "trial": "trial", "developer": "develop", "develop": "develop"}
    env_version = env_map.get(raw_state, "release")

    img_bytes = wechat_client.get_wxacode_unlimit(
        scene=scene_id,
        page="pages/share/share",
        width=320,
        env_version=env_version,
    )
    b64_str = None
    if img_bytes:
        mime = "image/png" if img_bytes[:4] == b"\x89PNG" else "image/jpeg"
        b64_str = f"data:{mime};base64,{base64.b64encode(img_bytes).decode('ascii')}"

    return {
        "scene_id": scene_id,
        "qrcode_base64": b64_str,
        "has_official_wxacode": bool(b64_str),
        "miniapp_path": f"/pages/share/share?scene={scene_id}",
        "expires_in": sess["expires_in"],
        "expires_at": sess["expires_at"],
    }


@router.post("/wechat/web-qr/scan")
def mark_wechat_web_qr_scanned(request: WebQrScanRequest):
    """Marks a Web QR login session as scanned when the user opens the Mini-Program code on phone."""
    from utils.local_store import LocalStore

    scene_id = (request.scene_id or "").strip()
    if not scene_id.startswith("wlogin_"):
        raise HTTPException(status_code=400, detail="无效的扫码登录标识")

    ok = LocalStore.mark_web_qr_scanned(
        scene_id,
        display_name=(request.display_name or "").strip(),
        avatar_url=(request.avatar_url or "").strip(),
    )
    if not ok:
        raise HTTPException(status_code=400, detail="二维码已过期或已使用，请在电脑网页端刷新二维码")
    return {"success": True, "status": "scanned", "scene_id": scene_id}


@router.post("/wechat/web-qr/confirm")
def confirm_wechat_web_qr_login(
    request: WebQrConfirmRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Confirms Web QR login from inside the WeChat Mini-Program.
    Strictly authenticates the caller via Mini-Program Bearer JWT or fresh WeChat `code` (jscode2session).
    """
    import jwt
    from datetime import datetime
    from utils.local_store import LocalStore

    scene_id = (request.scene_id or "").strip()
    if not scene_id.startswith("wlogin_"):
        raise HTTPException(status_code=400, detail="无效的扫码登录标识")

    caller_uid: Optional[str] = None

    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            caller_uid = payload.get("uid") or payload.get("sub")
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="小程序登录态已失效，请重新授权后再确认")

    if not caller_uid and request.code:
        res = wechat_client.code_to_session(request.code)
        if res and res.get("openid"):
            openid = res["openid"]
            unionid = (res.get("unionid") or "").strip() or None
            prof_wx = LocalStore.get_profile_by_unionid(unionid) if unionid else None
            if not prof_wx:
                prof_wx = LocalStore.get_profile_by_openid(openid)
            if prof_wx:
                caller_uid = prof_wx["id"]
            else:
                caller_uid = f"u_wx_{hashlib.md5(openid.encode('utf-8')).hexdigest()[:10]}"
                LocalStore.upsert_profile(caller_uid, {
                    "id": caller_uid,
                    "wechat_openid": openid,
                    "wechat_unionid": unionid,
                    "display_name": (request.display_name or "").strip() or f"跑者_{caller_uid[-4:]}",
                    "avatar_url": (request.avatar_url or "").strip(),
                    "garmin_connected": 0,
                    "created_at": datetime.utcnow().isoformat() + "Z",
                })
            LocalStore.bind_user_identity(caller_uid, "wechat_openid", openid)
            if unionid:
                LocalStore.bind_user_identity(caller_uid, "wechat_unionid", unionid)

    if not caller_uid:
        raise HTTPException(status_code=401, detail="安全拦截：请先在微信小程序内完成微信授权登录")

    canonical_uid = LocalStore.resolve_user_id(caller_uid)
    prof = LocalStore.get_profile(canonical_uid)
    if not prof:
        raise HTTPException(status_code=404, detail="未找到对应的跑者档案，请重新进入小程序后再试")

    disp_name = prof.get("display_name") or (request.display_name or "").strip() or "微信跑者"
    avatar = prof.get("avatar_url") or (request.avatar_url or "").strip()
    ok = LocalStore.confirm_web_qr_session(scene_id, canonical_uid, display_name=disp_name, avatar_url=avatar)
    if not ok:
        raise HTTPException(status_code=400, detail="二维码已过期或已被使用，请在网页端点击刷新二维码")

    return {
        "success": True,
        "status": "confirmed",
        "uid": canonical_uid,
        "display_name": disp_name,
    }


@router.get("/wechat/web-qr/status/{scene_id}")
def poll_wechat_web_qr_status(scene_id: str):
    """
    Polls a Web QR login session. When confirmed, atomically consumes the session once
    and issues a 30-day JWT session identical to Web email/watch login.
    """
    import time
    import jwt
    from utils.local_store import LocalStore

    clean_scene = (scene_id or "").strip()
    sess = LocalStore.get_web_qr_session(clean_scene)
    if not sess:
        return {"status": "expired", "message": "二维码不存在或已过期"}

    if sess["status"] == "confirmed":
        consumed = LocalStore.consume_web_qr_session(clean_scene)
        if not consumed:
            return {"status": "consumed"}
        uid = LocalStore.resolve_user_id(consumed["user_id"])
        prof = LocalStore.get_profile(uid) or {}
        email_val = prof.get("email") or prof.get("garmin_email") or prof.get("coros_account") or ""
        payload = {
            "sub": uid,
            "uid": uid,
            "email": email_val,
            "aud": "authenticated",
            "exp": int(time.time()) + 86400 * 30,
            "iat": int(time.time()),
        }
        token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
        disp_name = prof.get("display_name") or consumed.get("display_name") or "微信跑者"
        avatar_val = prof.get("avatar_url") or consumed.get("avatar_url") or ""
        garmin_conn = bool(prof.get("garmin_connected"))
        coros_conn = bool(prof.get("coros_connected"))
        return {
            "status": "confirmed",
            "token": token,
            "uid": uid,
            "user": {
                "id": uid,
                "email": email_val,
                "display_name": disp_name,
                "avatar_url": avatar_val,
                "garmin_connected": garmin_conn or coros_conn,
                "coros_connected": coros_conn,
                "apple_watch_connected": bool(prof.get("apple_watch_connected")),
                "huawei_connected": bool(prof.get("huawei_connected")),
                "suunto_connected": bool(prof.get("suunto_connected")),
                "is_coach_or_owner": LocalStore.is_user_coach_or_owner(uid),
                "is_admin": LocalStore.is_super_admin(uid),
            },
        }

    return {
        "status": sess["status"],
        "display_name": sess.get("display_name") or "",
        "avatar_url": sess.get("avatar_url") or "",
    }

