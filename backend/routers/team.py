from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import os
import json
import time
import hashlib
from datetime import datetime, date
from config import settings
from db import supabase_admin
from utils.local_store import LocalStore
from utils.security import is_safe_external_url, validate_uploaded_image_bytes

logger = logging.getLogger("router_team")
router = APIRouter()

class CreateClubRequest(BaseModel):
    owner_id: str
    name: str
    description: Optional[str] = None
    city: Optional[str] = "上海"
    logo_url: Optional[str] = None
    join_mode: Optional[str] = "free"
    invite_code: Optional[str] = None
    org_id: Optional[str] = None

class UpdateClubInfoOwnerRequest(BaseModel):
    operator_uid: str
    name: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None
    logo_url: Optional[str] = None
    org_id: Optional[str] = None

class JoinClubRequest(BaseModel):
    user_id: str
    invite_code: str
    privacy_consent: Optional[bool] = True
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

class JoinClubByIdRequest(BaseModel):
    user_id: str
    club_id: str
    invite_code: Optional[str] = None
    privacy_consent: Optional[bool] = True
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    inviter_uid: Optional[str] = None
    via_invite: Optional[bool] = False

class UpdateJoinModeRequest(BaseModel):
    operator_uid: str
    join_mode: Optional[str] = None # 'free' or 'invite'
    invite_code: Optional[str] = None

class UpdateMemberRoleRequest(BaseModel):
    operator_uid: str
    target_uid: str
    role: str # 'owner', 'coach', 'member'

class UpdateMemberTrainingGroupRequest(BaseModel):
    operator_uid: str
    target_uid: str
    training_group: Optional[str] = None

class CreateClubEventRequest(BaseModel):
    operator_uid: str
    title: str
    event_type: Optional[str] = "group_run" # 'group_run', 'distance_challenge'
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    meet_time: Optional[str] = None
    location: Optional[str] = None
    location_detail: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    cover_image: Optional[str] = None
    target_km: Optional[float] = 10.0
    pace_requirement: Optional[str] = None
    max_participants: Optional[int] = 0
    rules: Optional[str] = None
    repeat_rule: Optional[str] = "none" # 'none', 'weekly'
    repeat_weeks: Optional[int] = 1 # 1, 2, 4, 8
    visibility_mode: Optional[str] = "registered_only" # 'registered_only' | 'club_members' | 'public'
    recap_note: Optional[str] = None

class JoinEventRequest(BaseModel):
    user_id: str
    pace_group: Optional[str] = None
    runner_role: Optional[str] = None
    checkin_note: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    auto_join_club: Optional[bool] = True
    join_event: Optional[bool] = True
    inviter_uid: Optional[str] = None

class UpdateParticipantCheckinRequest(BaseModel):
    user_id: str
    pace_group: Optional[str] = None
    runner_role: Optional[str] = None
    checkin_note: Optional[str] = None
    manual_distance_km: Optional[float] = None
    manual_pace_str: Optional[str] = None
    manual_duration_str: Optional[str] = None
    activity_id: Optional[str] = None
    post_to_wall: Optional[bool] = True

class UpdateEventVisibilityRequest(BaseModel):
    operator_uid: str
    visibility_mode: str # 'registered_only' | 'club_members' | 'public'
    recap_note: Optional[str] = None

class HighfiveParticipantRequest(BaseModel):
    from_user_id: str
    target_user_id: str

class AddEventCommentRequest(BaseModel):
    user_id: str
    content: str

class SetClubStatusOwnerRequest(BaseModel):
    operator_uid: str
    status: str # 'active', 'paused', 'locked'


# Built-in fast GCJ-02 landmark index for instant lookup + gate precision
_KNOWN_LANDMARKS_GCJ02 = [
    {"name": "闵行文化公园", "address": "上海市闵行区吴中路2019号闵行文化公园", "latitude": 31.1634, "longitude": 121.3609},
    {"name": "闵行文化公园1号门", "address": "上海市闵行区吴中路2019号闵行文化公园1号门(北门)", "latitude": 31.1682, "longitude": 121.3586},
    {"name": "闵行文化公园2号门", "address": "上海市闵行区漕宝路2001号闵行文化公园2号门(南门)", "latitude": 31.1578, "longitude": 121.3595},
    {"name": "闵行文化公园3号门", "address": "上海市闵行区新镇路闵行文化公园3号门(西门)", "latitude": 31.1625, "longitude": 121.3538},
    {"name": "闵行体育公园", "address": "上海市闵行区新镇路456号闵行体育公园", "latitude": 31.1429, "longitude": 121.3708},
    {"name": "世纪公园", "address": "上海市浦东新区锦绣路1001号世纪公园", "latitude": 31.2166, "longitude": 121.5529},
    {"name": "世纪公园7号门", "address": "上海市浦东新区锦绣路701号世纪公园7号门跑步驿站", "latitude": 31.2165, "longitude": 121.5518},
    {"name": "世纪公园1号门", "address": "上海市浦东新区锦绣路1001号世纪公园1号门", "latitude": 31.2241, "longitude": 121.5403},
    {"name": "徐汇滨江", "address": "上海市徐汇区龙腾大道瑞宁路徐汇滨江跑步驿站", "latitude": 31.1892, "longitude": 121.4619},
    {"name": "卢湾体育场", "address": "上海市黄浦区肇嘉浜路128号卢湾体育场", "latitude": 31.2094, "longitude": 121.4646},
    {"name": "源深体育中心", "address": "上海市浦东新区源深路655号源深体育中心田径场", "latitude": 31.2335, "longitude": 121.5396},
    {"name": "半马苏河公园苗江路", "address": "上海市黄浦区苗江路望达路绿地", "latitude": 31.2016, "longitude": 121.4932},
    {"name": "大宁公园", "address": "上海市静安区广中西路288号大宁灵石公园", "latitude": 31.2752, "longitude": 121.4393},
    {"name": "大宁灵石公园", "address": "上海市静安区广中西路288号大宁灵石公园", "latitude": 31.2752, "longitude": 121.4393},
    {"name": "共青森林公园", "address": "上海市杨浦区军工路2000号共青森林公园", "latitude": 31.3187, "longitude": 121.5523},
    {"name": "顾村公园", "address": "上海市宝山区沪太路4788号顾村公园", "latitude": 31.3444, "longitude": 121.3732},
    {"name": "中山公园", "address": "上海市长宁区长宁路780号中山公园", "latitude": 31.2188, "longitude": 121.4165},
    {"name": "佘山国家森林公园", "address": "上海市松江区外青松公路9258号东佘山园", "latitude": 31.0956, "longitude": 121.1965},
    {"name": "滴水湖", "address": "上海市浦东新区南汇新城镇环湖西一路滴水湖", "latitude": 30.9069, "longitude": 121.9299},
    {"name": "奥林匹克森林公园", "address": "北京市朝阳区科荟路33号奥林匹克森林公园南门", "latitude": 40.0156, "longitude": 116.3924},
    {"name": "朝阳公园", "address": "北京市朝阳区朝阳公园南路1号", "latitude": 39.9428, "longitude": 116.4785},
    {"name": "玄武湖公园", "address": "江苏省南京市玄武区玄武巷1号玄武门", "latitude": 32.0724, "longitude": 118.7979},
    {"name": "西湖", "address": "浙江省杭州市西湖区龙井路1号杭州西湖风景名胜区", "latitude": 30.2437, "longitude": 120.1479},
    {"name": "深圳湾公园", "address": "广东省深圳市南山区滨海大道深圳湾公园", "latitude": 22.5216, "longitude": 113.9930},
]


@router.get("/geocode")
def geocode_venue_endpoint(
    q: str = Query(..., description="地点名称或地址关键词，如：闵行文化公园"),
    city: Optional[str] = Query("上海", description="优先城市")
):
    """
    Resolves a user-entered location name into GCJ-02 (WeChat/Tencent Map) coordinates
    so the miniapp can pop up an interactive map centered at that location for exact pin placement.
    """
    import re
    import requests as ext_req
    from utils.geo_utils import wgs84_to_gcj02

    raw_q = (q or "").strip()
    if not raw_q:
        return {"results": []}

    results: List[Dict[str, Any]] = []
    seen_coords = set()

    def _add_item(name: str, address: str, lat: float, lng: float):
        key = (round(lat, 4), round(lng, 4))
        if key in seen_coords:
            return
        seen_coords.add(key)
        results.append({
            "name": name,
            "address": address,
            "latitude": round(lat, 6),
            "longitude": round(lng, 6),
        })

    # 1. Match built-in known landmarks first
    base_q = re.sub(r"([0-9一二三四五六七八九十]+号门|[东南西北正]门|跑步驿站|田径场|跑道)$", "", raw_q).strip()
    for item in _KNOWN_LANDMARKS_GCJ02:
        if raw_q in item["name"] or item["name"] in raw_q or (base_q and len(base_q) >= 2 and base_q in item["name"]):
            # If user entered a specific gate suffix on a general landmark, preserve user's title on first match
            display_name = raw_q if (raw_q != item["name"] and item["name"] in raw_q and len(results) == 0) else item["name"]
            _add_item(display_name, item["address"], item["latitude"], item["longitude"])

    # 2. Live geocoding via Photon (OpenStreetMap) + WGS84 -> GCJ02 conversion
    search_queries = [raw_q]
    if base_q and base_q != raw_q and len(base_q) >= 2:
        search_queries.append(base_q)

    for sq in search_queries:
        if len(results) >= 6:
            break
        try:
            resp = ext_req.get(
                "https://photon.komoot.io/api/",
                params={"q": sq, "lat": 31.2304, "lon": 121.4737, "limit": 5},
                headers={"User-Agent": "Mozilla/5.0 (RGM-MiniApp/1.0)"},
                timeout=3.5,
            )
            if resp.status_code == 200:
                feats = resp.json().get("features") or []
                for f in feats:
                    coords = (f.get("geometry") or {}).get("coordinates") or []
                    if len(coords) >= 2:
                        wgs_lng, wgs_lat = float(coords[0]), float(coords[1])
                        gcj_lat, gcj_lng = wgs84_to_gcj02(wgs_lat, wgs_lng)
                        props = f.get("properties") or {}
                        pname = (props.get("name") or sq).strip()
                        addr_parts = [
                            props.get("state") or "",
                            props.get("city") or "",
                            props.get("district") or "",
                            props.get("street") or "",
                            pname,
                        ]
                        addr_str = "".join(dict.fromkeys([p for p in addr_parts if p]))
                        _add_item(pname, addr_str or pname, gcj_lat, gcj_lng)
        except Exception as e:
            logger.warning(f"Geocode query '{sq}' failed: {e}")

    return {"results": results[:6]}


