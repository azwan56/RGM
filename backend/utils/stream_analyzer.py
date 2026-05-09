"""
Stream Data Analyzer — computes detailed training metrics from Strava stream data.

Takes raw Strava streams (velocity, heartrate, cadence, altitude, distance)
and produces structured stats for AI coach analysis:
  - Per-km pace splits
  - Heart rate zone distribution
  - HR drift (cardiac decoupling)
  - Cadence consistency
  - Elevation profile stats
  - Pace variability & negative split detection
"""

from typing import Optional
import math


def analyze_streams(
    distances: list,
    velocities: list,
    heartrates: list,
    cadences: list,
    altitudes: list,
    *,
    max_hr: int = 190,
    rest_hr: int = 60,
) -> dict:
    """
    Analyze raw Strava stream arrays and return structured training metrics.

    Args:
        distances: distance in meters at each point
        velocities: smoothed velocity in m/s at each point
        heartrates: heart rate in bpm at each point
        cadences: cadence in RPM (Strava gives half-cycles, caller should *2 if needed)
        altitudes: altitude in meters at each point
        max_hr: user's max heart rate for zone calculation
        rest_hr: user's resting heart rate

    Returns:
        dict with pace_splits, hr_zones, hr_drift, cadence stats, etc.
    """
    result = {}

    # ── Per-km pace splits ────────────────────────────────────────────────────
    if distances and velocities:
        result["pace_splits"] = _compute_km_splits(distances, velocities)
        splits = result["pace_splits"]
        if splits:
            # Best / worst km
            result["best_km"] = {"km": 0, "pace": ""}
            result["worst_km"] = {"km": 0, "pace": ""}
            best_val, worst_val = 999, 0
            for s in splits:
                if s["pace_min"] < best_val:
                    best_val = s["pace_min"]
                    result["best_km"] = {"km": s["km"], "pace": s["pace"]}
                if s["pace_min"] > worst_val:
                    worst_val = s["pace_min"]
                    result["worst_km"] = {"km": s["km"], "pace": s["pace"]}

            # Pace consistency (coefficient of variation, lower = more consistent)
            pace_vals = [s["pace_min"] for s in splits]
            if len(pace_vals) > 1:
                avg_p = sum(pace_vals) / len(pace_vals)
                std_p = (sum((p - avg_p) ** 2 for p in pace_vals) / len(pace_vals)) ** 0.5
                result["pace_cv"] = round(std_p / avg_p * 100, 1)  # CV%
                result["pace_consistency"] = "稳定" if result["pace_cv"] < 5 else "较稳定" if result["pace_cv"] < 10 else "波动较大"
            else:
                result["pace_cv"] = 0
                result["pace_consistency"] = "—"

            # Negative split detection (2nd half faster than 1st half)
            mid = len(pace_vals) // 2
            if mid > 0:
                first_half_avg = sum(pace_vals[:mid]) / mid
                second_half_avg = sum(pace_vals[mid:]) / len(pace_vals[mid:])
                result["negative_split"] = second_half_avg < first_half_avg
                result["split_diff_pct"] = round(
                    (first_half_avg - second_half_avg) / first_half_avg * 100, 1
                )
            else:
                result["negative_split"] = False
                result["split_diff_pct"] = 0

    # ── Heart rate zone distribution ──────────────────────────────────────────
    if heartrates:
        valid_hr = [hr for hr in heartrates if hr and hr > 0]
        if valid_hr:
            result["hr_zones"] = _compute_hr_zones(valid_hr, max_hr, rest_hr)
            result["hr_avg"] = round(sum(valid_hr) / len(valid_hr))
            result["hr_max_actual"] = max(valid_hr)
            result["hr_min"] = min(valid_hr)

            # HR drift (cardiac decoupling): compare avg HR in 1st half vs 2nd half
            mid = len(valid_hr) // 2
            if mid > 0:
                first_avg = sum(valid_hr[:mid]) / mid
                second_avg = sum(valid_hr[mid:]) / len(valid_hr[mid:])
                result["hr_drift_pct"] = round(
                    (second_avg - first_avg) / first_avg * 100, 1
                )
                if result["hr_drift_pct"] < 3:
                    result["hr_drift_assessment"] = "良好（心脏效率高）"
                elif result["hr_drift_pct"] < 5:
                    result["hr_drift_assessment"] = "正常"
                elif result["hr_drift_pct"] < 10:
                    result["hr_drift_assessment"] = "偏高（可能需要降速或补水）"
                else:
                    result["hr_drift_assessment"] = "过高（有氧耐力不足或天气/脱水影响）"

    # ── Cadence analysis ─────────────────────────────────────────────────────
    if cadences:
        valid_cad = [int(c * 2) for c in cadences if c and c > 0]  # Strava gives half-cycles
        if valid_cad:
            result["cadence_avg"] = round(sum(valid_cad) / len(valid_cad))
            result["cadence_range"] = [min(valid_cad), max(valid_cad)]
            # Cadence assessment
            avg_cad = result["cadence_avg"]
            if avg_cad >= 180:
                result["cadence_assessment"] = "优秀（高效步频）"
            elif avg_cad >= 170:
                result["cadence_assessment"] = "良好"
            elif avg_cad >= 160:
                result["cadence_assessment"] = "一般（可适当提高步频）"
            else:
                result["cadence_assessment"] = "偏低（建议通过节拍器训练提升）"

    # ── Elevation profile ─────────────────────────────────────────────────────
    if altitudes:
        valid_alt = [a for a in altitudes if a is not None]
        if len(valid_alt) > 1:
            total_gain = 0
            total_loss = 0
            for i in range(1, len(valid_alt)):
                diff = valid_alt[i] - valid_alt[i - 1]
                if diff > 0:
                    total_gain += diff
                else:
                    total_loss += abs(diff)
            result["elevation_gain"] = round(total_gain)
            result["elevation_loss"] = round(total_loss)
            result["elevation_max"] = round(max(valid_alt))
            result["elevation_min"] = round(min(valid_alt))

            # Grade category (for total distance)
            if distances:
                total_dist_km = distances[-1] / 1000 if distances[-1] > 0 else 1
                gain_per_km = total_gain / total_dist_km
                if gain_per_km > 40:
                    result["terrain_type"] = "高强度山地/越野"
                elif gain_per_km > 20:
                    result["terrain_type"] = "丘陵/轻越野"
                elif gain_per_km > 5:
                    result["terrain_type"] = "起伏路面"
                else:
                    result["terrain_type"] = "平路"

    return result


