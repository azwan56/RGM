from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from utils.local_store import LocalStore

logger = logging.getLogger("router_org")
router = APIRouter()

class VerifyOrgCodeRequest(BaseModel):
    invite_code: str

class JoinOrganizationRequest(BaseModel):
    user_id: str
    invite_code: str
    real_name: str
    gender: str          # 'male' / 'female'
    date_of_birth: str   # 'YYYY-MM-DD'
    class_name: str      # 'EMBA 23春' / 'MBA 21级'
    phone: Optional[str] = None

class ConfirmMemberRequest(BaseModel):
    operator_uid: Optional[str] = None

class AssignSubClubRequest(BaseModel):
    user_id: str
    club_id: str

class CreateOrgRequest(BaseModel):
    name: str
    invite_code: str
    description: Optional[str] = None
    city: Optional[str] = "上海"
    logo_url: Optional[str] = None
    owner_id: Optional[str] = None

class UpdateOrgRequest(BaseModel):
    name: Optional[str] = None
    invite_code: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None
    logo_url: Optional[str] = None
    owner_id: Optional[str] = None

class BindClubRequest(BaseModel):
    club_id: str
    action: str = "bind"  # "bind" or "unbind"



@router.post("/verify-code")
def verify_org_code(req: VerifyOrgCodeRequest):
    """
    Validates organization invite code and returns basic org info.
    """
    code = (req.invite_code or "").strip().upper()
    org = LocalStore.get_organization_by_code(code)
    if not org:
        raise HTTPException(status_code=404, detail="无效的大群体邀请码，请向组织管理员核对后重新输入！")
    return {
        "valid": True,
        "organization": org
    }


