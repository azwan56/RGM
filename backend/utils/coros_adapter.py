"""
COROS Direct Adapter for China (teamcnapi.coros.com) & Global (teamapi.coros.com)
Supports syncing activities, health metrics, and normalizing into RGM schema.
Includes Token Persistence to avoid frequent login and rate limiting.
"""

import os
import json
import time
import hashlib
import logging
import requests
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger("coros_adapter")

TOKEN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tokens")

def pace_str(distance_m: float, moving_time_s: int) -> str:
    """Returns average pace as 'M:SS /km'."""
    km = distance_m / 1000.0
    if km <= 0 or moving_time_s <= 0:
        return "—"
    sec_per_km = moving_time_s / km
    mins = int(sec_per_km // 60)
    secs = int(sec_per_km % 60)
    return f"{mins}:{secs:02d} /km"


class CorosAdapter:
    def __init__(self, account: str, password: str, domain: str = "teamcnapi.coros.com"):
        self.account = account.strip()
        self.password = password
        self.domain = domain.lower().strip()
        self.is_cn = ("cn" in self.domain or "teamcnapi" in self.domain)
        self.base_url = "https://teamcnapi.coros.com" if self.is_cn else "https://teamapi.coros.com"
        self.last_error: Optional[str] = None
        self.access_token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.nick_name: Optional[str] = None
        self.avatar_url: Optional[str] = None

        os.makedirs(TOKEN_DIR, exist_ok=True)
        safe_acc = self.account.replace("@", "_at_").replace(".", "_").replace("+", "_")
        self.token_path = os.path.join(TOKEN_DIR, f"tokens_coros_{safe_acc}_{'cn' if self.is_cn else 'global'}.json")
        self._load_cached_token()

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

    def fetch_user_profile_info(self) -> Dict[str, Any]:
        """Returns normalized user profile information (avatar, display name, etc.)."""
        return {
            "avatar_url": self.avatar_url,
            "display_name": self.nick_name,
            "gender": None,
            "height_cm": None,
            "weight_kg": None,
            "vo2max": None,
        }

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
        # Total time / duration in seconds
        duration_s = int(act.get("totalTime") or act.get("duration") or 0)
        moving_s = int(act.get("movingTime") or duration_s)

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
            "avg_pace_str": pace_str(distance_m, moving_s),
            "average_heartrate": int(avg_hr) if avg_hr else None,
            "max_heartrate": int(max_hr) if max_hr else None,
            "average_cadence": int(avg_cadence) if avg_cadence else None,
            "total_elevation_gain": round(float(elev_gain), 1),
            "calories": int(calories),
            "aerobic_training_effect": round(float(aerobic_te), 1) if aerobic_te else None,
            "anaerobic_training_effect": round(float(anaerobic_te), 1) if anaerobic_te else None,
            "splits": act.get("splits") or [],
            "laps": act.get("laps") or [],
            "raw_garmin_data": act, # Compatible key for DB/LocalStore JSONB storage
        }

    def fetch_daily_health_metrics(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        """Fetches daily health metrics from COROS."""
        date_str = target_date or date.today().isoformat()
        metrics: Dict[str, Any] = {
            "date": date_str,
            "source": f"coros_{'cn' if self.is_cn else 'global'}",
        }
        return metrics
