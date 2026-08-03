"""
Activity Utilities — Deduplication & Normalization
"""

from datetime import datetime
from typing import List, Dict, Any

def parse_activity_time(act: Dict[str, Any]) -> float:
    """Parses start_date_local, start_date, or startTimeLocal into UNIX epoch seconds."""
    st = act.get("start_date_local") or act.get("start_date") or act.get("startTimeLocal") or ""
    if not st:
        return 0.0
    st_str = str(st).strip().replace(" ", "T")
    if st_str.endswith("Z") or st_str.endswith("z"):
        st_str = st_str[:-1]
    if "+" in st_str:
        st_str = st_str.split("+")[0]

    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(st_str, fmt)
            return dt.timestamp()
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(st_str)
        return dt.timestamp()
    except Exception:
        return 0.0

def get_activity_date_str(act: Dict[str, Any]) -> str:
    """Returns YYYY-MM-DD string for an activity."""
    st = act.get("start_date_local") or act.get("start_date") or act.get("startTimeLocal") or ""
    if not st:
        return ""
    st_str = str(st).strip()
    return st_str[:10]  # First 10 chars: YYYY-MM-DD

def deduplicate_activities(activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicates activities from multiple sources (Garmin, Strava, Apple Health).
    Two activities represent the exact same workout if:
    1. They occur within 5 minutes (300 seconds) OR on the same day (YYYY-MM-DD), AND
    2. Distance difference is <= 0.3 km (or <= 3%).
    Garmin activities take precedence over Strava.
    """
    if not activities:
        return []

    # Helper to sort: Garmin priority = 0, Strava = 1, AppleHealth = 2, others = 3
    def sort_key(act):
        source = str(act.get("source", "")).lower()
        prio = 0 if source == "garmin" else (1 if source == "strava" else (2 if source == "applehealth" else 3))
        return (parse_activity_time(act), -prio)

    sorted_acts = sorted(activities, key=sort_key, reverse=True)
    kept = []

    for act in sorted_acts:
        t_act = parse_activity_time(act)
        d_str_act = get_activity_date_str(act)
        d_act = float(act.get("distance_km", 0) or (act.get("distance", 0) / 1000.0) or 0)

        is_dup = False
        for k in kept:
            t_k = parse_activity_time(k)
            d_str_k = get_activity_date_str(k)
            d_k = float(k.get("distance_km", 0) or (k.get("distance", 0) / 1000.0) or 0)

            # Check distance difference (within 0.3 km or 3%)
            dist_diff = abs(d_act - d_k)
            dist_matches = dist_diff <= 0.3 or (d_k > 0 and (dist_diff / d_k) <= 0.03)

            if dist_matches:
                # Check time difference (within 5 mins / 300s) OR same date string
                time_diff = abs(t_act - t_k)
                time_matches = (t_act > 0 and t_k > 0 and time_diff <= 300) or (d_str_act and d_str_act == d_str_k)
                if time_matches:
                    is_dup = True
                    break

        if not is_dup:
            kept.append(act)

    # Return activities sorted by start_date_local descending
    return sorted(kept, key=parse_activity_time, reverse=True)
