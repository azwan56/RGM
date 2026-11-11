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
        self._token_expires_at: float = 0.0

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
        """Gets or refreshes WeChat Mini Program stable access_token with TTL expiration tracking."""
        import time

        now = time.time()
        if self._access_token and not force_refresh and now < self._token_expires_at:
            return self._access_token

        if not self.app_id or not self.app_secret:
            return None

        # Prefer WeChat stable_token endpoint (safe across workers/restarts)
        try:
            resp_stable = requests.post(
                "https://api.weixin.qq.com/cgi-bin/stable_token",
                json={
                    "grant_type": "client_credential",
                    "appid": self.app_id,
                    "secret": self.app_secret,
                    "force_refresh": bool(force_refresh),
                },
                timeout=10,
            )
            s_data = resp_stable.json()
            if "access_token" in s_data:
                self._access_token = s_data["access_token"]
                expires_in = int(s_data.get("expires_in") or 7200)
                self._token_expires_at = now + max(60, expires_in - 300)
                return self._access_token
        except Exception as e:
            logger.debug(f"[wechat] stable_token fallback to cgi-bin/token: {e}")

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
                expires_in = int(data.get("expires_in") or 7200)
                self._token_expires_at = now + max(60, expires_in - 300)
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

    def get_wxacode_by_path(
        self,
        path: str,
        width: int = 280,
        env_version: str = "release"
    ) -> Optional[bytes]:
        """
        Generates an official WeChat Mini Program QR code (wxacode) for a full path with query params.
        Endpoint: https://api.weixin.qq.com/wxa/getwxacode
        """
        for force in (False, True):
            token = self.get_access_token(force_refresh=force)
            if not token:
                return None

            url = f"https://api.weixin.qq.com/wxa/getwxacode?access_token={token}"
            payload = {
                "path": path[:128],
                "width": width,
                "is_hyaline": False,
                "env_version": env_version or "release"
            }
            try:
                resp = requests.post(url, json=payload, timeout=10)
                ctype = resp.headers.get("Content-Type", "")
                if "image" in ctype and len(resp.content) > 500:
                    return resp.content
                data = resp.json()
                errcode = data.get("errcode")
                if errcode in (40001, 42001) and not force:
                    continue
                logger.warning(f"[wechat] get_wxacode_by_path failed: {data}")
                return None
            except Exception as e:
                logger.error(f"[wechat] get_wxacode_by_path exception: {e}")
                return None
        return None

    def get_wxacode_unlimit(
        self,
        scene: str,
        page: str = "pages/team/team",
        width: int = 280,
        env_version: str = "release"
    ) -> Optional[bytes]:
        """
        Generates an official WeChat Mini Program unlimited QR code (wxacode).
        Endpoint: https://api.weixin.qq.com/wxa/getwxacodeunlimit
        """
        for force in (False, True):
            token = self.get_access_token(force_refresh=force)
            if not token:
                return None

            url = f"https://api.weixin.qq.com/wxa/getwxacodeunlimit?access_token={token}"
            payload = {
                "scene": (scene or "e=0")[:32],
                "page": page,
                "check_path": False,
                "width": width,
                "is_hyaline": False,
                "env_version": env_version or "release"
            }
            try:
                resp = requests.post(url, json=payload, timeout=10)
                ctype = resp.headers.get("Content-Type", "")
                if "image" in ctype and len(resp.content) > 500:
                    return resp.content
                data = resp.json()
                errcode = data.get("errcode")
                if errcode in (40001, 42001) and not force:
                    continue
                logger.warning(f"[wechat] get_wxacode_unlimit failed: {data}")
                return None
            except Exception as e:
                logger.error(f"[wechat] get_wxacode_unlimit exception: {e}")
                return None
        return None

    def get_stable_access_token(self, force_refresh: bool = False) -> Optional[str]:
        """
        Obtains WeChat Mini Program stable_token without invalidating tokens held by other processes.
        Endpoint: https://api.weixin.qq.com/cgi-bin/stable_token
        """
        if not self.app_id or not self.app_secret:
            return None
        try:
            resp = requests.post(
                "https://api.weixin.qq.com/cgi-bin/stable_token",
                json={
                    "grant_type": "client_credential",
                    "appid": self.app_id,
                    "secret": self.app_secret,
                    "force_refresh": bool(force_refresh),
                },
                timeout=8,
            )
            data = resp.json()
            if "access_token" in data:
                return data["access_token"]
            logger.warning(f"[wechat] get_stable_access_token warning: {data}")
        except Exception as e:
            logger.warning(f"[wechat] get_stable_access_token exception: {e}")
        return self.get_access_token(force_refresh=force_refresh)

    def get_datacube_overview(self, days: int = 14) -> Dict[str, Any]:
        """
        Fetches official WeChat Mini Program historical analytics (We分析 DataCube)
        for the past N completed days (T-1), cached in memory for 15 minutes.
        """
        import time as _time
        from datetime import datetime, timedelta, timezone

        eff_days = max(1, min(30, int(days or 14)))
        now_ts = _time.time()
        cache = getattr(self, "_datacube_cache", None) or {}
        cached_item = cache.get(eff_days)
        if cached_item and (now_ts - cached_item.get("ts", 0)) < 900:
            return cached_item["data"]

        token = self.get_stable_access_token(force_refresh=False)
        if not token:
            return {"available": False, "reason": "未配置或无法获取微信小程序 access_token"}

        SCENE_LABELS = {
            "1": "小程序历史列表",
            "2": "微信搜索",
            "3": "微信聊天/群聊分享卡片",
            "4": "扫一扫二维码",
            "5": "公众号主页",
            "6": "聊天顶部置顶",
            "7": "系统桌面快捷方式",
            "8": "小程序主页",
            "9": "附近的小程序",
            "10": "其他微信入口",
            "11": "订阅消息/服务通知",
            "13": "公众号菜单",
            "14": "APP分享",
            "16": "长按识别小程序码/战报海报",
            "17": "相册选取小程序码",
            "18": "公众号文章",
            "29": "微信下拉「最近使用」",
            "36": "微信下拉「我的小程序」",
        }
        PAGE_TITLES = {
            "pages/index/index": "首页（数据总览）",
            "pages/coach/coach": "训练（周期课表与AI教练）",
            "pages/team/team": "跑团（主页与大群）",
            "pages/team/rank": "英雄榜与打卡动态（主包）",
            "pages/rank/rank": "英雄榜与打卡动态（分包）",
            "pages/team/group-run": "约跑集结与完赛战报",
            "pages/group-run/group-run": "约跑集结（分包）",
            "pages/profile/profile": "我的（资料与手表绑定）",
            "pages/team/cockpit": "教练工作台",
            "pages/analysis/analysis": "身体数据与跑力分析",
            "pages/activities/activities": "全部跑步记录",
            "pages/onboarding/onboarding": "新手跑者4步引导",
            "pages/manual/manual": "帮助与常见问题",
            "pages/share/share": "邀请与海报落地页",
        }

        cn_today = datetime.now(timezone(timedelta(hours=8))).date()
        daily_trend = []
        page_agg: Dict[str, Dict[str, Any]] = {}
        scene_agg: Dict[str, int] = {}
        cumulative_visitors = 0

        try:
            for delta in range(eff_days, 0, -1):
                d_str = (cn_today - timedelta(days=delta)).strftime("%Y%m%d")
                r1 = requests.post(
                    f"https://api.weixin.qq.com/datacube/getweanalysisappiddailyvisittrend?access_token={token}",
                    json={"begin_date": d_str, "end_date": d_str},
                    timeout=6,
                ).json()
                for row in r1.get("list") or []:
                    ref = str(row.get("ref_date") or d_str)
                    daily_trend.append({
                        "date": f"{ref[:4]}-{ref[4:6]}-{ref[6:8]}" if len(ref) == 8 else ref,
                        "session_cnt": int(row.get("session_cnt") or 0),
                        "visit_pv": int(row.get("visit_pv") or 0),
                        "visit_uv": int(row.get("visit_uv") or 0),
                        "visit_uv_new": int(row.get("visit_uv_new") or 0),
                        "stay_time_uv_sec": round(float(row.get("stay_time_uv") or 0.0), 1),
                        "stay_time_session_sec": round(float(row.get("stay_time_session") or 0.0), 1),
                        "visit_depth": round(float(row.get("visit_depth") or 0.0), 2),
                    })

                r2 = requests.post(
                    f"https://api.weixin.qq.com/datacube/getweanalysisappidvisitpage?access_token={token}",
                    json={"begin_date": d_str, "end_date": d_str},
                    timeout=6,
                ).json()
                for p in r2.get("list") or []:
                    path = str(p.get("page_path") or "").strip("/")
                    if not path:
                        continue
                    rec = page_agg.setdefault(path, {
                        "page_path": path,
                        "page_title": PAGE_TITLES.get(path, path),
                        "pv": 0,
                        "daily_uv_sum": 0,
                        "stay_weighted": 0.0,
                        "entry_pv": 0,
                        "exit_pv": 0,
                        "share_pv": 0,
                    })
                    pv = int(p.get("page_visit_pv") or 0)
                    stay = float(p.get("page_staytime_pv") or 0.0)
                    rec["pv"] += pv
                    rec["daily_uv_sum"] += int(p.get("page_visit_uv") or 0)
                    rec["stay_weighted"] += pv * stay
                    rec["entry_pv"] += int(p.get("entrypage_pv") or 0)
                    rec["exit_pv"] += int(p.get("exitpage_pv") or 0)
                    rec["share_pv"] += int(p.get("page_share_pv") or 0)

                r3 = requests.post(
                    f"https://api.weixin.qq.com/datacube/getweanalysisappidvisitdistribution?access_token={token}",
                    json={"begin_date": d_str, "end_date": d_str},
                    timeout=6,
                ).json()
                for item in r3.get("list") or []:
                    if item.get("index") == "access_source_session_cnt":
                        for kv in item.get("item_list") or []:
                            k = str(kv.get("key"))
                            scene_agg[k] = scene_agg.get(k, 0) + int(kv.get("value") or 0)

            yesterday_str = (cn_today - timedelta(days=1)).strftime("%Y%m%d")
            r_sum = requests.post(
                f"https://api.weixin.qq.com/datacube/getweanalysisappiddailysummarytrend?access_token={token}",
                json={"begin_date": yesterday_str, "end_date": yesterday_str},
                timeout=6,
            ).json()
            if r_sum.get("list"):
                cumulative_visitors = int(r_sum["list"][0].get("visit_total") or 0)
        except Exception as e:
            logger.warning(f"[wechat] get_datacube_overview error: {e}")

        pages_list = []
        total_pv = sum(x["pv"] for x in page_agg.values())
        for path, st in sorted(page_agg.items(), key=lambda item: -item[1]["pv"]):
            pv = st["pv"]
            pages_list.append({
                "page_path": path,
                "page_title": st["page_title"],
                "pv": pv,
                "pv_share_pct": round(pv * 100.0 / total_pv, 1) if total_pv > 0 else 0.0,
                "daily_uv_sum": st["daily_uv_sum"],
                "avg_stay_sec": round(st["stay_weighted"] / pv, 1) if pv > 0 else 0.0,
                "entry_pv": st["entry_pv"],
                "exit_pv": st["exit_pv"],
                "exit_rate_pct": round(st["exit_pv"] * 100.0 / pv, 1) if pv > 0 else 0.0,
                "share_pv": st["share_pv"],
            })

        total_scene_cnt = sum(scene_agg.values())
        scenes_list = [
            {
                "scene_key": k,
                "scene_label": SCENE_LABELS.get(k, f"场景 #{k}"),
                "count": cnt,
                "pct": round(cnt * 100.0 / total_scene_cnt, 1) if total_scene_cnt > 0 else 0.0,
            }
            for k, cnt in sorted(scene_agg.items(), key=lambda item: -item[1])
        ]

        total_sessions = sum(d["session_cnt"] for d in daily_trend)
        total_new_uv = sum(d["visit_uv_new"] for d in daily_trend)
        weighted_stay = sum(d["session_cnt"] * d["stay_time_session_sec"] for d in daily_trend)
        weighted_depth = sum(d["session_cnt"] * d["visit_depth"] for d in daily_trend)

        result = {
            "available": True,
            "days": eff_days,
            "cumulative_visitors": cumulative_visitors,
            "total_sessions": total_sessions,
            "total_pv": sum(d["visit_pv"] for d in daily_trend),
            "total_new_uv": total_new_uv,
            "avg_session_stay_sec": round(weighted_stay / total_sessions, 1) if total_sessions > 0 else 0.0,
            "avg_visit_depth": round(weighted_depth / total_sessions, 2) if total_sessions > 0 else 0.0,
            "daily_trend": daily_trend,
            "pages": pages_list,
            "scenes": scenes_list,
        }
        cache[eff_days] = {"ts": now_ts, "data": result}
        self._datacube_cache = cache
        return result


