import os
import hmac
import time
import jwt
import logging
import hashlib
from fastapi import APIRouter, HTTPException, Header, Depends, UploadFile, File
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from config import settings
from utils.local_store import LocalStore
from utils.security import validate_uploaded_image_bytes

logger = logging.getLogger("router_admin")
router = APIRouter()

# Super Admin Credentials
ADMIN_EMAIL = os.getenv("RGM_ADMIN_EMAIL", "admin@rgm.com").strip().lower()
ADMIN_PASSWORD = os.getenv("RGM_ADMIN_PASSWORD", "rgm_admin_2026").strip()

class AdminLoginRequest(BaseModel):
    email: str
    password: str

class CreateClubAdminRequest(BaseModel):
    name: str
    description: Optional[str] = None
    city: Optional[str] = "上海"
    logo_url: Optional[str] = None
    owner_id: str
    org_id: Optional[str] = None
    join_mode: Optional[str] = "free"

class UpdateClubAdminRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None
    logo_url: Optional[str] = None
    invite_code: Optional[str] = None
    org_id: Optional[str] = None
    join_mode: Optional[str] = None
    status: Optional[str] = None

class SetClubStatusRequest(BaseModel):
    status: str # 'active', 'paused', 'locked'

class AssignOwnerRequest(BaseModel):
    new_owner_id: str

def verify_super_admin(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Middleware dependency ensuring request is signed with a valid Super Admin JWT.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供超级管理员认证令牌")

    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
        if not payload.get("is_super_admin"):
            raise HTTPException(status_code=403, detail="权限不足：需要平台超级管理员身份")
        return payload
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"无效或过期的管理员会话: {str(e)}")


@router.post("/login")
def admin_login(req: AdminLoginRequest):
    """
    Super Admin login endpoint.
    Strictly for platform super administrators to manage clubs and designate owners.
    """
    if settings.ENVIRONMENT.lower() == "production" and ADMIN_PASSWORD in ("", "rgm_admin_2026"):
        raise HTTPException(status_code=503, detail="生产环境尚未配置安全的 RGM_ADMIN_PASSWORD，已拒绝默认密码登录")

    clean_email = req.email.strip().lower()
    clean_pw = req.password.strip()

    email_ok = hmac.compare_digest(clean_email.encode("utf-8"), ADMIN_EMAIL.encode("utf-8"))
    pw_ok = hmac.compare_digest(clean_pw.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))
    if not (email_ok and pw_ok):
        raise HTTPException(status_code=401, detail="超级管理员账号或密码错误")

    payload = {
        "sub": "rgm_super_admin",
        "email": ADMIN_EMAIL,
        "role": "super_admin",
        "is_super_admin": True,
        "aud": "authenticated",
        "exp": int(time.time()) + 86400 * 7,  # 7 days
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

    return {
        "token": token,
        "admin": {
            "email": ADMIN_EMAIL,
            "role": "super_admin",
            "name": "平台超级管理员"
        },
        "message": "超级管理员验证成功"
    }


@router.get("/verify")
def verify_admin(admin_info: Dict[str, Any] = Depends(verify_super_admin)):
    """Verifies that current token holds super admin privilege."""
    return {"valid": True, "admin": admin_info}


@router.get("/clubs")
def get_all_clubs(admin_info: Dict[str, Any] = Depends(verify_super_admin)):
    """Returns all running clubs in the platform with owner details and member stats."""
    clubs = LocalStore.list_all_clubs()
    return {"clubs": clubs}


@router.post("/clubs")
def create_club_as_admin(req: CreateClubAdminRequest, admin_info: Dict[str, Any] = Depends(verify_super_admin)):
    """Super Admin creates a new running club and designates its initial owner."""
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="跑团名称不能为空")
    if not req.owner_id.strip():
        raise HTTPException(status_code=400, detail="必须指定跑团团长")

    owner = LocalStore.get_profile(req.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="指定的团长跑者不存在")

    club = LocalStore.create_club(
        owner_id=req.owner_id,
        name=req.name.strip(),
        description=req.description,
        city=req.city or "上海",
        logo_url=req.logo_url,
        org_id=req.org_id,
        join_mode=req.join_mode or "free"
    )
    return {"message": f"跑团【{req.name}】创建成功，团长已指定为【{owner.get('display_name')}】！", "club": club}