@router.get("/my-clubs/{uid}")
def get_user_clubs(uid: str):
    """Returns all running clubs the user has joined (invite_code visible only to owner and coach)."""
    clubs = LocalStore.get_user_clubs(uid)
    is_super = LocalStore.is_super_admin(uid)
    for c in clubs:
        if c.get("role") not in ("owner", "coach") and not is_super:
            c.pop("invite_code", None)
    if is_super:
        try:
            unaff_info = LocalStore.get_unaffiliated_users_status(viewer_uid=uid)
            unaff_total = int((unaff_info.get("summary") or {}).get("total_members") or 0)
        except Exception:
            unaff_total = 0
        clubs.append({
            "id": "unaffiliated",
            "name": f"未入团跑友({unaff_total})",
            "description": "尚未加入任何跑团的注册跑友全局名册（超级管理员专属视图）",
            "owner_id": uid,
            "owner_name": "超级管理员",
            "role": "owner",
            "status": "active",
            "join_mode": "invite",
            "city": "全局",
            "member_count": unaff_total,
            "is_virtual_unaffiliated": True,
        })
    return {"clubs": clubs, "is_super_admin": is_super}


@router.get("/all-clubs")
def get_all_public_clubs(
    user_id: Optional[str] = None,
    city: Optional[str] = None,
    search: Optional[str] = None
):
    """Returns all available clubs in the platform for runners to browse and join, filtered by user org visibility and optional city/search."""
    clubs = LocalStore.list_public_clubs(user_id=user_id, city=city, search=search)
    cities = LocalStore.list_public_cities(user_id=user_id)
    return {"clubs": clubs, "cities": cities}


@router.get("/creation-eligibility/{uid}")
def get_club_creation_eligibility(uid: str):
    """
    Returns user's referral progress (invited & watch-bound new users count vs required 3)
    and whether self-service club creation is unlocked.
    Note: Organization (大群) creation is disabled for regular users.
    """
    return LocalStore.get_referral_status(uid, required_count=3)


@router.post("/clubs")
def create_club(req: CreateClubRequest):
    """
    Self-service running club creation.
    Requires the user to have invited at least 3 new users who bound a watch (or be a super admin).
    Organization (大群) creation remains closed.
    """
    owner_id = (req.owner_id or "").strip()
    if not owner_id:
        raise HTTPException(status_code=400, detail="缺少创建人用户ID")

    club_name = (req.name or "").strip()
    if not club_name:
        raise HTTPException(status_code=400, detail="请输入跑团名称")
    if len(club_name) > 30:
        raise HTTPException(status_code=400, detail="跑团名称不能超过 30 个字符")

    eligibility = LocalStore.get_referral_status(owner_id, required_count=3)
    if not eligibility.get("can_create_club"):
        invited = eligibility.get("invited_count", 0)
        remaining = eligibility.get("remaining_count", 3)
        raise HTTPException(
            status_code=403,
            detail=f"自建跑团需累计成功邀请满 3 位新用户注册并绑定运动手表后解锁（当前已达标 {invited}/3 位，还差 {remaining} 位）。快去分享邀请跑友加入并绑定手表吧！"
        )

    custom_code = (req.invite_code or "").strip().upper() or None
    if custom_code and (len(custom_code) < 3 or len(custom_code) > 12):
        raise HTTPException(status_code=400, detail="专属邀请码长度需为 3-12 位字母或数字")

    join_mode = req.join_mode if req.join_mode in ("free", "invite") else "free"
    city = (req.city or "上海").strip() or "上海"
    description = (req.description or "").strip() or f"欢迎加入{club_name}，一起科学训练、无伤畅跑！"

    target_org_id = None
    org_name = None
    if req.org_id and req.org_id.strip() not in ("", "none", "independent"):
        clean_org_id = req.org_id.strip()
        org_obj = LocalStore.get_organization(clean_org_id)
        if not org_obj:
            raise HTTPException(status_code=404, detail="所选归属大群不存在")
        st_org = LocalStore.check_org_member_status(clean_org_id, owner_id)
        if not st_org.get("is_member") and org_obj.get("owner_id") != owner_id and owner_id not in ("admin", "super_admin"):
            raise HTTPException(status_code=403, detail="您尚未加入该大群，无法在该大群下创建分属跑团")
        target_org_id = clean_org_id
        org_name = org_obj.get("name")

    try:
        club = LocalStore.create_club(
            owner_id=owner_id,
            name=club_name,
            description=description,
            city=city,
            logo_url=req.logo_url,
            org_id=target_org_id,
            join_mode=join_mode,
            invite_code=custom_code,
        )
        if org_name:
            club["org_name"] = org_name
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "message": f"恭喜！跑团【{club['name']}】创建成功，您已成为跑团团长！",
        "club": club
    }


@router.post("/join-club")
def join_club_by_id(req: JoinClubByIdRequest):
    """Allows runner to select and join an existing club directly by club_id.
    If the club requires an invite code, verifies it."""
    profile_updates: Dict[str, Any] = {}
    if req.display_name and req.display_name.strip():
        profile_updates["display_name"] = req.display_name.strip()
    if req.avatar_url and req.avatar_url.strip():
        profile_updates["avatar_url"] = req.avatar_url.strip()
    if profile_updates:
        try:
            LocalStore.upsert_profile(req.user_id, profile_updates)
        except Exception as ex:
            logger.warning(f"Failed to update user profile on join-club: {ex}")

    try:
        club = LocalStore.join_club_by_id(
            user_id=req.user_id,
            club_id=req.club_id,
            privacy_consent=req.privacy_consent if req.privacy_consent is not None else True,
            invite_code=req.invite_code,
            inviter_uid=req.inviter_uid,
            via_invite=bool(req.via_invite),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not club:
        raise HTTPException(status_code=404, detail="所选跑团不存在或已解散！")

    sanitized = dict(club)
    sanitized.pop("invite_code", None)
    user_obj = LocalStore.get_profile(req.user_id) or {}

    # 隶属大群的跑团：返回大群资料补填状态，前端引导「稍后补填」
    org_membership = None
    message = f"成功加入跑团【{sanitized['name']}】！"
    if sanitized.get("org_id"):
        try:
            st = LocalStore.check_org_member_status(sanitized["org_id"], req.user_id)
            org_obj = LocalStore.get_organization(sanitized["org_id"]) or {}
            org_membership = {
                "org_id": sanitized["org_id"],
                "org_name": org_obj.get("name"),
                "status": st.get("status"),
                "days_remaining": st.get("days_remaining"),
                "deadline_at": st.get("deadline_at"),
                "missing_fields": st.get("missing_fields", []),
            }
            sanitized["org_name"] = org_obj.get("name")
            if st.get("status") == "temporary":
                message += (
                    f" 您已同时加入【{org_obj.get('name', '大群')}】，请在 {st.get('days_remaining', 14)} 天内补齐大群资料并通过审核，"
                    f"逾期将被移出大群下全部跑团。"
                )
            elif st.get("status") == "pending":
                message += f" 大群资料已提交，等待管理员审核（剩余 {st.get('days_remaining', 14)} 天）。"
        except Exception as ex:
            logger.warning(f"[join-club] org status lookup failed: {ex}")

    return {
        "message": message,
        "club": sanitized,
        "org_membership": org_membership,
        "display_name": user_obj.get("display_name"),
        "avatar_url": user_obj.get("avatar_url"),
    }


@router.post("/join")
def join_club_by_invite(req: JoinClubRequest):
    """Joins a running club using a 6-digit invite code."""
    profile_updates: Dict[str, Any] = {}
    if req.display_name and req.display_name.strip():
        profile_updates["display_name"] = req.display_name.strip()
    if req.avatar_url and req.avatar_url.strip():
        profile_updates["avatar_url"] = req.avatar_url.strip()
    if profile_updates:
        try:
            LocalStore.upsert_profile(req.user_id, profile_updates)
        except Exception as ex:
            logger.warning(f"Failed to update user profile on join: {ex}")

    try:
        club = LocalStore.join_club_by_code(
            user_id=req.user_id,
            invite_code=req.invite_code,
            privacy_consent=req.privacy_consent if req.privacy_consent is not None else True
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not club:
        code = (req.invite_code or "").strip().upper()
        org = LocalStore.get_organization_by_code(code)
        if org:
            org_name = org.get("name", "高校戈友")
            raise HTTPException(
                status_code=400,
                detail=f"【{org_name}】是高校戈友/大群体专属认证码（非普通跑团码）。请前往【跑团】页面，点击【凭专属邀请码实名认证加入】进行认证！"
            )
        raise HTTPException(status_code=404, detail="无效的邀请码，请向团长核对后重新输入！")

    sanitized = dict(club)
    sanitized.pop("invite_code", None)
    user_obj = LocalStore.get_profile(req.user_id) or {}
    return {
        "message": f"成功加入跑团【{sanitized['name']}】！",
        "club": sanitized,
        "display_name": user_obj.get("display_name"),
        "avatar_url": user_obj.get("avatar_url"),
    }


def _generate_club_invite_wxacode(
    club_id: str,
    invite_code: str = "",
    inviter_uid: Optional[str] = None,
    env_version: str = "release",
) -> Dict[str, str]:
    """Generates and caches an official WeChat Mini Program QR code (wxacode) for club invitation."""
    import base64
    from utils.wechat import wechat_client

    eff_env = env_version if env_version in ("release", "trial", "develop") else "release"
    safe_club = "".join(c for c in (club_id or "") if c.isalnum() or c in ("_", "-"))[:24]
    safe_uid = "".join(c for c in (inviter_uid or "web") if c.isalnum() or c in ("_", "-"))[:20]
    safe_code = "".join(c for c in (invite_code or "") if c.isalnum())[:12]
    filename = f"wxacode_club_inv_{eff_env}_{safe_club}_{safe_code}_{safe_uid}.jpg"
    avatar_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "avatars")
    os.makedirs(avatar_dir, exist_ok=True)
    file_path = os.path.join(avatar_dir, filename)

    qr_path = f"pages/team/team?club_id={club_id}&action=join_club&invite_code={invite_code}&inviter_uid={inviter_uid or ''}"

    if not os.path.exists(file_path) or os.path.getsize(file_path) < 500:
        try:
            img_bytes = wechat_client.get_wxacode_by_path(
                path=qr_path,
                width=280,
                env_version=eff_env,
            )
            if not img_bytes and inviter_uid:
                img_bytes = wechat_client.get_wxacode_unlimit(
                    scene=f"inv={inviter_uid[:16]}"[:32],
                    page="pages/team/team",
                    width=280,
                    env_version=eff_env,
                )
            if img_bytes and len(img_bytes) >= 500:
                with open(file_path, "wb") as f:
                    f.write(img_bytes)
        except Exception as e:
            logger.warning(f"[_generate_club_invite_wxacode] failed: {e}")

    qrcode_b64 = ""
    qrcode_url = ""
    if os.path.exists(file_path) and os.path.getsize(file_path) >= 500:
        qrcode_url = f"https://rgm.vanpower.net/api/avatars/{filename}"
        with open(file_path, "rb") as f:
            qrcode_b64 = base64.b64encode(f.read()).decode("ascii")
    else:
        try:
            fallback_qr = LocalStore.get_pure_miniapp_qrcode(eff_env)
            qrcode_url = fallback_qr.get("qrcode_url", "")
            qrcode_b64 = fallback_qr.get("qrcode_base64", "")
        except Exception:
            pass

    return {"qrcode_url": qrcode_url, "qrcode_base64": qrcode_b64}


@router.get("/{club_id}/invite-info")
def get_club_invite_info(
    club_id: str,
    invite_code: Optional[str] = None,
    user_id: Optional[str] = None,
    inviter_uid: Optional[str] = None
):
    """
    Returns public/safe preview info for an invited club, validating invite code and member status if provided.
    Used when a WeChat user taps an invite card or opens a web invite link.
    """
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="所受邀跑团不存在或已解散！")

    org_name = None
    org_id = club.get("org_id")
    if org_id:
        org = LocalStore.get_organization(org_id)
        if org:
            org_name = org.get("name")

    members = LocalStore.get_club_members(club_id)
    is_club_member = False
    is_org_member = False
    org_status = None

    if user_id:
        is_club_member = any(m["user_id"] == user_id for m in members)
        if org_id:
            st = LocalStore.check_org_member_status(org_id, user_id)
            is_org_member = st.get("is_member", False)
            org_status = st.get("status")

    clean_code = (invite_code or "").strip().upper()
    club_code = (club.get("invite_code") or "").strip().upper()
    is_code_valid = False
    if club.get("join_mode") == "free":
        is_code_valid = True
    elif clean_code and clean_code == club_code:
        is_code_valid = True
    elif inviter_uid and LocalStore.is_active_club_inviter(club_id, inviter_uid):
        # 由跑团有效成员发出的邀请卡片 / 小程序码 → 免邀请码一键入团
        is_code_valid = True

    inviter_name = ""
    if inviter_uid:
        inv_p = LocalStore.get_profile(inviter_uid) or {}
        inviter_name = (inv_p.get("real_name") or inv_p.get("display_name") or "").strip()
        if inviter_name in ("跑者", "微信用户", "微信跑者"):
            inviter_name = ""

    qr_info = _generate_club_invite_wxacode(
        club_id=club["id"],
        invite_code=clean_code or (club_code if is_code_valid else ""),
        inviter_uid=inviter_uid,
        env_version="release",
    )

    return {
        "club": {
            "id": club["id"],
            "name": club["name"],
            "logo_url": club.get("logo_url"),
            "city": club.get("city"),
            "description": club.get("description"),
            "join_mode": club.get("join_mode") or "free",
            "member_count": len(members),
            "org_id": org_id,
            "org_name": org_name,
        },
        "inviter_uid": inviter_uid or "",
        "inviter_name": inviter_name,
        "is_club_member": is_club_member,
        "is_org_member": is_org_member,
        "org_status": org_status,
        "is_code_valid": is_code_valid,
        "one_click_join": is_code_valid,
        "profile_deadline_days": LocalStore.ORG_PROFILE_DEADLINE_DAYS if org_id else None,
        "qrcode_url": qr_info["qrcode_url"],
        "qrcode_base64": qr_info["qrcode_base64"],
    }


