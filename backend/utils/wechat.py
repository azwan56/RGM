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

wechat_client = WeChatAPI()
