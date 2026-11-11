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
        Hot-patches garminconnect client to properly support Garmin China (garmin.cn) & Global (garmin.com):
        1. Ensures domain-aware URLs:
           - self._di_token_url = f"https://diauth.{self.domain}/di-oauth2-service/oauth/token"
           - self._ios_service_url = f"https://mobile.integration.{self.domain}/gcm/ios"
           - self._mobile_sso_service_url = f"https://mobile.integration.{self.domain}/gcm/android"
           - self._portal_service_url = f"https://connect.{self.domain}/app"
        2. Correctly matches DI client ID with the ticket's service_url:
           - When service_url contains '/ios', uses GARMIN_CONNECT_MOBILE_IOS_DI first to avoid burning single-use CAS ticket.
           - When service_url contains '/android', uses GARMIN_CONNECT_MOBILE_ANDROID_DI_* first.
        3. Avoids unresolvable mobile.integration hostnames during session establishment fallback.
        4. Detects ACCOUNT_LOCKED explicitly and provides clean error messages.
        """
        if getattr(gc_client, "_rgm_cn_patched", False):
            return

        import socket
        import threading
        from urllib.parse import urlparse

        _sso_tls = threading.local()

        def _get_global_sso_proxies(domain: str) -> Optional[Dict[str, str]]:
            if "cn" in (domain or "").lower():
                return None
            proxy_url = os.getenv("GARMIN_GLOBAL_PROXY", "http://172.18.0.1:1082")
            try:
                parsed = urlparse(proxy_url)
                host = parsed.hostname or "172.18.0.1"
                port = parsed.port or 1082
                with socket.create_connection((host, port), timeout=0.3):
                    return {"http": proxy_url, "https": proxy_url}
            except Exception:
                return None

        if getattr(gc_client, "HAS_CFFI", False) and hasattr(gc_client, "cffi_requests"):
            _orig_cffi_session = gc_client.cffi_requests.Session

            def _proxied_cffi_session(*args: Any, **kwargs: Any) -> Any:
                active_proxies = getattr(_sso_tls, "proxies", None)
                if active_proxies and "proxies" not in kwargs:
                    kwargs["proxies"] = active_proxies
                return _orig_cffi_session(*args, **kwargs)

            gc_client.cffi_requests.Session = _proxied_cffi_session

        def patched_exchange(self, ticket: str, service_url: str | None = None) -> None:
            svc_url = service_url or getattr(self, "_mobile_sso_service_url", f"https://mobile.integration.{self.domain}/gcm/android")
            di_token_url = getattr(self, "_di_token_url", f"https://diauth.{self.domain}/di-oauth2-service/oauth/token")
            di_grant_type = "https://connectapi.garmin.com/di-oauth2-service/oauth/grant/service_ticket"

            # Sort client IDs so we match the ticket's issuing service
            # CAS service tickets are single-use; trying an incompatible client ID invalidates the ticket!
            client_ids = list(gc_client.DI_CLIENT_IDS)
            if "ios" in (svc_url or "").lower():
                client_ids.sort(key=lambda cid: 0 if "IOS" in cid else 1)
            else:
                client_ids.sort(key=lambda cid: 0 if "ANDROID" in cid else 1)

            di_token = None
            di_refresh = None
            di_client_id = None
            last_err = None
            exchange_proxies = getattr(_sso_tls, "proxies", None) or _get_global_sso_proxies(self.domain)

            for client_id in client_ids:
                try:
                    post_kwargs: Dict[str, Any] = {
                        "headers": gc_client._native_headers(
                            {
                                "Authorization": gc_client._build_basic_auth(client_id),
                                "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
                                "Content-Type": "application/x-www-form-urlencoded",
                                "Cache-Control": "no-cache",
                            }
                        ),
                        "data": {
                            "client_id": client_id,
                            "service_ticket": ticket,
                            "grant_type": di_grant_type,
                            "service_url": svc_url,
                        },
                        "timeout": 30,
                    }
                    if exchange_proxies:
                        post_kwargs["proxies"] = exchange_proxies
                    r = self._http_post(di_token_url, **post_kwargs)
                except Exception as post_err:
                    logger.warning(f"[garmin] POST to {di_token_url} failed: {post_err}")
                    last_err = post_err
                    continue

                if r.status_code == 429:
                    raise gc_client.GarminConnectTooManyRequestsError("DI token exchange rate limited (429)")

                if not r.ok:
                    logger.warning(
                        f"[garmin] DI exchange failed for {client_id} (svc_url={svc_url}): {r.status_code} {r.text[:250]}"
                    )
                    last_err = f"HTTP {r.status_code}: {r.text[:200]}"
                    continue

                try:
                    data = r.json()
                    di_token = data["access_token"]
                    di_refresh = data.get("refresh_token")
                    di_client_id = self._extract_client_id_from_jwt(di_token) or client_id
                    logger.info(f"[garmin] Successfully exchanged DI token using {client_id}")
                    break
                except Exception as e:
                    logger.warning(f"[garmin] DI token JSON parse failed for {client_id}: {e}")
                    last_err = e
                    continue

            if not di_token:
                raise gc_client.GarminConnectAuthenticationError(
                    f"DI token exchange failed for all client IDs ({last_err})"
                )

            self.di_token = di_token
            self.di_refresh_token = di_refresh
            self.di_client_id = di_client_id

        def patched_mobile_login(self, sess: Any, email: str, password: str) -> None:
            ios_svc_url = getattr(self, "_ios_service_url", f"https://mobile.integration.{self.domain}/gcm/ios")
            login_url = f"{self._sso}/mobile/api/login"
            login_params = {
                "clientId": gc_client.IOS_SSO_CLIENT_ID,
                "locale": "zh-CN" if "cn" in self.domain else "en-US",
                "service": ios_svc_url,
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
                self._mfa_service_url = ios_svc_url
                self._mfa_flow = "ios"
                raise gc_client._MFARequired()

            if resp_type == "SUCCESSFUL":
                ticket = res["serviceTicketId"]
                logger.info(f"[garmin] Mobile login got serviceTicketId for {email} on {self.domain}")
                self._establish_session(ticket, sess=sess, service_url=ios_svc_url)
                return

            if resp_type == "INVALID_USERNAME_PASSWORD":
                raise gc_client.GarminConnectAuthenticationError(
                    "401 Unauthorized (Invalid Username or Password)"
                )

            if resp_type == "ACCOUNT_LOCKED":
                raise gc_client.GarminConnectAuthenticationError(
                    "账号已被锁定，请前往 Garmin 官网重置密码或解锁后再试"
                )

            if resp_type in (
                "PHONE_REGISTRATION_REQUIRED",
                "PHONE_VERIFICATION_REQUIRED",
                "CN_VERIFICATION_PHONE_NUMBER_NEEDED",
            ):
                raise gc_client.GarminConnectAuthenticationError(
                    "PHONE_REGISTRATION_REQUIRED"
                )

            if resp_type in ("PASSWORD_CHANGE_REQUIRED", "RESET_PASSWORD"):
                raise gc_client.GarminConnectAuthenticationError(
                    "PASSWORD_CHANGE_REQUIRED"
                )

            if res.get("error", {}).get("status-code") == "429":
                raise gc_client.GarminConnectTooManyRequestsError("Mobile login: 429 in JSON body")

            raise gc_client.GarminConnectConnectionError(f"Mobile login failed: {res}")

        orig_widget_login = gc_client.Client._widget_web_login
        orig_portal_login = gc_client.Client._do_portal_web_login

        def patched_widget_login(self, email: str, password: str) -> None:
            try:
                return orig_widget_login(self, email, password)
            except gc_client.GarminConnectConnectionError as err:
                msg = str(err)
                msg_lower = msg.lower()
                if "update phone number" in msg_lower or "verify phone" in msg_lower:
                    logger.warning(f"[garmin] Widget login hit phone registration prompt for {email} on {self.domain}: {msg}")
                    raise gc_client.GarminConnectAuthenticationError(
                        "PHONE_REGISTRATION_REQUIRED"
                    ) from err
                if "change password" in msg_lower or "reset password" in msg_lower:
                    raise gc_client.GarminConnectAuthenticationError(
                        "PASSWORD_CHANGE_REQUIRED"
                    ) from err
                raise

        def patched_portal_login(self, sess: Any, email: str, password: str) -> None:
            try:
                return orig_portal_login(self, sess, email, password)
            except gc_client.GarminConnectConnectionError as err:
                msg = str(err)
                if any(
                    k in msg
                    for k in (
                        "PHONE_REGISTRATION_REQUIRED",
                        "PHONE_VERIFICATION_REQUIRED",
                        "CN_VERIFICATION_PHONE_NUMBER_NEEDED",
                    )
                ):
                    logger.warning(f"[garmin] Portal login hit phone registration prompt for {email} on {self.domain}")
                    raise gc_client.GarminConnectAuthenticationError(
                        "PHONE_REGISTRATION_REQUIRED"
                    ) from err
                if "ACCOUNT_LOCKED" in msg:
                    raise gc_client.GarminConnectAuthenticationError(
                        "账号已被锁定，请前往 Garmin 官网重置密码或解锁后再试"
                    ) from err
                if "PASSWORD_CHANGE_REQUIRED" in msg:
                    raise gc_client.GarminConnectAuthenticationError(
                        "PASSWORD_CHANGE_REQUIRED"
                    ) from err
                raise

        # Tune delays and impersonation loops to prevent 70s timeouts and IP 429 rate-limit cascades
        gc_client.MOBILE_IMPERSONATIONS = ("safari_ios",)
        gc_client.PORTAL_IMPERSONATIONS = ("chrome120", "safari")
        gc_client.WIDGET_DELAY_MIN_S = 1.2
        gc_client.WIDGET_DELAY_MAX_S = 2.2
        gc_client.LOGIN_DELAY_MIN_S = 2.0
        gc_client.LOGIN_DELAY_MAX_S = 3.5

        def patched_client_login(
            self,
            email: str,
            password: str,
            prompt_mfa: Any = None,
            return_on_mfa: bool = False,
        ) -> tuple[str | None, Any]:
            if getattr(gc_client, "HAS_CFFI", False):
                strategies: list[tuple[str, Any]] = [
                    ("mobile+cffi", lambda: self._mobile_login_cffi(email, password)),
                    ("widget+cffi", lambda: self._widget_web_login(email, password)),
                    ("portal+cffi", lambda: self._portal_web_login_cffi(email, password)),
                ]
            else:
                strategies = [
                    ("mobile+requests", lambda: self._mobile_login_requests(email, password)),
                    ("portal+requests", lambda: self._portal_web_login_requests(email, password)),
                ]

            last_err: Exception | None = None
            rate_limited_count = 0
            sso_proxies = _get_global_sso_proxies(self.domain)
            _sso_tls.proxies = sso_proxies
            if sso_proxies:
                logger.info(f"[garmin] Routing global SSO login for {email} ({self.domain}) via non-CN proxy")

            try:
                for name, run in strategies:
                    try:
                        logger.info(f"[garmin] Trying login strategy: {name} for {email} ({self.domain})")
                        run()
                        return None, None
                    except gc_client.GarminConnectAuthenticationError:
                        raise
                    except gc_client._MFARequired:
                        if return_on_mfa:
                            return "needs_mfa", None
                        if prompt_mfa:
                            mfa_code = prompt_mfa()
                            self._complete_mfa(mfa_code)
                            return None, None
                        raise gc_client.GarminConnectAuthenticationError(
                            "MFA Required but no prompt_mfa mechanism supplied"
                        )
                    except gc_client.GarminConnectTooManyRequestsError as e:
                        logger.warning(f"[garmin] {name} returned 429: {e}")
                        rate_limited_count += 1
                        last_err = e
                        continue
                    except Exception as e:
                        err_str = str(e)
                        logger.warning(f"[garmin] {name} failed: {err_str}")
                        if getattr(_sso_tls, "proxies", None) and any(
                            k in err_str.lower()
                            for k in ("reset by peer", "curl: (56)", "curl: (7)", "proxy", "connect")
                        ):
                            logger.warning("[garmin] Proxy connection error detected; retrying strategy directly without proxy")
                            _sso_tls.proxies = None
                            try:
                                run()
                                return None, None
                            except (gc_client.GarminConnectAuthenticationError, gc_client._MFARequired):
                                raise
                            except Exception as retry_e:
                                last_err = retry_e
                                continue
                        last_err = e
                        continue

                if rate_limited_count == len(strategies):
                    raise gc_client.GarminConnectTooManyRequestsError(
                        "All login strategies rate limited (429). Try again later."
                    )
                raise gc_client.GarminConnectConnectionError(
                    f"All login strategies exhausted: {last_err}"
                )
            finally:
                _sso_tls.proxies = None

        def patched_establish(
            self, ticket: str, sess: Any = None, service_url: str | None = None
        ) -> None:
            try:
                self._exchange_service_ticket(ticket, service_url=service_url)
                return
            except Exception as e:
                logger.warning(f"[garmin] DI token exchange failed ({e}), checking JWT_WEB fallback")

            if sess is not None:
                self.cs = sess

            svc = service_url or getattr(self, "_portal_service_url", f"https://connect.{self.domain}/app")
            if "mobile.integration" in (svc or ""):
                svc = getattr(self, "_portal_service_url", f"https://connect.{self.domain}/app")

            try:
                self.cs.get(
                    svc,
                    params={"ticket": ticket},
                    allow_redirects=True,
                    timeout=30,
                )
            except Exception as ge:
                logger.warning(f"[garmin] JWT_WEB consumption GET failed: {ge}")

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

        gc_client.Client._exchange_service_ticket = patched_exchange
        gc_client.Client._establish_session = patched_establish
        gc_client.Client._do_mobile_login = patched_mobile_login
        gc_client.Client._widget_web_login = patched_widget_login
        gc_client.Client._do_portal_web_login = patched_portal_login
        gc_client.Client.login = patched_client_login
        gc_client._rgm_cn_patched = True
        logger.info("[garmin] Successfully patched garminconnect client for China & Global SSO support")

    _patch_garminconnect()

except ImportError:
    Garmin = None
    HAS_GARMINCONNECT = False

TOKEN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tokens")


def _secure_chmod_path(path: str):
    """Enforces 0700 on directories and 0600 on files for OAuth token caches."""
    try:
        if os.path.isdir(path):
            os.chmod(path, 0o700)
            for root, dirs, files in os.walk(path):
                for d in dirs:
                    os.chmod(os.path.join(root, d), 0o700)
                for fn in files:
                    os.chmod(os.path.join(root, fn), 0o600)
        elif os.path.exists(path):
            os.chmod(path, 0o600)
    except Exception:
        pass


def remove_cached_garmin_tokens(email: Optional[str]) -> int:
    """Removes cached Garmin OAuth token files/directories for both CN and Global domains."""
    if not email or not str(email).strip():
        return 0
    import shutil
    safe_email = str(email).strip().replace("@", "_at_").replace(".", "_")
    removed = 0
    if not os.path.exists(TOKEN_DIR):
        return 0
    for region_tag in ("cn", "global"):
        tp = os.path.join(TOKEN_DIR, f"tokens_{safe_email}_{region_tag}.json")
        if os.path.exists(tp):
            try:
                if os.path.isdir(tp):
                    shutil.rmtree(tp, ignore_errors=True)
                else:
                    os.remove(tp)
                removed += 1
            except Exception as e:
                logger.warning(f"[garmin] Failed removing cached token {tp}: {e}")
    return removed

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

        os.makedirs(TOKEN_DIR, mode=0o700, exist_ok=True)
        _secure_chmod_path(TOKEN_DIR)
        safe_email = self.email.replace("@", "_at_").replace(".", "_")
        self.token_path = os.path.join(TOKEN_DIR, f"tokens_{safe_email}_{'cn' if self.is_cn else 'global'}.json")

    @staticmethod
    def _format_error(err: str, chosen_domain: str) -> str:
        err_lower = err.lower()
        is_cn_domain = "cn" in (chosen_domain or "").lower()
        if (
            "phone_registration_required" in err_lower
            or "phone_verification_required" in err_lower
            or "update phone number" in err_lower
            or "cn_verification_phone_number_needed" in err_lower
        ):
            if is_cn_domain:
                return (
                    "佳明官方安全策略要求该账号完成手机号绑定校验。请先用手机或电脑浏览器登录佳明中国官网 (connect.garmin.cn) "
                    "根据提示绑定手机号后，再返回小程序重新绑定。"
                )
            return (
                "佳明官方安全策略要求该国际版账号补充绑定手机号或开启两步验证（Update Phone Number）。"
                "请先用手机或电脑浏览器登录佳明国际官网 (www.garmin.com/account/profile)，在账号安全设置中添加手机号码"
                "或开启两步验证（Two-Step Verification）后，再返回小程序重新绑定。"
            )
        elif "password_change_required" in err_lower or "reset_password" in err_lower:
            return "佳明官方要求该账号更新密码后方可登录，请先前往 Garmin 官网修改密码后再返回绑定。"
        elif "locked" in err_lower or "account_locked" in err_lower:
            return "佳明账号已被锁定，请前往 Garmin 官网解锁或重置密码后再试。"
        elif "429" in err or "rate limit" in err_lower:
            return "佳明官方安全风控拦截（尝试过于频繁），请等待 2~3 分钟后再试。"
        elif "401" in err or "unauthorized" in err_lower or "invalid username or password" in err_lower:
            region_hint = "中国版 (garmin.cn)" if is_cn_domain else "国际版 (garmin.com)"
            return f"佳明账号或密码错误。您当前选择的是【{region_hint}】，如手表购自海外或账号不同区域请核对后重试。"
        elif "403" in err or "portal login failed" in err_lower:
            region_hint = "中国版 (garmin.cn)" if is_cn_domain else "国际版 (garmin.com)"
            return f"佳明官方服务器安全策略拦截 (HTTP 403)。您当前选择的是【{region_hint}】，请稍等 1~2 分钟后重试或确认账号所在区域。"
        elif "jwt_web" in err_lower or "cookie not set" in err_lower:
            return "佳明登录凭证解析失败，请检查账号密码或稍后重试。"
        elif "social profile" in err_lower or "socialprofile" in err_lower:
            region_hint = "中国版 (garmin.cn)" if is_cn_domain else "国际版 (garmin.com)"
            return f"佳明账号授权失败（无法获取个人资料）。您当前选择的是【{region_hint}】，请核对账号密码，或尝试切换到另一个区域（中国版/国际版）重试。"
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
                    _secure_chmod_path(self.token_path)
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

            # If cached token was used and failed (e.g. expired, "Failed to retrieve social profile", 401),
            # purge stale token and retry with raw credentials
            if use_token and os.path.exists(self.token_path):
                logger.info(f"[garmin] Cached token for {self.email} invalid/expired ({err1}). Purging stale token and retrying with credentials...")
                try:
                    os.remove(self.token_path)
                except Exception as rm_err:
                    logger.warning(f"[garmin] Failed to remove stale token file: {rm_err}")
                self.client = None
                return self.login(use_token=False)

            self.client = None

            # Only attempt alternate region fallback if error indicates invalid credentials / account region mismatch
            # Do NOT fall back on 429 rate limit or locked account
            is_cred_error = any(k in err1.lower() for k in ("401", "unauthorized", "invalid username or password", "social profile"))
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
                        _secure_chmod_path(alt_token_path)
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
                self.client = None
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
            masked_code = f"{clean_code[:1]}****{clean_code[-1:]}" if len(clean_code) >= 2 else "***"
            logger.info(f"[garmin] Submitting MFA code {masked_code} for {self.email}...")
            self.client.resume_login({}, clean_code)
            # Dump token to disk
            if hasattr(self.client, "client") and hasattr(self.client.client, "dump"):
                try:
                    self.client.client.dump(self.token_path)
                    _secure_chmod_path(self.token_path)
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
            self.last_error = f"获取佳明活动失败: {e}"
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
            self.last_error = f"获取佳明活动失败: {e}"
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
            "trail_running": "TrailRun",
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
            "splits_data": act.get("splits") or [],
            "laps_data": act.get("laps") or [],
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

        # 1. User Summary Baseline & Daytime Dynamics (RHR, VO2 Max, Body Battery, Steps, Active Calories, Stress, All-day HR Min/Max)
        try:
            summary = self.client.get_user_summary(date_str)
            if isinstance(summary, dict):
                sub = summary.get("userDailySummary") if isinstance(summary.get("userDailySummary"), dict) else {}
                rhr = summary.get("restingHeartRate") or sub.get("restingHeartRate")
                if rhr and rhr > 0:
                    metrics["resting_heart_rate"] = int(rhr)
                vo2 = summary.get("vo2MaxPrecise") or summary.get("vo2Max") or sub.get("vo2Max")
                if vo2 and vo2 > 0:
                    metrics["vo2_max"] = round(float(vo2), 1)
                bb = summary.get("bodyBatteryHighestValue") or sub.get("bodyBatteryHighestValue")
                if bb and bb > 0:
                    metrics["body_battery_max"] = int(bb)
                bb_min = summary.get("bodyBatteryLowestValue") or sub.get("bodyBatteryLowestValue")
                if bb_min and bb_min > 0:
                    metrics["body_battery_min"] = int(bb_min)
                bb_cur = summary.get("bodyBatteryMostRecentValue") or sub.get("bodyBatteryMostRecentValue")
                if bb_cur and bb_cur > 0:
                    metrics["body_battery_current"] = int(bb_cur)

                steps = summary.get("totalSteps") or sub.get("totalSteps")
                if steps is not None and int(steps) >= 0:
                    metrics["steps"] = int(steps)
                act_kcal = summary.get("activeKilocalories") or sub.get("activeKilocalories")
                if act_kcal is not None and float(act_kcal) >= 0:
                    metrics["active_calories"] = int(round(float(act_kcal)))

                stress_avg = summary.get("averageStressLevel") or sub.get("averageStressLevel")
                if stress_avg is not None and int(stress_avg) > 0:
                    metrics["stress_avg"] = int(stress_avg)
                stress_max = summary.get("maxStressLevel") or sub.get("maxStressLevel")
                if stress_max is not None and int(stress_max) > 0:
                    metrics["stress_max"] = int(stress_max)

                hr_min = summary.get("minHeartRate") or sub.get("minHeartRate")
                if hr_min is not None and int(hr_min) > 0:
                    metrics["hr_min"] = int(hr_min)
                hr_max = summary.get("maxHeartRate") or sub.get("maxHeartRate")
                if hr_max is not None and int(hr_max) > 0:
                    metrics["hr_max"] = int(hr_max)
        except Exception as e:
            logger.warning(f"[garmin] Could not fetch user summary for {date_str}: {e}")

        # 2. Sleep & Daytime Nap Data (Dedicated Garmin Wellness Daily Sleep Endpoint)
        try:
            sleep_data = self.client.get_sleep_data(date_str)
            if isinstance(sleep_data, dict):
                dto = sleep_data.get("dailySleepDTO")
                if isinstance(dto, dict):
                    dur = dto.get("sleepTimeSeconds")
                    if dur and dur > 0:
                        metrics["sleep_duration_seconds"] = int(dur)
                        metrics["sleep_duration_hours"] = round(dur / 3600.0, 1)

                    # Daytime Nap Detection (Garmin napTimeSeconds / dailyNapDTOS)
                    nap_sec = dto.get("napTimeSeconds") or 0
                    nap_dtos = dto.get("dailyNapDTOS") or sleep_data.get("dailyNapDTOS") or []
                    if (not nap_sec or int(nap_sec) <= 0) and isinstance(nap_dtos, list):
                        nap_sec = sum(int(n.get("napTimeSeconds") or 0) for n in nap_dtos if isinstance(n, dict))
                    if nap_sec and int(nap_sec) > 0:
                        metrics["nap_duration_seconds"] = int(nap_sec)

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

        # 4. Strict Night-Wear Validation:
        # If the user did not wear the watch during sleep (neither sleep_duration_seconds nor overnight HRV is present),
        # do not retain daytime-only RHR, weekly HRV baseline, or uncalibrated body battery as recovery metrics.
        has_overnight_wear = bool(
            (metrics.get("sleep_duration_seconds") and float(metrics.get("sleep_duration_seconds") or 0) > 0)
            or (metrics.get("hrv_last_night_avg") and float(metrics.get("hrv_last_night_avg") or 0) > 0)
        )
        if not has_overnight_wear:
            metrics.pop("resting_heart_rate", None)
            metrics.pop("body_battery_max", None)
            metrics.pop("body_battery_min", None)
            metrics.pop("body_battery_current", None)
            metrics.pop("hrv_weekly_avg", None)
            metrics.pop("hrv_status", None)
            metrics.pop("sleep_score", None)
            metrics.pop("sleep_duration_hours", None)

        return metrics

    @staticmethod
    def _normalize_garmin_lap_item(lap_dto: Dict[str, Any], default_idx: int) -> Optional[Dict[str, Any]]:
        if not isinstance(lap_dto, dict):
            return None
        dist_m = float(lap_dto.get("distance") or 0.0)
        mov_s = float(lap_dto.get("movingDuration") or lap_dto.get("duration") or 0.0)
        elap_s = float(lap_dto.get("elapsedDuration") or lap_dto.get("duration") or mov_s)
        if dist_m <= 1.0 and mov_s <= 1.0:
            return None

        avg_spd = float(lap_dto.get("averageMovingSpeed") or lap_dto.get("averageSpeed") or 0.0)
        if avg_spd > 0.35:
            p_sec = int(round(1000.0 / avg_spd))
        elif dist_m >= 20.0 and mov_s > 0:
            p_sec = int(round(mov_s / (dist_m / 1000.0)))
        else:
            p_sec = None
        if p_sec is not None and not (110 <= p_sec <= 1200):
            p_sec = None

        gap_spd = float(lap_dto.get("avgGradeAdjustedSpeed") or 0.0)
        gap_sec = int(round(1000.0 / gap_spd)) if gap_spd > 0.35 else None
        if gap_sec is not None and not (110 <= gap_sec <= 1200):
            gap_sec = None

        raw_type = str(lap_dto.get("type") or lap_dto.get("splitType") or lap_dto.get("intensityType") or "").upper()
        if raw_type.startswith("RWD_"):
            # Run/Walk Detection summary buckets overlap the full activity distance; never treat as sequential laps
            return None
        if "WARMUP" in raw_type:
            itype = "WARMUP"
        elif "COOLDOWN" in raw_type:
            itype = "COOLDOWN"
        elif "RECOVERY" in raw_type or "REST" in raw_type:
            itype = "RECOVERY"
        elif "ACTIVE" in raw_type and raw_type != "INTERVAL":
            itype = "ACTIVE"
        else:
            itype = "AUTO"

        avg_hr = lap_dto.get("averageHR")
        max_hr = lap_dto.get("maxHR")
        cad = lap_dto.get("averageRunCadence")
        pwr = lap_dto.get("averagePower")

        return {
            "lap_index": int(lap_dto.get("lapIndex") or default_idx),
            "distance_m": round(dist_m, 1),
            "duration_s": round(mov_s if mov_s > 0 else elap_s, 1),
            "elapsed_s": round(elap_s, 1),
            "pace_sec": p_sec,
            "pace_str": f"{p_sec // 60}:{p_sec % 60:02d}/km" if p_sec else "—",
            "gap_sec": gap_sec,
            "avg_hr": int(round(float(avg_hr))) if avg_hr else None,
            "max_hr": int(round(float(max_hr))) if max_hr else None,
            "avg_cadence": int(round(float(cad))) if cad else None,
            "avg_power": int(round(float(pwr))) if pwr else None,
            "elev_gain_m": round(float(lap_dto.get("elevationGain") or 0.0), 1),
            "elev_loss_m": round(float(lap_dto.get("elevationLoss") or 0.0), 1),
            "intensity_type": itype,
        }

    def fetch_activity_gps_track(self, activity_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches GPS polyline coordinates, elevation profile, high-resolution telemetry stream,
        and per-lap / structured workout splits for an activity from Garmin.
        Transforms WGS-84 coordinates to GCJ-02 (China standard) and downsamples points for smooth rendering.
        """
        clean_id = str(activity_id).replace("garmin_", "").strip()
        if not self.client:
            if not self.login():
                return None

        try:
            logger.info(f"[garmin] Fetching activity details & splits for {clean_id}...")
            details = self.client.get_activity_details(clean_id)
            if not details or not isinstance(details, dict):
                logger.warning(f"[garmin] No details returned for activity {clean_id}")
                details = {}

            geo = details.get("geoPolylineDTO") or {}
            raw_polyline = geo.get("polyline") or []

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

            sampled_points = downsample_points(gcj_points, max_points=250) if gcj_points else []

            # Process Elevation & Full Telemetry Profile (Distance, Time, Speed/Pace, GAP, HR, Cadence, Elevation)
            descriptors = details.get("metricDescriptors") or []
            desc_map = {
                m["key"]: m.get("metricsIndex")
                for m in descriptors
                if isinstance(m, dict) and "key" in m and "metricsIndex" in m
            }
            elev_idx = desc_map.get("directElevation")
            dist_idx = desc_map.get("sumDistance")
            mov_idx = desc_map.get("sumMovingDuration") if desc_map.get("sumMovingDuration") is not None else desc_map.get("sumDuration")
            elap_idx = desc_map.get("sumElapsedDuration") if desc_map.get("sumElapsedDuration") is not None else mov_idx
            spd_idx = desc_map.get("directSpeed")
            gap_idx = desc_map.get("directGradeAdjustedSpeed")
            hr_idx = desc_map.get("directHeartRate")
            cad_idx = desc_map.get("directDoubleCadence") if desc_map.get("directDoubleCadence") is not None else desc_map.get("directRunCadence")

            raw_profile = []
            raw_telemetry = []
            metrics_list = details.get("activityDetailMetrics") or []

            def _metric_at(arr: List[Any], idx: Optional[int]) -> Optional[float]:
                if idx is None or idx >= len(arr) or arr[idx] is None:
                    return None
                try:
                    return float(arr[idx])
                except (ValueError, TypeError):
                    return None

            if dist_idx is not None and metrics_list:
                for m_obj in metrics_list:
                    m_vals = m_obj.get("metrics") or []
                    d = _metric_at(m_vals, dist_idx)
                    if d is None:
                        continue
                    e = _metric_at(m_vals, elev_idx)
                    hr_val = _metric_at(m_vals, hr_idx)
                    spd_val = _metric_at(m_vals, spd_idx)
                    gap_val = _metric_at(m_vals, gap_idx)
                    cad_val = _metric_at(m_vals, cad_idx)
                    t_sec = _metric_at(m_vals, mov_idx)
                    if t_sec is None:
                        t_sec = _metric_at(m_vals, elap_idx)

                    p_sec = int(round(1000.0 / spd_val)) if (spd_val and spd_val > 0.35) else None
                    if p_sec is not None and not (110 <= p_sec <= 1200):
                        p_sec = None
                    g_sec = int(round(1000.0 / gap_val)) if (gap_val and gap_val > 0.35) else None
                    if g_sec is not None and not (110 <= g_sec <= 1200):
                        g_sec = None
                    hr_int = int(round(hr_val)) if (hr_val is not None and 35 <= hr_val <= 235) else None
                    cad_int = int(round(cad_val)) if (cad_val is not None and 80 <= cad_val <= 250) else None
                    dist_km_val = round(d / 1000.0, 3)

                    if e is not None:
                        raw_profile.append({
                            "dist_km": round(d / 1000.0, 2),
                            "elevation_m": round(e, 1),
                            "hr": hr_int,
                            "pace_sec": p_sec,
                        })
                    raw_telemetry.append({
                        "dist_km": dist_km_val,
                        "elapsed_s": round(t_sec, 1) if t_sec is not None else None,
                        "pace_sec": p_sec,
                        "gap_sec": g_sec,
                        "hr": hr_int,
                        "cadence": cad_int,
                        "elevation_m": round(e, 1) if e is not None else None,
                    })

            sampled_elevation = downsample_points(raw_profile, max_points=120) if raw_profile else []
            sampled_telemetry = downsample_points(raw_telemetry, max_points=240) if raw_telemetry else []

            # Fetch per-lap splits & structured workout phases
            normalized_laps: List[Dict[str, Any]] = []
            structured_phases: List[Dict[str, Any]] = []
            try:
                sp_resp = self.client.get_activity_splits(clean_id)
                if isinstance(sp_resp, dict):
                    for i, l_dto in enumerate(sp_resp.get("lapDTOs") or [], start=1):
                        norm_l = self._normalize_garmin_lap_item(l_dto, i)
                        if norm_l:
                            normalized_laps.append(norm_l)
            except Exception as se:
                logger.warning(f"[garmin] get_activity_splits warning for {clean_id}: {se}")

            try:
                ts_resp = self.client.get_activity_typed_splits(clean_id)
                raw_ts = ts_resp.get("splits") if isinstance(ts_resp, dict) else None
                if isinstance(raw_ts, list) and len(raw_ts) >= 2:
                    candidate_phases: List[Dict[str, Any]] = []
                    for i, s_dto in enumerate(raw_ts, start=1):
                        norm_s = self._normalize_garmin_lap_item(s_dto, i)
                        if norm_s:
                            candidate_phases.append(norm_s)
                    has_stage_tag = any(
                        x.get("intensity_type") in ("WARMUP", "COOLDOWN", "RECOVERY")
                        for x in candidate_phases
                    )
                    laps_total_m = sum(float(x.get("distance_m") or 0.0) for x in normalized_laps)
                    cand_total_m = sum(float(x.get("distance_m") or 0.0) for x in candidate_phases)
                    seq_valid = (
                        laps_total_m <= 0
                        or (0.80 * laps_total_m <= cand_total_m <= 1.20 * laps_total_m)
                    )
                    if len(candidate_phases) >= 2 and has_stage_tag and seq_valid:
                        structured_phases = candidate_phases
            except Exception as tse:
                logger.debug(f"[garmin] get_activity_typed_splits notice for {clean_id}: {tse}")

            if not sampled_points and not sampled_telemetry and not normalized_laps:
                logger.info(f"[garmin] Activity {clean_id} has neither polyline nor telemetry/splits")
                return None

            track_data: Dict[str, Any] = {
                "activity_id": f"garmin_{clean_id}",
                "total_points": len(sampled_points),
                "original_point_count": len(raw_polyline),
                "points": sampled_points,
                "elevation_profile": sampled_elevation,
                "telemetry_series": sampled_telemetry,
                "laps": normalized_laps,
                "structured_splits": structured_phases,
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
                f"[garmin] Processed detail for {clean_id}: {len(sampled_points)} GPS pts, "
                f"{len(normalized_laps)} laps, {len(sampled_telemetry)} telemetry steps"
            )
            return track_data
        except Exception as e:
            logger.error(f"[garmin] Error fetching GPS track/details for {clean_id}: {e}", exc_info=True)
            return None

