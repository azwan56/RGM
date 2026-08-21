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
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/phone-login",
    "/api/auth/send-sms",
]

class SupabaseAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path == p or path.startswith(p + "/") for p in PUBLIC_PATHS):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # Allow non-strict paths or return 401
            request.state.user_id = None
            return await call_next(request)

        token = auth_header.replace("Bearer ", "").strip()
        try:
            # Decode token using Supabase JWT secret or GoTrue verification
            import jwt
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_aud": False}
            )
            user_id = payload.get("sub") or payload.get("uid")
            request.state.user_id = user_id
            request.state.user_email = payload.get("email")
        except Exception as e:
            # In development fallback to raw token if in dev mode
            if settings.ENVIRONMENT == "development" and len(token) > 0 and not token.startswith("eyJ"):
                request.state.user_id = token
            else:
                logger.debug(f"[auth] JWT verification notice: {e}")
                request.state.user_id = None

        response = await call_next(request)
        return response
