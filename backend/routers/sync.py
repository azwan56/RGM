from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from firebase_config import db
import requests
import os
from datetime import datetime, date, timedelta

router = APIRouter()


class SyncRequest(BaseModel):
    uid: str


def get_period_start(period: str) -> datetime:
    """Natural week (Monday 00:00) or natural month (1st 00:00)."""
    today = date.today()
    if period == "weekly":
        monday = today - timedelta(days=today.weekday())
        return datetime(monday.year, monday.month, monday.day, 0, 0, 0)
    else:
        return datetime(today.year, today.month, 1, 0, 0, 0)


def pace_str(distance_m: float, moving_time_s: int) -> str:
    """Returns avg pace as 'M:SS /km' or '—' if no distance."""
    km = distance_m / 1000
    if km <= 0 or moving_time_s <= 0:
        return "—"
    sec_per_km = moving_time_s / km
    mins = int(sec_per_km // 60)
    secs = int(sec_per_km % 60)
    return f"{mins}:{secs:02d}"


def format_duration(seconds: int) -> str:
    """Returns duration as H:MM:SS or M:SS."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _build_act_doc(act: dict, period: str, period_start) -> dict:
    """Convert a raw Strava activity dict to a Firestore document dict."""
    dist = act.get("distance", 0)
    t    = act.get("moving_time", 0)
    avg_hr = act.get("average_heartrate") or 0
    return {
        "activity_id":          act["id"],
        "name":                 act.get("name", "Run"),
        "start_date_local":     act.get("start_date_local", ""),
        "distance_km":          round(dist / 1000, 2),
        "moving_time":          t,
        "elapsed_time":         act.get("elapsed_time", t),
        "duration_str":         format_duration(t),
        "avg_pace":             pace_str(dist, t),
        "avg_speed_kmh":        round(act.get("average_speed", 0) * 3.6, 1),
        "max_speed_kmh":        round(act.get("max_speed", 0) * 3.6, 1),
        "avg_heart_rate":       round(avg_hr) if avg_hr else 0,
        "max_heart_rate":       act.get("max_heartrate") or 0,
        "has_heartrate":        act.get("has_heartrate", False),
        "total_elevation_gain": act.get("total_elevation_gain", 0),
        "avg_cadence":          round(act.get("average_cadence", 0) * 2) if act.get("average_cadence") else 0,
        "achievement_count":    act.get("achievement_count", 0),
        "kudos_count":          act.get("kudos_count", 0),
        "summary_polyline":     act.get("map", {}).get("summary_polyline", ""),
        "period":               period,
        "period_start":         period_start.isoformat(),
    }


# ── Trigger sync (current period) ────────────────────────────────────────────
@router.post("/trigger")
def sync_user_data(req: SyncRequest):
    """
    Syncs running data from Strava for the current natural week or month,
    depending on the user's goal period setting.
    """
    user_ref  = db.collection("users").document(req.uid)
    user_doc  = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    user_data     = user_doc.to_dict()
    refresh_token = user_data.get("strava_refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Strava not connected")

    # 1. Refresh token
    client_id     = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Strava credentials missing.")

    token_resp = requests.post("https://www.strava.com/oauth/token", data={
        "client_id":     client_id,
        "client_secret": client_secret,
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
    })
    if not token_resp.ok:
        raise HTTPException(status_code=400, detail=f"Failed to refresh token: {token_resp.text}")

    new_token_data = token_resp.json()
    access_token   = new_token_data["access_token"]
    user_ref.update({
        "strava_access_token":  access_token,
        "strava_refresh_token": new_token_data["refresh_token"],
        "strava_expires_at":    new_token_data["expires_at"],
    })

    # 2. Goal period
    goal_snap  = user_ref.collection("goals").document("current").get()
    period     = "monthly"
    target_dist = 0
    if goal_snap.exists:
        goal_data   = goal_snap.to_dict()
        period      = goal_data.get("period", "monthly")
        target_dist = goal_data.get("target_distance", 0)

    period_start = get_period_start(period)
    epoch_start  = int(period_start.timestamp())

    # 3. Fetch Strava activities from period start (single page, max 200)
    headers = {"Authorization": f"Bearer {access_token}"}
    activities_resp = requests.get(
        f"https://www.strava.com/api/v3/athlete/activities",
        params={"after": epoch_start, "per_page": 200},
        headers=headers,
        timeout=20,
    )
    if not activities_resp.ok:
        raise HTTPException(status_code=400, detail="Failed to fetch Strava activities")

    activities = activities_resp.json()

    # 4. Process & batch write
    total_distance = 0.0
    total_time     = 0
    heart_rate_sum = 0
    hr_count       = 0
    run_count      = 0
    batch          = db.batch()

    for act in activities:
        if act.get("type") != "Run":
            continue
        run_count += 1
        dist   = act.get("distance", 0)
        t      = act.get("moving_time", 0)
        avg_hr = act.get("average_heartrate") or 0
        total_distance += dist
        total_time     += t
        if act.get("has_heartrate") and avg_hr:
            heart_rate_sum += avg_hr
            hr_count       += 1
        act_ref = user_ref.collection("activities").document(str(act["id"]))
        batch.set(act_ref, _build_act_doc(act, period, period_start), merge=True)

    batch.commit()

    # 5. Aggregate + leaderboard
    km_distance      = total_distance / 1000
    avg_pace         = pace_str(total_distance, total_time)
    avg_heart_rate   = round(heart_rate_sum / hr_count) if hr_count > 0 else 0
    goal_percentage  = round((km_distance / target_dist) * 100) if target_dist > 0 else 0

    # Determine best display name (priority: profile name > strava > email prefix > uid)
    display_name = (
        user_data.get("display_name")
        or user_data.get("strava_name")
        or (user_data.get("email", "").split("@")[0] if user_data.get("email") else None)
        or f"Runner #{req.uid[:6]}"
    )

    db.collection("leaderboard").document(req.uid).set({
        "uid":                       req.uid,
        "display_name":              display_name,
        "email":                     user_data.get("email", ""),
        "total_distance_km":         round(km_distance, 2),
        "avg_pace":                  avg_pace,
        "avg_heart_rate":            avg_heart_rate,
        "goal_completion_percentage": min(goal_percentage, 100),
        "run_count":                 run_count,
        "period":                    period,
        "period_start":              period_start.isoformat(),
        "last_sync":                 datetime.now().isoformat(),
    }, merge=True)

    # ── Also update yearly leaderboard aggregate ───────────────────────────────
    _update_yearly_leaderboard(req.uid, user_data, display_name)

    return {
        "message": "Sync successful",
        "stats": {
            "km":        round(km_distance, 2),
            "pace":      avg_pace,
            "pct":       goal_percentage,
            "run_count": run_count,
            "period":    period,
        }
    }


# ── Full historical sync (background task) ───────────────────────────────────
class FullSyncRequest(SyncRequest):
    since_date: str = "2025-01-01"

def _run_full_sync_bg(uid: str, since_date: str, access_token: str, period: str, period_start):
    """
    Background task: paginate Strava history and write to Firestore.
    Writes progress to users/{uid}/meta/full_sync_status so the client can poll.
    """
    user_ref   = db.collection("users").document(uid)
    status_ref = user_ref.collection("meta").document("full_sync_status")

    status_ref.set({"state": "running", "saved": 0, "pages": 0, "since_date": since_date,
                    "started_at": datetime.now().isoformat()})

    try:
        since_dt    = datetime.strptime(since_date, "%Y-%m-%d")
        epoch_start = int(since_dt.timestamp())
        headers     = {"Authorization": f"Bearer {access_token}"}
        PER_PAGE    = 200
        page        = 1
        total_saved = 0

        while True:
            resp = requests.get(
                "https://www.strava.com/api/v3/athlete/activities",
                params={"after": epoch_start, "per_page": PER_PAGE, "page": page},
                headers=headers,
                timeout=30,
            )
            if not resp.ok:
                status_ref.set({"state": "error", "error": f"Strava error on page {page}: {resp.status_code}",
                                "saved": total_saved}, merge=True)
                return

            page_acts = resp.json()
            if not page_acts:
                break

            batch       = db.batch()
            batch_count = 0

            for act in page_acts:
                if act.get("type") != "Run":
                    continue
                act_ref = user_ref.collection("activities").document(str(act["id"]))
                batch.set(act_ref, _build_act_doc(act, period, period_start), merge=True)
                batch_count += 1
                total_saved += 1
                if batch_count >= 400:
                    batch.commit()
                    batch       = db.batch()
                    batch_count = 0

            batch.commit()

            # Update live progress
            status_ref.set({"state": "running", "saved": total_saved, "pages": page}, merge=True)

            if len(page_acts) < PER_PAGE:
                break
            page += 1

        status_ref.set({
            "state":      "done",
            "saved":      total_saved,
            "pages":      page,
            "since_date": since_date,
            "finished_at": datetime.now().isoformat(),
        }, merge=True)

    except Exception as e:
        status_ref.set({"state": "error", "error": str(e)}, merge=True)


@router.post("/full")
def sync_full_history(req: FullSyncRequest, background_tasks: BackgroundTasks):
    """
    Kicks off a full historical sync in the background.
    Returns immediately — poll GET /api/sync/full-status?uid=... to check progress.
    """
    user_ref  = db.collection("users").document(req.uid)
    user_doc  = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    user_data     = user_doc.to_dict()
    refresh_token = user_data.get("strava_refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Strava not connected")

    client_id     = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Strava credentials missing.")

    token_resp = requests.post("https://www.strava.com/oauth/token", data={
        "client_id":     client_id,
        "client_secret": client_secret,
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
    })
    if not token_resp.ok:
        raise HTTPException(status_code=400, detail=f"Token refresh failed: {token_resp.text}")

    new_token_data = token_resp.json()
    access_token   = new_token_data["access_token"]
    user_ref.update({
        "strava_access_token":  access_token,
        "strava_refresh_token": new_token_data["refresh_token"],
        "strava_expires_at":    new_token_data["expires_at"],
    })

    goal_snap    = user_ref.collection("goals").document("current").get()
    period       = "monthly"
    if goal_snap.exists:
        period   = goal_snap.to_dict().get("period", "monthly")
    period_start = get_period_start(period)

    # Fire and forget
    background_tasks.add_task(
        _run_full_sync_bg, req.uid, req.since_date, access_token, period, period_start
    )

    return {"message": "Full sync started in background", "since_date": req.since_date}


@router.get("/full-status")
def get_full_sync_status(uid: str):
    """Polls the background full-sync progress stored in Firestore."""
    status_ref = db.collection("users").document(uid).collection("meta").document("full_sync_status")
    doc = status_ref.get()
    if not doc.exists:
        return {"state": "idle", "saved": 0}
    return doc.to_dict()


@router.get("/activity/{activity_id}/detail")
def get_activity_detail(activity_id: int, uid: str):
    """
    Returns full activity detail including full-resolution polyline from Strava.
    """
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    access_token = user_doc.to_dict().get("strava_access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Strava not connected")

    resp = requests.get(
        f"https://www.strava.com/api/v3/activities/{activity_id}",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    if not resp.ok:
        raise HTTPException(status_code=400, detail=f"Failed to fetch activity: {resp.text}")

    data = resp.json()
    return {
        "polyline": data.get("map", {}).get("polyline", ""),
        "summary_polyline": data.get("map", {}).get("summary_polyline", ""),
    }


@router.get("/activity/{activity_id}/streams")
def get_activity_streams(activity_id: int, uid: str):
    """
    Fetches Strava stream data for chart rendering ONLY.
    Fast path — no VDOT computation here.
    """
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    access_token = user_doc.to_dict().get("strava_access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Strava not connected")

    resp = requests.get(
        "https://www.strava.com/api/v3/activities/{}/streams".format(activity_id),
        params={
            "keys": "time,distance,velocity_smooth,heartrate,cadence,altitude",
            "key_by_type": "true"
        },
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15  # Strava can be slow — set explicit timeout
    )
    if not resp.ok:
        raise HTTPException(status_code=400, detail=f"Failed to fetch streams: {resp.text}")

    raw = resp.json()
    distances  = raw.get("distance",        {}).get("data", [])
    velocities = raw.get("velocity_smooth", {}).get("data", [])
    heartrates = raw.get("heartrate",       {}).get("data", [])
    cadences   = raw.get("cadence",         {}).get("data", [])
    altitudes  = raw.get("altitude",        {}).get("data", [])

    if not distances:
        return {"points": []}

    # Sample to ~500 points max for chart rendering
    total = len(distances)
    step  = max(1, total // 500)

    points = []
    for i in range(0, total, step):
        vel = velocities[i] if i < len(velocities) else 0
        pace = round((1000 / vel) / 60, 3) if vel and vel > 0.5 else None
        cad  = int(cadences[i] * 2) if i < len(cadences) and cadences[i] else None
        hr   = int(heartrates[i]) if i < len(heartrates) and heartrates[i] else None
        alt  = round(altitudes[i], 1) if i < len(altitudes) and altitudes[i] is not None else None
        points.append({"distance": round(distances[i] / 1000, 3), "pace": pace, "heartRate": hr, "cadence": cad, "elevation": alt})

    return {"points": points}


@router.get("/activity/{activity_id}/vdot")
def get_activity_vdot(activity_id: int, uid: str):
    """
    Separate, explicitly lazy-loaded VDOT analysis endpoint.
    Called only after the activity chart has already rendered.
    """
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    if not user_doc.exists:
        return {"vdot_analysis": None, "error": "User not found"}

    profile = user_doc.to_dict()
    access_token = profile.get("strava_access_token")
    if not access_token:
        return {"vdot_analysis": None, "error": "Strava not connected"}

    # Fetch streams needed for VDOT (no cadence needed — saves bandwidth)
    resp = requests.get(
        "https://www.strava.com/api/v3/activities/{}/streams".format(activity_id),
        params={"keys": "time,distance,velocity_smooth,heartrate,altitude", "key_by_type": "true"},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=20
    )
    if not resp.ok:
        return {"vdot_analysis": None, "error": f"Strava API error: {resp.status_code}"}

    raw = resp.json()
    streams = {
        "time":             raw.get("time",             {}).get("data", []),
        "distance":         raw.get("distance",         {}).get("data", []),
        "velocity_smooth":  raw.get("velocity_smooth",  {}).get("data", []),
        "heartrate":        raw.get("heartrate",        {}).get("data", []),
        "altitude":         raw.get("altitude",         {}).get("data", []),
    }

    if not streams["velocity_smooth"] or not streams["heartrate"]:
        return {"vdot_analysis": None, "error": "Missing velocity or heartrate stream"}

    from utils.sports_science import compute_vdot_from_streams
    max_hr  = profile.get("max_heart_rate",    190)
    rest_hr = profile.get("resting_heart_rate", 60)
    result  = compute_vdot_from_streams(streams, max_hr=max_hr, rest_hr=rest_hr)

    # Cache VDOT to Firestore so race-predictor can read without re-computation
    if result and result.get("vdot") and not result.get("error"):
        try:
            act_ref = (db.collection("users").document(uid)
                         .collection("activities").document(str(activity_id)))
            act_ref.set({"vdot": result["vdot"], "vdot_r2": result.get("r_squared", 0)}, merge=True)
        except Exception as e:
            print(f"[VDOT cache] Failed to write: {e}")

    return {"vdot_analysis": result}


# ── Yearly leaderboard helper ──────────────────────────────────────────────────

def _update_yearly_leaderboard(uid: str, user_data: dict, display_name: str):
    """
    Aggregates all activities from Jan 1 of the current year and writes one
    document to the `leaderboard_yearly` collection.
    Called automatically after every regular sync.
    """
    try:
        year       = date.today().year
        year_start = f"{year}-01-01"

        acts = (db.collection("users").document(uid)
                  .collection("activities")
                  .where("start_date_local", ">=", year_start)
                  .stream())

        total_dist  = 0.0
        total_time  = 0
        hr_sum      = 0
        hr_count    = 0
        run_count   = 0

        for doc in acts:
            a = doc.to_dict()
            d = a.get("distance_km", 0) * 1000   # back to metres
            t = a.get("moving_time", 0)
            total_dist  += d
            total_time  += t
            run_count   += 1
            hr = a.get("avg_heart_rate", 0) or 0
            if hr:
                hr_sum   += hr
                hr_count += 1

        db.collection("leaderboard_yearly").document(f"{year}_{uid}").set({
            "uid":               uid,
            "year":              year,
            "display_name":      display_name,
            "email":             user_data.get("email", ""),
            "total_distance_km": round(total_dist / 1000, 2),
            "run_count":         run_count,
            "avg_pace":          pace_str(total_dist, total_time),
            "avg_heart_rate":    round(hr_sum / hr_count) if hr_count else 0,
            "last_sync":         datetime.now().isoformat(),
        }, merge=True)
    except Exception as e:
        print(f"[yearly leaderboard] update failed: {e}")


# ── GET /history/{uid} ─────────────────────────────────────────────────────────

@router.get("/history/{uid}")
def get_goal_history(uid: str):
    """
    Returns month-by-month goal achievement from Jan 1 of the current year to today.
    Each entry contains: month, target_km, actual_km, run_count, completion_pct.
    goal target = user's current monthly target_distance setting.
    """
    year        = date.today().year
    year_start  = f"{year}-01-01"
    this_month  = date.today().strftime("%Y-%m")
    MONTHS_CN   = ["一月","二月","三月","四月","五月","六月",
                   "七月","八月","九月","十月","十一月","十二月"]

    # Goal target — per-month targets take precedence over single overall target
    goal_doc = (db.collection("users").document(uid)
                  .collection("goals").document("current").get())
    overall_target  = 100.0
    monthly_targets_arr: list = []          # 12-element list, index = month-1
    if goal_doc.exists:
        gd = goal_doc.to_dict() or {}
        overall_target = float(gd.get("target_distance", gd.get("target_distance_km", 100)) or 100)
        raw = gd.get("monthly_targets") or []
        if isinstance(raw, list) and len(raw) == 12:
            monthly_targets_arr = [float(v or overall_target) for v in raw]
        else:
            monthly_targets_arr = [overall_target] * 12

    def month_target(m_idx: int) -> float:  # m_idx = 1-based month number
        """Return the target for a given month, using per-month if set."""
        t = monthly_targets_arr[m_idx - 1] if monthly_targets_arr else overall_target
        return t if t > 0 else overall_target

    # Scan activities
    acts = (db.collection("users").document(uid)
              .collection("activities")
              .where("start_date_local", ">=", year_start)
              .stream())

    # Group by YYYY-MM
    from collections import defaultdict
    monthly: dict = defaultdict(lambda: {"km": 0.0, "runs": 0, "moving_time": 0})
    for doc in acts:
        a  = doc.to_dict()
        mk = a.get("start_date_local", "")[:7]
        monthly[mk]["km"]          += a.get("distance_km", 0)
        monthly[mk]["runs"]        += 1
        monthly[mk]["moving_time"] += a.get("moving_time", 0)

    # Build Jan → current month
    results = []
    for m_idx in range(1, date.today().month + 1):
        mk       = f"{year}-{m_idx:02d}"
        data     = monthly.get(mk, {"km": 0.0, "runs": 0, "moving_time": 0})
        actual   = round(data["km"], 1)
        target   = round(month_target(m_idx), 1)
        pct      = round((actual / target) * 100) if target > 0 else 0
        results.append({
            "month":          mk,
            "month_name":     MONTHS_CN[m_idx - 1],
            "target_km":      target,
            "actual_km":      actual,
            "run_count":      data["runs"],
            "completion_pct": pct,
            "is_current":     mk == this_month,
            "achieved":       actual >= target,
        })

    # Year-to-date totals
    ytd_km      = sum(r["actual_km"]  for r in results)
    ytd_runs    = sum(r["run_count"]  for r in results)
    annual_tgt  = sum(month_target(m) for m in range(1, 13))

    return {
        "year":           year,
        "monthly_target": round(overall_target, 1),
        "annual_target":  round(annual_tgt, 1),
        "months":         results,
        "ytd_km":         round(ytd_km, 1),
        "ytd_runs":       ytd_runs,
    }


# ── GET /annual/{uid} ─────────────────────────────────────────────────────────

@router.get("/annual/{uid}")
def get_annual_summary(uid: str):
    """
    Returns annual running summary for the current year, plus comparison
    with monthly leaderboard data for context.
    """
    year       = date.today().year
    year_start = f"{year}-01-01"

    # Goal
    goal_doc = (db.collection("users").document(uid)
                  .collection("goals").document("current").get())
    overall_target = 100.0
    monthly_targets_arr: list = []
    if goal_doc.exists:
        gd = goal_doc.to_dict() or {}
        overall_target = float(gd.get("target_distance", gd.get("target_distance_km", 100)) or 100)
        raw = gd.get("monthly_targets") or []
        if isinstance(raw, list) and len(raw) == 12:
            monthly_targets_arr = [float(v or overall_target) for v in raw]
    annual_target = (
        sum(monthly_targets_arr) if len(monthly_targets_arr) == 12
        else overall_target * 12
    )

    # Activities
    acts_stream = (db.collection("users").document(uid)
                     .collection("activities")
                     .where("start_date_local", ">=", year_start)
                     .stream())

    from collections import defaultdict
    monthly: dict = defaultdict(float)
    total_km   = 0.0
    total_runs = 0
    total_time = 0
    hr_sum     = 0
    hr_cnt     = 0

    for doc in acts_stream:
        a = doc.to_dict()
        km = a.get("distance_km", 0)
        t  = a.get("moving_time", 0)
        monthly[a.get("start_date_local", "")[:7]] += km
        total_km   += km
        total_runs += 1
        total_time += t
        hr = a.get("avg_heart_rate", 0) or 0
        if hr:
            hr_sum += hr
            hr_cnt += 1

    best_month     = max(monthly, key=monthly.get) if monthly else None
    best_month_km  = round(monthly[best_month], 1) if best_month else 0
    months_elapsed = date.today().month
    projected_km   = round((total_km / months_elapsed) * 12, 1) if months_elapsed else 0

    return {
        "year":             year,
        "annual_target_km": round(annual_target, 1),
        "total_km":         round(total_km, 1),
        "total_runs":       total_runs,
        "completion_pct":   round((total_km / annual_target) * 100, 1) if annual_target else 0,
        "avg_monthly_km":   round(total_km / months_elapsed, 1) if months_elapsed else 0,
        "projected_km":     projected_km,
        "best_month":       best_month,
        "best_month_km":    best_month_km,
        "avg_pace":         pace_str(total_km * 1000, total_time),
        "avg_heart_rate":   round(hr_sum / hr_cnt) if hr_cnt else 0,
    }


# ── GET /yearly-leaderboard ───────────────────────────────────────────────────

@router.get("/yearly-leaderboard")
def get_yearly_leaderboard(year: int = 0, limit_n: int = 20):
    """Returns the top-N runners by total km for a given year (default: current year).
    Sorts in Python to avoid requiring a Firestore composite index on leaderboard_yearly.
    """
    if not year:
        year = date.today().year

    # Fetch all docs for the year (no orderBy → no composite index needed)
    docs = (db.collection("leaderboard_yearly")
              .where("year", "==", year)
              .stream())

    entries = [d.to_dict() for d in docs]
    entries.sort(key=lambda e: e.get("total_distance_km", 0), reverse=True)
    return {"year": year, "entries": entries[:limit_n]}


# ── GET /vdot-trend/{uid} ─────────────────────────────────────────────────────

@router.get("/vdot-trend/{uid}")
def get_vdot_trend(uid: str, limit: int = 10):
    """
    Returns the most recent activities that have a valid VDOT score,
    sorted by date descending. Used for VDOT trend chart.
    """
    acts = (db.collection("users").document(uid)
              .collection("activities")
              .order_by("start_date_local", direction="DESCENDING")
              .limit(200)
              .stream())

    results = []
    for doc in acts:
        a = doc.to_dict()
        v = a.get("vdot")
        if not v or float(v) < 20:
            continue
        results.append({
            "activity_id": a.get("activity_id"),
            "name": a.get("name", "Run"),
            "date": a.get("start_date_local", "")[:10],
            "distance_km": round(a.get("distance_km", 0), 2),
            "avg_pace": a.get("avg_pace", "—"),
            "avg_heart_rate": a.get("avg_heart_rate", 0),
            "vdot": round(float(v), 1),
            "vdot_r2": round(float(a.get("vdot_r2", 0) or 0), 2),
        })
        if len(results) >= limit:
            break

    return {"entries": results}

