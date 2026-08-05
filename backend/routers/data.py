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
# User profiles: 0 min cache (bypass to avoid distributed stale reads after bind/sync)
_profile_cache = _TTLCache(0)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _read_user_doc(uid: str):
    cached = _profile_cache.get(uid)
    if cached is not None:
        return cached
    try:
        doc = db.collection("users").document(uid).get(timeout=4.0)
        result = doc.to_dict() if doc.exists else None
        if result:
            _profile_cache.set(uid, result)
        return result
    except Exception as e:
        print(f"[data] Error reading user doc for {uid}: {e}")
        return None

def invalidate_profile_cache(uid: str):
    """Purges the user's cached profile so fresh auth/bind states are returned instantly."""
    _profile_cache._data.pop(uid, None)
    _profile_cache._ts.pop(uid, None)

def _read_goal_doc(uid: str):
    try:
        doc = db.collection("users").document(uid).collection("goals").document("current").get(timeout=4.0)
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        print(f"[data] Error reading goal doc for {uid}: {e}")
        return None

def _read_leaderboard_doc(uid: str, period: str = "monthly"):
    try:
        collection = "leaderboard_weekly" if period == "weekly" else "leaderboard"
        doc = db.collection(collection).document(uid).get(timeout=4.0)
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        print(f"[data] Error reading leaderboard doc for {uid}: {e}")
        return None

def _read_leaderboard_list(period: str, limit_n: int = 20):
    cache_key = f"{period}_{limit_n}"
    cached = _lb_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        if period == "monthly":
            docs = (db.collection("leaderboard")
                      .order_by("total_distance_km", direction="DESCENDING")
                      .limit(limit_n)
                      .stream(timeout=4.0))
        else:
            docs = (db.collection("leaderboard")
                      .where("period", "==", period)
                      .order_by("total_distance_km", direction="DESCENDING")
                      .limit(limit_n)
                      .stream(timeout=4.0))
        result = [d.to_dict() for d in docs]
        _lb_cache.set(cache_key, result)
        return result
    except Exception as e:
        print(f"[data] Error reading leaderboard list: {e}")
        return []

def _read_activities(uid: str, start: str, end: str):
    from utils.activity_utils import deduplicate_activities
    try:
        q = db.collection("users").document(uid).collection("activities")
        if start and end:
            q = (q.where("start_date_local", ">=", start)
                  .where("start_date_local", "<", end)
                  .order_by("start_date_local", direction="DESCENDING"))
        else:
            q = q.order_by("start_date_local", direction="DESCENDING").limit(50)
        raw = [d.to_dict() for d in q.stream(timeout=4.0)]
        return deduplicate_activities(raw)
    except Exception as e:
        print(f"[data] Error reading activities for {uid}: {e}")
        return []

