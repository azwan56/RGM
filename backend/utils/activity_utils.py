"""
Activity Utilities — Deduplication & Normalization
"""

from datetime import datetime
from typing import List, Dict, Any

def parse_activity_time(act: Dict[str, Any]) -> float:
    """Parses start_date_local or start_date into UNIX epoch seconds."""
    st = act.get("start_date_local") or act.get("start_date") or ""
    if not st:
        return 0.0
    st_clean = str(st).replace("Z", "").split("+")[0].rstrip("Z")
    try:
        dt = datetime.fromisoformat(st_clean)
        return dt.timestamp()
    except Exception:
        return 0.0

def deduplicate_activities(activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicates activities from multiple sources (Garmin, Strava, Apple Health).
    If two activities occur within 5 minutes (300 seconds) of each other and have
    distance difference <= 0.3 km (or 3%), they represent the exact same workout.
    Garmin activities take precedence over Strava.
    """
    if not activities:
        return []

    # Sort activities: Garmin first, then by timestamp descending
    def sort_key(act):
        source = str(act.get("source", "")).lower()
        # Priority: garmin = 0, strava = 1, applehealth = 2, other = 3
        prio = 0 if source == "garmin" else (1 if source == "strava" else (2 if source == "applehealth" else 3))
        return (parse_activity_time(act), -prio)

    sorted_acts = sorted(activities, key=sort_key, reverse=True)
    kept = []

    for act in sorted_acts:
        t_act = parse_activity_time(act)
        d_act = float(act.get("distance_km", 0) or (act.get("distance", 0) / 1000.0) or 0)

        is_dup = False
        for k in kept:
            t_k = parse_activity_time(k)
            d_k = float(k.get("distance_km", 0) or (k.get("distance", 0) / 1000.0) or 0)

            # Check time difference (within 5 mins / 300 seconds)
            time_diff = abs(t_act - t_k)
            if t_act > 0 and t_k > 0 and time_diff <= 300:
                # Check distance difference (within 0.3 km or 3%)
                dist_diff = abs(d_act - d_k)
                if dist_diff <= 0.3 or (d_k > 0 and (dist_diff / d_k) <= 0.03):
                    is_dup = True
                    break

        if not is_dup:
            kept.append(act)

    # Return activities sorted by start_date_local descending
    return sorted(kept, key=parse_activity_time, reverse=True)
