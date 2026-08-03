"""
Garmin Sync Adapter
Supports syncing Garmin Activity and Health Metrics from both:
- Garmin Global (connect.garmin.com)
- Garmin China (connect.garmin.cn)

Uses garminconnect python library or direct API fallback.
"""

import os
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("garmin_adapter")

try:
    from garminconnect import Garmin
    HAS_GARMINCONNECT = True
except ImportError:
    Garmin = None
    HAS_GARMINCONNECT = False

class GarminAdapter:
    def __init__(self, email: str, password: str, domain: str = "garmin.cn"):
        self.email = email
        self.password = password
        self.domain = domain.lower().strip()
        self.is_cn = ("garmin.cn" in self.domain or self.domain == "cn")
        self.client: Optional[Any] = None

    def login(self) -> bool:
        """Log in to Garmin Connect (Global or China)."""
        if not HAS_GARMINCONNECT:
            logger.warning("[garmin] garminconnect package not installed.")
            return False

        try:
            logger.info(f"[garmin] Logging in user {self.email} (is_cn={self.is_cn})...")
            self.client = Garmin(self.email, self.password, is_cn=self.is_cn)
            self.client.login()
            logger.info(f"[garmin] Login successful for {self.email}")
            return True
        except Exception as e:
            logger.error(f"[garmin] Login failed for {self.email}: {e}")
            return False

    def fetch_recent_activities(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Fetch latest activities from Garmin and normalize into RGM Activity format."""
        if not self.client:
            if not self.login():
                return []

        try:
            raw_acts = self.client.get_activities(0, limit)
            normalized = []
            for act in raw_acts:
                norm = self._normalize_activity(act)
                if norm:
                    normalized.append(norm)
            return normalized
        except Exception as e:
            logger.error(f"[garmin] Error fetching activities: {e}")
            return []

    def fetch_daily_health_metrics(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        """Fetch daily health metrics (HRV, Sleep, Resting HR, Body Battery)."""
        if not self.client:
            if not self.login():
                return {}

        date_str = target_date or date.today().isoformat()
        metrics = {
            "date": date_str,
            "source": f"garmin_{'cn' if self.is_cn else 'global'}",
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }

        # 0. User Summary Baseline (RHR, VO2 Max, Sleep, Body Battery)
        try:
            summary = self.client.get_user_summary(date_str)
            if isinstance(summary, dict):
                rhr = summary.get("restingHeartRate") or summary.get("userDailySummary", {}).get("restingHeartRate")
                if rhr and rhr > 0:
                    metrics["resting_heart_rate"] = rhr
                vo2 = summary.get("vo2MaxPrecise") or summary.get("vo2Max") or summary.get("userDailySummary", {}).get("vo2Max")
                if vo2 and vo2 > 0:
                    metrics["vo2_max"] = round(float(vo2), 1)
                dur = summary.get("sleepDuration") or summary.get("userDailySummary", {}).get("sleepDuration")
                if dur and dur > 0:
                    metrics["sleep_duration_seconds"] = dur
                bb = summary.get("bodyBatteryHighestValue") or summary.get("userDailySummary", {}).get("bodyBatteryHighestValue")
                if bb and bb > 0:
                    metrics["body_battery_max"] = bb
        except Exception as e:
            logger.debug(f"[garmin] Could not fetch user summary: {e}")

        # 1. Resting Heart Rate
        if "resting_heart_rate" not in metrics:
            try:
                rhr_data = self.client.get_rhr_day(date_str)
                if isinstance(rhr_data, list) and len(rhr_data) > 0:
                    rhr_data = rhr_data[0]
                if isinstance(rhr_data, dict):
                    val = rhr_data.get("restingHeartRate") or rhr_data.get("value")
                    if val and val > 0:
                        metrics["resting_heart_rate"] = val
            except Exception as e:
                logger.debug(f"[garmin] Could not fetch RHR: {e}")

        # 2. Sleep Data
        try:
            sleep_data = self.client.get_sleep_data(date_str)
            if isinstance(sleep_data, dict):
                daily_sleep = sleep_data.get("dailySleepDTO", {}) or sleep_data
                score = daily_sleep.get("sleepScores", {}).get("overall", {}).get("value") or daily_sleep.get("sleepScore")
                if score and score > 0:
                    metrics["sleep_score"] = score
                dur = daily_sleep.get("sleepTimeSeconds") or daily_sleep.get("sleepDuration")
                if dur and dur > 0:
                    metrics["sleep_duration_seconds"] = dur
        except Exception as e:
            logger.debug(f"[garmin] Could not fetch sleep data: {e}")

        # 3. HRV Data
        try:
            hrv_data = self.client.get_hrv_data(date_str)
            if isinstance(hrv_data, dict):
                summary = hrv_data.get("hrvSummary", {}) or hrv_data
                if summary.get("status"):
                    metrics["hrv_status"] = summary.get("status")
                if summary.get("weeklyAvg"):
                    metrics["hrv_weekly_avg"] = summary.get("weeklyAvg")
                if summary.get("lastNightAvg"):
                    metrics["hrv_last_night"] = summary.get("lastNightAvg")
        except Exception as e:
            logger.debug(f"[garmin] Could not fetch HRV: {e}")

        # 4. Body Battery Data
        if "body_battery_max" not in metrics:
            try:
                bb_data = self.client.get_body_battery(date_str)
                if isinstance(bb_data, list) and len(bb_data) > 0:
                    vals = [x.get("charged", 0) or x.get("chargedValue", 0) for x in bb_data if isinstance(x, dict)]
                    if vals and max(vals) > 0:
                        metrics["body_battery_max"] = max(vals)
            except Exception as e:
                logger.debug(f"[garmin] Could not fetch Body Battery: {e}")

        return metrics

    def _normalize_activity(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalizes raw Garmin activity dict to RGM Activity schema."""
        act_id = str(raw.get("activityId") or raw.get("id") or "")
        if not act_id:
            return None

        # Distance in km
        dist_m = raw.get("distance", 0) or 0
        dist_km = round(dist_m / 1000.0, 2)

        # Duration in seconds
        moving_sec = int(raw.get("duration") or raw.get("movingDuration") or 0)
        elapsed_sec = int(raw.get("elapsedDuration") or moving_sec)

        # Dates
        start_date_local = raw.get("startTimeLocal") or raw.get("startDateLocal") or ""
        if not start_date_local:
            return None

        # Format duration string
        mins = moving_sec // 60
        secs = moving_sec % 60
        duration_str = f"{mins}:{secs:02d}"

        # Pace string
        pace_str = "—"
        if dist_km > 0 and moving_sec > 0:
            sec_per_km = int(moving_sec / dist_km)
            p_min = sec_per_km // 60
            p_sec = sec_per_km % 60
            pace_str = f"{p_min}:{p_sec:02d}"

        avg_hr = round(raw.get("averageHR", 0) or 0)
        max_hr = round(raw.get("maxHR", 0) or 0)
        elevation = round(float(raw.get("elevationGain") or raw.get("totalElevationGain") or 0), 1)

        return {
            "activity_id": f"garmin_{act_id}",
            "name": raw.get("activityName") or "Garmin Running",
            "start_date_local": start_date_local,
            "distance_km": dist_km,
            "moving_time": moving_sec,
            "elapsed_time": elapsed_sec,
            "duration_str": duration_str,
            "avg_pace": pace_str,
            "avg_heart_rate": avg_hr,
            "max_heart_rate": max_hr,
            "total_elevation_gain": elevation,
            "activity_type": "run",
            "source": f"garmin_{'cn' if self.is_cn else 'global'}",
            "garmin_raw_id": act_id,
        }
