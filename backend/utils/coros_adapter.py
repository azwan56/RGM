"""
COROS Direct Adapter for China (teamcnapi.coros.com) & Global (teamapi.coros.com)
Supports syncing activities, health metrics, and normalizing into RGM schema.
Includes Token Persistence to avoid frequent login and rate limiting.
"""

import os
import json
import time
import hashlib
import random
import base64
import logging
import requests
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger("coros_adapter")

TOKEN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tokens")

_MOBILE_AES_IV = b"weloop3_2015_03#"

def _encrypt_mobile_param(plain_text: str, app_key: str) -> str:
    """
    Encrypt a string for the Coros mobile login API.
    Scheme reverse-engineered from libencrypt-lib.so in Coros APK:
      1. XOR plaintext bytes with appKey bytes cyclically
      2. PKCS7-pad the XOR'd result to 16-byte boundary
      3. AES-128-CBC encrypt: key = appKey.encode('ascii'), IV = b'weloop3_2015_03#'
      4. Base64-encode ciphertext
    Supports both cryptography and PyCryptodome libraries.
    """
    key_bytes = app_key.encode("ascii")
    data_bytes = plain_text.encode("utf-8")
    xored = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(data_bytes))
    pad_len = 16 - (len(xored) % 16)
    padded = xored + bytes([pad_len] * pad_len)

    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(_MOBILE_AES_IV), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
    except ImportError:
        from Crypto.Cipher import AES
        cipher = AES.new(key_bytes, AES.MODE_CBC, _MOBILE_AES_IV)
        ciphertext = cipher.encrypt(padded)

    return base64.b64encode(ciphertext).decode("ascii")

def pace_str(distance_m: float, moving_time_s: int) -> str:
    """Returns average pace as 'M:SS /km'."""
    km = distance_m / 1000.0
    if km <= 0 or moving_time_s <= 0:
        return "—"
    total_sec = int(round(moving_time_s / km))
    mins = total_sec // 60
    secs = total_sec % 60
    return f"{mins}:{secs:02d} /km"


