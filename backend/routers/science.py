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

    VDOT selection strategy (v6 — road-only training data):
    ┌─────────────────────────────────────────────────────────────────┐
    │  Source: recent training stream VDOT (road runs only)          │
    │  Window: 42 days, exponential decay (half-life 14 days)        │
    │  Filter: excludes trail runs (sport_type / name / elevation)   │
    │  Quality: R² weighted (exp boost, clamped [0.3, 3.0])          │
    │  PBs NOT used — they may be stale and not reflect current form │
    └─────────────────────────────────────────────────────────────────┘
    """
    vdot = req.vdot

    if vdot is None:
        from datetime import date, timedelta
        import math

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
            vdot        = round(weighted_sum / weight_total, 1)
            vdot_source = f"42d_road_only (n={len(candidates)}, trail_excluded={trail_excluded})"
        elif fallback:
            vdot        = fallback
            vdot_source = f"fallback_road (trail_excluded={trail_excluded})"
        else:
            vdot_source = f"none (trail_excluded={trail_excluded})"
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


# ─── Analysis Bundle (single-fetch optimization) ─────────────────────────────

class AnalysisBundleRequest(BaseModel):
    uid: str
    days: int = 30
    months: int = 6

@router.post("/analysis-bundle")
def get_analysis_bundle(req: AnalysisBundleRequest):
    """
    Combined endpoint for the Analysis page — reads activities ONCE from Firestore
    and computes all 4 analyses server-side:
      1. Fitness Trend (CTL/ATL/TSB) — from latest 90 activities
      2. Race Predictor (VDOT + zones + race times) — from latest 80 activities
      3. Monthly Trend — from all activities (up to 365)
      4. Stats Summary — from YTD activities

    Performance: 4 × Firestore reads → 1 read + 1 profile read (parallel).
    Saves ~1-1.5 seconds per page load.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from collections import defaultdict
    from datetime import date, timedelta
    import math

    today = date.today()
    year = today.year
    year_start = f"{year}-01-01"
    user_ref = db.collection("users").document(req.uid)

    # ── 2 parallel Firestore reads: activities (365) + profile ──
    with ThreadPoolExecutor(max_workers=3) as ex:
        act_future = ex.submit(
            lambda: [d.to_dict() for d in
                     user_ref.collection("activities")
                     .order_by("start_date_local", direction="DESCENDING")
                     .limit(365)
                     .stream()]
        )
        prof_future = ex.submit(lambda: _get_profile(req.uid))
        goal_future = ex.submit(
            lambda: (user_ref.collection("goals").document("current").get().to_dict() or {})
        )
        activities = act_future.result()
        profile = prof_future.result()
        goal = goal_future.result()

    max_hr = profile.get("max_heart_rate", 190)
    rest_hr = profile.get("resting_heart_rate", 60)

    # ── 1. Fitness Trend (latest 90 activities, chronological order) ──
    fitness_acts = list(reversed(activities[:90]))
    fitness_data = compute_fitness_fatigue_timeseries(fitness_acts, max_hr, rest_hr, req.days) or []

    # ── 2. Race Predictor (VDOT from latest 80 road activities) ──
    _TRAIL_KEYWORDS = {"trail", "越野", "山", "hill", "mountain", "hiking", "hike"}
    cutoff_42d = (today - timedelta(days=42)).isoformat()
    HALF_LIFE = 14.0

    def _is_trail(act):
        if act.get("sport_type", "").lower() == "trailrun":
            return True
        name = (act.get("name", "") or "").lower()
        if any(kw in name for kw in _TRAIL_KEYWORDS):
            return True
        km = act.get("distance_km", 0) or 0
        elev = act.get("total_elevation_gain", 0) or 0
        if km > 0 and elev > 0 and (elev / km) > 20:
            return True
        return False

    candidates = []
    fallback = None
    trail_excluded = 0
    vdot = None
    vdot_source = "none"

    for d in activities[:80]:
        v = d.get("vdot")
        r2 = d.get("vdot_r2", 0) or 0
        dt = d.get("start_date_local", "")[:10]
        if not v or float(v) < 20:
            continue
        if _is_trail(d):
            trail_excluded += 1
            continue
        if not fallback:
            fallback = float(v)
        if dt >= cutoff_42d:
            candidates.append((dt, float(v), float(r2)))

    if candidates:
        weighted_sum = 0.0
        weight_total = 0.0
        for dt, v, r2 in candidates:
            days_ago = max((today - date.fromisoformat(dt)).days, 0)
            decay = math.pow(2.0, -days_ago / HALF_LIFE)
            quality = max(0.3, min(3.0, math.exp(r2 * 4)))
            w = decay * quality
            weighted_sum += v * w
            weight_total += w
        vdot = round(weighted_sum / weight_total, 1)
        vdot_source = f"42d_road_only (n={len(candidates)}, trail_excluded={trail_excluded})"
    elif fallback:
        vdot = fallback
        vdot_source = f"fallback_road (trail_excluded={trail_excluded})"

    race_data = None
    if vdot and vdot >= 20:
        race_data = {
            "race_times": vdot_to_race_times(vdot),
            "zones": vdot_to_zones(vdot, max_hr, rest_hr),
            "vdot_used": vdot,
            "vdot_source": vdot_source,
        }

    # ── 3. Monthly Trend ──
    monthly_agg = defaultdict(lambda: {"distance_km": 0.0, "count": 0, "total_time": 0})
    for act in activities:
        date_str = act.get("start_date_local", "")[:7]
        if not date_str:
            continue
        monthly_agg[date_str]["distance_km"] += act.get("distance_km", 0)
        monthly_agg[date_str]["count"] += 1
        monthly_agg[date_str]["total_time"] += act.get("moving_time", 0)

    start_year = today.year
    start_month = today.month - (req.months - 1)
    while start_month <= 0:
        start_month += 12
        start_year -= 1

    trend_result = []
    y, m = start_year, start_month
    for _ in range(req.months):
        key = f"{y}-{m:02d}"
        data = monthly_agg.get(key, {"distance_km": 0.0, "count": 0, "total_time": 0})
        dist = data["distance_km"]
        t = data["total_time"]
        if dist > 0 and t > 0:
            secs = t / dist
            avg_pace = f"{int(secs) // 60}:{int(secs) % 60:02d}"
        else:
            avg_pace = "—"
        trend_result.append({
            "month": key, "label": f"{y}/{m}月",
            "distance_km": round(dist, 1), "run_count": data["count"], "avg_pace": avg_pace,
        })
        m += 1
        if m > 12:
            m = 1
            y += 1

    # ── 4. Stats Summary (YTD) ──
    MONTHS_CN = ["一月", "二月", "三月", "四月", "五月", "六月",
                 "七月", "八月", "九月", "十月", "十一月", "十二月"]
    overall_target = float(goal.get("target_distance", goal.get("target_distance_km", 100)) or 100)
    raw_mt = goal.get("monthly_targets") or []
    monthly_targets_arr = [float(v or overall_target) for v in raw_mt] if isinstance(raw_mt, list) and len(raw_mt) == 12 else [overall_target] * 12

    def month_target(m_idx):
        t = monthly_targets_arr[m_idx - 1] if monthly_targets_arr else overall_target
        return t if t > 0 else overall_target

    ytd_monthly = defaultdict(lambda: {"km": 0.0, "runs": 0, "moving_time": 0})
    total_km = total_runs = total_time = hr_sum = hr_cnt = 0
    for act in activities:
        ds = act.get("start_date_local", "")
        if ds[:4] != str(year):
            continue
        mk = ds[:7]
        km = act.get("distance_km", 0)
        t = act.get("moving_time", 0)
        ytd_monthly[mk]["km"] += km
        ytd_monthly[mk]["runs"] += 1
        ytd_monthly[mk]["moving_time"] += t
        total_km += km
        total_runs += 1
        total_time += t
        hr = act.get("avg_heart_rate", 0) or 0
        if hr:
            hr_sum += hr
            hr_cnt += 1

    this_month = today.strftime("%Y-%m")
    months_results = []
    for m_idx in range(1, today.month + 1):
        mk = f"{year}-{m_idx:02d}"
        data = ytd_monthly.get(mk, {"km": 0.0, "runs": 0, "moving_time": 0})
        actual = round(data["km"], 1)
        target = round(month_target(m_idx), 1)
        pct = round((actual / target) * 100) if target > 0 else 0
        months_results.append({
            "month": mk, "month_name": MONTHS_CN[m_idx - 1],
            "target_km": target, "actual_km": actual,
            "run_count": data["runs"], "completion_pct": pct,
            "is_current": mk == this_month, "achieved": actual >= target,
        })

    ytd_km = sum(r["actual_km"] for r in months_results)
    ytd_runs = sum(r["run_count"] for r in months_results)
    annual_tgt = sum(month_target(m) for m in range(1, 13))
    months_elapsed = today.month
    projected_km = round((total_km / months_elapsed) * 12, 1) if months_elapsed else 0

    monthly_km_map = {mk: d["km"] for mk, d in ytd_monthly.items()}
    best_month = max(monthly_km_map, key=monthly_km_map.get) if monthly_km_map else None
    best_month_km = round(monthly_km_map[best_month], 1) if best_month else 0

    def _pace_str(dist_m, time_s):
        if not dist_m or not time_s:
            return "—"
        secs_per_km = time_s / (dist_m / 1000) if dist_m > 0 else 0
        return f"{int(secs_per_km) // 60}:{int(secs_per_km) % 60:02d}"

    stats_summary = {
        "history": {
            "year": year, "monthly_target": round(overall_target, 1),
            "annual_target": round(annual_tgt, 1), "months": months_results,
            "ytd_km": round(ytd_km, 1), "ytd_runs": ytd_runs,
        },
        "annual": {
            "year": year, "annual_target_km": round(annual_tgt, 1),
            "total_km": round(total_km, 1), "total_runs": total_runs,
            "completion_pct": round((total_km / annual_tgt) * 100, 1) if annual_tgt else 0,
            "avg_monthly_km": round(total_km / months_elapsed, 1) if months_elapsed else 0,
            "projected_km": projected_km,
            "best_month": best_month, "best_month_km": best_month_km,
            "avg_pace": _pace_str(total_km * 1000, total_time),
            "avg_heart_rate": round(hr_sum / hr_cnt) if hr_cnt else 0,
        },
    }

    return {
        "fitness_trend": {"data": fitness_data},
        "race_predictor": race_data,
        "monthly_trend": {"data": trend_result},
        "stats_summary": stats_summary,
    }
