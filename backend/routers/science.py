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

    VDOT selection strategy (v5 — race PB priority):
    ┌─────────────────────────────────────────────────────────────────┐
    │  Priority 1: RACE PBs (gold standard for Daniels VDOT)        │
    │    Reverse-lookup VDOT from marathon/half/10K/5K PBs           │
    │    Average across available distances                           │
    │  Priority 2: BLEND (PB + training data)                        │
    │    vdot = 0.7 × pb_vdot + 0.3 × training_vdot                 │
    │  Priority 3: TRAINING ONLY (road runs, 42d decay)              │
    │    Same stream-based logic as before                            │
    └─────────────────────────────────────────────────────────────────┘
    """
    from utils.sports_science import race_time_to_vdot

    vdot = req.vdot
    vdot_source = "user_provided" if vdot else ""
    pb_detail = {}

    if vdot is None:
        from datetime import date, timedelta
        import math

        profile = _get_profile(req.uid)
        max_hr  = profile.get("max_heart_rate",    190)
        rest_hr = profile.get("resting_heart_rate", 60)

        # ── Step 1: Race PB → VDOT (highest priority) ──
        PB_FIELDS = [
            ("marathon_pb_sec", "FM"),
            ("half_pb_sec",     "HM"),
            ("ten_k_pb_sec",    "10K"),
            ("five_k_pb_sec",   "5K"),
        ]
        pb_vdots = []
        for field, dist in PB_FIELDS:
            pb_sec = profile.get(field)
            if pb_sec and int(pb_sec) > 0:
                v = race_time_to_vdot(int(pb_sec), dist)
                if v:
                    pb_vdots.append((dist, v))
                    h, r = divmod(int(pb_sec), 3600)
                    m, s = divmod(r, 60)
                    pb_detail[dist] = {
                        "time": f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}",
                        "vdot": v,
                    }

        pb_vdot = max(v for _, v in pb_vdots) if pb_vdots else None
        # Also record the average for diagnostics
        pb_vdot_avg = round(sum(v for _, v in pb_vdots) / len(pb_vdots), 1) if pb_vdots else None

        # ── Step 2: Training stream VDOT (road-only, 42d decay) ──
        today      = date.today()
        cutoff_42d = (today - timedelta(days=42)).isoformat()
        HALF_LIFE  = 14.0

        _TRAIL_KEYWORDS = {"trail", "越野", "山", "hill", "mountain", "hiking", "hike"}

        def _is_trail(act: dict) -> bool:
            if act.get("sport_type", "").lower() == "trailrun":
                return True
            name = (act.get("name", "") or "").lower()
            if any(kw in name for kw in _TRAIL_KEYWORDS):
                return True
            km   = act.get("distance_km", 0) or 0
            elev = act.get("total_elevation_gain", 0) or 0
            if km > 0 and elev > 0 and (elev / km) > 20:
                return True
            return False

        user_ref = db.collection("users").document(req.uid)
        docs = (user_ref.collection("activities")
                .order_by("start_date_local", direction="DESCENDING")
                .limit(80)
                .stream())

        candidates = []
        fallback   = None
        trail_excluded = 0

        for doc in docs:
            d   = doc.to_dict()
            v   = d.get("vdot")
            r2  = d.get("vdot_r2", 0) or 0
            dt  = d.get("start_date_local", "")[:10]
            if not v or float(v) < 20:
                continue
            if _is_trail(d):
                trail_excluded += 1
                continue
            if not fallback:
                fallback = float(v)
            if dt >= cutoff_42d:
                candidates.append((dt, float(v), float(r2)))

        training_vdot = None
        if candidates:
            weighted_sum = 0.0
            weight_total = 0.0
            for dt, v, r2 in candidates:
                days_ago = max((today - date.fromisoformat(dt)).days, 0)
                decay    = math.pow(2.0, -days_ago / HALF_LIFE)
                quality  = max(0.3, min(3.0, math.exp(r2 * 4)))
                w        = decay * quality
                weighted_sum += v * w
                weight_total += w
            training_vdot = round(weighted_sum / weight_total, 1)
        elif fallback:
            training_vdot = fallback

        # ── Step 3: Final VDOT selection ──
        if pb_vdot and training_vdot:
            # Blend: PB is gold standard (70%), training is recent form (30%)
            vdot = round(0.7 * pb_vdot + 0.3 * training_vdot, 1)
            vdot_source = (
                f"blended (pb={pb_vdot} × 0.7 + training={training_vdot} × 0.3, "
                f"pbs={list(pb_detail.keys())}, trail_excluded={trail_excluded})"
            )
        elif pb_vdot:
            vdot = pb_vdot
            vdot_source = f"race_pb (pbs={list(pb_detail.keys())})"
        elif training_vdot:
            vdot = training_vdot
            n = len(candidates)
            vdot_source = f"42d_road_only (n={n}, trail_excluded={trail_excluded})"
        else:
            vdot_source = f"none (trail_excluded={trail_excluded})"
    else:
        profile = _get_profile(req.uid)
        max_hr  = profile.get("max_heart_rate",    190)
        rest_hr = profile.get("resting_heart_rate", 60)

    if not vdot or vdot < 20:
        return {"error": "No VDOT data available. Open a run's detail page first to compute it."}

    if "profile" not in dir():
        profile = _get_profile(req.uid)
        max_hr  = profile.get("max_heart_rate",    190)
        rest_hr = profile.get("resting_heart_rate", 60)

    return {
        "race_times":  vdot_to_race_times(vdot),
        "zones":       vdot_to_zones(vdot, max_hr, rest_hr),
        "vdot_used":   vdot,
        "vdot_source": vdot_source,
        "pb_detail":   pb_detail,
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
