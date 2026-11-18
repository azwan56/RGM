from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Query, Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import os
import time
import hashlib
import base64

from utils.local_store import LocalStore
from utils.security import validate_uploaded_image_bytes

logger = logging.getLogger("router_community")
router = APIRouter()


def _extract_uid(explicit_uid: Optional[str], request: Optional[Request], required: bool = True) -> str:
    uid = (
        (explicit_uid or "").strip()
        or (request.headers.get("x-user-id", "").strip() if request else "")
        or (str(getattr(getattr(request, "state", None), "user_id", "") or "").strip() if request else "")
    )
    if required and not uid:
        raise HTTPException(status_code=401, detail="缺少用户身份标识，请先登录")
    return uid


def _build_showcase_photo_url(request: Request, filename: str) -> str:
    host = (request.url.hostname or "").lower()
    if host == "rgm.vanpower.net":
        return f"https://rgm.vanpower.net/api/showcase-photos/{filename}"
    return f"/api/showcase-photos/{filename}"


def _save_showcase_image_bytes(owner_type: str, owner_id: str, img_bytes: bytes, orig_name: str) -> str:
    ext = validate_uploaded_image_bytes(img_bytes, orig_name)
    photos_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "showcase_photos")
    os.makedirs(photos_dir, exist_ok=True)
    safe_oid = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(owner_id))
    safe_type = "coach" if str(owner_type).strip().lower() == "coach" else "club"
    rand_hex = hashlib.md5(f"{time.time()}_{safe_oid}_{len(img_bytes)}".encode()).hexdigest()[:8]
    filename = f"{safe_type}_{safe_oid}_{int(time.time())}_{rand_hex}{ext}"
    filepath = os.path.join(photos_dir, filename)
    with open(filepath, "wb") as f:
        f.write(img_bytes)
    return filename


# ── Pydantic Schemas ──

class CreateBroadcastRequest(BaseModel):
    author_id: Optional[str] = None
    operator_uid: Optional[str] = None
    category: Optional[str] = "notice"
    title: str
    content: str
    target_audience: Optional[str] = "all"
    linked_event_id: Optional[str] = None
    pin_hours: Optional[int] = 72


class AckBroadcastRequest(BaseModel):
    user_id: Optional[str] = None


class MicroCheerRequest(BaseModel):
    sender_id: Optional[str] = None
    user_id: Optional[str] = None
    target_type: str = "activity"
    target_id: str
    recipient_id: Optional[str] = ""
    cheer_key: str
    club_id: Optional[str] = ""


class FollowRequest(BaseModel):
    follower_id: Optional[str] = None
    user_id: Optional[str] = None
    target_uid: str


class ClubShowcaseUpsertRequest(BaseModel):
    operator_uid: Optional[str] = None
    slogan: Optional[str] = None
    hero_cover_url: Optional[str] = None
    style_tags: Optional[List[str]] = None
    home_landmarks: Optional[List[str]] = None
    schedule_summary: Optional[str] = None
    group_paces: Optional[List[Dict[str, Any]]] = None
    highlights_md: Optional[str] = None
    is_published: Optional[bool] = None


class CoachResumeUpsertRequest(BaseModel):
    operator_uid: Optional[str] = None
    headline: Optional[str] = None
    specialty_tags: Optional[List[str]] = None
    certifications: Optional[List[Dict[str, Any]]] = None
    bio_story: Optional[str] = None
    coaching_philosophy: Optional[str] = None
    featured_club_ids: Optional[List[str]] = None
    accepting_runners: Optional[bool] = None
    is_published: Optional[bool] = None


class ShowcasePhotoBase64Request(BaseModel):
    uploader_uid: Optional[str] = None
    operator_uid: Optional[str] = None
    owner_type: str = "club"
    owner_id: str
    category: Optional[str] = "group_run"
    caption: Optional[str] = ""
    is_cover: Optional[bool] = False
    image_base64: str
    ext: Optional[str] = ".jpg"


class ShowcasePhotoUpdateRequest(BaseModel):
    operator_uid: Optional[str] = None
    category: Optional[str] = None
    caption: Optional[str] = None
    sort_order: Optional[int] = None
    is_cover: Optional[bool] = None


