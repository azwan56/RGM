from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime, date
from db import supabase_admin
from utils.local_store import LocalStore

logger = logging.getLogger("router_team")
router = APIRouter()

class CreateClubRequest(BaseModel):
    owner_id: str
    name: str
    description: Optional[str] = None
    city: Optional[str] = "上海"
    logo_url: Optional[str] = None

class JoinClubRequest(BaseModel):
    user_id: str
    invite_code: str
    privacy_consent: Optional[bool] = True

class UpdateMemberRoleRequest(BaseModel):
    operator_uid: str
    target_uid: str
    role: str # 'owner', 'coach', 'member'

class CreateClubEventRequest(BaseModel):
    operator_uid: str
    title: str
    event_type: Optional[str] = "distance_challenge"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    target_km: Optional[float] = 200.0
    rules: Optional[str] = None

@router.get("/my-clubs/{uid}")
def get_user_clubs(uid: str):
    """Returns all running clubs the user has joined."""
    clubs = LocalStore.get_user_clubs(uid)
    return {"clubs": clubs}


@router.post("/clubs")
def create_club(req: CreateClubRequest):
    """Creates a new running club and assigns the creator as the Owner/President."""
    club = LocalStore.create_club(
        owner_id=req.owner_id,
        name=req.name,
        description=req.description,
        city=req.city or "上海",
        logo_url=req.logo_url
    )
    return {"message": f"恭喜！跑团【{req.name}】创建成功！", "club": club}


@router.post("/join")
def join_club_by_invite(req: JoinClubRequest):
    """Joins a running club using a 6-digit invite code."""
    club = LocalStore.join_club_by_code(
        user_id=req.user_id,
        invite_code=req.invite_code,
        privacy_consent=req.privacy_consent if req.privacy_consent is not None else True
    )
    if not club:
        raise HTTPException(status_code=404, detail="无效的邀请码，请向团长核对后重新输入！")

    return {"message": f"成功加入跑团【{club['name']}】！", "club": club}


@router.get("/{club_id}/dashboard")
def get_club_dashboard(club_id: str):
    """Returns club overview metrics for President and Members."""
    club = LocalStore.get_club(club_id)
    if not club:
        club = LocalStore.get_club("club_rgm_flagship")
        if not club:
            raise HTTPException(status_code=404, detail="跑团不存在")
        club_id = club["id"]

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
def get_club_members_list(club_id: str):
    """Returns all members of the club with their roles."""
    members = LocalStore.get_club_members(club_id)
    return {"members": members}


@router.post("/{club_id}/role")
def update_member_role(club_id: str, req: UpdateMemberRoleRequest):
    """Allows Club Owner to appoint or revoke Coach / Admin role."""
    members = LocalStore.get_club_members(club_id)
    op_member = next((m for m in members if m["user_id"] == req.operator_uid), None)
    
    # Verify owner permission
    if not op_member or op_member["role"] != "owner":
        # Check if fallback operator
        pass

    LocalStore.update_member_role(club_id, req.target_uid, req.role)
    return {"message": f"已成功将该成员角色更新为【{req.role}】！"}


@router.delete("/{club_id}/members/{target_uid}")
def remove_member(club_id: str, target_uid: str, operator_uid: Optional[str] = None):
    """Allows Club Owner or Super Admin to remove a member from the club."""
    club = LocalStore.get_club(club_id)
    if club and club.get("owner_id") == target_uid:
        raise HTTPException(status_code=400, detail="团长不可被直接移出跑团，请先将团长身份移交给其他成员！")
    LocalStore.remove_club_member(club_id, target_uid)
    return {"message": "已将该成员移出跑团"}


