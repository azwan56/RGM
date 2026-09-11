from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime

from utils.local_store import LocalStore
from utils.wechat import dispatch_canova_critique_push, wechat_client
from config import settings

logger = logging.getLogger("router_notifications")
router = APIRouter(prefix="/notifications", tags=["notifications"])


class ReadAllRequest(BaseModel):
    user_id: str


class TestPushRequest(BaseModel):
    user_id: str
    activity_name: Optional[str] = "公路专项拉练"
    distance_km: Optional[float] = 12.5
    critique: Optional[str] = "【稳态专项有氧进阶】配速稳健，心率漂移可控。已同步生成大师组超量恢复提示，建议保证 48 小时充裕恢复窗口。"


@router.get("")
def get_notifications(user_id: str = Query(..., description="User ID"), limit: int = Query(30, ge=1, le=100)):
    """Retrieves user system notifications and unread count."""
    canonical_uid = LocalStore.resolve_user_id(user_id)
    notifications = LocalStore.get_user_notifications(canonical_uid, limit=limit)
    unread_count = LocalStore.get_unread_notifications_count(canonical_uid)
    return {
        "success": True,
        "notifications": notifications,
        "unread_count": unread_count
    }


@router.post("/{notification_id}/read")
def mark_notification_read(notification_id: str, user_id: str = Query(..., description="User ID")):
    """Marks a single notification as read."""
    canonical_uid = LocalStore.resolve_user_id(user_id)
    ok = LocalStore.mark_notification_as_read(notification_id, canonical_uid)
    unread_count = LocalStore.get_unread_notifications_count(canonical_uid)
    return {
        "success": ok,
        "unread_count": unread_count
    }


@router.post("/read-all")
def mark_all_read(req: ReadAllRequest):
    """Marks all user notifications as read."""
    canonical_uid = LocalStore.resolve_user_id(req.user_id)
    updated_count = LocalStore.mark_all_notifications_read(canonical_uid)
    return {
        "success": True,
        "marked_read_count": updated_count,
        "unread_count": 0
    }


@router.post("/test-push")
def test_push_notification(req: TestPushRequest):
    """
    Sends a test Canova Coach critique push to both in-app notification center and WeChat Subscribe Message.
    Useful for developers and admins to verify push delivery to real phone.
    """
    canonical_uid = LocalStore.resolve_user_id(req.user_id)
    profile = LocalStore.get_profile(canonical_uid) or {}
    openid = profile.get("wechat_openid")

    mock_act = {
        "id": f"test_push_{int(datetime.utcnow().timestamp())}",
        "name": req.activity_name or "测试跑步",
        "distance_meters": int((req.distance_km or 10.0) * 1000),
        "avg_pace_str": "5:30 /km"
    }
    
    critique_text = req.critique or "Canova教练专业评语：节奏平稳，心率适中！"
    
    result = dispatch_canova_critique_push(
        user_id=canonical_uid,
        activity=mock_act,
        critique=critique_text
    )

    tmpl_id = getattr(settings, "WECHAT_SUBSCRIBE_TEMPLATE_ID", "")
    return {
        "success": True,
        "user_id": canonical_uid,
        "display_name": profile.get("display_name"),
        "wechat_openid": openid,
        "template_id_configured": bool(tmpl_id),
        "template_id": tmpl_id or "未配置 (请在 .env 设置 WECHAT_SUBSCRIBE_TEMPLATE_ID)",
        "wechat_sent": result.get("wechat_sent"),
        "wechat_errmsg": result.get("wechat_errmsg"),
        "notification": result.get("notification")
    }
