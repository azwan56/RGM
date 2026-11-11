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
    invite_code: Optional[str] = None
    org_id: Optional[str] = None
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
    jersey_size: Optional[str] = None
    running_shoe_size: Optional[str] = None
    full_marathon_pb: Optional[str] = None
    health_declaration: Optional[Any] = None
    extra_data: Optional[Dict[str, Any]] = None
    inviter_uid: Optional[str] = None
    via_invite: Optional[bool] = False
    skip_profile: Optional[bool] = False

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
    jersey_size: Optional[str] = None
    running_shoe_size: Optional[str] = None
    full_marathon_pb: Optional[str] = None
    health_declaration: Optional[Any] = None
    extra_data: Optional[Dict[str, Any]] = None

class ConfirmMemberRequest(BaseModel):
    operator_uid: Optional[str] = None

class AssignSubClubRequest(BaseModel):
    user_id: str
    club_id: str

class CreateOrgRequest(BaseModel):
    name: str
    invite_code: str
    join_mode: Optional[str] = "invite"
    description: Optional[str] = None
    city: Optional[str] = "上海"
    logo_url: Optional[str] = None
    owner_id: Optional[str] = None

class UpdateOrgRequest(BaseModel):
    name: Optional[str] = None
    invite_code: Optional[str] = None
    join_mode: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None
    logo_url: Optional[str] = None
    owner_id: Optional[str] = None
    operator_uid: Optional[str] = None

