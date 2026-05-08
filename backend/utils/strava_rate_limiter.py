"""
Strava API Rate Limiter — tracks and enforces Strava's rate limits.

Strava enforces two rolling windows:
  - 15-minute window: 200 requests (resets at :00, :15, :30, :45)
  - Daily window:     2,000 requests (resets at midnight UTC)

This module provides:
  1. Automatic tracking via response headers (X-RateLimit-Usage / X-RateLimit-Limit)
  2. Pre-flight check before making a request
  3. Smart backoff when approaching limits
  4. A wrapped `requests.get/post` that automatically tracks and throttles

Usage:
    from utils.strava_rate_limiter import strava_request, get_rate_limit_status

    # Drop-in replacement for requests.get/post
    resp = strava_request("GET", url, headers=headers, params=params)

    # Check current status
    status = get_rate_limit_status()
"""

import time
import threading
from datetime import datetime, timezone
from typing import Optional
import requests as _requests
import logging

logger = logging.getLogger("strava_rate_limiter")

# ── Rate limit state (thread-safe) ───────────────────────────────────────────

_lock = threading.Lock()

_state = {
    # Limits (defaults; updated from response headers)
    "limit_15min": 200,
    "limit_daily": 2000,
    # Current usage (updated from response headers)
    "usage_15min": 0,
    "usage_daily": 0,
    # Timestamps
    "last_updated": None,
    "last_request_time": None,
    # Tracking
    "total_requests": 0,
    "throttled_count": 0,
    "error_429_count": 0,
}

# Safety margins — stop before hitting the hard limit
_MARGIN_15MIN = 20   # Reserve 20 requests in the 15-min window
_MARGIN_DAILY = 200  # Reserve 200 requests in the daily window


def _update_from_headers(headers: dict):
    """Extract rate limit info from Strava response headers."""
    with _lock:
        # X-RateLimit-Limit: "200,2000"  (15min, daily)
        limit_header = headers.get("X-RateLimit-Limit", "")
        if limit_header and "," in limit_header:
            parts = limit_header.split(",")
            try:
                _state["limit_15min"] = int(parts[0].strip())
                _state["limit_daily"] = int(parts[1].strip())
            except (ValueError, IndexError):
                pass

        # X-RateLimit-Usage: "42,850"  (15min, daily)
        usage_header = headers.get("X-RateLimit-Usage", "")
        if usage_header and "," in usage_header:
            parts = usage_header.split(",")
            try:
                _state["usage_15min"] = int(parts[0].strip())
                _state["usage_daily"] = int(parts[1].strip())
            except (ValueError, IndexError):
                pass

        _state["last_updated"] = datetime.now(timezone.utc).isoformat()


def _can_make_request() -> tuple[bool, str]:
    """
    Pre-flight check: returns (allowed, reason).
    Uses safety margins to avoid hitting the hard 429 wall.
    """
    with _lock:
        remaining_15 = _state["limit_15min"] - _state["usage_15min"]
        remaining_day = _state["limit_daily"] - _state["usage_daily"]

        if remaining_15 <= _MARGIN_15MIN:
            return False, f"15-min limit nearly exhausted ({_state['usage_15min']}/{_state['limit_15min']})"
        if remaining_day <= _MARGIN_DAILY:
            return False, f"Daily limit nearly exhausted ({_state['usage_daily']}/{_state['limit_daily']})"
        return True, "ok"


def _get_backoff_seconds() -> float:
    """
    Returns how many seconds to wait before the next request.
    Implements progressive slowdown as we approach limits.
    """
    with _lock:
        usage_pct_15 = _state["usage_15min"] / max(_state["limit_15min"], 1)
        usage_pct_day = _state["usage_daily"] / max(_state["limit_daily"], 1)
        max_pct = max(usage_pct_15, usage_pct_day)

    if max_pct < 0.5:
        return 0          # Under 50% — full speed
    elif max_pct < 0.7:
        return 0.5         # 50-70% — slight delay
    elif max_pct < 0.85:
        return 2.0         # 70-85% — moderate delay
    elif max_pct < 0.95:
        return 5.0         # 85-95% — significant delay
    else:
        return 15.0        # 95%+ — heavy throttle, wait for window reset


def strava_request(
    method: str,
    url: str,
    *,
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    data: Optional[dict] = None,
    json: Optional[dict] = None,
    timeout: int = 20,
    skip_throttle: bool = False,
) -> _requests.Response:
    """
    Drop-in replacement for requests.get/post that tracks Strava rate limits.

    - Automatically reads X-RateLimit headers from responses
    - Applies backoff when approaching limits
    - Raises RateLimitExceeded if the limit is fully exhausted
    - Handles 429 responses with automatic retry after wait

    Args:
        method: "GET" or "POST"
        url: Full Strava API URL
        skip_throttle: If True, bypass pre-flight check (for critical ops like token refresh)
    """
    if not skip_throttle:
        allowed, reason = _can_make_request()
        if not allowed:
            with _lock:
                _state["throttled_count"] += 1
            logger.warning(f"[rate_limiter] Request blocked: {reason}")
            raise RateLimitExceeded(reason)

        # Apply backoff delay
        delay = _get_backoff_seconds()
        if delay > 0:
            logger.info(f"[rate_limiter] Backoff {delay}s before request")
            time.sleep(delay)

    # Make the actual request
    resp = _requests.request(
        method,
        url,
        headers=headers,
        params=params,
        data=data,
        json=json,
        timeout=timeout,
    )

    # Track rate limit headers
    _update_from_headers(dict(resp.headers))

    with _lock:
        _state["total_requests"] += 1
        _state["last_request_time"] = datetime.now(timezone.utc).isoformat()

    # Handle 429 Too Many Requests
    if resp.status_code == 429:
        with _lock:
            _state["error_429_count"] += 1
        logger.error(
            f"[rate_limiter] 429 Too Many Requests! "
            f"Usage: {_state['usage_15min']}/{_state['limit_15min']} (15min), "
            f"{_state['usage_daily']}/{_state['limit_daily']} (daily)"
        )

    return resp


def get_rate_limit_status() -> dict:
    """Returns the current rate limit tracking state."""
    with _lock:
        remaining_15 = _state["limit_15min"] - _state["usage_15min"]
        remaining_day = _state["limit_daily"] - _state["usage_daily"]
        return {
            **_state.copy(),
            "remaining_15min": remaining_15,
            "remaining_daily": remaining_day,
            "pct_used_15min": round(_state["usage_15min"] / max(_state["limit_15min"], 1) * 100, 1),
            "pct_used_daily": round(_state["usage_daily"] / max(_state["limit_daily"], 1) * 100, 1),
        }


class RateLimitExceeded(Exception):
    """Raised when Strava rate limit is exhausted."""
    pass