@router.get("/{club_id}/share-info")
def get_club_share_info(
    club_id: str,
    user_id: Optional[str] = None,
    env_version: Optional[str] = "release",
):
    """
    Returns share parameters including invite_code, official WeChat Mini Program QR code (wxacode),
    Web direct invite URL, and ready-to-forward WeChat text for verified club members, coaches, owners, or org organizers.
    """
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")

    members = LocalStore.get_club_members(club_id)
    is_member = any(m["user_id"] == user_id for m in members) if user_id else False
    is_owner = club.get("owner_id") == user_id
    org_id = club.get("org_id")
    is_org_admin = LocalStore.is_org_organizer(org_id, user_id) if (org_id and user_id) else False

    org_name = None
    if org_id:
        org = LocalStore.get_organization(org_id)
        if org:
            org_name = org.get("name")

    # If free join mode, or user is member/owner/coach/org_admin, include invite_code so invited friends can join seamlessly
    invite_code = (
        club.get("invite_code", "")
        if (is_member or is_owner or is_org_admin or club.get("join_mode") == "free")
        else ""
    )

    inviter_name = ""
    if user_id:
        inv_p = LocalStore.get_profile(user_id) or {}
        inviter_name = (inv_p.get("real_name") or inv_p.get("display_name") or "").strip()
        if inviter_name in ("跑者", "微信用户", "微信跑者"):
            inviter_name = ""

    qr_info = _generate_club_invite_wxacode(
        club_id=club["id"],
        invite_code=invite_code,
        inviter_uid=user_id,
        env_version=env_version or "release",
    )

    query_parts = [f"invite_club_id={club['id']}"]
    if invite_code:
        query_parts.append(f"invite_code={invite_code}")
    if user_id:
        query_parts.append(f"inviter_uid={user_id}")
    web_invite_url = f"https://rgm.vanpower.net/dashboard/team?{'&'.join(query_parts)}"

    inviter_prefix = f"【{inviter_name}】" if inviter_name else "跑友"
    org_line = f"\n🏛️ 所属大群：{org_name}" if org_name else ""
    code_line = (
        f"\n🔑 专属入团邀请码：{invite_code}"
        if invite_code
        else "\n🟢 入团方式：免邀请码 · 一键加入"
    )
    share_text = (
        f"🏃‍♂️ {inviter_prefix}诚邀你加入【{club['name']}】跑团！"
        f"{org_line}\n"
        f"📍 所在城市：{club.get('city') or '上海'}（已有 {len(members)} 位跑友同行）"
        f"{code_line}\n"
        f"👉 加入方式：\n"
        f"1️⃣ 微信打开「万跑跑团助手」小程序，在跑团页输入邀请码{f'【{invite_code}】' if invite_code else '一键入团'}；\n"
        f"2️⃣ 或直接点击下方链接一键加入：\n{web_invite_url}"
    )

    return {
        "club_id": club["id"],
        "name": club["name"],
        "logo_url": club.get("logo_url"),
        "city": club.get("city") or "上海",
        "description": club.get("description") or "精英跑者联盟，追求 PB 突破与健康长久奔跑。",
        "member_count": len(members),
        "join_mode": club.get("join_mode") or "free",
        "invite_code": invite_code,
        "org_id": org_id,
        "org_name": org_name,
        "inviter_uid": user_id or "",
        "inviter_name": inviter_name,
        "qrcode_url": qr_info["qrcode_url"],
        "qrcode_base64": qr_info["qrcode_base64"],
        "web_invite_url": web_invite_url,
        "share_text": share_text,
    }


@router.post("/{club_id}/join-mode")
def update_club_join_mode(club_id: str, req: UpdateJoinModeRequest):
    """Allows club owner (团长) or coach (教练) to view/switch between 'free' and 'invite', and customize invite_code."""
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")

    if req.join_mode and req.join_mode not in ("free", "invite"):
        raise HTTPException(status_code=400, detail="入团规则仅支持 'free' (自由入团) 或 'invite' (凭专属邀请码入团)")

    # Permission check: must be owner or coach
    members = LocalStore.get_club_members(club_id)
    is_authorized = (club.get("owner_id") == req.operator_uid) or any(
        m["user_id"] == req.operator_uid and m["role"] in ("owner", "coach") for m in members
    )

    if not is_authorized:
        raise HTTPException(status_code=403, detail="只有跑团团长和教练有权修改本跑团的入团规则与邀请码！")

    update_data = {}
    if req.join_mode:
        update_data["join_mode"] = req.join_mode
    if req.invite_code is not None:
        clean_code = req.invite_code.strip().upper()
        if not clean_code:
            raise HTTPException(status_code=400, detail="跑团专属邀请码不能为空！")
        if len(clean_code) < 3 or len(clean_code) > 12:
            raise HTTPException(status_code=400, detail="邀请码长度建议为 3-12 位英文或数字！")
        update_data["invite_code"] = clean_code

    try:
        updated = LocalStore.update_club(club_id, update_data)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    current_mode = req.join_mode or club.get("join_mode") or "free"
    mode_text = "自由入团（免邀请码）" if current_mode == "free" else "凭专属邀请码入团"
    return {
        "success": True,
        "message": f"入团规则与专属邀请码已更新成功！当前状态：【{mode_text}】",
        "club": updated
    }


@router.patch("/{club_id}/join-rule")
def update_club_join_rule_alias(club_id: str, req: UpdateJoinModeRequest):
    """Alias for updating club join mode and custom invite code."""
    return update_club_join_mode(club_id, req)


@router.get("/{club_id}/dashboard")
def get_club_dashboard(
    club_id: str,
    operator_uid: Optional[str] = None,
    user_id: Optional[str] = None,
    request: Request = None
):
    """Returns club overview metrics for President, Coaches and Members (invite_code visible only to owner and coaches)."""
    eff_uid = user_id or operator_uid or (request.headers.get("x-user-id") if request else None)
    if club_id in ("unaffiliated", "free_runners", "none"):
        info = LocalStore.get_unaffiliated_users_status(viewer_uid=eff_uid)
        m_list = info.get("members", [])
        total_km = round(sum(float(m.get("month_km") or 0.0) for m in m_list), 1)
        return {
            "club": {
                "id": "unaffiliated",
                "name": f"未入团跑友({len(m_list)})",
                "description": "尚未加入任何跑团的注册跑友全局名册",
                "owner_id": eff_uid or "admin",
                "status": "active",
                "city": "全局",
            },
            "metrics": {
                "members_count": len(m_list),
                "coaches_count": 0,
                "total_month_km": total_km,
                "active_events_count": 0,
            },
            "events": [],
        }
    if eff_uid:
        try:
            LocalStore.validate_sub_club_access(club_id, eff_uid)
        except ValueError as e:
            raise HTTPException(status_code=403, detail=str(e))

    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")

    club = dict(club)
    is_owner_or_coach = False
    if eff_uid:
        if club.get("owner_id") == eff_uid:
            is_owner_or_coach = True
        else:
            members = LocalStore.get_club_members(club_id)
            is_owner_or_coach = any(m["user_id"] == eff_uid and m["role"] in ("owner", "coach") for m in members)

    if not is_owner_or_coach:
        club.pop("invite_code", None)

    members = LocalStore.get_club_members(club_id)
    events = LocalStore.get_club_events(club_id)
    today = date.today()
    month_start = date(today.year, today.month, 1).isoformat()

    total_month_m = sum(LocalStore.get_month_distance_meters(m["user_id"], month_start) for m in members)
    total_month_km = round(total_month_m / 1000.0, 1)
    coaches_count = sum(1 for m in members if m["role"] in ("owner", "coach"))

    return {
        "club": club,
        "metrics": {
            "members_count": len(members),
            "coaches_count": coaches_count,
            "total_month_km": total_month_km,
            "active_events_count": len(events)
        },
        "events": events
    }