def _compute_km_splits(distances: list, velocities: list) -> list:
    """Compute per-km split paces from distance and velocity streams."""
    if not distances or not velocities:
        return []

    splits = []
    km_mark = 1000  # next km boundary in meters
    km_num = 1
    segment_times = []  # collect time-equivalent at each point

    # Build time from velocity (dt = ds / v)
    for i in range(1, min(len(distances), len(velocities))):
        ds = distances[i] - distances[i - 1]
        v = velocities[i] if velocities[i] and velocities[i] > 0.3 else velocities[i - 1] if velocities[i - 1] and velocities[i - 1] > 0.3 else 1.0
        dt = ds / v if v > 0 else 0
        segment_times.append((distances[i], dt))

        if distances[i] >= km_mark:
            # Calculate time for this km
            km_start = (km_num - 1) * 1000
            total_dt = sum(
                dt for d, dt in segment_times
                if km_start < d <= km_mark
            )
            if total_dt > 0:
                pace_min = total_dt / 60  # minutes per km
                mins = int(pace_min)
                secs = int((pace_min - mins) * 60)
                splits.append({
                    "km": km_num,
                    "pace": f"{mins}:{secs:02d}",
                    "pace_min": round(pace_min, 2),
                })
            km_num += 1
            km_mark = km_num * 1000

    return splits


