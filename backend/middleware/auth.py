import os
import re
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from config import settings
from utils.security import is_strict_auth_mode

logger = logging.getLogger("auth_middleware")

# Exact/prefix public routes that do not require an authenticated Bearer JWT
PUBLIC_EXACT_PATHS = {
    "/",
    "/api/health",
    "/privacy",
    "/citations",
    "/api/auth/wechat/miniapp-login",
    "/api/auth/app/wechat-login",
    "/api/auth/apple/login",
    "/api/auth/demo-login",
    "/api/auth/device-login",
    "/api/auth/email/login",
    "/api/auth/email/signup",
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/wechat/confirm-login",
    "/api/auth/wechat/web-qr/create",
    "/api/auth/wechat/web-qr/scan",
    "/api/auth/wechat/web-qr/confirm",
    "/api/admin/login",
    "/api/miniapp/telemetry/batch",
    "/api/assistant/navigate",
    "/api/assistant/transcribe",
    "/api/notifications/subscribe-config",
}

PUBLIC_PREFIX_PATHS = (
    "/api/avatars/",
    "/api/race-photos/",
    "/api/showcase-photos/",
    "/api/auth/wechat/web-qr/status/",
)

PUBLIC_GET_PATTERNS = (
    re.compile(r"^/api/community/invites/[^/]+$"),
    re.compile(r"^/api/community/showcase/(?:plaza|clubs/[^/]+|coaches/[^/]+)$"),
    re.compile(r"^/api/team/[^/]+/events/[^/]+$"),
    re.compile(r"^/api/team/[^/]+/share-info$"),
)


def _is_public_route(method: str, path: str) -> bool:
    if path in PUBLIC_EXACT_PATHS:
        return True
    if any(path.startswith(p) for p in PUBLIC_PREFIX_PATHS):
        return True
    if not is_strict_auth_mode() and path in ("/docs", "/redoc", "/openapi.json"):
        return True
    if method.upper() == "GET":
        if any(pat.match(path) for pat in PUBLIC_GET_PATTERNS):
            return True
    return False


class SupabaseAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method.upper()
        request.state.user_id = None
        request.state.user_email = None
        request.state.is_super_admin = False

        if method == "OPTIONS":
            return await call_next(request)

        is_public = _is_public_route(method, path)
        strict_auth = is_strict_auth_mode()

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            try:
                import jwt
                payload = jwt.decode(
                    token,
                    settings.SUPABASE_JWT_SECRET,
                    algorithms=["HS256"],
                    audience="authenticated",
                    options={"verify_aud": False},
                )
                user_id = payload.get("sub") or payload.get("uid")
                request.state.user_id = user_id
                request.state.user_email = payload.get("email")
                request.state.is_super_admin = bool(payload.get("is_super_admin", False))
            except Exception as e:
                if (
                    not strict_auth
                    and os.getenv("RGM_ALLOW_TEST_RAW_TOKEN") == "1"
                    and len(token) > 0
                    and not token.startswith("eyJ")
                ):
                    request.state.user_id = token
                else:
                    logger.debug(f"[auth] Rejected invalid/expired Bearer JWT on {path}: {e}")
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "登录凭证已过期或无效，请重新登录"},
                    )
        else:
            if strict_auth and not is_public and path.startswith("/api/"):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "安全拦截：请先登录后再访问该接口"},
                )
            if strict_auth:
                from utils.local_store import LocalStore
                for qp in ("viewer_uid", "operator_uid"):
                    qv = (request.query_params.get(qp) or "").strip()
                    if qv and LocalStore.is_super_admin(qv):
                        return JSONResponse(
                            status_code=401,
                            content={"detail": "安全拦截：特权身份参数必须附带有效的 Bearer 认证令牌"},
                        )

        # Prevent authenticated horizontal/vertical IDOR spoofing via ?viewer_uid=, ?operator_uid=, or x-user-id
        if request.state.user_id and not request.state.is_super_admin:
            from utils.local_store import LocalStore
            if not LocalStore.is_super_admin(request.state.user_id):
                caller_canonical = LocalStore.resolve_user_id(request.state.user_id)
                for qp in ("viewer_uid", "operator_uid"):
                    qv = (request.query_params.get(qp) or "").strip()
                    if qv and LocalStore.resolve_user_id(qv) != caller_canonical:
                        return JSONResponse(
                            status_code=403,
                            content={"detail": f"安全拦截：请求参数 {qp} 与当前登录身份不一致"},
                        )
                hdr_uid = (request.headers.get("x-user-id") or "").strip()
                if hdr_uid and LocalStore.resolve_user_id(hdr_uid) != caller_canonical:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "安全拦截：请求头 x-user-id 与当前登录身份不一致"},
                    )

        return await call_next(request)