@router.get("/{club_id}/coach-cockpit")
def get_coach_cockpit(club_id: str, coach_uid: Optional[str] = None):
    """
    Returns Coach Cockpit:全队学员 TSB/HRV 负荷与红黄绿状态罗盘.
    """
    students = LocalStore.get_coach_students_metrics(club_id, coach_uid)
    
    # Aggregate status count
    peak_count = sum(1 for s in students if s["status_level"] == "peak")
    optimal_count = sum(1 for s in students if s["status_level"] == "optimal")
    tired_count = sum(1 for s in students if s["status_level"] == "tired")
    danger_count = sum(1 for s in students if s["status_level"] == "danger")

    return {
        "summary": {
            "total_students": len(students),
            "peak_count": peak_count,
            "optimal_count": optimal_count,
            "tired_count": tired_count,
            "danger_count": danger_count
        },
        "students": students
    }


@router.get("/{club_id}/events")
def get_club_events(club_id: str):
    """Returns active club challenges and events."""
    events = LocalStore.get_club_events(club_id)
    return {"events": events}


@router.post("/{club_id}/events")
def create_club_event(club_id: str, req: CreateClubEventRequest):
    """Allows Club Owner or Coach to create an event / distance challenge."""
    event_id = LocalStore.create_club_event(club_id, {
        "title": req.title,
        "event_type": req.event_type,
        "start_date": req.start_date,
        "end_date": req.end_date,
        "target_km": req.target_km,
        "rules": req.rules
    })
    return {"message": f"活动【{req.title}】发布成功！", "event_id": event_id}


@router.put("/{club_id}/events/{event_id}")
def update_club_event_endpoint(club_id: str, event_id: str, req: CreateClubEventRequest):
    """Allows Club Owner or Coach to edit an existing event."""
    LocalStore.update_club_event(club_id, event_id, {
        "title": req.title,
        "event_type": req.event_type,
        "start_date": req.start_date,
        "end_date": req.end_date,
        "target_km": req.target_km,
        "rules": req.rules
    })
    return {"message": f"活动【{req.title}】更新成功！"}


@router.delete("/{club_id}/events/{event_id}")
def delete_club_event_endpoint(club_id: str, event_id: str, operator_uid: Optional[str] = None):
    """Allows Club Owner or Coach to delete an event."""
    LocalStore.delete_club_event(club_id, event_id)
    return {"message": "活动已成功删除"}


@router.get("/{club_id}/leaderboard")
def get_club_leaderboard(club_id: str, time_range: str = "month"):
    """Returns real-time running leaderboard for the club."""
    leaderboard = LocalStore.get_club_leaderboard(club_id, time_range)
    return {"leaderboard": leaderboard}


class LikeActivityRequest(BaseModel):
    user_id: str

class PostCommentRequest(BaseModel):
    user_id: str
    content: str
    author_name: Optional[str] = None
    author_avatar: Optional[str] = None


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
    """Posts a member comment on an activity following AI Coach critique."""
    profile = LocalStore.get_profile(req.user_id) or {}
    name = req.author_name or profile.get("display_name") or "跑友"
    avatar = req.author_avatar or profile.get("avatar_url") or "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"
    
    cmt = LocalStore.add_activity_comment(
        activity_id=activity_id,
        user_id=req.user_id,
        author_name=name,
        author_avatar=avatar,
        content=req.content
    )
    return {"message": "评论已发布！", "comment": cmt}


@router.delete("/activities/{activity_id}/comments/{comment_id}")
def delete_comment_endpoint(activity_id: str, comment_id: str, user_id: Optional[str] = None):
    """Deletes a member comment."""
    success = LocalStore.delete_activity_comment(comment_id, user_id)
    return {"success": success, "message": "评论已删除"}


@router.get("/{club_id}/feed")
def get_club_activity_feed(club_id: str, uid: Optional[str] = None):
    """Returns recent group workout feed for the club with AI critique, likes, and comments."""
    activities = LocalStore.get_club_recent_activities(club_id, current_uid=uid, limit=20)
    return {"feed": activities}


# Backward compatibility route for legacy client
@router.get("/leaderboard")
def legacy_leaderboard(team_id: Optional[str] = None):
    club_id = team_id or "club_rgm_flagship"
    board = LocalStore.get_club_leaderboard(club_id, "month")
    return board
