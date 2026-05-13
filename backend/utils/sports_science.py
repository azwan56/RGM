import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz

# ─── Jack Daniels VDOT Lookup Tables ──────────────────────────────────────────
# Source: Daniels' Running Formula (3rd/4th Ed.) — official published pace tables.
# Keys: VDOT values (30-85). Values: pace in seconds/km for each zone.
# Zone paces: [E_min, E_max, M, T, I, R] — all in sec/km
#
# ⚠️ These are the OFFICIAL Daniels training paces, NOT derived from race times.
#   Training paces and race paces are separate tables in the Daniels system.
#   Previous version incorrectly computed paces from _RACE_TABLE, causing:
#     - M/T paces that were too fast (derived from exact race pace / distance)
#     - I/R paces that were too slow (5K race pace ≠ Interval training pace)
#     - Compressed zone gaps that didn't match the published training tables
_VDOT_TABLE = {
    30: {"E": (380, 410), "M": 358, "T": 335, "I": 294, "R": 266},
    32: {"E": (368, 398), "M": 348, "T": 325, "I": 285, "R": 258},
    34: {"E": (357, 387), "M": 339, "T": 316, "I": 277, "R": 251},
    36: {"E": (347, 377), "M": 330, "T": 307, "I": 270, "R": 244},
    38: {"E": (338, 368), "M": 322, "T": 299, "I": 263, "R": 238},
    40: {"E": (308, 344), "M": 289, "T": 265, "I": 244, "R": 225},
    42: {"E": (298, 335), "M": 279, "T": 257, "I": 236, "R": 218},
    44: {"E": (290, 326), "M": 271, "T": 249, "I": 229, "R": 212},
    46: {"E": (282, 317), "M": 263, "T": 242, "I": 222, "R": 206},
    48: {"E": (275, 309), "M": 256, "T": 235, "I": 215, "R": 200},
    50: {"E": (268, 302), "M": 249, "T": 229, "I": 210, "R": 195},
    52: {"E": (263, 296), "M": 244, "T": 224, "I": 205, "R": 190},
    54: {"E": (258, 290), "M": 239, "T": 219, "I": 201, "R": 186},
    56: {"E": (253, 285), "M": 234, "T": 215, "I": 197, "R": 182},
    58: {"E": (248, 279), "M": 229, "T": 210, "I": 193, "R": 178},
    60: {"E": (243, 274), "M": 224, "T": 206, "I": 189, "R": 174},
    62: {"E": (238, 269), "M": 219, "T": 201, "I": 185, "R": 170},
    64: {"E": (234, 264), "M": 215, "T": 197, "I": 181, "R": 167},
    66: {"E": (230, 260), "M": 211, "T": 194, "I": 178, "R": 164},
    68: {"E": (226, 255), "M": 207, "T": 190, "I": 174, "R": 160},
    70: {"E": (222, 251), "M": 203, "T": 187, "I": 171, "R": 157},
    72: {"E": (218, 247), "M": 199, "T": 183, "I": 168, "R": 154},
    74: {"E": (214, 243), "M": 195, "T": 180, "I": 165, "R": 151},
    76: {"E": (211, 239), "M": 192, "T": 177, "I": 162, "R": 148},
    78: {"E": (207, 236), "M": 188, "T": 173, "I": 159, "R": 145},
    80: {"E": (204, 232), "M": 185, "T": 170, "I": 156, "R": 143},
    82: {"E": (200, 229), "M": 181, "T": 167, "I": 153, "R": 140},
    85: {"E": (195, 223), "M": 176, "T": 162, "I": 148, "R": 136},
}

