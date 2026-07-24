from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from firebase_config import db
from datetime import datetime, date, timedelta
import calendar
from zoneinfo import ZoneInfo

_DEFAULT_TZ = "Asia/Singapore"

router = APIRouter()

class AppleHealthSplit(BaseModel):
    km: int
    moving_time: int
    avg_heart_rate: int

class AppleHealthWorkout(BaseModel):
    uuid: str
    name: str
    start_date_local: str  # YYYY-MM-DDTHH:MM:SS
    distance_km: float
    moving_time: int       # seconds
    avg_heart_rate: int
    total_elevation_gain: float = 0.0
    active_calories: float = 0.0
    steps: int = 0
    max_heart_rate: int = 0
    splits: list[AppleHealthSplit] = []

class AppleHealthSyncRequest(BaseModel):
    uid: str
    workouts: list[AppleHealthWorkout]


def get_period_start(period: str, tz_name: str = _DEFAULT_TZ) -> datetime:
    tz = ZoneInfo(tz_name)
    today = datetime.now(tz).date()
    if period == "weekly":
        monday = today - timedelta(days=today.weekday())
        return datetime(monday.year, monday.month, monday.day, 0, 0, 0)
    else:
        return datetime(today.year, today.month, 1, 0, 0, 0)


def pace_str(distance_m: float, moving_time_s: int) -> str:
    km = distance_m / 1000
    if km <= 0 or moving_time_s <= 0:
        return "—"
    sec_per_km = moving_time_s / km
    mins = int(sec_per_km // 60)
    secs = int(sec_per_km % 60)
    return f"{mins}:{secs:02d}"


def format_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


@router.post("/sync")
async def sync_apple_health_workouts(req: AppleHealthSyncRequest):
    """
    Deprecated / Disabled: Apple Health workout sync is disabled.
    We now use Strava exclusively for workouts.
    """
    return {"success": False, "detail": "Apple Health data source disabled"}


class AppleHealthRecoveryItem(BaseModel):
    date: str                  # YYYY-MM-DD
    sleep_duration_sec: int = 0
    sleep_score: int = 0
    resting_heart_rate: int = 0
    heart_rate_variability: int = 0


class AppleHealthRecoverySyncRequest(BaseModel):
    uid: str
    recovery_data: list[AppleHealthRecoveryItem]


@router.post("/sync-recovery")
async def sync_apple_health_recovery(req: AppleHealthRecoverySyncRequest):
    """
    Deprecated / Disabled: Apple Health recovery sync is disabled.
    """
    return {"success": False, "detail": "Apple Health data source disabled"}