class TargetedInviteCreateRequest(BaseModel):
    inviter_uid: Optional[str] = None
    operator_uid: Optional[str] = None
    target_user_ids: List[str] = []
    preassigned_group: Optional[str] = ""
    reason_tag: Optional[str] = ""
    custom_message: Optional[str] = ""
    attach_showcase: Optional[bool] = True


class TargetedInviteRespondRequest(BaseModel):
    user_id: Optional[str] = None
    action: str = "accept"


# ── Phase 1: Broadcasts, Home Pulse & Micro-Cheers ──

@router.post("/clubs/{club_id}/broadcasts")
def create_broadcast(club_id: str, req: CreateBroadcastRequest, request: Request):
    uid = _extract_uid(req.author_id or req.operator_uid, request)
    try:
        item = LocalStore.create_club_broadcast(
            club_id=club_id,
            author_id=uid,
            category=req.category or "notice",
            title=req.title,
            content=req.content,
            target_audience=req.target_audience or "all",
            linked_event_id=req.linked_event_id,
            pin_hours=req.pin_hours or 72,
        )
        return {"success": True, "broadcast": item}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/clubs/{club_id}/broadcasts")
def list_broadcasts(
    club_id: str,
    request: Request,
    viewer_uid: Optional[str] = Query(None),
    include_history: bool = Query(False),
):
    uid = _extract_uid(viewer_uid, request, required=False)
    return LocalStore.get_club_broadcasts(club_id, viewer_uid=uid or None, include_history=include_history)


@router.post("/broadcasts/{broadcast_id}/ack")
def ack_broadcast(broadcast_id: str, req: AckBroadcastRequest, request: Request):
    uid = _extract_uid(req.user_id, request)
    try:
        res = LocalStore.ack_club_broadcast(broadcast_id, uid)
        return {"success": True, **res}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/broadcasts/{broadcast_id}")
def delete_or_unpin_broadcast(broadcast_id: str, request: Request, operator_uid: Optional[str] = Query(None)):
    uid = _extract_uid(operator_uid, request)
    try:
        res = LocalStore.unpin_club_broadcast(broadcast_id, uid)
        return {"success": True, **res}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/home-pulse")
def get_home_pulse(
    request: Request,
    viewer_uid: Optional[str] = Query(None),
    club_id: Optional[str] = Query(None),
    tab: str = Query("all"),
    limit: int = Query(20, ge=1, le=50),
):
    uid = _extract_uid(viewer_uid, request)
    return LocalStore.get_home_social_pulse(viewer_uid=uid, club_id=club_id, tab=tab, limit=limit)