@router.post("/join")
def join_organization_endpoint(req: JoinOrganizationRequest):
    """
    Joins a grand community (e.g. 复旦戈) using invite code and mandatory personal details:
    real_name, gender, date_of_birth, class_name.
    """
    if not req.user_id.strip():
        raise HTTPException(status_code=400, detail="缺少跑者用户ID")
    if not req.invite_code.strip():
        raise HTTPException(status_code=400, detail="组织邀请码不能为空")
    if not req.real_name.strip():
        raise HTTPException(status_code=400, detail="请填写真实姓名以便管理员核对确认")
    if req.gender not in ("male", "female"):
        raise HTTPException(status_code=400, detail="请选择性别")
    if not req.date_of_birth.strip() or len(req.date_of_birth.strip()) < 8:
        raise HTTPException(status_code=400, detail="请选择正确的出生日期")
    if not req.class_name.strip():
        raise HTTPException(status_code=400, detail="请填写所在班级或届别（例如 EMBA 23春、MBA 21级）")

    try:
        res = LocalStore.join_organization(
            user_id=req.user_id,
            invite_code=req.invite_code,
            real_name=req.real_name,
            gender=req.gender,
            date_of_birth=req.date_of_birth,
            class_name=req.class_name,
            phone=req.phone
        )
        return {
            "success": True,
            "message": f"恭喜您成功加入【{res['org_name']}】大群体！",
            "membership": res
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[join_organization] failed: {e}")
        raise HTTPException(status_code=500, detail="加入大组织失败，请重试")


@router.get("/my-orgs/{uid}")
def get_user_organizations_endpoint(uid: str):
    """
    Returns all grand communities/organizations the user has joined with verified credentials.
    """
    orgs = LocalStore.get_user_organizations(uid)
    return {"organizations": orgs}


@router.get("/{org_id}")
def get_organization_endpoint(org_id: str):
    """
    Returns detail of a specific grand community.
    """
    org = LocalStore.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    return {"organization": org}


@router.get("/{org_id}/sub-clubs")
def get_org_sub_clubs_endpoint(org_id: str, user_id: Optional[str] = None):
    """
    Returns all sub-running clubs under this organization, with 'is_member' flag for the user.
    """
    sub_clubs = LocalStore.get_org_sub_clubs(org_id, user_id)
    return {"sub_clubs": sub_clubs}


@router.get("/{org_id}/members")
def get_org_members_endpoint(org_id: str, search: Optional[str] = None, class_filter: Optional[str] = None):
    """
    Returns verified member directory for the grand community (name, class, birthdate, status, sub-clubs).
    """
    members = LocalStore.get_org_members(org_id, search, class_filter)
    return {"members": members}


@router.post("/{org_id}/members/{target_uid}/confirm")
def confirm_member_endpoint(org_id: str, target_uid: str, req: Optional[ConfirmMemberRequest] = None):
    """
    Allows Admin or Owner to confirm and audit a member's credential.
    """
    op = req.operator_uid if req else None
    ok = LocalStore.confirm_org_member(org_id, target_uid, op)
    if not ok:
        raise HTTPException(status_code=404, detail="未找到对应的成员记录")
    return {"success": True, "message": "成员资料核对确认完成！"}


@router.post("/{org_id}/assign-sub-club")
def assign_sub_club_endpoint(org_id: str, req: AssignSubClubRequest):
    """
    Directly assigns / invites an organization member into a sub-running club.
    """
    club = LocalStore.get_club(req.club_id)
    if not club or club.get("org_id") != org_id:
        raise HTTPException(status_code=400, detail="该跑团不属于当前大组织！")
    
    joined = LocalStore.assign_member_to_sub_club(user_id=req.user_id, club_id=req.club_id)
    return {
        "success": True,
        "message": f"成功将成员加入下属跑团【{club['name']}】！",
        "club": joined
    }


@router.get("/all/list")
def list_all_orgs_endpoint():
    """
    Returns all organizations in the platform (with member counts and sub-clubs counts).
    """
    orgs = LocalStore.list_all_organizations()
    for o in orgs:
        o.pop("invite_code", None)
    return {"organizations": orgs}


@router.get("/admin/all-list")
def list_all_orgs_admin_endpoint():
    """
    Returns all organizations in the platform with invite_code retained for admin console.
    """
    orgs = LocalStore.list_all_organizations()
    return {"organizations": orgs}


@router.put("/{org_id}")
def update_org_endpoint(org_id: str, req: UpdateOrgRequest):
    """
    Updates organization info (name, invite_code, description, city, logo_url, owner_id).
    """
    data = req.dict(exclude_unset=True)
    updated = LocalStore.update_organization(org_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="组织不存在")
    return {"success": True, "message": "大组织信息更新成功！", "organization": updated}


@router.post("/{org_id}/bind-club")
def bind_club_to_org_endpoint(org_id: str, req: BindClubRequest):
    """
    Binds or unbinds a running club to/from an organization.
    """
    club = LocalStore.get_club(req.club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")

    target_org = org_id if req.action == "bind" else None
    updated = LocalStore.update_club(req.club_id, {"org_id": target_org})
    action_text = "挂靠至此大组织" if req.action == "bind" else "解除挂靠，设为独立自由跑团"
    return {
        "success": True,
        "message": f"成功将跑团【{club['name']}】{action_text}！",
        "club": updated
    }


@router.post("/create")
def create_org_endpoint(req: CreateOrgRequest):
    """
    Creates a new grand community (e.g. 复旦戈).
    """
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="组织名称不能为空")
    if not req.invite_code.strip():
        raise HTTPException(status_code=400, detail="组织专属邀请码不能为空")

    try:
        org = LocalStore.create_organization(
            name=req.name,
            invite_code=req.invite_code,
            description=req.description,
            city=req.city or "上海",
            logo_url=req.logo_url,
            owner_id=req.owner_id
        )
        return {"success": True, "message": f"大组织【{req.name}】创建成功！", "organization": org}
    except Exception as e:
        logger.error(f"[create_organization] failed: {e}")
        raise HTTPException(status_code=400, detail=f"创建组织失败（邀请码可能已存在）: {str(e)}")

