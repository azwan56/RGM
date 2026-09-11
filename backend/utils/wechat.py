"""
WeChat Mini Program API Utilities
Supports:
- jscode2session (Mini Program wx.login code exchange for openid & session_key)
- getuserphonenumber (Decryption or cloud code exchange for phone number)
- Mini Program access_token caching
- Template subscribe message sending
"""

import logging
import requests
import json
from typing import Optional, Dict, Any
from config import settings

logger = logging.getLogger("wechat_api")

class WeChatAPI:
    def __init__(self, app_id: str = "", app_secret: str = ""):
        self.app_id = app_id or settings.WECHAT_APP_ID
        self.app_secret = app_secret or settings.WECHAT_APP_SECRET
        self._access_token: Optional[str] = None

    def code_to_session(self, js_code: str) -> Dict[str, Any]:
        """
        Exchanges WeChat wx.login js_code for openid and session_key.
        Endpoint: https://api.weixin.qq.com/sns/jscode2session
        """
        if not self.app_id or not self.app_secret:
            logger.warning("[wechat] WECHAT_APP_ID or WECHAT_APP_SECRET not configured.")
            return {"errcode": -1, "errmsg": "微信小程序未配置 AppID 或 AppSecret"}

        url = "https://api.weixin.qq.com/sns/jscode2session"
        params = {
            "appid": self.app_id,
            "secret": self.app_secret,
            "js_code": js_code,
            "grant_type": "authorization_code"
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            if "errcode" in data and data["errcode"] != 0:
                logger.error(f"[wechat] code2session failed: {data}")
            return data
        except Exception as e:
            logger.error(f"[wechat] code2session exception: {e}")
            return {"errcode": -500, "errmsg": str(e)}

    def get_access_token(self, force_refresh: bool = False) -> Optional[str]:
        """Gets or refreshes WeChat Mini Program stable access_token."""
        if self._access_token and not force_refresh:
            return self._access_token

        if not self.app_id or not self.app_secret:
            return None

        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            if "access_token" in data:
                self._access_token = data["access_token"]
                return self._access_token
            else:
                logger.error(f"[wechat] get_access_token failed: {data}")
                return None
        except Exception as e:
            logger.error(f"[wechat] get_access_token exception: {e}")
            return None

    def get_phone_number(self, code: str) -> Dict[str, Any]:
        """
        Exchanges WeChat getPhoneNumber dynamic code for user phone number.
        Endpoint: https://api.weixin.qq.com/wxa/business/getuserphonenumber
        """
        token = self.get_access_token()
        if not token:
            return {"errcode": -1, "errmsg": "Failed to obtain WeChat access token"}

        url = f"https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={token}"
        payload = {"code": code}

        try:
            resp = requests.post(url, json=payload, timeout=10)
            return resp.json()
        except Exception as e:
            logger.error(f"[wechat] get_phone_number exception: {e}")
            return {"errcode": -500, "errmsg": str(e)}

    def send_subscribe_message(
        self,
        touser: str,
        template_id: str,
        data: Dict[str, Any],
        page: str = "pages/index/index",
        miniprogram_state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends a WeChat Mini Program subscribe message (服务通知) to a user.
        Endpoint: https://api.weixin.qq.com/cgi-bin/message/subscribe/send
        """
        if not template_id:
            logger.info("[wechat] Subscribe template_id is empty, skipping external WeChat push.")
            return {"errcode": -1, "errmsg": "未配置 WECHAT_SUBSCRIBE_TEMPLATE_ID 模板ID"}

        token = self.get_access_token()
        if not token:
            logger.error("[wechat] Failed to obtain access token for subscribe message")
            return {"errcode": -1, "errmsg": "获取微信 access_token 失败"}

        state = miniprogram_state or getattr(settings, "WECHAT_MINIPROGRAM_STATE", "formal") or "formal"
        url = f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={token}"
        payload = {
            "touser": touser,
            "template_id": template_id,
            "page": page,
            "miniprogram_state": state,
            "lang": "zh_CN",
            "data": data
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            res_data = resp.json()
            if res_data.get("errcode") == 0:
                logger.info(f"[wechat] Subscribe message sent successfully to {touser}")
            else:
                logger.warning(f"[wechat] Subscribe message send response for {touser}: {res_data}")
            return res_data
        except Exception as e:
            logger.error(f"[wechat] Subscribe message send exception for {touser}: {e}")
            return {"errcode": -500, "errmsg": str(e)}

wechat_client = WeChatAPI()


def dispatch_canova_critique_push(
    user_id: str,
    activity: Dict[str, Any],
    critique: str
) -> Dict[str, Any]:
    """
    Dispatches Canova Coach critique:
    1. Persists an in-app system notification.
    2. If user has a valid WeChat openid and template is configured, sends WeChat Subscribe Message.
    """
    from utils.local_store import LocalStore
    from datetime import datetime

    canonical_uid = LocalStore.resolve_user_id(user_id)
    profile = LocalStore.get_profile(canonical_uid) or {}
    openid = profile.get("wechat_openid")

    act_id = activity.get("id") or ""
    act_name = activity.get("name") or "专项跑步训练"
    dist_m = activity.get("distance_meters") or 0.0
    dist_km = round(float(dist_m) / 1000.0, 2)
    pace = activity.get("avg_pace_str") or "--"
    
    title = f"【Canova教练】{dist_km}km 训练点评已送达"
    content = critique.strip()

    wechat_sent = 0
    wechat_errmsg = None

    # Try WeChat Subscribe Message push if openid is available
    tmpl_id = getattr(settings, "WECHAT_SUBSCRIBE_TEMPLATE_ID", "")
    if openid and openid.startswith("ogDgjx") and tmpl_id:
        clean_critique = critique.replace("\n", " ").strip()
        critique_snippet = clean_critique[:20] if len(clean_critique) > 20 else clean_critique
        sport_name = act_name[:20] if len(act_name) > 20 else act_name

        data = {
            "thing1": {"value": sport_name or "专项跑步"},
            "character_string2": {"value": f"{dist_km}km"},
            "thing3": {"value": critique_snippet or "Canova教练专业评语"},
            "time4": {"value": datetime.now().strftime("%Y-%m-%d %H:%M")}
        }
        res = wechat_client.send_subscribe_message(
            touser=openid,
            template_id=tmpl_id,
            data=data,
            page=f"pages/index/index?activity_id={act_id}"
        )
        if res.get("errcode") == 0:
            wechat_sent = 1
        else:
            wechat_sent = -1
            wechat_errmsg = f"[{res.get('errcode')}] {res.get('errmsg')}"
    elif not tmpl_id:
        wechat_errmsg = "待配置 WECHAT_SUBSCRIBE_TEMPLATE_ID"
    elif not openid:
        wechat_errmsg = "未绑定微信 openid"

    # Save to in-app system notification table
    notif = LocalStore.create_system_notification(
        user_id=canonical_uid,
        title=title,
        content=content,
        activity_id=act_id,
        notif_type="coach_critique",
        wechat_sent=wechat_sent,
        wechat_errmsg=wechat_errmsg
    )

    return {
        "notification": notif,
        "wechat_sent": wechat_sent,
        "wechat_errmsg": wechat_errmsg
    }

