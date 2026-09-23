from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from utils.local_store import LocalStore
from utils.encryption import mask_name, mask_id_card, mask_phone, compute_age_group

logger = logging.getLogger("router_org")
router = APIRouter()

class VerifyOrgCodeRequest(BaseModel):
    invite_code: str

class JoinOrganizationRequest(BaseModel):
    user_id: str
    invite_code: str
    real_name: Optional[str] = None
    gender: Optional[str] = "male"
    date_of_birth: Optional[str] = None
    class_name: Optional[str] = None
    program: Optional[str] = None
    class_detail: Optional[str] = None
    gobi_experience: Optional[str] = None
    phone: Optional[str] = None
    id_card: Optional[str] = None
    emergency_contact: Optional[str] = None
    clothing_size: Optional[str] = None
    shoe_size: Optional[str] = None
    marathon_pb: Optional[str] = None
    health_declaration: Optional[bool] = None
    extra_data: Optional[Dict[str, Any]] = None

class UpdateFieldRulesRequest(BaseModel):
    field_rules: List[Dict[str, Any]]
    operator_uid: Optional[str] = None

class UpdateMemberProfileRequest(BaseModel):
    user_id: str
    real_name: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    class_name: Optional[str] = None
    program: Optional[str] = None
    class_detail: Optional[str] = None
    gobi_experience: Optional[str] = None
    phone: Optional[str] = None
    id_card: Optional[str] = None
    emergency_contact: Optional[str] = None
    clothing_size: Optional[str] = None
    shoe_size: Optional[str] = None
    marathon_pb: Optional[str] = None
    health_declaration: Optional[bool] = None
    extra_data: Optional[Dict[str, Any]] = None

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


class UpdateOrgMemberRoleRequest(BaseModel):
    role: str  # 'admin' | 'member'
    operator_uid: Optional[str] = None


@router.post("/verify-code")
def verify_org_code(req: VerifyOrgCodeRequest):
    """
    Validates organization invite code and returns basic org info with field rules.
    """
    code = (req.invite_code or "").strip().upper()
    org = LocalStore.get_organization_by_code(code)
    if not org:
        raise HTTPException(status_code=404, detail="无效的大群体邀请码，请向组织管理员核对后重新输入！")
    rules = LocalStore.get_org_field_rules(org["id"])
    return {
        "valid": True,
        "organization": org,
        "field_rules": rules
    }