@router.put("/clubs/{club_id}")
def update_club_as_admin(club_id: str, req: UpdateClubAdminRequest, admin_info: Dict[str, Any] = Depends(verify_super_admin)):
    """Super Admin edits club profile (name, description, city, logo, invite_code)."""
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")

    update_dict = req.dict(exclude_unset=True)
    updated = LocalStore.update_club(club_id, update_dict)
    return {"message": "跑团信息更新成功", "club": updated}


@router.post("/clubs/{club_id}/assign-owner")
def assign_club_owner(club_id: str, req: AssignOwnerRequest, admin_info: Dict[str, Any] = Depends(verify_super_admin)):
    """
    Super Admin designates / reassigns the Club Owner (团长).
    Demotes prior owner to coach and grants new owner full management rights.
    """
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")

    new_owner = LocalStore.get_profile(req.new_owner_id)
    if not new_owner:
        raise HTTPException(status_code=404, detail="指定的跑者档案不存在")

    updated = LocalStore.set_club_owner(club_id, req.new_owner_id)
    owner_name = new_owner.get("display_name") or req.new_owner_id
    return {
        "message": f"成功将跑团【{club['name']}】的团长指定为【{owner_name}】！",
        "club": updated,
        "new_owner": {
            "id": req.new_owner_id,
            "display_name": owner_name
        }
    }


@router.post("/clubs/{club_id}/status")
def set_club_status_as_admin(club_id: str, req: SetClubStatusRequest, admin_info: Dict[str, Any] = Depends(verify_super_admin)):
    """Super Admin sets club status (active, paused, locked)."""
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")
    try:
        updated = LocalStore.set_club_status(club_id, req.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    status_names = {"active": "正常运行", "paused": "暂停运行", "locked": "锁定归档"}
    status_text = status_names.get(req.status, req.status)
    return {"message": f"跑团【{club['name']}】状态已更新为【{status_text}】", "club": updated}


@router.delete("/clubs/{club_id}")
def delete_club_as_admin(club_id: str, admin_info: Dict[str, Any] = Depends(verify_super_admin)):
    """
    Super Admin permanently dissolves / deletes a club.
    Deletes club memberships, events, and club records, but guarantees
    members' personal accounts, profiles, and workout history are completely preserved.
    """
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")

    success = LocalStore.delete_club(club_id)
    if not success:
        raise HTTPException(status_code=500, detail="删除跑团失败")

    return {
        "success": True,
        "message": f"跑团【{club['name']}】及相关数据已成功删除，队员个人历史运动数据已完整保留"
    }



@router.get("/users")
def get_users_for_admin(admin_info: Dict[str, Any] = Depends(verify_super_admin)):
    """Returns all registered users in the platform for designating club owners."""
    users = LocalStore.list_all_users_for_admin()
    return {"users": users}


@router.get("/unaffiliated-users")
def get_unaffiliated_users_for_admin(admin_info: Dict[str, Any] = Depends(verify_super_admin)):
    """Returns all users who have not joined any running club, with their watch binding and goal setting status."""
    return LocalStore.get_unaffiliated_users_status(viewer_uid="super_admin")


@router.post("/unaffiliated-users/{target_uid}/remind")
def remind_unaffiliated_user_as_admin(target_uid: str, admin_info: Dict[str, Any] = Depends(verify_super_admin)):
    """Super Admin sends a 1-tap setup reminder notification to an unaffiliated user."""
    try:
        return LocalStore.remind_unaffiliated_user_setup("super_admin", target_uid)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload-club-logo")
async def upload_club_logo(
    file: UploadFile = File(...),
    admin_info: Dict[str, Any] = Depends(verify_super_admin),
):
    """
    Uploads a club logo image from local disk, saves it to persistent static storage,
    and returns the public URL. Requires Super Admin authentication.
    """
    orig_name = file.filename or "club_logo.jpg"
    contents = await file.read()
    ext = validate_uploaded_image_bytes(contents, orig_name)

    avatars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "avatars")
    os.makedirs(avatars_dir, exist_ok=True)

    random_suffix = hashlib.md5(f"{time.time()}_{orig_name}".encode()).hexdigest()[:8]
    filename = f"club_logo_{int(time.time())}_{random_suffix}{ext}"
    filepath = os.path.join(avatars_dir, filename)

    try:
        with open(filepath, "wb") as f:
            f.write(contents)
    except Exception as e:
        logger.error(f"[admin] Failed to save club logo: {e}")
        raise HTTPException(status_code=500, detail="保存跑团Logo图片失败")

    logo_url = f"https://rgm.vanpower.net/api/avatars/{filename}"
    return {
        "success": True,
        "logo_url": logo_url,
        "url": logo_url,
        "message": "跑团 Logo 上传成功！"
    }


