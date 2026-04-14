from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from firebase_config import db
from utils.sports_science import (
    compute_fitness_fatigue_timeseries,
    vdot_to_zones,
    vdot_to_race_times,
)

router = APIRouter()

# ─── Shared helper ────────────────────────────────────────────────────────────

def _get_profile(uid: str):
    doc = db.collection("users").document(uid).get()
    if doc.exists:
        return doc.to_dict()
    return {}

# ─── Fitness Trend ────────────────────────────────────────────────────────────

class FitnessTrendRequest(BaseModel):
    uid: str
    days: int = 30

@router.post("/fitness-trend")
def get_fitness_trend(req: FitnessTrendRequest):
    """Returns daily CTL, ATL, and TSB values (90-activity cap for speed)."""
    user_ref = db.collection("users").document(req.uid)
    profile = _get_profile(req.uid)
    max_hr  = profile.get("max_heart_rate",    190)
    rest_hr = profile.get("resting_heart_rate", 60)

    docs = (
        user_ref.collection("activities")
        .order_by("start_date_local", direction="DESCENDING")
        .limit(90)
        .stream()
    )
    activities = [d.to_dict() for d in docs]
    activities.reverse()

    return {"data": compute_fitness_fatigue_timeseries(activities, max_hr, rest_hr, req.days) or []}


# ─── Race Predictor ───────────────────────────────────────────────────────────

class VdotRequest(BaseModel):
    uid: str
    vdot: Optional[float] = None  # If not passed, tries to find latest from Firestore

@router.post("/race-predictor")
def get_race_predictor(req: VdotRequest):
    """
    Returns predicted race finish times for 5K, 10K, HM, FM based on VDOT.
    Also returns personalized training zones.

    VDOT selection strategy (v3):
    ┌─────────────────────────────────────────────────────────────────┐
    │  Window : 42 days  (activities with cached vdot field)         │
    │  Decay  : exponential, half-life = 14 days                     │
    │           w = 2^(-days_ago / 14)                               │
    │           yesterday  → 0.95   │  7d ago  → 0.71               │
    │           14d ago    → 0.50   │  28d ago → 0.25               │
    │           42d ago    → 0.125  (lower cutoff, included)         │
    │  Quality: R² bonus  quality = clamp(R²×5 + 0.5, 0.5, 1.0)     │
    │  Final w = exponential_decay × quality                         │
    └─────────────────────────────────────────────────────────────────┘
    If no 42-day data exists, falls back to oldest available VDOT.
    """
    vdot = req.vdot

    if vdot is None:
        from datetime import date, timedelta
        import math

        today      = date.today()
        cutoff_42d = (today - timedelta(days=42)).isoformat()
        HALF_LIFE  = 14.0   # days — weight halves every 14 days

        user_ref = db.collection("users").document(req.uid)
        # Order descending so we hit recent activities first; fetch 80 to cover sparse data
        docs = (user_ref.collection("activities")
                .order_by("start_date_local", direction="DESCENDING")
                .limit(80)
                .stream())

        candidates = []   # (date_str, vdot_val, r2)
        fallback   = None

        for doc in docs:
            d   = doc.to_dict()
            v   = d.get("vdot")
            r2  = d.get("vdot_r2", 0) or 0
            dt  = d.get("start_date_local", "")[:10]
            if not v or float(v) < 20:
                continue
            if not fallback:
                fallback = float(v)     # most recent valid VDOT regardless of window
            if dt >= cutoff_42d:
                candidates.append((dt, float(v), float(r2)))

        if candidates:
            weighted_sum = 0.0
            weight_total = 0.0
            for dt, v, r2 in candidates:
                days_ago    = max((today - date.fromisoformat(dt)).days, 0)
                decay       = math.pow(2.0, -days_ago / HALF_LIFE)   # exponential recency
                quality     = math.exp(r2 * 4)                        # exp R² boost: 0→1.0, 0.1→1.49, 0.25→2.72
                quality     = max(0.3, min(3.0, quality))             # clamp [0.3, 3.0]
                w           = decay * quality
                weighted_sum += v * w
                weight_total += w

            vdot        = round(weighted_sum / weight_total, 1)
            vdot_source = f"42d_exp_decay (n={len(candidates)})"
        elif fallback:
            vdot        = fallback
            vdot_source = "fallback_latest"
        else:
            vdot_source = "none"

    else:
        vdot_source = "user_provided"

    if not vdot or vdot < 20:
        return {"error": "No VDOT data available. Open a run's detail page first to compute it."}

    profile = _get_profile(req.uid)
    max_hr  = profile.get("max_heart_rate",    190)
    rest_hr = profile.get("resting_heart_rate", 60)

    return {
        "race_times":  vdot_to_race_times(vdot),
        "zones":       vdot_to_zones(vdot, max_hr, rest_hr),
        "vdot_used":   vdot,
        "vdot_source": vdot_source,
    }


# ─── Monthly Trend ────────────────────────────────────────────────────────────

class MonthlyTrendRequest(BaseModel):
    uid: str
    months: int = 6

@router.post("/monthly-trend")
def get_monthly_trend(req: MonthlyTrendRequest):
    """
    Returns per-month totals: distance, run count, avg pace.
    """
    from collections import defaultdict
    from datetime import date, datetime

    user_ref = db.collection("users").document(req.uid)
    # Fetch last N months of activities (cap 365)
    docs = (user_ref.collection("activities")
            .order_by("start_date_local", direction="DESCENDING")
            .limit(365)
            .stream())

    monthly: dict = defaultdict(lambda: {"distance_km": 0.0, "count": 0, "total_time": 0})

    for doc in docs:
        act = doc.to_dict()
        date_str = act.get("start_date_local", "")[:7]  # "YYYY-MM"
        if not date_str:
            continue
        monthly[date_str]["distance_km"] += act.get("distance_km", 0)
        monthly[date_str]["count"]        += 1
        monthly[date_str]["total_time"]   += act.get("moving_time", 0)

    # Build sorted output for the last req.months months (correct calendar arithmetic)
    from datetime import date
    today = date.today()

    # Compute the start month by going back (months-1) months from current month
    start_year  = today.year
    start_month = today.month - (req.months - 1)
    while start_month <= 0:
        start_month += 12
        start_year  -= 1

    result = []
    y, m = start_year, start_month
    for _ in range(req.months):
        key  = f"{y}-{m:02d}"
        data = monthly.get(key, {"distance_km": 0.0, "count": 0, "total_time": 0})

        dist = data["distance_km"]
        t    = data["total_time"]
        if dist > 0 and t > 0:
            secs     = (t / dist)
            avg_pace = f"{int(secs)//60}:{int(secs)%60:02d}"
        else:
            avg_pace = "—"

        result.append({
            "month":       key,
            "label":       f"{y}/{m}月",
            "distance_km": round(dist, 1),
            "run_count":   data["count"],
            "avg_pace":    avg_pace,
        })

        # Advance to next month
        m += 1
        if m > 12:
            m  = 1
            y += 1

    return {"data": result}