@router.get("/{club_id}/members")
def get_club_members_list(
    club_id: str,
    user_id: Optional[str] = None,
    operator_uid: Optional[str] = None,
    request: Request = None
):
    """Returns all members of the club with their roles."""
    eff_uid = user_id or operator_uid or (request.headers.get("x-user-id") if request else None)
    if club_id in ("unaffiliated", "free_runners", "none"):
        info = LocalStore.get_unaffiliated_users_status(viewer_uid=eff_uid)
        return {"members": info.get("members", [])}
    if eff_uid:
        try:
            LocalStore.validate_sub_club_access(club_id, eff_uid)
        except ValueError as e:
            raise HTTPException(status_code=403, detail=str(e))

    members = LocalStore.get_club_members(club_id)
    return {"members": members}


class RemindMemberSetupRequest(BaseModel):
    operator_uid: str
    target_uid: str


@router.get("/unaffiliated-members")
def get_unaffiliated_users_status_endpoint(
    user_id: Optional[str] = None,
    viewer_uid: Optional[str] = None,
    operator_uid: Optional[str] = None,
    request: Request = None,
):
    """
    Returns users who have NOT joined any running club, together with their basic status
    (registration time, watch binding, goal setting, monthly progress).
    Accessible by Platform Super Admin and by unaffiliated users themselves.
    """
    eff_uid = (
        viewer_uid
        or user_id
        or operator_uid
        or (request.headers.get("x-user-id") if request else None)
        or (getattr(getattr(request, "state", None), "user_id", None) if request else None)
    )
    if eff_uid:
        is_super = LocalStore.is_super_admin(eff_uid)
        if not is_super:
            joined_clubs = LocalStore.get_user_clubs(eff_uid)
            if len(joined_clubs) > 0:
                raise HTTPException(
                    status_code=403,
                    detail="仅平台超级管理员或未加入跑团的跑友可查看未入团跑友名单",
                )
    return LocalStore.get_unaffiliated_users_status(viewer_uid=eff_uid)


@router.post("/unaffiliated/remind-member")
def remind_unaffiliated_user_setup_endpoint(req: RemindMemberSetupRequest):
    """Allows Platform Super Admin to send a 1-tap reminder notification to an unaffiliated user."""
    try:
        return LocalStore.remind_unaffiliated_user_setup(req.operator_uid, req.target_uid)
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.get("/runner-basic-status/{target_uid}")
def get_runner_basic_status_endpoint(
    target_uid: str,
    viewer_uid: Optional[str] = None,
    user_id: Optional[str] = None,
    request: Request = None,
):
    """
    Returns a runner's basic status (watch binding, goal setting, monthly km & progress)
    without exposing specific workout records or GPS tracks.
    Safe for cross-club and unaffiliated peer viewing.
    """
    eff_viewer = (
        viewer_uid
        or user_id
        or (request.headers.get("x-user-id") if request else None)
        or (getattr(getattr(request, "state", None), "user_id", None) if request else None)
    )
    try:
        return LocalStore.get_runner_basic_status(target_uid, viewer_uid=eff_viewer)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


@router.get("/{club_id}/new-members")
def get_club_new_members_status_endpoint(
    club_id: str,
    user_id: Optional[str] = None,
    operator_uid: Optional[str] = None,
    request: Request = None,
):
    """Returns club members ordered by join date (newest first) with watch binding and goal setting status."""
    eff_uid = (
        user_id
        or operator_uid
        or (request.headers.get("x-user-id") if request else None)
        or (getattr(getattr(request, "state", None), "user_id", None) if request else None)
    )
    if club_id in ("unaffiliated", "free_runners", "none"):
        if eff_uid and not LocalStore.is_super_admin(eff_uid) and len(LocalStore.get_user_clubs(eff_uid)) > 0:
            raise HTTPException(status_code=403, detail="仅平台超级管理员或未加入跑团的跑友可查看未入团跑友名单")
        return LocalStore.get_unaffiliated_users_status(viewer_uid=eff_uid)

    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")
    if eff_uid and not LocalStore.is_super_admin(eff_uid):
        try:
            LocalStore.validate_sub_club_access(club_id, eff_uid)
        except ValueError as e:
            raise HTTPException(status_code=403, detail=str(e))
    return LocalStore.get_club_new_members_status(club_id)


@router.post("/{club_id}/remind-member")
def remind_club_member_setup_endpoint(club_id: str, req: RemindMemberSetupRequest):
    """Allows Club Owner or Coach to send a 1-tap reminder notification to a member to bind watch / set goals."""
    try:
        return LocalStore.remind_club_member_setup(club_id, req.operator_uid, req.target_uid)
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.post("/{club_id}/role")
def update_member_role(club_id: str, req: UpdateMemberRoleRequest, request: Request = None):
    """Allows Club Owner (or platform Super Admin) to appoint or revoke Coach / Admin role."""
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")
    if club.get("status") in ("paused", "locked"):
        status_text = "暂停" if club.get("status") == "paused" else "锁定"
        raise HTTPException(status_code=400, detail=f"该跑团当前处于【{status_text}】状态，禁止调整成员角色！")

    allowed_roles = {"owner", "coach", "admin", "member"}
    if req.role not in allowed_roles:
        raise HTTPException(status_code=400, detail="无效的成员角色类型")

    token_uid = getattr(request.state, "user_id", None) if request else None
    token_is_sa = bool(getattr(request.state, "is_super_admin", False)) if request else False
    if settings.ENVIRONMENT.lower() == "production" and not token_uid and not token_is_sa:
        raise HTTPException(status_code=401, detail="安全拦截：请先登录后再执行角色管理操作")

    raw_op_uid = (req.operator_uid or "").strip()
    if token_uid and not token_is_sa and not LocalStore.is_super_admin(token_uid):
        if raw_op_uid and LocalStore.resolve_user_id(raw_op_uid) != LocalStore.resolve_user_id(token_uid):
            raise HTTPException(status_code=403, detail="安全拦截：操作人身份与当前登录会话不匹配")
        effective_op = LocalStore.resolve_user_id(token_uid)
    else:
        effective_op = LocalStore.resolve_user_id(raw_op_uid or token_uid or "")

    members = LocalStore.get_club_members(club_id)
    op_member = next(
        (m for m in members if LocalStore.resolve_user_id(m["user_id"]) == effective_op),
        None,
    )
    is_club_owner = bool(
        (op_member and op_member.get("role") == "owner")
        or (effective_op and LocalStore.resolve_user_id(str(club.get("owner_id") or "")) == effective_op)
    )
    if not (is_club_owner or token_is_sa or LocalStore.is_super_admin(effective_op)):
        raise HTTPException(status_code=403, detail="权限不足：仅跑团团长或平台超级管理员可调整成员角色")

    LocalStore.update_member_role(club_id, req.target_uid, req.role)
    return {"message": f"已成功将该成员角色更新为【{req.role}】！"}


@router.post("/{club_id}/member-group")
def update_member_training_group_endpoint(club_id: str, req: UpdateMemberTrainingGroupRequest):
    """Allows Club Owner or Coach / Assistant Coach to set a member's persistent training group (e.g. A组~E组 or 男组/女组)."""
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")
    LocalStore.update_member_training_group(club_id, req.target_uid, req.training_group)
    grp_label = req.training_group or "未分组"
    return {
        "success": True,
        "training_group": req.training_group,
        "message": f"已将该队员的常驻训练组别设为【{grp_label}】！",
    }


class LeaveClubRequest(BaseModel):
    user_id: str