# Race time predictions (seconds) per VDOT — Daniels formula
# Distances: 5K, 10K, HM (21.0975km), FM (42.195km)
_RACE_TABLE = {
    30: {"5K": 1530, "10K": 3162, "HM": 6960, "FM": 14700},
    32: {"5K": 1470, "10K": 3042, "HM": 6690, "FM": 14160},
    34: {"5K": 1414, "10K": 2928, "HM": 6432, "FM": 13620},
    36: {"5K": 1362, "10K": 2820, "HM": 6186, "FM": 13110},
    38: {"5K": 1314, "10K": 2718, "HM": 5952, "FM": 12630},
    40: {"5K": 1269, "10K": 2622, "HM": 5730, "FM": 12174},
    42: {"5K": 1227, "10K": 2532, "HM": 5520, "FM": 11718},
    44: {"5K": 1188, "10K": 2448, "HM": 5328, "FM": 11316},
    46: {"5K": 1152, "10K": 2370, "HM": 5148, "FM": 10914},
    48: {"5K": 1118, "10K": 2298, "HM": 4980, "FM": 10560},
    50: {"5K": 1086, "10K": 2232, "HM": 4824, "FM": 10230},
    52: {"5K": 1056, "10K": 2172, "HM": 4680, "FM": 9918},
    54: {"5K": 1028, "10K": 2112, "HM": 4548, "FM": 9630},
    56: {"5K": 1002, "10K": 2058, "HM": 4422, "FM": 9360},
    58: {"5K": 978,  "10K": 2004, "HM": 4302, "FM": 9102},
    60: {"5K": 955,  "10K": 1956, "HM": 4194, "FM": 8862},
    62: {"5K": 934,  "10K": 1908, "HM": 4086, "FM": 8640},
    64: {"5K": 914,  "10K": 1866, "HM": 3990, "FM": 8424},
    66: {"5K": 895,  "10K": 1824, "HM": 3894, "FM": 8220},
    68: {"5K": 877,  "10K": 1788, "HM": 3804, "FM": 8034},
    70: {"5K": 861,  "10K": 1752, "HM": 3720, "FM": 7848},
    72: {"5K": 846,  "10K": 1716, "HM": 3636, "FM": 7680},
    74: {"5K": 831,  "10K": 1686, "HM": 3564, "FM": 7524},
    76: {"5K": 817,  "10K": 1656, "HM": 3492, "FM": 7374},
    78: {"5K": 804,  "10K": 1626, "HM": 3426, "FM": 7236},
    80: {"5K": 792,  "10K": 1602, "HM": 3366, "FM": 7104},
    82: {"5K": 780,  "10K": 1578, "HM": 3306, "FM": 6972},
    85: {"5K": 762,  "10K": 1542, "HM": 3222, "FM": 6804},
}

def _find_nearest_vdot(vdot: float) -> int:
    """Find the closest VDOT key in the lookup table."""
    keys = sorted(_VDOT_TABLE.keys())
    return min(keys, key=lambda k: abs(k - vdot))


def race_time_to_vdot(seconds: int, distance: str):
    """
    Reverse-lookup VDOT from a race finish time.
    Uses linear interpolation between table entries for precision.

    Args:
        seconds: race finish time in seconds
        distance: one of "5K", "10K", "HM", "FM"

    Returns:
        VDOT value (float), or None if out of table range.
    """
    if not seconds or seconds <= 0 or distance not in ("5K", "10K", "HM", "FM"):
        return None

    keys = sorted(_RACE_TABLE.keys())  # [30, 32, 34, ..., 85]

    # Race table: higher VDOT → faster (fewer seconds)
    # Find the two VDOT keys that bracket the given time
    for i in range(len(keys) - 1):
        v_low  = keys[i]      # lower VDOT  (slower)
        v_high = keys[i + 1]  # higher VDOT (faster)
        t_low  = _RACE_TABLE[v_low][distance]   # slower time
        t_high = _RACE_TABLE[v_high][distance]   # faster time

        if t_high <= seconds <= t_low:
            # Linear interpolation
            frac = (t_low - seconds) / (t_low - t_high) if t_low != t_high else 0
            return round(v_low + frac * (v_high - v_low), 1)

    # Check boundaries
    if seconds >= _RACE_TABLE[keys[0]][distance]:
        return float(keys[0])   # slower than VDOT 30
    if seconds <= _RACE_TABLE[keys[-1]][distance]:
        return float(keys[-1])  # faster than VDOT 85

    return None

def _fmt_pace(sec_per_km: float) -> str:
    """Convert seconds/km to 'M:SS' string."""
    m = int(sec_per_km) // 60
    s = int(sec_per_km) % 60
    return f"{m}:{s:02d}"

