from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from firebase_config import db
from datetime import datetime, date, timedelta
import calendar
from zoneinfo import ZoneInfo

_DEFAULT_TZ = "Asia/Singapore"

router = APIRouter()

class AppleHealthWorkout(BaseModel):
    uuid: str
    name: str
    start_date_local: str  # YYYY-MM-DDTHH:MM:SS
    distance_km: float
    moving_time: int       # seconds
    avg_heart_rate: int
    total_elevation_gain: float = 0.0

class AppleHealthSyncRequest(BaseModel):
    uid: str
    workouts: list[AppleHealthWorkout]


def get_period_start(period: str, tz_name: str = _DEFAULT_TZ) -> datetime:
    tz = ZoneInfo(tz_name)
    today = datetime.now(tz).date()
    if period == "weekly":
        monday = today - timedelta(days=today.weekday())
        return datetime(monday.year, monday.month, monday.day, 0, 0, 0)
    else:
        return datetime(today.year, today.month, 1, 0, 0, 0)


def pace_str(distance_m: float, moving_time_s: int) -> str:
    km = distance_m / 1000
    if km <= 0 or moving_time_s <= 0:
        return "—"
    sec_per_km = moving_time_s / km
    mins = int(sec_per_km // 60)
    secs = int(sec_per_km % 60)
    return f"{mins}:{secs:02d}"


def format_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


@router.post("/sync")
def sync_apple_health_workouts(req: AppleHealthSyncRequest):
    """
    Receives workout records from the iOS client (via HealthKit), saves them to
    Firestore, and updates the user's weekly and monthly leaderboards.
    """
    user_ref = db.collection("users").document(req.uid)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    user_data = user_doc.to_dict()
    display_name = (
        user_data.get("display_name") or user_data.get("strava_name")
        or (user_data.get("email", "").split("@")[0] if user_data.get("email") else "跑者")
    )

    # 1. Update connection status
    user_ref.update({
        "apple_health_connected": True
    })

    # 2. Save workouts to activities sub-collection
    for w in req.workouts:
        act_ref = user_ref.collection("activities").document(w.uuid)
        
        # Check if activity already exists. If it does, we don't overwrite custom changes (like names).
        existing = act_ref.get()
        if existing.exists:
            # Only merge new metrics just in case
            act_ref.update({
                "distance_km": round(w.distance_km, 2),
                "moving_time": w.moving_time,
                "elapsed_time": w.moving_time,
                "duration_str": format_duration(w.moving_time),
                "avg_pace": pace_str(w.distance_km * 1000, w.moving_time),
                "avg_heart_rate": w.avg_heart_rate,
                "total_elevation_gain": round(w.total_elevation_gain, 1),
            })
        else:
            doc = {
                "activity_id":          w.uuid,
                "name":                 w.name or "Apple Health 跑步",
                "start_date_local":     w.start_date_local,
                "distance_km":          round(w.distance_km, 2),
                "moving_time":          w.moving_time,
                "elapsed_time":         w.moving_time,
                "duration_str":         format_duration(w.moving_time),
                "avg_pace":             pace_str(w.distance_km * 1000, w.moving_time),
                "avg_heart_rate":       w.avg_heart_rate,
                "total_elevation_gain": round(w.total_elevation_gain, 1),
                "activity_type":        "run",
                "sport_type":           "Run",
                "source":               "AppleHealth",
            }
            act_ref.set(doc)

    # 3. Retrieve user goal details
    goal_snap = user_ref.collection("goals").document("current").get()
    period = "monthly"
    target_dist = 0
    if goal_snap.exists:
        goal_data = goal_snap.to_dict()
        period = goal_data.get("period", "monthly")
        target_dist = goal_data.get("target_distance", 0)

    # 4. Recalculate Monthly Leaderboard Entry
    month_start_str = get_period_start("monthly").strftime("%Y-%m-%dT%H:%M:%S")
    month_acts = (
        user_ref.collection("activities")
        .where("start_date_local", ">=", month_start_str)
        .stream()
    )
    
    lb_dist = 0.0
    lb_time = 0
    lb_hr_sum = 0.0
    lb_hr_count = 0
    lb_runs = 0
    lb_elev = 0.0
    
    for a in month_acts:
        d = a.to_dict()
        if d.get("activity_type", "run") != "run":
            continue
        # Shield non-Apple Health data if Apple Health is connected
        if d.get("source") != "AppleHealth":
            continue
        lb_runs += 1
        lb_dist += d.get("distance_km", 0) or 0
        lb_time += d.get("moving_time", 0) or 0
        lb_elev += d.get("total_elevation_gain", 0) or 0
        hr = d.get("avg_heart_rate", 0) or 0
        if hr > 0:
            lb_hr_sum += hr
            lb_hr_count += 1

    lb_pace = pace_str(lb_dist * 1000, lb_time)
    lb_avg_hr = round(lb_hr_sum / lb_hr_count) if lb_hr_count > 0 else 0

    now = datetime.now(ZoneInfo(_DEFAULT_TZ))
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    monthly_target_dist = target_dist
    if period == "weekly" and target_dist > 0:
        monthly_target_dist = target_dist * (days_in_month / 7.0)

    lb_goal_percentage = round((lb_dist / monthly_target_dist) * 100) if monthly_target_dist > 0 else 0

    db.collection("leaderboard").document(req.uid).set({
        "uid":                       req.uid,
        "display_name":              display_name,
        "email":                     user_data.get("email", ""),
        "total_distance_km":         round(lb_dist, 2),
        "total_elevation_gain":      round(lb_elev, 1),
        "avg_pace":                  lb_pace,
        "avg_heart_rate":            lb_avg_hr,
        "goal_completion_percentage": min(lb_goal_percentage, 100),
        "run_count":                 lb_runs,
        "period":                    "monthly",
        "period_start":              get_period_start("monthly").isoformat(),
        "last_sync":                 datetime.now().isoformat(),
    })

    # 5. Recalculate Weekly Leaderboard Entry
    week_start_str = get_period_start("weekly").strftime("%Y-%m-%dT%H:%M:%S")
    week_acts = (
        user_ref.collection("activities")
        .where("start_date_local", ">=", week_start_str)
        .stream()
    )
    
    wk_dist = 0.0
    wk_time = 0
    wk_hr_sum = 0.0
    wk_hr_count = 0
    wk_runs = 0
    wk_elev = 0.0
    
    for a in week_acts:
        d = a.to_dict()
        if d.get("activity_type", "run") != "run":
            continue
        # Shield non-Apple Health data if Apple Health is connected
        if d.get("source") != "AppleHealth":
            continue
        wk_runs += 1
        wk_dist += d.get("distance_km", 0) or 0
        wk_time += d.get("moving_time", 0) or 0
        wk_elev += d.get("total_elevation_gain", 0) or 0
        hr = d.get("avg_heart_rate", 0) or 0
        if hr > 0:
            wk_hr_sum += hr
            wk_hr_count += 1
            
    wk_pace = pace_str(wk_dist * 1000, wk_time)
    wk_avg_hr = round(wk_hr_sum / wk_hr_count) if wk_hr_count > 0 else 0
    wk_goal_pct = round((wk_dist / target_dist) * 100) if period == "weekly" and target_dist > 0 else 0
    
    db.collection("leaderboard_weekly").document(req.uid).set({
        "uid":                       req.uid,
        "display_name":              display_name,
        "email":                     user_data.get("email", ""),
        "total_distance_km":         round(wk_dist, 2),
        "total_elevation_gain":      round(wk_elev, 1),
        "avg_pace":                  wk_pace,
        "avg_heart_rate":            wk_avg_hr,
        "goal_completion_percentage": min(wk_goal_pct, 100),
        "run_count":                 wk_runs,
        "period":                    "weekly",
        "period_start":              get_period_start("weekly").isoformat(),
        "last_sync":                 datetime.now().isoformat(),
    })

    return {"success": True, "synced_count": len(req.workouts)}
