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


# Paths that do NOT require authentication
_PUBLIC_PATHS = frozenset({
    "/",
    "/api/health",
    "/docs",
    "/openapi.json",
})

_PUBLIC_PREFIXES = (
    "/api/webhook/",
)


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
            decoded = firebase_auth.verify_id_token(token)
            request.state.uid = decoded["uid"]
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