def _fmt_time(seconds: int) -> str:
    """Convert total seconds to 'H:MM:SS'."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}:{m:02d}:{s:02d}"

def vdot_to_zones(vdot: float, max_hr: float = 190, rest_hr: float = 60) -> list:
    """
    Given a VDOT value, return 5 training zones with pace ranges and HR ranges.
    Based on Jack Daniels' Running Formula zone system.
    """
    nearest = _find_nearest_vdot(vdot)
    row = _VDOT_TABLE[nearest]

    # HR zone approximations (% of HRR)
    hr_zones = [
        (0.59, 0.74),  # E
        (0.74, 0.84),  # M
        (0.84, 0.88),  # T
        (0.88, 0.95),  # I
        (0.95, 1.00),  # R
    ]

    def hrr(pct):
        return round(rest_hr + (max_hr - rest_hr) * pct)

    zones = [
        {
            "zone": 1,
            "name": "轻松跑 (Easy)",
            "color": "#3b82f6",
            "pace_min": _fmt_pace(row["E"][1]),
            "pace_max": _fmt_pace(row["E"][0]),
            "hr_min": hrr(hr_zones[0][0]),
            "hr_max": hrr(hr_zones[0][1]),
            "description": "有氧基础，占训练量 70-80%",
        },
        {
            "zone": 2,
            "name": "马拉松配速 (Marathon)",
            "color": "#22c55e",
            "pace_min": _fmt_pace(row["M"] + 5),
            "pace_max": _fmt_pace(row["M"] - 5),
            "hr_min": hrr(hr_zones[1][0]),
            "hr_max": hrr(hr_zones[1][1]),
            "description": "目标马拉松节奏，稳定可持续",
        },
        {
            "zone": 3,
            "name": "乳酸阈值跑 (Threshold)",
            "color": "#f59e0b",
            "pace_min": _fmt_pace(row["T"] + 5),
            "pace_max": _fmt_pace(row["T"] - 5),
            "hr_min": hrr(hr_zones[2][0]),
            "hr_max": hrr(hr_zones[2][1]),
            "description": "提升乳酸清除能力，每次10-20分钟",
        },
        {
            "zone": 4,
            "name": "间歇跑 (Interval)",
            "color": "#f97316",
            "pace_min": _fmt_pace(row["I"] + 5),
            "pace_max": _fmt_pace(row["I"] - 5),
            "hr_min": hrr(hr_zones[3][0]),
            "hr_max": hrr(hr_zones[3][1]),
            "description": "提升最大摄氧量，400-1600m重复",
        },
        {
            "zone": 5,
            "name": "重复跑 (Repetition)",
            "color": "#ef4444",
            "pace_min": _fmt_pace(row["R"] + 5),
            "pace_max": _fmt_pace(row["R"] - 5),
            "hr_min": hrr(hr_zones[4][0]),
            "hr_max": hrr(hr_zones[4][1]),
            "description": "速度和跑步经济性，100-400m冲刺",
        },
    ]
    return zones


def vdot_to_race_times(vdot: float) -> dict:
    """
    Given a VDOT value, return predicted race finish times for standard distances.
    """
    nearest = _find_nearest_vdot(vdot)
    row = _RACE_TABLE[nearest]
    return {
        "vdot": round(vdot, 1),
        "5K":   {"seconds": row["5K"],  "formatted": _fmt_time(row["5K"]),  "pace": _fmt_pace(row["5K"] / 5)},
        "10K":  {"seconds": row["10K"], "formatted": _fmt_time(row["10K"]), "pace": _fmt_pace(row["10K"] / 10)},
        "HM":   {"seconds": row["HM"],  "formatted": _fmt_time(row["HM"]),  "pace": _fmt_pace(row["HM"] / 21.0975)},
        "FM":   {"seconds": row["FM"],  "formatted": _fmt_time(row["FM"]),  "pace": _fmt_pace(row["FM"] / 42.195)},
    }

def calculate_trimp(duration_min: float, avg_hr: float, max_hr: float = 190, rest_hr: float = 60) -> float:
    """
    Approximates TRIMP (Training Impulse) using the classic Heart Rate Reserve (HRR) formula.
    TRIMP = duration_in_minutes * HRreserve_ratio * 0.64 * e^(1.92 * HRreserve_ratio)
    """
    if duration_min <= 0 or avg_hr <= rest_hr:
        return 0.0
        
    avg_hr = min(avg_hr, max_hr)
    hrr_ratio = (avg_hr - rest_hr) / (max_hr - rest_hr)
    
    # Using generic male coefficient to approximate physiological stress
    trimp = duration_min * hrr_ratio * 0.64 * np.exp(1.92 * hrr_ratio)
    return round(float(trimp), 2)

def compute_fitness_fatigue_timeseries(activities: list, max_hr: float = 190, rest_hr: float = 60, days: int = 45):
    """
    Given an unordered list of activities, computes CTL, ATL, and TSB sequences.
    `activities`: List of dictionaries with 'start_date_local' (ISO), 'moving_time' (seconds), 'avg_heart_rate'
    `days`: Number of past days to generate the sequence for.
    """
    if not activities:
        return []

    # 1. Prepare base DataFrame
    # Note: activities might span years, so we create a time index from the oldest activity up to today
    df = pd.DataFrame(activities)
    
    if df.empty or 'start_date_local' not in df.columns:
         return []

    # Parse dates and handle missing HR gracefully (fallback to default TRIMP if heart rate is absent? 
    # For now, if no HR, we assign 0 TRIMP, or we could estimate based on pace. Let's strictly use HR if available)
    df['date'] = pd.to_datetime(df['start_date_local']).dt.floor('D').dt.tz_localize(None)
    
    # Ensure moving_time and avg_heart_rate are numeric
    df['moving_time'] = pd.to_numeric(df.get('moving_time', 0), errors='coerce').fillna(0)
    df['avg_heart_rate'] = pd.to_numeric(df.get('avg_heart_rate', 0), errors='coerce').fillna(0)
    
    # Add a fallback for missing HR: if HR=0 but moving_time > 0, estimate rough TRIMP using zone 2 (e.g. 135 bpm)
    # This prevents the CTL dropping suddenly just because someone ran without a watch.
    df.loc[(df['avg_heart_rate'] == 0) & (df['moving_time'] > 0), 'avg_heart_rate'] = rest_hr + (max_hr - rest_hr) * 0.5 

    # Calculate TRIMP per activity
    df['trimp'] = df.apply(lambda row: calculate_trimp(
        duration_min=row['moving_time'] / 60.0,
        avg_hr=row['avg_heart_rate'],
        max_hr=max_hr,
        rest_hr=rest_hr
    ), axis=1)

    # 2. Group by Day sum (if user runs twice a day, sum their TRIMP)
    daily_trimp = df.groupby('date')['trimp'].sum().reset_index()

    # 3. Create continuous daily date range from (oldest_activity - 42 days) to Today
    # We need padding to allow EWMA to build up properly (burn-in period)
    today = pd.to_datetime(datetime.now().date())
    oldest_date = daily_trimp['date'].min()
    
    # If the user's oldest run is very recent, EWMA will start building from that point.
    # To reduce EWMA initialization bias, we ideally want to start 42 days before the oldest date or 0.
    start_date = min(oldest_date, today - timedelta(days=days))
    
    date_range = pd.date_range(start=start_date, end=today, freq='D')
    ts_df = pd.DataFrame({'date': date_range})
    
    # Merge and fill missing days with 0 TRIMP
    ts_df = pd.merge(ts_df, daily_trimp, on='date', how='left').fillna(0)
    
    # 4. Compute EWMA (CTL and ATL)
    # CTL: 42-day time constant => com = 42
    # ATL: 7-day time constant => com = 7
    # Note: `span=X` roughly equals `com=(X-1)/2`. 
    # The traditional TRIMP CTL formula uses EWMA with an alpha = 1/42. 
    # In Pandas, alpha = 1 / (1 + com). So setting com = 41 gives alpha = 1/42.
    # Actually `com = 42` means alpha = 1/43 which is standard in some implementations. Let's stick to com=42.
    
    ts_df['CTL'] = ts_df['trimp'].ewm(com=42, adjust=False).mean()
    ts_df['ATL'] = ts_df['trimp'].ewm(com=7, adjust=False).mean()
    
    # 5. Compute TSB
    # Form/TSB for *today* is calculated based on yesterday's CTL and ATL!
    # TSB = CTL(t-1) - ATL(t-1)
    # This reflects the state of the body *before* today's workout.
    ts_df['CTL_yest'] = ts_df['CTL'].shift(1).fillna(0)
    ts_df['ATL_yest'] = ts_df['ATL'].shift(1).fillna(0)
    ts_df['TSB'] = ts_df['CTL_yest'] - ts_df['ATL_yest']

    # 6. Extract only the recent window requested by the user
    output_df = ts_df[ts_df['date'] >= (today - timedelta(days=days))].copy()
    
    # Output format
    output_df['date_str'] = output_df['date'].dt.strftime('%Y-%m-%d')
    output = []
    
    for _, row in output_df.iterrows():
        output.append({
            "date": row['date_str'],
            "trimp_today": round(row['trimp'], 1),
            "ctl": round(row['CTL'], 1),    # Fitness
            "atl": round(row['ATL'], 1),    # Fatigue
            "tsb": round(row['TSB'], 1)     # Form (Readiness)
        })
        
    return output

from sklearn.linear_model import LinearRegression

def compute_vdot_from_streams(streams: dict, max_hr: float = 190, rest_hr: float = 60) -> dict:
    """
    Computes a VDOT approximation from Strava activity streams.

    Algorithm (v2 — anchored threshold method):
    ─────────────────────────────────────────────
    Problem with naïve extrapolation to 100% HRR:
      Linear regression on trail/ultra data has low R² (HR stays stable but pace
      varies due to terrain). Extrapolating to 100% HRR amplifies the slope error
      catastrophically, producing wildly optimistic VDOT values.

    Solution — two anchored estimates, weighted by confidence:
    ① Direct VO₂ estimate: use the observed mean GAP and mean %HRR in the
       STEADY-STATE window (exclude warm-up and fatigue). Map (%HRR → %VO₂max)
       using Swain 1994 formula, then back-calculate vVO₂max.
    ② Threshold pace estimate: find pace at 85% HRR (aerobic threshold zone).
       Threshold pace ≈ 0.88× vVO₂max (Jack Daniels / Lucía et al.).
       Only used when R² > 0.10 (regression has some validity).

    Final VDOT = weighted average of ① and ②, with ① dominating when R² is low.
    """
    if 'velocity_smooth' not in streams or 'heartrate' not in streams or 'time' not in streams:
        return {"error": "Missing required streams (velocity, heartrate, time)"}

    vel  = np.array(streams['velocity_smooth'], dtype=float)
    hr   = np.array(streams['heartrate'],       dtype=float)
    t    = np.array(streams['time'],            dtype=float)

    # ── Grade Adjusted Pace (GAP) ──────────────────────────────────────────────
    gap_vel = vel.copy()
    if 'altitude' in streams and 'distance' in streams:
        alt  = np.array(streams['altitude'],  dtype=float)
        dist = np.array(streams['distance'],  dtype=float)
        win  = 10
        if len(dist) > win:
            delta_dist = dist[win:] - dist[:-win]
            delta_alt  = alt[win:]  - alt[:-win]
            grad_pct   = np.zeros_like(delta_dist)
            ok         = delta_dist > 0
            grad_pct[ok] = delta_alt[ok] / delta_dist[ok]
            grad         = np.zeros_like(alt)
            grad[win:]   = grad_pct
            # Strava / Minetti GAP factor (uphill costs 3.3×, downhill saves 1.2×)
            gap_factor              = np.ones_like(grad)
            gap_factor[grad > 0]   = 1 + 3.3  * grad[grad > 0]
            gap_factor[grad < 0]   = np.maximum(0.5, 1 - 1.2 * np.abs(grad[grad < 0]))
            gap_vel = np.clip(gap_vel * gap_factor, 0, 10)  # cap at 36 km/h

    # ── Exclude warm-up (first 10 min) and fatigue (last 10 min) ───────────────
    # This removes HR lag at start and glycogen-depletion effects at end.
    if t[-1] - t[0] > 2400:  # only trim if run > 40 min
        t_start = t[0]  + 600
        t_end   = t[-1] - 600
        steady_mask = (t >= t_start) & (t <= t_end)
    else:
        steady_mask = np.ones(len(t), dtype=bool)

    vel_s = gap_vel[steady_mask]
    hr_s  = hr[steady_mask]

    # Basic quality filter
    run_mask = (vel_s > 1.0) & (hr_s > 55) & (hr_s <= max_hr + 5)
    vel_s    = vel_s[run_mask]
    hr_s     = hr_s[run_mask]

    if len(vel_s) < 60:
        return {"error": "Not enough steady running data (need >10 min of valid HR + pace)."}

    # ── 60-pt rolling average (smooth GPS jitter + HR lag) ─────────────────────
    window = min(60, len(vel_s) // 4)
    if window > 1:
        k        = np.ones(window) / window
        v_smooth = np.convolve(vel_s, k, mode="valid")
        h_smooth = np.convolve(hr_s,  k, mode="valid")
    else:
        v_smooth = vel_s
        h_smooth = hr_s

    # %HRR
    hr_floor  = max(rest_hr, 40)
    hr_range  = max(max_hr - hr_floor, 1)
    hrr_pct   = np.clip((h_smooth - hr_floor) / hr_range, 0.0, 1.0)

    # ── Estimate ① — Aerobic Efficiency (Swain 1994) ──────────────────────────
    # %VO₂max ≈ 1.5472 × %HRR + 0.1728 × %HRR² (Swain et al. 1994 quadratic)
    # Works well when HR is in the 50-85% HRR range (aerobic zone).
    mean_hrr  = float(np.percentile(hrr_pct, 50))  # median %HRR
    mean_v    = float(np.median(v_smooth))           # median GAP velocity

    pct_vo2   = 1.5472 * mean_hrr - 0.1728 * (mean_hrr ** 2)
    pct_vo2   = np.clip(pct_vo2, 0.3, 1.0)
    vvo2max_1 = mean_v / pct_vo2  # vVO₂max in m/s

    # ── Linear Regression for estimate ② ─────────────────────────────────────
    X = hrr_pct.reshape(-1, 1)
    y = v_smooth
    from sklearn.linear_model import LinearRegression as LR
    model     = LR()
    model.fit(X, y)
    r_squared = float(model.score(X, y))

    # ── Estimate ② — Threshold-anchored (only if R² ≥ 0.10) ──────────────────
    # Predict pace at 85% HRR (aerobic threshold zone).
    # Physiological anchor: threshold pace ≈ 88% of vVO₂max (Daniels / Lucía 2000).
    if r_squared >= 0.10:
        v_at_threshold = float(model.predict([[0.85]])[0])
        v_at_threshold = np.clip(v_at_threshold, 1.5, 8.0)
        vvo2max_2      = v_at_threshold / 0.88
        # Weight ②: proportional to R² (max 60% weight, so ① always has ≥40%)
        w2 = min(r_squared * 3, 0.60)
        w1 = 1.0 - w2
    else:
        vvo2max_2 = vvo2max_1  # fall back to estimate ①
        w1, w2    = 1.0, 0.0

    vvo2max = w1 * vvo2max_1 + w2 * vvo2max_2
    vvo2max = np.clip(vvo2max, 2.0, 7.5)  # physiologically sane range

    # ── VDOT (Jack Daniels simplified) ────────────────────────────────────────
    # VO₂max (mL/kg/min) ≈ 0.182258 × vVO₂max(m/min) + 3.5  (running economy formula)
    vvo2max_m_min = vvo2max * 60
    vdot_approx   = 0.182258 * vvo2max_m_min + 3.5
    vdot_approx   = round(float(np.clip(vdot_approx, 20, 85)), 1)

    # ── Scatter & regression line for chart ───────────────────────────────────
    idx          = np.linspace(0, len(hrr_pct) - 1, min(120, len(hrr_pct)), dtype=int)
    scatter_data = [{"hrr": round(float(hrr_pct[i] * 100), 1),
                     "gap": round(float(v_smooth[i]), 2)} for i in idx]

    # Line: predict across observed HRR range (no extrapolation beyond data)
    hrr_min = max(float(hrr_pct.min()), 0.40)
    hrr_max = min(float(hrr_pct.max()), 0.92)
    line_x  = [round(hrr_min * 100, 1), round(hrr_max * 100, 1)]
    line_y  = [float(model.predict([[hrr_min]])[0]),
               float(model.predict([[hrr_max]])[0])]

    low_confidence = r_squared < 0.15

    return {
        "vdot":                 vdot_approx,
        "r_squared":            round(r_squared, 2),
        "low_confidence":       low_confidence,
        "max_aerobic_pace_sec": round(1000 / vvo2max),
        "max_aerobic_vel":      round(float(vvo2max), 2),
        "method_weights":       {"aerobic_efficiency": round(w1, 2), "threshold_anchor": round(w2, 2)},
        "scatter":              scatter_data,
        "regression_line":      {"x": line_x, "y": line_y},
    }




