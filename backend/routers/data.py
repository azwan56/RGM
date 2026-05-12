"""
Data router — provides read-only API endpoints that replace direct
browser-to-Firestore reads.  This allows Chinese users (behind GFW)
to load data via the Render backend instead of connecting directly
to firestore.googleapis.com (which is blocked).

Data flow: Browser → Render backend → Firestore (both outside GFW)
"""

from fastapi import APIRouter, Request
from firebase_config import db
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import time

router = APIRouter()

# Shared thread pool for parallel Firestore reads
_executor = ThreadPoolExecutor(max_workers=6)

# ── Server-side TTL Cache ─────────────────────────────────────────────────────
# Avoids repeated Firestore reads for data that changes infrequently.

class _TTLCache:
    """Simple thread-safe TTL cache for single-key values."""
    def __init__(self, ttl_seconds: int):
        self._ttl = ttl_seconds
        self._data: dict = {}
        self._ts: dict = {}

    def get(self, key: str):
        if key in self._data and (time.monotonic() - self._ts[key]) < self._ttl:
            return self._data[key]
        return None

    def set(self, key: str, value):
        self._data[key] = value
        self._ts[key] = time.monotonic()

# Leaderboard list: rarely changes, 5 min cache
_lb_cache = _TTLCache(300)
# User profiles: 2 min cache (same-session)
_profile_cache = _TTLCache(120)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _read_user_doc(uid: str):
    cached = _profile_cache.get(uid)
    if cached is not None:
        return cached
    doc = db.collection("users").document(uid).get()
    result = doc.to_dict() if doc.exists else None
    if result:
        _profile_cache.set(uid, result)
    return result

def _read_goal_doc(uid: str):
    doc = db.collection("users").document(uid).collection("goals").document("current").get()
    return doc.to_dict() if doc.exists else None

def _read_leaderboard_doc(uid: str):
    doc = db.collection("leaderboard").document(uid).get()
    return doc.to_dict() if doc.exists else None

def _read_leaderboard_list(period: str, limit_n: int = 20):
    cache_key = f"{period}_{limit_n}"
    cached = _lb_cache.get(cache_key)
    if cached is not None:
        return cached
    # Leaderboard always stores monthly data now, but legacy docs may have
    # period="weekly". For the monthly tab, fetch ALL docs sorted by distance.
    if period == "monthly":
        docs = (db.collection("leaderboard")
                  .order_by("total_distance_km", direction="DESCENDING")
                  .limit(limit_n)
                  .stream())
    else:
        docs = (db.collection("leaderboard")
                  .where("period", "==", period)
                  .order_by("total_distance_km", direction="DESCENDING")
                  .limit(limit_n)
                  .stream())
    result = [d.to_dict() for d in docs]
    _lb_cache.set(cache_key, result)
    return result

def _read_activities(uid: str, start: str, end: str):
    q = db.collection("users").document(uid).collection("activities")
    if start and end:
        q = (q.where("start_date_local", ">=", start)
              .where("start_date_local", "<", end)
              .order_by("start_date_local", direction="DESCENDING"))
    else:
        q = q.order_by("start_date_local", direction="DESCENDING").limit(50)
    return [d.to_dict() for d in q.stream()]


# ── Combined Dashboard endpoint (replaces 4 serial requests) ─────────────────