class AdminReplyTicketRequest(BaseModel):
    admin_reply: str
    status: Optional[str] = "resolved"


@router.get("/support-tickets")
def get_support_tickets_for_admin(
    status: Optional[str] = None,
    admin_info: Dict[str, Any] = Depends(verify_super_admin)
):
    """Returns user technical support tickets with diagnostic context for Super Admin."""
    tickets = LocalStore.list_all_support_tickets(status_filter=status)
    open_count = sum(1 for t in tickets if t.get("status") == "open")
    return {
        "tickets": tickets,
        "open_count": open_count,
        "total": len(tickets),
    }


@router.post("/support-tickets/{ticket_id}/reply")
def reply_support_ticket_as_admin(
    ticket_id: str,
    req: AdminReplyTicketRequest,
    admin_info: Dict[str, Any] = Depends(verify_super_admin)
):
    """Super Admin replies to a user support ticket and updates its status."""
    updated = LocalStore.reply_support_ticket(
        ticket_id=ticket_id,
        admin_reply=req.admin_reply or "",
        status=req.status or "resolved",
    )
    if not updated:
        raise HTTPException(status_code=404, detail="工单不存在")
    return {
        "success": True,
        "ticket": updated,
        "message": "工单回复及状态已保存！用户可在小程序【我的 → 帮助与技术支持】中查看。",
    }


@router.get("/analytics/overview")
def get_admin_analytics_overview(
    days: int = 14,
    include_wechat: bool = True,
    admin_info: Dict[str, Any] = Depends(verify_super_admin),
) -> Dict[str, Any]:
    """
    Returns unified UX & product analytics for Super Admin:
    1. Per-user real-time session, page stay, scroll depth, button click & navigation flow stats
    2. Real-user conversion funnel across business tables (excluding synthetic test profiles)
    3. Official WeChat Mini Program historical analytics (We分析 DataCube API)
    """
    from utils.wechat import wechat_client

    eff_days = max(1, min(30, int(days or 14)))
    behavior = LocalStore.get_behavior_analytics_overview(days=eff_days)
    conversion_funnel = LocalStore.get_conversion_funnel_analytics()
    wechat_datacube = None
    if include_wechat:
        try:
            wechat_datacube = wechat_client.get_datacube_overview(days=eff_days)
        except Exception as e:
            logger.warning(f"[admin] WeChat datacube fetch warning: {e}")
            wechat_datacube = {"available": False, "reason": str(e)}

    return {
        "success": True,
        "days": eff_days,
        "behavior": behavior,
        "conversion_funnel": conversion_funnel,
        "wechat_datacube": wechat_datacube,
    }


@router.get("/analytics/sessions/{session_id}")
def get_admin_session_timeline(
    session_id: str,
    admin_info: Dict[str, Any] = Depends(verify_super_admin),
) -> Dict[str, Any]:
    """
    Returns step-by-step chronological replay timeline for a single user session.
    """
    timeline = LocalStore.get_session_timeline(session_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="未找到该访问会话记录")
    return {"success": True, **timeline}


@router.get("/analytics/users/{user_id}/journey")
def get_admin_user_journey(
    user_id: str,
    limit: int = 20,
    admin_info: Dict[str, Any] = Depends(verify_super_admin),
) -> Dict[str, Any]:
    """
    Returns all recent MiniApp sessions and timelines for a specific runner.
    """
    journey = LocalStore.get_user_journey(user_id=user_id, limit_sessions=limit)
    return {"success": True, **journey}

