"""
Firebase Auth Middleware for FastAPI.

Validates Firebase ID tokens from the Authorization header.
Injects `request.state.uid` for authenticated routes.
Skips auth for public endpoints (health, webhooks, root).
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import firebase_admin.auth as firebase_auth
import time


# Paths that do NOT require authentication
_PUBLIC_PATHS = frozenset({
    "/",
    "/api/health",
    "/docs",
    "/openapi.json",
})

_PUBLIC_PREFIXES = (
    "/api/webhook/",
    "/api/admin/",
    "/api/wecom/",
)

# ── Token verification cache (saves 20-100ms per request) ────────────────────
# Key: token hash → (uid, expiry_timestamp)
_token_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 300  # 5 minutes
_MAX_CACHE_SIZE = 200


def _verify_token_cached(token: str) -> str:
    """Verify a Firebase ID token with in-memory caching."""
    # Use last 32 chars of token as cache key (unique enough, avoids storing full token)
    cache_key = token[-32:]
    now = time.time()

    # Check cache first
    cached = _token_cache.get(cache_key)
    if cached:
        uid, expires = cached
        if now < expires:
            return uid

    # Cache miss — verify with Firebase
    decoded = firebase_auth.verify_id_token(token)
    uid = decoded["uid"]

    # Evict oldest entries if cache is too large
    if len(_token_cache) >= _MAX_CACHE_SIZE:
        # Remove expired entries first
        expired_keys = [k for k, (_, exp) in _token_cache.items() if now >= exp]
        for k in expired_keys:
            del _token_cache[k]
        # If still too large, clear half
        if len(_token_cache) >= _MAX_CACHE_SIZE:
            keys_to_remove = list(_token_cache.keys())[:_MAX_CACHE_SIZE // 2]
            for k in keys_to_remove:
                del _token_cache[k]

    _token_cache[cache_key] = (uid, now + _CACHE_TTL)
    return uid


class FirebaseAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts and validates a Firebase ID token from the
    Authorization: Bearer <token> header.

    On success: sets request.state.uid to the verified Firebase UID.
    On failure: returns 401 Unauthorized.
    On public paths: skips validation, sets request.state.uid = None.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public endpoints
        if path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            request.state.uid = None
            return await call_next(request)

        # Skip auth for OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Extract token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header. Expected: Bearer <firebase_id_token>"},
            )

        token = auth_header.split("Bearer ", 1)[1].strip()
        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Empty token"},
            )

        try:
            request.state.uid = _verify_token_cached(token)
        except firebase_auth.ExpiredIdTokenError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token expired. Please re-authenticate."},
            )
        except firebase_auth.InvalidIdTokenError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid Firebase token."},
            )
        except Exception as e:
            return JSONResponse(
                status_code=401,
                content={"detail": f"Authentication failed: {str(e)}"},
            )

        return await call_next(request)

