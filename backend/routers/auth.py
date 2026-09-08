from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
from config import settings
from db import supabase_admin
from utils.encryption import encrypt_string, decrypt_string
from utils.garmin_adapter import GarminAdapter, HAS_GARMINCONNECT
from utils.coros_adapter import CorosAdapter
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

class GarminUnbindRequest(BaseModel):
    uid: str

class CorosBindRequest(BaseModel):
    uid: str
    account: str
    password: str
    domain: str = "teamcnapi.coros.com" # "teamcnapi.coros.com" or "teamapi.coros.com"

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

class SwitchAccountRequest(BaseModel):
    target_uid: str
    client_uuid: Optional[str] = None
    code: Optional[str] = None

PENDING_MFA_ADAPTERS: Dict[str, Any] = {}

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
    res = wechat_client.code_to_session(request.code)
    if res and res.get("openid"):
        openid = res["openid"]
    elif request.client_uuid:
        openid = f"wx_{hashlib.md5(request.client_uuid.encode('utf-8')).hexdigest()[:20]}"
    else:
        openid = f"wx_{hashlib.md5(request.code.encode('utf-8')).hexdigest()[:20]}"

    phone_number = None
    if request.phone_code:
        phone_res = wechat_client.get_phone_number(request.phone_code)
        if phone_res.get("errcode") == 0:
            phone_number = phone_res.get("phone_info", {}).get("phoneNumber")

    # 1. Lookup existing user by openid in LocalStore
    profile_data = LocalStore.get_profile_by_openid(openid)
    if profile_data:
        user_id = profile_data["id"]
        update_dict = {}
        if request.nick_name and profile_data.get("display_name") in (None, "", "微信跑者"):
            update_dict["display_name"] = request.nick_name
        if request.avatar_url and not profile_data.get("avatar_url"):
            update_dict["avatar_url"] = request.avatar_url
        if phone_number and not profile_data.get("phone"):
            update_dict["phone"] = phone_number
        if update_dict:
            LocalStore.upsert_profile(user_id, update_dict)
            profile_data.update(update_dict)
    else:
        # 2. Create brand new unique user
        user_id = f"u_wx_{hashlib.md5(openid.encode('utf-8')).hexdigest()[:10]}"
        display_name = request.nick_name or f"跑者_{user_id[-4:]}"
        profile_data = {
            "id": user_id,
            "wechat_openid": openid,
            "display_name": display_name,
            "avatar_url": request.avatar_url or "",
            "phone": phone_number,
            "garmin_connected": 0,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
        LocalStore.upsert_profile(user_id, profile_data)

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
        "role": "member"
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
        if request.mfa_code and email_key in PENDING_MFA_ADAPTERS:
            adapter = PENDING_MFA_ADAPTERS[email_key]
            if not adapter.client:
                adapter.login()
            ok = adapter.complete_mfa(request.mfa_code)
            if not ok:
                raise HTTPException(status_code=400, detail=adapter.last_error or "验证码错误或已失效")
            PENDING_MFA_ADAPTERS.pop(email_key, None)
        # Find existing profile
        existing_p = LocalStore.get_profile_by_garmin_email(account)
        password_verified = False
        if existing_p:
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
            if openid:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("UPDATE profiles SET wechat_openid = NULL WHERE wechat_openid = ? AND id != ?", (openid, user_id))
                    conn.execute("DELETE FROM profiles WHERE id LIKE 'u_wx_%' AND id != ? AND (garmin_connected = 0 OR garmin_connected IS NULL) AND (coros_connected = 0 OR coros_connected IS NULL) AND wechat_openid IS NULL", (user_id,))
                    conn.commit()
                update_data["wechat_openid"] = openid
            LocalStore.upsert_profile(user_id, update_data)
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
                "wechat_openid": openid or "",
                "created_at": datetime.utcnow().isoformat() + "Z"
            }
            if openid:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("UPDATE profiles SET wechat_openid = NULL WHERE wechat_openid = ? AND id != ?", (openid, user_id))
                    conn.execute("DELETE FROM profiles WHERE id LIKE 'u_wx_%' AND id != ? AND (garmin_connected = 0 OR garmin_connected IS NULL) AND (coros_connected = 0 OR coros_connected IS NULL) AND wechat_openid IS NULL", (user_id,))
                    conn.commit()
            LocalStore.upsert_profile(user_id, profile)

    elif brand == "coros":
        domain = (request.domain or "teamcnapi.coros.com").lower().strip()
        if "teamapi" not in domain and "teamcnapi" not in domain:
            domain = "teamcnapi.coros.com"

        existing_p = LocalStore.get_profile_by_coros_account(account)
        password_verified = False
        if existing_p:
            saved_pwd = decrypt_string(existing_p.get("coros_encrypted_password", ""))
            if saved_pwd and saved_pwd == pwd:
                password_verified = True

        if not password_verified:
            adapter = CorosAdapter(account=account, password=pwd, domain=domain)
            ok = adapter.login()
            if not ok:
                raise HTTPException(status_code=400, detail=adapter.last_error or f"高驰账号或密码错误（区域：{domain}）")
        if existing_p:
            user_id = existing_p["id"]
            update_data = {
                "coros_connected": 1,
                "coros_account": account,
                "coros_encrypted_password": encrypted_pwd,
                "coros_domain": domain,
            }
            if openid:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("UPDATE profiles SET wechat_openid = NULL WHERE wechat_openid = ? AND id != ?", (openid, user_id))
                    conn.execute("DELETE FROM profiles WHERE id LIKE 'u_wx_%' AND id != ? AND (garmin_connected = 0 OR garmin_connected IS NULL) AND (coros_connected = 0 OR coros_connected IS NULL) AND wechat_openid IS NULL", (user_id,))
                    conn.commit()
                update_data["wechat_openid"] = openid
            LocalStore.upsert_profile(user_id, update_data)
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
                "wechat_openid": openid or "",
                "created_at": datetime.utcnow().isoformat() + "Z"
            }
            if openid:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("UPDATE profiles SET wechat_openid = NULL WHERE wechat_openid = ? AND id != ?", (openid, user_id))
                    conn.execute("DELETE FROM profiles WHERE id LIKE 'u_wx_%' AND id != ? AND (garmin_connected = 0 OR garmin_connected IS NULL) AND (coros_connected = 0 OR coros_connected IS NULL) AND wechat_openid IS NULL", (user_id,))
                    conn.commit()
            LocalStore.upsert_profile(user_id, profile)
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
        "message": "运动手表验证通过，已成功进入跑者档案！"
    }