def _read_latest_health(uid: str):
    try:
        docs = (
            db.collection("users").document(uid).collection("health_metrics")
              .order_by("date", direction="DESCENDING")
              .limit(10)
              .stream(timeout=4.0)
        )
        for d in docs:
            h = d.to_dict()
            if any(h.get(k) is not None for k in ["resting_heart_rate", "sleep_score", "hrv_last_night", "hrv_weekly_avg", "body_battery_max"]):
                return h
        return None
    except Exception as e:
        print(f"[data] Error reading latest health for {uid}: {e}")
        return None


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
    goal_data = _read_goal_doc(uid)
    goal_period = "monthly"
    if goal_data:
        p = goal_data.get("period")
        if p in ("weekly", "monthly"):
            goal_period = p

    futures = {
        _executor.submit(_read_user_doc, uid): "user",
        _executor.submit(_read_leaderboard_doc, uid, goal_period): "stats",
        _executor.submit(_read_leaderboard_list, period): "leaderboard",
        _executor.submit(_read_activities, uid, act_start, act_end): "activities",
        _executor.submit(_read_latest_health, uid): "health",
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
    goal = goal_data
    leaderboard_entries = results.get("leaderboard") or []
    
    # Deduplicate activities
    from utils.activity_utils import deduplicate_activities
    raw_acts = results.get("activities") or []
    activities = deduplicate_activities(raw_acts)
    activities = [a for a in activities if a.get("source") != "AppleHealth"]

    strava_connected = bool(
        user_data.get("strava_connected")
        or user_data.get("strava_access_token")
        or user_data.get("strava_refresh_token")
        or user_data.get("strava_athlete_id")
    )
    garmin_connected = bool(
        user_data.get("garmin_connected")
        or (user_data.get("garmin_email") and user_data.get("garmin_encrypted_password"))
    )

    # Strip sensitive tokens from user profile
    safe_profile = {k: v for k, v in user_data.items()
                    if not k.startswith("strava_access") and not k.startswith("strava_refresh") and k != "garmin_encrypted_password"}

    display_name = (
        user_data.get("display_name") or user_data.get("strava_name")
        or (user_data.get("email", "").split("@")[0] if user_data.get("email") else "")
    )

    # Determine period from goal
    goal_period = "monthly"
    if goal:
        p = goal.get("period")
        if p in ("weekly", "monthly"):
            goal_period = p

    # Dynamically compute deduplicated stats for the current period
    run_acts = [a for a in activities if a.get("activity_type", "run") == "run"]
    calc_dist = round(sum(float(a.get("distance_km", 0) or 0) for a in run_acts), 2)
    calc_elev = round(sum(float(a.get("total_elevation_gain", 0) or 0) for a in run_acts), 1)
    calc_time = sum(int(a.get("moving_time", 0) or 0) for a in run_acts)
    calc_hrs = [float(a.get("avg_heart_rate", 0) or 0) for a in run_acts if float(a.get("avg_heart_rate", 0) or 0) > 0]
    calc_avg_hr = round(sum(calc_hrs) / len(calc_hrs)) if calc_hrs else 0

    from routers.sync import pace_str
    calc_pace = pace_str(calc_dist * 1000, calc_time)

    target_dist = float(goal.get("target_distance") or goal.get("target_distance_km", 0) or 0.0) if goal else 0.0
    calc_goal_pct = round((calc_dist / target_dist) * 100) if target_dist > 0 else 0

    stats = {
        "uid": uid,
        "display_name": display_name,
        "total_distance_km": calc_dist,
        "total_elevation_gain": calc_elev,
        "avg_pace": calc_pace,
        "avg_heart_rate": calc_avg_hr,
        "goal_completion_percentage": min(calc_goal_pct, 100),
        "run_count": len(run_acts),
        "period": goal_period,
    }

    # Update current user's row in leaderboard_entries
    updated_leaderboard = []
    found_user = False
    for entry in leaderboard_entries:
        if entry.get("uid") == uid:
            found_user = True
            e = dict(entry)
            e["total_distance_km"] = calc_dist
            e["total_elevation_gain"] = calc_elev
            e["avg_pace"] = calc_pace
            e["avg_heart_rate"] = calc_avg_hr
            e["run_count"] = len(run_acts)
            updated_leaderboard.append(e)
        else:
            updated_leaderboard.append(entry)

    if not found_user and calc_dist > 0:
        updated_leaderboard.append(stats)

    # Re-sort leaderboard entries by distance descending
    updated_leaderboard = sorted(updated_leaderboard, key=lambda x: x.get("total_distance_km", 0), reverse=True)

    latest_health = results.get("health")

    return {
        "profile": safe_profile,
        "goal": goal,
        "strava_connected": strava_connected,
        "garmin_connected": garmin_connected,
        "apple_health_connected": False,
        "display_name": display_name,
        "goal_period": goal_period,
        "stats": stats,
        "leaderboard": {"entries": updated_leaderboard},
        "activities": {"activities": activities},
        "latest_health": latest_health,
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
        return {"profile": None, "goal": None, "strava_connected": False, "garmin_connected": False}

    # Strip sensitive tokens
    safe = {k: v for k, v in data.items()
            if not k.startswith("strava_access") and not k.startswith("strava_refresh") and k != "garmin_encrypted_password"}

    goal = goal_future.result()

    strava_connected = bool(
        data.get("strava_connected")
        or data.get("strava_access_token")
        or data.get("strava_refresh_token")
        or data.get("strava_athlete_id")
    )
    garmin_connected = bool(
        data.get("garmin_connected")
        or (data.get("garmin_email") and data.get("garmin_encrypted_password"))
    )

    return {
        "profile": safe,
        "goal": goal,
        "strava_connected": strava_connected,
        "garmin_connected": garmin_connected,
        "apple_health_connected": False,
        "display_name": (
            data.get("display_name") or data.get("strava_name")
            or (data.get("email", "").split("@")[0] if data.get("email") else "")
        ),
    }


# ── Leaderboard stats for a single user ───────────────────────────────────────

@router.get("/stats/{uid}")
def get_user_stats(uid: str):
    """Returns the leaderboard document for a single user (used by RunningStatsPanel).
    Reads from the correct collection based on the user's goal period setting.
    """
    # Check user's goal period to pick the right leaderboard collection
    goal_doc = db.collection("users").document(uid).collection("goals").document("current").get()
    period = "monthly"
    if goal_doc.exists:
        period = (goal_doc.to_dict() or {}).get("period", "monthly")

    collection = "leaderboard_weekly" if period == "weekly" else "leaderboard"
    doc = db.collection(collection).document(uid).get()
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
        docs = (db.collection("leaderboard_weekly")
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