@router.post("/micro-cheer")
def toggle_micro_cheer(req: MicroCheerRequest, request: Request):
    uid = _extract_uid(req.sender_id or req.user_id, request)
    try:
        res = LocalStore.toggle_pulse_micro_cheer(
            sender_id=uid,
            target_type=req.target_type,
            target_id=req.target_id,
            recipient_id=req.recipient_id or "",
            cheer_key=req.cheer_key,
            club_id=req.club_id or "",
        )
        return {"success": True, **res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Phase 2: 6D Buddy Discovery, Follow & Weekly PK ──

@router.get("/discover")
def discover_buddies(
    request: Request,
    viewer_uid: Optional[str] = Query(None),
    scope: str = Query("org"),
    club_id: Optional[str] = Query(None),
    age_group: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    vdot_min: Optional[float] = Query(None),
    vdot_max: Optional[float] = Query(None),
    match_my_vdot: bool = Query(False),
    monthly_km_min: Optional[float] = Query(None),
    monthly_km_max: Optional[float] = Query(None),
    city: Optional[str] = Query(None),
    landmark: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    uid = _extract_uid(viewer_uid, request)
    return LocalStore.discover_running_buddies(
        viewer_uid=uid,
        scope=scope,
        club_id=club_id,
        age_group=age_group,
        gender=gender,
        vdot_min=vdot_min,
        vdot_max=vdot_max,
        match_my_vdot=match_my_vdot,
        monthly_km_min=monthly_km_min,
        monthly_km_max=monthly_km_max,
        city=city,
        landmark=landmark,
        tag=tag,
        limit=limit,
        offset=offset,
    )


@router.post("/follow")
def follow_runner_endpoint(req: FollowRequest, request: Request):
    uid = _extract_uid(req.follower_id or req.user_id, request)
    try:
        res = LocalStore.follow_runner(uid, req.target_uid)
        return {"success": True, **res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/follow/{target_uid}")
def unfollow_runner_endpoint(target_uid: str, request: Request, follower_id: Optional[str] = Query(None), user_id: Optional[str] = Query(None)):
    uid = _extract_uid(follower_id or user_id, request)
    res = LocalStore.unfollow_runner(uid, target_uid)
    return {"success": True, **res}


@router.get("/buddies")
def list_buddies(request: Request, viewer_uid: Optional[str] = Query(None)):
    uid = _extract_uid(viewer_uid, request)
    return LocalStore.get_user_buddies_overview(uid)


@router.get("/buddies/{target_uid}/pk")
def get_buddy_pk(target_uid: str, request: Request, viewer_uid: Optional[str] = Query(None)):
    uid = _extract_uid(viewer_uid, request)
    try:
        return LocalStore.get_buddy_weekly_pk(uid, target_uid)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Phase 3: Club & Coach Showcase Plaza, Verified Credentials & Photo Wall ──

@router.get("/showcase/plaza")
def get_showcase_plaza(
    request: Request,
    viewer_uid: Optional[str] = Query(None),
    tab: str = Query("clubs"),
    city: Optional[str] = Query(None),
    landmark: Optional[str] = Query(None),
    style_tag: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    uid = _extract_uid(viewer_uid, request, required=False)
    return LocalStore.list_showcase_plaza(
        viewer_uid=uid or None,
        tab=tab,
        city=city,
        landmark=landmark,
        style_tag=style_tag,
        org_id=org_id,
        search=search,
    )


@router.get("/showcase/clubs/{club_id}")
def get_club_showcase(
    club_id: str,
    request: Request,
    viewer_uid: Optional[str] = Query(None),
    invite_token: Optional[str] = Query(None),
):
    uid = _extract_uid(viewer_uid, request, required=False)
    try:
        return LocalStore.get_club_showcase_detail(club_id, viewer_uid=uid or None, invite_token=invite_token)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/showcase/clubs/{club_id}")
def upsert_club_showcase(club_id: str, req: ClubShowcaseUpsertRequest, request: Request):
    uid = _extract_uid(req.operator_uid, request)
    try:
        payload = {k: v for k, v in req.model_dump().items() if k != "operator_uid" and v is not None}
        detail = LocalStore.upsert_club_showcase_profile(club_id, uid, payload)
        return {"success": True, **detail}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/showcase/coaches/{coach_uid}")
def get_coach_showcase(coach_uid: str, request: Request, viewer_uid: Optional[str] = Query(None)):
    uid = _extract_uid(viewer_uid, request, required=False)
    try:
        return LocalStore.get_coach_showcase_detail(coach_uid, viewer_uid=uid or None)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/showcase/coaches/{coach_uid}")
def upsert_coach_showcase(coach_uid: str, req: CoachResumeUpsertRequest, request: Request):
    uid = _extract_uid(req.operator_uid, request)
    try:
        payload = {k: v for k, v in req.model_dump().items() if k != "operator_uid" and v is not None}
        detail = LocalStore.upsert_coach_public_resume(coach_uid, uid, payload)
        return {"success": True, **detail}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/showcase/photos/upload")
async def upload_showcase_photo_multipart(
    request: Request,
    file: UploadFile = File(...),
    owner_type: str = Form("club"),
    owner_id: str = Form(...),
    uploader_uid: Optional[str] = Form(None),
    category: str = Form("group_run"),
    caption: str = Form(""),
    is_cover: bool = Form(False),
):
    uid = _extract_uid(uploader_uid, request)
    contents = await file.read()
    filename = _save_showcase_image_bytes(owner_type, owner_id, contents, file.filename or "showcase.jpg")
    photo_url = _build_showcase_photo_url(request, filename)
    try:
        photo = LocalStore.add_showcase_photo(
            owner_type=owner_type,
            owner_id=owner_id,
            uploader_uid=uid,
            photo_url=photo_url,
            category=category,
            caption=caption,
            is_cover=is_cover,
        )
        return {"success": True, "photo": photo}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/showcase/photos/upload-base64")
def upload_showcase_photo_base64(req: ShowcasePhotoBase64Request, request: Request):
    uid = _extract_uid(req.uploader_uid or req.operator_uid, request)
    raw_ext = (req.ext or ".jpg").lower()
    if not raw_ext.startswith("."):
        raw_ext = f".{raw_ext}"
    try:
        raw_b64 = req.image_base64
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        img_bytes = base64.b64decode(raw_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="照片 Base64 编码格式无效")

    filename = _save_showcase_image_bytes(req.owner_type, req.owner_id, img_bytes, f"showcase{raw_ext}")
    photo_url = _build_showcase_photo_url(request, filename)
    try:
        photo = LocalStore.add_showcase_photo(
            owner_type=req.owner_type,
            owner_id=req.owner_id,
            uploader_uid=uid,
            photo_url=photo_url,
            category=req.category or "group_run",
            caption=req.caption or "",
            is_cover=bool(req.is_cover),
        )
        return {"success": True, "photo": photo}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/showcase/photos/{photo_id}")
def update_showcase_photo_endpoint(photo_id: str, req: ShowcasePhotoUpdateRequest, request: Request):
    uid = _extract_uid(req.operator_uid, request)
    try:
        payload = {k: v for k, v in req.model_dump().items() if k != "operator_uid" and v is not None}
        photo = LocalStore.update_showcase_photo(photo_id, uid, payload)
        return {"success": True, "photo": photo}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/showcase/photos/{photo_id}")
def delete_showcase_photo_endpoint(photo_id: str, request: Request, operator_uid: Optional[str] = Query(None)):
    uid = _extract_uid(operator_uid, request)
    try:
        res = LocalStore.delete_showcase_photo(photo_id, uid)
        return {"success": True, **res}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Phase 4: Non-Exclusive Multi-Club Targeted Recruitment & Funnel ──

@router.get("/clubs/{club_id}/recruit-candidates")
def get_recruit_candidates(
    club_id: str,
    request: Request,
    operator_uid: Optional[str] = Query(None),
    pool: str = Query("same_org"),
    preset: Optional[str] = Query(None),
    age_group: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    vdot_min: Optional[float] = Query(None),
    vdot_max: Optional[float] = Query(None),
    monthly_km_min: Optional[float] = Query(None),
    city: Optional[str] = Query(None),
    landmark: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    uid = _extract_uid(operator_uid, request)
    try:
        return LocalStore.search_recruit_candidates(
            club_id=club_id,
            operator_uid=uid,
            pool=pool,
            preset=preset,
            age_group=age_group,
            gender=gender,
            vdot_min=vdot_min,
            vdot_max=vdot_max,
            monthly_km_min=monthly_km_min,
            city=city,
            landmark=landmark,
            limit=limit,
            offset=offset,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/clubs/{club_id}/targeted-invites")
def create_targeted_invites_endpoint(club_id: str, req: TargetedInviteCreateRequest, request: Request):
    uid = _extract_uid(req.inviter_uid or req.operator_uid, request)
    try:
        res = LocalStore.create_targeted_invites(
            club_id=club_id,
            inviter_uid=uid,
            target_user_ids=req.target_user_ids,
            preassigned_group=req.preassigned_group or "",
            reason_tag=req.reason_tag or "",
            custom_message=req.custom_message or "",
            attach_showcase=True if req.attach_showcase is None else bool(req.attach_showcase),
        )
        return {"success": True, **res}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/clubs/{club_id}/recruit-funnel")
def get_recruit_funnel_endpoint(club_id: str, request: Request, operator_uid: Optional[str] = Query(None)):
    uid = _extract_uid(operator_uid, request)
    try:
        return LocalStore.get_club_recruit_funnel(club_id, uid)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/invites/my-pending")
def get_my_pending_invites(request: Request, user_id: Optional[str] = Query(None)):
    uid = _extract_uid(user_id, request)
    return {"invites": LocalStore.get_user_pending_targeted_invites(uid)}


@router.get("/invites/{invite_token}")
def preview_targeted_invite(invite_token: str, request: Request, viewer_uid: Optional[str] = Query(None)):
    uid = _extract_uid(viewer_uid, request, required=False)
    try:
        return LocalStore.get_targeted_invite_preview(invite_token, viewer_uid=uid or None)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/invites/{invite_token}/respond")
def respond_targeted_invite_endpoint(invite_token: str, req: TargetedInviteRespondRequest, request: Request):
    uid = _extract_uid(req.user_id, request)
    try:
        res = LocalStore.respond_targeted_invite(invite_token, uid, action=req.action)
        return {"success": True, **res}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