@router.post("/{club_id}/leave")
def leave_club_endpoint(club_id: str, req: LeaveClubRequest, request: Request = None):
    """Allows a club member to voluntarily leave a running club (personal running records 100% preserved)."""
    eff_uid = (
        req.user_id
        or (request.headers.get("x-user-id") if request else None)
        or (getattr(getattr(request, "state", None), "user_id", None) if request else None)
    )
    if not eff_uid:
        raise HTTPException(status_code=400, detail="缺少用户ID")
    try:
        res = LocalStore.remove_club_member(
            club_id=club_id,
            user_id=eff_uid,
            operator_uid=eff_uid,
            is_self_leave=True,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    return {
        "success": True,
        "message": f"您已成功退出跑团【{res.get('club_name', '')}】，个人历史运动数据与档案已 100% 完整保留！",
        **res,
    }


@router.delete("/{club_id}/members/{target_uid}")
def remove_member(
    club_id: str,
    target_uid: str,
    operator_uid: Optional[str] = None,
    user_id: Optional[str] = None,
    request: Request = None,
):
    """Allows Club Owner or Super Admin to remove a member from the club (or a member to remove themselves)."""
    eff_op = (
        operator_uid
        or user_id
        or (request.headers.get("x-user-id") if request else None)
        or (getattr(getattr(request, "state", None), "user_id", None) if request else None)
    )
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")
    try:
        is_self = bool(eff_op and LocalStore.resolve_user_id(eff_op) == LocalStore.resolve_user_id(target_uid))
        res = LocalStore.remove_club_member(
            club_id=club_id,
            user_id=target_uid,
            operator_uid=eff_op,
            is_self_leave=is_self,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    msg = (
        f"您已退出跑团【{res.get('club_name', '')}】"
        if is_self
        else f"已将【{res.get('display_name', '该成员')}】移出跑团【{res.get('club_name', '')}】"
    )
    return {"success": True, "message": msg, **res}


@router.get("/{club_id}/coach-cockpit")
def get_coach_cockpit(
    club_id: str,
    coach_uid: Optional[str] = None,
    user_id: Optional[str] = None,
    operator_uid: Optional[str] = None,
    sort_order: str = Query("danger_first", description="TSB状态排序: danger_first (预警优先) 或 peak_first (巅峰优先)"),
    request: Request = None
):
    """
    Returns Coach Cockpit:全队学员 TSB/HRV 负荷与红黄绿状态罗盘，支持以TSB状态排序.
    """
    eff_uid = user_id or coach_uid or operator_uid or (request.headers.get("x-user-id") if request else None)
    if club_id in ("unaffiliated", "free_runners", "none"):
        return {
            "summary": {
                "total_students": 0,
                "peak_count": 0,
                "optimal_count": 0,
                "tired_count": 0,
                "danger_count": 0,
                "plans_published_count": 0,
                "plans_draft_count": 0,
                "plans_none_count": 0,
                "avg_week_compliance": 0.0,
            },
            "students": [],
        }
    if eff_uid:
        try:
            LocalStore.validate_sub_club_access(club_id, eff_uid)
        except ValueError as e:
            raise HTTPException(status_code=403, detail=str(e))

    students = LocalStore.get_coach_students_metrics(club_id, coach_uid, sort_order=sort_order)
    
    # Aggregate status count
    peak_count = sum(1 for s in students if s["status_level"] == "peak")
    optimal_count = sum(1 for s in students if s["status_level"] == "optimal")
    tired_count = sum(1 for s in students if s["status_level"] == "tired")
    danger_count = sum(1 for s in students if s["status_level"] == "danger")

    plans_published_count = sum(1 for s in students if (s.get("plan_info") or {}).get("plan_state") == "published")
    plans_draft_count = sum(1 for s in students if (s.get("plan_info") or {}).get("plan_state") in ("draft_pending", "self_active"))
    plans_none_count = sum(1 for s in students if (s.get("plan_info") or {}).get("plan_state") == "none")
    active_compliances = [
        float(((s.get("plan_info") or {}).get("week_execution") or {}).get("compliance_rate") or 0.0)
        for s in students
        if (s.get("plan_info") or {}).get("week_execution") is not None
    ]
    avg_week_compliance = round(sum(active_compliances) / len(active_compliances), 1) if active_compliances else 0.0

    return {
        "summary": {
            "total_students": len(students),
            "peak_count": peak_count,
            "optimal_count": optimal_count,
            "tired_count": tired_count,
            "danger_count": danger_count,
            "plans_published_count": plans_published_count,
            "plans_draft_count": plans_draft_count,
            "plans_none_count": plans_none_count,
            "avg_week_compliance": avg_week_compliance
        },
        "students": students
    }


@router.get("/{club_id}/events")
def get_club_events(
    club_id: str,
    user_id: Optional[str] = None,
    include_archived: bool = False,
    request: Request = None
):
    """Returns active club challenges and group run events (completed events are auto-archived and excluded by default)."""
    eff_uid = user_id or (request.headers.get("x-user-id") if request else None)
    if club_id in ("unaffiliated", "free_runners", "none"):
        return {"events": []}
    if eff_uid:
        try:
            LocalStore.validate_sub_club_access(club_id, eff_uid)
        except ValueError as e:
            raise HTTPException(status_code=403, detail=str(e))

    events = LocalStore.get_club_events(club_id, user_id=eff_uid, include_archived=include_archived)
    return {"events": events}


class SaveClubEventTemplateRequest(BaseModel):
    operator_uid: Optional[str] = None
    id: Optional[str] = None
    name: str
    title: str
    event_type: Optional[str] = "group_run"
    target_km: Optional[float] = 15.0
    default_weekday: Optional[int] = 0
    meet_time_hm: Optional[str] = "06:30"
    location: Optional[str] = ""
    location_detail: Optional[str] = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    pace_requirement: Optional[str] = ""
    rules: Optional[str] = ""


@router.get("/{club_id}/event-templates")
def get_club_event_templates_endpoint(club_id: str):
    """Returns built-in + custom group run activity templates for this club."""
    club = LocalStore.get_club(club_id)
    if not club:
        return {"custom_templates": []}
    settings = club.get("settings") or {}
    if isinstance(settings, str):
        try:
            settings = json.loads(settings)
        except Exception:
            settings = {}
    custom_list = settings.get("group_run_templates") if isinstance(settings, dict) else []
    if not isinstance(custom_list, list):
        custom_list = []
    return {"custom_templates": custom_list}


@router.post("/{club_id}/event-templates")
def save_club_event_template_endpoint(club_id: str, req: SaveClubEventTemplateRequest):
    """Saves a custom group run activity template to the club's settings."""
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")
    settings = club.get("settings") or {}
    if isinstance(settings, str):
        try:
            settings = json.loads(settings)
        except Exception:
            settings = {}
    if not isinstance(settings, dict):
        settings = {}
    custom_list = settings.get("group_run_templates") or []
    if not isinstance(custom_list, list):
        custom_list = []

    tpl_id = req.id or f"ctpl_{int(datetime.utcnow().timestamp())}"
    new_item = {
        "id": tpl_id,
        "name": req.name.strip() or req.title.strip()[:8],
        "is_custom": True,
        "title": req.title.strip(),
        "event_type": req.event_type or "group_run",
        "target_km": float(req.target_km or 15.0),
        "default_weekday": int(req.default_weekday if req.default_weekday is not None else 0),
        "meet_time_hm": (req.meet_time_hm or "06:30").strip(),
        "location": (req.location or "").strip(),
        "location_detail": (req.location_detail or "").strip(),
        "latitude": req.latitude,
        "longitude": req.longitude,
        "pace_requirement": (req.pace_requirement or "").strip(),
        "rules": (req.rules or "").strip(),
    }
    custom_list = [t for t in custom_list if isinstance(t, dict) and t.get("id") != tpl_id and t.get("name") != new_item["name"]]
    custom_list.insert(0, new_item)
    settings["group_run_templates"] = custom_list[:20]
    LocalStore.update_club(club_id, {"settings": json.dumps(settings, ensure_ascii=False)})
    return {"message": "已存为跑团约跑模版 ✓", "template": new_item, "custom_templates": settings["group_run_templates"]}


@router.delete("/{club_id}/event-templates/{template_id}")
def delete_club_event_template_endpoint(club_id: str, template_id: str):
    """Deletes a custom group run activity template from the club's settings."""
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")
    settings = club.get("settings") or {}
    if isinstance(settings, str):
        try:
            settings = json.loads(settings)
        except Exception:
            settings = {}
    if not isinstance(settings, dict):
        settings = {}
    custom_list = settings.get("group_run_templates") or []
    if isinstance(custom_list, list):
        custom_list = [t for t in custom_list if isinstance(t, dict) and t.get("id") != template_id]
    settings["group_run_templates"] = custom_list
    LocalStore.update_club(club_id, {"settings": json.dumps(settings, ensure_ascii=False)})
    return {"message": "模版已删除", "custom_templates": custom_list}


@router.post("/{club_id}/events")
def create_club_event(club_id: str, req: CreateClubEventRequest):
    """Allows Club Owner, Coach, or Member to create a group run or distance challenge."""
    if req.operator_uid:
        try:
            LocalStore.validate_sub_club_access(club_id, req.operator_uid)
        except ValueError as e:
            raise HTTPException(status_code=403, detail=str(e))

    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")
    if club.get("status") == "paused":
        raise HTTPException(status_code=400, detail="该跑团当前处于暂停状态，暂停发布新活动与消息！")

    event_id = LocalStore.create_club_event(club_id, {
        "title": req.title,
        "event_type": req.event_type or "group_run",
        "start_date": req.start_date,
        "end_date": req.end_date,
        "meet_time": req.meet_time,
        "location": req.location,
        "location_detail": req.location_detail,
        "latitude": req.latitude,
        "longitude": req.longitude,
        "cover_image": req.cover_image,
        "target_km": req.target_km,
        "pace_requirement": req.pace_requirement,
        "max_participants": req.max_participants,
        "rules": req.rules,
        "operator_uid": req.operator_uid,
        "creator_id": req.operator_uid,
        "repeat_rule": req.repeat_rule or "none",
        "repeat_weeks": req.repeat_weeks or 1,
        "visibility_mode": req.visibility_mode or "registered_only",
        "recap_note": req.recap_note or ""
    })
    msg = f"约跑【{req.title}】发布成功！"
    if req.repeat_rule == "weekly" and (req.repeat_weeks or 1) > 1:
        msg = f"已成功创建未来 {req.repeat_weeks} 周的例跑【{req.title}】！"
    return {"message": msg, "event_id": event_id}


@router.get("/{club_id}/events/{event_id}")
def get_club_event_detail_endpoint(
    club_id: str,
    event_id: str,
    user_id: Optional[str] = None,
    request: Request = None
):
    """Returns full group run detail, participant roster with running metrics, MVPs, and social comments."""
    eff_uid = user_id or (request.headers.get("x-user-id") if request else None)
    try:
        ev = LocalStore.get_club_event_detail(club_id, event_id, user_id=eff_uid)
        return {"event": ev}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Get club event detail error: {e}")
        raise HTTPException(status_code=500, detail="获取约跑详情失败")


@router.get("/{club_id}/events/{event_id}/qrcode")
def get_club_event_qrcode_endpoint(club_id: str, event_id: str, env_version: Optional[str] = "release"):
    """Generates and caches an official WeChat Mini Program QR code (wxacode) + club/event images (base64) for the group run poster."""
    import os
    import base64
    import hashlib
    import requests as ext_req
    from utils.wechat import wechat_client

    eff_env = env_version if env_version in ("release", "trial", "develop") else "release"
    safe_eid = "".join(c for c in event_id if c.isalnum() or c in ("_", "-"))[:40]
    filename = f"wxacode_v2_{eff_env}_{safe_eid}.jpg"
    avatar_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "avatars")
    os.makedirs(avatar_dir, exist_ok=True)
    file_path = os.path.join(avatar_dir, filename)

    ev = None
    eff_club_id = club_id if (club_id and club_id != "auto") else "club_fudan_gobi_main"
    club_code = ""
    try:
        ev = LocalStore.get_club_event_detail(club_id, event_id)
        if ev and ev.get("club_id"):
            eff_club_id = ev["club_id"]
        club_obj = LocalStore.get_club(eff_club_id)
        if club_obj:
            club_code = (club_obj.get("invite_code") or "").strip()
    except Exception:
        pass

    qr_path = f"pages/team/team?club_id={eff_club_id}&action=join_club&invite_code={club_code}&event_id={event_id}"

    if not os.path.exists(file_path) or os.path.getsize(file_path) < 500:
        img_bytes = wechat_client.get_wxacode_by_path(
            path=qr_path,
            width=280,
            env_version=eff_env
        )
        if not img_bytes:
            img_bytes = wechat_client.get_wxacode_unlimit(
                scene=f"e={event_id}"[:32],
                page="pages/team/team",
                width=280,
                env_version=eff_env
            )
        if img_bytes:
            with open(file_path, "wb") as f:
                f.write(img_bytes)

    qrcode_b64 = ""
    qrcode_url = ""
    if os.path.exists(file_path) and os.path.getsize(file_path) >= 500:
        qrcode_url = f"https://rgm.vanpower.net/api/avatars/{filename}"
        with open(file_path, "rb") as f:
            qrcode_b64 = base64.b64encode(f.read()).decode("ascii")

    race_photos_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "race_photos")

    def _resolve_img_b64(img_url: Optional[str]) -> str:
        if not img_url:
            return ""
        u = img_url.strip()
        if "/api/avatars/" in u:
            fname = os.path.basename(u.split("?")[0])
            local_p = os.path.join(avatar_dir, fname)
            if os.path.exists(local_p) and os.path.getsize(local_p) > 200:
                with open(local_p, "rb") as f:
                    return base64.b64encode(f.read()).decode("ascii")
        if "/api/race-photos/" in u:
            fname = os.path.basename(u.split("?")[0])
            local_rp = os.path.join(race_photos_dir, fname)
            if os.path.exists(local_rp) and os.path.getsize(local_rp) > 200:
                with open(local_rp, "rb") as f:
                    return base64.b64encode(f.read()).decode("ascii")
        if u.startswith("http") and is_safe_external_url(u):
            cache_name = f"poster_cache_{hashlib.md5(u.encode('utf-8')).hexdigest()[:16]}.jpg"
            cache_p = os.path.join(avatar_dir, cache_name)
            if not os.path.exists(cache_p) or os.path.getsize(cache_p) < 200:
                try:
                    r = ext_req.get(u, timeout=6, allow_redirects=False)
                    if r.status_code == 200 and 200 < len(r.content) <= 10 * 1024 * 1024:
                        with open(cache_p, "wb") as f:
                            f.write(r.content)
                except Exception:
                    pass
            if os.path.exists(cache_p) and os.path.getsize(cache_p) > 200:
                with open(cache_p, "rb") as f:
                    return base64.b64encode(f.read()).decode("ascii")
        return ""

    cover_b64 = ""
    logo_b64 = ""
    try:
        if not ev:
            ev = LocalStore.get_club_event_detail(club_id, event_id)
        logo_b64 = _resolve_img_b64(ev.get("club_logo"))
        raw_cover = str(ev.get("cover_image") or "")
        if not raw_cover or "images.unsplash.com" in raw_cover:
            cover_b64 = logo_b64 or _resolve_img_b64(raw_cover)
        else:
            cover_b64 = _resolve_img_b64(raw_cover) or logo_b64
    except Exception:
        pass

    return {
        "qrcode_url": qrcode_url,
        "qrcode_base64": qrcode_b64,
        "cover_base64": cover_b64,
        "logo_base64": logo_b64,
        "path": qr_path,
        "scene": f"e={event_id}"[:32]
    }


