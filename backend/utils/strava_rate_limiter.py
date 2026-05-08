"""
Strava API Rate Limiter — tracks and enforces Strava's rate limits.

Strava enforces TWO sets of rate limits per application:

  Overall (all endpoints):
    - 15-minute: 200 requests (resets at :00, :15, :30, :45)
    - Daily:     2,000 requests (resets at midnight UTC)

  Read / Non-Upload (all endpoints EXCEPT POST activities, POST uploads):
    - 15-minute: 100 requests
    - Daily:     1,000 requests

Response headers to track:
    X-RateLimit-Limit / X-RateLimit-Usage        → overall limits
    X-ReadRateLimit-Limit / X-ReadRateLimit-Usage → read-only limits

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
    # ── Overall limits (all endpoints) ──
    "overall_limit_15min": 200,
    "overall_limit_daily": 2000,
    "overall_usage_15min": 0,
    "overall_usage_daily": 0,
    # ── Read / Non-Upload limits (GET endpoints) ──
    "read_limit_15min": 100,
    "read_limit_daily": 1000,
    "read_usage_15min": 0,
    "read_usage_daily": 0,
    # ── Tracking ──
    "last_updated": None,
    "last_request_time": None,
    "total_requests": 0,
    "throttled_count": 0,
    "error_429_count": 0,
}

# Safety margins — stop before hitting the hard limit
_OVERALL_MARGIN_15MIN = 20   # Reserve 20 in overall 15-min window
_OVERALL_MARGIN_DAILY = 200  # Reserve 200 in overall daily window
_READ_MARGIN_15MIN = 10      # Reserve 10 in read 15-min window (stricter)
_READ_MARGIN_DAILY = 100     # Reserve 100 in read daily window


def _parse_pair(header_value: str) -> tuple[int, int]:
    """Parse a 'N,N' header into (fifteen_min, daily) integers."""
    if not header_value or "," not in header_value:
        return (0, 0)
    parts = header_value.split(",")
    try:
        return (int(parts[0].strip()), int(parts[1].strip()))
    except (ValueError, IndexError):
        return (0, 0)


def _update_from_headers(headers: dict):
    """Extract rate limit info from Strava response headers."""
    with _lock:
        # Overall: X-RateLimit-Limit / X-RateLimit-Usage
        # Note: Strava uses inconsistent casing (X-Ratelimit vs X-RateLimit)
        overall_limit = (
            headers.get("X-RateLimit-Limit")
            or headers.get("X-Ratelimit-Limit", "")
        )
        overall_usage = (
            headers.get("X-RateLimit-Usage")
            or headers.get("X-Ratelimit-Usage", "")
        )

        if overall_limit:
            lim15, lim_d = _parse_pair(overall_limit)
            if lim15 > 0:
                _state["overall_limit_15min"] = lim15
            if lim_d > 0:
                _state["overall_limit_daily"] = lim_d

        if overall_usage:
            u15, u_d = _parse_pair(overall_usage)
            _state["overall_usage_15min"] = u15
            _state["overall_usage_daily"] = u_d

        # Read / Non-Upload: X-ReadRateLimit-Limit / X-ReadRateLimit-Usage
        read_limit = (
            headers.get("X-ReadRateLimit-Limit")
            or headers.get("X-Readratelimit-Limit", "")
        )
        read_usage = (
            headers.get("X-ReadRateLimit-Usage")
            or headers.get("X-Readratelimit-Usage", "")
        )

        if read_limit:
            lim15, lim_d = _parse_pair(read_limit)
            if lim15 > 0:
                _state["read_limit_15min"] = lim15
            if lim_d > 0:
                _state["read_limit_daily"] = lim_d

        if read_usage:
            u15, u_d = _parse_pair(read_usage)
            _state["read_usage_15min"] = u15
            _state["read_usage_daily"] = u_d

        _state["last_updated"] = datetime.now(timezone.utc).isoformat()


def _can_make_request(is_read: bool = True) -> tuple[bool, str]:
    """
    Pre-flight check: returns (allowed, reason).
    Uses safety margins to avoid hitting the hard 429 wall.

    Args:
        is_read: True for GET requests (subject to both overall + read limits),
                 False for POST uploads/activities (only overall limits apply).
    """
    with _lock:
        # Always check overall limits
        overall_rem_15 = _state["overall_limit_15min"] - _state["overall_usage_15min"]
        overall_rem_day = _state["overall_limit_daily"] - _state["overall_usage_daily"]

        if overall_rem_15 <= _OVERALL_MARGIN_15MIN:
            return False, (
                f"Overall 15-min limit nearly exhausted "
                f"({_state['overall_usage_15min']}/{_state['overall_limit_15min']})"
            )
        if overall_rem_day <= _OVERALL_MARGIN_DAILY:
            return False, (
                f"Overall daily limit nearly exhausted "
                f"({_state['overall_usage_daily']}/{_state['overall_limit_daily']})"
            )

        # For read (non-upload) requests, also check stricter read limits
        if is_read:
            read_rem_15 = _state["read_limit_15min"] - _state["read_usage_15min"]
            read_rem_day = _state["read_limit_daily"] - _state["read_usage_daily"]

            if read_rem_15 <= _READ_MARGIN_15MIN:
                return False, (
                    f"Read 15-min limit nearly exhausted "
                    f"({_state['read_usage_15min']}/{_state['read_limit_15min']})"
                )
            if read_rem_day <= _READ_MARGIN_DAILY:
                return False, (
                    f"Read daily limit nearly exhausted "
                    f"({_state['read_usage_daily']}/{_state['read_limit_daily']})"
                )

        return True, "ok"


def _get_backoff_seconds(is_read: bool = True) -> float:
    """
    Returns how many seconds to wait before the next request.
    Implements progressive slowdown as we approach limits.
    Uses the TIGHTER of overall vs read limits for read requests.
    """
    with _lock:
        overall_pct_15 = _state["overall_usage_15min"] / max(_state["overall_limit_15min"], 1)
        overall_pct_day = _state["overall_usage_daily"] / max(_state["overall_limit_daily"], 1)
        max_pct = max(overall_pct_15, overall_pct_day)

        if is_read:
            read_pct_15 = _state["read_usage_15min"] / max(_state["read_limit_15min"], 1)
            read_pct_day = _state["read_usage_daily"] / max(_state["read_limit_daily"], 1)
            max_pct = max(max_pct, read_pct_15, read_pct_day)

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

    - Automatically reads X-RateLimit and X-ReadRateLimit headers
    - Applies backoff when approaching limits (overall AND read limits)
    - Raises RateLimitExceeded if the limit is fully exhausted
    - Handles 429 responses with automatic tracking

    Args:
        method: "GET" or "POST"
        url: Full Strava API URL
        skip_throttle: If True, bypass pre-flight check (for critical ops like token refresh)
    """
    is_read = method.upper() == "GET"

    if not skip_throttle:
        allowed, reason = _can_make_request(is_read=is_read)
        if not allowed:
            with _lock:
                _state["throttled_count"] += 1
            logger.warning(f"[rate_limiter] Request blocked: {reason}")
            raise RateLimitExceeded(reason)

        # Apply backoff delay
        delay = _get_backoff_seconds(is_read=is_read)
        if delay > 0:
            logger.info(f"[rate_limiter] Backoff {delay}s before {method} request")
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

    # Track rate limit headers from response
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
            f"Overall: {_state['overall_usage_15min']}/{_state['overall_limit_15min']} (15min), "
            f"{_state['overall_usage_daily']}/{_state['overall_limit_daily']} (daily) | "
            f"Read: {_state['read_usage_15min']}/{_state['read_limit_15min']} (15min), "
            f"{_state['read_usage_daily']}/{_state['read_limit_daily']} (daily)"
        )

    return resp