@router.post("/join")
def join_organization_endpoint(req: JoinOrganizationRequest):
    """
    Joins a grand community (e.g. 复旦戈) using invite code and personal details.
    Assigns temporary, pending, or confirmed status based on field rules.
    """
    if not req.user_id.strip():
        raise HTTPException(status_code=400, detail="缺少跑者用户ID")
    if not req.invite_code.strip():
        raise HTTPException(status_code=400, detail="组织邀请码不能为空")

    extra = dict(req.extra_data or {})
    if req.emergency_contact:
        extra["emergency_contact"] = req.emergency_contact.strip()
    if req.clothing_size:
        extra["clothing_size"] = req.clothing_size.strip()
    if req.shoe_size:
        extra["shoe_size"] = req.shoe_size.strip()
    if req.marathon_pb:
        extra["marathon_pb"] = req.marathon_pb.strip()
    if req.health_declaration is not None:
        extra["health_declaration"] = req.health_declaration

    try:
        res = LocalStore.join_organization(
            user_id=req.user_id,
            invite_code=req.invite_code,
            real_name=req.real_name,
            gender=req.gender or "male",
            date_of_birth=req.date_of_birth,
            class_name=req.class_name,
            phone=req.phone,
            id_card=req.id_card,
            extra_data=extra,
            program=req.program,
            class_detail=req.class_detail,
            gobi_experience=req.gobi_experience
        )
        status_cn = {
            "confirmed": "正式戈友已认证",
            "pending": "已提交必填资料，待管理员审核",
            "temporary": "临时人员（资料待补齐）",
            "expired": "已过期"
        }.get(res.get("status"), "临时人员")

        msg = f"恭喜您成功加入【{res['org_name']}】大群体！当前状态：{status_cn}。"
        if res.get("status") == "temporary":
            msg += f" 您为临时人员（有效期还剩 {res.get('days_remaining', 14)} 天），请在到期前补齐必填资料并由管理员审核批准后方可加入下属跑团。"
        elif res.get("status") == "pending":
            msg += f" 必填资料已填齐（有效期还剩 {res.get('days_remaining', 14)} 天），正等待大群管理员审核批准后解锁下属跑团。"

        return {
            "success": True,
            "message": msg,
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
    for org in orgs:
        org["age_group"] = compute_age_group(org.get("date_of_birth"))
    return {"organizations": orgs}


@router.get("/{org_id}/field-rules")
def get_org_field_rules_endpoint(org_id: str):
    """
    Returns field requirements configuration for this organization.
    """
    rules = LocalStore.get_org_field_rules(org_id)
    return {"field_rules": rules}


@router.put("/{org_id}/field-rules")
def update_org_field_rules_endpoint(org_id: str, req: UpdateFieldRulesRequest):
    """
    Allows admin to update field requirements (required/optional) for this organization.
    """
    ok = LocalStore.update_org_field_rules(org_id, req.field_rules)
    if not ok:
        raise HTTPException(status_code=404, detail="组织不存在")
    return {"success": True, "message": "大群准入必填字段要求已更新！", "field_rules": req.field_rules}


@router.post("/{org_id}/members/update-profile")
def update_org_member_profile_endpoint(org_id: str, req: UpdateMemberProfileRequest):
    """
    Allows temporary or active members to complete/update their profile fields.
    """
    extra = dict(req.extra_data or {})
    if req.emergency_contact is not None:
        extra["emergency_contact"] = req.emergency_contact.strip()
    if req.clothing_size is not None:
        extra["clothing_size"] = req.clothing_size.strip()
    if req.shoe_size is not None:
        extra["shoe_size"] = req.shoe_size.strip()
    if req.marathon_pb is not None:
        extra["marathon_pb"] = req.marathon_pb.strip()
    if req.health_declaration is not None:
        extra["health_declaration"] = req.health_declaration

    try:
        updated = LocalStore.update_org_member_profile(
            org_id=org_id,
            user_id=req.user_id,
            data={
                "real_name": req.real_name,
                "gender": req.gender,
                "date_of_birth": req.date_of_birth,
                "class_name": req.class_name,
                "program": req.program,
                "class_detail": req.class_detail,
                "gobi_experience": req.gobi_experience,
                "phone": req.phone,
                "id_card": req.id_card,
                "extra_data": extra
            }
        )
        return {
            "success": True,
            "message": "大群体成员资料更新成功！",
            "membership": updated
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[update_org_member_profile] failed: {e}")
        raise HTTPException(status_code=500, detail="更新资料失败，请重试")


@router.get("/{org_id}")
def get_organization_endpoint(org_id: str, user_id: Optional[str] = None):
    """
    Returns detail of a specific grand community, rejecting expired/suspended members.
    """
    org = LocalStore.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if user_id:
        status_info = LocalStore.check_org_member_status(org_id, user_id)
        if status_info.get("is_member") and (status_info.get("status") in ("expired", "suspended") or not status_info.get("is_valid", True)):
            raise HTTPException(
                status_code=403,
                detail=f"您在【{org.get('name', '大群')}】的临时访问权限已到期（超过2周未完成必填字段审核），已无法进入大群。如需继续参与，请前往个人中心补齐必填资料并联系管理员确认。"
            )
        org["user_membership"] = status_info
    return {"organization": org}


@router.get("/{org_id}/sub-clubs")
def get_org_sub_clubs_endpoint(org_id: str, user_id: Optional[str] = None, request: Request = None):
    """
    Returns all sub-running clubs under this organization, with 'is_member' flag for the user.
    Blocks expired/suspended members from browsing.
    """
    eff_uid = user_id or (request.headers.get("x-user-id") if request else None)
    if eff_uid:
        status_info = LocalStore.check_org_member_status(org_id, eff_uid)
        if status_info.get("is_member") and (status_info.get("status") in ("expired", "suspended") or not status_info.get("is_valid", True)):
            org = LocalStore.get_organization(org_id)
            org_name = org.get("name") if org else "大群"
            raise HTTPException(
                status_code=403,
                detail=f"您在【{org_name}】的临时访问权限已到期（超过2周未完成必填字段审核），已无法浏览下属跑团列表。如需继续参与，请前往个人中心补齐必填资料并联系管理员确认。"
            )
    sub_clubs = LocalStore.get_org_sub_clubs(org_id, user_id)
    return {"sub_clubs": sub_clubs}


@router.get("/{org_id}/members")
def get_org_members_endpoint(org_id: str, search: Optional[str] = None, class_filter: Optional[str] = None, operator_uid: Optional[str] = None):
    """
    Returns verified member directory for the grand community (name, class, age_group, status, sub-clubs).
    Protects runner birth year, phone, and id_card privacy for non-admin viewers.
    Blocks expired members from viewing roster.
    """
    org = LocalStore.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")

    is_admin = False
    if operator_uid:
        if org.get("owner_id") == operator_uid or operator_uid in ("super_admin", "admin"):
            is_admin = True
        else:
            status_info = LocalStore.check_org_member_status(org_id, operator_uid)
            if status_info.get("is_member") and (status_info.get("status") in ("expired", "suspended") or not status_info.get("is_valid", True)):
                raise HTTPException(
                    status_code=403,
                    detail=f"您在【{org.get('name', '大群')}】的临时访问权限已到期，无法查看大群花名册。请前往个人中心补齐必填资料并联系管理员确认。"
                )
            if status_info.get("role") in ("owner", "admin"):
                is_admin = True

    members = LocalStore.get_org_members(org_id, search, class_filter)
    if not is_admin and not any(m.get("user_id") == operator_uid and m.get("role") in ("owner", "admin") for m in members):
        is_admin = False
    else:
        is_admin = True

    for m in members:
        is_self = bool(operator_uid and m.get("user_id") == operator_uid)
        dob = m.get("date_of_birth") or ""
        m["age_group"] = compute_age_group(dob)
        m["birth_year"] = dob[:4] if len(dob) >= 4 and dob[:4].isdigit() else ""

        if is_admin:
            # Org admin/owner sees full real name, but masked phone & ID card
            m["phone"] = mask_phone(m.get("phone"))
            m["id_card"] = mask_id_card(m.get("id_card"))
        elif is_self:
            # Self sees unmasked phone and masked ID card
            m["phone"] = m.get("phone") or ""
            m["id_card"] = mask_id_card(m.get("id_card"))
        else:
            # Other members: masked name, remove sensitive fields
            m["real_name"] = mask_name(m.get("real_name"))
            m.pop("phone", None)
            m.pop("id_card", None)
            m.pop("date_of_birth", None)
            m.pop("extra_data", None)
    return {"members": members}


@router.post("/{org_id}/members/{target_uid}/confirm")
def confirm_member_endpoint(org_id: str, target_uid: str, req: Optional[ConfirmMemberRequest] = None):
    """
    Allows Admin or Owner to confirm and audit a member's credential.
    """
    op = req.operator_uid if req else None
    try:
        ok = LocalStore.confirm_org_member(org_id, target_uid, op)
        if not ok:
            raise HTTPException(status_code=404, detail="未找到对应的成员记录")
        return {"success": True, "message": "成员资料核对确认完成！"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{org_id}/members/{target_uid}/role")
def update_org_member_role_endpoint(org_id: str, target_uid: str, req: UpdateOrgMemberRoleRequest):
    """
    Allows Org Owner or Super Admin to appoint or revoke Organization Admin role.
    """
    try:
        ok = LocalStore.update_org_member_role(org_id, target_uid, req.role, req.operator_uid)
        role_label = "大群管理员" if req.role == "admin" else "普通成员"
        return {"success": True, "message": f"已成功将该成员角色更新为【{role_label}】！"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[update_org_member_role] failed: {e}")
        raise HTTPException(status_code=500, detail="调整成员大群角色失败")


@router.post("/{org_id}/assign-sub-club")
def assign_sub_club_endpoint(org_id: str, req: AssignSubClubRequest):
    """
    Directly assigns / invites an organization member into a sub-running club.
    """
    club = LocalStore.get_club(req.club_id)
    if not club or club.get("org_id") != org_id:
        raise HTTPException(status_code=400, detail="该跑团不属于当前大组织！")
    
    try:
        joined = LocalStore.assign_member_to_sub_club(user_id=req.user_id, club_id=req.club_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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