wechat_client = WeChatAPI()


def dispatch_canova_critique_push(
    user_id: str,
    activity: Dict[str, Any],
    critique: str,
    miniprogram_state: Optional[str] = None
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
    tmpl_id = getattr(settings, "WECHAT_SUBSCRIBE_TEMPLATE_ID", "") or "I8K67iHNWQB0on15Z01rxKinP18DAuIPgaz7LSXIqT0"
    if openid and openid.startswith("ogDgjx") and tmpl_id:
        # Format fields strictly adhering to template I8K67iHNWQB0on15Z01rxKinP18DAuIPgaz7LSXIqT0 (收到点评通知)
        # name1: 点评对象 (name rule, 10 Chinese chars or 20 letters max, no digits or special chars)
        runner_raw = profile.get("display_name") or "跑者同学"
        clean_name = "".join(c for c in runner_raw if c.isalpha() or '\u4e00' <= c <= '\u9fff')[:10]
        if not clean_name:
            clean_name = "跑者同学"

        # thing2: 点评主题 (thing rule, 20 chars max)
        theme = f"{dist_km}km跑步训练点评"[:20]

        # thing3: 点评内容 (thing rule, 20 chars max)
        clean_critique = critique.replace("\n", " ").replace("【", "").replace("】", "").strip()[:20]
        if not clean_critique:
            clean_critique = "Canova教练已完成分析"

        data = {
            "name1": {"value": clean_name},
            "thing2": {"value": theme},
            "thing3": {"value": clean_critique}
        }

        state = miniprogram_state or getattr(settings, "WECHAT_MINIPROGRAM_STATE", "formal") or "formal"
        res = wechat_client.send_subscribe_message(
            touser=openid,
            template_id=tmpl_id,
            data=data,
            page=f"pages/index/index?activity_id={act_id}",
            miniprogram_state=state
        )
        if res.get("errcode") == 0:
            wechat_sent = 1
        elif res.get("errcode") == 43101:
            wechat_sent = -1
            wechat_errmsg = "用户尚未在手机微信中授权此订阅通知，请点击【开启微信手机消息提醒】并选择【允许】"
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

