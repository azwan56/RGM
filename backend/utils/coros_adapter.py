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

        os.makedirs(TOKEN_DIR, exist_ok=True)
        safe_acc = self.account.replace("@", "_at_").replace(".", "_").replace("+", "_")
        region_str = "cn" if self.is_cn else ("eu" if self.is_eu else "global")
        self.token_path = os.path.join(TOKEN_DIR, f"tokens_coros_{safe_acc}_{region_str}.json")
        self.mobile_token_path = os.path.join(TOKEN_DIR, f"tokens_coros_mobile_{safe_acc}_{region_str}.json")
        self._load_cached_token()
        self._load_cached_mobile_token()

    def _load_cached_token(self) -> bool:
        """Attempts to load cached access token if file exists and has not expired."""
        if not os.path.exists(self.token_path):
            return False
        try:
            with open(self.token_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                token = data.get("access_token")
                saved_at = data.get("saved_at", 0)
                # Tokens usually valid for at least 7-30 days; we use 14 days conservatively
                if token and (time.time() - saved_at < 14 * 86400):
                    self.access_token = token
                    self.user_id = data.get("user_id")
                    self.nick_name = data.get("nick_name")
                    self.avatar_url = data.get("avatar_url")
                    return True
        except Exception as e:
            logger.warning(f"[coros] Failed to read cached token: {e}")
        return False

    def _save_cached_token(self):
        """Persists access token to disk."""
        if not self.access_token:
            return
        try:
            with open(self.token_path, "w", encoding="utf-8") as f:
                json.dump({
                    "access_token": self.access_token,
                    "user_id": self.user_id,
                    "nick_name": self.nick_name,
                    "avatar_url": self.avatar_url,
                    "saved_at": time.time()
                }, f)
        except Exception as e:
            logger.warning(f"[coros] Failed to save token cache: {e}")

    def _load_cached_mobile_token(self) -> bool:
        """Attempts to load cached mobile access token."""
        if not os.path.exists(self.mobile_token_path):
            return False
        try:
            with open(self.mobile_token_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                token = data.get("access_token")
                saved_at = data.get("saved_at", 0)
                if token and (time.time() - saved_at < 14 * 86400):
                    self.mobile_access_token = token
                    return True
        except Exception as e:
            logger.warning(f"[coros] Failed to read mobile cached token: {e}")
        return False

    def _save_cached_mobile_token(self):
        """Persists mobile access token to disk."""
        if not self.mobile_access_token:
            return
        try:
            with open(self.mobile_token_path, "w", encoding="utf-8") as f:
                json.dump({
                    "access_token": self.mobile_access_token,
                    "saved_at": time.time()
                }, f)
        except Exception as e:
            logger.warning(f"[coros] Failed to save mobile token cache: {e}")

    def mobile_login(self, override_account: Optional[str] = None, override_type: Optional[int] = None) -> bool:
        """
        Logs into COROS Mobile API using AES-encrypted credentials.
        Required for daily sleep statistics and other mobile-only wellness data.
        Handles both email (accountType=2) and mobile numbers (accountType=1, requires +86- for CN).
        """
        if self.mobile_access_token:
            logger.info(f"[coros] Using cached mobile token for {self.account}")
            return True

        target_acc = (override_account or self.account).strip()
        if override_type is not None:
            account_type = override_type
            mobile_acc = target_acc
        elif "@" in target_acc:
            mobile_acc = target_acc
            account_type = 2
        elif target_acc.isdigit() and len(target_acc) == 11 and self.is_cn:
            mobile_acc = f"+86-{target_acc}"
            account_type = 1
        elif target_acc.startswith("+"):
            mobile_acc = target_acc
            account_type = 1
        else:
            mobile_acc = target_acc
            account_type = 1 if target_acc.replace("-", "").isdigit() else 2

        login_url = f"{self.mobile_base_url}/coros/user/login"
        app_key = str(random.randint(1_000_000_000_000_000, 9_999_999_999_999_999))
        pwd_md5 = hashlib.md5(self.password.encode("utf-8")).hexdigest()

        payload = {
            "account": _encrypt_mobile_param(mobile_acc, app_key) + "\n",
            "accountType": account_type,
            "appKey": app_key,
            "clientType": 1,
            "hasHrCalibrated": 0,
            "kbValidity": 0,
            "pwd": _encrypt_mobile_param(pwd_md5, app_key) + "\n",
            "region": "460|Asia/Shanghai|CN" if self.is_cn else "840|America/New_York|US",
            "skipValidation": False,
        }

        yfheader = json.dumps({
            "appVersion": 1125917087236096,
            "clientType": 1,
            "language": "zh-CN" if self.is_cn else "en-US",
            "mobileName": "sdk_gphone64_arm64,google,Google",
            "releaseType": 1,
            "systemVersion": "13",
            "timezone": 8 if self.is_cn else -5,
            "versionCode": "404080400",
        }, separators=(",", ":"))

        headers = {
            "content-type": "application/json",
            "accept-encoding": "gzip",
            "user-agent": "okhttp/4.12.0",
            "request-time": str(int(time.time() * 1000)),
            "yfheader": yfheader,
        }

        try:
            logger.info(f"[coros] Attempting mobile login for {mobile_acc} (type={account_type}, {self.mobile_base_url})...")
            resp = requests.post(login_url, json=payload, headers=headers, timeout=12)
            if resp.status_code == 200:
                res_json = resp.json()
                if str(res_json.get("result")) == "0000":
                    data = res_json.get("data") or {}
                    self.mobile_access_token = data.get("accessToken")
                    if self.mobile_access_token:
                        self._save_cached_mobile_token()
                        logger.info(f"[coros] Mobile login success for {self.account}")
                        return True

                # If account not registered (1029) and we haven't overridden yet, try fallback via training hub
                res_code = str(res_json.get("result"))
                if res_code == "1029" and override_account is None:
                    try:
                        if not self.access_token:
                            self.login()
                        if self.access_token and self.user_id:
                            acc_resp = requests.get(
                                f"{self.base_url}/account/query?userId={self.user_id}",
                                headers=self._get_headers(),
                                timeout=8
                            )
                            if acc_resp.status_code == 200:
                                p_data = acc_resp.json().get("data") or {}
                                alt_email = p_data.get("email")
                                alt_mobile = p_data.get("mobile")
                                if alt_email and alt_email != self.account:
                                    logger.info(f"[coros] Retrying mobile login with profile email: {alt_email}")
                                    return self.mobile_login(override_account=alt_email, override_type=2)
                                elif alt_mobile and alt_mobile != self.account:
                                    logger.info(f"[coros] Retrying mobile login with profile mobile: {alt_mobile}")
                                    return self.mobile_login(override_account=alt_mobile, override_type=1)
                    except Exception as fe:
                        logger.warning(f"[coros] Mobile fallback query failed: {fe}")

                logger.warning(f"[coros] Mobile login rejected: {res_json.get('result')} {res_json.get('message')}")
            else:
                logger.warning(f"[coros] Mobile login HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"[coros] Mobile login exception for {self.account}: {e}")
        return False

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://t.coros.com",
            "referer": "https://t.coros.com/",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }
        if self.access_token:
            headers["accesstoken"] = self.access_token
            headers["cookie"] = f"CPL-coros-region=2; CPL-coros-token={self.access_token}"
        return headers

    def login(self) -> bool:
        """
        Logs into COROS Training Hub with MD5 encrypted password.
        Uses cached token if available and tests validity.
        """
        if self.access_token:
            # Verify cached token with lightweight query
            if self._verify_token():
                logger.info(f"[coros] Using valid cached token for {self.account}")
                self.last_error = None
                return True
            else:
                logger.info(f"[coros] Cached token expired for {self.account}, re-authenticating...")

        login_url = f"{self.base_url}/account/login"
        # COROS requires MD5 of password
        pwd_md5 = hashlib.md5(self.password.encode("utf-8")).hexdigest()
        payload = {
            "account": self.account,
            "accountType": 2,
            "pwd": pwd_md5
        }

        try:
            logger.info(f"[coros] Attempting login for {self.account} ({self.base_url})...")
            resp = requests.post(login_url, json=payload, headers=self._get_headers(), timeout=15)
            if resp.status_code != 200:
                self.last_error = f"COROS 登录接口返回 HTTP {resp.status_code}"
                logger.error(f"[coros] Login failed HTTP {resp.status_code}: {resp.text}")
                return False

            res_json = resp.json()
            # Result code "0000" signifies success in COROS API
            result_code = str(res_json.get("result", ""))
            if result_code != "0000":
                msg = res_json.get("message") or "账号或密码错误"
                self.last_error = f"高驰登录失败：{msg}"
                logger.warning(f"[coros] Login rejected: {res_json}")
                return False

            data = res_json.get("data") or {}
            self.access_token = data.get("accessToken")
            self.user_id = str(data.get("userId") or "")
            self.nick_name = data.get("nickName")
            self.avatar_url = data.get("headPic")

            if not self.access_token:
                self.last_error = "登录成功但未能解析到访问凭证 (accessToken)"
                return False

            self._save_cached_token()
            self.last_error = None
            logger.info(f"[coros] Login success for {self.account}, userId={self.user_id}")
            return True
        except Exception as e:
            self.last_error = f"连接高驰服务器失败: {str(e)}"
            logger.error(f"[coros] Login exception for {self.account}: {e}")
            return False

    def _verify_token(self) -> bool:
        """Checks if current access token is valid by querying activity count."""
        try:
            url = f"{self.base_url}/activity/query?pageNumber=1&size=1"
            resp = requests.get(url, headers=self._get_headers(), timeout=8)
            if resp.status_code == 200:
                res_json = resp.json()
                return str(res_json.get("result")) == "0000"
        except Exception:
            pass
        return False

    def _get_analyse_data(self) -> Optional[Dict[str, Any]]:
        """Queries or returns cached EvoLab analyse data."""
        if not self.access_token and not self.login():
            return None
        now = time.time()
        if self._analyse_cache and (now - self._analyse_cache_time < 300):
            return self._analyse_cache
        try:
            url = f"{self.base_url}/analyse/query?userId={self.user_id}"
            resp = requests.get(url, headers=self._get_headers(), timeout=12)
            if resp.status_code == 200:
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

        if not self.access_token and not self.login():
            return info

        # 1. Query account for biometrics & personal info
        try:
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
        if not self.access_token and not self.login():
            return []

        try:
            # 100: Outdoor Run, 101: Indoor/Treadmill, 102: Trail Run, 103: Track Run
            url = f"{self.base_url}/activity/query?modeList=100,101,102,103&pageNumber=1&size={limit}"
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            if resp.status_code != 200:
                logger.error(f"[coros] Query activities failed HTTP {resp.status_code}")
                return []

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
        if not self.access_token and not self.login():
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
        sport_type_code = act.get("sportType") or 100
        type_map = {
            100: "Run",
            101: "Run",
            102: "Run",
            103: "Run",
            200: "Ride",
            300: "Swim",
        }
        mapped_type = type_map.get(sport_type_code, "Run")

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
        avg_cadence = act.get("avgCadence")
        elev_gain = act.get("elevationGain") or act.get("totalElevationGain") or 0.0
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
            "name": act.get("name") or act.get("activityName") or "COROS 跑步",
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
            "map_image_url": act.get("imageUrl"),
            "raw_garmin_data": act, # Compatible key for DB/LocalStore JSONB storage
        }

    def fetch_sleep_data(self, start_date: str, end_date: str) -> Dict[str, Dict[str, Any]]:
        """
        Fetches sleep statistics between start_date and end_date (inclusive, YYYY-MM-DD).
        Returns a dict mapping "YYYY-MM-DD" to normalized sleep metrics.
        Caches results in self._sleep_cache.
        """
        if not self.mobile_access_token and not self.mobile_login():
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
                # If mobile token expired, refresh and retry once
                if str(res_json.get("result")) in ["1019", "401", "1001"]:
                    logger.info(f"[coros] Mobile token expired, re-authenticating...")
                    self.mobile_access_token = None
                    if self.mobile_login():
                        url = f"{self.mobile_base_url}/coros/data/statistic/daily?accessToken={self.mobile_access_token}"
                        headers["accesstoken"] = self.mobile_access_token
                        resp = requests.post(url, json=payload, headers=headers, timeout=12)
                        res_json = resp.json()

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

        # 1. Fetch sleep data from mobile API (pre-fill cache with 14-day window)
        try:
            if date_str not in self._sleep_cache:
                t_dt = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
                s_window = (t_dt - timedelta(days=14)).isoformat()
                e_window = (t_dt + timedelta(days=1)).isoformat()
                self.fetch_sleep_data(s_window, e_window)

            s_info = self._sleep_cache.get(date_str)
            if s_info:
                metrics["sleep_duration_seconds"] = s_info.get("sleep_duration_seconds")
                metrics["sleep_duration_hours"] = s_info.get("sleep_duration_hours")
                metrics["sleep_score"] = s_info.get("sleep_score")
                if s_info.get("min_heart_rate"):
                    metrics["resting_heart_rate"] = int(s_info["min_heart_rate"])
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

                # Fallback to latest item if matching today and today's day record isn't generated yet
                if not matched_item and day_list and date_str == date.today().isoformat():
                    matched_item = day_list[-1]

                if matched_item:
                    # Daily measured resting HR (more accurate than static profile)
                    if matched_item.get("rhr") and int(matched_item["rhr"]) > 0:
                        metrics["resting_heart_rate"] = int(matched_item["rhr"])
                    elif not metrics.get("resting_heart_rate") and matched_item.get("testRhr"):
                        metrics["resting_heart_rate"] = int(matched_item["testRhr"])

                    # Stamina level (0-100) maps directly to body battery / recovery
                    if matched_item.get("staminaLevel") is not None:
                        try:
                            stamina = float(matched_item["staminaLevel"])
                            if stamina >= 0:
                                metrics["body_battery_max"] = min(100, max(0, int(round(stamina))))
                        except (ValueError, TypeError):
                            pass

                    if matched_item.get("avgSleepHrv"):
                        metrics["hrv_last_night_avg"] = int(matched_item["avgSleepHrv"])
                    if matched_item.get("sleepHrvBase"):
                        metrics["hrv_weekly_avg"] = int(matched_item["sleepHrvBase"])
                    if matched_item.get("vo2max") and float(matched_item["vo2max"]) > 0:
                        metrics["vo2_max"] = round(float(matched_item["vo2max"]), 1)

                    # HRV Status
                    if metrics.get("hrv_last_night_avg") and metrics.get("hrv_weekly_avg"):
                        ratio = metrics["hrv_last_night_avg"] / float(metrics["hrv_weekly_avg"])
                        if 0.85 <= ratio <= 1.15:
                            metrics["hrv_status"] = "balanced"
                        elif ratio < 0.85:
                            metrics["hrv_status"] = "low"
                        else:
                            metrics["hrv_status"] = "unbalanced"
        except Exception as ae:
            logger.warning(f"[coros] Error fetching EvoLab analyse data for {date_str}: {ae}")

        # 3. Fallback to profile metrics if resting_heart_rate or vo2_max still missing
        try:
            if not metrics.get("resting_heart_rate") or not metrics.get("vo2_max"):
                profile_info = self.fetch_user_profile_info()
                if not metrics.get("resting_heart_rate") and profile_info.get("resting_heart_rate"):
                    metrics["resting_heart_rate"] = profile_info["resting_heart_rate"]
                if not metrics.get("vo2_max") and profile_info.get("vo2max"):
                    metrics["vo2_max"] = profile_info["vo2max"]
        except Exception as pe:
            logger.warning(f"[coros] Error fetching fallback profile info: {pe}")

        return metrics