def get_rate_limit_status() -> dict:
    """Returns the current rate limit tracking state for monitoring."""
    with _lock:
        s = _state.copy()

    overall_rem_15 = s["overall_limit_15min"] - s["overall_usage_15min"]
    overall_rem_day = s["overall_limit_daily"] - s["overall_usage_daily"]
    read_rem_15 = s["read_limit_15min"] - s["read_usage_15min"]
    read_rem_day = s["read_limit_daily"] - s["read_usage_daily"]

    return {
        "overall": {
            "limit_15min": s["overall_limit_15min"],
            "usage_15min": s["overall_usage_15min"],
            "remaining_15min": overall_rem_15,
            "pct_used_15min": round(s["overall_usage_15min"] / max(s["overall_limit_15min"], 1) * 100, 1),
            "limit_daily": s["overall_limit_daily"],
            "usage_daily": s["overall_usage_daily"],
            "remaining_daily": overall_rem_day,
            "pct_used_daily": round(s["overall_usage_daily"] / max(s["overall_limit_daily"], 1) * 100, 1),
        },
        "read": {
            "limit_15min": s["read_limit_15min"],
            "usage_15min": s["read_usage_15min"],
            "remaining_15min": read_rem_15,
            "pct_used_15min": round(s["read_usage_15min"] / max(s["read_limit_15min"], 1) * 100, 1),
            "limit_daily": s["read_limit_daily"],
            "usage_daily": s["read_usage_daily"],
            "remaining_daily": read_rem_day,
            "pct_used_daily": round(s["read_usage_daily"] / max(s["read_limit_daily"], 1) * 100, 1),
        },
        "tracking": {
            "total_requests": s["total_requests"],
            "throttled_count": s["throttled_count"],
            "error_429_count": s["error_429_count"],
            "last_updated": s["last_updated"],
            "last_request_time": s["last_request_time"],
        },
    }


class RateLimitExceeded(Exception):
    """Raised when Strava rate limit is exhausted."""
    pass
