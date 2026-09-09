import os
import time
import jwt
import logging
import hashlib
from fastapi import APIRouter, HTTPException, Header, Depends, UploadFile, File
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from config import settings
from utils.local_store import LocalStore

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
    clean_email = req.email.strip().lower()
    clean_pw = req.password.strip()

    if clean_email != ADMIN_EMAIL or clean_pw != ADMIN_PASSWORD:
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


@router.get("/users")
def get_users_for_admin(admin_info: Dict[str, Any] = Depends(verify_super_admin)):
    """Returns all registered users in the platform for designating club owners."""
    users = LocalStore.list_all_users_for_admin()
    return {"users": users}


@router.post("/upload-club-logo")
async def upload_club_logo(file: UploadFile = File(...)):
    """
    Uploads a club logo image from local disk, saves it to persistent static storage,
    and returns the public URL.
    """
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}
    orig_name = file.filename or "club_logo.jpg"
    ext = os.path.splitext(orig_name)[1].lower()
    if not ext or ext not in allowed_exts:
        ext = ".jpg"

    avatars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "avatars")
    os.makedirs(avatars_dir, exist_ok=True)

    random_suffix = hashlib.md5(f"{time.time()}_{orig_name}".encode()).hexdigest()[:8]
    filename = f"club_logo_{int(time.time())}_{random_suffix}{ext}"
    filepath = os.path.join(avatars_dir, filename)

    try:
        contents = await file.read()
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

