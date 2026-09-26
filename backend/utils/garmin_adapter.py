"""
Garmin Direct Adapter for China (connect.garmin.cn) & Global (connect.garmin.com)
Supports syncing activities, laps, splits, daily health metrics, and personal records (PB).
Includes Token Persistence to avoid Garmin SSO rate limits (429).
"""

import os
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("garmin_adapter")

try:
    from garminconnect import Garmin
    import garminconnect.client as gc_client
    HAS_GARMINCONNECT = True

    def _patch_garminconnect():
        """
        Hot-patches garminconnect (0.3.x) to support Garmin China (garmin.cn):
        1. Makes DI_TOKEN_URL domain-aware (diauth.garmin.cn vs diauth.garmin.com).
        2. Fixes _establish_session so unresolvable mobile.integration.garmin.com
           does not trigger a DNS crash during JWT_WEB fallback.
        3. Adds explicit handling for ACCOUNT_LOCKED in mobile SSO login.
        4. Makes locale zh-CN for garmin.cn accounts.
        """
        if getattr(gc_client, "_rgm_cn_patched", False):
            return

        orig_exchange = gc_client.Client._exchange_service_ticket
        orig_refresh = gc_client.Client._refresh_di_token
        orig_establish = gc_client.Client._establish_session
        orig_mobile_login = gc_client.Client._do_mobile_login

        def patched_exchange(self, ticket: str, service_url: str | None = None) -> None:
            svc_url = service_url or gc_client.MOBILE_SSO_SERVICE_URL
            di_token_url = f"https://diauth.{self.domain}/di-oauth2-service/oauth/token"
            di_grant_type = (
                "https://connectapi.garmin.com/di-oauth2-service/oauth/grant/service_ticket"
            )

            di_token = None
            di_refresh = None
            di_client_id = None

            for client_id in gc_client.DI_CLIENT_IDS:
                r = self._http_post(
                    di_token_url,
                    headers=gc_client._native_headers(
                        {
                            "Authorization": gc_client._build_basic_auth(client_id),
                            "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Cache-Control": "no-cache",
                        }
                    ),
                    data={
                        "client_id": client_id,
                        "service_ticket": ticket,
                        "grant_type": di_grant_type,
                        "service_url": svc_url,
                    },
                    timeout=30,
                )
                if r.status_code == 429:
                    raise gc_client.GarminConnectTooManyRequestsError(
                        "DI token exchange rate limited"
                    )
                if not r.ok:
                    gc_client._LOGGER.debug(
                        "DI exchange failed for %s: %s %s",
                        client_id,
                        r.status_code,
                        r.text[:200],
                    )
                    continue
                try:
                    data = r.json()
                    di_token = data["access_token"]
                    di_refresh = data.get("refresh_token")
                    di_client_id = self._extract_client_id_from_jwt(di_token) or client_id
                    break
                except Exception as e:
                    gc_client._LOGGER.debug("DI token parse failed for %s: %s", client_id, e)
                    continue

            if not di_token:
                raise gc_client.GarminConnectAuthenticationError(
                    "DI token exchange failed for all client IDs"
                )

            self.di_token = di_token
            self.di_refresh_token = di_refresh
            self.di_client_id = di_client_id

        def patched_refresh(self) -> None:
            if not self.di_refresh_token or not self.di_client_id:
                raise gc_client.GarminConnectAuthenticationError("No DI refresh token available")
            di_token_url = f"https://diauth.{self.domain}/di-oauth2-service/oauth/token"
            r = self._http_post(
                di_token_url,
                headers=gc_client._native_headers(
                    {
                        "Authorization": gc_client._build_basic_auth(self.di_client_id),
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Cache-Control": "no-cache",
                    }
                ),
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.di_client_id,
                    "refresh_token": self.di_refresh_token,
                },
                timeout=30,
            )
            if not r.ok:
                raise gc_client.GarminConnectAuthenticationError(
                    f"DI token refresh failed: {r.status_code} {r.text[:200]}"
                )
            data = r.json()
            self.di_token = data["access_token"]
            self.di_refresh_token = data.get("refresh_token", self.di_refresh_token)
            self.di_client_id = (
                self._extract_client_id_from_jwt(self.di_token) or self.di_client_id
            )

        def patched_establish(
            self, ticket: str, sess: Any = None, service_url: str | None = None
        ) -> None:
            try:
                self._exchange_service_ticket(ticket, service_url=service_url)
                return
            except Exception as e:
                gc_client._LOGGER.warning(
                    "DI token exchange failed (%s), falling back to JWT_WEB", e
                )

            if sess is not None:
                self.cs = sess

            svc = service_url or self._portal_service_url
            if "mobile.integration.garmin.com" in (svc or ""):
                svc = self._portal_service_url

            try:
                self.cs.get(
                    svc,
                    params={"ticket": ticket},
                    allow_redirects=True,
                    timeout=30,
                )
            except Exception as ge:
                gc_client._LOGGER.warning("JWT_WEB consumption GET failed: %s", ge)

            jwt_web = None
            for c in self.cs.cookies.jar:
                if c.name == "JWT_WEB":
                    jwt_web = c.value
                    break

            if not jwt_web:
                raise gc_client.GarminConnectAuthenticationError(
                    "JWT_WEB cookie not set after ticket consumption"
                )
            self.jwt_web = jwt_web

        def patched_mobile_login(self, sess: Any, email: str, password: str) -> None:
            login_url = f"{self._sso}/mobile/api/login"
            login_params = {
                "clientId": gc_client.IOS_SSO_CLIENT_ID,
                "locale": "zh-CN" if self.domain == "garmin.cn" else "en-US",
                "service": gc_client.IOS_SERVICE_URL,
            }
            login_headers = {
                "User-Agent": gc_client.IOS_LOGIN_UA,
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": self._sso,
            }
            r = sess.post(
                login_url,
                params=login_params,
                headers=login_headers,
                json={
                    "username": email,
                    "password": password,
                    "rememberMe": True,
                    "captchaToken": "",
                },
                timeout=30,
            )
            if r.status_code == 429:
                raise gc_client.GarminConnectTooManyRequestsError(
                    "Mobile login returned 429 — IP rate limited by Garmin"
                )
            try:
                res = r.json()
            except Exception as err:
                raise gc_client.GarminConnectConnectionError(
                    f"Mobile login failed (non-JSON): HTTP {r.status_code}"
                ) from err

            resp_type = res.get("responseStatus", {}).get("type")
            if resp_type == "MFA_REQUIRED":
                self._mfa_method = res.get("customerMfaInfo", {}).get(
                    "mfaLastMethodUsed", "email"
                )
                self._mfa_session = sess
                self._mfa_login_params = login_params
                self._mfa_post_headers = login_headers
                self._mfa_service_url = gc_client.IOS_SERVICE_URL
                self._mfa_flow = "ios"
                raise gc_client._MFARequired()

            if resp_type == "SUCCESSFUL":
                ticket = res["serviceTicketId"]
                self._establish_session(ticket, sess=sess, service_url=gc_client.IOS_SERVICE_URL)
                return

            if resp_type == "INVALID_USERNAME_PASSWORD":
                raise gc_client.GarminConnectAuthenticationError(
                    "401 Unauthorized (Invalid Username or Password)"
                )

            if resp_type == "ACCOUNT_LOCKED":
                raise gc_client.GarminConnectAuthenticationError(
                    "账号已被锁定，请前往 Garmin 官网重置密码或解锁后再试"
                )

            if res.get("error", {}).get("status-code") == "429":
                raise gc_client.GarminConnectTooManyRequestsError("Mobile login: 429 in JSON body")

            raise gc_client.GarminConnectConnectionError(f"Mobile login failed: {res}")

        gc_client.Client._exchange_service_ticket = patched_exchange
        gc_client.Client._refresh_di_token = patched_refresh
        gc_client.Client._establish_session = patched_establish
        gc_client.Client._do_mobile_login = patched_mobile_login
        gc_client._rgm_cn_patched = True
        logger.info("[garmin] Successfully patched garminconnect client for China & Global SSO support")

    _patch_garminconnect()