@router.get("/dashboard/{uid}")
def get_dashboard_all(uid: str, period: str = "monthly", month: int = -1):
    """
    Single-request dashboard loader — returns init, stats, leaderboard, and
    current month activities in one response. Cuts 4 serial API round-trips
    down to 1 (saving 1-3s on high-latency connections).
    """
    # Default month = current month
    if month < 0:
        month = date.today().month - 1  # 0-indexed

    # Calculate month range for activities
    year = date.today().year
    pad = lambda n: str(n).zfill(2)
    act_start = f"{year}-{pad(month + 1)}-01T00:00:00"
    next_month = month + 1
    end_year = year + 1 if next_month > 11 else year
    end_mon = 0 if next_month > 11 else next_month
    act_end = f"{end_year}-{pad(end_mon + 1)}-01T00:00:00"

    # Fire all Firestore reads in parallel
    futures = {
        _executor.submit(_read_user_doc, uid): "user",
        _executor.submit(_read_goal_doc, uid): "goal",
        _executor.submit(_read_leaderboard_doc, uid): "stats",
        _executor.submit(_read_leaderboard_list, period): "leaderboard",
        _executor.submit(_read_activities, uid, act_start, act_end): "activities",
    }

    results = {}
    for future in as_completed(futures):
        key = futures[future]
        try:
            results[key] = future.result()
        except Exception as e:
            print(f"[dashboard] {key} fetch error: {e}")
            results[key] = None

    user_data = results.get("user") or {}
    goal = results.get("goal")
    stats = results.get("stats") or {}
    leaderboard_entries = results.get("leaderboard") or []
    activities = results.get("activities") or []

    # Strip sensitive tokens from user profile
    safe_profile = {k: v for k, v in user_data.items()
                    if not k.startswith("strava_access") and not k.startswith("strava_refresh")}

    display_name = (
        user_data.get("display_name") or user_data.get("strava_name")
        or (user_data.get("email", "").split("@")[0] if user_data.get("email") else "")
    )

    strava_connected = bool(user_data.get("strava_connected"))

    # Determine period from goal
    goal_period = "monthly"
    if goal:
        p = goal.get("period")
        if p in ("weekly", "monthly"):
            goal_period = p

    return {
        "profile": safe_profile,
        "goal": goal,
        "strava_connected": strava_connected,
        "display_name": display_name,
        "goal_period": goal_period,
        "stats": stats,
        "leaderboard": {"entries": leaderboard_entries},
        "activities": {"activities": activities},
    }


# ── Dashboard init (profile + goals + strava status) ──────────────────────────

@router.get("/init/{uid}")
def get_dashboard_init(uid: str):
    """Combined endpoint for dashboard initial load — parallel Firestore reads."""
    # Parallel read: user doc + goal doc
    user_future = _executor.submit(_read_user_doc, uid)
    goal_future = _executor.submit(_read_goal_doc, uid)

    data = user_future.result()
    if not data:
        return {"profile": None, "goal": None, "strava_connected": False}

    # Strip sensitive tokens
    safe = {k: v for k, v in data.items()
            if not k.startswith("strava_access") and not k.startswith("strava_refresh")}

    goal = goal_future.result()

    return {
        "profile": safe,
        "goal": goal,
        "strava_connected": bool(data.get("strava_connected")),
        "display_name": (
            data.get("display_name") or data.get("strava_name")
            or (data.get("email", "").split("@")[0] if data.get("email") else "")
        ),
    }


# ── Leaderboard stats for a single user ───────────────────────────────────────

@router.get("/stats/{uid}")
def get_user_stats(uid: str):
    """Returns the leaderboard document for a single user (used by RunningStatsPanel)."""
    doc = db.collection("leaderboard").document(uid).get()
    if not doc.exists:
        return {}
    return doc.to_dict()


# ── Leaderboard list ──────────────────────────────────────────────────────────

@router.get("/leaderboard")
def get_leaderboard(period: str = "monthly", limit_n: int = 20):
    """Returns sorted leaderboard entries for the given period (monthly or weekly)."""
    # Monthly tab fetches all docs (leaderboard now always stores monthly data)
    if period == "monthly":
        docs = (db.collection("leaderboard")
                  .order_by("total_distance_km", direction="DESCENDING")
                  .limit(limit_n)
                  .stream())
    else:
        docs = (db.collection("leaderboard")
                  .where("period", "==", period)
                  .order_by("total_distance_km", direction="DESCENDING")
                  .limit(limit_n)
                  .stream())
    return {"entries": [d.to_dict() for d in docs]}


# ── Activities list for a month ───────────────────────────────────────────────

@router.get("/activities/{uid}")
def get_activities(uid: str, start: str = "", end: str = ""):
    """
    Returns activities for a user within a date range.
    start/end format: 'YYYY-MM-DDT00:00:00'
    """
    return {"activities": _read_activities(uid, start, end)}


# ── Single activity ───────────────────────────────────────────────────────────

@router.get("/activity/{uid}/{activity_id}")
def get_single_activity(uid: str, activity_id: str):
    """Returns a single activity document."""
    doc = db.collection("users").document(uid).collection("activities").document(activity_id).get()
    if not doc.exists:
        return {"activity": None}
    return {"activity": doc.to_dict()}

