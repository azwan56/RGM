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
            logger.error(f"[garmin] Failed to fetch activities for {self.email}: {e}")
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
                if summary.get("restingHeartRate"):
                    metrics["resting_heart_rate"] = summary.get("restingHeartRate")
                if summary.get("vo2Max"):
                    metrics["vo2_max"] = summary.get("vo2Max")
                if summary.get("sleepDuration"):
                    metrics["sleep_duration_seconds"] = summary.get("sleepDuration")
                if summary.get("bodyBatteryHighestValue"):
                    metrics["body_battery_max"] = summary.get("bodyBatteryHighestValue")
        except Exception as e:
            logger.debug(f"[garmin] Could not fetch user summary: {e}")

        # 1. Resting Heart Rate (override/supplement)
        try:
            rhr_data = self.client.get_rhr_day(date_str)
            if isinstance(rhr_data, dict) and "allMetrics" in rhr_data:
                val = rhr_data["allMetrics"].get("metricsMap", {}).get("WELLNESS_RESTING_HEART_RATE", [{}])[0].get("value")
                if val:
                    metrics["resting_heart_rate"] = val
            elif isinstance(rhr_data, dict) and "restingHeartRate" in rhr_data:
                val = rhr_data.get("restingHeartRate")
                if val:
                    metrics["resting_heart_rate"] = val
        except Exception as e:
            logger.debug(f"[garmin] Could not fetch RHR: {e}")

        # 2. Sleep Data
        try:
            sleep_data = self.client.get_sleep_data(date_str)
            if isinstance(sleep_data, dict):
                daily_sleep = sleep_data.get("dailySleepDTO", {})
                score = daily_sleep.get("sleepScores", {}).get("overall", {}).get("value")
                if score:
                    metrics["sleep_score"] = score
                dur = daily_sleep.get("sleepTimeSeconds")
                if dur:
                    metrics["sleep_duration_seconds"] = dur
        except Exception as e:
            logger.debug(f"[garmin] Could not fetch sleep data: {e}")

        # 3. HRV Data
        try:
            hrv_data = self.client.get_hrv_data(date_str)
            if isinstance(hrv_data, dict) and "hrvSummary" in hrv_data:
                summary = hrv_data["hrvSummary"]
                metrics["hrv_status"] = summary.get("status")
                metrics["hrv_weekly_avg"] = summary.get("weeklyAvg")
                metrics["hrv_last_night"] = summary.get("lastNightAvg")
        except Exception as e:
            logger.debug(f"[garmin] Could not fetch HRV data: {e}")

        # 4. Body Battery
        try:
            bb_data = self.client.get_body_battery(date_str)
            if isinstance(bb_data, list) and len(bb_data) > 0:
                values = [item.get("charged", 0) for item in bb_data if "charged" in item]
                if values:
                    metrics["body_battery_max"] = max(values)
        except Exception as e:
            logger.debug(f"[garmin] Could not fetch Body Battery data: {e}")

        return metrics

    def _normalize_activity(self, act: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transforms a Garmin activity dict into RGM's standardized Activity format."""
        try:
            act_id = str(act.get("activityId", ""))
            if not act_id:
                return None

            # Type mapping
            raw_type = act.get("activityType", {}).get("typeKey", "running").capitalize()
            activity_type = "Run" if raw_type in ["Running", "Run", "Track_running", "Treadmill_running"] else raw_type

            # Start time formatting
            start_time_local = act.get("startTimeLocal", "")
            if start_time_local and "T" not in start_time_local:
                start_time_local = start_time_local.replace(" ", "T") + "Z"

            # Speed & Pace
            avg_speed = float(act.get("averageSpeed", 0.0))  # m/s
            max_speed = float(act.get("maxSpeed", 0.0))
            distance_m = float(act.get("distance", 0.0))
            moving_time_s = int(act.get("duration", 0))
            elapsed_time_s = int(act.get("elapsedDuration", moving_time_s))

            # Cadence (Garmin returns SPM or RPM; if RPM, multiply by 2 for running steps/min)
            raw_cadence = act.get("averageRunningCadenceInStepsPerMinute") or act.get("averageCadence") or 0
            cadence = int(raw_cadence)

            # Heart Rate
            avg_hr = act.get("averageHR")
            max_hr = act.get("maxHR")

            # Elevation
            elevation_gain = round(float(act.get("elevationGain", 0.0)), 1)

            return {
                "id": f"garmin_{act_id}",
                "source": "garmin",
                "garmin_domain": self.domain,
                "garmin_activity_id": act_id,
                "name": act.get("activityName", "Garmin Workout"),
                "type": activity_type,
                "distance": distance_m,
                "moving_time": moving_time_s,
                "elapsed_time": elapsed_time_s,
                "start_date_local": start_time_local,
                "start_date": start_time_local,
                "average_speed": avg_speed,
                "max_speed": max_speed,
                "average_heartrate": avg_hr,
                "max_heartrate": max_hr,
                "has_heartrate": avg_hr is not None,
                "average_cadence": cadence,
                "total_elevation_gain": elevation_gain,
                "summary_polyline": act.get("summaryPolyline") or "",
            }
        except Exception as e:
            logger.error(f"[garmin] Failed to normalize activity: {e}")
            return None