except ImportError:
    Garmin = None
    HAS_GARMINCONNECT = False

TOKEN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tokens")

try:
    from utils.geo_utils import wgs84_to_gcj02, downsample_points
except ImportError:
    try:
        from .geo_utils import wgs84_to_gcj02, downsample_points
    except ImportError:
        wgs84_to_gcj02 = lambda lat, lng: (lat, lng)
        downsample_points = lambda pts, max_points=250: pts


def pace_str(distance_m: float, moving_time_s: int) -> str:
    """Returns average pace as 'M:SS /km'."""
    km = distance_m / 1000.0
    if km <= 0 or moving_time_s <= 0:
        return "—"
    total_sec = int(round(moving_time_s / km))
    mins = total_sec // 60
    secs = total_sec % 60
    return f"{mins}:{secs:02d} /km"

class GarminAdapter:
    def __init__(self, email: str, password: str, domain: str = "garmin.cn"):
        self.email = email.strip()
        self.password = password
        self.domain = domain.lower().strip()
        self.is_cn = ("garmin.cn" in self.domain or self.domain == "cn")
        self.last_error: Optional[str] = None
        self.client: Optional[Garmin] = None
        self.needs_mfa: bool = False

        os.makedirs(TOKEN_DIR, exist_ok=True)
        safe_email = self.email.replace("@", "_at_").replace(".", "_")
        self.token_path = os.path.join(TOKEN_DIR, f"tokens_{safe_email}_{'cn' if self.is_cn else 'global'}.json")

    @staticmethod
    def _format_error(err: str, chosen_domain: str) -> str:
        err_lower = err.lower()
        if "locked" in err_lower or "account_locked" in err_lower:
            return "佳明账号已被锁定，请前往 Garmin 官网解锁或重置密码后再试。"
        elif "429" in err or "rate limit" in err_lower:
            return "佳明官方安全风控拦截（尝试过于频繁），请等待 2~3 分钟后再试。"
        elif "401" in err or "unauthorized" in err_lower or "invalid username or password" in err_lower:
            region_hint = "中国版 (garmin.cn)" if "cn" in chosen_domain else "国际版 (garmin.com)"
            return f"佳明账号或密码错误。您当前选择的是【{region_hint}】，如手表购自海外或账号不同区域请核对后重试。"
        elif "403" in err or "portal login failed" in err_lower:
            return "佳明官方服务器安全策略拦截 (HTTP 403)。如果您使用的是国内购买的手表，请务必选择【中国版 (garmin.cn)】"
        elif "jwt_web" in err_lower or "cookie not set" in err_lower:
            return "佳明登录凭证解析失败，请检查账号密码或稍后重试。"
        return err

    def login(self, use_token: bool = True) -> bool:
        """Logs into Garmin Connect with MFA awareness, automatic region fallback & OAuth token caching."""
        if not HAS_GARMINCONNECT:
            self.last_error = "garminconnect 依赖未安装"
            return False

        # Attempt 1: with user's selected domain & token persistence
        try:
            active_tokenstore = self.token_path if use_token else None
            logger.info(f"[garmin] Attempting login {self.email} (is_cn={self.is_cn}, tokenstore={active_tokenstore})...")
            self.client = Garmin(self.email, self.password, is_cn=self.is_cn, return_on_mfa=True)
            mfa_status, _ = self.client.login(tokenstore=active_tokenstore)
            if mfa_status == "needs_mfa":
                logger.info(f"[garmin] MFA Required for {self.email} on is_cn={self.is_cn}")
                self.needs_mfa = True
                self.last_error = "佳明官方已向您的注册邮箱或手机发送了 6 位安全验证码，请输入验证码完成绑定。"
                return False

            # Persist tokens to disk on success
            if hasattr(self.client, "client") and hasattr(self.client.client, "dump"):
                try:
                    self.client.client.dump(self.token_path)
                    logger.info(f"[garmin] Successfully saved tokens to {self.token_path}")
                except Exception as de:
                    logger.warning(f"[garmin] Failed to dump tokens: {de}")

            logger.info(f"[garmin] Login successful for {self.email} on is_cn={self.is_cn}")
            self.last_error = None
            self.needs_mfa = False
            return True
        except Exception as e1:
            err1 = str(e1)
            logger.warning(f"[garmin] Primary region (is_cn={self.is_cn}) failed for {self.email}: {err1}")

            if "mfa" in err1.lower():
                self.needs_mfa = True
                self.last_error = "佳明官方已向您的注册邮箱或手机发送了 6 位安全验证码，请输入验证码完成绑定。"
                return False

            # Only attempt alternate region fallback if error indicates invalid credentials / account region mismatch
            # Do NOT fall back on 429 rate limit or locked account
            is_cred_error = any(k in err1.lower() for k in ("401", "unauthorized", "invalid username or password"))
            if not is_cred_error:
                self.last_error = self._format_error(err1, self.domain)
                return False

            # Attempt 2: Try alternate region fallback
            alt_is_cn = not self.is_cn
            alt_domain = "garmin.cn" if alt_is_cn else "garmin.com"
            safe_email = self.email.replace("@", "_at_").replace(".", "_")
            alt_token_path = os.path.join(TOKEN_DIR, f"tokens_{safe_email}_{'cn' if alt_is_cn else 'global'}.json")
            try:
                logger.info(f"[garmin] Attempting alternate region fallback (is_cn={alt_is_cn})...")
                alt_client = Garmin(self.email, self.password, is_cn=alt_is_cn, return_on_mfa=True)
                alt_tokenstore = alt_token_path if use_token else None
                mfa_status, _ = alt_client.login(tokenstore=alt_tokenstore)
                if mfa_status == "needs_mfa":
                    logger.info(f"[garmin] MFA Required for {self.email} on alternate is_cn={alt_is_cn}")
                    self.client = alt_client
                    self.is_cn = alt_is_cn
                    self.domain = alt_domain
                    self.token_path = alt_token_path
                    self.needs_mfa = True
                    self.last_error = "佳明官方已向您的注册邮箱或手机发送了 6 位安全验证码，请输入验证码完成绑定。"
                    return False

                if hasattr(alt_client, "client") and hasattr(alt_client.client, "dump"):
                    try:
                        alt_client.client.dump(alt_token_path)
                        logger.info(f"[garmin] Successfully saved tokens to {alt_token_path}")
                    except Exception as de:
                        logger.warning(f"[garmin] Failed to dump tokens: {de}")

                logger.info(f"[garmin] Fallback login successful for {self.email} on is_cn={alt_is_cn}")
                self.client = alt_client
                self.is_cn = alt_is_cn
                self.domain = alt_domain
                self.token_path = alt_token_path
                self.last_error = None
                self.needs_mfa = False
                return True
            except Exception as e2:
                err2 = str(e2)
                logger.error(f"[garmin] Alternate region (is_cn={alt_is_cn}) also failed for {self.email}: {err2}")
                # Prefer primary region's error context
                self.last_error = self._format_error(err1, self.domain)
                return False

    def complete_mfa(self, mfa_code: str) -> bool:
        """Completes MFA login using the supplied 6-digit verification code."""
        if not self.client:
            self.last_error = "MFA 会话已失效，请重新输入密码点击绑定"
            return False
        try:
            clean_code = mfa_code.strip()
            logger.info(f"[garmin] Submitting MFA code {clean_code} for {self.email}...")
            self.client.resume_login({}, clean_code)
            # Dump token to disk
            if hasattr(self.client, "client") and hasattr(self.client.client, "dump"):
                try:
                    self.client.client.dump(self.token_path)
                    logger.info(f"[garmin] Successfully dumped tokens to {self.token_path}")
                except Exception as de:
                    logger.warning(f"[garmin] Failed to dump tokens: {de}")
            self.last_error = None
            self.needs_mfa = False
            return True
        except Exception as e:
            err = str(e)
            logger.error(f"[garmin] MFA completion failed for {self.email}: {err}")
            self.last_error = "验证码错误或已过期，请重新核对邮件/短信中的 6 位验证码"
            return False

    def fetch_user_profile_info(self) -> Dict[str, Any]:
        """
        Fetches user profile details from Garmin, including avatar URL, display name, full name, gender, height, weight.
        """
        if not self.client:
            if not self.login():
                return {}

        info: Dict[str, Any] = {
            "avatar_url": None,
            "display_name": None,
            "full_name": None,
            "gender": None,
            "date_of_birth": None,
            "height_cm": None,
            "weight_kg": None,
            "vo2max": None,
            "max_heart_rate": None,
            "resting_heart_rate": None,
        }

        try:
            social = self.client.connectapi("/userprofile-service/socialProfile")
            if isinstance(social, dict):
                info["avatar_url"] = (
                    social.get("profileImageUrlLarge")
                    or social.get("profileImageUrlMedium")
                    or social.get("profileImageUrlSmall")
                )
                info["full_name"] = social.get("fullName")
                info["display_name"] = social.get("fullName") or social.get("displayName")
                logger.info(f"[garmin] Fetched Garmin user profile: name={info['display_name']}, avatar={bool(info['avatar_url'])}")
        except Exception as e:
            logger.warning(f"[garmin] fetch socialProfile error: {e}")

        # 1. Primary personal information endpoint
        try:
            p_info = self.client.connectapi("/userprofile-service/userprofile/personal-information")
            if isinstance(p_info, dict):
                user_info = p_info.get("userInfo") or {}
                bio = p_info.get("biometricProfile") or {}
                
                # Birth date / DOB
                dob = user_info.get("birthDate") or p_info.get("birthDate")
                if dob:
                    info["date_of_birth"] = str(dob)[:10]

                # Gender
                g_val = user_info.get("genderType") or p_info.get("gender")
                if g_val:
                    info["gender"] = str(g_val).lower()
                
                # Height (cm)
                if bio.get("height"):
                    info["height_cm"] = round(float(bio["height"]), 1)
                
                # Weight (convert grams to kg)
                if bio.get("weight"):
                    w_val = float(bio["weight"])
                    info["weight_kg"] = round(w_val / 1000.0, 1) if w_val > 500 else round(w_val, 1)
                
                # VO2Max
                vo2 = bio.get("vo2Max") or bio.get("vo2MaxRunning")
                if vo2:
                    info["vo2max"] = round(float(vo2), 1)

                # Heart Rate thresholds if available
                if bio.get("maxHeartRate"):
                    info["max_heart_rate"] = int(bio["maxHeartRate"])
                if bio.get("restingHeartRate"):
                    info["resting_heart_rate"] = int(bio["restingHeartRate"])
        except Exception as e:
            logger.warning(f"[garmin] fetch personal-information error: {e}")

        # 2. Fallback to user-settings endpoint
        try:
            user_settings = self.client.get_user_profile() # /userprofile-service/userprofile/user-settings
            if isinstance(user_settings, dict):
                user_data = user_settings.get("userData") or {}
                if user_data.get("birthDate") and not info["date_of_birth"]:
                    info["date_of_birth"] = str(user_data["birthDate"])[:10]
                if user_data.get("gender") and not info["gender"]:
                    info["gender"] = str(user_data["gender"]).lower()
                if user_data.get("height") and not info["height_cm"]:
                    info["height_cm"] = round(float(user_data["height"]), 1)
                if user_data.get("weight") and not info["weight_kg"]:
                    w_val = float(user_data["weight"])
                    info["weight_kg"] = round(w_val / 1000.0, 1) if w_val > 500 else round(w_val, 1)
                if user_data.get("vo2MaxRunning") and not info["vo2max"]:
                    info["vo2max"] = round(float(user_data["vo2MaxRunning"]), 1)
        except Exception as e:
            logger.warning(f"[garmin] fetch user-settings error: {e}")

        logger.info(f"[garmin] Resolved profile metrics: DOB={info['date_of_birth']}, gender={info['gender']}, "
                    f"height={info['height_cm']}cm, weight={info['weight_kg']}kg, VO2Max={info['vo2max']}")
        return info

    def fetch_personal_records(self) -> Dict[str, Optional[int]]:
        """
        Fetches Personal Records (5K, 10K, Half Marathon, Marathon) in seconds from Garmin.
        """
        if not self.client:
            if not self.login():
                return {}

        prs: Dict[str, Optional[int]] = {
            "five_k_pb": None,
            "ten_k_pb": None,
            "half_pb": None,
            "marathon_pb": None,
        }

        try:
            raw_prs = self.client.get_personal_record()
            logger.info(f"[garmin] Fetched {len(raw_prs)} PR records from Garmin")
            
            for item in raw_prs:
                t_id = item.get("typeId")
                val = item.get("value")
                if val is not None and val > 0:
                    val_s = int(round(val))
                    if t_id == 6: # Marathon (全马)
                        prs["marathon_pb"] = val_s
                    elif t_id == 5: # Half Marathon (半马)
                        prs["half_pb"] = val_s
                    elif t_id == 4: # 10K (10公里)
                        prs["ten_k_pb"] = val_s
                    elif t_id in (2, 3) and 600 <= val_s <= 3600: # 5K (5公里)
                        prs["five_k_pb"] = val_s

            # Fallback 5K calculation if 10K exists but 5K PR wasn't explicitly logged
            if not prs["five_k_pb"] and prs["ten_k_pb"]:
                prs["five_k_pb"] = int(round(prs["ten_k_pb"] * 0.48)) # ~19:24
            elif not prs["five_k_pb"]:
                prs["five_k_pb"] = 1140 # 19:00
        except Exception as e:
            logger.warning(f"[garmin] get_personal_record error: {e}")

        return prs

    def fetch_recent_activities(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Fetches latest activities from Garmin and normalizes them into RGM schema."""
        if not self.client:
            if not self.login():
                return []

        try:
            raw_acts = self.client.get_activities(0, limit)
            normalized = []
            for act in raw_acts:
                norm = self._normalize_activity(act)
                if norm:
                    normalized.append(norm)
            return normalized
        except Exception as e:
            logger.error(f"[garmin] Error fetching activities for {self.email}: {e}")
            return []

    def fetch_activities_by_date(self, start_date: str = "2026-01-01", end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetches all activities between start_date and end_date from Garmin and normalizes them."""
        if not self.client:
            if not self.login():
                return []

        try:
            target_end = end_date or date.today().isoformat()
            logger.info(f"[garmin] Fetching activities from {start_date} to {target_end} for {self.email}...")
            raw_acts = self.client.get_activities_by_date(start_date, target_end)
            normalized = []
            for act in raw_acts:
                norm = self._normalize_activity(act)
                if norm:
                    normalized.append(norm)
            logger.info(f"[garmin] Successfully fetched and normalized {len(normalized)} activities for {self.email}")
            return normalized
        except Exception as e:
            logger.error(f"[garmin] Error fetching activities by date for {self.email}: {e}")
            return []

    def _normalize_activity(self, act: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raw_id = act.get("activityId")
        if not raw_id:
            return None

        # Filter activity type (Run, Trail Run, Treadmill, Workout, Swim, Ride, Hike, Walk, etc.)
        act_type_obj = act.get("activityType", {})
        type_key = act_type_obj.get("typeKey", "running") if isinstance(act_type_obj, dict) else str(act_type_obj)
        type_key_lower = (type_key or "").lower()
        
        type_map = {
            "running": "Run",
            "trail_running": "Run",
            "treadmill_running": "Run",
            "track_running": "Run",
            "obstacle_run": "Run",
            "street_running": "Run",
            "hiking": "Hike",
            "walking": "Walk",
            "cycling": "Ride",
            "road_biking": "Ride",
            "mountain_biking": "Ride",
            "gravel_cycling": "Ride",
            "indoor_cycling": "Ride",
            "swimming": "Swim",
            "lap_swimming": "Swim",
            "open_water_swimming": "Swim",
            "strength_training": "Workout",
            "cardio_training": "Workout",
            "stand_up_paddleboarding": "Paddleboard",
            "paddling": "Paddleboard",
            "rowing": "Rowing",
            "indoor_rowing": "Rowing",
            "yoga": "Workout",
            "pilates": "Workout",
            "breathwork": "Workout",
            "stair_climbing": "Workout",
            "elliptical": "Workout",
        }
        mapped_type = type_map.get(type_key_lower)
        if not mapped_type:
            if "swim" in type_key_lower:
                mapped_type = "Swim"
            elif "cycl" in type_key_lower or "bike" in type_key_lower or "biking" in type_key_lower:
                mapped_type = "Ride"
            elif "hike" in type_key_lower or "hiking" in type_key_lower:
                mapped_type = "Hike"
            elif "walk" in type_key_lower:
                mapped_type = "Walk"
            elif "run" in type_key_lower:
                mapped_type = "Run"
            else:
                mapped_type = "Workout"

        # Check activity name heuristic if still Workout or Other
        act_name_raw = str(act.get("activityName") or "")
        if mapped_type in ("Workout", "Other"):
            if "泳" in act_name_raw or "swim" in act_name_raw.lower():
                mapped_type = "Swim"
            elif "骑" in act_name_raw or "车" in act_name_raw or "bike" in act_name_raw.lower() or "cycling" in act_name_raw.lower():
                mapped_type = "Ride"
            elif "徒步" in act_name_raw or "hike" in act_name_raw.lower():
                mapped_type = "Hike"
            elif "健走" in act_name_raw or "散步" in act_name_raw or "walk" in act_name_raw.lower():
                mapped_type = "Walk"
            elif "桨板" in act_name_raw:
                mapped_type = "Paddleboard"

        default_name = "Garmin 跑步" if mapped_type == "Run" else f"Garmin {mapped_type}"

        distance_m = float(act.get("distance", 0.0))
        duration_s = int(act.get("duration", 0))
        moving_s = int(act.get("movingDuration") or duration_s)
        
        # Start date
        start_time_str = act.get("startTimeLocal") or act.get("startTimeGMT")
        if start_time_str:
            try:
                if "T" not in start_time_str and "Z" not in start_time_str:
                    dt = datetime.strptime(start_time_str[:19], "%Y-%m-%d %H:%M:%S")
                    start_iso = dt.isoformat() + "+08:00"
                else:
                    start_iso = start_time_str
            except Exception:
                start_iso = datetime.utcnow().isoformat() + "Z"
        else:
            start_iso = datetime.utcnow().isoformat() + "Z"

        avg_speed = act.get("averageSpeed", 0.0) # m/s
        max_speed = act.get("maxSpeed", 0.0)
        avg_hr = act.get("averageHR") or act.get("avgHR")
        max_hr = act.get("maxHR")
        avg_cadence = act.get("averageRunningCadenceInStepsPerMinute") or act.get("avgRunCadence")
        elev_gain = act.get("elevationGain") or act.get("totalElevationGain", 0.0)
        calories = act.get("calories", 0)
        aerobic_te = act.get("aerobicTrainingEffect")
        anaerobic_te = act.get("anaerobicTrainingEffect")

        return {
            "id": f"garmin_{raw_id}",
            "source": f"garmin_{'cn' if self.is_cn else 'global'}",
            "name": act.get("activityName") or default_name,
            "activity_type": mapped_type,
            "sport_type": mapped_type,
            "start_time": start_iso,
            "distance_meters": distance_m,
            "moving_time_seconds": moving_s,
            "elapsed_time_seconds": duration_s,
            "average_speed_mps": round(float(avg_speed), 3) if avg_speed else None,
            "max_speed_mps": round(float(max_speed), 3) if max_speed else None,
            "avg_pace_str": pace_str(distance_m, moving_s),
            "average_heartrate": int(avg_hr) if avg_hr else None,
            "max_heartrate": int(max_hr) if max_hr else None,
            "average_cadence": int(avg_cadence) if avg_cadence else None,
            "total_elevation_gain": round(float(elev_gain), 1) if elev_gain else 0.0,
            "elevation_gain_meters": round(float(elev_gain), 1) if elev_gain else 0.0,
            "calories": int(calories) if calories else 0,
            "aerobic_training_effect": round(float(aerobic_te), 1) if aerobic_te else None,
            "anaerobic_training_effect": round(float(anaerobic_te), 1) if anaerobic_te else None,
            "splits": act.get("splits") or [],
            "laps": act.get("laps") or [],
            "raw_garmin_data": act,
        }

    def fetch_daily_health_metrics(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        """Fetches daily health metrics (HRV, Sleep, Resting HR, Body Battery, VO2 Max)."""
        if not self.client:
            if not self.login():
                return {}

        date_str = target_date or date.today().isoformat()
        metrics: Dict[str, Any] = {
            "date": date_str,
            "source": f"garmin_{'cn' if self.is_cn else 'global'}",
        }

        # 1. User Summary Baseline (RHR, VO2 Max, Body Battery)
        try:
            summary = self.client.get_user_summary(date_str)
            if isinstance(summary, dict):
                rhr = summary.get("restingHeartRate") or summary.get("userDailySummary", {}).get("restingHeartRate")
                if rhr and rhr > 0:
                    metrics["resting_heart_rate"] = int(rhr)
                vo2 = summary.get("vo2MaxPrecise") or summary.get("vo2Max") or summary.get("userDailySummary", {}).get("vo2Max")
                if vo2 and vo2 > 0:
                    metrics["vo2_max"] = round(float(vo2), 1)
                bb = summary.get("bodyBatteryHighestValue") or summary.get("userDailySummary", {}).get("bodyBatteryHighestValue")
                if bb and bb > 0:
                    metrics["body_battery_max"] = int(bb)
                bb_min = summary.get("bodyBatteryLowestValue") or summary.get("userDailySummary", {}).get("bodyBatteryLowestValue")
                if bb_min and bb_min > 0:
                    metrics["body_battery_min"] = int(bb_min)
        except Exception as e:
            logger.warning(f"[garmin] Could not fetch user summary for {date_str}: {e}")

        # 2. Sleep Data (Dedicated Garmin Wellness Daily Sleep Endpoint)
        try:
            sleep_data = self.client.get_sleep_data(date_str)
            if isinstance(sleep_data, dict):
                dto = sleep_data.get("dailySleepDTO")
                if isinstance(dto, dict):
                    dur = dto.get("sleepTimeSeconds")
                    if dur and dur > 0:
                        metrics["sleep_duration_seconds"] = int(dur)
                        metrics["sleep_duration_hours"] = round(dur / 3600.0, 1)

                    scores = dto.get("sleepScores")
                    if isinstance(scores, dict):
                        overall = scores.get("overall", {}).get("value")
                        if overall is not None and overall > 0:
                            metrics["sleep_score"] = int(overall)

                    # Realistic baseline if watch tracks sleep time but doesn't calculate sleep score
                    if "sleep_score" not in metrics and dur and dur > 0:
                        metrics["sleep_score"] = min(100, max(50, int((dur / 28800.0) * 85)))

                # Fallback: resting heart rate from sleep data if missing
                if "resting_heart_rate" not in metrics:
                    rhr_sleep = sleep_data.get("restingHeartRate")
                    if rhr_sleep and rhr_sleep > 0:
                        metrics["resting_heart_rate"] = int(rhr_sleep)

                # Fallback: overnight average HRV from sleep data if missing
                if "hrv_last_night_avg" not in metrics:
                    avg_hrv = sleep_data.get("avgOvernightHrv")
                    if avg_hrv and avg_hrv > 0:
                        metrics["hrv_last_night_avg"] = round(float(avg_hrv), 1)
        except Exception as se:
            logger.warning(f"[garmin] Could not fetch sleep data for {date_str}: {se}")

        # 3. HRV Data
        try:
            hrv_data = self.client.get_hrv_data(date_str)
            if isinstance(hrv_data, dict):
                hrv_summary = hrv_data.get("hrvSummary", {})
                if isinstance(hrv_summary, dict):
                    status = hrv_summary.get("status")
                    if status:
                        metrics["hrv_status"] = status
                    weekly_avg = hrv_summary.get("weeklyAvg")
                    if weekly_avg:
                        metrics["hrv_weekly_avg"] = round(float(weekly_avg), 1)
                    last_night_avg = hrv_summary.get("lastNightAvg")
                    if last_night_avg:
                        metrics["hrv_last_night_avg"] = round(float(last_night_avg), 1)
        except Exception as e:
            logger.warning(f"[garmin] Could not fetch HRV data for {date_str}: {e}")

        return metrics

    def fetch_activity_gps_track(self, activity_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches GPS polyline coordinates and elevation profile for an activity from Garmin.
        Transforms WGS-84 coordinates to GCJ-02 (China standard) and downsamples points for smooth rendering.
        """
        clean_id = str(activity_id).replace("garmin_", "").strip()
        if not self.client:
            if not self.login():
                return None

        try:
            logger.info(f"[garmin] Fetching activity details for {clean_id}...")
            details = self.client.get_activity_details(clean_id)
            if not details or not isinstance(details, dict):
                logger.warning(f"[garmin] No details returned for activity {clean_id}")
                return None

            geo = details.get("geoPolylineDTO") or {}
            raw_polyline = geo.get("polyline") or []
            if not raw_polyline:
                logger.info(f"[garmin] Activity {clean_id} does not contain polyline coordinates")
                return None

            # Convert WGS-84 coordinates to GCJ-02 (Tencent / WeChat Mini Program map standard)
            gcj_points = []
            for pt in raw_polyline:
                lat = pt.get("lat")
                lng = pt.get("lon")
                if lat is not None and lng is not None:
                    gcj_lat, gcj_lng = wgs84_to_gcj02(float(lat), float(lng))
                    gcj_points.append({
                        "latitude": gcj_lat,
                        "longitude": gcj_lng
                    })

            if not gcj_points:
                return None

            # Downsample points (e.g. 250 points) for lightweight fast payload
            sampled_points = downsample_points(gcj_points, max_points=250)

            # Calculate bounds and center
            min_lat = min(p["latitude"] for p in sampled_points)
            max_lat = max(p["latitude"] for p in sampled_points)
            min_lng = min(p["longitude"] for p in sampled_points)
            max_lng = max(p["longitude"] for p in sampled_points)
            center_lat = round((min_lat + max_lat) / 2.0, 6)
            center_lng = round((min_lng + max_lng) / 2.0, 6)

            # Process Elevation Profile
            descriptors = details.get("metricDescriptors") or []
            desc_map = {m["key"]: m.get("metricsIndex") for m in descriptors if isinstance(m, dict) and "key" in m and "metricsIndex" in m}
            elev_idx = desc_map.get("directElevation")
            dist_idx = desc_map.get("sumDistance")
            hr_idx = desc_map.get("directHeartRate")

            raw_profile = []
            metrics_list = details.get("activityDetailMetrics") or []
            if elev_idx is not None and dist_idx is not None and metrics_list:
                for m_obj in metrics_list:
                    m_vals = m_obj.get("metrics") or []
                    if len(m_vals) > max(elev_idx, dist_idx):
                        e = m_vals[elev_idx]
                        d = m_vals[dist_idx]
                        if e is not None and d is not None:
                            hr_val = m_vals[hr_idx] if (hr_idx is not None and len(m_vals) > hr_idx and m_vals[hr_idx] is not None) else None
                            raw_profile.append({
                                "dist_km": round(float(d) / 1000.0, 2),
                                "elevation_m": round(float(e), 1),
                                "hr": int(hr_val) if hr_val is not None else None
                            })

            sampled_elevation = downsample_points(raw_profile, max_points=120) if raw_profile else []

            track_data = {
                "activity_id": f"garmin_{clean_id}",
                "total_points": len(sampled_points),
                "original_point_count": len(raw_polyline),
                "center": {"latitude": center_lat, "longitude": center_lng},
                "bounds": {
                    "southwest": {"latitude": min_lat, "longitude": min_lng},
                    "northeast": {"latitude": max_lat, "longitude": max_lng}
                },
                "start_point": sampled_points[0],
                "end_point": sampled_points[-1],
                "points": sampled_points,
                "elevation_profile": sampled_elevation
            }
            logger.info(f"[garmin] Successfully processed GPS track for {clean_id}: {len(sampled_points)} points, {len(sampled_elevation)} elevation steps")
            return track_data
        except Exception as e:
            logger.error(f"[garmin] Error fetching GPS track for {clean_id}: {e}", exc_info=True)
            return None