@router.put("/{club_id}/events/{event_id}")
def update_club_event_endpoint(club_id: str, event_id: str, req: CreateClubEventRequest):
    """Allows Club Owner, Coach, or Creator to edit an existing event."""
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")
    if club.get("status") == "paused":
        raise HTTPException(status_code=400, detail="该跑团当前处于暂停状态，暂停修改活动与消息！")

    LocalStore.update_club_event(club_id, event_id, {
        "title": req.title,
        "event_type": req.event_type or "group_run",
        "start_date": req.start_date,
        "end_date": req.end_date,
        "meet_time": req.meet_time,
        "location": req.location,
        "location_detail": req.location_detail,
        "latitude": req.latitude,
        "longitude": req.longitude,
        "cover_image": req.cover_image,
        "target_km": req.target_km,
        "pace_requirement": req.pace_requirement,
        "max_participants": req.max_participants,
        "rules": req.rules,
        "repeat_rule": req.repeat_rule,
        "visibility_mode": req.visibility_mode,
        "recap_note": req.recap_note
    })
    return {"message": f"约跑【{req.title}】更新成功！"}


@router.post("/{club_id}/events/{event_id}/archive")
def archive_club_event_endpoint(club_id: str, event_id: str, operator_uid: Optional[str] = None):
    """Archives a completed group run or event so it is hidden from active lists without deleting battle-report history."""
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")
    LocalStore.archive_club_event(club_id, event_id)
    return {"success": True, "message": "约跑活动已归档"}


@router.delete("/{club_id}/events/{event_id}")
def delete_club_event_endpoint(club_id: str, event_id: str, operator_uid: Optional[str] = None):
    """Allows Club Owner, Coach, or Creator to delete an event."""
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")
    if club.get("status") == "paused":
        raise HTTPException(status_code=400, detail="该跑团当前处于暂停状态，暂停操作活动！")

    LocalStore.delete_club_event(club_id, event_id)
    return {"message": "活动已成功删除"}