def _compute_hr_zones(heartrates: list, max_hr: int, rest_hr: int) -> dict:
    """
    Compute time-in-zone distribution using Karvonen formula.
    Zones:
      Z1: 50-60% HRR (Recovery)
      Z2: 60-70% HRR (Aerobic base)
      Z3: 70-80% HRR (Tempo)
      Z4: 80-90% HRR (Threshold)
      Z5: 90-100% HRR (VO2max)
    """
    hrr = max_hr - rest_hr
    if hrr <= 0:
        hrr = 130  # fallback

    zone_thresholds = [
        rest_hr + hrr * 0.50,  # Z1 lower
        rest_hr + hrr * 0.60,  # Z2 lower
        rest_hr + hrr * 0.70,  # Z3 lower
        rest_hr + hrr * 0.80,  # Z4 lower
        rest_hr + hrr * 0.90,  # Z5 lower
    ]

    counts = {"Z1": 0, "Z2": 0, "Z3": 0, "Z4": 0, "Z5": 0}
    zone_names = {"Z1": "恢复区", "Z2": "有氧区", "Z3": "节奏区", "Z4": "阈值区", "Z5": "极限区"}

    for hr in heartrates:
        if hr < zone_thresholds[0]:
            counts["Z1"] += 1
        elif hr < zone_thresholds[1]:
            counts["Z1"] += 1
        elif hr < zone_thresholds[2]:
            counts["Z2"] += 1
        elif hr < zone_thresholds[3]:
            counts["Z3"] += 1
        elif hr < zone_thresholds[4]:
            counts["Z4"] += 1
        else:
            counts["Z5"] += 1

    total = len(heartrates) or 1
    result = {}
    for zone, count in counts.items():
        pct = round(count / total * 100, 1)
        result[zone] = {"pct": pct, "name": zone_names[zone]}

    # Determine primary zone
    primary_zone = max(counts, key=counts.get)
    result["primary_zone"] = f"{primary_zone} ({zone_names[primary_zone]})"
    result["thresholds"] = {
        f"Z{i+1}": round(zone_thresholds[i]) for i in range(5)
    }

    return result


def format_stream_stats_for_prompt(stats: dict) -> str:
    """Format stream analysis results into a readable string for AI prompt injection."""
    lines = []

    # Pace splits
    splits = stats.get("pace_splits", [])
    if splits:
        split_strs = [f"  K{s['km']}: {s['pace']}/km" for s in splits]
        lines.append("【逐公里配速】")
        lines.extend(split_strs)
        if stats.get("best_km"):
            lines.append(f"  最快: K{stats['best_km']['km']} ({stats['best_km']['pace']}/km)")
        if stats.get("worst_km"):
            lines.append(f"  最慢: K{stats['worst_km']['km']} ({stats['worst_km']['pace']}/km)")
        if stats.get("pace_consistency"):
            lines.append(f"  配速稳定性: {stats['pace_consistency']} (CV={stats.get('pace_cv', 0)}%)")
        if "negative_split" in stats:
            ns = "负分段（后半程加速）" if stats["negative_split"] else "正分段（后半程减速）"
            lines.append(f"  分段策略: {ns}, 差异{abs(stats.get('split_diff_pct', 0))}%")

    # HR zones
    hr_zones = stats.get("hr_zones", {})
    if hr_zones and hr_zones.get("primary_zone"):
        lines.append("\n【心率区间分布】")
        for z in ["Z1", "Z2", "Z3", "Z4", "Z5"]:
            if z in hr_zones and isinstance(hr_zones[z], dict):
                pct = hr_zones[z]["pct"]
                name = hr_zones[z]["name"]
                bar = "█" * int(pct / 5) if pct > 0 else ""
                lines.append(f"  {z} {name}: {pct}% {bar}")
        lines.append(f"  主要训练区间: {hr_zones['primary_zone']}")

    # HR drift
    if "hr_drift_pct" in stats:
        lines.append(f"\n【心率漂移】{stats['hr_drift_pct']}% — {stats.get('hr_drift_assessment', '')}")

    # Cadence
    if "cadence_avg" in stats:
        lines.append(f"\n【步频分析】平均 {stats['cadence_avg']}spm, 范围 {stats.get('cadence_range', [])}")
        if stats.get("cadence_assessment"):
            lines.append(f"  评估: {stats['cadence_assessment']}")

    # Elevation
    if "elevation_gain" in stats:
        lines.append(
            f"\n【海拔分析】爬升 +{stats['elevation_gain']}m / 下降 -{stats['elevation_loss']}m, "
            f"海拔范围 {stats.get('elevation_min', 0)}-{stats.get('elevation_max', 0)}m"
        )
        if stats.get("terrain_type"):
            lines.append(f"  地形: {stats['terrain_type']}")

    return "\n".join(lines)