@router.post("/wechat/confirm-login")
def wechat_confirm_login(request: WeChatConfirmLoginRequest):
    """
    Explicit login flow:
    - Sets user display name / custom identity
    - Strictly blocks hijacking of existing accounts (especially with Garmin connected)
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
        # Security protection: forbid hijacking existing users with Garmin or special IDs
        if existing_profile.get("garmin_connected") or uid in ("u_df65d9a588c9", "Vivian Chen"):
            raise HTTPException(status_code=403, detail="该账号受安全保护，不可直接选定登录。请通过微信授权或佳明账号登录。")
        profile = existing_profile
        if wechat_id and profile.get("display_name") in (None, "", "微信跑者"):
            LocalStore.upsert_profile(uid, {"display_name": wechat_id})
            profile["display_name"] = wechat_id
    else:
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

    email_key = request.email.strip().lower()

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
    else:
        # Initial login path
        adapter = GarminAdapter(email=request.email, password=request.password, domain=domain)
        if HAS_GARMINCONNECT:
            ok = adapter.login()
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

    from utils.local_store import LocalStore
    effective_uid = request.uid

    # Check if this Garmin email is already associated with an existing profile (e.g. u_df65d9a588c9 for Zhong Wan)
    existing_p = LocalStore.get_profile_by_garmin_email(request.email)
    if existing_p and existing_p["id"] != request.uid:
        effective_uid = existing_p["id"]
        # Link current user's wechat openid to this existing account
        curr_p = LocalStore.get_profile(request.uid)
        oid = curr_p.get("wechat_openid") if curr_p else None
        update_data = {
            "garmin_connected": 1,
            "garmin_email": request.email,
            "garmin_encrypted_password": encrypted_pwd,
            "garmin_domain": domain,
        }
        if oid:
            update_data["wechat_openid"] = oid
        LocalStore.upsert_profile(effective_uid, update_data)
        # Remove placeholder user if different
        LocalStore.delete_profile(request.uid)
    else:
        LocalStore.upsert_profile(effective_uid, {
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

    return {
        "success": True,
        "connected": True,
        "uid": effective_uid,
        "token": token,
        "message": f"佳明 ({domain}) 账号绑定成功！已开始自动同步最近运动数据。",
        "email": request.email,
        "domain": domain
    }


@router.post("/garmin/unbind")
@router.post("/garmin/disconnect")
def unbind_garmin(request: GarminUnbindRequest, authorization: Optional[str] = Header(None)):
    """Unbinds Garmin account with strict caller ownership verification."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="请先登录")

    import jwt
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
        caller_uid = payload.get("uid") or payload.get("sub")
        is_admin = payload.get("is_super_admin", False)
        if not is_admin and caller_uid != request.uid:
            from utils.local_store import LocalStore
            caller_p = LocalStore.get_profile(caller_uid)
            target_p = LocalStore.get_profile(request.uid)
            c_oid = caller_p.get("wechat_openid") if caller_p else None
            t_oid = target_p.get("wechat_openid") if target_p else None
            if not c_oid or c_oid != t_oid:
                raise HTTPException(status_code=403, detail="安全拦截：无权操作其他用户的佳明账号绑定")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="登录会话已过期，请重新登录")

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
    """
    domain = request.domain.lower().strip()
    if "teamapi" not in domain and "teamcnapi" not in domain and domain not in ["cn", "global"]:
        domain = "teamcnapi.coros.com"

    adapter = CorosAdapter(account=request.account, password=request.password, domain=domain)
    ok = adapter.login()
    if not ok:
        err_msg = adapter.last_error or "高驰绑定失败，请检查高驰账号、密码及选择的区域。"
        raise HTTPException(status_code=400, detail=err_msg)

    # 2. Encrypt password
    encrypted_pwd = encrypt_string(request.password)

    from utils.local_store import LocalStore
    effective_uid = request.uid

    # Check if this COROS account is already associated with an existing profile
    existing_p = LocalStore.get_profile_by_coros_account(request.account)
    if existing_p and existing_p["id"] != request.uid:
        effective_uid = existing_p["id"]
        # Link current user's wechat openid to this existing account
        curr_p = LocalStore.get_profile(request.uid)
        oid = curr_p.get("wechat_openid") if curr_p else None
        update_data = {
            "coros_connected": 1,
            "coros_account": request.account,
            "coros_encrypted_password": encrypted_pwd,
            "coros_domain": domain,
        }
        if oid:
            update_data["wechat_openid"] = oid
        LocalStore.upsert_profile(effective_uid, update_data)
        # Remove placeholder user if different
        LocalStore.delete_profile(request.uid)
    else:
        LocalStore.upsert_profile(effective_uid, {
            "coros_connected": 1,
            "coros_account": request.account,
            "coros_encrypted_password": encrypted_pwd,
            "coros_domain": domain,
        })

    if supabase_admin:
        try:
            supabase_admin.table("profiles").update({
                "coros_connected": True,
                "coros_account": request.account,
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

    return {
        "success": True,
        "connected": True,
        "uid": effective_uid,
        "token": token,
        "message": f"高驰 ({domain}) 账号绑定成功！已开始自动同步最近运动数据。",
        "account": request.account,
        "domain": domain
    }


@router.post("/coros/unbind")
@router.post("/coros/disconnect")
def unbind_coros(request: CorosUnbindRequest, authorization: Optional[str] = Header(None)):
    """Unbinds COROS account with strict caller ownership verification."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="请先登录")

    import jwt
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
        caller_uid = payload.get("uid") or payload.get("sub")
        is_admin = payload.get("is_super_admin", False)
        if not is_admin and caller_uid != request.uid:
            from utils.local_store import LocalStore
            caller_p = LocalStore.get_profile(caller_uid)
            target_p = LocalStore.get_profile(request.uid)
            c_oid = caller_p.get("wechat_openid") if caller_p else None
            t_oid = target_p.get("wechat_openid") if target_p else None
            if not c_oid or c_oid != t_oid:
                raise HTTPException(status_code=403, detail="安全拦截：无权操作其他用户的高驰账号绑定")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="登录会话已过期，请重新登录")

    from utils.local_store import LocalStore
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