@router.post("/{club_id}/events/{event_id}/join")
def join_club_event_endpoint(club_id: str, event_id: str, req: JoinEventRequest):
    """Allows a runner (member or newcomer) to join a group run event, activate account, and auto-join the club."""
    try:
        res = LocalStore.join_club_event(
            club_id,
            event_id,
            req.user_id,
            pace_group=req.pace_group,
            runner_role=req.runner_role,
            checkin_note=req.checkin_note,
            display_name=req.display_name,
            avatar_url=req.avatar_url,
            phone=req.phone,
            auto_join_club=True if req.auto_join_club is None else bool(req.auto_join_club),
            join_event=True if req.join_event is None else bool(req.join_event),
            inviter_uid=req.inviter_uid,
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Join group run error: {e}")
        raise HTTPException(status_code=500, detail="报名失败，请稍后重试")


@router.post("/{club_id}/events/{event_id}/leave")
def leave_club_event_endpoint(club_id: str, event_id: str, req: JoinEventRequest):
    """Allows a club member to cancel participation in a group run."""
    try:
        res = LocalStore.leave_club_event(club_id, event_id, req.user_id)
        return res
    except Exception as e:
        logger.error(f"Leave group run error: {e}")
        raise HTTPException(status_code=500, detail="取消失败，请稍后重试")


@router.post("/{club_id}/events/{event_id}/checkin")
def update_event_participant_checkin_endpoint(
    club_id: str,
    event_id: str,
    req: UpdateParticipantCheckinRequest
):
    """Allows a participant to update their pace group, social role, check-in note, or bind running stats."""
    try:
        return LocalStore.update_event_participant_checkin(club_id, event_id, req.user_id, req.dict())
    except Exception as e:
        logger.error(f"Update participant checkin error: {e}")
        raise HTTPException(status_code=500, detail="更新约跑打卡失败")


@router.post("/{club_id}/events/{event_id}/visibility")
def update_club_event_visibility_endpoint(
    club_id: str,
    event_id: str,
    req: UpdateEventVisibilityRequest
):
    """Allows organizer / club owner / coach to configure whether the roster & stats page is open to registered participants only, club members, or public."""
    try:
        return LocalStore.update_club_event_visibility(
            club_id,
            event_id,
            req.operator_uid,
            req.visibility_mode,
            req.recap_note
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Update event visibility error: {e}")
        raise HTTPException(status_code=500, detail="更新开放设置失败")


@router.post("/{club_id}/events/{event_id}/highfive")
def highfive_event_participant_endpoint(
    club_id: str,
    event_id: str,
    req: HighfiveParticipantRequest
):
    """Gives a high-five (击掌) to a fellow group run participant."""
    try:
        return LocalStore.highfive_event_participant(
            club_id,
            event_id,
            req.target_user_id,
            req.from_user_id
        )
    except Exception as e:
        logger.error(f"Highfive participant error: {e}")
        raise HTTPException(status_code=500, detail="击掌失败，请稍后重试")


@router.post("/{club_id}/events/{event_id}/comments")
def add_event_comment_endpoint(
    club_id: str,
    event_id: str,
    req: AddEventCommentRequest
):
    """Posts a comment or post-run reflection to the group run social wall."""
    try:
        return LocalStore.add_event_comment(club_id, event_id, req.user_id, req.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Add event comment error: {e}")
        raise HTTPException(status_code=500, detail="发送留言失败")


@router.get("/upcoming-runs/{user_id}")
def get_user_upcoming_runs_endpoint(user_id: str):
    """Returns upcoming group runs that the user has joined."""
    runs = LocalStore.get_user_upcoming_runs(user_id)
    return {"upcoming_runs": runs}



@router.get("/{club_id}/leaderboard")
def get_club_leaderboard(
    club_id: str,
    time_range: str = "month",
    user_id: Optional[str] = None,
    uid: Optional[str] = None,
    request: Request = None
):
    """Returns real-time running leaderboard for the club."""
    eff_uid = user_id or uid or (request.headers.get("x-user-id") if request else None)
    if club_id in ("unaffiliated", "free_runners", "none"):
        info = LocalStore.get_unaffiliated_users_status(viewer_uid=eff_uid)
        raw_members = sorted(
            info.get("members", []),
            key=lambda m: (float(m.get("month_km") or 0.0), int(m.get("total_runs_count") or 0)),
            reverse=True,
        )
        lb = []
        for idx, m in enumerate(raw_members, start=1):
            lb.append({
                "rank": idx,
                "user_id": m.get("user_id"),
                "display_name": m.get("display_name"),
                "avatar_url": m.get("avatar_url"),
                "role": "free_runner",
                "distance_km": float(m.get("month_km") or 0.0),
                "target_km": float(m.get("monthly_target_km") or 200.0),
                "completion_rate": float(m.get("completion_rate") or 0.0),
                "runs_count": int(m.get("total_runs_count") or 0),
            })
        return {"leaderboard": lb}
    if eff_uid:
        try:
            LocalStore.validate_sub_club_access(club_id, eff_uid)
        except ValueError as e:
            raise HTTPException(status_code=403, detail=str(e))

    leaderboard = LocalStore.get_club_leaderboard(club_id, time_range)
    return {"leaderboard": leaderboard}


class LikeActivityRequest(BaseModel):
    user_id: str

class PostCommentRequest(BaseModel):
    user_id: str
    content: str
    author_name: Optional[str] = None
    author_avatar: Optional[str] = None
    parent_id: Optional[str] = None
    reply_to_user_id: Optional[str] = None
    reply_to_name: Optional[str] = None


@router.post("/activities/{activity_id}/like")
def toggle_like_endpoint(activity_id: str, req: LikeActivityRequest):
    """Toggles like/kudos for an activity."""
    res = LocalStore.toggle_activity_like(activity_id, req.user_id)
    return res


@router.get("/activities/{activity_id}/social")
def get_activity_social_endpoint(activity_id: str, uid: Optional[str] = None):
    """Gets likes and comments for an activity."""
    return LocalStore.get_activity_social(activity_id, uid)


@router.post("/activities/{activity_id}/comments")
def post_comment_endpoint(activity_id: str, req: PostCommentRequest):
    """Posts a member comment or threaded reply on an activity following AI Coach critique."""
    canonical_uid = LocalStore.resolve_user_id(req.user_id)
    profile = LocalStore.get_profile(canonical_uid) or {}
    
    # Priority: registered display_name > client author_name (excluding raw email prefixes) > fallback
    profile_name = (profile.get("display_name") or "").strip()
    req_name = (req.author_name or "").strip()
    
    if profile_name and profile_name not in ("跑者", "微信跑者"):
        name = profile_name
    elif req_name and not ("@" in req_name):
        name = req_name
    else:
        name = profile_name or "跑友"

    profile_avatar = profile.get("avatar_url")
    avatar = profile_avatar or req.author_avatar or "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"
    
    cmt = LocalStore.add_activity_comment(
        activity_id=activity_id,
        user_id=canonical_uid,
        author_name=name,
        author_avatar=avatar,
        content=req.content,
        parent_id=req.parent_id,
        reply_to_user_id=req.reply_to_user_id,
        reply_to_name=req.reply_to_name,
    )
    return {"message": "评论已发布！", "comment": cmt}


@router.delete("/activities/{activity_id}/comments/{comment_id}")
def delete_comment_endpoint(activity_id: str, comment_id: str, user_id: Optional[str] = None):
    """Deletes a member comment."""
    success = LocalStore.delete_activity_comment(comment_id, user_id)
    return {"success": success, "message": "评论已删除"}


@router.get("/{club_id}/feed")
def get_club_activity_feed(
    club_id: str,
    uid: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    before_time: Optional[str] = None,
    scope: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    request: Request = None
):
    """
    Returns group workout feed for the club.
    - Default (when limit is None or scope="month"): Returns all check-in activities of the current month.
    - If limit & offset are explicitly provided for pagination: Returns paginated records.
    """
    eff_uid = user_id or uid or (request.headers.get("x-user-id") if request else None)
    if club_id in ("unaffiliated", "free_runners", "none"):
        today = LocalStore.get_beijing_today()
        return {
            "feed": [],
            "total": 0,
            "month_total": 0,
            "is_current_month": True,
            "current_month": f"{today.year}-{today.month:02d}",
            "month_label": f"{today.year}年{today.month}月",
            "has_more": False,
            "limit": 20,
            "offset": 0,
        }
    if eff_uid:
        try:
            LocalStore.validate_sub_club_access(club_id, eff_uid)
        except ValueError as e:
            raise HTTPException(status_code=403, detail=str(e))
    today = LocalStore.get_beijing_today()
    target_year = year or today.year
    target_month = month or today.month

    # If explicit pagination is requested (e.g. limit is given and scope != "month", or offset > 0, or before_time)
    if (limit is not None and scope != "month") or offset > 0 or before_time or scope == "all":
        eff_limit = limit or 20
        activities, total = LocalStore.get_club_recent_activities(
            club_id, current_uid=eff_uid, limit=eff_limit, offset=offset, before_time=before_time
        )
        return {
            "feed": activities,
            "total": total,
            "limit": eff_limit,
            "offset": offset,
            "has_more": (offset + len(activities)) < total,
            "scope": "paginated"
        }

    # Default: Return all activities for the current month
    month_acts, month_total, total_all = LocalStore.get_club_month_activities(
        club_id, current_uid=eff_uid, year=target_year, month=target_month
    )

    # Fallback if current month has 0 activities so far
    is_fallback = False
    if month_total == 0 and not before_time:
        fallback_acts, _ = LocalStore.get_club_recent_activities(
            club_id, current_uid=eff_uid, limit=20, offset=0
        )
        if fallback_acts:
            month_acts = fallback_acts
            is_fallback = True

    return {
        "feed": month_acts,
        "total": total_all,
        "month_total": month_total,
        "is_current_month": (target_year == today.year and target_month == today.month) and not is_fallback,
        "current_month": f"{target_year}-{target_month:02d}",
        "month_label": f"{target_year}年{target_month}月",
        "has_more": total_all > len(month_acts),
        "limit": len(month_acts),
        "offset": 0
    }


# Backward compatibility route for legacy client
@router.get("/leaderboard")
def legacy_leaderboard(team_id: Optional[str] = None):
    club_id = team_id or "club_rgm_flagship"
    board = LocalStore.get_club_leaderboard(club_id, "month")
    return board


@router.post("/upload-logo")
async def upload_team_logo(request: Request, file: UploadFile = File(...)):
    """Uploads a club logo image and returns the public URL."""
    if settings.ENVIRONMENT.lower() == "production" and not getattr(request.state, "user_id", None):
        raise HTTPException(status_code=401, detail="请先登录后再上传跑团 Logo")

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
        logger.error(f"[team] Failed to save club logo: {e}")
        raise HTTPException(status_code=500, detail="保存跑团Logo图片失败")

    logo_url = f"https://rgm.vanpower.net/api/avatars/{filename}"
    return {
        "success": True,
        "logo_url": logo_url,
        "url": logo_url,
        "message": "跑团 Logo 上传成功！"
    }


@router.get("/{club_id}/reports")
def get_club_periodic_report(
    club_id: str,
    operator_uid: str = Query(..., description="操作人用户ID，团长、教练或跑团成员均可查看/制作"),
    period_type: str = Query("week", pattern="^(week|month)$", description="统计周期: week 或 month"),
    year: Optional[int] = Query(None, description="年份，如 2026"),
    period_index: Optional[int] = Query(None, description="周序号(1-53)或月份(1-12)"),
    period_offset: Optional[int] = Query(None, description="周期偏移: 0=本周期, -1=上一周期"),
    trail_mode: str = Query("include", pattern="^(include|exclude_pace|exclude_all)$", description="越野跑统计口径: include(默认包含), exclude_pace(仅去除越野配速), exclude_all(去除越野跑量与配速)")
):
    """
    专属跑团周报与月报查询与制作。
    权限：跑团团长(Owner)、认证教练(Coach)以及成员均有权查看与制作。
    """
    if not operator_uid:
        raise HTTPException(status_code=400, detail="缺少 operator_uid 参数")

    # 校验权限：跑团成员、教练或团长均可查看与制作
    is_owner = LocalStore.is_club_owner(club_id, operator_uid)
    is_coach = LocalStore.is_club_coach(club_id, operator_uid)
    members = LocalStore.get_club_members(club_id)
    is_member = any(m["user_id"] == operator_uid for m in members)
    if not (is_owner or is_coach or is_member):
        raise HTTPException(
            status_code=403,
            detail="只有跑团成员和团长有权查看跑团周报/月报！"
        )

    try:
        report = LocalStore.get_club_periodic_report(
            club_id=club_id,
            period_type=period_type,
            year=year,
            period_index=period_index,
            period_offset=period_offset,
            trail_mode=trail_mode
        )
        return report
    except Exception as e:
        logger.error(f"[team] Error generating club report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成跑团报表失败: {str(e)}")


@router.get("/{club_id}/reports/export")
def export_club_periodic_report(
    club_id: str,
    operator_uid: str = Query(..., description="操作人用户ID，团长、教练或跑团成员均可导出"),
    period_type: str = Query("week", pattern="^(week|month)$", description="统计周期: week 或 month"),
    year: Optional[int] = Query(None, description="年份，如 2026"),
    period_index: Optional[int] = Query(None, description="周序号(1-53)或月份(1-12)"),
    period_offset: Optional[int] = Query(None, description="周期偏移: 0=本周期, -1=上一周期"),
    trail_mode: str = Query("include", pattern="^(include|exclude_pace|exclude_all)$", description="越野跑统计口径: include(默认包含), exclude_pace(仅去除越野配速), exclude_all(去除越野跑量与配速)")
):
    """
    导出跑团周报与月报微信转发格式文本。
    权限：跑团团长(Owner)、认证教练(Coach)以及成员均有权导出。
    """
    if not operator_uid:
        raise HTTPException(status_code=400, detail="缺少 operator_uid 参数")

    # 校验权限：跑团成员、教练或团长均可导出
    is_owner = LocalStore.is_club_owner(club_id, operator_uid)
    is_coach = LocalStore.is_club_coach(club_id, operator_uid)
    members = LocalStore.get_club_members(club_id)
    is_member = any(m["user_id"] == operator_uid for m in members)
    if not (is_owner or is_coach or is_member):
        raise HTTPException(
            status_code=403,
            detail="只有跑团成员和团长有权导出跑团周报/月报！"
        )

    try:
        report = LocalStore.get_club_periodic_report(
            club_id=club_id,
            period_type=period_type,
            year=year,
            period_index=period_index,
            period_offset=period_offset,
            trail_mode=trail_mode
        )
        forward_text = report.get("forward_text", "")
        club_name = report.get("club_name", club_id)
        display = report.get("period_display", period_type).replace(" ", "_")
        filename = f"{club_name}_{display}_战报.txt"

        import urllib.parse
        encoded_filename = urllib.parse.quote(filename)

        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "Content-Type": "text/plain; charset=utf-8"
        }
        return PlainTextResponse(content=forward_text, headers=headers)
    except Exception as e:
        logger.error(f"[team] Error exporting club report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导出跑团报表失败: {str(e)}")


@router.post("/{club_id}/status")
def set_club_status_by_owner(club_id: str, req: SetClubStatusOwnerRequest):
    """Allows Club Owner (团长) to switch club status between 'active', 'paused', 'locked'."""
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")

    if not LocalStore.is_club_owner(club_id, req.operator_uid):
        raise HTTPException(status_code=403, detail="只有跑团团长有权调整跑团运行状态！")

    try:
        updated = LocalStore.set_club_status(club_id, req.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    status_names = {"active": "正常运行", "paused": "暂停运行", "locked": "锁定归档"}
    status_text = status_names.get(req.status, req.status)
    return {"message": f"跑团【{club['name']}】状态已成功更新为【{status_text}】！", "club": updated}


@router.delete("/{club_id}")
def dissolve_club_by_owner(club_id: str, operator_uid: str = Query(..., description="团长用户ID")):
    """
    Allows Club Owner (团长) to dissolve and delete the club.
    Deletes club record and memberships, but guarantees
    members' personal accounts, profiles, and workout history are completely preserved.
    """
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")

    if not LocalStore.is_club_owner(club_id, operator_uid):
        raise HTTPException(status_code=403, detail="只有跑团团长有权解散并删除本跑团！")

    success = LocalStore.delete_club(club_id)
    if not success:
        raise HTTPException(status_code=500, detail="解散跑团失败")

    return {
        "success": True,
        "message": f"跑团【{club['name']}】已成功解散并清理，全体队员的个人历史运动数据与档案已完整保留！"
    }


@router.put("/{club_id}/info")
def update_club_info_by_owner(club_id: str, req: UpdateClubInfoOwnerRequest):
    """Allows Club Owner (团长) or Coach (教练) to update basic club profile (name, city, description, logo_url)."""
    club = LocalStore.get_club(club_id)
    if not club:
        raise HTTPException(status_code=404, detail="跑团不存在")

    is_owner = LocalStore.is_club_owner(club_id, req.operator_uid)
    is_coach = LocalStore.is_club_coach(club_id, req.operator_uid)
    if not (is_owner or is_coach):
        raise HTTPException(status_code=403, detail="只有跑团团长和教练有权修改跑团基本资料！")

    update_data: Dict[str, Any] = {}
    if req.name is not None:
        clean_name = req.name.strip()
        if not clean_name:
            raise HTTPException(status_code=400, detail="跑团名称不能为空")
        if len(clean_name) > 30:
            raise HTTPException(status_code=400, detail="跑团名称不能超过 30 个字符")
        update_data["name"] = clean_name
    if req.city is not None:
        update_data["city"] = req.city.strip() or "上海"
    if req.description is not None:
        update_data["description"] = req.description.strip()
    if req.logo_url is not None and req.logo_url.strip():
        update_data["logo_url"] = req.logo_url.strip()
    if req.org_id is not None:
        clean_org_id = req.org_id.strip()
        if clean_org_id in ("", "none", "independent"):
            update_data["org_id"] = None
        else:
            org_obj = LocalStore.get_organization(clean_org_id)
            if not org_obj:
                raise HTTPException(status_code=404, detail="所选归属大群不存在")
            st_org = LocalStore.check_org_member_status(clean_org_id, req.operator_uid)
            if not st_org.get("is_member") and org_obj.get("owner_id") != req.operator_uid and req.operator_uid not in ("admin", "super_admin"):
                raise HTTPException(status_code=403, detail="您尚未加入该大群，无法将跑团归属到该大群下")
            update_data["org_id"] = clean_org_id

    updated = LocalStore.update_club(club_id, update_data)
    return {
        "success": True,
        "message": f"跑团【{updated['name']}】基本资料已保存！",
        "club": updated,
    }


# ── Mentorship (师傅/徒弟 1对1 结对，1位师傅最多同时带3位队员，同大群内支持跨跑团) ──

class BindMentorshipRequest(BaseModel):
    mentor_uid: str
    mentee_uid: str
    org_id: Optional[str] = None
    club_id: Optional[str] = None
    operator_uid: Optional[str] = None
    via_invite: Optional[bool] = False


class UnbindMentorshipRequest(BaseModel):
    mentor_uid: str
    mentee_uid: str
    operator_uid: Optional[str] = None


@router.get("/mentorship/overview")
def get_mentorship_overview_endpoint(
    uid: Optional[str] = Query(None, description="当前用户ID"),
    user_id: Optional[str] = Query(None, description="当前用户ID别名"),
    org_id: Optional[str] = Query(None, description="可选的大群ID"),
    club_id: Optional[str] = Query(None, description="可选的当前跑团ID"),
    request: Request = None
):
    """
    获取当前用户的师徒结对概览：
    - my_mentor: 我的师傅（最多1位）
    - my_mentees: 我带教的队员（最多3位，含完整训练与休息恢复摘要）
    - candidates: 同大群（跨跑团）或同跑团可结对成员列表
    """
    eff_uid = (uid or user_id or (request.headers.get("x-user-id") if request else "") or "").strip()
    if not eff_uid:
        raise HTTPException(status_code=400, detail="缺少用户标识 uid")
    try:
        return LocalStore.get_mentorship_overview(eff_uid, org_id=org_id, club_id=club_id)
    except Exception as e:
        logger.error(f"[team] Error getting mentorship overview for {eff_uid}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取师徒结对信息失败: {str(e)}")


@router.post("/mentorship/bind")
def bind_mentorship_endpoint(req: BindMentorshipRequest):
    """
    建立 1对1 师徒关系（每位队员限 1 位师傅，每位师傅最多同时带 3 位队员，支持同大群内跨跑团）。
    """
    try:
        return LocalStore.bind_mentor_mentee(
            mentor_uid=req.mentor_uid,
            mentee_uid=req.mentee_uid,
            org_id=req.org_id,
            club_id=req.club_id,
            operator_uid=req.operator_uid,
            via_invite=bool(req.via_invite),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[team] Error binding mentorship: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"建立师徒关系失败: {str(e)}")


@router.post("/mentorship/unbind")
def unbind_mentorship_endpoint(req: UnbindMentorshipRequest):
    """
    解除 1对1 师徒关系。
    """
    try:
        return LocalStore.unbind_mentor_mentee(
            mentor_uid=req.mentor_uid,
            mentee_uid=req.mentee_uid,
            operator_uid=req.operator_uid,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[team] Error unbinding mentorship: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"解除师徒关系失败: {str(e)}")


@router.get("/mentorship/mentee/{mentee_uid}/detail")
def get_mentee_full_detail_endpoint(
    mentee_uid: str,
    viewer_uid: Optional[str] = Query(None, description="查看人（师傅或教练）UID"),
    uid: Optional[str] = Query(None, description="查看人UID别名"),
    request: Request = None
):
    """
    师傅（或教练）专属只读视图：获取结对队员的全部训练课表、近期全部跑步记录（含保密GPS轨迹）、
    以及近14天全部休息恢复生理数据（静息心率、HRV、睡眠质量、身体电量、恢复度）。
    """
    eff_viewer = (viewer_uid or uid or (request.headers.get("x-user-id") if request else "") or "").strip()
    if not eff_viewer:
        raise HTTPException(status_code=400, detail="缺少查看人用户标识 viewer_uid")
    try:
        return LocalStore.get_mentee_full_detail(eff_viewer, mentee_uid)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"[team] Error getting mentee detail for {mentee_uid}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取队员详细训练与休息数据失败: {str(e)}")


# ── Club-Wide Official Pacer Radar & Group-Run Pacer Assignment ──

class AssignEventPacerRequest(BaseModel):
    operator_uid: str
    target_uid: str
    pace_group: Optional[str] = ""
    note: Optional[str] = ""


@router.get("/{club_id}/pacer-radar")
def get_club_pacer_radar_endpoint(
    club_id: str,
    event_name: Optional[str] = Query("上海马拉松", description="目标赛事名称或拉练名称"),
    distance_type: str = Query("fm", description="项目类型: fm | hm | 10k | custom"),
    target_groups: Optional[str] = Query(None, description="逗号分隔的目标兔组，如 300,330,400,430"),
    custom_distance_km: Optional[float] = Query(None, description="自定义拉练距离(km)"),
    custom_target_pace: Optional[str] = Query(None, description="自定义拉练配速，如 5:00"),
    operator_uid: Optional[str] = Query(None, description="教练/团长 UID"),
    user_id: Optional[str] = Query(None, description="教练/团长 UID 别名"),
    coach_uid: Optional[str] = Query(None, description="教练 UID 别名"),
    allow_web_search: bool = Query(True, description="冷门赛事是否允许联网检索"),
    request: Request = None,
):
    """
    Coach / Club Owner Workbench endpoint: evaluates and ranks all active club members
    across official pacer groups or custom LSD pacer targets.
    """
    eff_uid = (
        operator_uid
        or user_id
        or coach_uid
        or (request.headers.get("x-user-id") if request else "")
        or ""
    ).strip()
    if not eff_uid:
        raise HTTPException(status_code=400, detail="缺少操作人标识 operator_uid")

    try:
        LocalStore.validate_sub_club_access(club_id, eff_uid)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    # Ensure operator is club owner, coach, or platform super admin
    op_canon = LocalStore.resolve_user_id(eff_uid)
    is_auth = op_canon in LocalStore.SUPER_ADMIN_UIDS or eff_uid in LocalStore.SUPER_ADMIN_UIDS
    if not is_auth:
        import sqlite3
        from utils.local_store import DB_PATH
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT owner_id FROM clubs WHERE id = ?", (club_id,))
            c_row = c.fetchone()
            if c_row and LocalStore.resolve_user_id(c_row[0] or "") == op_canon:
                is_auth = True
            else:
                c.execute(
                    "SELECT role FROM club_memberships WHERE club_id = ? AND (user_id = ? OR user_id = ?) AND status = 'active'",
                    (club_id, op_canon, eff_uid),
                )
                m_row = c.fetchone()
                if m_row and m_row[0] in ("owner", "coach"):
                    is_auth = True
    if not is_auth:
        raise HTTPException(status_code=403, detail="仅跑团团长或认证教练可使用全团选兔雷达")

    from utils.pacer_evaluator import evaluate_club_pacer_candidates
    groups_list = [g.strip() for g in target_groups.split(",") if g.strip()] if target_groups else None
    try:
        return evaluate_club_pacer_candidates(
            club_id=club_id,
            viewer_uid=op_canon,
            event_name=event_name,
            distance_type=distance_type,
            target_groups=groups_list,
            custom_distance_km=custom_distance_km,
            custom_target_pace=custom_target_pace,
            allow_web_search=allow_web_search,
        )
    except Exception as e:
        logger.error(f"[team] Pacer radar failed for club {club_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"全团选兔雷达计算失败: {str(e)}")


@router.post("/{club_id}/events/{event_id}/assign-pacer")
def assign_club_event_pacer_endpoint(
    club_id: str,
    event_id: str,
    req: AssignEventPacerRequest,
):
    """
    Assigns a candidate member as '🐰 领跑兔' for a specific club offline group-run / LSD event
    and dispatches an in-app pacer invitation notification.
    """
    try:
        return LocalStore.assign_event_pacer_by_coach(
            club_id=club_id,
            event_id=event_id,
            operator_uid=req.operator_uid,
            target_uid=req.target_uid,
            pace_group=req.pace_group or "",
            note=req.note or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=403 if "仅跑团" in str(e) else 400, detail=str(e))
    except Exception as e:
        logger.error(f"[team] Assign pacer failed for event {event_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"指派约跑领跑兔失败: {str(e)}")