class CorosAdapter:
    def __init__(self, account: str, password: str, domain: str = "teamcnapi.coros.com"):
        self.account = account.strip()
        self.password = password
        self.domain = domain.lower().strip()
        self.is_cn = ("cn" in self.domain or "teamcnapi" in self.domain)
        self.is_eu = ("eu" in self.domain or "teameuapi" in self.domain)
        
        if self.is_cn:
            self.base_url = "https://teamcnapi.coros.com"
            self.mobile_base_url = "https://apicn.coros.com"
        elif self.is_eu:
            self.base_url = "https://teameuapi.coros.com"
            self.mobile_base_url = "https://apieu.coros.com"
        else:
            self.base_url = "https://teamapi.coros.com"
            self.mobile_base_url = "https://api.coros.com"

        self.last_error: Optional[str] = None
        self.access_token: Optional[str] = None
        self.mobile_access_token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.nick_name: Optional[str] = None
        self.avatar_url: Optional[str] = None
        self._analyse_cache: Optional[Dict[str, Any]] = None
        self._analyse_cache_time: float = 0
        self._sleep_cache: Dict[str, Dict[str, Any]] = {}
        self._login_failed: bool = False
        self._mobile_login_failed: bool = False

        # 2FA (Two-Factor Authentication / 手机二次验证) properties
        self.needs_2fa: bool = False
        self.login_ticket: Optional[str] = None
        self.app_key: Optional[str] = None
        self.two_fa_account: Optional[str] = None
        self.account_type_2fa: int = 1
        self.region_id: int = 2
        self.cookies: Dict[str, str] = {}
        self.token_saved_at: float = 0.0

        os.makedirs(TOKEN_DIR, mode=0o700, exist_ok=True)
        try:
            os.chmod(TOKEN_DIR, 0o700)
        except Exception:
            pass
        safe_acc = self.account.replace("@", "_at_").replace(".", "_").replace("+", "_")
        region_str = "cn" if self.is_cn else ("eu" if self.is_eu else "global")
        self.token_path = os.path.join(TOKEN_DIR, f"tokens_coros_{safe_acc}_{region_str}.json")
        self.mobile_token_path = os.path.join(TOKEN_DIR, f"tokens_coros_mobile_{safe_acc}_{region_str}.json")
        self._load_cached_token()
        self._load_cached_mobile_token()

    @staticmethod
    def get_cached_auth_state(account: str, domain: str = "teamcnapi.coros.com") -> Dict[str, Any]:
        """
        Inspects the local token cache file with zero network I/O to report whether
        the COROS account currently holds a valid token, a 30-day refresh cookie,
        or requires manual SMS 2FA / password re-authorization.
        """
        state: Dict[str, Any] = {
            "has_token": False,
            "has_refresh_cookie": False,
            "needs_reauth": False,
            "blocked_reason": "",
            "blocked_error": "",
        }
        acc = (account or "").strip()
        if not acc:
            return state

        dom = (domain or "teamcnapi.coros.com").lower().strip()
        is_cn = ("cn" in dom or "teamcnapi" in dom)
        is_eu = ("eu" in dom or "teameuapi" in dom)
        region_str = "cn" if is_cn else ("eu" if is_eu else "global")

        candidates = [acc]
        if acc.startswith("+86"):
            stripped = acc[3:].lstrip("- ").strip()
            if stripped and stripped not in candidates:
                candidates.append(stripped)

        token_path = None
        for cand in candidates:
            safe_acc = cand.replace("@", "_at_").replace(".", "_").replace("+", "_")
            p = os.path.join(TOKEN_DIR, f"tokens_coros_{safe_acc}_{region_str}.json")
            if os.path.exists(p):
                token_path = p
                break

        if not token_path:
            return state

        try:
            with open(token_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cookies = data.get("cookies") if isinstance(data.get("cookies"), dict) else {}
            has_refresh_cookie = any(str(k).startswith("acct_ext") and v for k, v in cookies.items())
            has_token = bool(data.get("access_token"))
            blocked_reason = str(data.get("auth_blocked_reason") or "")
            blocked_error = str(data.get("auth_blocked_error") or "")

            state["has_token"] = has_token
            state["has_refresh_cookie"] = has_refresh_cookie
            state["blocked_reason"] = blocked_reason
            state["blocked_error"] = blocked_error
            if not has_token and not has_refresh_cookie and blocked_reason in ("needs_2fa", "bad_password"):
                state["needs_reauth"] = True
        except Exception as e:
            logger.debug(f"[coros] get_cached_auth_state read notice: {e}")
        return state

    def _capture_response_cookies(self, resp: Any):
        """Extracts Set-Cookie values (e.g. acct_ext_2, acct_uid_2) from a requests Response."""
        try:
            cookies_obj = getattr(resp, "cookies", None)
            if cookies_obj is not None:
                if hasattr(cookies_obj, "get_dict"):
                    c_dict = cookies_obj.get_dict()
                elif isinstance(cookies_obj, dict):
                    c_dict = cookies_obj
                else:
                    c_dict = {}
                if isinstance(c_dict, dict):
                    for k, v in c_dict.items():
                        if k and v and isinstance(k, str) and isinstance(v, str):
                            self.cookies[k] = v
        except Exception as e:
            logger.debug(f"[coros] Cookie capture notice: {e}")

    def _load_cached_token(self) -> bool:
        """
        Loads cached access token if file exists.
        Never artificially expires tokens at 7 days (which previously forced re-login and 2FA SMS loops);
        instead, token validity is verified against COROS API and only cleared on explicit 1019/401 rejection.
        Also loads persistent auth circuit-breaker state (needs_2fa / bad_password / account_locked)
        so background schedulers never hammer /account/login or /account/captcha.
        """
        if not os.path.exists(self.token_path):
            return False
        try:
            with open(self.token_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data.get("cookies"), dict):
                    self.cookies = {str(k): str(v) for k, v in data["cookies"].items() if k and v}
                self.token_saved_at = float(data.get("saved_at") or 0.0)
                token = data.get("access_token")
                if token:
                    self.access_token = token
                    self.user_id = data.get("user_id")
                    self.nick_name = data.get("nick_name")
                    self.avatar_url = data.get("avatar_url")
                    return True

                blocked_reason = data.get("auth_blocked_reason")
                blocked_at = float(data.get("auth_blocked_at") or 0)
                if blocked_reason:
                    # Keep circuit breaker active permanently for needs_2fa / bad_password
                    # (until user manually re-binds with force=True), or for 6h on account_locked (2018)
                    if blocked_reason in ("needs_2fa", "bad_password") or (
                        blocked_reason == "account_locked" and (time.time() - blocked_at < 6 * 3600)
                    ):
                        self.needs_2fa = (blocked_reason == "needs_2fa")
                        self._login_failed = True
                        self.last_error = data.get("auth_blocked_error") or (
                            "高驰安全授权已到期，请前往【我的 → 手表连接】输入短信验证码重新授权"
                        )
        except Exception as e:
            logger.warning(f"[coros] Failed to read cached token: {e}")
        return False

    def _save_cached_token(self):
        """Persists valid access token and refresh cookies to disk and clears any circuit-breaker flags."""
        if not self.access_token:
            return
        self.token_saved_at = time.time()
        try:
            tmp_path = f"{self.token_path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump({
                    "access_token": self.access_token,
                    "user_id": self.user_id,
                    "nick_name": self.nick_name,
                    "avatar_url": self.avatar_url,
                    "cookies": self.cookies,
                    "saved_at": self.token_saved_at
                }, f)
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self.token_path)
        except Exception as e:
            logger.warning(f"[coros] Failed to save token cache: {e}")

    def _save_auth_blocked(self, reason: str, error_msg: str):
        """
        Persists auth failure / 2FA requirement to disk so background sync jobs do not
        repeatedly attempt login or trigger 2FA SMS every 30 minutes.
        """
        try:
            with open(self.token_path, "w", encoding="utf-8") as f:
                json.dump({
                    "access_token": None,
                    "user_id": self.user_id,
                    "nick_name": self.nick_name,
                    "avatar_url": self.avatar_url,
                    "cookies": self.cookies,
                    "auth_blocked_reason": reason,
                    "auth_blocked_error": error_msg,
                    "auth_blocked_at": time.time(),
                    "saved_at": time.time()
                }, f)
        except Exception as e:
            logger.warning(f"[coros] Failed to save auth blocked state: {e}")

    def _load_cached_mobile_token(self) -> bool:
        """Permanently disabled: mobile tokens trigger single-device session conflicts."""
        return False

    def _save_cached_mobile_token(self):
        """Permanently disabled: mobile tokens trigger single-device session conflicts."""
        pass

    def mobile_login(self, override_account: Optional[str] = None, override_type: Optional[int] = None) -> bool:
        """
        [PERMANENTLY DISABLED FOR USER PROTECTION]
        COROS mobile API (/coros/user/login with clientType=1) enforces a strict single-device policy.
        Logging in via mobile API kicks the user out of the official COROS App on their physical phone,
        causing repeated logouts and prompting security alerts ('被盗号了').
        To guarantee zero disruption to the user's phone app, mobile login is strictly disabled.
        All data (activities, GPS tracks, EvoLab fitness & recovery metrics) is fetched via Web Training Hub.
        """
        logger.info(f"[coros] mobile_login permanently disabled to protect user's phone app session ({self.account})")
        self._mobile_login_failed = True
        return False

    def _get_headers(self) -> Dict[str, str]:
        if self.is_cn:
            hub_origin = "https://trainingcn.coros.com"
        elif self.is_eu:
            hub_origin = "https://trainingeu.coros.com"
        else:
            hub_origin = "https://training.coros.com"
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "content-type": "application/json;charset=UTF-8",
            "origin": hub_origin,
            "referer": f"{hub_origin}/",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }
        if self.user_id:
            headers["YFHeader"] = json.dumps({"userId": str(self.user_id), "language": "zh-CN"})
        cookie_parts = [f"CPL-coros-region={self.region_id}"]
        if self.access_token:
            headers["accesstoken"] = self.access_token
            cookie_parts.append(f"CPL-coros-token={self.access_token}")
        for ck, cv in (self.cookies or {}).items():
            if ck not in ("CPL-coros-region", "CPL-coros-token") and cv:
                cookie_parts.append(f"{ck}={cv}")
        if self.access_token or self.cookies:
            headers["cookie"] = "; ".join(cookie_parts)
        return headers

    def refresh_access_token(self) -> bool:
        """
        Refreshes COROS web accessToken via /account/refresh using persistent Remember-Me cookies
        (acct_ext_2 / acct_uid_2). Rotates both accessToken and 30-day refresh cookies without
        requiring password login or triggering 2FA SMS.
        """
        has_refresh_cookie = any(k.startswith("acct_ext") for k in (self.cookies or {}))
        if not has_refresh_cookie:
            return False
        url = f"{self.base_url}/account/refresh"
        for attempt in range(2):
            try:
                resp = requests.post(url, headers=self._get_headers(), timeout=12)
                if resp.status_code == 200:
                    res_json = resp.json()
                    if str(res_json.get("result")) == "0000":
                        data = res_json.get("data") if isinstance(res_json.get("data"), dict) else {}
                        new_token = data.get("accessToken") or res_json.get("accessToken")
                        if new_token and isinstance(new_token, str):
                            self.access_token = new_token
                            if data.get("userId"):
                                self.user_id = str(data.get("userId"))
                            self._capture_response_cookies(resp)
                            self.needs_2fa = False
                            self._login_failed = False
                            self.last_error = None
                            self._save_cached_token()
                            logger.info(f"[coros] Refreshed accessToken via /account/refresh for {self.account}")
                            return True
                    # Explicit rejection (e.g. 1019) means cookie is expired/invalid; do not retry
                    return False
            except Exception as e:
                logger.warning(f"[coros] refresh_access_token warning (attempt {attempt + 1}) for {self.account}: {e}")
                if attempt == 0:
                    time.sleep(0.5)
        return False

    def send_2fa_code(self) -> bool:
        """
        Sends or resends the 2FA SMS verification code via COROS captcha API.
        """
        if not self.two_fa_account:
            self.last_error = "无法发送验证码：未找到二次验证绑定的手机号/邮箱"
            return False
        url = f"{self.base_url}/account/captcha"
        payload = {
            "account": self.two_fa_account,
            "accountType": str(self.account_type_2fa),
            "codeType": 20,
            "lengthType": 2
        }
        headers = self._get_headers()
        headers["X-No-Warnning"] = "1"
        try:
            logger.info(f"[coros] Triggering 2FA SMS captcha to {self.two_fa_account} (accountType={self.account_type_2fa})")
            resp = requests.post(url, json=payload, headers=headers, timeout=12)
            if resp.status_code == 200:
                res = resp.json()
                if str(res.get("result")) == "0000":
                    logger.info(f"[coros] 2FA SMS sent successfully to {self.two_fa_account}")
                    return True
                else:
                    msg = res.get("message") or res.get("result")
                    self.last_error = f"发送验证码失败: {msg}"
                    logger.warning(f"[coros] Captcha request returned {res}")
                    return False
            else:
                self.last_error = f"验证码服务返回 HTTP {resp.status_code}"
                return False
        except Exception as e:
            self.last_error = f"发送验证码异常: {e}"
            logger.error(f"[coros] send_2fa_code error: {e}")
            return False

    def complete_2fa(self, code: str) -> bool:
        """
        Verifies 2FA SMS verification code and exchanges it for accessToken.
        """
        code = (code or "").strip()
        if not code:
            self.last_error = "请输入 6 位短信验证码"
            return False
        if not self.login_ticket or not self.app_key:
            self.last_error = "二次验证会话已过期，请重新输入高驰账号密码"
            return False

        url = f"{self.base_url}/account/2fa/login/verify"
        payload = {
            "loginTicket": self.login_ticket,
            "appKey": self.app_key,
            "code": code,
            "rmbm": 1
        }
        headers = self._get_headers()
        headers["X-No-Warnning"] = "1"
        try:
            logger.info(f"[coros] Verifying 2FA code for {self.account}...")
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code != 200:
                self.last_error = f"高驰验证接口返回 HTTP {resp.status_code}"
                return False

            res_json = resp.json()
            result_code = str(res_json.get("result", ""))
            if result_code != "0000":
                msg = res_json.get("message") or "验证码错误"
                if result_code == "2102":
                    msg = "验证码错误，请核对手机收到的 6 位短信验证码"
                elif result_code == "2112":
                    msg = "验证码已过期，请重新获取"
                elif result_code == "2117":
                    msg = "验证码输入错误次数过多，请稍后重试"
                elif result_code == "1002":
                    msg = "验证参数无效或已过期，请重新获取验证码"
                self.last_error = f"高驰二次验证失败：{msg}"
                logger.warning(f"[coros] 2FA verification rejected: {res_json}")
                return False

            data = res_json.get("data") or {}
            self.access_token = data.get("accessToken")
            self.user_id = str(data.get("userId") or "")
            self.needs_2fa = False
            self._capture_response_cookies(resp)

            if not self.access_token:
                self.last_error = "验证通过但未能获取到访问凭证 (accessToken)"
                return False

            # Save token to cache
            self._save_cached_token()

            # Attempt to fetch profile info to populate nickname and avatar
            try:
                p_info = self.fetch_user_profile_info()
                if p_info.get("display_name"):
                    self.nick_name = p_info["display_name"]
                if p_info.get("avatar_url"):
                    self.avatar_url = p_info["avatar_url"]
                self._save_cached_token()
            except Exception as e:
                logger.warning(f"[coros] Post-2FA fetch_user_profile_info non-fatal: {e}")

            self.last_error = None
            self._login_failed = False
            logger.info(f"[coros] 2FA verification success for {self.account}, userId={self.user_id}")
            return True
        except Exception as e:
            self.last_error = f"连接高驰服务器失败: {e}"
            logger.error(f"[coros] 2FA exception for {self.account}: {e}")
            return False

    def login(self, force: bool = False, trigger_2fa_sms: bool = False) -> bool:
        """
        Logs into COROS Training Hub with MD5 encrypted password.
        Uses cached token if available and tests validity (unless force=True).
        Proactively rotates tokens via /account/refresh when Remember-Me cookies (acct_ext_2) are present.
        IMPORTANT: trigger_2fa_sms defaults to False so background syncs NEVER send SMS codes.
        Only explicit user-initiated binding endpoints pass trigger_2fa_sms=True.
        """
        if self._login_failed and not force:
            if any(k.startswith("acct_ext") for k in (self.cookies or {})):
                if self.refresh_access_token():
                    return True
            return False

        if not force and self.access_token:
            # Proactively roll 30-day session forward if token is >12h old and Remember-Me cookie exists
            if self.token_saved_at > 0 and (time.time() - self.token_saved_at > 12 * 3600):
                if any(k.startswith("acct_ext") for k in (self.cookies or {})):
                    self.refresh_access_token()

            # Verify cached token with lightweight query
            if self._verify_token():
                logger.info(f"[coros] Using valid cached token for {self.account}")
                self.last_error = None
                return True
            else:
                logger.info(f"[coros] Cached token rejected by server for {self.account}, attempting silent refresh...")
                if self.refresh_access_token():
                    return True
                logger.info(f"[coros] Silent refresh unavailable for {self.account}, re-authenticating...")
                self.access_token = None
                try:
                    if os.path.exists(self.token_path):
                        os.remove(self.token_path)
                except Exception:
                    pass
        elif not force and not self.access_token and any(k.startswith("acct_ext") for k in (self.cookies or {})):
            if self.refresh_access_token():
                return True

        login_url = f"{self.base_url}/account/login"
        # COROS requires MD5 of password; rmbm=1 enables 30-day renewable acct_ext_2 cookie
        pwd_md5 = hashlib.md5(self.password.encode("utf-8")).hexdigest()
        payload = {
            "account": self.account,
            "accountType": 2,
            "pwd": pwd_md5,
            "rmbm": 1
        }

        try:
            logger.info(f"[coros] Attempting login for {self.account} ({self.base_url}, trigger_2fa_sms={trigger_2fa_sms})...")
            resp = requests.post(login_url, json=payload, headers=self._get_headers(), timeout=15)
            if resp.status_code != 200:
                self.last_error = f"COROS 登录接口返回 HTTP {resp.status_code}"
                logger.error(f"[coros] Login failed HTTP {resp.status_code}: {resp.text}")
                self._login_failed = True
                return False

            self._capture_response_cookies(resp)
            res_json = resp.json()
            # Result code "0000" signifies success in COROS API
            result_code = str(res_json.get("result", ""))
            if result_code != "0000":
                msg = res_json.get("message") or "账号或密码错误"
                if result_code == "1030":
                    msg = "账号或密码不匹配，请核对您的高驰登录密码"
                elif result_code == "2018":
                    msg = "密码错误次数超限被高驰安全锁定，请稍后15-30分钟再试，或在COROS App重置密码"
                elif result_code == "1029":
                    msg = "该账号未在高驰注册"
                self.last_error = f"高驰登录失败：{msg}"
                logger.warning(f"[coros] Login rejected: {res_json}")
                self._login_failed = True
                if result_code in ("1030", "1029"):
                    self._save_auth_blocked("bad_password", self.last_error)
                elif result_code == "2018":
                    self._save_auth_blocked("account_locked", self.last_error)
                return False

            data = res_json.get("data") or {}

            # Check if 2FA (Two-Factor Authentication) is required
            if data.get("twoFactorRequired") or data.get("loginTicket"):
                self.needs_2fa = True
                self._login_failed = True
                self.login_ticket = data.get("loginTicket")
                self.app_key = data.get("appKey")
                self.two_fa_account = data.get("account") or self.account
                self.account_type_2fa = data.get("accountType2fa", 1)
                self.region_id = data.get("regionId", 2)

                logger.info(f"[coros] 2FA required for {self.account}, account={self.two_fa_account}, trigger_2fa_sms={trigger_2fa_sms}")

                if trigger_2fa_sms:
                    sms_ok = self.send_2fa_code()
                    if sms_ok:
                        self.last_error = "高驰账号已开启二次安全验证，已向您的手机发送 6 位验证码，请输入验证码完成绑定。"
                    else:
                        self.last_error = self.last_error or "高驰账号已开启二次验证，但验证码发送失败，请稍后重试。"
                    if not self.access_token:
                        self._save_auth_blocked(
                            "needs_2fa",
                            "高驰安全授权已到期，请前往【我的 → 手表连接】输入手机短信验证码完成重新授权。",
                        )
                else:
                    self.last_error = "高驰安全授权已到期，请前往【我的 → 手表连接】输入手机短信验证码完成重新授权。"
                    self._save_auth_blocked("needs_2fa", self.last_error)

                return False

            self.access_token = data.get("accessToken")
            self.user_id = str(data.get("userId") or "")
            self.nick_name = data.get("nickName")
            self.avatar_url = data.get("headPic")

            if not self.access_token:
                self.last_error = "登录成功但未能解析到访问凭证 (accessToken)"
                self._login_failed = True
                return False

            self._save_cached_token()
            self.last_error = None
            self._login_failed = False
            logger.info(f"[coros] Login success for {self.account}, userId={self.user_id}")
            return True
        except Exception as e:
            self.last_error = f"连接高驰服务器失败: {str(e)}"
            self._login_failed = True
            logger.error(f"[coros] Login exception for {self.account}: {e}")
            return False

    def _verify_token(self) -> bool:
        """
        Checks if current access token is valid by querying activity count.
        Only returns False when COROS explicitly rejects the token (1019/401/1001).
        Transient network timeouts or 5xx errors return True so valid cached tokens are never wiped.
        """
        try:
            url = f"{self.base_url}/activity/query?pageNumber=1&size=1"
            resp = requests.get(url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                res_json = resp.json()
                res_code = str(res_json.get("result", ""))
                if res_code in ("1019", "401", "1001"):
                    return False
                return True
            elif resp.status_code in (401, 403):
                return False
        except Exception as e:
            logger.warning(f"[coros] _verify_token network warning for {self.account} (keeping cached token): {e}")
            return True
        return True

    def _get_analyse_data(self) -> Optional[Dict[str, Any]]:
        """Queries or returns cached EvoLab analyse data."""
        if not self.access_token and not self.login(trigger_2fa_sms=False):
            return None
        now = time.time()
        if self._analyse_cache and (now - self._analyse_cache_time < 300):
            return self._analyse_cache
        try:
            url = f"{self.base_url}/analyse/query?userId={self.user_id}"
            resp = requests.get(url, headers=self._get_headers(), timeout=12)
            if resp.status_code == 200:
                res_json = resp.json()
                if str(res_json.get("result")) in ["1019", "401", "1001"]:
                    logger.info(f"[coros] Web token expired for {self.account}, refreshing/re-authenticating (no SMS)...")
                    self.access_token = None
                    if self.refresh_access_token() or self.login(trigger_2fa_sms=False):
                        resp = requests.get(url, headers=self._get_headers(), timeout=12)
                        res_json = resp.json()

                if str(res_json.get("result")) == "0000":
                    self._analyse_cache = res_json.get("data") or {}
                    self._analyse_cache_time = now
                    return self._analyse_cache
                else:
                    logger.warning(f"[coros] /analyse/query non-0000 result: {res_json}")
        except Exception as e:
            logger.warning(f"[coros] _get_analyse_data error: {e}")
        return None

    def fetch_user_profile_info(self) -> Dict[str, Any]:
        """Returns normalized user profile information (avatar, display name, gender, height, weight, birth date, vo2max)."""
        info: Dict[str, Any] = {
            "avatar_url": self.avatar_url,
            "display_name": self.nick_name,
            "gender": None,
            "date_of_birth": None,
            "height_cm": None,
            "weight_kg": None,
            "vo2max": None,
            "max_heart_rate": None,
            "resting_heart_rate": None,
        }

        if not self.access_token and not self.login(trigger_2fa_sms=False):
            return info

        # 1. Query account for biometrics & personal info
        try:
            url = f"{self.base_url}/account/query?userId={self.user_id}"
            resp = requests.get(url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                res_json = resp.json()
                if str(res_json.get("result")) in ("1019", "401", "1001"):
                    self.access_token = None
                    if self.refresh_access_token() or self.login(trigger_2fa_sms=False):
                        url = f"{self.base_url}/account/query?userId={self.user_id}"
                        resp = requests.get(url, headers=self._get_headers(), timeout=10)
                        if resp.status_code == 200:
                            res_json = resp.json()
                if str(res_json.get("result")) == "0000":
                    p_data = res_json.get("data") or {}
                    if p_data.get("nickname"):
                        info["display_name"] = p_data["nickname"]
                    if p_data.get("headPic"):
                        info["avatar_url"] = p_data["headPic"]

                    # Gender: 0=male, 1=female in COROS
                    g = p_data.get("sex")
                    if g in [0, "0", "male", "MALE", "m", "M"]:
                        info["gender"] = "male"
                    elif g in [1, "1", "female", "FEMALE", "f", "F"]:
                        info["gender"] = "female"

                    # Height (cm): "stature": 168.0
                    h = p_data.get("stature") or p_data.get("height")
                    if h:
                        info["height_cm"] = round(float(h), 1)

                    # Weight (kg): "weight": 60.0
                    w = p_data.get("weight")
                    if w:
                        w_val = float(w)
                        info["weight_kg"] = round(w_val / 1000.0, 1) if w_val > 500 else round(w_val, 1)

                    # Birth date (e.g. 19900622)
                    b = p_data.get("birthday") or p_data.get("birthDate") or p_data.get("birth_date")
                    if b:
                        b_str = str(b).strip()
                        if len(b_str) == 8 and b_str.isdigit():
                            info["date_of_birth"] = f"{b_str[:4]}-{b_str[4:6]}-{b_str[6:]}"
                        elif "-" in b_str:
                            info["date_of_birth"] = b_str[:10]
                        elif b_str.isdigit() and len(b_str) >= 10:
                            ts = int(b_str[:10])
                            info["date_of_birth"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

                    if p_data.get("maxHr") or p_data.get("maxHeartRate"):
                        info["max_heart_rate"] = int(p_data.get("maxHr") or p_data.get("maxHeartRate"))
                    if p_data.get("rhr") or p_data.get("restHeartRate"):
                        info["resting_heart_rate"] = int(p_data.get("rhr") or p_data.get("restHeartRate"))

                    zone_data = p_data.get("zoneData") or {}
                    if zone_data.get("lthr"):
                        info["threshold_heart_rate"] = int(zone_data["lthr"])
                    if zone_data.get("ltsp"):
                        info["threshold_pace_sec"] = int(zone_data["ltsp"])
        except Exception as e:
            logger.warning(f"[coros] fetch_user_profile_info /account/query error: {e}")

        # 2. Query EvoLab analysis for VO2Max
        try:
            a_data = self._get_analyse_data()
            if a_data:
                day_list = a_data.get("dayList") or a_data.get("t7dayList") or []
                for item in reversed(day_list):
                    vo2 = item.get("vo2max") or item.get("vo2Max")
                    if vo2 and float(vo2) > 0:
                        info["vo2max"] = round(float(vo2), 1)
                        break
                if not info["vo2max"]:
                    top_vo2 = a_data.get("vo2Max") or a_data.get("vo2max") or a_data.get("runningVo2Max")
                    if top_vo2:
                        info["vo2max"] = round(float(top_vo2), 1)
        except Exception as e:
            logger.warning(f"[coros] fetch_user_profile_info /analyse/query error: {e}")

        logger.info(f"[coros] Resolved profile metrics: DOB={info['date_of_birth']}, gender={info['gender']}, "
                    f"height={info['height_cm']}cm, weight={info['weight_kg']}kg, VO2Max={info['vo2max']}, "
                    f"RHR={info['resting_heart_rate']}, MaxHR={info['max_heart_rate']}")
        return info

    def fetch_recent_activities(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Fetches latest running activities from COROS."""
        if not self.access_token and not self.login(trigger_2fa_sms=False):
            return []

        try:
            # 100: Outdoor Run, 101: Indoor/Treadmill, 102: Trail Run, 103: Track Run
            url = f"{self.base_url}/activity/query?modeList=100,101,102,103&pageNumber=1&size={limit}"
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            if resp.status_code != 200:
                logger.error(f"[coros] Query activities failed HTTP {resp.status_code}")
                return []

            res_json = resp.json()
            if str(res_json.get("result")) in ("1019", "401", "1001"):
                self.access_token = None
                if self.refresh_access_token() or self.login(trigger_2fa_sms=False):
                    resp = requests.get(url, headers=self._get_headers(), timeout=15)
                    if resp.status_code == 200:
                        res_json = resp.json()

            if str(res_json.get("result")) != "0000":
                logger.warning(f"[coros] Query activities returned non-zero result: {res_json}")
                return []

            data_list = res_json.get("data", {}).get("dataList") or []
            normalized = []
            for act in data_list:
                norm = self._normalize_activity(act)
                if norm:
                    normalized.append(norm)
            logger.info(f"[coros] Fetched and normalized {len(normalized)} recent activities for {self.account}")
            return normalized
        except Exception as e:
            logger.error(f"[coros] Error fetching recent activities for {self.account}: {e}")
            return []

    def fetch_activities_by_date(self, start_date: str = "2026-01-01", end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetches activities since start_date.
        Paginates through COROS activity records until start_date is passed.
        """
        if not self.access_token and not self.login(trigger_2fa_sms=False):
            return []

        try:
            start_dt = datetime.strptime(start_date[:10], "%Y-%m-%d")
            end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d") if end_date else datetime.now() + timedelta(days=1)
        except Exception:
            start_dt = datetime(date.today().year, 1, 1)
            end_dt = datetime.now() + timedelta(days=1)

        normalized = []
        page_number = 1
        page_size = 50

        try:
            while True:
                url = f"{self.base_url}/activity/query?modeList=100,101,102,103&pageNumber={page_number}&size={page_size}"
                resp = requests.get(url, headers=self._get_headers(), timeout=15)
                if resp.status_code != 200:
                    break

                res_json = resp.json()
                if str(res_json.get("result")) in ("1019", "401", "1001") and page_number == 1:
                    self.access_token = None
                    if self.refresh_access_token() or self.login(trigger_2fa_sms=False):
                        resp = requests.get(url, headers=self._get_headers(), timeout=15)
                        if resp.status_code == 200:
                            res_json = resp.json()

                if str(res_json.get("result")) != "0000":
                    break

                data_list = res_json.get("data", {}).get("dataList") or []
                if not data_list:
                    break

                reached_past = False
                for act in data_list:
                    norm = self._normalize_activity(act)
                    if not norm:
                        continue

                    # Check time bounds
                    act_time_str = norm.get("start_time", "")
                    try:
                        act_dt = datetime.fromisoformat(act_time_str.replace("Z", "+00:00"))
                        act_dt_naive = act_dt.replace(tzinfo=None)
                    except Exception:
                        act_dt_naive = datetime.now()

                    if act_dt_naive < start_dt:
                        reached_past = True
                        break

                    if act_dt_naive <= end_dt:
                        normalized.append(norm)

                if reached_past or len(data_list) < page_size:
                    break

                page_number += 1
                if page_number > 20: # Safety guard: max 1000 activities
                    break

            logger.info(f"[coros] Successfully fetched and normalized {len(normalized)} activities for {self.account}")
            return normalized
        except Exception as e:
            logger.error(f"[coros] Error fetching activities by date for {self.account}: {e}")
            return normalized

    def _normalize_activity(self, act: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raw_id = act.get("labelId") or act.get("activityId") or act.get("hId")
        if not raw_id:
            return None

        # COROS Sport Types:
        # 100: Run (户外跑), 101: Indoor Run (跑步机), 102: Trail Run (越野跑), 103: Track Run (田径场)
        # 200: Outdoor Cycling (骑行), 201: Indoor Cycling
        # 300: Pool Swim (泳池游泳), 301: Open Water Swim (公开水域游泳)
        # 400: Triathlon (铁人三项)
        # 500: Hike (徒步), 501: Walk (健走), 502: Mountain Climb (登山)
        # 600: Strength (力量训练), 601: Gym Cardio (室内健身)
        # 700: Ski / Snowboard (滑雪), 701: Cross Country Ski
        # 800: Rowing, 900: Jump Rope
        sport_type_code = act.get("sportType")
        type_map = {
            100: "Run",
            101: "Run",
            102: "Run",
            103: "Run",
            200: "Ride",
            201: "Ride",
            300: "Swim",
            301: "Swim",
            400: "Triathlon",
            500: "Hike",
            501: "Walk",
            502: "Climb",
            600: "Workout",
            601: "Workout",
            700: "Ski",
            701: "Ski",
            800: "Rowing",
            900: "JumpRope",
        }
        mapped_type = type_map.get(sport_type_code)
        if not mapped_type:
            act_name_raw = str(act.get("name") or act.get("activityName") or "")
            if "跑" in act_name_raw or "run" in act_name_raw.lower():
                mapped_type = "Run"
            elif "泳" in act_name_raw or "swim" in act_name_raw.lower():
                mapped_type = "Swim"
            elif "骑" in act_name_raw or "车" in act_name_raw or "bike" in act_name_raw.lower():
                mapped_type = "Ride"
            elif "徒步" in act_name_raw or "hike" in act_name_raw.lower():
                mapped_type = "Hike"
            elif "健走" in act_name_raw or "散步" in act_name_raw or "walk" in act_name_raw.lower():
                mapped_type = "Walk"
            else:
                mapped_type = "Workout"

        default_name = "COROS 跑步" if mapped_type == "Run" else f"COROS {mapped_type}"

        distance_m = float(act.get("distance", 0.0))
        # Total elapsed time (including pauses / rest intervals) in seconds
        duration_s = int(act.get("totalTime") or act.get("duration") or 0)
        # Active workout / moving time (excluding pauses / rest intervals) in seconds:
        # COROS API returns 'workoutTime' for active exercise duration.
        # Fallbacks: 'movingTime', 'sportTime', 'activeTime', and finally duration_s.
        raw_moving_time = (
            act.get("workoutTime")
            or act.get("movingTime")
            or act.get("sportTime")
            or act.get("activeTime")
        )
        if raw_moving_time is not None and int(raw_moving_time) > 0:
            moving_s = int(raw_moving_time)
            if duration_s > 0 and moving_s > duration_s:
                moving_s = duration_s
        else:
            moving_s = duration_s
        if duration_s == 0 and moving_s > 0:
            duration_s = moving_s

        # Parse start time: COROS returns Unix timestamp (either seconds or ms) or date string
        start_val = act.get("startTime") or act.get("date") or act.get("createTime")
        start_iso = datetime.utcnow().isoformat() + "Z"
        if start_val is not None:
            try:
                if isinstance(start_val, (int, float)):
                    # Check if milliseconds or seconds
                    ts = start_val / 1000.0 if start_val > 1e11 else float(start_val)
                    dt = datetime.fromtimestamp(ts)
                    start_iso = dt.isoformat() + "+08:00"
                elif isinstance(start_val, str):
                    if start_val.isdigit():
                        ts = float(start_val) / 1000.0 if float(start_val) > 1e11 else float(start_val)
                        dt = datetime.fromtimestamp(ts)
                        start_iso = dt.isoformat() + "+08:00"
                    elif "T" in start_val:
                        start_iso = start_val
                    else:
                        dt = datetime.strptime(start_val[:19], "%Y-%m-%d %H:%M:%S")
                        start_iso = dt.isoformat() + "+08:00"
            except Exception as te:
                logger.warning(f"[coros] Could not parse start time {start_val}: {te}")

        avg_speed = round(distance_m / moving_s, 3) if moving_s > 0 and distance_m > 0 else None
        max_speed = round(float(act.get("maxSpeed")), 3) if act.get("maxSpeed") else None
        avg_hr = act.get("avgHeartRate") or act.get("avgHr")
        max_hr = act.get("maxHeartRate") or act.get("maxHr")
        avg_cadence = act.get("avgCadence") or act.get("cadence")
        raw_ascent = act.get("ascent")
        if raw_ascent is not None:
            elev_gain = raw_ascent
        else:
            elev_gain = (
                act.get("elevGain")
                or act.get("elevationGain")
                or act.get("totalElevationGain")
                or 0.0
            )
        calories = act.get("calorie") or act.get("calories") or 0
        aerobic_te = act.get("aerobicEffect") or act.get("trainingLoad")
        anaerobic_te = act.get("anaerobicEffect")

        pace_display = pace_str(distance_m, moving_s)
        coros_avg_speed = act.get("avgSpeed")
        if sport_type_code in [100, 101, 102, 103] and coros_avg_speed is not None:
            try:
                speed_sec = float(coros_avg_speed)
                if speed_sec > 0:
                    tot_s = int(round(speed_sec))
                    pace_display = f"{tot_s // 60}:{tot_s % 60:02d} /km"
            except (ValueError, TypeError):
                pass

        return {
            "id": f"coros_{raw_id}",
            "source": f"coros_{'cn' if self.is_cn else 'global'}",
            "name": act.get("name") or act.get("activityName") or default_name,
            "activity_type": mapped_type,
            "sport_type": mapped_type,
            "start_time": start_iso,
            "distance_meters": distance_m,
            "moving_time_seconds": moving_s,
            "elapsed_time_seconds": duration_s,
            "average_speed_mps": avg_speed,
            "max_speed_mps": max_speed,
            "avg_pace_str": pace_display,
            "average_heartrate": int(avg_hr) if avg_hr else None,
            "max_heartrate": int(max_hr) if max_hr else None,
            "average_cadence": int(avg_cadence) if avg_cadence else None,
            "total_elevation_gain": round(float(elev_gain), 1),
            "elevation_gain_meters": round(float(elev_gain), 1),
            "calories": int(calories),
            "aerobic_training_effect": round(float(aerobic_te), 1) if aerobic_te else None,
            "anaerobic_training_effect": round(float(anaerobic_te), 1) if anaerobic_te else None,
            "splits": act.get("splits") or [],
            "laps": act.get("laps") or [],
            "splits_data": act.get("splits") or [],
            "laps_data": act.get("laps") or [],
            "coros_sport_type": sport_type_code,
            "map_image_url": act.get("imageUrl"),
            "raw_garmin_data": act, # Compatible key for DB/LocalStore JSONB storage
        }

    def fetch_sleep_data(self, start_date: str, end_date: str) -> Dict[str, Dict[str, Any]]:
        """
        [PROTECTED FOR USER APP SESSION SAFETY]
        Fetches sleep statistics only if an explicit non-conflicting token is already available.
        Does NOT attempt mobile_login, preventing any kickout of the user's official COROS App.
        """
        if not self.mobile_access_token:
            return self._sleep_cache

        try:
            start_int = int(start_date.replace("-", "")[:8])
            end_int = int(end_date.replace("-", "")[:8])
        except Exception:
            today = date.today()
            start_int = int((today - timedelta(days=14)).strftime("%Y%m%d"))
            end_int = int(today.strftime("%Y%m%d"))

        url = f"{self.mobile_base_url}/coros/data/statistic/daily?accessToken={self.mobile_access_token}"
        payload = {
            "allDeviceSleep": 1,
            "dataType": [5],
            "dataVersion": 0,
            "startTime": start_int,
            "endTime": end_int,
            "statisticType": 1,
        }
        headers = {
            "content-type": "application/json",
            "accesstoken": self.mobile_access_token,
            "user-agent": "okhttp/4.12.0",
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=12)
            if resp.status_code == 200:
                res_json = resp.json()
                if str(res_json.get("result")) in ["1019", "401", "1001"]:
                    logger.info(f"[coros] Mobile token expired/invalid. Not re-authenticating to protect mobile app session.")
                    self.mobile_access_token = None
                    return self._sleep_cache

                if str(res_json.get("result")) == "0000":
                    stat_data = res_json.get("data") or {}
                    day_list = (
                        stat_data.get("statisticData", {}).get("dayDataList")
                        or stat_data.get("dayDataList")
                        or []
                    )
                    for day_item in day_list:
                        day_int = day_item.get("happenDay") or day_item.get("date")
                        if not day_int:
                            continue
                        day_str = str(day_int)
                        if len(day_str) == 8:
                            date_key = f"{day_str[:4]}-{day_str[4:6]}-{day_str[6:]}"
                        else:
                            continue

                        sleep_data = day_item.get("sleepData") or {}
                        tot_minutes = int(sleep_data.get("totalSleepTime") or 0)
                        if tot_minutes <= 0:
                            continue

                        dur_seconds = tot_minutes * 60
                        dur_hours = round(tot_minutes / 60.0, 1)

                        deep_min = int(sleep_data.get("deepTime") or 0)
                        rem_min = int(sleep_data.get("eyeTime") or 0)
                        light_min = int(sleep_data.get("lightTime") or 0)
                        wake_min = int(sleep_data.get("wakeTime") or 0)

                        perf = day_item.get("performance")
                        if perf is not None and int(perf) > 0:
                            sleep_score = int(perf)
                        else:
                            # Realistic baseline sleep score based on duration & sleep phases
                            base_score = (min(tot_minutes, 480) / 480.0) * 75.0
                            deep_bonus = min(15.0, (deep_min / 60.0) * 15.0)
                            rem_bonus = min(10.0, (rem_min / 60.0) * 10.0)
                            wake_penalty = min(15.0, (wake_min / 30.0) * 10.0) if wake_min > 20 else 0.0
                            calc_score = int(round(base_score + deep_bonus + rem_bonus - wake_penalty))
                            sleep_score = max(45, min(99, calc_score))

                        self._sleep_cache[date_key] = {
                            "date": date_key,
                            "sleep_duration_seconds": dur_seconds,
                            "sleep_duration_hours": dur_hours,
                            "sleep_score": sleep_score,
                            "deep_sleep_seconds": deep_min * 60,
                            "rem_sleep_seconds": rem_min * 60,
                            "light_sleep_seconds": light_min * 60,
                            "awake_seconds": wake_min * 60,
                            "min_heart_rate": sleep_data.get("minHeartRate"),
                            "avg_heart_rate": sleep_data.get("avgHeartRate"),
                            "max_heart_rate": sleep_data.get("maxHeartRate"),
                        }
                    logger.info(f"[coros] Parsed and cached {len(self._sleep_cache)} sleep days for {self.account}")
        except Exception as e:
            logger.warning(f"[coros] Error fetching sleep data for {self.account}: {e}")

        return self._sleep_cache

    def fetch_daily_health_metrics(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetches daily health metrics from COROS.
        Combines:
        1. Mobile API sleep duration, stages, and sleep score
        2. EvoLab daily dynamic resting HR (rhr), stamina recovery (staminaLevel -> body_battery_max),
           VO2Max, and night sleep HRV (avgSleepHrv & sleepHrvBase)
        """
        date_str = target_date or date.today().isoformat()
        metrics: Dict[str, Any] = {
            "date": date_str,
            "source": f"coros_{'cn' if self.is_cn else 'global'}",
        }

        # 1. Read sleep data from cache if present (strictly no mobile login to protect phone app session)
        try:
            s_info = self._sleep_cache.get(date_str)
            if s_info:
                metrics["sleep_duration_seconds"] = s_info.get("sleep_duration_seconds")
                metrics["sleep_duration_hours"] = s_info.get("sleep_duration_hours")
                metrics["sleep_score"] = s_info.get("sleep_score")
                if s_info.get("min_heart_rate"):
                    metrics["resting_heart_rate"] = int(s_info["min_heart_rate"])
                    metrics["hr_min"] = int(s_info["min_heart_rate"])
                if s_info.get("max_heart_rate"):
                    metrics["hr_max"] = int(s_info["max_heart_rate"])
        except Exception as se:
            logger.warning(f"[coros] Failed to fetch sleep for {date_str}: {se}")

        # 2. EvoLab daily analysis (rhr, staminaLevel, HRV, VO2Max)
        try:
            a_data = self._get_analyse_data()
            if a_data:
                day_list = a_data.get("dayList") or a_data.get("t7dayList") or []
                target_day_int = None
                try:
                    target_day_int = int(date_str.replace("-", "")[:8])
                except Exception:
                    pass

                matched_item = None
                if target_day_int:
                    for item in day_list:
                        if item.get("happenDay") == target_day_int:
                            matched_item = item
                            break

                if matched_item:
                    if matched_item.get("steps") and int(matched_item["steps"]) > 0:
                        metrics["steps"] = int(matched_item["steps"])
                    if matched_item.get("activeCalories") and float(matched_item["activeCalories"]) > 0:
                        metrics["active_calories"] = int(round(float(matched_item["activeCalories"])))
                    if matched_item.get("napTime") and int(matched_item["napTime"]) > 0:
                        metrics["nap_duration_seconds"] = int(matched_item["napTime"]) * 60
                    if matched_item.get("vo2max") and float(matched_item["vo2max"]) > 0:
                        metrics["vo2_max"] = round(float(matched_item["vo2max"]), 1)
                    if matched_item.get("tiredRate") is not None:
                        try:
                            tr = float(matched_item["tiredRate"])
                            if tr > 0:
                                metrics["stress_avg"] = min(100, max(10, int(round(tr))))
                        except (ValueError, TypeError):
                            pass

                    avg_sleep_hrv = matched_item.get("avgSleepHrv")
                    has_overnight_sleep = bool(
                        (avg_sleep_hrv and float(avg_sleep_hrv) > 0)
                        or (metrics.get("sleep_duration_seconds") and float(metrics.get("sleep_duration_seconds") or 0) > 0)
                    )

                    # Only accept RHR, HRV, Stamina/BodyBattery, and Sleep Score if watch was worn overnight
                    if has_overnight_sleep:
                        if matched_item.get("rhr") and int(matched_item["rhr"]) > 0:
                            metrics["resting_heart_rate"] = int(matched_item["rhr"])

                        stamina_val = matched_item.get("staminaLevel")
                        if stamina_val is not None:
                            try:
                                stamina = float(stamina_val)
                                if stamina > 0:
                                    bb_val = min(100, max(0, int(round(stamina))))
                                    metrics["body_battery_max"] = bb_val
                                    metrics["body_battery_current"] = bb_val
                            except (ValueError, TypeError):
                                pass

                        if avg_sleep_hrv and float(avg_sleep_hrv) > 0:
                            metrics["hrv_last_night_avg"] = int(avg_sleep_hrv)
                            if matched_item.get("sleepHrvBase") and float(matched_item["sleepHrvBase"]) > 0:
                                metrics["hrv_weekly_avg"] = int(matched_item["sleepHrvBase"])

                        # HRV Status
                        if metrics.get("hrv_last_night_avg") and metrics.get("hrv_weekly_avg"):
                            ratio = metrics["hrv_last_night_avg"] / float(metrics["hrv_weekly_avg"])
                            if 0.85 <= ratio <= 1.15:
                                metrics["hrv_status"] = "balanced"
                            elif ratio < 0.85:
                                metrics["hrv_status"] = "low"
                            else:
                                metrics["hrv_status"] = "unbalanced"

                        # 2.3 Sleep Quality Score from EvoLab Night HRV (ONLY when avgSleepHrv was actually measured overnight)
                        if metrics.get("sleep_score") is None and avg_sleep_hrv and float(avg_sleep_hrv) > 0:
                            hrv_base = matched_item.get("sleepHrvBase")
                            intervals = matched_item.get("sleepHrvIntervalList") or []
                            rhr = metrics.get("resting_heart_rate")
                            test_rhr = matched_item.get("testRhr")
                            tired_rate = matched_item.get("tiredRate")
                            tib = matched_item.get("tib")

                            base_score = None
                            if hrv_base and float(hrv_base) > 0:
                                h_ratio = float(avg_sleep_hrv) / float(hrv_base)
                                if h_ratio >= 1.0:
                                    base_score = 82.0 + min(15.0, (h_ratio - 1.0) * 80.0)
                                else:
                                    base_score = 82.0 - min(35.0, (1.0 - h_ratio) * 110.0)
                            elif intervals and len(intervals) >= 4:
                                if avg_sleep_hrv >= intervals[2]:
                                    base_score = 82.0 + min(12.0, (avg_sleep_hrv - intervals[2]) / max(1.0, intervals[3] - intervals[2]) * 10.0)
                                elif avg_sleep_hrv >= intervals[1]:
                                    base_score = 70.0 + (avg_sleep_hrv - intervals[1]) / max(1.0, intervals[2] - intervals[1]) * 12.0
                                else:
                                    base_score = 55.0

                            if base_score is not None:
                                rhr_mod = 0.0
                                if rhr and rhr > 0:
                                    if rhr <= 40:
                                        rhr_mod = 3.0
                                    elif rhr <= 45:
                                        rhr_mod = 1.5
                                    elif rhr >= 60:
                                        rhr_mod = -4.0
                                    elif rhr >= 54:
                                        rhr_mod = -2.0

                                    if test_rhr and test_rhr > rhr:
                                        dip = test_rhr - rhr
                                        if dip >= 8:
                                            rhr_mod += 1.5
                                        elif dip <= 2:
                                            rhr_mod -= 1.0

                                tired_mod = 0.0
                                if tired_rate is not None:
                                    try:
                                        tr = float(tired_rate)
                                        if tr < 42:
                                            tired_mod = 2.5
                                        elif tr < 48:
                                            tired_mod = 1.0
                                        elif tr > 65:
                                            tired_mod = -3.5
                                        elif tr > 55:
                                            tired_mod = -2.0
                                    except (ValueError, TypeError):
                                        pass

                                if tib is not None:
                                    try:
                                        tib_val = float(tib)
                                        if tib_val > 5:
                                            tired_mod += 1.5
                                        elif tib_val < -15:
                                            tired_mod -= 2.0
                                    except (ValueError, TypeError):
                                        pass

                                calc_score = int(round(base_score + rhr_mod + tired_mod))
                                metrics["sleep_score"] = max(50, min(98, calc_score))
        except Exception as ae:
            logger.warning(f"[coros] Error fetching EvoLab analyse data for {date_str}: {ae}")

        # 3. Fallback to profile metrics ONLY if watch was worn overnight (for RHR) or for VO2Max
        has_overnight = bool(
            (metrics.get("hrv_last_night_avg") and float(metrics.get("hrv_last_night_avg") or 0) > 0)
            or (metrics.get("sleep_duration_seconds") and float(metrics.get("sleep_duration_seconds") or 0) > 0)
        )
        try:
            if (has_overnight and not metrics.get("resting_heart_rate")) or not metrics.get("vo2_max"):
                profile_info = self.fetch_user_profile_info()
                if has_overnight and not metrics.get("resting_heart_rate") and profile_info.get("resting_heart_rate"):
                    metrics["resting_heart_rate"] = profile_info["resting_heart_rate"]
                if not metrics.get("vo2_max") and profile_info.get("vo2max"):
                    metrics["vo2_max"] = profile_info["vo2max"]
        except Exception as pe:
            logger.warning(f"[coros] Error fetching fallback profile info: {pe}")

        return metrics

    @staticmethod
    def _normalize_coros_lap_item(item: Dict[str, Any], default_idx: int) -> Optional[Dict[str, Any]]:
        if not isinstance(item, dict):
            return None
        dist_cm = float(item.get("distance") or 0.0)
        time_cs = float(item.get("time") or item.get("totalLength") or 0.0)
        dist_m = round(dist_cm / 100.0, 1)
        dur_s = round(time_cs / 100.0, 1)
        if dist_m <= 1.0 and dur_s <= 1.0:
            return None

        raw_pace = item.get("avgPace") or item.get("avgMoveSpeed") or item.get("avgSpeed")
        p_sec: Optional[int] = None
        if raw_pace is not None:
            try:
                pv = float(raw_pace)
                if 90 <= pv <= 1200:
                    p_sec = int(round(pv))
            except (ValueError, TypeError):
                pass
        if p_sec is None and dist_m >= 20.0 and dur_s > 0:
            calc_p = int(round(dur_s / (dist_m / 1000.0)))
            if 90 <= calc_p <= 1200:
                p_sec = calc_p

        gap_raw = item.get("adjustedPace")
        gap_sec: Optional[int] = None
        if gap_raw is not None:
            try:
                gv = float(gap_raw)
                if 90 <= gv <= 1200:
                    gap_sec = int(round(gv))
            except (ValueError, TypeError):
                pass

        # COROS sportStage / intensityType: 1=warmup, 2=active/main, 3=recovery/rest, 4=cooldown
        stage_code = int(item.get("sportStage") or item.get("intensityType") or 0)
        if stage_code == 1:
            itype = "WARMUP"
        elif stage_code == 2:
            itype = "ACTIVE"
        elif stage_code == 3:
            itype = "RECOVERY"
        elif stage_code == 4:
            itype = "COOLDOWN"
        else:
            itype = "AUTO"

        avg_hr = item.get("avgHr")
        max_hr = item.get("maxHr")
        cad = item.get("avgCadence")
        pwr = item.get("avgPower")

        return {
            "lap_index": int(item.get("lapIndex") or default_idx),
            "distance_m": dist_m,
            "duration_s": dur_s,
            "elapsed_s": round((dur_s + float(item.get("pauseTime") or 0.0) / 100.0), 1),
            "pace_sec": p_sec,
            "pace_str": f"{p_sec // 60}:{p_sec % 60:02d}/km" if p_sec else "—",
            "gap_sec": gap_sec,
            "avg_hr": int(round(float(avg_hr))) if avg_hr else None,
            "max_hr": int(round(float(max_hr))) if max_hr else None,
            "avg_cadence": int(round(float(cad))) if cad else None,
            "avg_power": int(round(float(pwr))) if pwr else None,
            "elev_gain_m": round(float(item.get("elevGain") or 0.0), 1),
            "elev_loss_m": round(float(item.get("totalDescent") or 0.0), 1),
            "intensity_type": itype,
        }

    def fetch_activity_gps_track(
        self,
        activity_id: str,
        sport_type_hint: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches GPS polyline (GCJ-02), elevation profile, 1Hz telemetry stream, and lap/1km splits
        for a COROS activity via Web Training Hub (/activity/detail/query).
        Strictly uses Web accessToken (trigger_2fa_sms=False) with zero mobile session disruption.
        """
        try:
            from utils.geo_utils import wgs84_to_gcj02, downsample_points
        except ImportError:
            try:
                from .geo_utils import wgs84_to_gcj02, downsample_points
            except ImportError:
                wgs84_to_gcj02 = lambda lat, lng: (lat, lng)
                downsample_points = lambda pts, max_points=250: pts

        clean_id = str(activity_id).replace("coros_", "").strip()
        if not clean_id:
            return None

        if not self.access_token and not self.login(trigger_2fa_sms=False):
            return None

        candidate_types = []
        if sport_type_hint in (100, 101, 102, 103):
            candidate_types.append(int(sport_type_hint))
        for st in (100, 102, 103, 101):
            if st not in candidate_types:
                candidate_types.append(st)

        detail_data: Optional[Dict[str, Any]] = None
        for st in candidate_types:
            url = f"{self.base_url}/activity/detail/query?labelId={clean_id}&sportType={st}"
            payload = {"labelId": clean_id, "sportType": st}
            try:
                resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=15)
                if resp.status_code != 200:
                    continue
                res_json = resp.json()
                res_code = str(res_json.get("result", ""))
                if res_code in ("1019", "401", "1001"):
                    self.access_token = None
                    if self.refresh_access_token() or self.login(trigger_2fa_sms=False):
                        resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=15)
                        if resp.status_code == 200:
                            res_json = resp.json()
                            res_code = str(res_json.get("result", ""))
                if res_code == "0000" and isinstance(res_json.get("data"), dict):
                    cand = res_json["data"]
                    if cand.get("frequencyList") or cand.get("lapList"):
                        detail_data = cand
                        break
            except Exception as e:
                logger.warning(f"[coros] /activity/detail/query ({clean_id}, st={st}) warning: {e}")

        if not detail_data:
            logger.info(f"[coros] No detail data returned for activity {clean_id}")
            return None

        freq_list = detail_data.get("frequencyList") or []
        gcj_points: List[Dict[str, float]] = []
        raw_profile: List[Dict[str, Any]] = []
        raw_telemetry: List[Dict[str, Any]] = []

        t0_cs: Optional[float] = None
        for pt in freq_list:
            if not isinstance(pt, dict):
                continue
            ts_val = pt.get("timestamp")
            if ts_val is not None and t0_cs is None:
                try:
                    t0_cs = float(ts_val)
                except (ValueError, TypeError):
                    pass

            lat_i = pt.get("gpsLat")
            lon_i = pt.get("gpsLon")
            if lat_i and lon_i:
                try:
                    lat_f = float(lat_i) / 1e7 if abs(float(lat_i)) > 1000 else float(lat_i)
                    lon_f = float(lon_i) / 1e7 if abs(float(lon_i)) > 1000 else float(lon_i)
                    if -90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0 and (abs(lat_f) > 0.01 or abs(lon_f) > 0.01):
                        g_lat, g_lng = wgs84_to_gcj02(lat_f, lon_f)
                        gcj_points.append({"latitude": round(g_lat, 6), "longitude": round(g_lng, 6)})
                except (ValueError, TypeError):
                    pass

            dist_cm = pt.get("distance")
            if dist_cm is not None:
                try:
                    dist_km = round(float(dist_cm) / 100000.0, 3)
                except (ValueError, TypeError):
                    dist_km = None
            else:
                dist_km = None

            elap_s = None
            if ts_val is not None and t0_cs is not None:
                try:
                    elap_s = round(max(0.0, (float(ts_val) - t0_cs) / 100.0), 1)
                except (ValueError, TypeError):
                    pass

            spd = pt.get("speed")
            p_sec = int(round(float(spd))) if (spd is not None and 90 <= float(spd) <= 1200) else None
            gap_v = pt.get("adjustedPace")
            g_sec = int(round(float(gap_v))) if (gap_v is not None and 90 <= float(gap_v) <= 1200) else None
            hr_v = pt.get("heart")
            hr_int = int(round(float(hr_v))) if (hr_v is not None and 35 <= float(hr_v) <= 235) else None
            cad_v = pt.get("cadence")
            cad_int = int(round(float(cad_v))) if (cad_v is not None and 80 <= float(cad_v) <= 250) else None
            alt_v = pt.get("altitude")
            elev_m = round(float(alt_v), 1) if alt_v is not None else None

            if dist_km is not None:
                if elev_m is not None:
                    raw_profile.append({
                        "dist_km": round(dist_km, 2),
                        "elevation_m": elev_m,
                        "hr": hr_int,
                        "pace_sec": p_sec,
                    })
                raw_telemetry.append({
                    "dist_km": dist_km,
                    "elapsed_s": elap_s,
                    "pace_sec": p_sec,
                    "gap_sec": g_sec,
                    "hr": hr_int,
                    "cadence": cad_int,
                    "elevation_m": elev_m,
                })

        sampled_points = downsample_points(gcj_points, max_points=250) if gcj_points else []
        sampled_elevation = downsample_points(raw_profile, max_points=120) if raw_profile else []
        sampled_telemetry = downsample_points(raw_telemetry, max_points=240) if raw_telemetry else []

        # Parse lapList groups:
        # type 0 / 1 = manual / structured workout laps; type 2 (lapDistance=100000) = 1km auto splits
        km_splits: List[Dict[str, Any]] = []
        structured_laps: List[Dict[str, Any]] = []
        for lg in detail_data.get("lapList") or []:
            if not isinstance(lg, dict):
                continue
            lg_type = lg.get("type")
            lg_dist = int(lg.get("lapDistance") or 0)
            items = lg.get("lapItemList") or []
            parsed_items = []
            for idx, it in enumerate(items, start=1):
                norm_it = self._normalize_coros_lap_item(it, idx)
                if norm_it:
                    parsed_items.append(norm_it)
            if not parsed_items:
                continue
            if lg_type == 2 or lg_dist == 100000:
                km_splits = parsed_items
            elif lg_type in (0, 1) and len(parsed_items) >= 2:
                structured_laps = parsed_items

        primary_laps = structured_laps if structured_laps else km_splits
        if not sampled_points and not sampled_telemetry and not primary_laps:
            return None

        track_data: Dict[str, Any] = {
            "activity_id": f"coros_{clean_id}",
            "has_gps_points": len(sampled_points) >= 2,
            "total_points": len(sampled_points),
            "original_point_count": len(gcj_points),
            "points": sampled_points,
            "elevation_profile": sampled_elevation,
            "telemetry_series": sampled_telemetry,
            "laps": primary_laps,
            "km_splits": km_splits or primary_laps,
            "structured_splits": structured_laps,
        }
        if sampled_points:
            min_lat = min(p["latitude"] for p in sampled_points)
            max_lat = max(p["latitude"] for p in sampled_points)
            min_lng = min(p["longitude"] for p in sampled_points)
            max_lng = max(p["longitude"] for p in sampled_points)
            track_data["center"] = {
                "latitude": round((min_lat + max_lat) / 2.0, 6),
                "longitude": round((min_lng + max_lng) / 2.0, 6),
            }
            track_data["bounds"] = {
                "southwest": {"latitude": min_lat, "longitude": min_lng},
                "northeast": {"latitude": max_lat, "longitude": max_lng},
            }
            track_data["start_point"] = sampled_points[0]
            track_data["end_point"] = sampled_points[-1]

        logger.info(
            f"[coros] Processed detail for {clean_id}: {len(sampled_points)} GPS pts, "
            f"{len(primary_laps)} laps, {len(sampled_telemetry)} telemetry steps"
        )
        return track_data


def remove_cached_coros_tokens(account: Optional[str]):
    """Removes any cached COROS web and mobile token files for the given account."""
    if not account:
        return
    safe_acc = account.replace("@", "_at_").replace(".", "_").replace("+", "_")
    for region_str in ["cn", "global", "eu"]:
        for prefix in ["tokens_coros_", "tokens_coros_mobile_"]:
            p = os.path.join(TOKEN_DIR, f"{prefix}{safe_acc}_{region_str}.json")
            if os.path.exists(p):
                try:
                    os.remove(p)
                    logger.info(f"[coros] Removed cached token file: {p}")
                except Exception as e:
                    logger.warning(f"[coros] Could not remove token file {p}: {e}")
