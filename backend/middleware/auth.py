import os
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from config import settings

logger = logging.getLogger("auth_middleware")

# Public routes that bypass token verification
PUBLIC_PATHS = [
    "/",
    "/api/health",
    "/docs",
    "/openapi.json",
    "/api/auth/wechat/miniapp-login",
    "/api/auth/app/wechat-login",
    "/api/auth/apple/login",
    "/api/auth/demo-login",
    "/api/auth/device-login",
    "/api/auth/email/login",
    "/api/auth/email/signup",
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/phone-login",
    "/api/auth/send-sms",
    "/api/miniapp/telemetry/batch",
]


class SupabaseAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        request.state.user_id = None
        request.state.is_super_admin = False
        if any(path == p or path.startswith(p + "/") for p in PUBLIC_PATHS):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            if settings.ENVIRONMENT.lower() == "production":
                from utils.local_store import LocalStore
                for qp in ("viewer_uid", "operator_uid"):
                    qv = (request.query_params.get(qp) or "").strip()
                    if qv and LocalStore.is_super_admin(qv):
                        return JSONResponse(
                            status_code=401,
                            content={"detail": "安全拦截：特权身份参数必须附带有效的 Bearer 认证令牌"},
                        )
            return await call_next(request)

        token = auth_header.replace("Bearer ", "").strip()
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
                settings.ENVIRONMENT.lower() != "production"
                and os.getenv("RGM_ALLOW_TEST_RAW_TOKEN") == "1"
                and len(token) > 0
                and not token.startswith("eyJ")
            ):
                request.state.user_id = token
            else:
                logger.debug(f"[auth] JWT verification notice: {e}")
                request.state.user_id = None

        # Prevent authenticated horizontal/vertical IDOR spoofing via ?viewer_uid= or ?operator_uid=
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

        response = await call_next(request)
        return response