class UpdateOrgJoinModeRequest(BaseModel):
    operator_uid: str
    join_mode: Optional[str] = None  # 'free' or 'invite'
    invite_code: Optional[str] = None

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
    clean_code = (req.invite_code or "").strip()
    clean_org_id = (req.org_id or "").strip()
    if not clean_code and not clean_org_id:
        raise HTTPException(status_code=400, detail="组织专属邀请码与组织ID不能同时为空")

    # 一键入群：由大群有效成员发出的邀请卡片 / 小程序码 → 免大群邀请码
    skip_code_check = False
    if clean_org_id and req.via_invite and LocalStore.is_active_org_inviter(clean_org_id, req.inviter_uid):
        skip_code_check = True
    if clean_org_id and clean_code:
        org_by_code = LocalStore.get_organization_by_code(clean_code)
        if not org_by_code or org_by_code.get("id") != clean_org_id:
            if skip_code_check:
                clean_code = ""  # stale/absent code in link — trust the inviter instead
        else:
            skip_code_check = True

    extra = dict(req.extra_data or {})
    if req.emergency_contact:
        extra["emergency_contact"] = req.emergency_contact.strip()
    clothing = (req.clothing_size or req.jersey_size or "").strip()
    if clothing:
        extra["clothing_size"] = clothing
        extra["jersey_size"] = clothing
    shoe = (req.shoe_size or req.running_shoe_size or "").strip()
    if shoe:
        extra["shoe_size"] = shoe
        extra["running_shoe_size"] = shoe
    pb = (req.marathon_pb or req.full_marathon_pb or "").strip()
    if pb:
        extra["marathon_pb"] = pb
        extra["full_marathon_pb"] = pb
    if req.health_declaration is not None:
        if isinstance(req.health_declaration, bool):
            extra["health_declaration"] = req.health_declaration
        elif isinstance(req.health_declaration, str):
            clean_hd = req.health_declaration.strip()
            if clean_hd.lower() in ("false", "0", "否", "no", ""):
                extra["health_declaration"] = False
            else:
                extra["health_declaration"] = True
                extra["health_declaration_text"] = clean_hd
        else:
            extra["health_declaration"] = bool(req.health_declaration)

    try:
        res = LocalStore.join_organization(
            user_id=req.user_id,
            invite_code=clean_code or None,
            org_id=clean_org_id or None,
            real_name=req.real_name,
            gender=req.gender or "male",
            date_of_birth=req.date_of_birth,
            class_name=req.class_name,
            phone=req.phone,
            id_card=req.id_card,
            extra_data=extra,
            program=req.program,
            class_detail=req.class_detail,
            gobi_experience=req.gobi_experience,
            skip_code_check=skip_code_check
        )
        status_cn = {
            "confirmed": "正式戈友已认证",
            "pending": "资料已提交，待管理员审核",
            "temporary": "临时成员（资料可稍后补填）",
            "expired": "已过期"
        }.get(res.get("status"), "临时成员")

        days = res.get('days_remaining', 14)
        msg = f"恭喜您成功加入【{res['org_name']}】！当前状态：{status_cn}。"
        if res.get("status") == "temporary":
            msg += f" 现在即可直接加入下属跑团，无需审批。请在 {days} 天内补齐必填资料并通过管理员审核，逾期将被自动移出大群下全部跑团。"
        elif res.get("status") == "pending":
            msg += f" 已可直接加入下属跑团。管理员将在 {days} 天内完成审核。"
        elif res.get("status") == "expired":
            msg = (
                f"您在【{res['org_name']}】的资料补填期限已过，已被移出下属跑团。"
                f"请补齐全部必填资料提交审核，或联系大群管理员恢复资格。"
            )

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
    Allows Org Owner, Org Admin, or Super Admin to update field requirements (required/optional/hidden) for this organization.
    """
    try:
        updated_rules = LocalStore.update_org_field_rules(org_id, req.field_rules, req.operator_uid)
        if not updated_rules:
            raise HTTPException(status_code=404, detail="组织不存在")
        return {"success": True, "message": "大群准入字段规则（必填/选填/不显示）已更新！", "field_rules": updated_rules}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


@router.post("/{org_id}/members/update-profile")
def update_org_member_profile_endpoint(org_id: str, req: UpdateMemberProfileRequest):
    """
    Allows temporary or active members to complete/update their profile fields.
    """
    extra = dict(req.extra_data or {})
    if req.emergency_contact is not None:
        extra["emergency_contact"] = req.emergency_contact.strip()
    clothing = (req.clothing_size or req.jersey_size or "").strip()
    if clothing:
        extra["clothing_size"] = clothing
        extra["jersey_size"] = clothing
    shoe = (req.shoe_size or req.running_shoe_size or "").strip()
    if shoe:
        extra["shoe_size"] = shoe
        extra["running_shoe_size"] = shoe
    pb = (req.marathon_pb or req.full_marathon_pb or "").strip()
    if pb:
        extra["marathon_pb"] = pb
        extra["full_marathon_pb"] = pb
    if req.health_declaration is not None:
        if isinstance(req.health_declaration, bool):
            extra["health_declaration"] = req.health_declaration
        elif isinstance(req.health_declaration, str):
            clean_hd = req.health_declaration.strip()
            if clean_hd.lower() in ("false", "0", "否", "no", ""):
                extra["health_declaration"] = False
            else:
                extra["health_declaration"] = True
                extra["health_declaration_text"] = clean_hd
        else:
            extra["health_declaration"] = bool(req.health_declaration)

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
        # If operator is owner or admin, expose invite_code
        if status_info.get("role") in ("owner", "admin") or org.get("owner_id") == user_id or user_id in ("admin", "super_admin"):
            full_org = LocalStore.get_organization_admin(org_id)
            if full_org and full_org.get("invite_code"):
                org["invite_code"] = full_org["invite_code"]
    return {"organization": org}


@router.get("/{org_id}/invite-info")
def get_org_invite_info(
    org_id: str,
    invite_code: Optional[str] = None,
    user_id: Optional[str] = None,
    inviter_uid: Optional[str] = None
):
    """
    Returns public/safe preview info for an invited organization, validating code and member status.
    Used when a WeChat user taps an organization invite card.
    """
    org = LocalStore.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="大群体组织不存在！")

    org_admin = LocalStore.get_organization_admin(org_id)
    member_count = org_admin.get("member_count", 0) if org_admin else 0
    sub_clubs_count = org_admin.get("sub_clubs_count", 0) if org_admin else 0

    is_member = False
    member_status = None
    if user_id:
        st = LocalStore.check_org_member_status(org_id, user_id)
        is_member = st.get("is_member", False)
        member_status = st.get("status")

    clean_code = (invite_code or "").strip().upper()
    real_code = (org_admin.get("invite_code") if org_admin else (org.get("invite_code") or "")).strip().upper()

    is_code_valid = False
    if (org.get("join_mode") or "invite") == "free":
        is_code_valid = True
    elif clean_code and clean_code == real_code:
        is_code_valid = True
    elif inviter_uid and LocalStore.is_active_org_inviter(org_id, inviter_uid):
        is_code_valid = True

    return {
        "organization": {
            "id": org["id"],
            "name": org["name"],
            "logo_url": org.get("logo_url"),
            "city": org.get("city"),
            "description": org.get("description"),
            "join_mode": org.get("join_mode") or "invite",
            "member_count": member_count,
            "sub_clubs_count": sub_clubs_count,
        },
        "is_member": is_member,
        "member_status": member_status,
        "is_code_valid": is_code_valid,
        "one_click_join": is_code_valid,
        "profile_deadline_days": LocalStore.ORG_PROFILE_DEADLINE_DAYS,
    }


@router.get("/{org_id}/share-info")
def get_org_share_info(org_id: str, user_id: Optional[str] = None):
    """
    Returns share parameters including invite_code for verified org members or admins.
    """
    org = LocalStore.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="大群体不存在")

    org_admin = LocalStore.get_organization_admin(org_id)
    real_code = (org_admin.get("invite_code") if org_admin else (org.get("invite_code") or "")).strip().upper()

    return {
        "org_id": org["id"],
        "name": org["name"],
        "logo_url": org.get("logo_url"),
        "city": org.get("city"),
        "join_mode": org.get("join_mode") or "invite",
        "invite_code": real_code,
    }


@router.get("/{org_id}/sub-clubs")
def get_org_sub_clubs_endpoint(org_id: str, user_id: Optional[str] = None, request: Request = None):
    """
    Returns all sub-running clubs under this organization, with 'is_member' flag for the user.
    Blocks expired/suspended members from browsing.
    """
    eff_uid = user_id or (request.headers.get("x-user-id") if request else None)
    if eff_uid:
        status_info = LocalStore.check_org_member_status(org_id, eff_uid)
        if not status_info.get("is_member") and eff_uid not in ("admin", "super_admin"):
            # Not a member of the organization -> sub-clubs are completely invisible
            return {"sub_clubs": []}

        if status_info.get("status") in ("expired", "suspended") or not status_info.get("is_valid", True):
            org = LocalStore.get_organization(org_id)
            org_name = org.get("name") if org else "大群"
            raise HTTPException(
                status_code=403,
                detail=f"您在【{org_name}】的临时访问权限已到期（超过2周未完成必填字段审核），已无法浏览下属跑团列表。如需继续参与，请前往个人中心补齐必填资料并联系管理员确认。"
            )

    sub_clubs = LocalStore.get_org_sub_clubs(org_id, eff_uid)
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


@router.post("/{org_id}/members/{target_uid}/grace-period")
def grant_member_grace_period_endpoint(org_id: str, target_uid: str):
    """
    Allows Admin or Owner to grant a fresh 14-day temporary grace period to an expired member.
    """
    ok = LocalStore.grant_member_grace_period(org_id, target_uid)
    if not ok:
        raise HTTPException(status_code=404, detail="未找到对应的大群成员记录")
    return {"success": True, "message": "已成功为该队员重置14天临时宽限期！"}


@router.post("/{org_id}/remove-expired-sub-club-members")
def remove_expired_sub_club_members_endpoint(org_id: str):
    """
    Recalculates organization member statuses and removes all expired members
    from all sub-clubs belonging to this organization.
    """
    org = LocalStore.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="大群体组织不存在")
    res = LocalStore.remove_expired_org_members_from_sub_clubs(org_id)
    return {
        "success": True,
        "message": f"已完成【{org.get('name', org_id)}】下属跑团过期人员清理，共从下属跑团移除 {res['removed_count']} 条过期成员记录。",
        "result": res
    }


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


@router.post("/{org_id}/join-mode")
def update_org_join_mode_endpoint(org_id: str, req: UpdateOrgJoinModeRequest):
    """
    Allows organization organizer (owner / admin) to view/switch between 'free' and 'invite', and customize invite_code.
    """
    if req.join_mode and req.join_mode not in ("free", "invite"):
        raise HTTPException(status_code=400, detail="入会规则仅支持 'free' (自由入会) 或 'invite' (凭专属邀请码入会)")
    try:
        updated = LocalStore.update_organization_join_mode(
            org_id=org_id,
            operator_uid=req.operator_uid,
            join_mode=req.join_mode,
            invite_code=req.invite_code
        )
        mode_label = "自由入会（免邀请码）" if updated.get("join_mode") == "free" else "凭专属邀请码入会"
        return {
            "success": True,
            "message": f"大群入会规则已成功切换为【{mode_label}】！",
            "organization": updated
        }
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"[update_org_join_mode] failed: {e}")
        raise HTTPException(status_code=500, detail="更新大群入会规则失败")


@router.put("/{org_id}")
def update_org_endpoint(org_id: str, req: UpdateOrgRequest):
    """
    Updates organization info (name, invite_code, description, city, logo_url, owner_id, join_mode).
    Allows Org Owner, Org Admin, or Super Admin.
    """
    data = req.model_dump(exclude_unset=True) if hasattr(req, "model_dump") else req.dict(exclude_unset=True)
    op_uid = data.pop("operator_uid", None)
    if op_uid and not LocalStore.is_org_organizer(org_id, op_uid):
        raise HTTPException(status_code=403, detail="只有大群主理人、大群管理员或超级管理员有权修改大群设定！")

    if ("join_mode" in data or "invite_code" in data) and op_uid:
        try:
            LocalStore.update_organization_join_mode(
                org_id=org_id,
                operator_uid=op_uid,
                join_mode=data.get("join_mode"),
                invite_code=data.get("invite_code")
            )
        except PermissionError as pe:
            raise HTTPException(status_code=403, detail=str(pe))
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))

    updated = LocalStore.update_organization(org_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="组织不存在")
    return {"success": True, "message": "大群设定信息更新成功！", "organization": updated}


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
            owner_id=req.owner_id,
            join_mode=req.join_mode or "invite"
        )
        return {"success": True, "message": f"大组织【{req.name}】创建成功！", "organization": org}
    except Exception as e:
        logger.error(f"[create_organization] failed: {e}")
        raise HTTPException(status_code=400, detail=f"创建组织失败（邀请码可能已存在）: {str(e)}")


class CreateOrgEventRequest(BaseModel):
    operator_uid: str
    title: str
    event_type: Optional[str] = "group_run"  # 'group_run' | 'distance_challenge'
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    meet_time: Optional[str] = None
    location: Optional[str] = None
    location_detail: Optional[str] = None
    target_km: Optional[float] = 15.0
    pace_requirement: Optional[str] = "A组 / B组 / C组 / 健康组"
    rules: Optional[str] = None
    max_participants: Optional[int] = 0
    scope_club_ids: Optional[Any] = "all"  # 'all' or list of club_ids
    host_club_id: Optional[str] = None
    repeat_rule: Optional[str] = "none"
    repeat_weeks: Optional[int] = 1


class AssignOrgMemberClubRequest(BaseModel):
    operator_uid: str
    club_id: str


@router.get("/{org_id}/reports")
def get_org_periodic_report_endpoint(
    org_id: str,
    operator_uid: Optional[str] = None,
    period_type: str = "week",
    year: Optional[int] = None,
    period_index: Optional[int] = None,
    period_offset: Optional[int] = None,
    trail_mode: str = "include",
):
    """
    Returns cross-club periodic report (sub-club PK rankings, deduplicated member rankings, unaffiliated members radar)
    for Org Owners, Org Admins, or Super Admins.
    """
    try:
        return LocalStore.get_org_periodic_report(
            org_id=org_id,
            operator_uid=operator_uid,
            period_type=period_type,
            year=year,
            period_index=period_index,
            period_offset=period_offset,
            trail_mode=trail_mode,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"[get_org_periodic_report] failed: {e}")
        raise HTTPException(status_code=500, detail="获取大群全域报表失败")


@router.get("/{org_id}/events")
def get_org_events_endpoint(org_id: str, user_id: Optional[str] = None):
    """
    Returns all cross-club events and sub-club events under this organization, including per-sub-club participation breakdown.
    """
    try:
        return LocalStore.get_org_events(org_id=org_id, user_id=user_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"[get_org_events] failed: {e}")
        raise HTTPException(status_code=500, detail="获取大群跨跑团活动失败")


@router.post("/{org_id}/events")
def create_org_event_endpoint(org_id: str, req: CreateOrgEventRequest):
    """
    Allows Org Owner, Org Admin, or Super Admin to publish a cross-club event (group run or mileage challenge).
    """
    if not req.title or not req.title.strip():
        raise HTTPException(status_code=400, detail="活动名称不能为空")
    try:
        data = req.model_dump() if hasattr(req, "model_dump") else req.dict()
        return LocalStore.create_org_event(org_id=org_id, operator_uid=req.operator_uid, data=data)
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"[create_org_event] failed: {e}")
        raise HTTPException(status_code=500, detail="发布跨跑团联合活动失败")


@router.post("/{org_id}/members/{target_uid}/assign-club")
def assign_org_member_to_sub_club_endpoint(org_id: str, target_uid: str, req: AssignOrgMemberClubRequest):
    """
    Allows Org Owner, Org Admin, or Super Admin to assign an unaffiliated (or any) org member to a sub-club.
    """
    try:
        return LocalStore.assign_org_member_to_sub_club(
            org_id=org_id,
            target_uid=target_uid,
            club_id=req.club_id,
            operator_uid=req.operator_uid,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"[assign_org_member_to_sub_club] failed: {e}")
        raise HTTPException(status_code=500, detail="分配下属跑团失败")


