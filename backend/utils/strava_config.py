"""
Strava API URL Configuration — single source of truth for all Strava endpoints.

Centralizes the base URLs so the upcoming Strava API migration
(www.strava.com/api/v3 → www.api-v3.strava.com, effective June 1, 2027)
can be handled with a one-line change.

The OAuth base URL is separate because it may or may not change;
Strava's migration announcement only mentions the API base URL.
"""

import os

# ── API base URL ──────────────────────────────────────────────────────────────
# Current:  https://www.strava.com/api/v3
# After June 1 2027:  https://www.api-v3.strava.com
#
# Override via env var for testing the new URL before the cutover date.
STRAVA_API_BASE = os.getenv(
    "STRAVA_API_BASE",
    "https://www.strava.com/api/v3",
)

# ── OAuth base URL ────────────────────────────────────────────────────────────
# Token exchange, authorization, and (future) revocation.
STRAVA_OAUTH_BASE = os.getenv(
    "STRAVA_OAUTH_BASE",
    "https://www.strava.com/oauth",
)

# ── Convenience: full endpoint URLs ──────────────────────────────────────────

STRAVA_OAUTH_TOKEN_URL = f"{STRAVA_OAUTH_BASE}/token"
STRAVA_OAUTH_AUTHORIZE_URL = f"{STRAVA_OAUTH_BASE}/authorize"
# New revoke endpoint (available now, mandatory after June 1, 2027)
STRAVA_OAUTH_REVOKE_URL = f"{STRAVA_OAUTH_BASE}/revoke"
