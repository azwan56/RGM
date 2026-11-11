import sqlite3 as _raw_sqlite3
import os
import json
import uuid
import hashlib
import random
import string
import logging
import time
import calendar
import copy
import math
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date, timedelta, timezone
from utils.encryption import encrypt_pii, decrypt_pii, compute_age_group


class _AutoClosingConnection(_raw_sqlite3.Connection):
    """Ensures `with sqlite3.connect(...) as conn:` both commits/rolls back AND closes the file descriptor."""
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            try:
                self.close()
            except Exception:
                pass


class _Sqlite3Proxy:
    Row = _raw_sqlite3.Row
    Error = _raw_sqlite3.Error
    OperationalError = _raw_sqlite3.OperationalError
    IntegrityError = _raw_sqlite3.IntegrityError
    DatabaseError = _raw_sqlite3.DatabaseError

    @staticmethod
    def connect(database, *args, **kwargs):
        kwargs.setdefault("timeout", 15.0)
        kwargs.setdefault("factory", _AutoClosingConnection)
        conn = _raw_sqlite3.connect(database, *args, **kwargs)
        try:
            conn.execute("PRAGMA busy_timeout = 15000")
            conn.execute("PRAGMA synchronous = NORMAL")
        except Exception:
            pass
        return conn

    def __getattr__(self, name):
        return getattr(_raw_sqlite3, name)


sqlite3 = _Sqlite3Proxy()

logger = logging.getLogger("local_store")

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.environ.get("RGM_DB_PATH") or os.path.join(DB_DIR, "rgm.db")


def db_connect(database: Optional[str] = None, *args, **kwargs):
    """Unified auto-closing SQLite connection helper with WAL/busy_timeout pragmas."""
    return sqlite3.connect(database or DB_PATH, *args, **kwargs)

DEFAULT_ORG_PROGRAMS = [
    "中文EMBA",
    "台大班",
    "复旦-BI（挪威）",
    "奥林班",
    "港大班"
]

GOBI_EDITIONS = [f"戈{i}" for i in range(1, 22)]
GOBI_GROUPS = ["A组", "B组", "C组"]

DEFAULT_ORG_FIELD_RULES = [
    {"field": "real_name", "label": "真实姓名", "required": True, "hidden": False, "mode": "required", "type": "text"},
    {"field": "gender", "label": "性别", "required": True, "hidden": False, "mode": "required", "type": "select", "options": ["male", "female"]},
    {"field": "date_of_birth", "label": "出生日期", "required": True, "hidden": False, "mode": "required", "type": "date"},
    {"field": "class_name", "label": "商学院项目与班级", "required": True, "hidden": False, "mode": "required", "type": "text"},
    {"field": "gobi_experience", "label": "戈壁经历(新戈/戈1-戈21)", "required": False, "hidden": False, "mode": "optional", "type": "select"},
    {"field": "phone", "label": "手机号码", "required": False, "hidden": False, "mode": "optional", "type": "phone"},
    {"field": "id_card", "label": "证件号码(身份证/护照)", "required": False, "hidden": False, "mode": "optional", "type": "id_card"},
    {"field": "emergency_contact", "label": "紧急联系人及电话", "required": False, "hidden": False, "mode": "optional", "type": "text"},
    {"field": "clothing_size", "label": "队服尺码", "required": False, "hidden": False, "mode": "optional", "type": "text"},
    {"field": "shoe_size", "label": "跑鞋尺码", "required": False, "hidden": False, "mode": "optional", "type": "text"},
    {"field": "marathon_pb", "label": "全马PB成绩", "required": False, "hidden": False, "mode": "optional", "type": "text"},
    {"field": "health_declaration", "label": "健康状况声明", "required": False, "hidden": False, "mode": "optional", "type": "boolean"},
]

def parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        clean = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean)
    except Exception:
        try:
            clean_str = dt_str.split(".")[0].replace("Z", "")
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(clean_str, fmt).replace(tzinfo=timezone.utc)
                except Exception:
                    continue
        except Exception:
            pass
    return None

def generate_invite_code(length: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace("O", "").replace("0", "").replace("I", "").replace("1", "")
    return "".join(random.choice(chars) for _ in range(length))

_CN_TZ = timezone(timedelta(hours=8))

def get_beijing_now() -> datetime:
    """Returns current datetime in China Standard Time (UTC+8)."""
    return datetime.utcnow() + timedelta(hours=8)

def get_beijing_today() -> date:
    """Returns today's date in China Standard Time (UTC+8)."""
    return (datetime.utcnow() + timedelta(hours=8)).date()

def get_beijing_iso() -> str:
    """Returns current China Standard Time (UTC+8) as ISO-8601 string, e.g. '2026-11-06T10:35:00+08:00'."""
    return datetime.now(_CN_TZ).isoformat(timespec="seconds")

def to_beijing_iso(dt_str: Optional[str]) -> Optional[str]:
    """Normalizes any UTC ('...Z' / '+00:00') or tz-aware ISO timestamp to China Standard Time ('+08:00')."""
    if not dt_str or not isinstance(dt_str, str):
        return dt_str
    s = dt_str.strip()
    if not s or s.endswith("+08:00") or s.endswith("+0800"):
        return s
    if not (s.endswith(("Z", "z")) or re.search(r"[+-]\d{2}:?\d{2}$", s)):
        return s
    dt = parse_iso_datetime(s)
    if dt is not None and dt.tzinfo is not None:
        return dt.astimezone(_CN_TZ).isoformat(timespec="seconds")
    return s

def _build_slim_route_preview(raw_track: Any) -> Optional[Dict[str, Any]]:
    """Extracts a compact <=250-point polyline thumbnail (normalized to latitude/longitude + bounds) from full gps_track_data."""
    if not raw_track:
        return None
    parsed = raw_track
    if isinstance(raw_track, str):
        try:
            parsed = json.loads(raw_track)
        except Exception:
            return None
    if isinstance(parsed, list):
        pts = parsed
    elif isinstance(parsed, dict):
        pts = parsed.get("points") if parsed.get("points") is not None else parsed.get("route")
    else:
        return None
    if not isinstance(pts, list) or len(pts) < 2:
        return None

    valid_pts: List[Dict[str, float]] = []
    for p in pts:
        lat_v = None
        lng_v = None
        if isinstance(p, dict):
            lat_v = p.get("latitude") if p.get("latitude") is not None else p.get("lat")
            lng_v = (
                p.get("longitude")
                if p.get("longitude") is not None
                else (p.get("lng") if p.get("lng") is not None else p.get("lon"))
            )
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            lat_v, lng_v = p[0], p[1]
        if lat_v is not None and lng_v is not None:
            try:
                valid_pts.append({"latitude": float(lat_v), "longitude": float(lng_v)})
            except (TypeError, ValueError):
                continue

    if len(valid_pts) < 2:
        return None
    try:
        from utils.geo_utils import smooth_sparse_stadium_track
        smoothed = smooth_sparse_stadium_track(valid_pts, max_output_points=250)
        if smoothed is not valid_pts and len(smoothed) >= 2:
            valid_pts = smoothed
    except Exception:
        pass
    max_pts = 250
    if len(valid_pts) <= max_pts:
        sampled = valid_pts
    else:
        step = (len(valid_pts) - 1) / float(max_pts - 1)
        sampled = [valid_pts[int(round(i * step))] for i in range(max_pts - 1)] + [valid_pts[-1]]
    slim_pts = [
        {
            "latitude": round(float(p["latitude"]), 6),
            "longitude": round(float(p["longitude"]), 6),
        }
        for p in sampled
    ]
    if len(slim_pts) < 2:
        return None
    min_lat = min(p["latitude"] for p in slim_pts)
    max_lat = max(p["latitude"] for p in slim_pts)
    min_lng = min(p["longitude"] for p in slim_pts)
    max_lng = max(p["longitude"] for p in slim_pts)
    return {
        "points": slim_pts,
        "center": {
            "latitude": round((min_lat + max_lat) / 2.0, 6),
            "longitude": round((min_lng + max_lng) / 2.0, 6),
        },
        "bounds": {
            "southwest": {"latitude": min_lat, "longitude": min_lng},
            "northeast": {"latitude": max_lat, "longitude": max_lng},
        },
    }


def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA synchronous = NORMAL")
        except Exception:
            pass
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                email TEXT,
                password_hash TEXT,
                display_name TEXT,
                avatar_url TEXT,
                phone TEXT,
                wechat_openid TEXT,
                garmin_connected BOOLEAN DEFAULT 0,
                garmin_email TEXT,
                garmin_encrypted_password TEXT,
                garmin_domain TEXT DEFAULT 'garmin.cn',
                garmin_last_sync_at TEXT,
                coros_connected BOOLEAN DEFAULT 0,
                coros_account TEXT,
                coros_encrypted_password TEXT,
                coros_domain TEXT DEFAULT 'teamcnapi.coros.com',
                coros_last_sync_at TEXT,
                marathon_pb INTEGER DEFAULT NULL,
                half_pb INTEGER DEFAULT NULL,
                ten_k_pb INTEGER DEFAULT NULL,
                five_k_pb INTEGER DEFAULT NULL,
                resting_heart_rate INTEGER DEFAULT 56,
                max_heart_rate INTEGER DEFAULT 190,
                gender TEXT DEFAULT 'male',
                height_cm REAL DEFAULT 175.0,
                weight_kg REAL DEFAULT 65.0,
                years_running INTEGER DEFAULT 3,
                bio TEXT,
                date_of_birth TEXT,
                real_name TEXT,
                id_card TEXT,
                vo2max REAL,
                wecom_webhook_url TEXT,
                created_at TEXT
            )
        """)
        try:
            cursor.execute("ALTER TABLE profiles ADD COLUMN password_hash TEXT")
        except Exception:
            pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                name TEXT,
                sport_type TEXT,
                start_time TEXT,
                distance_meters REAL,
                moving_time_seconds INTEGER,
                elapsed_time_seconds INTEGER,
                elevation_gain_meters REAL,
                average_heartrate INTEGER,
                max_heartrate INTEGER,
                average_cadence REAL,
                avg_pace_str TEXT,
                calories INTEGER,
                aerobic_training_effect REAL,
                anaerobic_training_effect REAL,
                trimp REAL,
                ai_journal TEXT,
                laps_data TEXT,
                splits_data TEXT,
                gps_track_data TEXT,
                map_image_url TEXT,
                segment_analysis_json TEXT,
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)
        try:
            cursor.execute("ALTER TABLE activities ADD COLUMN gps_track_data TEXT")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE activities ADD COLUMN map_image_url TEXT")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE activities ADD COLUMN exclude_mode TEXT DEFAULT 'normal'")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE activities ADD COLUMN segment_analysis_json TEXT")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE activities ADD COLUMN route_preview_json TEXT")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE activities ADD COLUMN has_gps_track INTEGER DEFAULT 0")
        except Exception:
            pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_streams (
                activity_id TEXT PRIMARY KEY,
                user_id TEXT,
                gps_track_data TEXT,
                updated_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_streams_user ON activity_streams(user_id)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_health (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                date TEXT,
                resting_heart_rate INTEGER,
                vo2_max REAL,
                sleep_duration_seconds INTEGER,
                sleep_duration_hours REAL,
                sleep_score INTEGER,
                body_battery_max INTEGER,
                body_battery_min INTEGER,
                body_battery_current INTEGER,
                hrv_status TEXT,
                hrv_weekly_avg REAL,
                hrv_last_night_avg REAL,
                steps INTEGER,
                active_calories INTEGER,
                nap_duration_seconds INTEGER,
                stress_avg INTEGER,
                stress_max INTEGER,
                hr_min INTEGER,
                hr_max INTEGER,
                updated_at TEXT,
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)
        for dh_col in [
            "body_battery_current INTEGER",
            "steps INTEGER",
            "active_calories INTEGER",
            "nap_duration_seconds INTEGER",
            "stress_avg INTEGER",
            "stress_max INTEGER",
            "hr_min INTEGER",
            "hr_max INTEGER",
            "updated_at TEXT",
        ]:
            try:
                cursor.execute(f"ALTER TABLE daily_health ADD COLUMN {dh_col}")
            except Exception:
                pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                user_id TEXT PRIMARY KEY,
                target_distance REAL DEFAULT 200.0,
                weekly_target REAL DEFAULT 50.0,
                period_type TEXT DEFAULT 'monthly',
                monthly_targets TEXT,
                weekly_targets_map TEXT,
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)
        try:
            cursor.execute("ALTER TABLE goals ADD COLUMN weekly_target REAL DEFAULT 50.0")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE goals ADD COLUMN weekly_targets_map TEXT")
        except Exception:
            pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS race_plans (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                name TEXT,
                race_type TEXT,
                race_date TEXT,
                target_time TEXT,
                priority INTEGER DEFAULT 1,
                created_at TEXT,
                race_info TEXT,
                status TEXT DEFAULT 'upcoming',
                finish_time TEXT,
                finish_notes TEXT,
                photo_url TEXT,
                photos TEXT,
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)
        # Migration: add columns to existing databases
        for col_def in [
            "race_info TEXT",
            "status TEXT DEFAULT 'upcoming'",
            "finish_time TEXT",
            "finish_notes TEXT",
            "photo_url TEXT",
            "photos TEXT",
            "was_official_pacer INTEGER DEFAULT 0",
            "pacer_target_time TEXT DEFAULT ''",
        ]:
            try:
                cursor.execute(f"ALTER TABLE race_plans ADD COLUMN {col_def}")
            except Exception:
                pass

        for prof_col in [
            "first_aid_cert_type TEXT DEFAULT ''",
            "pacer_bio_tags TEXT DEFAULT ''",
        ]:
            try:
                cursor.execute(f"ALTER TABLE profiles ADD COLUMN {prof_col}")
            except Exception:
                pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS race_intel_cache (
                cache_key TEXT PRIMARY KEY,
                event_name TEXT NOT NULL,
                race_category TEXT DEFAULT 'road',
                race_info_json TEXT NOT NULL,
                source TEXT DEFAULT 'official_web_search',
                updated_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coach_reports (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                content TEXT,
                updated_at TEXT,
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)

        # ── Grand Community / Organization Hierarchy Schema ──
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                logo_url TEXT,
                description TEXT,
                city TEXT DEFAULT '上海',
                invite_code TEXT UNIQUE NOT NULL,
                join_mode TEXT DEFAULT 'invite', -- 'free' (自由入会) or 'invite' (凭邀请码入会)
                owner_id TEXT,
                created_at TEXT,
                settings TEXT,
                FOREIGN KEY(owner_id) REFERENCES profiles(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS organization_members (
                id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                real_name TEXT NOT NULL,
                gender TEXT NOT NULL,
                date_of_birth TEXT NOT NULL,
                class_name TEXT NOT NULL,
                phone TEXT,
                id_card TEXT,
                role TEXT DEFAULT 'member', -- 'owner', 'admin', 'member'
                status TEXT DEFAULT 'confirmed', -- 'confirmed', 'pending'
                joined_at TEXT,
                confirmed_at TEXT,
                confirmed_by TEXT,
                UNIQUE(org_id, user_id),
                FOREIGN KEY(org_id) REFERENCES organizations(id),
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)

        # ── Multi-Tenant Running Clubs Schema ──
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clubs (
                id TEXT PRIMARY KEY,
                org_id TEXT,
                name TEXT NOT NULL,
                logo_url TEXT,
                description TEXT,
                city TEXT DEFAULT '上海',
                invite_code TEXT UNIQUE,
                owner_id TEXT,
                created_at TEXT,
                settings TEXT,
                join_mode TEXT DEFAULT 'free', -- 'free' (自由入团) or 'invite' (凭邀请码入团)
                status TEXT DEFAULT 'active', -- 'active' (正常), 'paused' (暂停), 'locked' (锁定)
                FOREIGN KEY(org_id) REFERENCES organizations(id),
                FOREIGN KEY(owner_id) REFERENCES profiles(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS club_memberships (
                id TEXT PRIMARY KEY,
                club_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT DEFAULT 'member', -- 'owner', 'coach', 'member'
                status TEXT DEFAULT 'active', -- 'active', 'pending', 'banned'
                joined_at TEXT,
                privacy_consent BOOLEAN DEFAULT 1, -- 1: allow coach to view physiological load
                UNIQUE(club_id, user_id),
                FOREIGN KEY(club_id) REFERENCES clubs(id),
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS club_events (
                id TEXT PRIMARY KEY,
                club_id TEXT NOT NULL,
                title TEXT NOT NULL,
                event_type TEXT DEFAULT 'distance_challenge', -- 'distance_challenge', 'lsd_group_run'
                start_date TEXT,
                end_date TEXT,
                target_km REAL DEFAULT 200.0,
                rules TEXT,
                created_at TEXT,
                FOREIGN KEY(club_id) REFERENCES clubs(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coach_assignments (
                id TEXT PRIMARY KEY,
                club_id TEXT NOT NULL,
                coach_id TEXT NOT NULL,
                student_id TEXT NOT NULL,
                created_at TEXT,
                UNIQUE(club_id, coach_id, student_id),
                FOREIGN KEY(club_id) REFERENCES clubs(id),
                FOREIGN KEY(coach_id) REFERENCES profiles(id),
                FOREIGN KEY(student_id) REFERENCES profiles(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_likes (
                id TEXT PRIMARY KEY,
                activity_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                created_at TEXT,
                UNIQUE(activity_id, user_id),
                FOREIGN KEY(activity_id) REFERENCES activities(id),
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_comments (
                id TEXT PRIMARY KEY,
                activity_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                author_name TEXT,
                author_avatar TEXT,
                content TEXT NOT NULL,
                parent_id TEXT,
                reply_to_user_id TEXT,
                reply_to_name TEXT,
                created_at TEXT,
                FOREIGN KEY(activity_id) REFERENCES activities(id),
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)
        for col_sql in (
            "ALTER TABLE activity_comments ADD COLUMN parent_id TEXT",
            "ALTER TABLE activity_comments ADD COLUMN reply_to_user_id TEXT",
            "ALTER TABLE activity_comments ADD COLUMN reply_to_name TEXT",
        ):
            try:
                cursor.execute(col_sql)
            except Exception:
                pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_plans (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                club_id TEXT,
                title TEXT NOT NULL,
                goal_type TEXT NOT NULL,
                maintenance_focus TEXT,
                target_race_id TEXT,
                target_race_name TEXT,
                target_date TEXT,
                start_date TEXT,
                end_date TEXT,
                weeks_count INTEGER DEFAULT 8,
                days_per_week INTEGER DEFAULT 4,
                preferred_long_run_day TEXT DEFAULT 'Sunday',
                status TEXT DEFAULT 'active',
                review_status TEXT DEFAULT 'self_created',
                reviewed_by TEXT,
                reviewed_by_name TEXT,
                reviewed_at TEXT,
                coach_review_note TEXT,
                overview_summary TEXT,
                schedule_data TEXT,
                creator_id TEXT NOT NULL,
                last_modified_by TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)
        cursor.execute("PRAGMA table_info(training_plans)")
        tp_cols = {row[1] for row in cursor.fetchall()}
        if "review_status" not in tp_cols:
            cursor.execute("ALTER TABLE training_plans ADD COLUMN review_status TEXT DEFAULT 'self_created'")
        if "reviewed_by" not in tp_cols:
            cursor.execute("ALTER TABLE training_plans ADD COLUMN reviewed_by TEXT")
        if "reviewed_by_name" not in tp_cols:
            cursor.execute("ALTER TABLE training_plans ADD COLUMN reviewed_by_name TEXT")
        if "reviewed_at" not in tp_cols:
            cursor.execute("ALTER TABLE training_plans ADD COLUMN reviewed_at TEXT")
        if "coach_review_note" not in tp_cols:
            cursor.execute("ALTER TABLE training_plans ADD COLUMN coach_review_note TEXT")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coach_custom_templates (
                id TEXT PRIMARY KEY,
                club_id TEXT,
                creator_id TEXT,
                group_code TEXT NOT NULL,
                category TEXT DEFAULT 'custom',
                name TEXT NOT NULL,
                short_name TEXT NOT NULL,
                badge_color TEXT DEFAULT 'amber',
                target_level TEXT,
                intensity_tag TEXT,
                weekly_km REAL DEFAULT 50.0,
                days_per_week INTEGER DEFAULT 5,
                pace_zones TEXT,
                macro_roadmap TEXT,
                coach_review_note TEXT,
                days_template TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_plan_backups (
                id TEXT PRIMARY KEY,
                batch_id TEXT,
                user_id TEXT NOT NULL,
                club_id TEXT,
                action_type TEXT NOT NULL,
                action_label TEXT,
                previous_active_plan_id TEXT,
                previous_active_plan_json TEXT,
                created_plan_id TEXT,
                created_status TEXT,
                operator_uid TEXT,
                created_at TEXT,
                restored_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tp_backups_user ON training_plan_backups(user_id, created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tp_backups_batch ON training_plan_backups(batch_id, created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tp_backups_club ON training_plan_backups(club_id, created_at DESC)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_notifications (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                activity_id TEXT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                type TEXT DEFAULT 'coach_critique',
                wechat_sent INTEGER DEFAULT 0,
                wechat_errmsg TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TEXT,
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sys_notif_user ON system_notifications(user_id, created_at DESC)")

        # Dynamic migration for existing profiles table
        cursor.execute("PRAGMA table_info(profiles)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if "coros_connected" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN coros_connected BOOLEAN DEFAULT 0")
        if "coros_account" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN coros_account TEXT")
        if "coros_encrypted_password" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN coros_encrypted_password TEXT")
        if "coros_domain" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN coros_domain TEXT DEFAULT 'teamcnapi.coros.com'")
        if "coros_last_sync_at" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN coros_last_sync_at TEXT")
        if "vo2max" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN vo2max REAL")
        if "date_of_birth" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN date_of_birth TEXT")
        if "id_card" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN id_card TEXT")
        if "real_name" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN real_name TEXT")
        if "wechat_unionid" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN wechat_unionid TEXT")
        if "apple_user_id" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN apple_user_id TEXT")
        if "apple_watch_connected" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN apple_watch_connected BOOLEAN DEFAULT 0")
        if "apple_watch_last_sync_at" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN apple_watch_last_sync_at TEXT")
        if "huawei_connected" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN huawei_connected BOOLEAN DEFAULT 0")
        if "huawei_account" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN huawei_account TEXT")
        if "huawei_last_sync_at" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN huawei_last_sync_at TEXT")
        if "suunto_connected" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN suunto_connected BOOLEAN DEFAULT 0")
        if "suunto_account" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN suunto_account TEXT")
        if "suunto_last_sync_at" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN suunto_last_sync_at TEXT")
        if "updated_at" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN updated_at TEXT")
        if "hide_gps_route" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN hide_gps_route BOOLEAN DEFAULT 0")
        if "hide_biometrics" not in existing_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN hide_biometrics BOOLEAN DEFAULT 0")

        # Mentorship relationships table (1-on-1 per mentee, max 3 mentees per mentor, cross-club within same org)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mentor_relationships (
                id TEXT PRIMARY KEY,
                org_id TEXT,
                club_id TEXT,
                mentor_id TEXT NOT NULL,
                mentee_id TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                created_by TEXT,
                FOREIGN KEY(mentor_id) REFERENCES profiles(id),
                FOREIGN KEY(mentee_id) REFERENCES profiles(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mentor_rel_mentor ON mentor_relationships(mentor_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mentor_rel_mentee ON mentor_relationships(mentee_id, status)")

        # Dynamic migration for organizations table
        cursor.execute("PRAGMA table_info(organizations)")
        org_cols = {row[1] for row in cursor.fetchall()}
        if "join_mode" not in org_cols:
            cursor.execute("ALTER TABLE organizations ADD COLUMN join_mode TEXT DEFAULT 'invite'")

        # Dynamic migration for organization_members table
        cursor.execute("PRAGMA table_info(organization_members)")
        org_mem_cols = {row[1] for row in cursor.fetchall()}
        if "id_card" not in org_mem_cols:
            cursor.execute("ALTER TABLE organization_members ADD COLUMN id_card TEXT")
        if "extra_data" not in org_mem_cols:
            cursor.execute("ALTER TABLE organization_members ADD COLUMN extra_data TEXT")

        # Dynamic migration for clubs table
        cursor.execute("PRAGMA table_info(clubs)")
        club_cols = {row[1] for row in cursor.fetchall()}
        if "org_id" not in club_cols:
            cursor.execute("ALTER TABLE clubs ADD COLUMN org_id TEXT")
        if "join_mode" not in club_cols:
            cursor.execute("ALTER TABLE clubs ADD COLUMN join_mode TEXT DEFAULT 'free'")
        if "status" not in club_cols:
            cursor.execute("ALTER TABLE clubs ADD COLUMN status TEXT DEFAULT 'active'")

        # Dynamic migration for club_memberships table (persistent training_group per member)
        cursor.execute("PRAGMA table_info(club_memberships)")
        cm_cols = {row[1] for row in cursor.fetchall()}
        if "training_group" not in cm_cols:
            cursor.execute("ALTER TABLE club_memberships ADD COLUMN training_group TEXT DEFAULT NULL")

        # Dynamic migration for club_events table & club_event_participants
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS club_event_participants (
                id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                club_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                status TEXT DEFAULT 'joined',
                UNIQUE(event_id, user_id),
                FOREIGN KEY(event_id) REFERENCES club_events(id),
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)

        cursor.execute("PRAGMA table_info(club_events)")
        event_cols = {row[1] for row in cursor.fetchall()}
        if "meet_time" not in event_cols:
            cursor.execute("ALTER TABLE club_events ADD COLUMN meet_time TEXT")
        if "location" not in event_cols:
            cursor.execute("ALTER TABLE club_events ADD COLUMN location TEXT")
        if "location_detail" not in event_cols:
            cursor.execute("ALTER TABLE club_events ADD COLUMN location_detail TEXT")
        if "latitude" not in event_cols:
            cursor.execute("ALTER TABLE club_events ADD COLUMN latitude REAL")
        if "longitude" not in event_cols:
            cursor.execute("ALTER TABLE club_events ADD COLUMN longitude REAL")
        if "cover_image" not in event_cols:
            cursor.execute("ALTER TABLE club_events ADD COLUMN cover_image TEXT")
        if "pace_requirement" not in event_cols:
            cursor.execute("ALTER TABLE club_events ADD COLUMN pace_requirement TEXT")
        if "creator_id" not in event_cols:
            cursor.execute("ALTER TABLE club_events ADD COLUMN creator_id TEXT")
        if "status" not in event_cols:
            cursor.execute("ALTER TABLE club_events ADD COLUMN status TEXT DEFAULT 'upcoming'")
        if "max_participants" not in event_cols:
            cursor.execute("ALTER TABLE club_events ADD COLUMN max_participants INTEGER DEFAULT 0")
        if "repeat_rule" not in event_cols:
            cursor.execute("ALTER TABLE club_events ADD COLUMN repeat_rule TEXT DEFAULT 'none'")
        if "repeat_group_id" not in event_cols:
            cursor.execute("ALTER TABLE club_events ADD COLUMN repeat_group_id TEXT DEFAULT NULL")
        if "visibility_mode" not in event_cols:
            cursor.execute("ALTER TABLE club_events ADD COLUMN visibility_mode TEXT DEFAULT 'registered_only'")
        if "recap_note" not in event_cols:
            cursor.execute("ALTER TABLE club_events ADD COLUMN recap_note TEXT DEFAULT ''")

        cursor.execute("PRAGMA table_info(club_event_participants)")
        ep_cols = {row[1] for row in cursor.fetchall()}
        if "pace_group" not in ep_cols:
            cursor.execute("ALTER TABLE club_event_participants ADD COLUMN pace_group TEXT DEFAULT ''")
        if "runner_role" not in ep_cols:
            cursor.execute("ALTER TABLE club_event_participants ADD COLUMN runner_role TEXT DEFAULT 'member'")
        if "checkin_note" not in ep_cols:
            cursor.execute("ALTER TABLE club_event_participants ADD COLUMN checkin_note TEXT DEFAULT ''")
        if "manual_distance_km" not in ep_cols:
            cursor.execute("ALTER TABLE club_event_participants ADD COLUMN manual_distance_km REAL DEFAULT NULL")
        if "manual_pace_str" not in ep_cols:
            cursor.execute("ALTER TABLE club_event_participants ADD COLUMN manual_pace_str TEXT DEFAULT NULL")
        if "manual_duration_str" not in ep_cols:
            cursor.execute("ALTER TABLE club_event_participants ADD COLUMN manual_duration_str TEXT DEFAULT NULL")
        if "activity_id" not in ep_cols:
            cursor.execute("ALTER TABLE club_event_participants ADD COLUMN activity_id TEXT DEFAULT NULL")
        if "likes_count" not in ep_cols:
            cursor.execute("ALTER TABLE club_event_participants ADD COLUMN likes_count INTEGER DEFAULT 0")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS club_event_comments (
                id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                club_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        cursor.execute("PRAGMA table_info(profiles)")
        p_cols = {row[1] for row in cursor.fetchall()}
        if "onboarding_completed" not in p_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0")
        if "is_solo_runner" not in p_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN is_solo_runner BOOLEAN DEFAULT 0")
        if "device_skipped" not in p_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN device_skipped BOOLEAN DEFAULT 0")
        if "history_skipped" not in p_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN history_skipped BOOLEAN DEFAULT 0")
        if "invited_by" not in p_cols:
            cursor.execute("ALTER TABLE profiles ADD COLUMN invited_by TEXT")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_referrals (
                id TEXT PRIMARY KEY,
                inviter_uid TEXT NOT NULL,
                invitee_uid TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                FOREIGN KEY(inviter_uid) REFERENCES profiles(id),
                FOREIGN KEY(invitee_uid) REFERENCES profiles(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_inviter ON user_referrals(inviter_uid, created_at DESC)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                display_name TEXT,
                category TEXT DEFAULT 'general',
                content TEXT NOT NULL,
                contact_info TEXT,
                diagnostic_context TEXT,
                status TEXT DEFAULT 'open',
                admin_reply TEXT,
                replied_at TEXT,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_user ON support_tickets(user_id, created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status, created_at DESC)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS miniapp_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                client_uuid TEXT,
                scene INTEGER,
                scene_label TEXT,
                entry_page TEXT,
                exit_page TEXT,
                inviter_uid TEXT,
                device_model TEXT,
                platform TEXT,
                app_version TEXT,
                started_at TEXT NOT NULL,
                last_event_at TEXT NOT NULL,
                ended_at TEXT,
                duration_ms INTEGER DEFAULT 0,
                page_count INTEGER DEFAULT 0,
                click_count INTEGER DEFAULT 0,
                max_scroll_pct INTEGER DEFAULT 0,
                had_error INTEGER DEFAULT 0
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_miniapp_sessions_started ON miniapp_sessions(started_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_miniapp_sessions_user ON miniapp_sessions(user_id, started_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_miniapp_sessions_client ON miniapp_sessions(client_uuid, started_at DESC)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS miniapp_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                event_id TEXT,
                user_id TEXT,
                client_uuid TEXT,
                event_type TEXT NOT NULL,
                event_name TEXT NOT NULL,
                event_label TEXT,
                page_path TEXT,
                page_title TEXT,
                stay_ms INTEGER DEFAULT 0,
                scroll_pct INTEGER DEFAULT NULL,
                props_json TEXT,
                client_ts INTEGER,
                created_at TEXT NOT NULL
            )
        """)
        try:
            cursor.execute("ALTER TABLE miniapp_events ADD COLUMN event_id TEXT")
        except Exception:
            pass
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_miniapp_events_dedup "
            "ON miniapp_events(session_id, event_id) WHERE event_id IS NOT NULL"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_miniapp_events_session ON miniapp_events(session_id, client_ts ASC, id ASC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_miniapp_events_user ON miniapp_events(user_id, created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_miniapp_events_type ON miniapp_events(event_type, created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_miniapp_events_page ON miniapp_events(page_path, created_at DESC)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_activities_user_start "
            "ON activities(user_id, start_time DESC, sport_type, exclude_mode, distance_meters)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_activity_comments_act "
            "ON activity_comments(activity_id, created_at ASC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_daily_health_user_date "
            "ON daily_health(user_id, date DESC)"
        )

        # Phase 1: Multi-platform identity mapping & Web WeChat Mini-Program QR login sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_identities (
                provider TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                bound_at TEXT NOT NULL,
                PRIMARY KEY (provider, provider_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_identities_uid ON user_identities(user_id)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS web_qr_login_sessions (
                scene_id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'pending',
                user_id TEXT,
                display_name TEXT,
                avatar_url TEXT,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                scanned_at INTEGER,
                confirmed_at INTEGER
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_web_qr_expires ON web_qr_login_sessions(expires_at)")

        # Phase 1: Hot secondary indexes across core lookup tables
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_profiles_openid ON profiles(wechat_openid)",
            "CREATE INDEX IF NOT EXISTS idx_profiles_unionid ON profiles(wechat_unionid)",
            "CREATE INDEX IF NOT EXISTS idx_profiles_garmin ON profiles(garmin_email)",
            "CREATE INDEX IF NOT EXISTS idx_profiles_coros ON profiles(coros_account)",
            "CREATE INDEX IF NOT EXISTS idx_profiles_email ON profiles(email)",
            "CREATE INDEX IF NOT EXISTS idx_club_memberships_user ON club_memberships(user_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_club_memberships_club ON club_memberships(club_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_org_members_user ON organization_members(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_training_plans_user ON training_plans(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_training_plan_backups_user ON training_plan_backups(user_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_race_plans_user ON race_plans(user_id, race_date)",
        ]:
            try:
                cursor.execute(idx_sql)
            except Exception:
                pass

        # Phase 2: Cold/hot separation — migrate inline heavy gps_track_data blobs to activity_streams
        try:
            cursor.execute(
                "SELECT id, user_id, gps_track_data FROM activities WHERE gps_track_data IS NOT NULL AND gps_track_data != ''"
            )
            inline_stream_rows = cursor.fetchall()
            if inline_stream_rows:
                now_mig_iso = datetime.utcnow().isoformat() + "Z"
                for s_row in inline_stream_rows:
                    a_id, a_uid, raw_gps = s_row[0], s_row[1], s_row[2]
                    slim_preview = _build_slim_route_preview(raw_gps)
                    preview_str = json.dumps(slim_preview, ensure_ascii=False) if slim_preview else None
                    has_pts = 1 if (slim_preview and slim_preview.get("points")) else 0
                    cursor.execute(
                        """
                        INSERT INTO activity_streams (activity_id, user_id, gps_track_data, updated_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(activity_id) DO UPDATE SET
                            gps_track_data = COALESCE(activity_streams.gps_track_data, excluded.gps_track_data),
                            user_id = COALESCE(excluded.user_id, activity_streams.user_id),
                            updated_at = excluded.updated_at
                        """,
                        (a_id, a_uid, raw_gps, now_mig_iso),
                    )
                    cursor.execute(
                        "UPDATE activities SET route_preview_json = COALESCE(?, route_preview_json), has_gps_track = ?, gps_track_data = NULL WHERE id = ?",
                        (preview_str, has_pts, a_id),
                    )
        except Exception as mig_err:
            logger.warning(f"[init_db] activity_streams migration warning: {mig_err}")

        # Seed default Fudan Gobi Organization if none exists
        cursor.execute("SELECT COUNT(*) FROM organizations WHERE id = 'org_fudan_gobi'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT OR IGNORE INTO organizations (id, name, logo_url, description, city, invite_code, owner_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "org_fudan_gobi",
                "复旦戈",
                "https://rgm.vanpower.net/api/avatars/rgm-logo.png",
                "复旦大学戈壁挑战赛大群体 · 汇聚商学院EMBA/MBA及泛复旦戈友，下设各个戈友跑团与训练营。",
                "上海",
                "FDGOBI",
                "u_df65d9a588c9",
                datetime.utcnow().isoformat() + "Z"
            ))

        # Seed default field rules for organizations if settings or field_rules missing or missing gobi_experience
        cursor.execute("SELECT id, settings FROM organizations")
        for org_row in cursor.fetchall():
            oid = org_row[0]
            settings_str = org_row[1]
            s_dict = {}
            if settings_str:
                try:
                    s_dict = json.loads(settings_str)
                except Exception:
                    s_dict = {}
            if not isinstance(s_dict, dict) or "field_rules" not in s_dict:
                if not isinstance(s_dict, dict):
                    s_dict = {}
                s_dict["field_rules"] = copy.deepcopy(DEFAULT_ORG_FIELD_RULES)
                cursor.execute("UPDATE organizations SET settings = ? WHERE id = ?", (json.dumps(s_dict, ensure_ascii=False), oid))
            else:
                fr_keys = {r.get("field") for r in s_dict["field_rules"]}
                if "gobi_experience" not in fr_keys:
                    s_dict["field_rules"].insert(4, {"field": "gobi_experience", "label": "戈壁经历(新戈/戈1-戈21)", "required": False, "type": "select"})
                    cursor.execute("UPDATE organizations SET settings = ? WHERE id = ?", (json.dumps(s_dict, ensure_ascii=False), oid))

        # Associate any club named like '复旦戈' or '闵文' to org_fudan_gobi
        cursor.execute("UPDATE clubs SET org_id = 'org_fudan_gobi' WHERE (name LIKE '%复旦戈%' OR name LIKE '%闵文%') AND (org_id IS NULL OR org_id = '')")

        # Seed default sub-club for org_fudan_gobi if none exists
        cursor.execute("SELECT COUNT(*) FROM clubs WHERE org_id = 'org_fudan_gobi'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT OR IGNORE INTO clubs (id, name, logo_url, description, city, invite_code, owner_id, org_id, join_mode, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'free', ?)
            """, (
                "club_fudan_gobi_main",
                "复旦戈闵文跑团",
                "https://rgm.vanpower.net/api/avatars/rgm-logo.png",
                "复旦戈闵文跑团 · 汇聚复旦戈友与闵文精英跑者，定期开展长距离拉练与马拉松科学耐力备战。",
                "上海",
                "FD8888",
                "u_df65d9a588c9",
                "org_fudan_gobi",
                datetime.utcnow().isoformat() + "Z"
            ))

        # Seed default flagship club if none exists
        cursor.execute("SELECT COUNT(*) FROM clubs")
        if cursor.fetchone()[0] == 0:
            default_club_id = "club_rgm_flagship"
            cursor.execute("""
                INSERT OR IGNORE INTO clubs (id, name, logo_url, description, city, invite_code, owner_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                default_club_id,
                "RGM先锋跑团",
                "https://rgm.vanpower.net/api/avatars/rgm-logo.png",
                "基于科学耐力训练与 Renato Canova 哲学的精英跑者联盟，追求 PB 突破与健康长久奔跑。",
                "上海",
                "RGM888",
                "u_df65d9a588c9",
                datetime.utcnow().isoformat() + "Z"
            ))

            cursor.execute("""
                INSERT OR IGNORE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                f"{default_club_id}_u_df65d9a588c9",
                default_club_id,
                "u_df65d9a588c9",
                "owner",
                "active",
                datetime.utcnow().isoformat() + "Z",
                1
            ))

            # Seed demo club event
            cursor.execute("""
                INSERT OR IGNORE INTO club_events (id, club_id, title, event_type, start_date, end_date, target_km, rules, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "event_sept_200k",
                default_club_id,
                "9月百团大战 · 200km 破风进阶挑战",
                "distance_challenge",
                "2026-09-01",
                "2026-09-30",
                200.0,
                "单月累计完成 200km，且配速在 4:00~7:30 之间即视为挑战成功，解锁完赛电子勋章与专属证书。",
                get_beijing_iso()
            ))

        # Normalize legacy UTC ('...Z' / '+00:00') social/event/notification timestamps to China Standard Time (+08:00)
        for _tbl, _col in (
            ("activity_comments", "created_at"),
            ("activity_likes", "created_at"),
            ("club_event_comments", "created_at"),
            ("system_notifications", "created_at"),
            ("support_tickets", "created_at"),
            ("support_tickets", "replied_at"),
            ("training_plan_backups", "created_at"),
        ):
            try:
                cursor.execute(
                    f"SELECT id, {_col} FROM {_tbl} WHERE {_col} LIKE '%Z' OR {_col} LIKE '%+00:00'"
                )
                _z_rows = cursor.fetchall()
                if _z_rows:
                    cursor.executemany(
                        f"UPDATE {_tbl} SET {_col} = ? WHERE id = ?",
                        [(to_beijing_iso(r[1]), r[0]) for r in _z_rows],
                    )
            except Exception:
                pass

        conn.commit()

init_db()

RUNNING_SPORT_TYPES = (
    "Run",
    "running",
    "TrailRun",
    "Trail Run",
    "trail_running",
    "treadmill_running",
    "track_running",
    "street_running",
    "obstacle_run",
)

RUNNING_SQL_FILTER = (
    "(LOWER(sport_type) IN ('run', 'running', 'trailrun', 'trail run', "
    "'trail_running', 'treadmill_running', 'track_running', 'street_running', 'obstacle_run') "
    "AND COALESCE(exclude_mode, 'normal') != 'excluded')"
)

class LocalStore:
    RUNNING_SPORT_TYPES = RUNNING_SPORT_TYPES
    RUNNING_SQL_FILTER = RUNNING_SQL_FILTER
    SUPER_ADMIN_UIDS = {"admin", "super_admin", "u_df65d9a588c9", "u_wx_0f769b6cfb"}

    @staticmethod
    def is_running_activity(sport_type: Optional[str]) -> bool:
        """Determines if an activity's sport_type is running or trail running (eligible for mileage)."""
        if not sport_type:
            return False
        st = str(sport_type).strip().lower()
        return st in {
            "run",
            "running",
            "trailrun",
            "trail run",
            "trail_running",
            "treadmill_running",
            "track_running",
            "street_running",
            "obstacle_run",
        }

    @staticmethod
    def is_trail_activity(act_or_sport_type: Any, name: Optional[str] = None) -> bool:
        """Determines if an activity is a trail running activity based on sport_type or activity name."""
        if isinstance(act_or_sport_type, dict):
            st = str(act_or_sport_type.get("sport_type") or "").strip().lower()
            act_name = str(act_or_sport_type.get("name") or "").strip()
        else:
            st = str(act_or_sport_type or "").strip().lower()
            act_name = str(name or "").strip()
        if st in {"trailrun", "trail run", "trail_running", "obstacle_run"} or "trail" in st or "越野" in st:
            return True
        name_lower = act_name.lower()
        if "越野" in act_name or "trail" in name_lower:
            return True
        return False
    @staticmethod
    def resolve_user_id(uid: str) -> str:
        """Resolves canonical user_id from profiles or merged user_identities."""
        if not uid:
            return uid
        if uid in ("u_wx_ac848a8f47", "u_wx_a9e9067fe2", "u_wx_fc10855228", "u_wx_220959b918", "u_wx_12dda0f9c1", "u_wx_ff680df8b5"):
            return "u_df65d9a588c9"
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM profiles WHERE id = ? OR email = ? OR display_name = ?", (uid, uid, uid))
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
            try:
                cursor.execute(
                    "SELECT user_id FROM user_identities WHERE provider = 'merged_uid' AND provider_id = ?",
                    (uid,),
                )
                merged_row = cursor.fetchone()
                if merged_row and merged_row[0]:
                    return merged_row[0]
            except Exception:
                pass
        return uid

    @staticmethod
    def bind_user_identity(user_id: str, provider: str, provider_id: Optional[str]):
        """Idempotently records (provider, provider_id) -> user_id in user_identities."""
        if not user_id or not provider or not provider_id:
            return
        clean_pid = str(provider_id).strip()
        if not clean_pid:
            return
        now_iso = datetime.utcnow().isoformat() + "Z"
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO user_identities (provider, provider_id, user_id, bound_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(provider, provider_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    bound_at = excluded.bound_at
                """,
                (provider, clean_pid, user_id, now_iso),
            )
            conn.commit()

    @staticmethod
    def merge_user_profiles(
        source_uid: str,
        target_uid: str,
        profile_updates: Optional[Dict[str, Any]] = None,
        drop_transient_watch_activities: bool = False,
    ) -> str:
        """
        Atomically merges `source_uid` into `target_uid` inside a single BEGIN IMMEDIATE transaction,
        losslessly migrating club_memberships, organization_members, training_plans, race_plans,
        goals, activities, daily_health, referrals, mentorships, notifications, and user_identities.
        """
        if not source_uid or not target_uid or source_uid == target_uid:
            if target_uid and profile_updates:
                LocalStore.upsert_profile(target_uid, profile_updates)
            return target_uid

        src_profile = LocalStore.get_profile(source_uid) or {}
        tgt_profile = LocalStore.get_profile(target_uid) or {}
        merged_updates: Dict[str, Any] = dict(profile_updates or {})

        for carry_field in ("wechat_openid", "wechat_unionid", "apple_user_id", "invited_by", "avatar_url", "phone"):
            if carry_field not in merged_updates:
                src_val = src_profile.get(carry_field)
                tgt_val = tgt_profile.get(carry_field)
                if src_val and not tgt_val:
                    if carry_field == "wechat_openid" and str(src_val).startswith("wx_") and tgt_val:
                        continue
                    merged_updates[carry_field] = src_val

        now_iso = datetime.utcnow().isoformat() + "Z"
        role_rank = {"owner": 4, "coach": 3, "admin": 2, "member": 1}

        conn = sqlite3.connect(DB_PATH, isolation_level=None)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")

            if drop_transient_watch_activities:
                cursor.execute(
                    "DELETE FROM activity_streams WHERE user_id = ? AND (activity_id LIKE 'hk_%' OR activity_id LIKE 'aw_%' OR activity_id LIKE 'hw_%')",
                    (source_uid,),
                )
                cursor.execute(
                    "DELETE FROM activities WHERE user_id = ? AND (id LIKE 'hk_%' OR id LIKE 'aw_%' OR id LIKE 'hw_%')",
                    (source_uid,),
                )
            cursor.execute("UPDATE OR IGNORE activities SET user_id = ? WHERE user_id = ?", (target_uid, source_uid))
            cursor.execute("DELETE FROM activities WHERE user_id = ?", (source_uid,))
            cursor.execute("UPDATE OR IGNORE activity_streams SET user_id = ? WHERE user_id = ?", (target_uid, source_uid))
            cursor.execute("DELETE FROM activity_streams WHERE user_id = ?", (source_uid,))

            # Migrate daily_health rows whose composite id is '{uid}_{date}'
            cursor.execute("SELECT * FROM daily_health WHERE user_id = ?", (source_uid,))
            src_dh_rows = [dict(r) for r in cursor.fetchall()]
            for dh in src_dh_rows:
                d_str = dh.get("date")
                if not d_str:
                    continue
                new_dh_id = f"{target_uid}_{d_str}"
                cursor.execute("SELECT 1 FROM daily_health WHERE id = ?", (new_dh_id,))
                if not cursor.fetchone():
                    cursor.execute(
                        "UPDATE OR IGNORE daily_health SET id = ?, user_id = ? WHERE id = ?",
                        (new_dh_id, target_uid, dh["id"]),
                    )
            cursor.execute("DELETE FROM daily_health WHERE user_id = ?", (source_uid,))

            # Migrate club_memberships (preserving highest role if member of same club)
            cursor.execute("SELECT * FROM club_memberships WHERE user_id = ?", (source_uid,))
            src_memberships = [dict(r) for r in cursor.fetchall()]
            for sm in src_memberships:
                cid = sm["club_id"]
                cursor.execute(
                    "SELECT role, training_group FROM club_memberships WHERE club_id = ? AND user_id = ?",
                    (cid, target_uid),
                )
                tm = cursor.fetchone()
                if tm:
                    best_role = (
                        sm["role"]
                        if role_rank.get(sm.get("role") or "member", 1) > role_rank.get(tm["role"] or "member", 1)
                        else tm["role"]
                    )
                    t_grp = tm["training_group"] or sm.get("training_group")
                    cursor.execute(
                        "UPDATE club_memberships SET role = ?, training_group = ? WHERE club_id = ? AND user_id = ?",
                        (best_role, t_grp, cid, target_uid),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent, training_group)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            f"{cid}_{target_uid}",
                            cid,
                            target_uid,
                            sm.get("role") or "member",
                            sm.get("status") or "active",
                            sm.get("joined_at") or now_iso,
                            1 if sm.get("privacy_consent", 1) else 0,
                            sm.get("training_group"),
                        ),
                    )
            cursor.execute("DELETE FROM club_memberships WHERE user_id = ?", (source_uid,))
            cursor.execute("UPDATE clubs SET owner_id = ? WHERE owner_id = ?", (target_uid, source_uid))

            # Migrate organization_members
            cursor.execute("SELECT * FROM organization_members WHERE user_id = ?", (source_uid,))
            for om in [dict(r) for r in cursor.fetchall()]:
                oid = om["org_id"]
                cursor.execute("SELECT 1 FROM organization_members WHERE org_id = ? AND user_id = ?", (oid, target_uid))
                if not cursor.fetchone():
                    cursor.execute(
                        "UPDATE OR IGNORE organization_members SET user_id = ? WHERE org_id = ? AND user_id = ?",
                        (target_uid, oid, source_uid),
                    )
            cursor.execute("DELETE FROM organization_members WHERE user_id = ?", (source_uid,))
            cursor.execute("UPDATE organizations SET owner_id = ? WHERE owner_id = ?", (target_uid, source_uid))

            # Migrate training_plans, backups, race_plans, goals, referrals, mentorships, notifications, event signups
            cursor.execute("UPDATE training_plans SET user_id = ? WHERE user_id = ?", (target_uid, source_uid))
            cursor.execute("UPDATE training_plan_backups SET user_id = ? WHERE user_id = ?", (target_uid, source_uid))
            cursor.execute("UPDATE race_plans SET user_id = ? WHERE user_id = ?", (target_uid, source_uid))
            cursor.execute("SELECT 1 FROM goals WHERE user_id = ?", (target_uid,))
            if not cursor.fetchone():
                cursor.execute("UPDATE OR IGNORE goals SET user_id = ? WHERE user_id = ?", (target_uid, source_uid))
            cursor.execute("DELETE FROM goals WHERE user_id = ?", (source_uid,))

            cursor.execute("UPDATE OR IGNORE user_referrals SET invitee_uid = ? WHERE invitee_uid = ?", (target_uid, source_uid))
            cursor.execute("UPDATE user_referrals SET inviter_uid = ? WHERE inviter_uid = ?", (target_uid, source_uid))
            cursor.execute("DELETE FROM user_referrals WHERE invitee_uid = ?", (source_uid,))

            cursor.execute("UPDATE mentor_relationships SET mentor_id = ? WHERE mentor_id = ?", (target_uid, source_uid))
            cursor.execute("UPDATE mentor_relationships SET mentee_id = ? WHERE mentee_id = ?", (target_uid, source_uid))
            cursor.execute("UPDATE system_notifications SET user_id = ? WHERE user_id = ?", (target_uid, source_uid))
            cursor.execute("UPDATE OR IGNORE club_event_participants SET user_id = ? WHERE user_id = ?", (target_uid, source_uid))
            cursor.execute("DELETE FROM club_event_participants WHERE user_id = ?", (source_uid,))

            cursor.execute("UPDATE user_identities SET user_id = ? WHERE user_id = ?", (target_uid, source_uid))
            cursor.execute(
                """
                INSERT INTO user_identities (provider, provider_id, user_id, bound_at)
                VALUES ('merged_uid', ?, ?, ?)
                ON CONFLICT(provider, provider_id) DO UPDATE SET user_id = excluded.user_id, bound_at = excluded.bound_at
                """,
                (source_uid, target_uid, now_iso),
            )
            cursor.execute("DELETE FROM profiles WHERE id = ?", (source_uid,))
            cursor.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            conn.close()

        if merged_updates:
            LocalStore.upsert_profile(target_uid, merged_updates)
        return target_uid

    @staticmethod
    def create_web_qr_session(scene_id: str, ttl_seconds: int = 300) -> Dict[str, Any]:
        now_ts = int(time.time())
        exp_ts = now_ts + max(60, ttl_seconds)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM web_qr_login_sessions WHERE expires_at < ?", (now_ts - 600,))
            conn.execute(
                """
                INSERT OR REPLACE INTO web_qr_login_sessions
                (scene_id, status, user_id, display_name, avatar_url, created_at, expires_at, scanned_at, confirmed_at)
                VALUES (?, 'pending', NULL, NULL, NULL, ?, ?, NULL, NULL)
                """,
                (scene_id, now_ts, exp_ts),
            )
            conn.commit()
        return {"scene_id": scene_id, "status": "pending", "expires_at": exp_ts, "expires_in": exp_ts - now_ts}

    @staticmethod
    def get_web_qr_session(scene_id: str) -> Optional[Dict[str, Any]]:
        if not scene_id:
            return None
        now_ts = int(time.time())
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM web_qr_login_sessions WHERE scene_id = ?", (scene_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            if d["status"] in ("pending", "scanned") and int(d["expires_at"] or 0) < now_ts:
                conn.execute("UPDATE web_qr_login_sessions SET status = 'expired' WHERE scene_id = ?", (scene_id,))
                conn.commit()
                d["status"] = "expired"
            return d

    @staticmethod
    def mark_web_qr_scanned(scene_id: str, display_name: str = "", avatar_url: str = "") -> bool:
        sess = LocalStore.get_web_qr_session(scene_id)
        if not sess or sess["status"] not in ("pending", "scanned"):
            return False
        now_ts = int(time.time())
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                UPDATE web_qr_login_sessions
                SET status = 'scanned',
                    display_name = COALESCE(NULLIF(?, ''), display_name),
                    avatar_url = COALESCE(NULLIF(?, ''), avatar_url),
                    scanned_at = COALESCE(scanned_at, ?)
                WHERE scene_id = ? AND status IN ('pending', 'scanned')
                """,
                (display_name, avatar_url, now_ts, scene_id),
            )
            conn.commit()
        return True

    @staticmethod
    def confirm_web_qr_session(scene_id: str, user_id: str, display_name: str = "", avatar_url: str = "") -> bool:
        sess = LocalStore.get_web_qr_session(scene_id)
        if not sess or sess["status"] not in ("pending", "scanned"):
            return False
        canonical_uid = LocalStore.resolve_user_id(user_id)
        now_ts = int(time.time())
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                """
                UPDATE web_qr_login_sessions
                SET status = 'confirmed',
                    user_id = ?,
                    display_name = COALESCE(NULLIF(?, ''), display_name),
                    avatar_url = COALESCE(NULLIF(?, ''), avatar_url),
                    confirmed_at = ?
                WHERE scene_id = ? AND status IN ('pending', 'scanned') AND expires_at >= ?
                """,
                (canonical_uid, display_name, avatar_url, now_ts, scene_id, now_ts),
            )
            conn.commit()
            return cur.rowcount > 0

    @staticmethod
    def consume_web_qr_session(scene_id: str) -> Optional[Dict[str, Any]]:
        """Atomically consumes a confirmed Web QR login session so its token can only be claimed once."""
        now_ts = int(time.time())
        conn = sqlite3.connect(DB_PATH, isolation_level=None)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            row = cur.execute(
                "SELECT * FROM web_qr_login_sessions WHERE scene_id = ? AND status = 'confirmed' AND expires_at >= ?",
                (scene_id, now_ts - 60),
            ).fetchone()
            if not row:
                cur.execute("COMMIT")
                return None
            data = dict(row)
            cur.execute("UPDATE web_qr_login_sessions SET status = 'consumed' WHERE scene_id = ?", (scene_id,))
            cur.execute("COMMIT")
            return data
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            conn.close()

    @staticmethod
    def _decrypt_profile_dict(d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not d:
            return d
        res = dict(d)
        for flag in ("garmin_connected", "coros_connected", "apple_watch_connected", "huawei_connected", "suunto_connected"):
            if flag in res:
                res[flag] = bool(res.get(flag))
        for f in ["id_card", "date_of_birth", "phone", "real_name"]:
            if f in res and res[f]:
                res[f] = decrypt_pii(res[f])
        return res

    @staticmethod
    def get_profile(uid: str) -> Optional[Dict[str, Any]]:
        eff_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profiles WHERE id = ? OR email = ? OR display_name = ?", (eff_uid, eff_uid, eff_uid))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["garmin_connected"] = bool(d.get("garmin_connected"))
                d["coros_connected"] = bool(d.get("coros_connected"))
                res = LocalStore._decrypt_profile_dict(d)
                if not res:
                    return res

                # Check if organization_members has extra fields to enrich profile
                try:
                    cursor.execute("""
                        SELECT real_name, gender, date_of_birth, class_name, phone, id_card, extra_data 
                        FROM organization_members 
                        WHERE user_id = ? ORDER BY joined_at DESC LIMIT 1
                    """, (eff_uid,))
                    om_row = cursor.fetchone()
                    if om_row:
                        om = dict(om_row)
                        for pii_key in ("real_name", "date_of_birth", "phone", "id_card"):
                            if om.get(pii_key):
                                om[pii_key] = decrypt_pii(om[pii_key])
                        if not res.get("real_name") and om.get("real_name"):
                            res["real_name"] = om["real_name"]
                        if not res.get("date_of_birth") and om.get("date_of_birth"):
                            res["date_of_birth"] = om["date_of_birth"]
                        if (not res.get("gender") or res.get("gender") == "male") and om.get("gender"):
                            res["gender"] = om["gender"]
                        if not res.get("phone") and om.get("phone"):
                            res["phone"] = om["phone"]
                        if not res.get("id_card") and om.get("id_card"):
                            res["id_card"] = om["id_card"]
                        if not res.get("class_name") and om.get("class_name"):
                            res["class_name"] = om["class_name"]
                        if om.get("extra_data"):
                            try:
                                om_extra = json.loads(om["extra_data"])
                                for k in ["program", "class_detail", "gobi_experience", "emergency_contact", "clothing_size", "shoe_size", "health_declaration"]:
                                    if not res.get(k) and om_extra.get(k) is not None:
                                        res[k] = om_extra[k]
                                org_pb = (str(om_extra.get("marathon_pb") or om_extra.get("full_marathon_pb") or "")).strip()
                                if org_pb:
                                    res["org_marathon_pb"] = org_pb
                            except Exception:
                                pass
                except Exception:
                    pass

                return res
            return None

    @staticmethod
    def get_profile_by_openid(openid: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profiles WHERE wechat_openid = ?", (openid,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["garmin_connected"] = bool(d.get("garmin_connected"))
                return LocalStore._decrypt_profile_dict(d)
            return None

    @staticmethod
    def get_profile_by_unionid(unionid: str) -> Optional[Dict[str, Any]]:
        if not unionid:
            return None
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profiles WHERE wechat_unionid = ?", (unionid,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["garmin_connected"] = bool(d.get("garmin_connected"))
                return LocalStore._decrypt_profile_dict(d)
            return None

    @staticmethod
    def get_profile_by_apple_id(apple_user_id: str) -> Optional[Dict[str, Any]]:
        if not apple_user_id:
            return None
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profiles WHERE apple_user_id = ?", (apple_user_id,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["garmin_connected"] = bool(d.get("garmin_connected"))
                return LocalStore._decrypt_profile_dict(d)
            return None

    @staticmethod
    def get_profile_by_email(email: str) -> Optional[Dict[str, Any]]:
        if not email:
            return None
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            clean_email = email.strip().lower()
            cursor.execute("SELECT * FROM profiles WHERE LOWER(email) = ?", (clean_email,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["garmin_connected"] = bool(d.get("garmin_connected"))
                return LocalStore._decrypt_profile_dict(d)
            return None

    @staticmethod
    def get_profile_by_garmin_email(email: str) -> Optional[Dict[str, Any]]:
        if not email:
            return None
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            clean_email = email.strip().lower()
            cursor.execute("SELECT * FROM profiles WHERE LOWER(garmin_email) = ? OR LOWER(email) = ?", (clean_email, clean_email))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["garmin_connected"] = bool(d.get("garmin_connected"))
                return LocalStore._decrypt_profile_dict(d)
            return None

    @staticmethod
    def get_profile_by_coros_account(account: str) -> Optional[Dict[str, Any]]:
        if not account:
            return None
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            clean_acc = account.strip().lower()
            cursor.execute("SELECT * FROM profiles WHERE LOWER(coros_account) = ? OR LOWER(email) = ?", (clean_acc, clean_acc))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["coros_connected"] = bool(d.get("coros_connected"))
                return LocalStore._decrypt_profile_dict(d)
            return None

    @staticmethod
    def list_profiles(limit: int = 50) -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profiles ORDER BY created_at ASC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["garmin_connected"] = bool(d.get("garmin_connected"))
                result.append(LocalStore._decrypt_profile_dict(d))
            return result

    @staticmethod
    def delete_profile(uid: str):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM profiles WHERE id = ?", (uid,))
            cursor.execute("DELETE FROM club_memberships WHERE user_id = ?", (uid,))
            cursor.execute("DELETE FROM organization_members WHERE user_id = ?", (uid,))
            cursor.execute("DELETE FROM activity_streams WHERE user_id = ?", (uid,))
            conn.commit()

    @staticmethod
    def upsert_profile(uid: str, data: Dict[str, Any]):
        eff_uid = LocalStore.resolve_user_id(uid)
        data = dict(data)
        # Encrypt sensitive personal privacy fields before saving
        for pii in ["id_card", "date_of_birth", "phone", "real_name"]:
            if pii in data and data[pii] is not None:
                data[pii] = encrypt_pii(data[pii])

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            _safe_col_re = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
            safe_data = {k: v for k, v in data.items() if isinstance(k, str) and _safe_col_re.match(k)}

            cursor.execute("PRAGMA table_info(profiles)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            for col in safe_data.keys():
                if col != "id" and col not in existing_cols:
                    try:
                        cursor.execute(f"ALTER TABLE profiles ADD COLUMN {col} TEXT")
                        existing_cols.add(col)
                    except Exception:
                        pass

            cursor.execute("SELECT * FROM profiles WHERE id = ?", (eff_uid,))
            existing = cursor.fetchone()
            if existing:
                fields = []
                values = []
                for k, v in safe_data.items():
                    if k != "id" and k in existing_cols:
                        fields.append(f"{k} = ?")
                        values.append(v)
                if fields:
                    values.append(eff_uid)
                    cursor.execute(f"UPDATE profiles SET {', '.join(fields)} WHERE id = ?", values)
            else:
                safe_data["id"] = eff_uid
                if "created_at" not in safe_data:
                    safe_data["created_at"] = datetime.utcnow().isoformat() + "Z"
                valid_data = {k: v for k, v in safe_data.items() if k in existing_cols or k == "id"}
                cols = list(valid_data.keys())
                placeholders = ["?"] * len(cols)
                cursor.execute(f"INSERT INTO profiles ({', '.join(cols)}) VALUES ({', '.join(placeholders)})", list(valid_data.values()))
            conn.commit()

        # Synchronize relevant runner credentials to any organizations joined
        org_sync_keys = {"real_name", "gender", "date_of_birth", "phone", "id_card", "class_name",
                         "program", "class_detail", "gobi_experience", "emergency_contact",
                         "clothing_size", "shoe_size", "health_declaration"}
        if any(k in data for k in org_sync_keys):
            try:
                LocalStore.sync_profile_to_org_memberships(eff_uid, data)
            except Exception as e:
                logger.warning(f"Error auto-syncing profile to orgs for {eff_uid}: {e}")

    @staticmethod
    def sync_profile_to_org_memberships(uid: str, raw_data: Dict[str, Any]):
        eff_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT org_id FROM organization_members WHERE user_id = ?", (eff_uid,))
            rows = cursor.fetchall()
            for r in rows:
                oid = r["org_id"]
                try:
                    LocalStore.update_org_member_profile(oid, eff_uid, raw_data)
                except Exception as e:
                    logger.warning(f"Failed to sync profile update to org {oid} for user {eff_uid}: {e}")

    @staticmethod
    def save_activity_streams(
        activity_id: str,
        user_id: Optional[str] = None,
        gps_track_data: Any = None,
        laps_data: Any = None,
        splits_data: Any = None,
    ) -> None:
        """Persists full-resolution GPS stream in `activity_streams` and updates slim preview on `activities`."""
        if not activity_id:
            return
        gps_str: Optional[str] = None
        preview_str: Optional[str] = None
        has_pts: Optional[int] = None
        if gps_track_data is not None:
            gps_str = json.dumps(gps_track_data, ensure_ascii=False) if isinstance(gps_track_data, (dict, list)) else str(gps_track_data)
            slim_prev = _build_slim_route_preview(gps_track_data)
            preview_str = json.dumps(slim_prev, ensure_ascii=False) if slim_prev else None
            has_pts = 1 if (slim_prev and slim_prev.get("points")) else 0

        laps_str = json.dumps(laps_data, ensure_ascii=False) if isinstance(laps_data, (dict, list)) else laps_data
        splits_str = json.dumps(splits_data, ensure_ascii=False) if isinstance(splits_data, (dict, list)) else splits_data
        now_iso = datetime.utcnow().isoformat() + "Z"

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if not user_id:
                u_row = cursor.execute("SELECT user_id FROM activities WHERE id = ?", (activity_id,)).fetchone()
                if u_row:
                    user_id = u_row[0]
            if gps_str is not None:
                cursor.execute(
                    """
                    INSERT INTO activity_streams (activity_id, user_id, gps_track_data, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(activity_id) DO UPDATE SET
                        user_id = COALESCE(excluded.user_id, activity_streams.user_id),
                        gps_track_data = excluded.gps_track_data,
                        updated_at = excluded.updated_at
                    """,
                    (activity_id, user_id, gps_str, now_iso),
                )
            cursor.execute(
                """
                UPDATE activities
                SET gps_track_data = NULL,
                    route_preview_json = COALESCE(?, route_preview_json),
                    has_gps_track = COALESCE(?, has_gps_track),
                    laps_data = COALESCE(?, laps_data),
                    splits_data = COALESCE(?, splits_data)
                WHERE id = ?
                """,
                (preview_str, has_pts, laps_str, splits_str, activity_id),
            )
            conn.commit()

    @staticmethod
    def upsert_activity(act: Dict[str, Any], notify: bool = True, reconcile_plan: bool = True):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cols = [
                "id", "user_id", "name", "sport_type", "start_time", "distance_meters",
                "moving_time_seconds", "elapsed_time_seconds", "elevation_gain_meters",
                "average_heartrate", "max_heartrate", "average_cadence", "avg_pace_str",
                "calories", "aerobic_training_effect", "anaerobic_training_effect", "trimp",
                "ai_journal", "laps_data", "splits_data", "gps_track_data", "map_image_url",
                "exclude_mode", "segment_analysis_json", "route_preview_json", "has_gps_track"
            ]
            act_id = act.get("id")
            cursor.execute(
                """
                SELECT a.id, COALESCE(s.gps_track_data, a.gps_track_data), a.map_image_url, a.laps_data, a.splits_data,
                       a.exclude_mode, a.segment_analysis_json, a.ai_journal, a.route_preview_json, a.has_gps_track
                FROM activities a
                LEFT JOIN activity_streams s ON s.activity_id = a.id
                WHERE a.id = ?
                """,
                (act_id,),
            )
            existing_row = cursor.fetchone()
            is_new = existing_row is None

            incoming_gps = act.get("gps_track_data")
            preserved_gps = existing_row[1] if (not is_new and existing_row) else None

            if not is_new and existing_row:
                if not act.get("map_image_url") and existing_row[2]:
                    act["map_image_url"] = existing_row[2]
                if not act.get("laps_data") and existing_row[3]:
                    act["laps_data"] = existing_row[3]
                if not act.get("splits_data") and existing_row[4]:
                    act["splits_data"] = existing_row[4]
                if not act.get("exclude_mode") and existing_row[5]:
                    act["exclude_mode"] = existing_row[5]
                if not act.get("segment_analysis_json") and existing_row[6]:
                    act["segment_analysis_json"] = existing_row[6]
                if not act.get("ai_journal") and existing_row[7]:
                    act["ai_journal"] = existing_row[7]

            if not act.get("exclude_mode"):
                act["exclude_mode"] = "normal"

            # Ensure elevation_gain_meters is robustly captured from any common adapter key
            if act.get("elevation_gain_meters") is None:
                elev = act.get("total_elevation_gain")
                if elev is None:
                    elev = act.get("elevationGain")
                if elev is None:
                    elev = act.get("elevation_gain")
                if elev is not None:
                    try:
                        act["elevation_gain_meters"] = round(float(elev), 1)
                    except (ValueError, TypeError):
                        pass

            if not act.get("ai_journal") or not str(act.get("ai_journal")).strip():
                act["ai_journal"] = LocalStore.generate_canova_critique(act)

            # Cold/hot stream separation: store full GPS stream in `activity_streams`, slim preview in `activities`
            eff_gps = incoming_gps if incoming_gps else preserved_gps
            if incoming_gps:
                slim_prev = _build_slim_route_preview(incoming_gps)
                route_preview_str = json.dumps(slim_prev, ensure_ascii=False) if slim_prev else None
                has_gps_flag = 1 if (slim_prev and slim_prev.get("points")) else 0
                gps_stream_str = json.dumps(incoming_gps, ensure_ascii=False) if isinstance(incoming_gps, (dict, list)) else str(incoming_gps)
                cursor.execute(
                    """
                    INSERT INTO activity_streams (activity_id, user_id, gps_track_data, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(activity_id) DO UPDATE SET
                        user_id = COALESCE(excluded.user_id, activity_streams.user_id),
                        gps_track_data = excluded.gps_track_data,
                        updated_at = excluded.updated_at
                    """,
                    (act_id, act.get("user_id"), gps_stream_str, datetime.utcnow().isoformat() + "Z"),
                )
            elif not is_new and existing_row:
                route_preview_str = existing_row[8]
                has_gps_flag = int(existing_row[9] or 0)
                if not route_preview_str and preserved_gps:
                    slim_prev = _build_slim_route_preview(preserved_gps)
                    route_preview_str = json.dumps(slim_prev, ensure_ascii=False) if slim_prev else None
                    has_gps_flag = 1 if (slim_prev and slim_prev.get("points")) else 0
            else:
                route_preview_str = None
                has_gps_flag = 0

            row_map = dict(act)
            row_map["gps_track_data"] = None
            row_map["route_preview_json"] = route_preview_str
            row_map["has_gps_track"] = has_gps_flag

            row_data = []
            for col in cols:
                val = row_map.get(col)
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                row_data.append(val)
            placeholders = ["?"] * len(cols)
            cursor.execute(f"INSERT OR REPLACE INTO activities ({', '.join(cols)}) VALUES ({', '.join(placeholders)})", row_data)
            conn.commit()
            if eff_gps and not act.get("gps_track_data"):
                act["gps_track_data"] = route_preview_str or eff_gps

        # Trigger training plan auto-reconciliation if active plan exists
        if reconcile_plan:
            try:
                uid = act.get("user_id")
                if uid:
                    active_plan = LocalStore.get_user_active_training_plan(uid, reconcile=False)
                    if active_plan:
                        LocalStore.reconcile_training_plan_activities(active_plan, uid)
            except Exception as e:
                logger.warning(f"Plan reconciliation after upsert_activity skipped: {e}")

        # If this is a new activity and has Canova critique, dispatch push notification
        if notify and is_new and act.get("ai_journal") and act.get("user_id"):
            try:
                from utils.wechat import dispatch_canova_critique_push
                dispatch_canova_critique_push(
                    user_id=act["user_id"],
                    activity=act,
                    critique=act["ai_journal"]
                )
            except Exception as pe:
                logger.warning(f"Canova critique push notification failed: {pe}")

    @staticmethod
    def get_recent_activities(uid: str, limit: int = 15, include_splits: bool = True) -> List[Dict[str, Any]]:
        canonical_uid = LocalStore.resolve_user_id(uid)
        split_cols = ", laps_data, splits_data, segment_analysis_json" if include_splits else ""
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT id, user_id, name, sport_type, start_time, distance_meters,
                       moving_time_seconds, elapsed_time_seconds, elevation_gain_meters,
                       average_heartrate, max_heartrate, average_cadence, avg_pace_str,
                       calories, aerobic_training_effect, anaerobic_training_effect, trimp,
                       ai_journal, map_image_url, exclude_mode, has_gps_track,
                       COALESCE(route_preview_json, gps_track_data) AS gps_track_data{split_cols}
                FROM activities
                WHERE user_id = ? OR user_id = ?
                ORDER BY start_time DESC
                LIMIT ?
                """,
                (canonical_uid, uid, limit),
            )
            rows = [dict(r) for r in cursor.fetchall()]

        profile = LocalStore.get_profile(canonical_uid) or {}
        rest_hr = float(profile.get("resting_heart_rate") or 58.0)
        max_hr = float(profile.get("max_heart_rate") or 190.0)
        from utils.running_metrics import calculate_workout_effective_vdot

        for r in rows:
            r["exclude_mode"] = r.get("exclude_mode") or "normal"
            if r["exclude_mode"] == "normal" and LocalStore.is_running_activity(r.get("sport_type")):
                r["workout_effective_vdot"] = calculate_workout_effective_vdot(
                    distance_meters=float(r.get("distance_meters") or 0.0),
                    time_seconds=float(r.get("moving_time_seconds") or 0.0),
                    avg_hr=float(r.get("average_heartrate") or 0.0) if r.get("average_heartrate") else None,
                    rest_hr=rest_hr,
                    max_hr=max_hr,
                    elevation_gain_m=float(r.get("elevation_gain_meters") or 0.0),
                )
            else:
                r["workout_effective_vdot"] = None

            if not r.get("ai_journal") or not str(r["ai_journal"]).strip():
                r["ai_journal"] = LocalStore.generate_canova_critique(r)

        return rows

    @staticmethod
    def set_activity_exclude_mode(uid: str, activity_id: str, exclude_mode: str) -> Dict[str, Any]:
        """
        Updates an activity's exclude_mode:
        - 'normal': 正常计入跑量、负荷与等效 VDOT
        - 'ignore_vdot': 仅计跑量与负荷，不计入等效 VDOT（如私兔陪跑/休闲慢摇）
        - 'excluded': 忽略此记录（多表重复佩戴或心率异常，不计入跑量、排行榜与负荷）
        """
        valid_modes = {"normal", "ignore_vdot", "excluded"}
        mode = str(exclude_mode or "normal").strip().lower()
        if mode not in valid_modes:
            mode = "normal"

        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, user_id, name FROM activities WHERE id = ?", (activity_id,))
            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": "未找到该跑步记录"}
            owner_id = LocalStore.resolve_user_id(row["user_id"])
            if owner_id != canonical_uid and row["user_id"] != uid:
                return {"success": False, "error": "仅记录本人可修改统计状态"}
            cursor.execute("UPDATE activities SET exclude_mode = ? WHERE id = ?", (mode, activity_id))
            conn.commit()

        mode_labels = {
            "normal": "正常计入统计与等效 VDOT",
            "ignore_vdot": "陪跑/慢摇模式（计入跑量，不拉低等效 VDOT）",
            "excluded": "已忽略（不计入跑量、排行榜与体能负荷）",
        }
        return {
            "success": True,
            "activity_id": activity_id,
            "exclude_mode": mode,
            "label": mode_labels[mode],
            "message": f"已设为：{mode_labels[mode]}",
        }

    @staticmethod
    def get_activity_gps_track(activity_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.id, a.user_id, a.name, a.sport_type, a.start_time, a.distance_meters,
                       a.moving_time_seconds, a.elapsed_time_seconds, a.elevation_gain_meters,
                       a.avg_pace_str, a.average_heartrate, a.max_heartrate, a.average_cadence,
                       a.map_image_url,
                       COALESCE(s.gps_track_data, a.gps_track_data, a.route_preview_json) AS gps_track_data,
                       a.laps_data, a.splits_data,
                       a.segment_analysis_json, a.ai_journal
                FROM activities a
                LEFT JOIN activity_streams s ON s.activity_id = a.id
                WHERE a.id = ?
            """, (activity_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            for jcol in ("gps_track_data", "laps_data", "splits_data", "segment_analysis_json"):
                if res.get(jcol) and isinstance(res[jcol], str):
                    try:
                        res[jcol] = json.loads(res[jcol])
                    except Exception:
                        pass
            return res

    @staticmethod
    def resolve_activity_plan_and_preset_race(
        uid: str,
        act_date: str,
        dist_km: float,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Resolves (planned_day, preset_race) for a runner on act_date (YYYY-MM-DD).
        Strict rule: preset_race is returned ONLY if the runner has a preset race on act_date
        (in race_plans or as a race day in active/published training_plans) and dist_km meets
        the minimum distance threshold for that preset race.
        """
        if not uid or not act_date or len(act_date) < 10:
            return None, None

        canonical_uid = LocalStore.resolve_user_id(uid)
        planned_day: Optional[Dict[str, Any]] = None
        preset_race: Optional[Dict[str, Any]] = None

        def _min_dist_for_race(rtype: str, rname: str, ri_dist_val: float = 0.0) -> float:
            rt = (rtype or "").lower()
            rn = (rname or "").lower()
            if ri_dist_val > 0:
                return max(3.5, ri_dist_val * 0.65)
            if "全马" in rt or "full" in rt or rt == "marathon" or ("马拉松" in rn and "半" not in rn and not rt):
                return 30.0
            if "半马" in rt or "half" in rt or "半程" in rn or "半马" in rn:
                return 15.0
            if "10" in rt or "10k" in rn or "10公里" in rn:
                return 8.0
            if "5" in rt or "5k" in rn or "5公里" in rn:
                return 4.0
            if "trail" in rt or "越野" in rt or "越野" in rn:
                return 10.0
            return 4.5

        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # 1. Check user's preset race_plans on act_date
                cursor.execute(
                    """
                    SELECT id, name, race_type, race_date, target_time, race_info
                    FROM race_plans
                    WHERE (user_id = ? OR user_id = ?)
                      AND substr(race_date, 1, 10) = ?
                    ORDER BY priority ASC, created_at DESC
                    """,
                    (canonical_uid, uid, act_date[:10]),
                )
                for r in cursor.fetchall():
                    rdict = dict(r)
                    ri = {}
                    if rdict.get("race_info"):
                        try:
                            ri = json.loads(rdict["race_info"]) if isinstance(rdict["race_info"], str) else rdict["race_info"]
                        except Exception:
                            ri = {}
                    ri_dist = float((ri or {}).get("race_distance_km") or 0.0)
                    min_req = _min_dist_for_race(str(rdict.get("race_type") or ""), str(rdict.get("name") or ""), ri_dist)
                    if dist_km >= min_req:
                        preset_race = {
                            "id": rdict.get("id"),
                            "name": rdict.get("name") or "预设目标比赛",
                            "race_type": rdict.get("race_type") or "",
                            "race_date": act_date[:10],
                            "target_time": rdict.get("target_time") or "",
                            "source": "race_plans",
                        }
                        break

                # 2. Check active/published training_plans for scheduled workout or race day
                cursor.execute(
                    """
                    SELECT id, title, goal_type, target_race_id, target_race_name, target_date, status, schedule_data
                    FROM training_plans
                    WHERE (user_id = ? OR user_id = ?)
                      AND status IN ('active', 'published')
                    ORDER BY CASE WHEN status = 'active' THEN 0 ELSE 1 END, updated_at DESC
                    LIMIT 5
                    """,
                    (canonical_uid, uid),
                )
                for row in cursor.fetchall():
                    p_row = dict(row)
                    try:
                        sched = json.loads(p_row.get("schedule_data") or "{}")
                    except Exception:
                        sched = {}

                    matched_d = None
                    for w in sched.get("weeks") or []:
                        for d in w.get("days") or []:
                            if str(d.get("date") or "")[:10] == act_date[:10]:
                                matched_d = d
                                break
                        if matched_d:
                            break

                    if matched_d and planned_day is None:
                        planned_day = matched_d

                    if preset_race is None:
                        t_date = str(p_row.get("target_date") or "")[:10]
                        t_name = str(p_row.get("target_race_name") or p_row.get("title") or "").strip()
                        if matched_d and str(matched_d.get("workout_type") or "").lower() == "race":
                            d_target_km = float(matched_d.get("distance_km") or 0.0)
                            min_req = _min_dist_for_race("", t_name or str(matched_d.get("title") or ""), d_target_km)
                            if dist_km >= min_req:
                                preset_race = {
                                    "id": p_row.get("target_race_id") or p_row.get("id"),
                                    "name": t_name or str(matched_d.get("title") or "课表目标比赛"),
                                    "race_type": "全马" if d_target_km >= 38 else ("半马" if d_target_km >= 20 else ""),
                                    "race_date": act_date[:10],
                                    "target_time": str(sched.get("target_finish_time") or ""),
                                    "source": "training_plans",
                                }
                        elif t_date == act_date[:10] and p_row.get("goal_type") == "race_prep":
                            min_req = _min_dist_for_race("", t_name, 0.0)
                            if dist_km >= min_req:
                                preset_race = {
                                    "id": p_row.get("target_race_id") or p_row.get("id"),
                                    "name": t_name or "备赛目标赛事",
                                    "race_type": "全马" if dist_km >= 35 else ("半马" if dist_km >= 18 else ""),
                                    "race_date": act_date[:10],
                                    "target_time": str(sched.get("target_finish_time") or ""),
                                    "source": "training_plans",
                                }
        except Exception as e:
            logger.warning(f"resolve_activity_plan_and_preset_race failed for {uid} on {act_date}: {e}")

        return planned_day, preset_race

    @staticmethod
    def compute_and_cache_segment_analysis(
        activity_id: str,
        track_override: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Computes structured workout/preset-race segmentation & diagnosis for activity_id,
        persists segment_analysis_json (and updated ai_journal) in activities table, and returns it.
        """
        act_row = LocalStore.get_activity_gps_track(activity_id)
        if not act_row:
            return None
        if not LocalStore.is_running_activity(act_row.get("sport_type")):
            return None

        existing_seg = act_row.get("segment_analysis_json")
        if isinstance(existing_seg, dict) and existing_seg.get("mode") and not force:
            # Recompute if legacy planned_workout cache predates schema_version 2 discrepancy filter,
            # or if track_override brings newly fetched granular splits where previously none existed.
            needs_schema_upgrade = (
                existing_seg.get("mode") == "planned_workout" and existing_seg.get("schema_version") != 2
            )
            has_new_splits = bool(
                not existing_seg.get("has_granular_splits")
                and isinstance(track_override, dict)
                and (track_override.get("laps") or track_override.get("km_splits") or track_override.get("telemetry_series"))
            )
            if not needs_schema_upgrade and not has_new_splits:
                return existing_seg

        uid = str(act_row.get("user_id") or "")
        canonical_uid = LocalStore.resolve_user_id(uid) if uid else ""
        profile = LocalStore.get_profile(canonical_uid) if canonical_uid else {}
        profile = profile or {}

        rest_hr = float(profile.get("resting_heart_rate") or 58.0)
        max_hr = float(profile.get("max_heart_rate") or 190.0)
        hrr = max(40.0, max_hr - rest_hr)
        aerobic_ceiling = rest_hr + hrr * 0.75
        threshold_ceiling = rest_hr + hrr * 0.88

        dist_km = round(float(act_row.get("distance_meters") or 0.0) / 1000.0, 2)
        act_date = str(act_row.get("start_time") or "")[:10]
        planned_day, preset_race = LocalStore.resolve_activity_plan_and_preset_race(canonical_uid or uid, act_date, dist_km)

        eff_track = track_override if isinstance(track_override, dict) else (
            act_row.get("gps_track_data") if isinstance(act_row.get("gps_track_data"), dict) else None
        )

        from utils.workout_segmentation import analyze_activity_segments, parse_pace_str_to_sec

        seg_result = analyze_activity_segments(
            activity=act_row,
            track_data=eff_track,
            planned_day=planned_day,
            preset_race=preset_race,
            max_hr=max_hr,
            aerobic_ceiling=aerobic_ceiling,
            threshold_ceiling=threshold_ceiling,
        )

        # Build harmonized ai_journal critique for Club Feed & summary cards
        concise_base = str(seg_result.get("concise_critique") or "").strip()
        new_journal = concise_base
        if concise_base and seg_result.get("mode") != "race" and canonical_uid:
            try:
                v_meta = LocalStore.resolve_verified_runner_profile_and_pbs(
                    canonical_uid, profile=profile, query_activities=False
                )
                m_pb = v_meta.get("verified_mp_sec")
                h_pb = v_meta.get("verified_hp_sec")
                raw_years = profile.get("years_running")
                years = float(raw_years) if raw_years is not None else 1.0
                is_elite = bool(
                    (m_pb and m_pb <= 3 * 3600 + 5 * 60)
                    or (h_pb and h_pb <= 85 * 60 and (not m_pb or m_pb <= 3 * 3600 + 15 * 60))
                )
                is_beginner = (years <= 2 or (m_pb and m_pb > 4 * 3600) or (not m_pb and not h_pb)) and not is_elite
                if is_elite:
                    if "【精英专项进阶】" not in concise_base:
                        new_journal = f"{concise_base} ⚡【精英专项进阶】专项指标达成，紧扣配速收敛。"
                else:
                    p_str = str(act_row.get("avg_pace_str") or "5:30/km").replace("/km", "").strip() + "/km"
                    p_sec = parse_pace_str_to_sec(p_str) or 330
                    enc = LocalStore._build_runner_progress_encouragement(
                        activity=act_row,
                        dist_km=dist_km,
                        pace_str=p_str,
                        pace_seconds=p_sec,
                        avg_hr=act_row.get("average_heartrate"),
                        aerobic_ceiling=aerobic_ceiling,
                        is_beginner=is_beginner,
                    )
                    if "💡" in concise_base:
                        head, tail = concise_base.split("💡", 1)
                        new_journal = f"{head.strip()}{enc} 💡 {tail.strip()}"
                    else:
                        new_journal = f"{concise_base}{enc}"
            except Exception as je:
                logger.debug(f"Progress encouragement merge skipped: {je}")

        try:
            seg_json_str = json.dumps(seg_result, ensure_ascii=False)
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                if new_journal:
                    cursor.execute(
                        "UPDATE activities SET segment_analysis_json = ?, ai_journal = ? WHERE id = ?",
                        (seg_json_str, new_journal, activity_id),
                    )
                else:
                    cursor.execute(
                        "UPDATE activities SET segment_analysis_json = ? WHERE id = ?",
                        (seg_json_str, activity_id),
                    )
                conn.commit()
        except Exception as db_e:
            logger.warning(f"Failed saving segment_analysis_json for {activity_id}: {db_e}")

        if new_journal:
            seg_result["updated_ai_journal"] = new_journal
        return seg_result

    @staticmethod
    def get_training_load(uid: str, days: int = 90) -> Dict[str, Any]:
        """
        Calculates Banister impulse-response model metrics:
        - CTL (Fitness - 42d EWMA)
        - ATL (Fatigue - 7d EWMA)
        - TSB (Form = CTL - ATL)
        - ACWR (Acute:Chronic Workload Ratio)
        - Physiological status & injury risk warnings
        """
        canonical_uid = LocalStore.resolve_user_id(uid)
        today = get_beijing_today()
        start_date = today - timedelta(days=days)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT start_time, distance_meters, moving_time_seconds, average_heartrate, trimp, exclude_mode
                FROM activities
                WHERE (user_id = ? OR user_id = ?) AND start_time >= ?
                  AND COALESCE(exclude_mode, 'normal') != 'excluded'
                ORDER BY start_time ASC
            """, (canonical_uid, uid, start_date.isoformat()))
            rows = [dict(r) for r in cursor.fetchall()]

        profile = LocalStore.get_profile(uid) or {}
        max_hr = float(profile.get("max_heart_rate") or 190)
        rest_hr = float(profile.get("resting_heart_rate") or 56)
        gender = str(profile.get("gender") or "male")

        from utils.running_metrics import calculate_trimp, compute_ctl_atl_tsb

        # Group TRIMP by YYYY-MM-DD
        daily_map: Dict[str, float] = {}
        for r in rows:
            st = str(r.get("start_time") or "")[:10]
            if not st:
                continue
            trimp = float(r.get("trimp") or 0)
            if trimp <= 0:
                dur_min = float(r.get("moving_time_seconds") or 0) / 60.0
                avg_hr = float(r.get("average_heartrate") or 0)
                if dur_min > 0 and avg_hr > rest_hr:
                    trimp = calculate_trimp(dur_min, avg_hr, rest_hr, max_hr, gender)
            daily_map[st] = daily_map.get(st, 0.0) + trimp

        # Build day-by-day continuous series (decay happens on rest days with 0 TRIMP)
        cur_date = start_date
        daily_series = []
        while cur_date <= today:
            d_str = cur_date.isoformat()
            daily_series.append((d_str, daily_map.get(d_str, 0.0)))
            cur_date += timedelta(days=1)

        tsb_history = compute_ctl_atl_tsb(daily_series)
        if not tsb_history:
            return {
                "ctl": 0.0,
                "atl": 0.0,
                "tsb": 0.0,
                "acwr": 0.0,
                "status": "初始基线建立中",
                "status_code": "initial",
                "risk_warning": None,
                "history_last_14d": []
            }

        latest = tsb_history[-1]
        ctl = latest["ctl"]
        atl = latest["atl"]
        tsb = latest["tsb"]
        acwr = round(atl / max(1.0, ctl), 2)

        if tsb > 15:
            status = "巅峰就绪 (Peak Form)"
            status_code = "fresh"
            risk = None
        elif tsb >= -10:
            status = "平衡稳健 (Neutral Form)"
            status_code = "neutral"
            risk = None
        elif tsb >= -30:
            status = "最佳吸收 (Productive Training)"
            status_code = "optimal"
            risk = None
        elif tsb >= -45:
            status = "高度疲劳 (High Fatigue)"
            status_code = "fatigued"
            risk = "近期急性疲劳 (ATL) 累积过快，注意控制高强度课密度，保证水分、电解质与夜间充足睡眠。"
        else:
            status = "过度负荷 / 伤病高危预警 (High Injury Risk)"
            status_code = "danger"
            risk = "⚠️ 警报：短期负荷已达机能红线 (TSB < -45)，肌肉与韧带过度承压，强烈建议安排 48~72 小时减量慢跑或彻底休整，严禁盲目执行大强度刺激！"

        return {
            "ctl": ctl,
            "atl": atl,
            "tsb": tsb,
            "acwr": acwr,
            "status": status,
            "status_code": status_code,
            "risk_warning": risk,
            "history_last_14d": tsb_history[-14:]
        }


    @staticmethod
    def get_beijing_today() -> date:
        return get_beijing_today()

    @staticmethod
    def get_beijing_now() -> datetime:
        return get_beijing_now()

    @staticmethod
    def get_month_distance_meters(uid: str, month_start: str) -> float:
        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT SUM(distance_meters) FROM activities WHERE user_id = ? AND start_time >= ? AND {RUNNING_SQL_FILTER}", (canonical_uid, month_start))
            res = cursor.fetchone()
            return float(res[0]) if res and res[0] is not None else 0.0

    @staticmethod
    def get_month_activities(uid: str, year: Optional[int] = None, month: Optional[int] = None) -> List[Dict[str, Any]]:
        canonical_uid = LocalStore.resolve_user_id(uid)
        today = get_beijing_today()
        target_year = year or today.year
        target_month = month or today.month

        start_date = f"{target_year:04d}-{target_month:02d}-01"
        if target_month == 12:
            end_date = f"{target_year + 1:04d}-01-01"
        else:
            end_date = f"{target_year:04d}-{target_month + 1:02d}-01"

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT id, user_id, name, sport_type, start_time, distance_meters,
                       moving_time_seconds, elapsed_time_seconds, elevation_gain_meters,
                       average_heartrate, max_heartrate, average_cadence, avg_pace_str,
                       calories, aerobic_training_effect, anaerobic_training_effect, trimp,
                       ai_journal, map_image_url, exclude_mode, has_gps_track,
                       COALESCE(route_preview_json, gps_track_data) AS gps_track_data
                FROM activities 
                WHERE user_id = ? AND start_time >= ? AND start_time < ? 
                  AND {RUNNING_SQL_FILTER}
                ORDER BY start_time DESC
            """, (canonical_uid, start_date, end_date))
            rows = [dict(r) for r in cursor.fetchall()]

        profile = LocalStore.get_profile(canonical_uid) or {}
        rest_hr = float(profile.get("resting_heart_rate") or 58.0)
        max_hr = float(profile.get("max_heart_rate") or 190.0)
        from utils.running_metrics import calculate_workout_effective_vdot

        # Generate Canova critiques in memory (no write-on-GET) and workout_effective_vdot
        for r in rows:
            r["exclude_mode"] = r.get("exclude_mode") or "normal"
            if r["exclude_mode"] == "normal" and LocalStore.is_running_activity(r.get("sport_type")):
                r["workout_effective_vdot"] = calculate_workout_effective_vdot(
                    distance_meters=float(r.get("distance_meters") or 0.0),
                    time_seconds=float(r.get("moving_time_seconds") or 0.0),
                    avg_hr=float(r.get("average_heartrate") or 0.0) if r.get("average_heartrate") else None,
                    rest_hr=rest_hr,
                    max_hr=max_hr,
                    elevation_gain_m=float(r.get("elevation_gain_meters") or 0.0),
                )
            else:
                r["workout_effective_vdot"] = None

            if not r.get("ai_journal") or not str(r["ai_journal"]).strip():
                try:
                    r["ai_journal"] = LocalStore.generate_canova_critique(r)
                except Exception as ex:
                    logger.warning(f"Generate critique in get_month_activities failed: {ex}")

        return rows

    @staticmethod
    def get_weekly_stats(uid: str, target_km: Optional[float] = None) -> Dict[str, Any]:
        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            today = get_beijing_today()
            weekday = today.weekday()  # 0 = Monday, 6 = Sunday
            monday = today - timedelta(days=weekday)
            sunday = monday + timedelta(days=6)

            monday_iso = monday.isoformat()
            next_monday_iso = (sunday + timedelta(days=1)).isoformat()

            # 1. Resolve weekly target distance (current started week is locked; next week is editable)
            g_info = LocalStore.get_goal(canonical_uid)
            next_monday = sunday + timedelta(days=1)
            next_sunday = next_monday + timedelta(days=6)
            next_iso_year, next_iso_week, _ = next_monday.isocalendar()
            if target_km is None or target_km <= 0:
                if g_info and g_info.get("current_week_target") and float(g_info["current_week_target"]) > 0:
                    target_km = float(g_info["current_week_target"])
                elif g_info and g_info.get("weekly_target") and float(g_info["weekly_target"]) > 0:
                    target_km = float(g_info["weekly_target"])
                else:
                    target_km = 50.0
            next_week_target_km = float(g_info.get("next_weekly_target") or g_info.get("weekly_target") or target_km)

            # 2. Total week distance & runs
            cursor.execute(f"""
                SELECT SUM(distance_meters), COUNT(id)
                FROM activities
                WHERE (user_id = ? OR user_id = ?) AND start_time >= ? AND start_time < ?
                  AND {RUNNING_SQL_FILTER}
            """, (canonical_uid, uid, monday_iso, next_monday_iso))
            res = cursor.fetchone()
            week_m = float(res[0]) if res and res[0] is not None else 0.0
            week_runs = int(res[1]) if res and res[1] is not None else 0
            current_week_km = round(week_m / 1000.0, 1)

            progress_pct = round((current_week_km / target_km) * 100, 1) if target_km > 0 else 0.0
            remaining_km = max(0.0, round(target_km - current_week_km, 1))
            days_left = max(1, 7 - weekday)  # remaining days in current week including today
            daily_req = round(remaining_km / days_left, 1)

            # 3. Daily breakdown Mon-Sun
            day_names = ["一", "二", "三", "四", "五", "六", "日"]
            cursor.execute(f"""
                SELECT substr(start_time, 1, 10) as act_date, SUM(distance_meters), COUNT(id)
                FROM activities
                WHERE (user_id = ? OR user_id = ?) AND start_time >= ? AND start_time < ?
                  AND {RUNNING_SQL_FILTER}
                GROUP BY substr(start_time, 1, 10)
            """, (canonical_uid, uid, monday_iso, next_monday_iso))
            daily_map = { row[0]: (float(row[1] or 0), int(row[2] or 0)) for row in cursor.fetchall() }

            daily_breakdown = []
            for d_idx in range(7):
                cur_d = monday + timedelta(days=d_idx)
                cur_d_str = cur_d.isoformat()
                d_m, d_count = daily_map.get(cur_d_str, (0.0, 0))
                daily_breakdown.append({
                    "day_idx": d_idx,
                    "day_name": f"周{day_names[d_idx]}",
                    "short_day": day_names[d_idx],
                    "date": cur_d.strftime("%m/%d"),
                    "full_date": cur_d_str,
                    "distance_km": round(d_m / 1000.0, 1),
                    "runs_count": d_count,
                    "is_today": (cur_d == today),
                    "is_past": (cur_d < today)
                })

            iso_year, iso_week, _ = today.isocalendar()
            today_workout = LocalStore.get_today_workout(uid)
            return {
                "week_number": iso_week,
                "week_label": f"第{iso_week}周 ({monday.strftime('%m/%d')}~{sunday.strftime('%m/%d')})",
                "week_start": monday_iso,
                "week_end": sunday.isoformat(),
                "current_week_km": current_week_km,
                "target_week_km": target_km,
                "current_week_locked": True,
                "next_week_number": next_iso_week,
                "next_week_label": f"第{next_iso_week}周 ({next_monday.strftime('%m/%d')}~{next_sunday.strftime('%m/%d')})",
                "next_week_start": next_monday.isoformat(),
                "next_week_end": next_sunday.isoformat(),
                "next_week_target_km": next_week_target_km,
                "total_runs": week_runs,
                "progress_pct": progress_pct,
                "remaining_km": remaining_km,
                "days_left_in_week": days_left,
                "daily_required_km": daily_req,
                "daily_breakdown": daily_breakdown,
                "today_workout": today_workout
            }

    @staticmethod
    def get_today_workout(uid: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves today's scheduled workout from the runner's active periodized training plan.
        """
        canonical_uid = LocalStore.resolve_user_id(uid)
        plan = LocalStore.get_user_active_training_plan(canonical_uid, reconcile=False)
        if not plan:
            return None

        sched = plan.get("schedule_data") or {}
        weeks = sched.get("weeks") or []
        if not weeks:
            return None

        today_iso = get_beijing_today().isoformat()

        for w in weeks:
            days = w.get("days") or []
            for d_idx, day in enumerate(days):
                if str(day.get("date") or "") == today_iso:
                    raw_photos = day.get("workout_photos")
                    if not isinstance(raw_photos, list):
                        raw_photos = [day["photo_url"]] if day.get("photo_url") else []
                    workout_photos = [str(p).strip() for p in raw_photos if p and str(p).strip()]
                    return {
                        "plan_id": plan.get("id"),
                        "plan_title": plan.get("title"),
                        "goal_type": plan.get("goal_type"),
                        "target_race_name": plan.get("target_race_name"),
                        "week_index": w.get("week_index"),
                        "week_title": w.get("week_title"),
                        "phase": w.get("phase"),
                        "day_index": d_idx,
                        "date": day.get("date"),
                        "day_of_week": day.get("day_of_week"),
                        "workout_type": day.get("workout_type") or "easy_run",
                        "title": day.get("title") or "训练课目",
                        "distance_km": float(day.get("distance_km") or 0.0),
                        "target_pace": day.get("target_pace"),
                        "target_hr_zone": day.get("target_hr_zone"),
                        "description": day.get("description"),
                        "coach_notes": day.get("coach_notes"),
                        "completed": bool(day.get("completed")),
                        "auto_matched": bool(day.get("auto_matched")),
                        "actual_distance_km": day.get("actual_distance_km"),
                        "actual_pace": day.get("actual_pace"),
                        "actual_heartrate": day.get("actual_heartrate"),
                        "actual_execution_text": day.get("actual_execution_text") or "",
                        "rpe": day.get("rpe"),
                        "feeling_tag": day.get("feeling_tag") or "",
                        "athlete_notes": day.get("athlete_notes") or "",
                        "workout_photos": workout_photos,
                        "photo_url": workout_photos[0] if workout_photos else (day.get("photo_url") or ""),
                        "is_missed": bool(day.get("is_missed"))
                    }
        return None

    @staticmethod
    def get_monthly_trend(uid: str, num_months: int = 6) -> Dict[str, Any]:
        canonical_uid = LocalStore.resolve_user_id(uid)
        today = get_beijing_today()
        months = []
        for i in range(num_months - 1, -1, -1):
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            months.append((y, m))

        first_y, first_m = months[0]
        last_y, last_m = months[-1]
        range_start = f"{first_y:04d}-{first_m:02d}-01"
        range_end = f"{(last_y + 1 if last_m == 12 else last_y):04d}-{(1 if last_m == 12 else last_m + 1):02d}-01"

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT substr(start_time, 1, 7) AS ym, COALESCE(SUM(distance_meters), 0.0), COUNT(id)
                FROM activities
                WHERE (user_id = ? OR user_id = ?) AND start_time >= ? AND start_time < ?
                  AND {RUNNING_SQL_FILTER}
                GROUP BY substr(start_time, 1, 7)
                """,
                (canonical_uid, uid, range_start, range_end),
            )
            agg_map = {str(r[0]): (float(r[1] or 0.0), int(r[2] or 0)) for r in cursor.fetchall()}

        trend = []
        for (y, m) in months:
            ym_key = f"{y:04d}-{m:02d}"
            dist_m, count = agg_map.get(ym_key, (0.0, 0))
            dist_km = round(dist_m / 1000.0, 1)
            trend.append({
                "month_label": f"{y}/{m}月",
                "year": y,
                "month": m,
                "distance_km": dist_km,
                "count": count,
                "is_current": (y == today.year and m == today.month),
            })

        cur_km = trend[-1]["distance_km"] if trend else 0.0
        prev_km = trend[-2]["distance_km"] if len(trend) >= 2 else 0.0
        pct_change = round(((cur_km - prev_km) / prev_km) * 100, 1) if prev_km > 0 else 0.0

        return {
            "trend": trend,
            "current_month_km": cur_km,
            "prev_month_km": prev_km,
            "pct_change": pct_change,
            "recent_3_months": trend[-3:] if len(trend) >= 3 else trend,
        }

    @staticmethod
    def get_yearly_stats(uid: str, year: Optional[int] = None) -> Dict[str, Any]:
        canonical_uid = LocalStore.resolve_user_id(uid)
        today = get_beijing_today()
        eff_year = int(year) if year else today.year
        start_iso = f"{eff_year:04d}-01-01"
        end_iso = f"{eff_year + 1:04d}-01-01"

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT CAST(substr(start_time, 6, 2) AS INTEGER) AS m_num,
                       COALESCE(SUM(distance_meters), 0.0) AS dist_m,
                       COUNT(id) AS run_cnt
                FROM activities
                WHERE (user_id = ? OR user_id = ?) AND start_time >= ? AND start_time < ?
                  AND {RUNNING_SQL_FILTER}
                GROUP BY CAST(substr(start_time, 6, 2) AS INTEGER)
                """,
                (canonical_uid, uid, start_iso, end_iso),
            )
            month_agg = {int(r["m_num"]): (float(r["dist_m"] or 0.0), int(r["run_cnt"] or 0)) for r in cursor.fetchall() if r["m_num"]}

            target_year_km = 2400.0
            cursor.execute("SELECT monthly_targets, target_distance FROM goals WHERE user_id = ? OR user_id = ?", (canonical_uid, uid))
            g_row = cursor.fetchone()
            if g_row:
                try:
                    targets = json.loads(g_row["monthly_targets"]) if g_row["monthly_targets"] else None
                    if isinstance(targets, list) and len(targets) > 0:
                        target_year_km = sum(float(t) for t in targets)
                    elif g_row["target_distance"]:
                        target_year_km = float(g_row["target_distance"]) * 12.0
                except Exception:
                    pass

        total_m = sum(v[0] for v in month_agg.values())
        total_runs = sum(v[1] for v in month_agg.values())
        total_km = round(total_m / 1000.0, 1)

        passed_months = today.month if eff_year == today.year else (12 if eff_year < today.year else 1)
        avg_monthly_km = round(total_km / max(1, passed_months), 1)
        projected_year_km = round(avg_monthly_km * 12, 1)
        progress_pct = round((total_km / target_year_km) * 100, 1) if target_year_km > 0 else 0.0

        best_month_name = f"{today.month if eff_year == today.year else 1}月"
        best_month_km = 0.0
        monthly_breakdown = []
        for m in range(1, 13):
            m_dist, m_count = month_agg.get(m, (0.0, 0))
            m_km = round(m_dist / 1000.0, 1)
            if m_km > best_month_km:
                best_month_km = m_km
                best_month_name = f"{m}月"

            monthly_breakdown.append({
                "month": m,
                "month_label": f"{m}月",
                "distance_km": m_km,
                "runs_count": m_count,
                "is_current": (eff_year == today.year and m == today.month),
                "is_past": (eff_year < today.year or (eff_year == today.year and m <= today.month)),
            })

        return {
            "year": eff_year,
            "total_km": total_km,
            "total_runs": total_runs,
            "avg_monthly_km": avg_monthly_km,
            "projected_year_km": projected_year_km,
            "target_year_km": target_year_km,
            "monthly_target_km": round(target_year_km / 12, 1),
            "progress_pct": progress_pct,
            "best_month": {
                "name": best_month_name,
                "distance_km": best_month_km,
            },
            "monthly_breakdown": monthly_breakdown,
        }

    @staticmethod
    def sanitize_daily_health_row(d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Validates whether a daily_health record reflects actual overnight watch wearing.
        For Garmin/COROS, overnight wear requires a valid overnight HRV (`hrv_last_night_avg > 0`).
        For Apple HealthKit / Huawei Health (`allow_non_hrv_sleep=True`), genuine overnight sleep
        (`sleep_duration_seconds >= 7200`) is also accepted even if SDNN was not sampled.
        """
        if not d or not isinstance(d, dict):
            return d
        out = dict(d)
        allow_non_hrv = bool(out.pop("allow_non_hrv_sleep", False))
        has_overnight_hrv = bool(
            out.get("hrv_last_night_avg") is not None and float(out.get("hrv_last_night_avg") or 0) > 0
        )
        has_verified_hk_sleep = bool(
            (allow_non_hrv or out.get("hrv_status") == "HK_SLEEP")
            and out.get("sleep_duration_seconds") is not None
            and float(out.get("sleep_duration_seconds") or 0) >= 7200
        )
        if not (has_overnight_hrv or has_verified_hk_sleep):
            out["resting_heart_rate"] = None
            out["sleep_score"] = None
            out["sleep_duration_hours"] = None
            out["sleep_duration_seconds"] = None
            out["body_battery_max"] = None
            out["body_battery_min"] = None
            out["body_battery_current"] = None
            out["hrv_last_night_avg"] = None
            out["hrv_weekly_avg"] = None
            out["hrv_status"] = None
            out["overnight_wear_valid"] = False
        else:
            if has_verified_hk_sleep and not has_overnight_hrv and not out.get("hrv_status"):
                out["hrv_status"] = "HK_SLEEP"
            out["overnight_wear_valid"] = True
        return out

    @staticmethod
    def upsert_daily_health(uid: str, metrics: Dict[str, Any]):
        metrics = LocalStore.sanitize_daily_health_row(metrics) or {}
        wear_valid_flag = 1 if metrics.get("overnight_wear_valid") else 0
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            date_str = metrics.get("date") or get_beijing_today().isoformat()
            entry_id = f"{uid}_{date_str}"
            now_iso = datetime.utcnow().isoformat() + "Z"
            cursor.execute("""
                INSERT INTO daily_health 
                (id, user_id, date, resting_heart_rate, vo2_max, sleep_duration_seconds, sleep_duration_hours, sleep_score,
                 body_battery_max, body_battery_min, body_battery_current, hrv_status, hrv_weekly_avg, hrv_last_night_avg,
                 steps, active_calories, nap_duration_seconds, stress_avg, stress_max, hr_min, hr_max, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    resting_heart_rate = CASE WHEN ? = 0 THEN NULL ELSE COALESCE(excluded.resting_heart_rate, daily_health.resting_heart_rate) END,
                    vo2_max = COALESCE(excluded.vo2_max, daily_health.vo2_max),
                    sleep_duration_seconds = CASE WHEN ? = 0 THEN NULL ELSE COALESCE(excluded.sleep_duration_seconds, daily_health.sleep_duration_seconds) END,
                    sleep_duration_hours = CASE WHEN ? = 0 THEN NULL ELSE COALESCE(excluded.sleep_duration_hours, daily_health.sleep_duration_hours) END,
                    sleep_score = CASE WHEN ? = 0 THEN NULL ELSE COALESCE(excluded.sleep_score, daily_health.sleep_score) END,
                    body_battery_max = CASE WHEN ? = 0 THEN NULL ELSE COALESCE(excluded.body_battery_max, daily_health.body_battery_max) END,
                    body_battery_min = CASE WHEN ? = 0 THEN NULL ELSE COALESCE(excluded.body_battery_min, daily_health.body_battery_min) END,
                    body_battery_current = CASE WHEN ? = 0 THEN NULL ELSE COALESCE(excluded.body_battery_current, daily_health.body_battery_current) END,
                    hrv_status = CASE WHEN ? = 0 THEN NULL ELSE COALESCE(excluded.hrv_status, daily_health.hrv_status) END,
                    hrv_weekly_avg = CASE WHEN ? = 0 THEN NULL ELSE COALESCE(excluded.hrv_weekly_avg, daily_health.hrv_weekly_avg) END,
                    hrv_last_night_avg = CASE WHEN ? = 0 THEN NULL ELSE COALESCE(excluded.hrv_last_night_avg, daily_health.hrv_last_night_avg) END,
                    steps = COALESCE(excluded.steps, daily_health.steps),
                    active_calories = COALESCE(excluded.active_calories, daily_health.active_calories),
                    nap_duration_seconds = COALESCE(excluded.nap_duration_seconds, daily_health.nap_duration_seconds),
                    stress_avg = COALESCE(excluded.stress_avg, daily_health.stress_avg),
                    stress_max = COALESCE(excluded.stress_max, daily_health.stress_max),
                    hr_min = COALESCE(excluded.hr_min, daily_health.hr_min),
                    hr_max = COALESCE(excluded.hr_max, daily_health.hr_max),
                    updated_at = excluded.updated_at
            """, (
                entry_id,
                uid,
                date_str,
                metrics.get("resting_heart_rate"),
                metrics.get("vo2_max"),
                metrics.get("sleep_duration_seconds"),
                metrics.get("sleep_duration_hours"),
                metrics.get("sleep_score"),
                metrics.get("body_battery_max"),
                metrics.get("body_battery_min"),
                metrics.get("body_battery_current"),
                metrics.get("hrv_status"),
                metrics.get("hrv_weekly_avg"),
                metrics.get("hrv_last_night_avg"),
                metrics.get("steps"),
                metrics.get("active_calories"),
                metrics.get("nap_duration_seconds"),
                metrics.get("stress_avg"),
                metrics.get("stress_max"),
                metrics.get("hr_min"),
                metrics.get("hr_max"),
                metrics.get("updated_at") or now_iso,
                wear_valid_flag,
                wear_valid_flag,
                wear_valid_flag,
                wear_valid_flag,
                wear_valid_flag,
                wear_valid_flag,
                wear_valid_flag,
                wear_valid_flag,
                wear_valid_flag,
                wear_valid_flag,
            ))
            conn.commit()

    @staticmethod
    def get_latest_health(uid: str, max_age_days: int = 2) -> Optional[Dict[str, Any]]:
        """
        Fetches the user's most recent daily_health record within the last `max_age_days` days.
        STRICT DATA INTEGRITY:
        - Never splices historical sleep_score, HRV, or resting_heart_rate from older dates onto a newer date
          where the user did NOT wear their watch at night.
        - Strips out any recovery fields on days where overnight HRV (`hrv_last_night_avg > 0`) was not recorded.
        """
        cutoff_date = (get_beijing_today() - timedelta(days=max_age_days)).isoformat()
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM daily_health
                WHERE user_id = ? AND date >= ?
                ORDER BY date DESC LIMIT 2
            """, (uid, cutoff_date))
            rows = [LocalStore.sanitize_daily_health_row(dict(r)) for r in cursor.fetchall() if r]
            if not rows:
                return None
            return rows[0]

    @staticmethod
    def assess_recovery_data_availability(
        uid: str,
        health_row: Optional[Dict[str, Any]] = None,
        profile: Optional[Dict[str, Any]] = None,
        recent_acts: Optional[List[Dict[str, Any]]] = None,
        health_rows_14d: Optional[List[Dict[str, Any]]] = None,
        has_older_health_history: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Checks both:
        1. Whether the user wore their watch on the most recent night (overnight HRV & RHR present).
        2. Whether the user maintained continuous overnight wear over the past 7/14 days (`valid_nights_7d >= 5`
           and a valid 7-day HRV baseline `hrv_weekly_avg`, without `hrv_status == 'NONE'`).
        If a user either did not wear the watch on the latest night (e.g. 阿玥, 李敏) OR missed multiple nights
        recently so their 7-day HRV/RHR baseline is broken/skewed (e.g. 李敏, 陈晓韵), returns
        `recovery_data_available: False` and `night_wear_missing: True` with specific diagnostics.
        """
        if profile is not None and profile.get("id"):
            canonical_uid = str(profile["id"])
        else:
            canonical_uid = LocalStore.resolve_user_id(uid)
        if profile is None:
            profile = LocalStore.get_profile(canonical_uid) or {}
        if recent_acts is None:
            recent_acts = LocalStore.get_recent_activities(canonical_uid, limit=15) or []
        if health_row is None and health_rows_14d is None:
            health_row = LocalStore.get_latest_health(canonical_uid)
        elif health_row is not None:
            health_row = LocalStore.sanitize_daily_health_row(health_row)

        watch_connected = bool(
            profile.get("garmin_connected")
            or profile.get("coros_connected")
            or profile.get("apple_watch_connected")
            or profile.get("huawei_connected")
            or profile.get("suunto_connected")
        )
        has_recent_runs = len(recent_acts) > 0

        today = get_beijing_today()
        cutoff_recent = (today - timedelta(days=2)).isoformat()
        cutoff_7d = (today - timedelta(days=6)).isoformat()
        cutoff_14d = (today - timedelta(days=13)).isoformat()
        cutoff_5d = (today - timedelta(days=4)).isoformat()

        rows_14d: List[Dict[str, Any]] = []
        has_older_history = bool(has_older_health_history) if has_older_health_history is not None else False
        if health_rows_14d is not None:
            rows_14d = [
                LocalStore.sanitize_daily_health_row(dict(r))
                for r in health_rows_14d
                if r and str(r.get("date") or "")[:10] >= cutoff_14d
            ]
            rows_14d.sort(key=lambda r: str(r.get("date") or ""), reverse=True)
            if has_older_health_history is None:
                has_older_history = any(
                    str(r.get("date") or "")[:10] <= cutoff_5d for r in health_rows_14d if r
                )
        else:
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT * FROM daily_health
                        WHERE user_id = ? AND date >= ?
                        ORDER BY date DESC
                    """, (canonical_uid, cutoff_14d))
                    rows_14d = [LocalStore.sanitize_daily_health_row(dict(r)) for r in cursor.fetchall() if r]
                    cursor.execute("""
                        SELECT 1 FROM daily_health WHERE user_id = ? AND date <= ? LIMIT 1
                    """, (canonical_uid, cutoff_5d))
                    if cursor.fetchone():
                        has_older_history = True
            except Exception:
                rows_14d = []

        if not has_older_history and recent_acts:
            for a in recent_acts:
                st_date = str(a.get("start_time") or "")[:10]
                if st_date and st_date <= cutoff_5d:
                    has_older_history = True
                    break

        rows_7d = [r for r in rows_14d if str(r.get("date") or "")[:10] >= cutoff_7d]
        valid_rows_7d = [r for r in rows_7d if r.get("overnight_wear_valid")]
        non_wear_rows_7d = [r for r in rows_7d if not r.get("overnight_wear_valid")]
        valid_rows_14d = [r for r in rows_14d if r.get("overnight_wear_valid")]
        non_wear_rows_14d = [r for r in rows_14d if not r.get("overnight_wear_valid")]

        valid_nights_7d = len(valid_rows_7d)
        valid_nights_14d = len(valid_rows_14d)

        is_established_user = bool(has_older_history or len(rows_14d) >= 4 or len(non_wear_rows_14d) >= 2)
        if is_established_user:
            missing_nights_7d = max(len(non_wear_rows_7d), max(0, 7 - valid_nights_7d))
            missing_nights_14d = max(len(non_wear_rows_14d), max(0, 14 - valid_nights_14d))
        else:
            missing_nights_7d = len(non_wear_rows_7d)
            missing_nights_14d = len(non_wear_rows_14d)

        h = health_row or (rows_14d[0] if rows_14d else {})
        h_date = str(h.get("date") or "")[:10]
        is_recent_date = bool(h_date and h_date >= cutoff_recent)

        has_overnight_wear = bool(is_recent_date and h.get("overnight_wear_valid"))
        has_recent_hrv = bool(
            has_overnight_wear and h.get("hrv_last_night_avg") is not None and float(h.get("hrv_last_night_avg") or 0) > 0
        )
        has_recent_rhr = bool(
            has_overnight_wear and h.get("resting_heart_rate") is not None and float(h.get("resting_heart_rate") or 0) > 0
        )
        has_recent_sleep = bool(
            has_overnight_wear
            and (
                (h.get("sleep_duration_seconds") is not None and float(h.get("sleep_duration_seconds") or 0) > 0)
                or (h.get("sleep_score") is not None and float(h.get("sleep_score") or 0) > 0)
            )
        )

        raw_hrv_status = str(h.get("hrv_status") or "").strip().upper()
        has_weekly_hrv_baseline = bool(
            h.get("hrv_weekly_avg") is not None
            and float(h.get("hrv_weekly_avg") or 0) > 0
            and raw_hrv_status not in ("NONE", "UNAVAILABLE", "POOR_QUALITY", "MISSING")
        )

        # Intermittent non-wear / broken 7-day baseline detection:
        # Triggered when user missed >=3 nights in last 7 days (wore <5/7 nights) OR watch reports hrv_status=NONE / no weekly baseline
        hrv_baseline_broken = bool(
            raw_hrv_status in ("NONE", "UNAVAILABLE", "POOR_QUALITY")
            or (is_established_user and valid_nights_7d < 5)
            or (not has_weekly_hrv_baseline and is_established_user and valid_nights_7d < 5)
            or len(non_wear_rows_7d) >= 2
        )
        night_wear_intermittent = bool(
            (watch_connected or has_recent_runs)
            and (
                (valid_nights_14d > 0 and missing_nights_7d >= 2)
                or (has_overnight_wear and hrv_baseline_broken)
            )
        )

        missing_fields: List[str] = []
        if not has_recent_hrv:
            missing_fields.append("夜间HRV")
        if not has_recent_rhr:
            missing_fields.append("晨起静息心率")
        if not has_recent_sleep:
            missing_fields.append("睡眠恢复")
        if has_overnight_wear and hrv_baseline_broken and "7日HRV个人基线" not in missing_fields:
            missing_fields.append("7日HRV个人基线")

        recovery_data_available = bool(
            has_overnight_wear
            and has_recent_hrv
            and has_recent_rhr
            and not hrv_baseline_broken
        )
        night_wear_missing = bool(not recovery_data_available and (watch_connected or has_recent_runs))

        missing_str = "、".join(missing_fields) if missing_fields else "夜间HRV、晨起静息心率与睡眠恢复"
        if recovery_data_available:
            status_label = "恢复数据完整"
            user_warning = ""
            coach_warning = ""
        elif night_wear_missing and has_overnight_wear and hrv_baseline_broken:
            # Case like 陈晓韵: wore watch on the latest 1-3 nights, but missed multiple nights earlier so 7-day baseline is broken/skewed
            status_label = f"前段时间夜间漏戴 · 基线偏差 (近7天仅戴{valid_nights_7d}晚)"
            user_warning = (
                f"⚠️ 检测到您前段时间有多日夜间未佩戴手表（近7天仅佩戴 {valid_nights_7d}/7 晚、近14天佩戴 {valid_nights_14d}/14 晚），"
                "导致 7 日 HRV 与静息心率个人基线中断，当前单日恢复数据存在明显偏差，暂无法给出准确的训练强度建议。请连续 24 小时佩戴满 7 天以重建个人基线！"
            )
            coach_warning = (
                f"⚠️ 该队员前段时间多日夜间未佩戴手表（近7天仅佩戴 {valid_nights_7d}/7 晚、近14天佩戴 {valid_nights_14d}/14 晚），"
                "导致 7 日 HRV 与静息心率基线中断，当前恢复数据存在偏差，已暂停采用偏差数据生成训练建议。请提醒队员连续 24 小时佩戴满 7 天重建基线。"
            )
        elif night_wear_missing and valid_nights_14d > 0:
            # Case like 李敏: wore watch on some nights, but missed recent nights (e.g. missed 4 of last 7 nights including latest night)
            status_label = f"近期多日夜间未佩戴 · 恢复数据缺失 (近7天仅戴{valid_nights_7d}晚)"
            user_warning = (
                f"⚠️ 检测到您近期多日夜间未佩戴手表（近7天仅佩戴 {valid_nights_7d}/7 晚、漏戴 {missing_nights_7d} 晚，且最近夜间未佩戴），"
                f"缺失【{missing_str}】且日间心率存在偏差。系统已过滤无效数据，暂无法为您提供准确的训练强度建议。请保持连续 24 小时全天佩戴手表！"
            )
            coach_warning = (
                f"⚠️ 该队员近期多日夜间未佩戴手表（近7天仅佩戴 {valid_nights_7d}/7 晚、漏戴 {missing_nights_7d} 晚，最新夜间未佩戴），"
                f"缺失{missing_str}且日间心率存在偏差，已过滤无效数据，暂无法给出准确的训练强度建议。请提醒队员保持连续 24 小时佩戴手表。"
            )
        elif night_wear_missing:
            # Case like 阿玥 / 王鹏飞 / 跑者_98b0: never wears watch at night (0/7 nights)
            status_label = "夜间未佩戴 · 恢复数据缺失"
            user_warning = (
                f"⚠️ 检测到您近期未在夜间睡眠时佩戴手表（近7天佩戴 {valid_nights_7d}/7 晚），缺失【{missing_str}】等关键恢复数据。"
                "仅在跑步时佩戴手表无法评估自主神经与身体恢复状态，暂无法为您提供准确的训练强度建议。请保持 24 小时全天佩戴手表！"
            )
            coach_warning = (
                f"⚠️ 该队员近期夜间未佩戴手表（近7天佩戴 {valid_nights_7d}/7 晚，缺失{missing_str}数据），无法凭无效数据评估身体恢复度，暂无法给出准确的训练强度与负荷建议。请提醒队员保持 24 小时佩戴手表。"
            )
        else:
            status_label = "待连接手表并24小时佩戴"
            user_warning = (
                "⌚ 请连接运动手表并保持 24 小时全天（含夜间睡眠）佩戴，以获取夜间 HRV、静息心率与睡眠恢复数据，生成科学的训练建议。"
            )
            coach_warning = (
                "⚠️ 该队员暂未同步近期的夜间 HRV 与静息心率等恢复数据，暂无法依据生理恢复指标给出准确的训练建议。"
            )

        return {
            "recovery_data_available": recovery_data_available,
            "night_wear_missing": night_wear_missing,
            "night_wear_intermittent": night_wear_intermittent,
            "hrv_baseline_broken": hrv_baseline_broken,
            "valid_nights_7d": valid_nights_7d,
            "missing_nights_7d": missing_nights_7d,
            "valid_nights_14d": valid_nights_14d,
            "missing_nights_14d": missing_nights_14d,
            "watch_connected": watch_connected,
            "has_recent_runs": has_recent_runs,
            "has_recent_hrv": has_recent_hrv,
            "has_recent_rhr": has_recent_rhr,
            "has_recent_sleep": has_recent_sleep,
            "latest_valid_recovery_date": h_date if recovery_data_available else None,
            "missing_recovery_fields": missing_fields,
            "recovery_status_label": status_label,
            "user_warning": user_warning,
            "coach_warning": coach_warning,
            "watch_wearing_notice": "请保持 24 小时全天（含夜间睡眠）佩戴手表，确保小程序获取夜间 HRV、静息心率与睡眠恢复等必要数据。",
        }

    @staticmethod
    def get_health_trend_30d(uid: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            today = date.today()
            cutoff = (today - timedelta(days=30)).isoformat()
            cursor.execute("SELECT * FROM daily_health WHERE user_id = ? AND date >= ? ORDER BY date ASC", (uid, cutoff))
            rows = cursor.fetchall()
            if not rows:
                return []

            existing_map = {r["date"]: LocalStore.sanitize_daily_health_row(dict(r)) or {} for r in rows}
            trend = []
            for i in range(29, -1, -1):
                d = today - timedelta(days=i)
                d_str = d.isoformat()
                short_d = d.strftime("%m-%d")
                
                if d_str in existing_map:
                    item = existing_map[d_str]
                    rhr = item.get("resting_heart_rate")
                    hrv = item.get("hrv_last_night_avg")
                    hrv_wk = item.get("hrv_weekly_avg")
                    bb = item.get("body_battery_max")
                    sleep_score = item.get("sleep_score")
                    vo2_m = item.get("vo2_max")

                    trend.append({
                        "date": d_str,
                        "date_label": short_d,
                        "resting_heart_rate": int(rhr) if rhr is not None else None,
                        "hrv": int(hrv) if hrv is not None else None,
                        "hrv_last_night_avg": int(hrv) if hrv is not None else None,
                        "hrv_weekly_avg": int(hrv_wk) if hrv_wk is not None else None,
                        "body_battery": int(bb) if bb is not None else None,
                        "body_battery_max": int(bb) if bb is not None else None,
                        "sleep_score": int(sleep_score) if sleep_score is not None else None,
                        "vo2_max": float(vo2_m) if vo2_m is not None else None,
                        "sleep_duration_hours": float(item.get("sleep_duration_hours")) if item.get("sleep_duration_hours") is not None else None,
                        "sleep_duration_seconds": int(item.get("sleep_duration_seconds")) if item.get("sleep_duration_seconds") is not None else None
                    })

            return trend

    @staticmethod
    def _format_goal_dict(row_dict: Optional[Dict[str, Any]], today: Optional[date] = None) -> Dict[str, Any]:
        eff_today = today or get_beijing_today()
        cur_monday = eff_today - timedelta(days=eff_today.weekday())
        next_monday = cur_monday + timedelta(days=7)
        cur_iso_y, cur_iso_w, _ = cur_monday.isocalendar()
        next_iso_y, next_iso_w, _ = next_monday.isocalendar()
        cur_week_key = f"{cur_iso_y}-W{cur_iso_w:02d}"
        next_week_key = f"{next_iso_y}-W{next_iso_w:02d}"

        if row_dict:
            d = dict(row_dict)
            if d.get("monthly_targets"):
                if isinstance(d["monthly_targets"], list):
                    pass
                else:
                    try:
                        d["monthly_targets"] = json.loads(d["monthly_targets"])
                    except Exception:
                        d["monthly_targets"] = [200.0] * 12
            else:
                d["monthly_targets"] = [float(d.get("target_distance") or 200.0)] * 12
            if d.get("weekly_target") is not None and float(d["weekly_target"]) > 0:
                d["weekly_target"] = float(d["weekly_target"])
            else:
                d["weekly_target"] = round(float(d.get("target_distance") or 200.0) / 4.0, 1)

            w_map: Dict[str, float] = {}
            if d.get("weekly_targets_map"):
                if isinstance(d["weekly_targets_map"], dict):
                    w_map = {str(k): float(v) for k, v in d["weekly_targets_map"].items() if v is not None}
                else:
                    try:
                        raw_map = json.loads(d["weekly_targets_map"])
                        if isinstance(raw_map, dict):
                            w_map = {str(k): float(v) for k, v in raw_map.items() if v is not None}
                    except Exception:
                        w_map = {}
            base_w = float(d["weekly_target"])
            d["weekly_targets_map"] = w_map
            d["current_week_key"] = cur_week_key
            d["next_week_key"] = next_week_key
            d["current_week_target"] = float(w_map.get(cur_week_key, base_w))
            d["next_weekly_target"] = float(w_map.get(next_week_key, base_w))
            d["current_week_locked"] = True
            d["current_month"] = eff_today.month
            d["locked_months"] = list(range(1, eff_today.month + 1))
            d["is_default"] = False
            return d

        return {
            "is_default": True,
            "target_distance": 200.0,
            "weekly_target": 50.0,
            "current_week_target": 50.0,
            "next_weekly_target": 50.0,
            "weekly_targets_map": {},
            "current_week_key": cur_week_key,
            "next_week_key": next_week_key,
            "current_week_locked": True,
            "current_month": eff_today.month,
            "locked_months": list(range(1, eff_today.month + 1)),
            "period_type": "monthly",
            "monthly_targets": [200.0] * 12,
        }

    @staticmethod
    def get_goal(uid: str) -> Dict[str, Any]:
        canonical_uid = LocalStore.resolve_user_id(uid)
        today = get_beijing_today()
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM goals WHERE user_id = ? OR user_id = ?", (canonical_uid, uid))
            row = cursor.fetchone()
        return LocalStore._format_goal_dict(dict(row) if row else None, today=today)

    @staticmethod
    def upsert_goal(uid: str, data: Dict[str, Any], enforce_started_lock: bool = False) -> Dict[str, Any]:
        canonical_uid = LocalStore.resolve_user_id(uid)
        today = get_beijing_today()
        cur_monday = today - timedelta(days=today.weekday())
        next_monday = cur_monday + timedelta(days=7)
        cur_iso_y, cur_iso_w, _ = cur_monday.isocalendar()
        next_iso_y, next_iso_w, _ = next_monday.isocalendar()
        cur_week_key = f"{cur_iso_y}-W{cur_iso_w:02d}"
        next_week_key = f"{next_iso_y}-W{next_iso_w:02d}"

        existing = LocalStore.get_goal(canonical_uid)
        raw_existing_mt = existing.get("monthly_targets")
        if isinstance(raw_existing_mt, dict):
            existing_monthly = [float(raw_existing_mt.get(str(m), raw_existing_mt.get(m, 200.0))) for m in range(1, 13)]
        elif isinstance(raw_existing_mt, list):
            existing_monthly = [float(v) for v in raw_existing_mt]
        else:
            existing_monthly = [200.0] * 12
        while len(existing_monthly) < 12:
            existing_monthly.append(200.0)
        existing_w_map = dict(existing.get("weekly_targets_map") or {})
        existing_cur_w_target = float(existing.get("current_week_target") or existing.get("weekly_target") or 50.0)

        target_dist = float(data.get("target_distance") or data.get("monthly_target") or existing.get("target_distance") or 200.0)
        req_weekly = data.get("next_weekly_target") if data.get("next_weekly_target") is not None else data.get("weekly_target")
        weekly_target = float(req_weekly if req_weekly is not None else (existing.get("weekly_target") or round(target_dist / 4.0, 1) or 50.0))

        raw_incoming_mt = data.get("monthly_targets")
        if isinstance(raw_incoming_mt, dict):
            incoming_monthly = [float(raw_incoming_mt.get(str(m), raw_incoming_mt.get(m, existing_monthly[m - 1]))) for m in range(1, 13)]
        elif isinstance(raw_incoming_mt, list) and len(raw_incoming_mt) > 0:
            incoming_monthly = [float(v) for v in raw_incoming_mt]
        else:
            incoming_monthly = list(existing_monthly)
        while len(incoming_monthly) < 12:
            incoming_monthly.append(target_dist)

        if enforce_started_lock:
            # 1) Started months (1 .. today.month) are locked and cannot be modified
            final_monthly = []
            for m_idx in range(12):
                if (m_idx + 1) <= today.month:
                    final_monthly.append(existing_monthly[m_idx])
                else:
                    final_monthly.append(incoming_monthly[m_idx])
            # 2) Started current week (cur_week_key) is locked; update applies to next week & future weeks
            existing_w_map[cur_week_key] = existing_cur_w_target
            existing_w_map[next_week_key] = weekly_target
            if isinstance(data.get("weekly_targets_map"), dict):
                for wk_k, wk_v in data["weekly_targets_map"].items():
                    if wk_k > cur_week_key and wk_v is not None:
                        existing_w_map[str(wk_k)] = float(wk_v)
        else:
            final_monthly = incoming_monthly
            if isinstance(data.get("weekly_targets_map"), dict):
                for wk_k, wk_v in data["weekly_targets_map"].items():
                    if wk_v is not None:
                        existing_w_map[str(wk_k)] = float(wk_v)
            existing_w_map[cur_week_key] = float(data.get("current_week_target") or weekly_target)
            existing_w_map[next_week_key] = weekly_target

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            targets_json = json.dumps(final_monthly)
            w_map_json = json.dumps(existing_w_map)
            cursor.execute("""
                INSERT INTO goals (user_id, target_distance, period_type, monthly_targets, weekly_target, weekly_targets_map)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    target_distance = excluded.target_distance,
                    period_type = excluded.period_type,
                    monthly_targets = excluded.monthly_targets,
                    weekly_target = excluded.weekly_target,
                    weekly_targets_map = excluded.weekly_targets_map
            """, (
                canonical_uid,
                target_dist,
                data.get("period_type", "monthly"),
                targets_json,
                weekly_target,
                w_map_json
            ))
            conn.commit()
        return LocalStore.get_goal(canonical_uid)

    @staticmethod
    def time_str_to_seconds(time_str: Any) -> Optional[int]:
        if not time_str:
            return None
        if isinstance(time_str, (int, float)):
            return int(time_str)
        s = str(time_str).strip()
        parts = s.split(":")
        try:
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(float(parts[2]))
            elif len(parts) == 2:
                return int(parts[0]) * 60 + int(float(parts[1]))
            elif len(parts) == 1 and parts[0].isdigit():
                return int(parts[0])
        except Exception:
            return None
        return None

    @staticmethod
    def seconds_to_time_str(seconds: Optional[int]) -> str:
        if not seconds or seconds <= 0:
            return "00:00"
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    @staticmethod
    def get_race_plans(uid: str) -> List[Dict[str, Any]]:
        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM race_plans WHERE user_id = ? OR user_id = ? ORDER BY race_date ASC", (canonical_uid, uid))
            rows = cursor.fetchall()
            plans = []
            seen = set()
            today = date.today()
            for r in rows:
                p = dict(r)
                if p.get("id") in seen:
                    continue
                seen.add(p.get("id"))
                
                status = p.get("status") or "upcoming"
                finish_time = p.get("finish_time") or ""
                p["status"] = status
                p["finish_time"] = finish_time
                p["finish_notes"] = p.get("finish_notes") or ""
                p["photo_url"] = p.get("photo_url") or ""
                p["was_official_pacer"] = bool(p.get("was_official_pacer"))
                p["pacer_target_time"] = p.get("pacer_target_time") or ""
                
                # Photos list
                raw_photos = p.get("photos")
                if raw_photos:
                    try:
                        p["photos"] = json.loads(raw_photos) if isinstance(raw_photos, str) else raw_photos
                    except Exception:
                        p["photos"] = [p["photo_url"]] if p.get("photo_url") else []
                else:
                    p["photos"] = [p["photo_url"]] if p.get("photo_url") else []

                # Deserialize race_info JSON early so auto-matching can inspect race_distance_km
                raw_ri = p.get("race_info")
                if raw_ri:
                    try:
                        p["race_info"] = json.loads(raw_ri) if isinstance(raw_ri, str) else raw_ri
                    except Exception:
                        p["race_info"] = {}
                else:
                    p["race_info"] = {}

                # Completed status & countdown calculation
                is_completed = (status == "completed" or bool(finish_time))
                p["is_completed"] = is_completed

                r_date = None
                if p.get("race_date"):
                    try:
                        r_date = datetime.strptime(p["race_date"][:10], "%Y-%m-%d").date()
                        days_left = (r_date - today).days
                        p["days_left"] = max(0, days_left)
                        p["days_until"] = p["days_left"]
                        p["is_past"] = days_left < 0
                    except Exception:
                        p["days_left"] = 0
                        p["days_until"] = None
                        p["is_past"] = False
                else:
                    p["days_left"] = 0
                    p["days_until"] = None
                    p["is_past"] = False

                # Auto-match watch activity if race date has arrived/passed and not yet completed
                if not is_completed and r_date is not None and r_date <= today:
                    try:
                        ri_dist = float((p.get("race_info") or {}).get("race_distance_km") or 0)
                        rtype_lower = str(p.get("race_type") or "").lower()
                        if ri_dist > 0:
                            min_dist_km = max(3.5, ri_dist * 0.65)
                        elif "全马" in rtype_lower or "full" in rtype_lower or rtype_lower == "marathon":
                            min_dist_km = 30.0
                        elif "半马" in rtype_lower or "half" in rtype_lower:
                            min_dist_km = 15.0
                        elif "10" in rtype_lower:
                            min_dist_km = 8.0
                        elif "5" in rtype_lower:
                            min_dist_km = 4.0
                        elif "trail" in rtype_lower or "越野" in rtype_lower:
                            min_dist_km = 10.0
                        else:
                            min_dist_km = 5.0

                        matched_act = LocalStore.find_matched_activity_for_race(
                            canonical_uid, p["race_date"], min_distance_km=min_dist_km
                        )
                        if matched_act and matched_act.get("formatted_time"):
                            finish_time = matched_act["formatted_time"]
                            auto_notes = (
                                p["finish_notes"]
                                or f"匹配到手表记录【{matched_act.get('name')}】({matched_act.get('distance_km')}km, 平均配速 {matched_act.get('avg_pace_str')})"
                            )
                            status = "completed"
                            is_completed = True
                            p["status"] = "completed"
                            p["is_completed"] = True
                            p["finish_time"] = finish_time
                            p["finish_notes"] = auto_notes
                            cursor.execute(
                                """
                                UPDATE race_plans
                                SET status = 'completed', finish_time = ?, finish_notes = ?
                                WHERE id = ?
                                """,
                                (finish_time, auto_notes, p.get("id")),
                            )
                            conn.commit()
                    except Exception as e:
                        logger.warning(f"[get_race_plans] Auto-match failed for race {p.get('id')}: {e}")

                # Performance comparison if target_time and finish_time both exist
                if finish_time and p.get("target_time"):
                    try:
                        t_sec = LocalStore.time_str_to_seconds(p["target_time"])
                        f_sec = LocalStore.time_str_to_seconds(finish_time)
                        if t_sec and f_sec:
                            diff = f_sec - t_sec
                            p["diff_seconds"] = diff
                            if diff < 0:
                                p["diff_str"] = f"-{LocalStore.seconds_to_time_str(abs(diff))}"
                                p["performance_badge"] = "超额达标 🎉"
                            elif diff == 0:
                                p["diff_str"] = "精准达标"
                                p["performance_badge"] = "精准达标 🎯"
                            else:
                                p["diff_str"] = f"+{LocalStore.seconds_to_time_str(diff)}"
                                p["performance_badge"] = "顺利完赛 🏅"
                    except Exception:
                        pass

                # Official pacer finish accuracy if marked as past official pacer
                if p.get("was_official_pacer") and finish_time:
                    ref_pacer_t = p.get("pacer_target_time") or p.get("target_time")
                    if ref_pacer_t:
                        try:
                            pt_sec = LocalStore.time_str_to_seconds(ref_pacer_t)
                            pf_sec = LocalStore.time_str_to_seconds(finish_time)
                            if pt_sec and pf_sec:
                                p_err = pf_sec - pt_sec
                                p["pacer_error_seconds"] = p_err
                                sign = "+" if p_err > 0 else ("-" if p_err < 0 else "±")
                                p["pacer_error_str"] = f"{sign}{LocalStore.seconds_to_time_str(abs(p_err))}" if p_err != 0 else "0:00"
                        except Exception:
                            pass

                plans.append(p)
            
            return plans

    @staticmethod
    def upsert_race_plan(uid: str, plan_data: Dict[str, Any]):
        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            plan_id = plan_data.get("id") or f"race_{int(datetime.utcnow().timestamp()*1000)}_{uuid.uuid4().hex[:6]}"
            cursor.execute("SELECT * FROM race_plans WHERE id = ?", (plan_id,))
            existing = dict(cursor.fetchone() or {})

            raw_pri = str(plan_data.get("priority", existing.get("priority", 1))).upper()
            if raw_pri in ["A", "1"]:
                pri = 1
            elif raw_pri in ["B", "2"]:
                pri = 2
            elif raw_pri in ["C", "3"]:
                pri = 3
            else:
                pri = 1

            status = plan_data.get("status") or existing.get("status") or "upcoming"
            finish_time = plan_data.get("finish_time") if plan_data.get("finish_time") is not None else existing.get("finish_time")
            finish_notes = plan_data.get("finish_notes") if plan_data.get("finish_notes") is not None else existing.get("finish_notes")
            photo_url = plan_data.get("photo_url") if plan_data.get("photo_url") is not None else existing.get("photo_url")
            photos = plan_data.get("photos")
            if photos is not None:
                photos_json = json.dumps(photos, ensure_ascii=False)
            elif existing.get("photos"):
                photos_json = existing.get("photos")
            elif photo_url:
                photos_json = json.dumps([photo_url], ensure_ascii=False)
            else:
                photos_json = None

            was_pacer = (
                1 if bool(plan_data.get("was_official_pacer")) else 0
            ) if plan_data.get("was_official_pacer") is not None else int(existing.get("was_official_pacer") or 0)
            pacer_target = (
                str(plan_data.get("pacer_target_time") or "").strip()
                if plan_data.get("pacer_target_time") is not None
                else str(existing.get("pacer_target_time") or "")
            )
            race_info_json = (
                json.dumps(plan_data.get("race_info") or {}, ensure_ascii=False)
                if plan_data.get("race_info") is not None
                else existing.get("race_info")
            )

            cursor.execute("""
                INSERT OR REPLACE INTO race_plans (
                    id, user_id, name, race_type, race_date, target_time, priority, created_at, race_info,
                    status, finish_time, finish_notes, photo_url, photos, was_official_pacer, pacer_target_time
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_id,
                canonical_uid,
                plan_data.get("name") or existing.get("name") or "未命名赛事",
                plan_data.get("race_type") or existing.get("race_type") or "全马",
                plan_data.get("race_date") or existing.get("race_date") or date.today().isoformat(),
                plan_data.get("target_time") or existing.get("target_time") or "3:30:00",
                pri,
                existing.get("created_at") or (datetime.utcnow().isoformat() + "Z"),
                race_info_json,
                status,
                finish_time,
                finish_notes,
                photo_url,
                photos_json,
                was_pacer,
                pacer_target,
            ))
            conn.commit()
            return plan_id

    @staticmethod
    def update_race_completion(
        uid: str,
        race_id: str,
        status: str = "completed",
        finish_time: Optional[str] = None,
        finish_notes: Optional[str] = None,
        photo_url: Optional[str] = None,
        was_official_pacer: Optional[bool] = None,
        pacer_target_time: Optional[str] = None,
    ) -> bool:
        """Marks a race as completed or upcoming, updating finish time, notes, pacer badge, and photo."""
        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Fetch existing photos and pacer flags
            cursor.execute(
                "SELECT photo_url, photos, was_official_pacer, pacer_target_time FROM race_plans WHERE (user_id = ? OR user_id = ?) AND (id = ? OR name = ?)",
                (canonical_uid, uid, race_id, race_id)
            )
            row = cursor.fetchone()
            if not row:
                return False
            existing_photo_url, existing_photos_raw, ex_was_pacer, ex_pacer_target = row
            final_photo_url = photo_url if photo_url is not None else existing_photo_url
            photos_list = []
            if existing_photos_raw:
                try:
                    photos_list = json.loads(existing_photos_raw)
                except Exception:
                    photos_list = []
            if final_photo_url and final_photo_url not in photos_list:
                photos_list.append(final_photo_url)

            final_was_pacer = (1 if was_official_pacer else 0) if was_official_pacer is not None else int(ex_was_pacer or 0)
            final_pacer_target = pacer_target_time.strip() if pacer_target_time is not None else (ex_pacer_target or "")

            cursor.execute("""
                UPDATE race_plans
                SET status = ?, finish_time = COALESCE(?, finish_time), finish_notes = COALESCE(?, finish_notes),
                    photo_url = COALESCE(?, photo_url), photos = ?,
                    was_official_pacer = ?, pacer_target_time = ?
                WHERE (user_id = ? OR user_id = ?) AND (id = ? OR name = ?)
            """, (
                status,
                finish_time,
                finish_notes,
                final_photo_url,
                json.dumps(photos_list, ensure_ascii=False) if photos_list else None,
                final_was_pacer,
                final_pacer_target,
                canonical_uid,
                uid,
                race_id,
                race_id
            ))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def add_race_photo(uid: str, race_id: str, photo_url: str) -> List[str]:
        """Appends a new photo to the race plan photos list and sets it as primary photo_url."""
        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT photos FROM race_plans WHERE (user_id = ? OR user_id = ?) AND (id = ? OR name = ?)",
                (canonical_uid, uid, race_id, race_id)
            )
            row = cursor.fetchone()
            photos_list = []
            if row and row[0]:
                try:
                    photos_list = json.loads(row[0])
                except Exception:
                    photos_list = []
            if photo_url not in photos_list:
                photos_list.append(photo_url)
            cursor.execute("""
                UPDATE race_plans
                SET photo_url = ?, photos = ?
                WHERE (user_id = ? OR user_id = ?) AND (id = ? OR name = ?)
            """, (photo_url, json.dumps(photos_list, ensure_ascii=False), canonical_uid, uid, race_id, race_id))
            conn.commit()
            return photos_list

    @staticmethod
    def delete_race_photo(uid: str, race_id: str, photo_url: str) -> List[str]:
        """Removes a photo from the race plan photos list."""
        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT photo_url, photos FROM race_plans WHERE (user_id = ? OR user_id = ?) AND (id = ? OR name = ?)",
                (canonical_uid, uid, race_id, race_id)
            )
            row = cursor.fetchone()
            if not row:
                return []
            curr_main, existing_photos_raw = row
            photos_list = []
            if existing_photos_raw:
                try:
                    photos_list = json.loads(existing_photos_raw)
                except Exception:
                    photos_list = []
            photos_list = [p for p in photos_list if p != photo_url]
            new_main = photos_list[0] if photos_list else None
            cursor.execute("""
                UPDATE race_plans
                SET photo_url = ?, photos = ?
                WHERE (user_id = ? OR user_id = ?) AND (id = ? OR name = ?)
            """, (new_main, json.dumps(photos_list, ensure_ascii=False) if photos_list else None, canonical_uid, uid, race_id, race_id))
            conn.commit()
            return photos_list

    @staticmethod
    def find_matched_activity_for_race(
        uid: str, race_date: str, min_distance_km: float = 0.0
    ) -> Optional[Dict[str, Any]]:
        """
        Finds a Garmin/COROS activity matching the given race date (within date or ±1 day).
        Useful for one-click or automatic filling of actual finish time and metrics into race plan.
        """
        canonical_uid = LocalStore.resolve_user_id(uid)
        date_clean = (race_date or "")[:10]
        if not date_clean:
            return None
        min_dist_meters = max(0.0, float(min_distance_km or 0.0) * 1000.0)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Match exact date first
            cursor.execute(f"""
                SELECT id, name, sport_type, start_time, distance_meters, moving_time_seconds, 
                       elapsed_time_seconds, avg_pace_str, elevation_gain_meters, average_heartrate
                FROM activities
                WHERE (user_id = ? OR user_id = ?) AND start_time LIKE ?
                  AND distance_meters >= ?
                  AND {RUNNING_SQL_FILTER}
                ORDER BY distance_meters DESC
                LIMIT 1
            """, (canonical_uid, uid, f"{date_clean}%", min_dist_meters))
            row = cursor.fetchone()
            if not row:
                # Try ±1 day
                try:
                    d_obj = datetime.strptime(date_clean, "%Y-%m-%d").date()
                    prev_d = (d_obj - timedelta(days=1)).isoformat()
                    next_d = (d_obj + timedelta(days=1)).isoformat()
                    cursor.execute(f"""
                        SELECT id, name, sport_type, start_time, distance_meters, moving_time_seconds, 
                               elapsed_time_seconds, avg_pace_str, elevation_gain_meters, average_heartrate
                        FROM activities
                        WHERE (user_id = ? OR user_id = ?) AND (start_time LIKE ? OR start_time LIKE ?)
                          AND distance_meters >= ?
                          AND {RUNNING_SQL_FILTER}
                        ORDER BY distance_meters DESC
                        LIMIT 1
                    """, (canonical_uid, uid, f"{prev_d}%", f"{next_d}%", min_dist_meters))
                    row = cursor.fetchone()
                except Exception:
                    row = None
            if not row:
                return None
            act = dict(row)
            # Duration formatting
            secs = act.get("elapsed_time_seconds") or act.get("moving_time_seconds") or 0
            act["formatted_time"] = LocalStore.seconds_to_time_str(int(secs))
            act["distance_km"] = round((act.get("distance_meters") or 0) / 1000.0, 2)
            return act

    @staticmethod
    def update_race_plan_priority(uid: str, race_identifier: str, priority: int) -> bool:
        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE race_plans 
                SET priority = ? 
                WHERE (user_id = ? OR user_id = ?) AND (id = ? OR name = ?)
            """, (priority, canonical_uid, uid, race_identifier, race_identifier))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def delete_race_plan(uid: str, race_id: str):
        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM race_plans 
                WHERE (user_id = ? OR user_id = ?) AND (id = ? OR name = ?)
            """, (canonical_uid, uid, race_id, race_id))
            conn.commit()

    @staticmethod
    def update_race_info(uid: str, race_identifier: str, race_info: Dict[str, Any]) -> bool:
        """Update only the race_info JSON blob for a specific race plan."""
        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE race_plans
                SET race_info = ?
                WHERE (user_id = ? OR user_id = ?) AND (id = ? OR name = ?)
            """, (json.dumps(race_info, ensure_ascii=False), canonical_uid, uid, race_identifier, race_identifier))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def get_coach_report(uid: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT content FROM coach_reports WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1", (uid,))
            row = cursor.fetchone()
            if row and row["content"]:
                try:
                    return json.loads(row["content"])
                except Exception:
                    pass
            return None

    @staticmethod
    def save_coach_report(uid: str, report: Dict[str, Any]):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            entry_id = f"coach_{uid}"
            cursor.execute("""
                INSERT OR REPLACE INTO coach_reports (id, user_id, content, updated_at)
                VALUES (?, ?, ?, ?)
            """, (entry_id, uid, json.dumps(report, ensure_ascii=False), datetime.utcnow().isoformat() + "Z"))
            conn.commit()

    # ── Referral & Self-Service Club Creation Eligibility Methods ──

    @staticmethod
    def record_referral(inviter_uid: str, invitee_uid: str) -> bool:
        """
        Records that `inviter_uid` referred a new user `invitee_uid`.
        Returns True if a new referral was recorded, False if invalid or already recorded.
        """
        if not inviter_uid or not invitee_uid:
            return False
        eff_inviter = LocalStore.resolve_user_id(inviter_uid.strip())
        eff_invitee = LocalStore.resolve_user_id(invitee_uid.strip())
        if not eff_inviter or not eff_invitee or eff_inviter == eff_invitee:
            return False

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Ensure both profiles exist
            cursor.execute("SELECT id FROM profiles WHERE id = ?", (eff_inviter,))
            if not cursor.fetchone():
                return False
            cursor.execute("SELECT id, invited_by FROM profiles WHERE id = ?", (eff_invitee,))
            invitee_row = cursor.fetchone()
            if not invitee_row:
                return False
            if invitee_row["invited_by"]:
                return False

            # Prevent circular referral (if invitee previously invited inviter)
            cursor.execute(
                "SELECT id FROM user_referrals WHERE inviter_uid = ? AND invitee_uid = ?",
                (eff_invitee, eff_inviter),
            )
            if cursor.fetchone():
                return False

            # Check if invitee was already referred
            cursor.execute("SELECT id FROM user_referrals WHERE invitee_uid = ?", (eff_invitee,))
            if cursor.fetchone():
                return False

            now_str = datetime.utcnow().isoformat() + "Z"
            ref_id = f"ref_{eff_inviter}_{eff_invitee}"
            try:
                cursor.execute(
                    """
                    INSERT INTO user_referrals (id, inviter_uid, invitee_uid, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (ref_id, eff_inviter, eff_invitee, now_str),
                )
                cursor.execute(
                    "UPDATE profiles SET invited_by = ? WHERE id = ?",
                    (eff_inviter, eff_invitee),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    @staticmethod
    def get_referral_status(uid: str, required_count: int = 3) -> Dict[str, Any]:
        """
        Returns the referral progress and club creation eligibility for `uid`.
        Only invited new users who have successfully bound a sports watch
        (Garmin, COROS, Apple Watch, Huawei, or Suunto) count toward `invited_count`.
        """
        eff_uid = LocalStore.resolve_user_id(uid) if uid else ""
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT r.invitee_uid as id,
                       r.created_at as referred_at,
                       p.display_name,
                       p.avatar_url,
                       p.garmin_connected,
                       p.coros_connected,
                       p.apple_watch_connected,
                       p.huawei_connected,
                       p.suunto_connected
                FROM user_referrals r
                JOIN profiles p ON r.invitee_uid = p.id
                WHERE r.inviter_uid = ?
                ORDER BY r.created_at DESC
                """,
                (eff_uid,),
            )
            raw_rows = cursor.fetchall()
            invited_users = []
            for row in raw_rows:
                d = dict(row)
                watch_bound = bool(
                    d.get("garmin_connected")
                    or d.get("coros_connected")
                    or d.get("apple_watch_connected")
                    or d.get("huawei_connected")
                    or d.get("suunto_connected")
                )
                invited_users.append({
                    "id": d["id"],
                    "referred_at": d.get("referred_at"),
                    "display_name": d.get("display_name") or "新跑友",
                    "avatar_url": d.get("avatar_url") or "",
                    "watch_connected": watch_bound,
                })

            # Sort watch-connected users first so qualified slots appear first
            invited_users.sort(
                key=lambda u: (1 if u["watch_connected"] else 0, u.get("referred_at") or ""),
                reverse=True,
            )

            cursor.execute(
                """
                SELECT id, name, city, invite_code, join_mode, status, created_at
                FROM clubs
                WHERE owner_id = ?
                ORDER BY created_at DESC
                """,
                (eff_uid,),
            )
            owned_clubs = [dict(row) for row in cursor.fetchall()]

        qualified_count = sum(1 for u in invited_users if u["watch_connected"])
        registered_count = len(invited_users)
        pending_watch_count = registered_count - qualified_count
        remaining_count = max(0, required_count - qualified_count)
        is_super = eff_uid in ("admin", "super_admin")
        return {
            "user_id": eff_uid,
            "invited_count": qualified_count,
            "registered_count": registered_count,
            "pending_watch_count": pending_watch_count,
            "required_count": required_count,
            "remaining_count": remaining_count,
            "can_create_club": is_super or (qualified_count >= required_count),
            "invited_users": invited_users,
            "owned_clubs": owned_clubs,
            "org_creation_enabled": False,
        }

    # ── Multi-Tenant Running Clubs API Methods ──

    @staticmethod
    def create_club(
        owner_id: str,
        name: str,
        description: Optional[str] = None,
        city: str = "上海",
        logo_url: Optional[str] = None,
        org_id: Optional[str] = None,
        join_mode: str = "free",
        invite_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        eff_owner_id = LocalStore.resolve_user_id(owner_id)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            club_id = f"club_{int(datetime.utcnow().timestamp()*1000)}_{uuid.uuid4().hex[:6]}"
            custom_code = (invite_code or "").strip().upper()
            if custom_code:
                cursor.execute("SELECT id FROM clubs WHERE UPPER(invite_code) = ?", (custom_code,))
                if cursor.fetchone():
                    raise ValueError(f"专属邀请码【{custom_code}】已被其他跑团使用，请更换一个！")
                code = custom_code
            else:
                code = generate_invite_code()
            logo = logo_url or "https://rgm.vanpower.net/api/avatars/rgm-logo.png"
            created_at = datetime.utcnow().isoformat() + "Z"
            mode = join_mode if join_mode in ("free", "invite") else "free"

            cursor.execute("""
                INSERT INTO clubs (id, org_id, name, logo_url, description, city, invite_code, owner_id, created_at, join_mode, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """, (club_id, org_id, name, logo, description, city, code, eff_owner_id, created_at, mode))

            cursor.execute("""
                INSERT INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                VALUES (?, ?, ?, 'owner', 'active', ?, 1)
            """, (f"{club_id}_{eff_owner_id}", club_id, eff_owner_id, created_at))

            conn.commit()
            return {
                "id": club_id,
                "org_id": org_id,
                "name": name,
                "logo_url": logo,
                "description": description,
                "city": city,
                "invite_code": code,
                "owner_id": eff_owner_id,
                "created_at": created_at,
                "join_mode": mode,
                "status": "active"
            }

    @staticmethod
    def get_club(club_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.*, o.name as org_name
                FROM clubs c
                LEFT JOIN organizations o ON c.org_id = o.id
                WHERE c.id = ?
            """, (club_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    get_club_by_id = get_club
    get_user = lambda uid: LocalStore.get_profile(uid)
    upsert_user = lambda uid, data: LocalStore.upsert_profile(uid, data)

    @staticmethod
    def get_user_clubs(uid: str) -> List[Dict[str, Any]]:
        eff_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.*, o.name as org_name, m.role, m.joined_at, m.privacy_consent
                FROM club_memberships m
                JOIN clubs c ON m.club_id = c.id
                LEFT JOIN organizations o ON c.org_id = o.id
                WHERE m.user_id = ? AND m.status = 'active'
                ORDER BY m.joined_at ASC
            """, (eff_uid,))
            rows = cursor.fetchall()
            clubs = [dict(r) for r in rows]
            visible_clubs = []
            for c in clubs:
                if c.get("org_id"):
                    st = LocalStore.check_org_member_status(c["org_id"], eff_uid)
                    if not st.get("is_member") and c.get("owner_id") != eff_uid and eff_uid not in ("admin", "super_admin"):
                        # Users who have not joined the organization must not see sub-clubs under that organization
                        continue
                    c["org_member_status"] = st.get("status")
                    c["org_member_info"] = st
                    is_suspended = (st.get("status") in ("expired", "suspended")) or not st.get("is_valid", True)
                    c["is_access_suspended"] = is_suspended
                    if is_suspended:
                        c["suspension_reason"] = f"该跑团隶属于【{c.get('org_name') or '大群体'}】。大团2周临时访问期已过，超期未完成所有必填资料并获管理员确认，已暂停使用。"
                else:
                    c["is_access_suspended"] = False
                visible_clubs.append(c)
            return visible_clubs

    @staticmethod
    def is_user_coach_or_owner(uid: str) -> bool:
        """Returns True if the user is an owner, coach, or admin in any active club or organization."""
        if not uid:
            return False
        eff_uid = LocalStore.resolve_user_id(uid)
        if eff_uid in ("admin", "super_admin", "u_df65d9a588c9"):
            return True
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT 1 FROM club_memberships m
                    JOIN clubs c ON m.club_id = c.id
                    WHERE m.user_id = ? AND m.status = 'active'
                      AND m.role IN ('owner', 'coach', 'admin')
                      AND COALESCE(c.status, 'active') != 'deleted'
                    LIMIT 1
                    """,
                    (eff_uid,),
                )
                if cursor.fetchone():
                    return True
                cursor.execute(
                    "SELECT 1 FROM clubs WHERE owner_id = ? AND COALESCE(status, 'active') != 'deleted' LIMIT 1",
                    (eff_uid,),
                )
                if cursor.fetchone():
                    return True
                cursor.execute(
                    """
                    SELECT 1 FROM organization_members
                    WHERE user_id = ? AND role IN ('owner', 'admin', 'coach')
                    LIMIT 1
                    """,
                    (eff_uid,),
                )
                if cursor.fetchone():
                    return True
                cursor.execute(
                    "SELECT 1 FROM organizations WHERE owner_id = ? LIMIT 1",
                    (eff_uid,),
                )
                if cursor.fetchone():
                    return True
        except Exception:
            pass
        return False

    @staticmethod
    def _fetch_club_row(where_sql: str, param: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM clubs WHERE {where_sql}", (param,))
            rows = cursor.fetchall()
            return dict(rows[0]) if rows else None

    @staticmethod
    def _notify_club_members_of_new_join(club_id: str, new_user_id: str) -> int:
        """
        Notifies all existing active members of `club_id` (excluding `new_user_id` itself)
        when a new user newly joins the club.
        """
        try:
            canonical_new_uid = LocalStore.resolve_user_id(new_user_id)
            now_str = get_beijing_iso()
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT name, owner_id FROM clubs WHERE id = ?", (club_id,))
                club_row = cursor.fetchone()
                if not club_row:
                    return 0
                club_name = club_row["name"] or "跑团"
                owner_id = LocalStore.resolve_user_id(club_row["owner_id"]) if club_row["owner_id"] else ""

                cursor.execute(
                    "SELECT display_name, real_name FROM profiles WHERE id = ? OR id = ?",
                    (canonical_new_uid, new_user_id),
                )
                prof_row = cursor.fetchone()
                new_member_name = "新跑友"
                if prof_row:
                    dn = (prof_row["display_name"] or "").strip()
                    rn = decrypt_pii(prof_row["real_name"]) if prof_row["real_name"] else ""
                    new_member_name = dn or rn or "新跑友"

                cursor.execute(
                    """
                    SELECT DISTINCT user_id, role
                    FROM club_memberships
                    WHERE club_id = ? AND status = 'active' AND user_id NOT IN (?, ?)
                    """,
                    (club_id, canonical_new_uid, new_user_id),
                )
                member_rows = cursor.fetchall()
                if not member_rows:
                    return 0

                act_id = f"club_new_member:{club_id}:{canonical_new_uid}"
                base_ts = int(time.time() * 1000)
                notified_uids = set()
                for idx, m_row in enumerate(member_rows):
                    target_uid = LocalStore.resolve_user_id(m_row["user_id"])
                    if not target_uid or target_uid in (canonical_new_uid, new_user_id) or target_uid in notified_uids:
                        continue
                    notified_uids.add(target_uid)
                    is_leader = (m_row["role"] in ("owner", "coach")) or (target_uid == owner_id)
                    if is_leader:
                        title = f"🌱 新队员入团：{new_member_name} 加入【{club_name}】"
                        content = (
                            f"欢迎新队员【{new_member_name}】加入【{club_name}】！"
                            f"您可前往【跑团 → 新队员管理】查看其加入时间、手表绑定及目标设定状态。"
                        )
                    else:
                        title = f"🎉 新队友加入【{club_name}】"
                        content = f"欢迎新跑友【{new_member_name}】加入【{club_name}】！快去跑团一起约跑打卡、互相鼓励吧！"
                    notif_id = f"notif_{base_ts}_{idx}_{uuid.uuid4().hex[:6]}"
                    cursor.execute(
                        """
                        INSERT INTO system_notifications (id, user_id, activity_id, title, content, type, wechat_sent, wechat_errmsg, is_read, created_at)
                        VALUES (?, ?, ?, ?, ?, 'club_new_member', 0, NULL, 0, ?)
                        """,
                        (notif_id, target_uid, act_id, title, content, now_str),
                    )
                conn.commit()
                return len(notified_uids)
        except Exception as e:
            logger.warning(f"Failed to notify club members of new join ({club_id}, {new_user_id}): {e}")
            return 0

    @staticmethod
    def _insert_active_club_membership(club_id: str, user_id: str, privacy_consent: bool = True):
        canonical_uid = LocalStore.resolve_user_id(user_id)
        membership_id = f"{club_id}_{user_id}"
        joined_at = datetime.utcnow().isoformat() + "Z"
        was_already_active = False
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM club_memberships WHERE club_id = ? AND user_id IN (?, ?) AND status = 'active'",
                (club_id, user_id, canonical_uid),
            )
            if cursor.fetchone():
                was_already_active = True
            cursor.execute("""
                INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                VALUES (?, ?, ?, COALESCE((SELECT role FROM club_memberships WHERE id = ?), 'member'), 'active',
                        COALESCE((SELECT joined_at FROM club_memberships WHERE id = ? AND status = 'active'), ?), ?)
            """, (membership_id, club_id, user_id, membership_id, membership_id, joined_at, int(privacy_consent)))
            conn.commit()
        if not was_already_active:
            LocalStore._notify_club_members_of_new_join(club_id, user_id)

    @staticmethod
    def _assert_club_open(club_dict: Dict[str, Any]):
        club_status = club_dict.get("status") or "active"
        if club_status == "paused":
            raise ValueError(f"跑团【{club_dict.get('name')}】当前已暂停运行，暂不接受新成员加入！")
        if club_status == "locked":
            raise ValueError(f"跑团【{club_dict.get('name')}】已被锁定，禁止新成员加入！")

    @staticmethod
    def join_club_by_code(user_id: str, invite_code: str, privacy_consent: bool = True) -> Optional[Dict[str, Any]]:
        club_dict = LocalStore._fetch_club_row("UPPER(invite_code) = ?", invite_code.strip().upper())
        if not club_dict:
            return None
        LocalStore._assert_club_open(club_dict)

        # 凭有效跑团邀请码入团：大群未加入者自动以临时成员身份入群（免大群邀请码、资料稍后补填），无需审批
        LocalStore.validate_sub_club_join_eligibility(club_dict, user_id, auto_join_org=True)
        LocalStore._insert_active_club_membership(club_dict["id"], user_id, privacy_consent)
        return club_dict

    @staticmethod
    def join_club_by_id(
        user_id: str,
        club_id: str,
        privacy_consent: bool = True,
        invite_code: Optional[str] = None,
        inviter_uid: Optional[str] = None,
        via_invite: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Joins a club by id.
        via_invite=True（来自跑团邀请卡片 / 小程序码）时实现「一键入团」：
          - 邀请码正确，或邀请人是该跑团的有效成员 → 跳过跑团邀请码校验；
          - 跑团隶属大群且用户未入大群 → 自动以临时成员身份入群（免大群邀请码、资料可稍后补填）；
          - 无需大群/跑团管理员审批，直接入团。
        """
        club_dict = LocalStore._fetch_club_row("id = ?", club_id.strip())
        if not club_dict:
            return None
        LocalStore._assert_club_open(club_dict)

        provided_code = (invite_code or "").strip().upper()
        expected_code = (club_dict.get("invite_code") or "").strip().upper()
        code_ok = bool(provided_code) and provided_code == expected_code
        inviter_ok = via_invite and LocalStore.is_active_club_inviter(club_dict["id"], inviter_uid)
        trusted_invite = code_ok or inviter_ok or (via_invite and club_dict.get("join_mode") != "invite")

        # If club requires invite code, validate it (skipped for trusted one-click invites)
        if club_dict.get("join_mode") == "invite" and not trusted_invite:
            if not provided_code:
                raise ValueError(f"跑团【{club_dict.get('name')}】已设置凭专属邀请码入团，请输入专属邀请码！")
            raise ValueError("跑团邀请码错误，请向团长核对后重新输入！")

        LocalStore.validate_sub_club_join_eligibility(club_dict, user_id, auto_join_org=trusted_invite)
        LocalStore._insert_active_club_membership(club_dict["id"], user_id, privacy_consent)
        return club_dict

    @staticmethod
    def get_club_members(club_id: str) -> List[Dict[str, Any]]:
        today = get_beijing_today()
        month_start = date(today.year, today.month, 1).isoformat()
        current_month_idx = today.month - 1

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.id as user_id, p.display_name, p.avatar_url, p.marathon_pb, p.half_pb,
                       p.ten_k_pb, p.five_k_pb, p.gender, p.date_of_birth,
                       p.garmin_connected, p.coros_connected, p.apple_watch_connected, p.huawei_connected, p.suunto_connected,
                       p.garmin_email, p.coros_account, p.huawei_account,
                       p.garmin_last_sync_at, p.coros_last_sync_at,
                       m.role, m.joined_at, m.privacy_consent, m.training_group
                FROM club_memberships m
                JOIN profiles p ON m.user_id = p.id
                WHERE m.club_id = ? AND m.status = 'active'
                ORDER BY CASE m.role WHEN 'owner' THEN 1 WHEN 'coach' THEN 2 ELSE 3 END, m.joined_at ASC
            """, (club_id,))
            rows = cursor.fetchall()
            if not rows:
                return []

            uids = [str(r["user_id"]) for r in rows]
            ph = ",".join("?" for _ in uids)
            cursor.execute(
                f"""
                SELECT user_id, COALESCE(SUM(distance_meters), 0.0) AS total_m
                FROM activities
                WHERE user_id IN ({ph}) AND start_time >= ? AND {RUNNING_SQL_FILTER}
                GROUP BY user_id
                """,
                uids + [month_start],
            )
            dist_map = {str(r["user_id"]): float(r["total_m"] or 0.0) for r in cursor.fetchall()}

            cursor.execute(f"SELECT * FROM goals WHERE user_id IN ({ph})", uids)
            goal_map = {str(r["user_id"]): dict(r) for r in cursor.fetchall()}

        res = []
        for r in rows:
            d = dict(r)
            uid = str(d["user_id"])
            if d.get("date_of_birth"):
                d["date_of_birth"] = decrypt_pii(d["date_of_birth"])
            v_meta = LocalStore.resolve_verified_runner_profile_and_pbs(uid, profile=d, query_activities=False)
            d["marathon_pb"] = v_meta.get("marathon_pb")
            d["half_pb"] = v_meta.get("half_pb")
            d["age"] = v_meta.get("age")
            d["gender"] = v_meta.get("gender")
            d["gender_label"] = v_meta.get("gender_label")
            dist_m = dist_map.get(uid, 0.0)
            d["month_km"] = round(dist_m / 1000.0, 1)
            g = LocalStore._format_goal_dict(goal_map.get(uid), today=today)
            tgts = g.get("monthly_targets") or [200.0] * 12
            month_tgt = float(tgts[current_month_idx] if current_month_idx < len(tgts) else 200.0)
            if month_tgt == 200.0 and g.get("target_distance") and float(g.get("target_distance")) != 200.0:
                month_tgt = float(g.get("target_distance"))
            d["target_km"] = month_tgt
            d["completion_rate"] = round((d["month_km"] / d["target_km"]) * 100.0, 1) if d["target_km"] > 0 else 0.0

            # Watch binding status
            watch_brands: List[str] = []
            has_garmin = bool(d.get("garmin_connected") or (d.get("garmin_email") and str(d.get("garmin_email")).strip()))
            has_coros = bool(d.get("coros_connected") or (d.get("coros_account") and str(d.get("coros_account")).strip()))
            has_apple = bool(d.get("apple_watch_connected"))
            has_huawei = bool(d.get("huawei_connected") or (d.get("huawei_account") and str(d.get("huawei_account")).strip()))
            has_suunto = bool(d.get("suunto_connected"))
            if has_garmin:
                watch_brands.append("佳明")
            if has_coros:
                watch_brands.append("高驰")
            if has_apple:
                watch_brands.append("苹果")
            if has_huawei:
                watch_brands.append("华为")
            if has_suunto:
                watch_brands.append("颂拓")
            d["garmin_connected"] = has_garmin
            d["coros_connected"] = has_coros
            d["apple_watch_connected"] = has_apple
            d["huawei_connected"] = has_huawei
            d["suunto_connected"] = has_suunto
            d["watch_brands"] = watch_brands
            d["watch_bound"] = len(watch_brands) > 0
            d["watch_connected"] = d["watch_bound"]
            d["watch_status_label"] = f"已绑{'/'.join(watch_brands)}" if watch_brands else "未绑定手表"
            d["last_sync_at"] = d.get("garmin_last_sync_at") or d.get("coros_last_sync_at") or None
            d.pop("garmin_email", None)
            d.pop("coros_account", None)
            d.pop("huawei_account", None)

            # Goal setting status
            goal_set = not bool(g.get("is_default", True))
            weekly_target_km = float(g.get("current_week_target") or g.get("weekly_target") or 50.0)
            monthly_target_km = d["target_km"]
            d["goal_set"] = goal_set
            d["weekly_target_km"] = weekly_target_km
            d["monthly_target_km"] = monthly_target_km
            d["goal_status_label"] = (
                f"周 {weekly_target_km:g}k · 月 {monthly_target_km:g}k"
                if goal_set
                else f"未设目标 (默认周{weekly_target_km:g}k/月{monthly_target_km:g}k)"
            )

            # Joined time & onboarding metadata
            raw_joined = (d.get("joined_at") or "").strip()
            bj_joined = to_beijing_iso(raw_joined) or raw_joined
            if bj_joined:
                d["joined_at_display"] = bj_joined.replace("T", " ")[:16]
                dt_obj = parse_iso_datetime(raw_joined)
                if dt_obj is not None:
                    bj_date = dt_obj.astimezone(_CN_TZ).date() if dt_obj.tzinfo else dt_obj.date()
                    days_since = max(0, (today - bj_date).days)
                else:
                    days_since = 0
                d["days_since_joined"] = days_since
                d["is_new_7d"] = days_since <= 7
                d["is_new_30d"] = days_since <= 30
                if days_since == 0:
                    d["joined_relative_label"] = "今日入团"
                elif days_since == 1:
                    d["joined_relative_label"] = "昨日入团"
                elif days_since <= 30:
                    d["joined_relative_label"] = f"{days_since}天前入团"
                else:
                    d["joined_relative_label"] = d["joined_at_display"][:10]
            else:
                d["joined_at_display"] = "早期入团"
                d["days_since_joined"] = 999
                d["is_new_7d"] = False
                d["is_new_30d"] = False
                d["joined_relative_label"] = "早期入团"

            d["onboarding_complete"] = bool(d["watch_bound"] and d["goal_set"])
            res.append(d)
        return res

    @staticmethod
    def get_club_new_members_status(club_id: str) -> Dict[str, Any]:
        """
        Returns all active members of `club_id` ordered by `joined_at DESC` (newest first),
        together with onboarding summary metrics (watch binding, goal setting, recent joins,
        training plan status, and activity count).
        """
        club = LocalStore.get_club(club_id) or {}
        members = LocalStore.get_club_members(club_id)
        uids = [m["user_id"] for m in members if m.get("user_id")]
        act_counts: Dict[str, int] = {}
        plan_uids: set = set()
        if uids:
            placeholders = ",".join("?" for _ in uids)
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT user_id, COUNT(*) FROM activities WHERE user_id IN ({placeholders}) GROUP BY user_id",
                    tuple(uids),
                )
                for uid_val, cnt in cursor.fetchall():
                    act_counts[str(uid_val)] = int(cnt or 0)
                cursor.execute(
                    f"SELECT DISTINCT user_id FROM training_plans WHERE user_id IN ({placeholders})",
                    tuple(uids),
                )
                for (uid_val,) in cursor.fetchall():
                    if uid_val:
                        plan_uids.add(str(uid_val))

        enriched: List[Dict[str, Any]] = []
        for m in members:
            item = dict(m)
            uid_val = item["user_id"]
            item["total_runs_count"] = act_counts.get(uid_val, 0)
            item["has_training_plan"] = uid_val in plan_uids
            if not item.get("watch_bound") and item["total_runs_count"] > 0:
                item["watch_bound"] = True
                item["watch_connected"] = True
                item["watch_status_label"] = "已同步运动数据"
            if not item.get("goal_set") and item["has_training_plan"]:
                item["goal_set"] = True
            item["onboarding_complete"] = bool(item.get("watch_bound") and item.get("goal_set"))
            enriched.append(item)

        # Sort newest members first (by joined_at DESC)
        enriched.sort(
            key=lambda x: (x.get("joined_at") or "", 1 if x.get("role") == "member" else 0),
            reverse=True,
        )

        summary = {
            "total_members": len(enriched),
            "new_7d_count": sum(1 for m in enriched if m.get("is_new_7d")),
            "new_30d_count": sum(1 for m in enriched if m.get("is_new_30d")),
            "watch_bound_count": sum(1 for m in enriched if m.get("watch_bound")),
            "watch_unbound_count": sum(1 for m in enriched if not m.get("watch_bound")),
            "goal_set_count": sum(1 for m in enriched if m.get("goal_set")),
            "goal_unset_count": sum(1 for m in enriched if not m.get("goal_set")),
            "pending_setup_count": sum(1 for m in enriched if not m.get("onboarding_complete")),
        }
        return {
            "club_id": club_id,
            "club_name": club.get("name") or "跑团",
            "summary": summary,
            "members": enriched,
        }

    @staticmethod
    def is_super_admin(uid: Optional[str]) -> bool:
        """Returns True if the given user ID belongs to a platform Super Administrator."""
        if not uid:
            return False
        raw = str(uid).strip()
        if raw in LocalStore.SUPER_ADMIN_UIDS or raw == "rgm_super_admin":
            return True
        canon = LocalStore.resolve_user_id(raw)
        return canon in LocalStore.SUPER_ADMIN_UIDS or canon == "rgm_super_admin"

    @staticmethod
    def are_in_same_club(uid_a: Optional[str], uid_b: Optional[str]) -> bool:
        """
        Returns True if uid_a and uid_b resolve to the same user, or share at least one
        active club membership in `club_memberships`.
        """
        if not uid_a or not uid_b:
            return False
        raw_a = str(uid_a).strip()
        raw_b = str(uid_b).strip()
        if not raw_a or not raw_b:
            return False
        if raw_a == raw_b:
            return True
        ca = LocalStore.resolve_user_id(raw_a)
        cb = LocalStore.resolve_user_id(raw_b)
        if ca == cb:
            return True
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1
                FROM club_memberships m1
                INNER JOIN club_memberships m2 ON m1.club_id = m2.club_id
                WHERE (m1.user_id = ? OR m1.user_id = ?)
                  AND (m2.user_id = ? OR m2.user_id = ?)
                  AND m1.status = 'active'
                  AND m2.status = 'active'
                LIMIT 1
                """,
                (ca, raw_a, cb, raw_b),
            )
            return cursor.fetchone() is not None

    @staticmethod
    def can_view_specific_workout_records(
        viewer_uid: Optional[str],
        target_uid: Optional[str],
    ) -> bool:
        """
        Enforces the cross-user workout record visibility rule:
        Users who are NOT in the same running club can see each other's basic status,
        but CANNOT see each other's specific workout records (activities, splits, GPS tracks, etc.).
        Allowed viewers of specific workout records:
        1. Self (viewer_uid == target_uid)
        2. Platform Super Admin
        3. Members of the same running club (are_in_same_club == True)
        4. Bound 1-on-1 Mentor / Mentee
        """
        if not viewer_uid or not target_uid:
            return False
        raw_v = str(viewer_uid).strip()
        raw_t = str(target_uid).strip()
        if not raw_v or not raw_t:
            return False
        if raw_v == raw_t:
            return True
        cv = LocalStore.resolve_user_id(raw_v)
        ct = LocalStore.resolve_user_id(raw_t)
        if cv == ct:
            return True
        if LocalStore.is_super_admin(raw_v) or LocalStore.is_super_admin(cv):
            return True
        if LocalStore.are_in_same_club(cv, ct):
            return True
        if LocalStore.is_mentor_of_runner(cv, ct) or LocalStore.is_mentor_of_runner(ct, cv):
            return True
        return False

    @staticmethod
    def _build_user_onboarding_status_dict(
        row_dict: Dict[str, Any],
        today: date,
        month_start: str,
        current_month_idx: int,
        act_counts: Dict[str, int],
        plan_uids: set,
        joined_time_field: str = "created_at",
        relative_verb: str = "加入",
    ) -> Dict[str, Any]:
        """Helper to build a standardized basic status & onboarding dict for a user profile row."""
        d = dict(row_dict)
        uid = str(d.get("user_id") or d.get("id") or "")
        d["user_id"] = uid
        if d.get("date_of_birth"):
            d["date_of_birth"] = decrypt_pii(d["date_of_birth"])
        v_meta = LocalStore.resolve_verified_runner_profile_and_pbs(uid, profile=d, query_activities=False)
        d["marathon_pb"] = v_meta.get("marathon_pb")
        d["half_pb"] = v_meta.get("half_pb")
        d["age"] = v_meta.get("age")
        d["gender"] = v_meta.get("gender")
        d["gender_label"] = v_meta.get("gender_label")

        dist_m = LocalStore.get_month_distance_meters(uid, month_start)
        d["month_km"] = round(dist_m / 1000.0, 1)
        g = LocalStore.get_goal(uid)
        tgts = g.get("monthly_targets") or [200.0] * 12
        month_tgt = float(tgts[current_month_idx] if current_month_idx < len(tgts) else 200.0)
        if month_tgt == 200.0 and g.get("target_distance") and float(g.get("target_distance")) != 200.0:
            month_tgt = float(g.get("target_distance"))
        d["target_km"] = month_tgt
        d["monthly_target_km"] = month_tgt
        d["monthly_km"] = d["month_km"]
        d["completion_rate"] = round((d["month_km"] / d["target_km"]) * 100.0, 1) if d["target_km"] > 0 else 0.0
        d["month_progress_pct"] = d["completion_rate"]

        watch_brands: List[str] = []
        has_garmin = bool(d.get("garmin_connected") or (d.get("garmin_email") and str(d.get("garmin_email")).strip()))
        has_coros = bool(d.get("coros_connected") or (d.get("coros_account") and str(d.get("coros_account")).strip()))
        has_apple = bool(d.get("apple_watch_connected"))
        has_huawei = bool(d.get("huawei_connected") or (d.get("huawei_account") and str(d.get("huawei_account")).strip()))
        has_suunto = bool(d.get("suunto_connected"))
        if has_garmin:
            watch_brands.append("佳明")
        if has_coros:
            watch_brands.append("高驰")
        if has_apple:
            watch_brands.append("苹果")
        if has_huawei:
            watch_brands.append("华为")
        if has_suunto:
            watch_brands.append("颂拓")

        total_runs = int(act_counts.get(uid, 0))
        has_plan = uid in plan_uids
        watch_bound = len(watch_brands) > 0 or total_runs > 0
        if watch_bound and not watch_brands:
            watch_status_label = "已同步运动数据"
        elif watch_brands:
            watch_status_label = f"已绑{'/'.join(watch_brands)}"
        else:
            watch_status_label = "未绑定手表"

        d["garmin_connected"] = has_garmin
        d["coros_connected"] = has_coros
        d["apple_watch_connected"] = has_apple
        d["huawei_connected"] = has_huawei
        d["suunto_connected"] = has_suunto
        d["watch_brands"] = watch_brands
        d["watch_bound"] = watch_bound
        d["watch_connected"] = watch_bound
        d["watch_status_label"] = watch_status_label
        d["last_sync_at"] = d.get("garmin_last_sync_at") or d.get("coros_last_sync_at") or None
        d.pop("garmin_email", None)
        d.pop("coros_account", None)
        d.pop("huawei_account", None)
        d.pop("wechat_openid", None)

        goal_set = (not bool(g.get("is_default", True))) or has_plan
        weekly_target_km = float(g.get("current_week_target") or g.get("weekly_target") or 50.0)
        monthly_target_km = d["target_km"]
        d["goal_set"] = goal_set
        d["weekly_target_km"] = weekly_target_km
        d["monthly_target_km"] = monthly_target_km
        d["has_training_plan"] = has_plan
        d["total_runs_count"] = total_runs
        d["goal_status_label"] = (
            f"周 {weekly_target_km:g}k · 月 {monthly_target_km:g}k"
            if goal_set
            else f"未设目标 (默认周{weekly_target_km:g}k/月{monthly_target_km:g}k)"
        )

        raw_joined = str(d.get(joined_time_field) or d.get("joined_at") or d.get("created_at") or "").strip()
        d["joined_at"] = raw_joined
        bj_joined = to_beijing_iso(raw_joined) or raw_joined
        if bj_joined:
            d["joined_at_display"] = bj_joined.replace("T", " ")[:16]
            dt_obj = parse_iso_datetime(raw_joined)
            if dt_obj is not None:
                bj_date = dt_obj.astimezone(_CN_TZ).date() if dt_obj.tzinfo else dt_obj.date()
                days_since = max(0, (today - bj_date).days)
            else:
                days_since = 0
            d["days_since_joined"] = days_since
            d["is_new_7d"] = days_since <= 7
            d["is_new_30d"] = days_since <= 30
            if days_since == 0:
                d["joined_relative_label"] = f"今日{relative_verb}"
            elif days_since == 1:
                d["joined_relative_label"] = f"昨日{relative_verb}"
            elif days_since <= 30:
                d["joined_relative_label"] = f"{days_since}天前{relative_verb}"
            else:
                d["joined_relative_label"] = d["joined_at_display"][:10]
        else:
            d["joined_at_display"] = f"早期{relative_verb}"
            d["days_since_joined"] = 999
            d["is_new_7d"] = False
            d["is_new_30d"] = False
            d["joined_relative_label"] = f"早期{relative_verb}"

        if d["month_km"] > 0:
            d["basic_status_label"] = f"本月已跑 {d['month_km']}km · 目标完成 {d['completion_rate']}%"
        elif total_runs > 0:
            d["basic_status_label"] = f"{watch_status_label} · 累计打卡 {total_runs} 次"
        elif watch_bound:
            d["basic_status_label"] = f"{watch_status_label} · 待同步首跑"
        else:
            d["basic_status_label"] = "尚未绑定手表 · 独立训练中"

        d["onboarding_complete"] = bool(watch_bound and goal_set)
        return d

    @staticmethod
    def get_runner_basic_status(target_uid: str, viewer_uid: Optional[str] = None) -> Dict[str, Any]:
        """
        Returns a user's basic status (watch binding, goal setting, monthly progress summary,
        and club affiliation summary) WITHOUT exposing specific workout records or GPS tracks.
        Safe to return when viewer_uid and target_uid are not in the same club.
        """
        canonical_target = LocalStore.resolve_user_id(target_uid)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id as user_id, display_name, avatar_url, marathon_pb, half_pb,
                       ten_k_pb, five_k_pb, gender, date_of_birth,
                       garmin_connected, coros_connected, apple_watch_connected, huawei_connected, suunto_connected,
                       garmin_email, coros_account, huawei_account,
                       garmin_last_sync_at, coros_last_sync_at, created_at
                FROM profiles
                WHERE id = ?
                """,
                (canonical_target,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("未找到该跑友信息")

            cursor.execute("SELECT COUNT(*) FROM activities WHERE user_id = ?", (canonical_target,))
            act_cnt = int((cursor.fetchone() or [0])[0] or 0)
            cursor.execute("SELECT 1 FROM training_plans WHERE user_id = ? LIMIT 1", (canonical_target,))
            has_plan = cursor.fetchone() is not None
            cursor.execute(
                """
                SELECT c.id, c.name, m.role
                FROM club_memberships m
                JOIN clubs c ON m.club_id = c.id
                WHERE m.user_id = ? AND m.status = 'active'
                """,
                (canonical_target,),
            )
            club_rows = cursor.fetchall()

        today = get_beijing_today()
        month_start = date(today.year, today.month, 1).isoformat()
        current_month_idx = today.month - 1
        item = LocalStore._build_user_onboarding_status_dict(
            dict(row),
            today=today,
            month_start=month_start,
            current_month_idx=current_month_idx,
            act_counts={canonical_target: act_cnt},
            plan_uids={canonical_target} if has_plan else set(),
            joined_time_field="created_at",
            relative_verb="加入",
        )
        club_names = [str(r["name"]) for r in club_rows if r["name"]]
        item["club_names"] = club_names
        item["is_unaffiliated"] = len(club_names) == 0
        item["role"] = str(club_rows[0]["role"]) if club_rows else "free_runner"
        item["same_club"] = LocalStore.are_in_same_club(viewer_uid, canonical_target) if viewer_uid else False
        item["can_view_records"] = LocalStore.can_view_specific_workout_records(viewer_uid, canonical_target) if viewer_uid else False
        return item

    @staticmethod
    def get_unaffiliated_users_status(viewer_uid: Optional[str] = None) -> Dict[str, Any]:
        """
        Returns all registered users who have NOT joined any active running club (`club_memberships`),
        ordered by `created_at DESC` (newest first), with their basic status (watch binding, goal setting,
        monthly progress).
        - Super Admin can view full status and drill into runner profiles / send reminders.
        - Unaffiliated users can see each other's basic status (`can_view_records=False` for other users).
        """
        canonical_viewer = LocalStore.resolve_user_id(viewer_uid) if viewer_uid else ""
        is_admin_viewer = LocalStore.is_super_admin(viewer_uid) or LocalStore.is_super_admin(canonical_viewer)

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT p.id as user_id, p.id, p.display_name, p.email, p.wechat_openid, p.invited_by,
                       p.avatar_url, p.marathon_pb, p.half_pb,
                       p.ten_k_pb, p.five_k_pb, p.gender, p.date_of_birth,
                       p.garmin_connected, p.coros_connected, p.apple_watch_connected, p.huawei_connected, p.suunto_connected,
                       p.garmin_email, p.coros_account, p.huawei_account,
                       p.garmin_last_sync_at, p.coros_last_sync_at,
                       p.created_at
                FROM profiles p
                WHERE NOT EXISTS (
                    SELECT 1 FROM club_memberships m
                    INNER JOIN clubs c ON m.club_id = c.id
                    WHERE m.user_id = p.id AND m.status = 'active'
                )
                ORDER BY p.created_at DESC
                """
            )
            raw_rows = [dict(r) for r in cursor.fetchall()]

            # Filter out synthetic test fixtures when real users exist
            non_synth = [
                r for r in raw_rows
                if not LocalStore.is_synthetic_test_user(r)
                and str(r.get("id") or "") not in ("admin", "super_admin")
            ]
            rows = non_synth if (non_synth or not raw_rows) else [
                r for r in raw_rows if str(r.get("id") or "") not in ("admin", "super_admin")
            ]

            uids = [str(r["user_id"]) for r in rows if r.get("user_id")]
            act_counts: Dict[str, int] = {}
            plan_uids: set = set()
            if uids:
                placeholders = ",".join("?" for _ in uids)
                cursor.execute(
                    f"SELECT user_id, COUNT(*) FROM activities WHERE user_id IN ({placeholders}) GROUP BY user_id",
                    tuple(uids),
                )
                for uid_val, cnt in cursor.fetchall():
                    act_counts[str(uid_val)] = int(cnt or 0)
                cursor.execute(
                    f"SELECT DISTINCT user_id FROM training_plans WHERE user_id IN ({placeholders})",
                    tuple(uids),
                )
                for (uid_val,) in cursor.fetchall():
                    if uid_val:
                        plan_uids.add(str(uid_val))

        today = get_beijing_today()
        month_start = date(today.year, today.month, 1).isoformat()
        current_month_idx = today.month - 1

        enriched: List[Dict[str, Any]] = []
        for r in rows:
            item = LocalStore._build_user_onboarding_status_dict(
                r,
                today=today,
                month_start=month_start,
                current_month_idx=current_month_idx,
                act_counts=act_counts,
                plan_uids=plan_uids,
                joined_time_field="created_at",
                relative_verb="注册",
            )
            uid_val = item["user_id"]
            item["role"] = "free_runner"
            item["is_unaffiliated"] = True
            is_self = bool(canonical_viewer and uid_val in (viewer_uid, canonical_viewer))
            item["same_club"] = is_self
            item["can_view_records"] = bool(is_admin_viewer or is_self)
            item.pop("email", None)
            item.pop("invited_by", None)
            enriched.append(item)

        enriched.sort(key=lambda x: (x.get("joined_at") or ""), reverse=True)

        summary = {
            "total_members": len(enriched),
            "new_7d_count": sum(1 for m in enriched if m.get("is_new_7d")),
            "new_30d_count": sum(1 for m in enriched if m.get("is_new_30d")),
            "watch_bound_count": sum(1 for m in enriched if m.get("watch_bound")),
            "watch_unbound_count": sum(1 for m in enriched if not m.get("watch_bound")),
            "goal_set_count": sum(1 for m in enriched if m.get("goal_set")),
            "goal_unset_count": sum(1 for m in enriched if not m.get("goal_set")),
            "pending_setup_count": sum(1 for m in enriched if not m.get("onboarding_complete")),
        }
        return {
            "scope": "unaffiliated",
            "club_id": "unaffiliated",
            "club_name": "未入团自由跑友",
            "is_super_admin_view": is_admin_viewer,
            "privacy_notice": "未在同一个跑团的用户之间仅可相互查看基本状态，不能相互查看具体运动记录等详情信息",
            "summary": summary,
            "members": enriched,
        }

    @staticmethod
    def remind_unaffiliated_user_setup(operator_uid: str, target_uid: str) -> Dict[str, Any]:
        """
        Allows Platform Super Admin to send a 1-tap reminder notification to an unaffiliated user
        to complete watch binding, weekly/monthly goal setup, or join a running club.
        """
        if not LocalStore.is_super_admin(operator_uid):
            raise PermissionError("仅平台超级管理员可向未入团跑友发送设置提醒")
        canonical_target = LocalStore.resolve_user_id(target_uid)
        basic_st = LocalStore.get_runner_basic_status(canonical_target, viewer_uid=operator_uid)

        missing_parts: List[str] = []
        if not basic_st.get("watch_bound"):
            missing_parts.append("运动手表绑定")
        if not basic_st.get("goal_set"):
            missing_parts.append("周/月跑量目标设定")
        if basic_st.get("is_unaffiliated"):
            missing_parts.append("加入心仪跑团合练")

        target_name = basic_st.get("display_name") or "跑友"
        missing_str = "、".join(missing_parts)
        title = "🔔 万跑助手提醒：完善绑表与目标设定"
        content = (
            f"欢迎使用万跑跑团助手！管理员提醒您尽快完成「{missing_str}」，"
            f"绑定运动手表并设定周/月跑量目标后即可自动同步打卡、获取 Canova 教练复盘。"
        )
        notif = LocalStore.create_system_notification(
            user_id=canonical_target,
            title=title,
            content=content,
            activity_id=f"unaffiliated_remind:{canonical_target}",
            notif_type="club_onboarding_reminder",
        )
        return {
            "success": True,
            "message": f"已向【{target_name}】发送「{missing_str}」提醒通知！",
            "notification": notif,
        }

    @staticmethod
    def remind_club_member_setup(club_id: str, operator_uid: str, target_uid: str) -> Dict[str, Any]:
        """
        Allows Club Owner / Coach / Super Admin to send a 1-tap reminder notification to a club member
        to complete watch binding and/or weekly/monthly goal setup.
        """
        if club_id in ("unaffiliated", "free_runners", "none"):
            return LocalStore.remind_unaffiliated_user_setup(operator_uid, target_uid)
        club = LocalStore.get_club(club_id)
        if not club:
            raise ValueError("跑团不存在")
        canonical_op = LocalStore.resolve_user_id(operator_uid)
        canonical_target = LocalStore.resolve_user_id(target_uid)
        members = LocalStore.get_club_members(club_id)
        is_authorized = (
            LocalStore.is_super_admin(operator_uid)
            or club.get("owner_id") in (operator_uid, canonical_op)
            or any(
                m["user_id"] in (operator_uid, canonical_op) and m.get("role") in ("owner", "coach")
                for m in members
            )
        )
        if not is_authorized:
            raise PermissionError("仅跑团团长或教练可发送新队员设置提醒")

        target_member = next(
            (m for m in members if m["user_id"] in (target_uid, canonical_target)),
            None,
        )
        if not target_member:
            raise ValueError("该跑友不在当前跑团成员列表中")

        missing_parts: List[str] = []
        if not target_member.get("watch_bound"):
            missing_parts.append("运动手表绑定")
        if not target_member.get("goal_set"):
            missing_parts.append("周/月跑量目标设定")
        if not missing_parts:
            missing_parts.append("训练课表与打卡同步")

        club_name = club.get("name") or "跑团"
        target_name = target_member.get("display_name") or "跑友"
        missing_str = "、".join(missing_parts)
        title = f"🔔 团长提醒：请完善【{club_name}】入团设置"
        content = (
            f"欢迎加入【{club_name}】！团长提醒您尽快完成「{missing_str}」，"
            f"绑定运动手表并设定周/月跑量目标后即可自动同步打卡并参与跑团排行。"
        )
        notif = LocalStore.create_system_notification(
            user_id=canonical_target,
            title=title,
            content=content,
            activity_id=f"club_remind:{club_id}:{canonical_target}",
            notif_type="club_onboarding_reminder",
        )
        return {
            "success": True,
            "message": f"已向【{target_name}】发送「{missing_str}」提醒通知！",
            "notification": notif,
        }

    @staticmethod
    def update_member_role(club_id: str, user_id: str, role: str):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if role == "owner":
                # Demote existing owner to coach
                cursor.execute("UPDATE club_memberships SET role = 'coach' WHERE club_id = ? AND role = 'owner'", (club_id,))
                cursor.execute("UPDATE clubs SET owner_id = ? WHERE id = ?", (user_id, club_id))
            cursor.execute("UPDATE club_memberships SET role = ? WHERE club_id = ? AND user_id = ?", (role, club_id, user_id))
            conn.commit()

    @staticmethod
    def update_member_training_group(club_id: str, user_id: str, training_group: Optional[str]):
        canonical_uid = LocalStore.resolve_user_id(user_id)
        grp_val = (training_group or "").strip() or None
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE club_memberships SET training_group = ? WHERE club_id = ? AND user_id IN (?, ?)",
                (grp_val, club_id, user_id, canonical_uid),
            )
            conn.commit()

    @staticmethod
    def remove_club_member(
        club_id: str,
        user_id: str,
        operator_uid: Optional[str] = None,
        is_self_leave: bool = False,
    ) -> Dict[str, Any]:
        canonical_target = LocalStore.resolve_user_id(user_id)
        canonical_op = LocalStore.resolve_user_id(operator_uid) if operator_uid else None
        club_name = "跑团"
        owner_id = ""
        target_name = "跑友"

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT status, name, owner_id FROM clubs WHERE id = ?", (club_id,))
            c_row = cursor.fetchone()
            if not c_row:
                raise ValueError("跑团不存在或已解散！")
            club_name = c_row["name"] or "跑团"
            owner_id = c_row["owner_id"] or ""
            c_status = c_row["status"] or "active"
            if c_status == "paused" and not is_self_leave:
                raise ValueError(f"跑团【{club_name}】当前处于暂停状态，禁止变更队员！")
            if c_status == "locked" and not is_self_leave:
                raise ValueError(f"跑团【{club_name}】当前处于锁定状态，禁止变更队员！")

            cursor.execute(
                "SELECT role FROM club_memberships WHERE club_id = ? AND user_id IN (?, ?)",
                (club_id, user_id, canonical_target),
            )
            m_row = cursor.fetchone()
            if not m_row:
                raise ValueError("该用户不在当前跑团中！")

            is_target_owner = (owner_id in (user_id, canonical_target)) or (m_row["role"] == "owner")
            if is_target_owner:
                if is_self_leave or (canonical_op and canonical_op == canonical_target):
                    raise ValueError("您是本跑团团长，退出跑团前请先将团长身份移交给其他成员，或在管理中心解散跑团！")
                raise ValueError("团长不可被直接移出跑团，请先将团长身份移交给其他成员！")

            if operator_uid and not is_self_leave and canonical_op != canonical_target:
                is_op_super = LocalStore.is_super_admin(operator_uid)
                is_op_owner = owner_id in (operator_uid, canonical_op)
                if not is_op_owner and not is_op_super:
                    cursor.execute(
                        "SELECT role FROM club_memberships WHERE club_id = ? AND user_id IN (?, ?)",
                        (club_id, operator_uid, canonical_op),
                    )
                    op_row = cursor.fetchone()
                    if not op_row or op_row["role"] != "owner":
                        raise PermissionError("仅跑团团长或平台超级管理员有权将队员移出跑团！")

            cursor.execute(
                "SELECT display_name, real_name FROM profiles WHERE id IN (?, ?) LIMIT 1",
                (canonical_target, user_id),
            )
            p_row = cursor.fetchone()
            if p_row:
                target_name = p_row["display_name"] or p_row["real_name"] or "跑友"

            cursor.execute(
                "DELETE FROM club_memberships WHERE club_id = ? AND user_id IN (?, ?)",
                (club_id, user_id, canonical_target),
            )
            conn.commit()

        # Send notification (non-blocking)
        try:
            if is_self_leave or (canonical_op and canonical_op == canonical_target):
                if owner_id and owner_id not in (user_id, canonical_target):
                    LocalStore.create_system_notification(
                        user_id=LocalStore.resolve_user_id(owner_id),
                        title=f"📤 队员退团通知：【{target_name}】已退出【{club_name}】",
                        content=f"队员【{target_name}】已主动退出跑团【{club_name}】。",
                        activity_id=f"club_leave:{club_id}:{canonical_target}",
                        notif_type="club_member_left",
                    )
            else:
                LocalStore.create_system_notification(
                    user_id=canonical_target,
                    title=f"📤 跑团成员变动：您已离开【{club_name}】",
                    content=f"您已被团长移出跑团【{club_name}】。您的所有个人跑步历史、手表连接与跑力数据 100% 完整保留。",
                    activity_id=f"club_remove:{club_id}:{canonical_target}",
                    notif_type="club_member_removed",
                )
        except Exception as ne:
            logger.warning(f"Failed sending club removal/leave notification: {ne}")

        return {
            "success": True,
            "club_id": club_id,
            "club_name": club_name,
            "user_id": canonical_target,
            "display_name": target_name,
        }

    @staticmethod
    def list_all_clubs() -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.*, 
                       o.name as org_name,
                       p.display_name as owner_name, 
                       p.avatar_url as owner_avatar,
                       p.email as owner_email,
                       (SELECT COUNT(*) FROM club_memberships m WHERE m.club_id = c.id AND m.status = 'active') as member_count
                FROM clubs c
                LEFT JOIN organizations o ON c.org_id = o.id
                LEFT JOIN profiles p ON c.owner_id = p.id
                ORDER BY c.created_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def list_public_clubs(user_id: Optional[str] = None, city: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        raw = LocalStore.list_all_clubs()
        user_club_ids = set()
        valid_user_org_ids = set()
        is_admin_user = False
        if user_id:
            if user_id in ("admin", "super_admin"):
                is_admin_user = True
            user_clubs = LocalStore.get_user_clubs(user_id)
            user_club_ids = {c["id"] for c in user_clubs}
            user_orgs = LocalStore.get_user_organizations(user_id)
            valid_user_org_ids = {
                o["id"] for o in user_orgs
                if o.get("status") in ("confirmed", "temporary", "pending") or
                   o.get("role") in ("owner", "admin") or
                   o.get("owner_id") == user_id
            }

        sanitized = []
        for c in raw:
            item = dict(c)
            item.pop("invite_code", None) # Strictly hide invite_code from public
            is_member = item["id"] in user_club_ids
            item["is_member"] = is_member
            status = item.get("status") or "active"

            # Paused and locked clubs are hidden from external runners
            if status in ("paused", "locked") and not is_member and not is_admin_user:
                continue

            # ── Requirement 1: Clubs belonging to an organization are INVISIBLE to users who haven't joined that organization ──
            club_org_id = item.get("org_id")
            if club_org_id:
                if not is_admin_user and club_org_id not in valid_user_org_ids:
                    continue

            # ── Requirement 2: Filter by location/city and keyword search ──
            if city and city.strip() not in ("全部", "all", "All", ""):
                target_city = city.strip()
                club_city = (item.get("city") or "").strip()
                if target_city not in club_city and club_city not in target_city:
                    continue

            if search and search.strip():
                kw = search.strip().lower()
                c_name = (item.get("name") or "").lower()
                c_desc = (item.get("description") or "").lower()
                c_city = (item.get("city") or "").lower()
                c_org = (item.get("org_name") or "").lower()
                if kw not in c_name and kw not in c_desc and kw not in c_city and kw not in c_org:
                    continue

            sanitized.append(item)
        return sanitized

    @staticmethod
    def list_public_cities(user_id: Optional[str] = None) -> List[str]:
        clubs = LocalStore.list_public_clubs(user_id=user_id)
        city_set = set()
        for c in clubs:
            ct = (c.get("city") or "").strip()
            if ct:
                city_set.add(ct)

        priority = ["全部", "上海", "北京", "深圳", "广州", "杭州", "南京", "成都", "武汉", "苏州", "西安", "厦门"]
        res = ["全部"]
        for p in priority[1:]:
            if p in city_set:
                res.append(p)
        for ct in sorted(list(city_set)):
            if ct not in res:
                res.append(ct)
        return res

    @staticmethod
    def update_club(club_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            allowed = ["name", "description", "city", "logo_url", "invite_code", "org_id", "join_mode", "status", "settings"]
            set_clauses = []
            params = []
            for k in allowed:
                if k in data:
                    val = data[k]
                    if k == "org_id":
                        val = val if val else None
                        set_clauses.append(f"{k} = ?")
                        params.append(val)
                    elif val is not None:
                        set_clauses.append(f"{k} = ?")
                        params.append(val)
            if not set_clauses:
                return LocalStore.get_club(club_id)
            params.append(club_id)
            try:
                cursor.execute(f"UPDATE clubs SET {', '.join(set_clauses)} WHERE id = ?", tuple(params))
                conn.commit()
            except sqlite3.IntegrityError as e:
                if "invite_code" in str(e).lower() or "unique" in str(e).lower():
                    raise ValueError(f"该专属邀请码【{data.get('invite_code')}】已被其他跑团使用，请更换一个！")
                raise e
            return LocalStore.get_club(club_id)

    @staticmethod
    def set_club_status(club_id: str, status: str) -> Optional[Dict[str, Any]]:
        status = status.lower().strip()
        if status not in ("active", "paused", "locked"):
            raise ValueError("跑团状态仅支持: active (正常运行), paused (暂停跑团), locked (锁定跑团)")
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE clubs SET status = ? WHERE id = ?", (status, club_id))
            conn.commit()
        return LocalStore.get_club(club_id)

    @staticmethod
    def delete_club(club_id: str) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM clubs WHERE id = ?", (club_id,))
            if not cursor.fetchone():
                return False
            cursor.execute("DELETE FROM club_events WHERE club_id = ?", (club_id,))
            cursor.execute("DELETE FROM coach_assignments WHERE club_id = ?", (club_id,))
            cursor.execute("DELETE FROM club_memberships WHERE club_id = ?", (club_id,))
            cursor.execute("UPDATE training_plans SET club_id = NULL WHERE club_id = ?", (club_id,))
            cursor.execute("DELETE FROM clubs WHERE id = ?", (club_id,))
            conn.commit()
            return True

    @staticmethod
    def set_club_owner(club_id: str, new_owner_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT owner_id FROM clubs WHERE id = ?", (club_id,))
            club = cursor.fetchone()
            if not club:
                return None
            old_owner_id = club["owner_id"]

            cursor.execute("UPDATE clubs SET owner_id = ? WHERE id = ?", (new_owner_id, club_id))

            if old_owner_id and old_owner_id != new_owner_id:
                cursor.execute("""
                    UPDATE club_memberships 
                    SET role = 'coach' 
                    WHERE club_id = ? AND user_id = ? AND role = 'owner'
                """, (club_id, old_owner_id))

            membership_id = f"{club_id}_{new_owner_id}"
            joined_at = datetime.utcnow().isoformat() + "Z"
            cursor.execute("""
                INSERT INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                VALUES (?, ?, ?, 'owner', 'active', ?, 1)
                ON CONFLICT(id) DO UPDATE SET role = 'owner', status = 'active'
            """, (membership_id, club_id, new_owner_id, joined_at))

            conn.commit()
            return LocalStore.get_club(club_id)

    @staticmethod
    def list_all_users_for_admin() -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, display_name, email, phone, avatar_url, 
                       garmin_connected, garmin_email, 
                       coros_connected, coros_account,
                       apple_watch_connected, huawei_connected, huawei_account,
                       created_at
                FROM profiles
                WHERE NOT (
                    (id LIKE 'u_test_%' OR id LIKE 'u_org_%' OR id LIKE 'u_runner_%' OR id LIKE 'u_expired_runner_%' OR id LIKE 'u_stranger_%' OR id LIKE 'u_rep_%')
                    AND (wechat_openid IS NULL OR wechat_openid = '')
                )
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["garmin_connected"] = bool(d.get("garmin_connected"))
                d["coros_connected"] = bool(d.get("coros_connected"))
                d["apple_watch_connected"] = bool(d.get("apple_watch_connected"))
                d["huawei_connected"] = bool(d.get("huawei_connected"))
                result.append(d)
            return result

    @staticmethod
    def _evaluate_club_event_lifecycle(
        ev: Dict[str, Any],
        now_bj: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Determines whether a club event (group_run or distance_challenge) is
        'upcoming', 'ongoing', or 'archived' (completed), using Beijing time (UTC+8).
        Group runs automatically transition to 'archived' 4 hours after meet_time.
        """
        if now_bj is None:
            now_bj = datetime.utcnow() + timedelta(hours=8)
        today_str = now_bj.strftime("%Y-%m-%d")

        # Sanitize meet_time consistently
        mt_clean = ""
        if ev.get("meet_time"):
            mt_clean = str(ev["meet_time"]).strip().replace("T", " ")
            if "+" in mt_clean:
                mt_clean = mt_clean.split("+")[0].strip()
            if mt_clean.endswith("Z"):
                mt_clean = mt_clean[:-1].strip()
            if ":" not in mt_clean:
                mt_clean = f"{mt_clean.split(' ')[0]} 06:30"
            elif "00:00" in mt_clean[:16]:
                mt_clean = mt_clean.replace("00:00", "06:30", 1)

        raw_status = str(ev.get("status") or "upcoming").strip().lower()
        sort_key = mt_clean or str(ev.get("start_date") or ev.get("created_at") or "")
        if raw_status in ("archived", "completed", "ended"):
            return {
                "is_archived": True,
                "lifecycle_status": "archived",
                "sanitized_meet_time": mt_clean,
                "sort_key": sort_key,
            }

        event_type = str(ev.get("event_type") or "group_run").strip().lower()
        if event_type == "distance_challenge" and not mt_clean:
            end_str = str(ev.get("end_date") or ev.get("start_date") or "")[:10]
            start_str = str(ev.get("start_date") or "")[:10]
            if end_str and end_str < today_str:
                return {
                    "is_archived": True,
                    "lifecycle_status": "archived",
                    "sanitized_meet_time": mt_clean,
                    "sort_key": end_str,
                }
            if start_str and start_str <= today_str:
                return {
                    "is_archived": False,
                    "lifecycle_status": "ongoing",
                    "sanitized_meet_time": mt_clean,
                    "sort_key": start_str,
                }
            return {
                "is_archived": False,
                "lifecycle_status": "upcoming",
                "sanitized_meet_time": mt_clean,
                "sort_key": start_str or today_str,
            }

        # Group run (or event with meet_time / start_date)
        candidate_str = mt_clean
        if not candidate_str and ev.get("start_date"):
            sd = str(ev["start_date"]).strip()[:10]
            if sd:
                candidate_str = f"{sd} 06:30"

        meet_dt: Optional[datetime] = None
        if candidate_str:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
                try:
                    meet_dt = datetime.strptime(candidate_str[:19] if "S" in fmt else candidate_str[:16], fmt)
                    break
                except ValueError:
                    continue

        if meet_dt is not None:
            sort_key = meet_dt.strftime("%Y-%m-%d %H:%M")
            if now_bj >= meet_dt + timedelta(hours=4):
                return {
                    "is_archived": True,
                    "lifecycle_status": "archived",
                    "sanitized_meet_time": mt_clean or sort_key,
                    "sort_key": sort_key,
                }
            if now_bj >= meet_dt:
                return {
                    "is_archived": False,
                    "lifecycle_status": "ongoing",
                    "sanitized_meet_time": mt_clean or sort_key,
                    "sort_key": sort_key,
                }

        return {
            "is_archived": False,
            "lifecycle_status": "upcoming",
            "sanitized_meet_time": mt_clean,
            "sort_key": sort_key,
        }

    @staticmethod
    def get_club_events(
        club_id: str,
        user_id: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[Dict[str, Any]]:
        canonical_uid = LocalStore.resolve_user_id(user_id) if user_id else None
        now_bj = datetime.utcnow() + timedelta(hours=8)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            for col_sql in [
                "ALTER TABLE club_events ADD COLUMN org_id TEXT DEFAULT NULL",
                "ALTER TABLE club_events ADD COLUMN is_org_event INTEGER DEFAULT 0",
                "ALTER TABLE club_events ADD COLUMN scope_club_ids TEXT DEFAULT 'all'",
            ]:
                try:
                    cursor.execute(col_sql)
                except Exception:
                    pass

            club_org_id = None
            org_name = None
            cursor.execute("SELECT org_id FROM clubs WHERE id = ?", (club_id,))
            c_row = cursor.fetchone()
            if c_row and c_row["org_id"]:
                club_org_id = c_row["org_id"]
                cursor.execute("SELECT name FROM organizations WHERE id = ?", (club_org_id,))
                o_row = cursor.fetchone()
                if o_row:
                    org_name = o_row["name"]

            if club_org_id:
                cursor.execute("""
                    SELECT * FROM club_events 
                    WHERE club_id = ? OR (org_id = ? AND is_org_event = 1)
                    ORDER BY 
                        CASE WHEN meet_time IS NOT NULL AND meet_time != '' THEN meet_time ELSE start_date END ASC
                """, (club_id, club_org_id))
            else:
                cursor.execute("""
                    SELECT * FROM club_events 
                    WHERE club_id = ? 
                    ORDER BY 
                        CASE WHEN meet_time IS NOT NULL AND meet_time != '' THEN meet_time ELSE start_date END ASC
                """, (club_id,))
            rows = cursor.fetchall()
            active_events: List[Dict[str, Any]] = []
            archived_events: List[Dict[str, Any]] = []
            newly_archived_ids: List[str] = []

            seen_event_ids = set()
            for r in rows:
                ev = dict(r)
                evt_id = ev["id"]
                if evt_id in seen_event_ids:
                    continue
                is_org_evt = bool(ev.get("is_org_event"))
                if is_org_evt and ev.get("club_id") != club_id:
                    raw_scope = (ev.get("scope_club_ids") or "all").strip()
                    if raw_scope and raw_scope != "all":
                        try:
                            scope_list = json.loads(raw_scope)
                            if isinstance(scope_list, list) and scope_list and club_id not in scope_list:
                                continue
                        except Exception:
                            pass
                seen_event_ids.add(evt_id)
                ev["is_org_event"] = is_org_evt
                ev["org_id"] = ev.get("org_id") or club_org_id
                ev["org_name"] = org_name if is_org_evt else None
                lc = LocalStore._evaluate_club_event_lifecycle(ev, now_bj=now_bj)
                if lc["sanitized_meet_time"] and ev.get("meet_time"):
                    ev["meet_time"] = lc["sanitized_meet_time"]

                if lc["is_archived"]:
                    if str(ev.get("status") or "").lower() not in ("archived", "completed", "ended"):
                        newly_archived_ids.append(evt_id)
                    ev["status"] = "archived"
                    ev["is_archived"] = True
                    ev["lifecycle_status"] = "archived"
                    if not include_archived:
                        continue
                else:
                    ev["is_archived"] = False
                    ev["lifecycle_status"] = lc["lifecycle_status"]

                ev["_sort_key"] = lc["sort_key"]
                ev["visibility_mode"] = ev.get("visibility_mode") or "registered_only"
                ev["recap_note"] = ev.get("recap_note") or ""
                # Query participants
                cursor.execute("""
                    SELECT p.id as participant_id, p.user_id, p.joined_at, p.status,
                           p.pace_group, p.runner_role, p.checkin_note,
                           p.manual_distance_km, p.manual_pace_str, p.manual_duration_str,
                           p.activity_id, COALESCE(p.likes_count, 0) as likes_count,
                           pr.display_name, pr.avatar_url, pr.real_name
                    FROM club_event_participants p
                    LEFT JOIN profiles pr ON p.user_id = pr.id
                    WHERE p.event_id = ? AND p.status = 'joined'
                    ORDER BY p.joined_at ASC
                """, (evt_id,))
                part_rows = cursor.fetchall()
                participants = []
                is_joined = False
                for pr_row in part_rows:
                    p_dict = dict(pr_row)
                    p_dict["display_name"] = p_dict.get("display_name") or p_dict.get("real_name") or "跑友"
                    p_dict["pace_group"] = p_dict.get("pace_group") or "🏃 有氧组"
                    p_dict["runner_role"] = p_dict.get("runner_role") or "跟跑团员"
                    participants.append(p_dict)
                    if canonical_uid and p_dict["user_id"] == canonical_uid:
                        is_joined = True

                ev["participants"] = participants
                ev["participant_count"] = len(participants)
                ev["is_joined"] = is_joined

                # Fetch creator info with fallback to club owner
                creator_id = ev.get("creator_id")
                if not creator_id:
                    cursor.execute("SELECT owner_id FROM clubs WHERE id = ?", (club_id,))
                    cl_row = cursor.fetchone()
                    if cl_row and cl_row[0]:
                        creator_id = cl_row[0]
                        ev["creator_id"] = creator_id

                if creator_id:
                    cursor.execute("SELECT display_name, avatar_url, real_name FROM profiles WHERE id = ?", (creator_id,))
                    cr = cursor.fetchone()
                    if cr:
                        ev["creator_name"] = cr["display_name"] or cr["real_name"] or "跑团跑友"
                        ev["creator_avatar"] = cr["avatar_url"] or ""
                    else:
                        ev["creator_name"] = "跑团发起"
                        ev["creator_avatar"] = ""

                    # Check creator role in club
                    cursor.execute("SELECT role FROM club_memberships WHERE club_id = ? AND user_id = ?", (club_id, creator_id))
                    cm = cursor.fetchone()
                    if cm and cm[0]:
                        ev["creator_role"] = "🏛️ 大群联合" if ev.get("is_org_event") else ("团长" if cm[0] == "owner" else ("教练" if cm[0] == "coach" else "发起人"))
                    else:
                        cursor.execute("SELECT owner_id FROM clubs WHERE id = ?", (club_id,))
                        clo = cursor.fetchone()
                        if ev.get("is_org_event"):
                            ev["creator_role"] = "🏛️ 大群联合"
                        elif clo and clo[0] == creator_id:
                            ev["creator_role"] = "团长"
                        else:
                            ev["creator_role"] = "发起人"
                else:
                    ev["creator_name"] = "跑团组织"
                    ev["creator_avatar"] = None
                    ev["creator_role"] = "🏛️ 大群联合" if ev.get("is_org_event") else "发起人"

                ev["repeat_rule"] = ev.get("repeat_rule") or "none"
                ev["repeat_group_id"] = ev.get("repeat_group_id")

                # Default fallback cover image for group run if not set
                if not ev.get("cover_image"):
                    ev["cover_image"] = "https://images.unsplash.com/photo-1476480862126-209bfaa8edc8?w=800&auto=format&fit=crop&q=80"

                if ev["is_archived"]:
                    archived_events.append(ev)
                else:
                    active_events.append(ev)

            if newly_archived_ids:
                cursor.executemany(
                    "UPDATE club_events SET status = 'archived' WHERE id = ?",
                    [(eid,) for eid in newly_archived_ids],
                )
                conn.commit()

            active_events.sort(key=lambda x: (0 if x.get("is_org_event") else 1, x.get("_sort_key") or ""))
            archived_events.sort(key=lambda x: x.get("_sort_key") or "", reverse=True)
            combined = active_events + archived_events if include_archived else active_events
            for item in combined:
                item.pop("_sort_key", None)
            return combined

    @staticmethod
    def create_club_event(club_id: str, data: Dict[str, Any]) -> str:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Ensure columns exist dynamically
            for col_sql in [
                "ALTER TABLE club_events ADD COLUMN repeat_rule TEXT DEFAULT 'none'",
                "ALTER TABLE club_events ADD COLUMN repeat_group_id TEXT DEFAULT NULL",
                "ALTER TABLE club_events ADD COLUMN visibility_mode TEXT DEFAULT 'registered_only'",
                "ALTER TABLE club_events ADD COLUMN recap_note TEXT DEFAULT ''",
                "ALTER TABLE club_events ADD COLUMN org_id TEXT DEFAULT NULL",
                "ALTER TABLE club_events ADD COLUMN is_org_event INTEGER DEFAULT 0",
                "ALTER TABLE club_events ADD COLUMN scope_club_ids TEXT DEFAULT 'all'",
            ]:
                try:
                    cursor.execute(col_sql)
                except Exception:
                    pass

            now_iso = datetime.utcnow().isoformat() + "Z"
            creator_id = data.get("creator_id") or data.get("operator_uid")
            if creator_id:
                creator_id = LocalStore.resolve_user_id(creator_id)

            meet_time_str = data.get("meet_time") or data.get("start_date") or date.today().isoformat()
            cover_img = data.get("cover_image") or "https://images.unsplash.com/photo-1476480862126-209bfaa8edc8?w=800&auto=format&fit=crop&q=80"
            evt_type = data.get("event_type") or "group_run"
            repeat_rule = data.get("repeat_rule") or "none"
            repeat_weeks = int(data.get("repeat_weeks") or 1)
            visibility_mode = data.get("visibility_mode") or "registered_only"
            recap_note = data.get("recap_note") or ""
            if repeat_rule != "weekly" or repeat_weeks <= 1:
                repeat_weeks = 1

            repeat_group_id = f"rgrp_{int(time.time()*1000)}" if repeat_rule == "weekly" else None
            first_event_id = None

            # Parse meet_time to get date and time parts
            base_date = None
            time_part = "06:30"
            try:
                cleaned_mt = meet_time_str.replace("T", " ")
                parts = cleaned_mt.split(" ")
                date_str = parts[0]
                base_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if len(parts) > 1 and parts[1]:
                    time_part = parts[1][:5]
                    if time_part == "00:00":
                        time_part = "06:30"
            except Exception:
                base_date = date.today()

            for i in range(repeat_weeks):
                cur_date = base_date + timedelta(days=7 * i)
                cur_meet_time = f"{cur_date.isoformat()} {time_part}" if evt_type == "group_run" else cur_date.isoformat()
                event_id = f"event_{int(datetime.utcnow().timestamp()*1000)}_{i}"
                if first_event_id is None:
                    first_event_id = event_id

                cursor.execute("""
                    INSERT INTO club_events (
                        id, club_id, title, event_type, start_date, end_date, target_km, rules,
                        meet_time, location, location_detail, latitude, longitude, cover_image,
                        pace_requirement, creator_id, status, max_participants, created_at,
                        repeat_rule, repeat_group_id, visibility_mode, recap_note,
                        org_id, is_org_event, scope_club_ids
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_id,
                    club_id,
                    data.get("title") or "跑团约跑",
                    evt_type,
                    cur_date.isoformat(),
                    cur_date.isoformat() if evt_type == "group_run" else (data.get("end_date") or (date.today() + timedelta(days=30)).isoformat()),
                    float(data.get("target_km") or 10.0),
                    data.get("rules") or data.get("description") or "健康跑，欢迎各位跑友报名！",
                    cur_meet_time,
                    data.get("location") or "跑团集合点",
                    data.get("location_detail") or "",
                    data.get("latitude"),
                    data.get("longitude"),
                    cover_img,
                    data.get("pace_requirement") or "轻松配速",
                    creator_id,
                    data.get("status") or "upcoming",
                    int(data.get("max_participants") or 0),
                    now_iso,
                    repeat_rule,
                    repeat_group_id,
                    visibility_mode,
                    recap_note,
                    data.get("org_id"),
                    1 if data.get("is_org_event") else 0,
                    data.get("scope_club_ids") or "all",
                ))

                # Automatically join creator to each session as pacer / organizer
                if creator_id:
                    part_id = f"part_{int(time.time() * 1000)}_{i}"
                    cursor.execute("""
                        INSERT OR IGNORE INTO club_event_participants (
                            id, event_id, club_id, user_id, joined_at, status, pace_group, runner_role
                        )
                        VALUES (?, ?, ?, ?, ?, 'joined', '🏃 有氧组', '🐰 领跑兔')
                    """, (part_id, event_id, club_id, creator_id, now_iso))

            conn.commit()
            return first_event_id

    @staticmethod
    def update_club_event(club_id: str, event_id: str, data: Dict[str, Any]):
        mt_val = data.get("meet_time")
        if mt_val:
            mt_str = str(mt_val).strip()
            if ":" not in mt_str:
                mt_val = f"{mt_str.split(' ')[0]} 06:30"
            elif "00:00" in mt_str:
                mt_val = mt_str.replace("00:00", "06:30")

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE club_events 
                SET title = ?, event_type = ?, start_date = ?, end_date = ?, target_km = ?, rules = ?,
                    meet_time = ?, location = ?, location_detail = ?, latitude = ?, longitude = ?,
                    cover_image = ?, pace_requirement = ?, max_participants = ?, status = ?,
                    repeat_rule = COALESCE(?, repeat_rule),
                    visibility_mode = COALESCE(?, visibility_mode),
                    recap_note = COALESCE(?, recap_note)
                WHERE id = ? AND club_id = ?
            """, (
                data.get("title") or "跑团约跑",
                data.get("event_type") or "group_run",
                data.get("start_date") or mt_val,
                data.get("end_date"),
                float(data.get("target_km") or 10.0),
                data.get("rules") or data.get("description") or "",
                mt_val,
                data.get("location"),
                data.get("location_detail"),
                data.get("latitude"),
                data.get("longitude"),
                data.get("cover_image"),
                data.get("pace_requirement"),
                int(data.get("max_participants") or 0),
                data.get("status") or "upcoming",
                data.get("repeat_rule"),
                data.get("visibility_mode"),
                data.get("recap_note"),
                event_id,
                club_id
            ))
            conn.commit()

    @staticmethod
    def archive_club_event(club_id: str, event_id: str) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if club_id and club_id != "auto":
                cursor.execute(
                    "UPDATE club_events SET status = 'archived' WHERE id = ? AND club_id = ?",
                    (event_id, club_id),
                )
            else:
                cursor.execute(
                    "UPDATE club_events SET status = 'archived' WHERE id = ?",
                    (event_id,),
                )
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def delete_club_event(club_id: str, event_id: str):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM club_event_comments WHERE event_id = ?", (event_id,))
            cursor.execute("DELETE FROM club_event_participants WHERE event_id = ?", (event_id,))
            cursor.execute("DELETE FROM club_events WHERE id = ? AND club_id = ?", (event_id, club_id))
            conn.commit()

    @staticmethod
    def join_club_event(
        club_id: str,
        event_id: str,
        user_id: str,
        pace_group: Optional[str] = None,
        runner_role: Optional[str] = None,
        checkin_note: Optional[str] = None,
        display_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        phone: Optional[str] = None,
        auto_join_club: bool = True,
        join_event: bool = True,
        inviter_uid: Optional[str] = None,
    ) -> Dict[str, Any]:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        auto_joined_club = False
        account_activated = False
        club_name = "跑团"
        final_display_name = (display_name or "").strip()

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if club_id and club_id != "auto":
                cursor.execute("SELECT * FROM club_events WHERE id = ? AND club_id = ?", (event_id, club_id))
            else:
                cursor.execute("SELECT * FROM club_events WHERE id = ?", (event_id,))
            evt_row = cursor.fetchone()
            if not evt_row:
                cursor.execute("SELECT * FROM club_events WHERE id = ?", (event_id,))
                evt_row = cursor.fetchone()
            if not evt_row:
                raise ValueError("约跑活动不存在或已下架")
            evt = dict(evt_row)
            eff_club_id = evt["club_id"]

            lc = LocalStore._evaluate_club_event_lifecycle(evt)
            if lc["is_archived"] and join_event:
                if str(evt.get("status") or "").lower() not in ("archived", "completed", "ended"):
                    cursor.execute("UPDATE club_events SET status = 'archived' WHERE id = ?", (event_id,))
                    conn.commit()
                raise ValueError("该约跑活动已完成并归档，无法继续报名")

            cursor.execute("SELECT name, status, org_id FROM clubs WHERE id = ?", (eff_club_id,))
            club_row = cursor.fetchone()
            club_org_id = None
            if club_row:
                club_name = club_row["name"] or "跑团"
                club_org_id = club_row["org_id"]

            now_iso = datetime.utcnow().isoformat() + "Z"
            is_profile_incomplete = False
            is_existing_user = False

            # 1. Activate / link profile seamlessly (existing user links profile; new user created directly, profile details can be filled later)
            cursor.execute("SELECT id, display_name, real_name, avatar_url, phone FROM profiles WHERE id = ?", (canonical_uid,))
            prof_row = cursor.fetchone()
            default_avatar = "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"
            if not prof_row:
                eff_name = final_display_name or f"跑者_{canonical_uid[-4:]}"
                eff_avatar = (avatar_url or "").strip() or default_avatar
                cursor.execute("""
                    INSERT INTO profiles (id, display_name, avatar_url, phone, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (canonical_uid, eff_name, eff_avatar, (phone or "").strip() or None, now_iso))
                final_display_name = eff_name
                account_activated = True
                is_profile_incomplete = not bool((display_name or "").strip() and (phone or "").strip())
            else:
                is_existing_user = True
                old_name = (prof_row["display_name"] or "").strip()
                dec_real_name = (decrypt_pii(prof_row["real_name"]) if prof_row["real_name"] else "").strip()
                is_placeholder = (
                    (not old_name)
                    or old_name in ("微信跑者", "微信用户", "跑者")
                    or old_name.startswith("跑者_")
                    or old_name.startswith("微信跑者_")
                )
                if final_display_name and final_display_name != old_name:
                    cursor.execute("UPDATE profiles SET display_name = ?, updated_at = ? WHERE id = ?", (final_display_name, now_iso, canonical_uid))
                    if is_placeholder:
                        account_activated = True
                elif is_placeholder and dec_real_name:
                    final_display_name = dec_real_name
                else:
                    final_display_name = old_name or f"跑者_{canonical_uid[-4:]}"
                if avatar_url and avatar_url.strip():
                    cursor.execute("UPDATE profiles SET avatar_url = ?, updated_at = ? WHERE id = ?", (avatar_url.strip(), now_iso, canonical_uid))
                if phone and phone.strip():
                    cursor.execute("UPDATE profiles SET phone = ?, updated_at = ? WHERE id = ?", (phone.strip(), now_iso, canonical_uid))
                eff_phone = (phone or prof_row["phone"] or "").strip()
                name_still_placeholder = (
                    (not final_display_name)
                    or final_display_name in ("微信跑者", "微信用户", "跑者")
                    or final_display_name.startswith("跑者_")
                    or final_display_name.startswith("微信跑者_")
                )
                is_profile_incomplete = bool(name_still_placeholder or (not eff_phone and not dec_real_name))

            # 2. Auto-join the group run's running club (and parent organization temporary access if applicable)
            target_join_cid = (
                club_id
                if (bool(evt.get("is_org_event")) and club_id and club_id != "auto")
                else eff_club_id
            )
            if auto_join_club and target_join_cid:
                cursor.execute(
                    "SELECT status, role FROM club_memberships WHERE club_id = ? AND user_id = ?",
                    (target_join_cid, canonical_uid)
                )
                cm_row = cursor.fetchone()
                if not cm_row or cm_row["status"] != "active":
                    membership_id = f"{target_join_cid}_{canonical_uid}"
                    role_keep = cm_row["role"] if (cm_row and cm_row["role"]) else "member"
                    cursor.execute("""
                        INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                        VALUES (?, ?, ?, ?, 'active', ?, 1)
                    """, (membership_id, target_join_cid, canonical_uid, role_keep, now_iso))
                    auto_joined_club = True
                if club_org_id:
                    cursor.execute(
                        "SELECT id FROM organization_members WHERE org_id = ? AND user_id = ?",
                        (club_org_id, canonical_uid)
                    )
                    if not cursor.fetchone():
                        enc_name = encrypt_pii(final_display_name or "跑友")
                        enc_phone = encrypt_pii((phone or "").strip()) if (phone and phone.strip()) else ""
                        cursor.execute("""
                            INSERT OR IGNORE INTO organization_members (
                                id, org_id, user_id, real_name, gender, date_of_birth, class_name, phone, id_card, role, status, joined_at
                            ) VALUES (?, ?, ?, ?, '', '', '', ?, '', 'member', 'temporary', ?)
                        """, (f"{club_org_id}_{canonical_uid}", club_org_id, canonical_uid, enc_name, enc_phone, now_iso))

            # 3. Join the group run event
            if join_event:
                max_p = evt.get("max_participants") or 0
                if max_p > 0:
                    cursor.execute("SELECT COUNT(*) FROM club_event_participants WHERE event_id = ? AND status = 'joined' AND user_id != ?", (event_id, canonical_uid))
                    current_p = cursor.fetchone()[0]
                    if current_p >= max_p:
                        raise ValueError(f"抱歉，该约跑活动人数已达上限（{max_p}人）！")

                part_id = f"part_{int(time.time() * 1000)}"
                pg_val = pace_group or "🏃 有氧组"
                role_val = runner_role or "🏃 跟跑团员"
                note_val = checkin_note or ""
                cursor.execute("""
                    INSERT INTO club_event_participants (
                        id, event_id, club_id, user_id, joined_at, status, pace_group, runner_role, checkin_note
                    )
                    VALUES (?, ?, ?, ?, ?, 'joined', ?, ?, ?)
                    ON CONFLICT(event_id, user_id) DO UPDATE SET
                        status = 'joined',
                        joined_at = excluded.joined_at,
                        pace_group = COALESCE(NULLIF(?, ''), club_event_participants.pace_group),
                        runner_role = COALESCE(NULLIF(?, ''), club_event_participants.runner_role),
                        checkin_note = CASE WHEN ? != '' THEN ? ELSE club_event_participants.checkin_note END
                """, (part_id, event_id, eff_club_id, canonical_uid, now_iso, pg_val, role_val, note_val, pace_group or "", runner_role or "", note_val, note_val))

            conn.commit()

        # Notify existing club members if this user newly joined the club via group run
        if auto_joined_club and eff_club_id:
            try:
                LocalStore._notify_club_members_of_new_join(eff_club_id, canonical_uid)
            except Exception as e:
                logger.warning(f"Notify club members on auto_join_club skipped: {e}")

        # Record referral if inviter_uid was provided
        if inviter_uid and inviter_uid.strip() and inviter_uid.strip() != canonical_uid:
            try:
                LocalStore.record_referral(inviter_uid.strip(), canonical_uid)
            except Exception as e:
                logger.warning(f"Referral record skipped: {e}")

        # Send in-app system notification for reminder
        try:
            meet_time_str = evt.get("meet_time") or evt.get("start_date") or "近期"
            loc_str = evt.get("location") or "跑团指定地点"
            club_tag = f"已为您同步开通账号并加入【{club_name}】跑团！\n" if auto_joined_club else ""
            LocalStore.create_system_notification(
                user_id=canonical_uid,
                title=f"🏃【约跑提醒】报名成功！",
                content=f"{club_tag}您已成功加入【{evt.get('title', '跑团约跑')}】！\n⏰ 时间：{meet_time_str}\n📍 集合地点：{loc_str}\n请提前做好热身与补给，准时赴约！",
                notif_type="group_run_reminder"
            )
        except Exception as e:
            logger.warning(f"Failed to record group run notification: {e}")

        msg = f"已加入【{club_name}】并成功报名约跑！个人资料可稍后补齐" if (auto_joined_club and is_profile_incomplete) else (
            f"已关联您的跑者资料并加入【{club_name}】，约跑已同步至首页" if auto_joined_club else "报名成功！约跑已同步至您的首页"
        )
        return {
            "success": True,
            "message": msg,
            "is_joined": bool(join_event),
            "is_club_member": True,
            "auto_joined_club": auto_joined_club,
            "account_activated": account_activated,
            "is_existing_user": is_existing_user,
            "is_profile_incomplete": is_profile_incomplete,
            "club_id": eff_club_id,
            "club_name": club_name,
            "display_name": final_display_name,
            "event_title": evt.get("title"),
            "meet_time": evt.get("meet_time"),
            "location": evt.get("location")
        }

    @staticmethod
    def _pace_str_to_seconds(pace_str: Optional[str]) -> Optional[int]:
        """Helper to parse '5''12\"' or '5:12' into total seconds per km (e.g., 312)."""
        if not pace_str:
            return None
        s = str(pace_str).strip().replace('"', '').replace("''", ":").replace("'", ":").replace("/km", "").strip(":")
        parts = [p for p in s.split(":") if p.strip().isdigit()]
        if len(parts) >= 2:
            mins = int(parts[0])
            secs = int(parts[1])
            if 120 <= mins * 60 + secs <= 1200:
                return mins * 60 + secs
        return None

    @staticmethod
    def _seconds_to_pace_str(sec_per_km: Optional[float]) -> str:
        if not sec_per_km or sec_per_km <= 0:
            return "--"
        m = int(sec_per_km // 60)
        s = int(round(sec_per_km % 60))
        if s == 60:
            m += 1
            s = 0
        return f"{m}'{s:02d}\""

    @staticmethod
    def _seconds_to_duration_str(total_sec: Optional[float]) -> str:
        if not total_sec or total_sec <= 0:
            return "--"
        total_sec = int(total_sec)
        h = total_sec // 3600
        m = (total_sec % 3600) // 60
        s = total_sec % 60
        if h > 0:
            return f"{h}h{m:02d}m"
        return f"{m}分{s:02d}秒"

    @staticmethod
    def get_club_event_detail(club_id: str, event_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Returns comprehensive group run detail, including:
        - Event metadata + club info + creator info
        - Visibility & permission flags (`visibility_mode`, `can_view_roster`, `can_manage`, `is_joined`, `is_club_member`)
        - Final participant list enriched with actual running metrics (distance_km, pace, duration, heartrate, calories)
          matched from watch activities on the event date (or bound activity_id / manual check-in), plus 30-day reference pace
        - Team collective statistics & MVP badges (`mvp_longest`, `mvp_fastest`, `mvp_earliest`)
        - Pace group breakdown (`pace_groups_summary`)
        - Pre-generated social copy (`share_solitaire_text`, `share_battle_report_text`)
        - Event comments (`comments`) and viewer's recent activities (`my_recent_activities`) for 1-click run binding.
        """
        canonical_uid = LocalStore.resolve_user_id(user_id) if user_id else None
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if club_id and club_id != "auto":
                cursor.execute("""
                    SELECT e.*, c.name as club_name, c.logo_url as club_logo, c.owner_id as club_owner_id,
                           c.city as club_city, c.description as club_description, c.join_mode as club_join_mode
                    FROM club_events e
                    LEFT JOIN clubs c ON e.club_id = c.id
                    WHERE e.id = ? AND e.club_id = ?
                """, (event_id, club_id))
            else:
                cursor.execute("""
                    SELECT e.*, c.name as club_name, c.logo_url as club_logo, c.owner_id as club_owner_id,
                           c.city as club_city, c.description as club_description, c.join_mode as club_join_mode
                    FROM club_events e
                    LEFT JOIN clubs c ON e.club_id = c.id
                    WHERE e.id = ?
                """, (event_id,))
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    SELECT e.*, c.name as club_name, c.logo_url as club_logo, c.owner_id as club_owner_id,
                           c.city as club_city, c.description as club_description, c.join_mode as club_join_mode
                    FROM club_events e
                    LEFT JOIN clubs c ON e.club_id = c.id
                    WHERE e.id = ?
                """, (event_id,))
                row = cursor.fetchone()
            if not row:
                raise ValueError("约跑活动不存在或已删除")

            ev = dict(row)
            eff_club_id = ev.get("club_id") or club_id
            ev["club_id"] = eff_club_id
            ev["visibility_mode"] = ev.get("visibility_mode") or "registered_only"
            ev["recap_note"] = ev.get("recap_note") or ""
            if not ev.get("cover_image") or "photo-1476480862126-209bfaa8edc8" in str(ev.get("cover_image", "")):
                ev["cover_image"] = ev.get("club_logo") or "https://images.unsplash.com/photo-1476480862126-209bfaa8edc8?w=800&auto=format&fit=crop&q=80"

            # Sanitize meet_time & evaluate lifecycle (auto-archive completed runs)
            lc = LocalStore._evaluate_club_event_lifecycle(ev)
            if lc["sanitized_meet_time"] and ev.get("meet_time"):
                ev["meet_time"] = lc["sanitized_meet_time"]
            if lc["is_archived"]:
                if str(ev.get("status") or "").lower() not in ("archived", "completed", "ended"):
                    cursor.execute("UPDATE club_events SET status = 'archived' WHERE id = ?", (event_id,))
                    conn.commit()
                ev["status"] = "archived"
                ev["is_archived"] = True
                ev["lifecycle_status"] = "archived"
            else:
                ev["is_archived"] = False
                ev["lifecycle_status"] = lc["lifecycle_status"]

            event_date_str = str(ev.get("meet_time") or ev.get("start_date") or "")[:10]

            # Creator info
            creator_id = ev.get("creator_id") or ev.get("club_owner_id")
            ev["creator_id"] = creator_id
            if creator_id:
                cursor.execute("SELECT display_name, avatar_url, real_name FROM profiles WHERE id = ?", (creator_id,))
                cr = cursor.fetchone()
                ev["creator_name"] = (cr["display_name"] or cr["real_name"] or "跑团发起人") if cr else "跑团发起人"
                ev["creator_avatar"] = (cr["avatar_url"] or "") if cr else ""
            else:
                ev["creator_name"] = "跑团发起人"
                ev["creator_avatar"] = ""

            # Check viewer's profile & club membership & admin permissions
            is_club_member = False
            viewer_club_role = "guest"
            viewer_profile = {
                "display_name": "",
                "avatar_url": "",
                "phone": "",
                "is_new_account": True
            }
            if canonical_uid:
                cursor.execute("SELECT display_name, real_name, avatar_url, phone FROM profiles WHERE id = ?", (canonical_uid,))
                vp_row = cursor.fetchone()
                if vp_row:
                    v_name = (vp_row["display_name"] or "").strip()
                    r_name = decrypt_pii(vp_row["real_name"]) if vp_row["real_name"] else ""
                    if (not v_name or v_name in ("微信跑者", "微信用户", "跑者") or v_name.startswith("跑者_") or v_name.startswith("微信跑者_")) and r_name:
                        v_name = r_name.strip()
                    is_placeholder = (not v_name) or v_name in ("微信跑者", "微信用户", "跑者") or v_name.startswith("跑者_") or v_name.startswith("微信跑者_")
                    viewer_profile = {
                        "display_name": v_name,
                        "avatar_url": vp_row["avatar_url"] or "",
                        "phone": vp_row["phone"] or "",
                        "is_new_account": is_placeholder
                    }

                cursor.execute("SELECT role, status FROM club_memberships WHERE club_id = ? AND user_id = ?", (eff_club_id, canonical_uid))
                cm = cursor.fetchone()
                if cm and cm["status"] == "active":
                    is_club_member = True
                    viewer_club_role = cm["role"] or "member"
                elif ev.get("club_owner_id") == canonical_uid:
                    is_club_member = True
                    viewer_club_role = "owner"
                if is_club_member:
                    viewer_profile["is_new_account"] = False
            ev["viewer_profile"] = viewer_profile

            can_manage = bool(
                canonical_uid and (
                    canonical_uid == creator_id
                    or canonical_uid == ev.get("club_owner_id")
                    or viewer_club_role in ("owner", "coach", "admin")
                )
            )

            # Query joined participants
            cursor.execute("""
                SELECT p.id as participant_id, p.user_id, p.joined_at, p.status,
                       p.pace_group, p.runner_role, p.checkin_note,
                       p.manual_distance_km, p.manual_pace_str, p.manual_duration_str,
                       p.activity_id, COALESCE(p.likes_count, 0) as likes_count,
                       pr.display_name, pr.avatar_url, pr.real_name
                FROM club_event_participants p
                LEFT JOIN profiles pr ON p.user_id = pr.id
                WHERE p.event_id = ? AND p.status = 'joined'
                ORDER BY p.joined_at ASC
            """, (event_id,))
            part_rows = cursor.fetchall()

            is_joined = any(canonical_uid and r["user_id"] == canonical_uid for r in part_rows)

            # Determine visibility access for the full participant roster & running stats
            vis_mode = ev["visibility_mode"]
            if can_manage or is_joined or vis_mode == "public":
                can_view_roster = True
            elif vis_mode == "club_members" and is_club_member:
                can_view_roster = True
            else:
                can_view_roster = False

            participants_full = []
            my_participation = None
            thirty_days_ago = (date.today() - timedelta(days=30)).isoformat()

            for idx, pr_row in enumerate(part_rows):
                p = dict(pr_row)
                uid = p["user_id"]
                p["join_order"] = idx + 1
                p["display_name"] = p.get("display_name") or p.get("real_name") or f"跑友{idx+1}"
                p["pace_group"] = p.get("pace_group") or "🏃 有氧组"
                p["runner_role"] = p.get("runner_role") or ("🐰 领跑兔" if uid == creator_id else "🏃 跟跑团员")
                p["checkin_note"] = p.get("checkin_note") or ""
                p["likes_count"] = int(p.get("likes_count") or 0)

                # 1. Try matched activity (explicitly bound activity_id or same-day activity on event_date_str)
                act_row = None
                if p.get("activity_id"):
                    cursor.execute("""
                        SELECT id, name, start_time, distance_meters, moving_time_seconds,
                               avg_pace_str, average_heartrate, calories, trimp
                        FROM activities WHERE id = ? AND user_id = ?
                    """, (p["activity_id"], uid))
                    act_row = cursor.fetchone()

                if not act_row and event_date_str:
                    cursor.execute("""
                        SELECT id, name, start_time, distance_meters, moving_time_seconds,
                               avg_pace_str, average_heartrate, calories, trimp
                        FROM activities
                        WHERE user_id = ? AND substr(start_time, 1, 10) = ?
                        ORDER BY distance_meters DESC LIMIT 1
                    """, (uid, event_date_str))
                    act_row = cursor.fetchone()

                # 2. Query 30-day reference stats for this runner (so even before the run, teammates see their usual pace & mileage)
                cursor.execute("""
                    SELECT COALESCE(SUM(distance_meters), 0) as recent_meters,
                           COUNT(*) as recent_runs,
                           AVG(CASE WHEN distance_meters >= 1000 AND moving_time_seconds > 0
                               THEN (moving_time_seconds * 1000.0 / distance_meters) ELSE NULL END) as avg_sec_per_km
                    FROM activities
                    WHERE user_id = ? AND substr(start_time, 1, 10) >= ?
                """, (uid, thirty_days_ago))
                ref_row = cursor.fetchone()
                recent_30d_km = round((ref_row["recent_meters"] or 0) / 1000.0, 1) if ref_row else 0.0
                ref_pace_str = LocalStore._seconds_to_pace_str(ref_row["avg_sec_per_km"]) if (ref_row and ref_row["avg_sec_per_km"]) else "5'30\""

                # Resolve final displayed running performance for this group run
                has_completed_run = False
                data_source = "reference"  # 'watch_sync' | 'manual_checkin' | 'reference'
                actual_km = 0.0
                actual_pace_str = "--"
                actual_duration_str = "--"
                actual_hr = None
                actual_calories = None
                pace_seconds = None

                if act_row and (act_row["distance_meters"] or 0) > 0:
                    has_completed_run = True
                    data_source = "watch_sync"
                    actual_km = round((act_row["distance_meters"] or 0) / 1000.0, 2)
                    mv_sec = act_row["moving_time_seconds"] or 0
                    actual_duration_str = LocalStore._seconds_to_duration_str(mv_sec)
                    if act_row["avg_pace_str"]:
                        actual_pace_str = act_row["avg_pace_str"]
                        pace_seconds = LocalStore._pace_str_to_seconds(actual_pace_str)
                    if not pace_seconds and actual_km > 0 and mv_sec > 0:
                        pace_seconds = int(mv_sec / actual_km)
                        actual_pace_str = LocalStore._seconds_to_pace_str(pace_seconds)
                    actual_hr = int(round(act_row["average_heartrate"])) if act_row["average_heartrate"] else None
                    actual_calories = int(round(act_row["calories"])) if act_row["calories"] else int(round(actual_km * 62))
                elif p.get("manual_distance_km") and float(p.get("manual_distance_km") or 0) > 0:
                    has_completed_run = True
                    data_source = "manual_checkin"
                    actual_km = round(float(p["manual_distance_km"]), 2)
                    actual_pace_str = p.get("manual_pace_str") or ref_pace_str
                    pace_seconds = LocalStore._pace_str_to_seconds(actual_pace_str)
                    if p.get("manual_duration_str"):
                        actual_duration_str = p["manual_duration_str"]
                    elif pace_seconds and actual_km > 0:
                        actual_duration_str = LocalStore._seconds_to_duration_str(pace_seconds * actual_km)
                    actual_calories = int(round(actual_km * 62))

                p["has_completed_run"] = has_completed_run
                p["data_source"] = data_source
                p["actual_distance_km"] = actual_km
                p["actual_pace_str"] = actual_pace_str
                p["actual_duration_str"] = actual_duration_str
                p["actual_heartrate"] = actual_hr
                p["actual_calories"] = actual_calories
                p["pace_seconds"] = pace_seconds
                p["reference_pace_str"] = ref_pace_str
                p["recent_30d_km"] = recent_30d_km
                p["display_distance_km"] = actual_km if has_completed_run else float(ev.get("target_km") or 10.0)
                p["display_pace_str"] = actual_pace_str if has_completed_run else ref_pace_str
                p["badges"] = []

                if canonical_uid and uid == canonical_uid:
                    my_participation = p

                participants_full.append(p)

            # Compute MVPs and collective stats
            completed_runners = [p for p in participants_full if p["has_completed_run"] and p["actual_distance_km"] > 0]
            total_actual_km = round(sum(p["actual_distance_km"] for p in completed_runners), 1)
            total_target_km = round(len(participants_full) * float(ev.get("target_km") or 10.0), 1)
            total_calories = sum(p["actual_calories"] or 0 for p in completed_runners)

            valid_paces = [p["pace_seconds"] for p in completed_runners if p.get("pace_seconds")]
            if valid_paces:
                team_avg_pace_str = LocalStore._seconds_to_pace_str(sum(valid_paces) / len(valid_paces))
            else:
                ref_paces = [LocalStore._pace_str_to_seconds(p["reference_pace_str"]) for p in participants_full]
                ref_paces = [x for x in ref_paces if x]
                team_avg_pace_str = LocalStore._seconds_to_pace_str(sum(ref_paces) / len(ref_paces)) if ref_paces else (ev.get("pace_requirement") or "5'30\"")

            mvp_longest = None
            mvp_fastest = None
            mvp_earliest = participants_full[0] if participants_full else None

            if completed_runners:
                mvp_longest = max(completed_runners, key=lambda x: x["actual_distance_km"])
                mvp_longest["badges"].append("🏆 里程王")
                fastest_candidates = [p for p in completed_runners if p.get("pace_seconds") and p["actual_distance_km"] >= 3.0]
                if not fastest_candidates:
                    fastest_candidates = [p for p in completed_runners if p.get("pace_seconds")]
                if fastest_candidates:
                    mvp_fastest = min(fastest_candidates, key=lambda x: x["pace_seconds"])
                    if "⚡ 破风王" not in mvp_fastest["badges"]:
                        mvp_fastest["badges"].append("⚡ 破风王")

            if mvp_earliest:
                mvp_earliest["badges"].append("🌅 早鸟先锋")

            # Group by pace train
            pace_groups_map: Dict[str, List[Dict[str, Any]]] = {}
            for p in participants_full:
                pg = p.get("pace_group") or "🏃 有氧组"
                pace_groups_map.setdefault(pg, []).append({
                    "user_id": p["user_id"],
                    "display_name": p["display_name"],
                    "avatar_url": p.get("avatar_url"),
                    "runner_role": p.get("runner_role"),
                    "display_pace_str": p.get("display_pace_str"),
                    "has_completed_run": p.get("has_completed_run"),
                    "actual_distance_km": p.get("actual_distance_km"),
                })

            pace_groups_summary = [
                {"pace_group": k, "count": len(v), "members": v}
                for k, v in pace_groups_map.items()
            ]

            # Build 1-click WeChat Solitaire & Battle Report copy
            club_title = ev.get("club_name") or "跑团"
            ev_title = ev.get("title") or "周末约跑"
            mt_display = ev.get("meet_time") or ev.get("start_date") or ""
            loc_display = ev.get("location") or "跑团集合点"
            target_km_val = ev.get("target_km") or 10

            solitaire_lines = [
                f"🔥【{club_title} · 约跑集结接龙】🔥",
                f"🏃 主题：{ev_title}",
                f"⏰ 时间：{mt_display}",
                f"📍 地点：{loc_display}",
                f"🎯 目标：{target_km_val}km · {ev.get('pace_requirement') or '全配速友好'}",
                f"👥 已报名（{len(participants_full)}人）：",
            ]
            for idx, p in enumerate(participants_full[:30]):
                role_tag = f"[{p['runner_role']}]" if p.get("runner_role") else ""
                pg_tag = p.get("pace_group") or ""
                solitaire_lines.append(f"{idx+1}. {p['display_name']} {role_tag} ({pg_tag} · 参考配速 {p['display_pace_str']})")
            solitaire_lines.append("👉 打开RGM小程序一键跟团报名，自动同步手表完赛战报！")
            share_solitaire_text = "\n".join(solitaire_lines)

            battle_lines = [
                f"🏆【{club_title} · 约跑完赛战报】🏆",
                f"📅 {mt_display} | 📍 {loc_display}",
                f"📊 参团 {len(participants_full)} 人 · 完赛打卡 {len(completed_runners)} 人",
                f"🔥 团队累计里程：{total_actual_km if total_actual_km > 0 else total_target_km} km | 平均配速：{team_avg_pace_str}",
            ]
            if mvp_longest:
                battle_lines.append(f"👑 里程担当：{mvp_longest['display_name']} ({mvp_longest['actual_distance_km']}km)")
            if mvp_fastest:
                battle_lines.append(f"⚡ 破风先锋：{mvp_fastest['display_name']} (配速 {mvp_fastest['actual_pace_str']})")
            battle_lines.append("━━━━━━━━━━━━━━")
            for idx, p in enumerate(participants_full[:20]):
                if p["has_completed_run"]:
                    battle_lines.append(f"#{idx+1} {p['display_name']} | {p['actual_distance_km']}km | 配速 {p['actual_pace_str']} | 用时 {p['actual_duration_str']}")
                else:
                    battle_lines.append(f"#{idx+1} {p['display_name']} | {p['pace_group']} | 目标 {target_km_val}km")
            share_battle_report_text = "\n".join(battle_lines)

            # Comments wall
            cursor.execute("""
                SELECT c.id, c.user_id, c.content, c.created_at,
                       pr.display_name, pr.avatar_url, pr.real_name
                FROM club_event_comments c
                LEFT JOIN profiles pr ON c.user_id = pr.id
                WHERE c.event_id = ?
                ORDER BY c.created_at DESC LIMIT 50
            """, (event_id,))
            comments = []
            for cr_row in cursor.fetchall():
                c_dict = dict(cr_row)
                c_dict["display_name"] = c_dict.get("display_name") or c_dict.get("real_name") or "跑友"
                c_dict["created_at"] = to_beijing_iso(c_dict.get("created_at"))
                comments.append(c_dict)

            # Viewer's recent activities for 1-click check-in binding
            my_recent_activities = []
            if canonical_uid:
                cursor.execute("""
                    SELECT id, name, start_time, distance_meters, moving_time_seconds, avg_pace_str, average_heartrate
                    FROM activities
                    WHERE user_id = ?
                    ORDER BY start_time DESC LIMIT 8
                """, (canonical_uid,))
                for ar in cursor.fetchall():
                    ad = dict(ar)
                    ad["distance_km"] = round((ad.get("distance_meters") or 0) / 1000.0, 2)
                    ad["duration_str"] = LocalStore._seconds_to_duration_str(ad.get("moving_time_seconds"))
                    ad["date_label"] = str(ad.get("start_time") or "")[:16].replace("T", " ")
                    my_recent_activities.append(ad)

            # If viewer does NOT have permission to view the full roster (`can_view_roster == False`),
            # mask detailed participant metrics and return only avatar preview & count so privacy setting is enforced.
            visible_participants = participants_full if can_view_roster else [
                {
                    "participant_id": p["participant_id"],
                    "user_id": p["user_id"],
                    "display_name": (p["display_name"][0] + "**") if p.get("display_name") else "团员**",
                    "avatar_url": p.get("avatar_url"),
                    "pace_group": p.get("pace_group"),
                    "runner_role": p.get("runner_role"),
                    "is_masked": True,
                }
                for p in participants_full[:8]
            ]

            ev["is_joined"] = is_joined
            ev["is_club_member"] = is_club_member
            ev["can_manage"] = can_manage
            ev["can_view_roster"] = can_view_roster
            ev["participant_count"] = len(participants_full)
            ev["completed_count"] = len(completed_runners)
            ev["participants"] = visible_participants
            ev["my_participation"] = my_participation
            ev["my_recent_activities"] = my_recent_activities
            ev["comments"] = comments if can_view_roster else []
            ev["social_summary"] = {
                "participant_count": len(participants_full),
                "completed_count": len(completed_runners),
                "completion_rate": int(round(len(completed_runners) * 100.0 / len(participants_full))) if participants_full else 0,
                "total_actual_km": total_actual_km,
                "total_target_km": total_target_km,
                "total_calories": total_calories,
                "team_avg_pace_str": team_avg_pace_str,
                "mvp_longest": {
                    "display_name": mvp_longest["display_name"],
                    "avatar_url": mvp_longest.get("avatar_url"),
                    "value_label": f"{mvp_longest['actual_distance_km']} km",
                } if (mvp_longest and can_view_roster) else None,
                "mvp_fastest": {
                    "display_name": mvp_fastest["display_name"],
                    "avatar_url": mvp_fastest.get("avatar_url"),
                    "value_label": mvp_fastest["actual_pace_str"],
                } if (mvp_fastest and can_view_roster) else None,
                "mvp_earliest": {
                    "display_name": mvp_earliest["display_name"],
                    "avatar_url": mvp_earliest.get("avatar_url"),
                    "value_label": "首棒集结",
                } if (mvp_earliest and can_view_roster) else None,
                "pace_groups_summary": pace_groups_summary if can_view_roster else [],
                "share_solitaire_text": share_solitaire_text if can_view_roster else "",
                "share_battle_report_text": share_battle_report_text if can_view_roster else "",
            }
            return ev

    @staticmethod
    def update_event_participant_checkin(club_id: str, event_id: str, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Updates a participant's pace_group, runner_role, checkin_note, bound activity_id, or manual distance/pace."""
        canonical_uid = LocalStore.resolve_user_id(user_id)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM club_event_participants WHERE event_id = ? AND user_id = ? AND status = 'joined'",
                (event_id, canonical_uid)
            )
            existing = cursor.fetchone()
            now_iso = get_beijing_iso()
            if not existing:
                # Auto-join if they check in directly
                part_id = f"part_{int(time.time() * 1000)}"
                cursor.execute("""
                    INSERT INTO club_event_participants (
                        id, event_id, club_id, user_id, joined_at, status,
                        pace_group, runner_role, checkin_note,
                        manual_distance_km, manual_pace_str, manual_duration_str, activity_id
                    )
                    VALUES (?, ?, ?, ?, ?, 'joined', ?, ?, ?, ?, ?, ?, ?)
                """, (
                    part_id, event_id, club_id, canonical_uid, now_iso,
                    data.get("pace_group") or "🏃 有氧组",
                    data.get("runner_role") or "🏃 跟跑团员",
                    data.get("checkin_note") or "",
                    float(data["manual_distance_km"]) if data.get("manual_distance_km") is not None else None,
                    data.get("manual_pace_str"),
                    data.get("manual_duration_str"),
                    data.get("activity_id")
                ))
            else:
                cursor.execute("""
                    UPDATE club_event_participants
                    SET pace_group = COALESCE(?, pace_group),
                        runner_role = COALESCE(?, runner_role),
                        checkin_note = COALESCE(?, checkin_note),
                        manual_distance_km = COALESCE(?, manual_distance_km),
                        manual_pace_str = COALESCE(?, manual_pace_str),
                        manual_duration_str = COALESCE(?, manual_duration_str),
                        activity_id = COALESCE(?, activity_id)
                    WHERE event_id = ? AND user_id = ?
                """, (
                    data.get("pace_group"),
                    data.get("runner_role"),
                    data.get("checkin_note"),
                    float(data["manual_distance_km"]) if data.get("manual_distance_km") is not None else None,
                    data.get("manual_pace_str"),
                    data.get("manual_duration_str"),
                    data.get("activity_id"),
                    event_id,
                    canonical_uid
                ))

            # If participant left a checkin_note and requested to sync to comment wall
            note_text = (data.get("checkin_note") or "").strip()
            if note_text and data.get("post_to_wall", True):
                cid = f"evcmt_{int(time.time() * 1000)}"
                cursor.execute("""
                    INSERT INTO club_event_comments (id, event_id, club_id, user_id, content, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (cid, event_id, club_id, canonical_uid, note_text, now_iso))

            conn.commit()
        return {"success": True, "message": "约跑名片与完赛数据已更新！"}

    @staticmethod
    def update_club_event_visibility(
        club_id: str,
        event_id: str,
        operator_uid: str,
        visibility_mode: str,
        recap_note: Optional[str] = None
    ) -> Dict[str, Any]:
        canonical_uid = LocalStore.resolve_user_id(operator_uid)
        if visibility_mode not in ("registered_only", "club_members", "public"):
            raise ValueError("无效的开放权限设置")

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.creator_id, c.owner_id
                FROM club_events e
                LEFT JOIN clubs c ON e.club_id = c.id
                WHERE e.id = ? AND e.club_id = ?
            """, (event_id, club_id))
            row = cursor.fetchone()
            if not row:
                raise ValueError("约跑活动不存在")

            cursor.execute("SELECT role FROM club_memberships WHERE club_id = ? AND user_id = ?", (club_id, canonical_uid))
            cm = cursor.fetchone()
            role = cm["role"] if cm else ""

            if canonical_uid != row["creator_id"] and canonical_uid != row["owner_id"] and role not in ("owner", "coach", "admin"):
                raise PermissionError("仅约跑发起人、团长或教练可修改页面开放范围")

            cursor.execute("""
                UPDATE club_events
                SET visibility_mode = ?,
                    recap_note = COALESCE(?, recap_note)
                WHERE id = ? AND club_id = ?
            """, (visibility_mode, recap_note, event_id, club_id))
            conn.commit()

        mode_labels = {
            "registered_only": "仅报名约跑的团员可见",
            "club_members": "本跑团全体成员可见",
            "public": "公开战报（所有人可查看分享页）"
        }
        return {
            "success": True,
            "visibility_mode": visibility_mode,
            "message": f"页面权限已设为：{mode_labels.get(visibility_mode, visibility_mode)}"
        }

    @staticmethod
    def highfive_event_participant(club_id: str, event_id: str, target_user_id: str, from_user_id: str) -> Dict[str, Any]:
        canonical_target = LocalStore.resolve_user_id(target_user_id)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE club_event_participants
                SET likes_count = COALESCE(likes_count, 0) + 1
                WHERE event_id = ? AND user_id = ?
            """, (event_id, canonical_target))
            conn.commit()
            cursor.execute(
                "SELECT COALESCE(likes_count, 0) FROM club_event_participants WHERE event_id = ? AND user_id = ?",
                (event_id, canonical_target)
            )
            row = cursor.fetchone()
            likes_count = row[0] if row else 1
        return {"success": True, "likes_count": likes_count, "message": "👏 已为队友击掌打气！"}

    @staticmethod
    def add_event_comment(club_id: str, event_id: str, user_id: str, content: str) -> Dict[str, Any]:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        clean_content = (content or "").strip()
        if not clean_content:
            raise ValueError("留言内容不能为空")
        now_iso = get_beijing_iso()
        cid = f"evcmt_{int(time.time() * 1000)}"
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO club_event_comments (id, event_id, club_id, user_id, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (cid, event_id, club_id, canonical_uid, clean_content, now_iso))
            conn.commit()
            cursor.execute("SELECT display_name, avatar_url, real_name FROM profiles WHERE id = ?", (canonical_uid,))
            pr = cursor.fetchone()
            display_name = (pr["display_name"] or pr["real_name"] or "跑友") if pr else "跑友"
            avatar_url = pr["avatar_url"] if pr else None

        return {
            "success": True,
            "comment": {
                "id": cid,
                "event_id": event_id,
                "club_id": club_id,
                "user_id": canonical_uid,
                "content": clean_content,
                "created_at": now_iso,
                "display_name": display_name,
                "avatar_url": avatar_url,
            }
        }

    @staticmethod
    def leave_club_event(club_id: str, event_id: str, user_id: str) -> Dict[str, Any]:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE club_event_participants
                SET status = 'cancelled'
                WHERE event_id = ? AND user_id = ?
            """, (event_id, canonical_uid))
            conn.commit()
        return {"success": True, "message": "已成功取消报名", "is_joined": False}

    @staticmethod
    def get_user_upcoming_runs(user_id: str) -> List[Dict[str, Any]]:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.*, c.name as club_name, c.logo_url as club_logo,
                       (SELECT COUNT(*) FROM club_event_participants p2 WHERE p2.event_id = e.id AND p2.status = 'joined') as participant_count
                FROM club_events e
                JOIN club_event_participants p ON e.id = p.event_id
                JOIN clubs c ON e.club_id = c.id
                WHERE p.user_id = ? AND p.status = 'joined'
                ORDER BY CASE WHEN e.meet_time IS NOT NULL AND e.meet_time != '' THEN e.meet_time ELSE e.start_date END ASC
            """, (canonical_uid,))
            return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def get_coach_students_metrics(club_id: str, coach_id: str, sort_order: str = "danger_first") -> List[Dict[str, Any]]:
        """
        Calculates TSB fatigue, Resting Heart Rate, Night HRV, and risk levels for all authorized students in the club.
        Batch-preloads all member profiles, 180-day + PB activities, 14-day + plan daily_health, goals, race_plans,
        active/draft training_plans, and plan backups in a single connection (~7 SQL queries total instead of 2,000+).
        """
        members = LocalStore.get_club_members(club_id)
        if not members:
            return []

        students = []
        today = get_beijing_today()
        today_str = today.isoformat()
        cutoff_2d = (today - timedelta(days=2)).isoformat()
        cutoff_5d = (today - timedelta(days=4)).isoformat()
        cutoff_14d = (today - timedelta(days=13)).isoformat()
        cutoff_180d = (today - timedelta(days=180)).isoformat()
        seven_days_ago_iso = (today - timedelta(days=6)).isoformat()
        current_month_idx = today.month - 1

        uids = [str(m["user_id"]) for m in members]
        ph = ",".join("?" for _ in uids)

        profiles_map: Dict[str, Dict[str, Any]] = {}
        active_plans_map: Dict[str, Dict[str, Any]] = {}
        draft_plans_map: Dict[str, Dict[str, Any]] = {}
        health_rows_map: Dict[str, List[Dict[str, Any]]] = {u: [] for u in uids}
        health_min_date_map: Dict[str, Optional[str]] = {}
        acts_map: Dict[str, List[Dict[str, Any]]] = {u: [] for u in uids}
        goals_map: Dict[str, Dict[str, Any]] = {}
        races_map: Dict[str, List[Dict[str, Any]]] = {u: [] for u in uids}
        backups_map: Dict[str, Dict[str, Any]] = {}

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Batch profiles
            cursor.execute(f"SELECT * FROM profiles WHERE id IN ({ph})", uids)
            for r in cursor.fetchall():
                d = LocalStore._decrypt_profile_dict(dict(r)) or {}
                profiles_map[str(d.get("id"))] = d

            # 2. Batch active & draft training plans
            cursor.execute(
                f"""
                SELECT * FROM training_plans
                WHERE user_id IN ({ph}) AND status IN ('active', 'draft')
                ORDER BY updated_at DESC
                """,
                uids,
            )
            earliest_plan_start = cutoff_180d
            earliest_health_start = cutoff_14d
            for r in cursor.fetchall():
                pd = dict(r)
                p_uid = str(pd.get("user_id") or "")
                p_status = str(pd.get("status") or "")
                if pd.get("schedule_data"):
                    try:
                        pd["schedule_data"] = json.loads(pd["schedule_data"])
                    except Exception:
                        pass
                if p_status == "active" and p_uid not in active_plans_map:
                    active_plans_map[p_uid] = pd
                    st_d = str(pd.get("start_date") or "")[:10]
                    if st_d and len(st_d) == 10:
                        if st_d < earliest_plan_start:
                            earliest_plan_start = st_d
                        if st_d < earliest_health_start:
                            earliest_health_start = st_d
                elif p_status == "draft" and p_uid not in draft_plans_map:
                    draft_plans_map[p_uid] = pd

            # 3. Batch daily_health (recent/plan window + earliest history date per user)
            cursor.execute(
                f"""
                SELECT * FROM daily_health
                WHERE user_id IN ({ph}) AND date >= ?
                ORDER BY date DESC
                """,
                uids + [earliest_health_start],
            )
            for r in cursor.fetchall():
                hd = LocalStore.sanitize_daily_health_row(dict(r)) or {}
                h_uid = str(hd.get("user_id") or "")
                if h_uid in health_rows_map:
                    health_rows_map[h_uid].append(hd)

            cursor.execute(
                f"SELECT user_id, MIN(date) AS min_date FROM daily_health WHERE user_id IN ({ph}) GROUP BY user_id",
                uids,
            )
            for r in cursor.fetchall():
                health_min_date_map[str(r["user_id"])] = str(r["min_date"]) if r["min_date"] else None

            # 4. Batch scalar activities (180d + plan window + all-time >=4.85km PB candidates, zero GPS/journal blobs)
            cursor.execute(
                f"""
                SELECT id, user_id, name, sport_type, start_time, distance_meters,
                       moving_time_seconds, elapsed_time_seconds, avg_pace_str,
                       average_heartrate, max_heartrate, average_cadence, trimp, exclude_mode
                FROM activities
                WHERE user_id IN ({ph})
                  AND (start_time >= ? OR (distance_meters >= 4850 AND moving_time_seconds >= 800))
                ORDER BY start_time DESC
                """,
                uids + [earliest_plan_start],
            )
            for r in cursor.fetchall():
                ad = dict(r)
                if ad.get("start_time"):
                    ad["start_time"] = to_beijing_iso(ad["start_time"])
                a_uid = str(ad.get("user_id") or "")
                if a_uid in acts_map:
                    acts_map[a_uid].append(ad)

            # 5. Batch goals
            cursor.execute(f"SELECT * FROM goals WHERE user_id IN ({ph})", uids)
            for r in cursor.fetchall():
                goals_map[str(r["user_id"])] = dict(r)

            # 6. Batch race plans
            cursor.execute(f"SELECT * FROM race_plans WHERE user_id IN ({ph}) ORDER BY race_date ASC", uids)
            for r in cursor.fetchall():
                rd = dict(r)
                r_uid = str(rd.get("user_id") or "")
                if r_uid in races_map:
                    races_map[r_uid].append(rd)

            # 7. Batch latest un-restored plan backup per user
            cursor.execute(
                f"""
                SELECT id, batch_id, user_id, club_id, action_type, action_label,
                       previous_active_plan_id, previous_active_plan_json,
                       created_plan_id, created_status, operator_uid, created_at, restored_at
                FROM training_plan_backups
                WHERE user_id IN ({ph}) AND restored_at IS NULL
                ORDER BY created_at DESC
                """,
                uids,
            )
            for r in cursor.fetchall():
                b_uid = str(r["user_id"] or "")
                if b_uid in backups_map:
                    continue
                item = dict(r)
                prev_title = None
                prev_source_label = None
                raw_json = item.pop("previous_active_plan_json", None)
                if raw_json:
                    try:
                        prev_obj = json.loads(raw_json)
                        prev_title = prev_obj.get("title")
                        prev_src = LocalStore.classify_plan_source(prev_obj)
                        prev_source_label = prev_src.get("source_label")
                    except Exception:
                        pass
                item["previous_title"] = prev_title
                item["previous_plan_title"] = prev_title
                item["previous_source_label"] = prev_source_label
                item["created_at"] = to_beijing_iso(item.get("created_at"))
                item["restored_at"] = to_beijing_iso(item.get("restored_at"))
                backups_map[b_uid] = item

        from utils.metrics_domain import MetricsDomainService

        for m in members:
            uid = str(m["user_id"])
            profile = profiles_map.get(uid) or {"id": uid}
            month_km = float(m.get("month_km") or 0.0)

            user_health_rows = health_rows_map.get(uid) or []
            recent_health_candidates = [
                hr for hr in user_health_rows if str(hr.get("date") or "")[:10] >= cutoff_2d
            ]
            h = recent_health_candidates[0] if recent_health_candidates else {}
            rows_14d = [hr for hr in user_health_rows if str(hr.get("date") or "")[:10] >= cutoff_14d]
            min_h_date = health_min_date_map.get(uid)
            has_older_health_hist = bool(min_h_date and min_h_date[:10] <= cutoff_5d)

            all_user_acts = acts_map.get(uid) or []
            acts_180d = [
                a for a in all_user_acts
                if str(a.get("start_time") or "")[:10] >= cutoff_180d
                and a.get("exclude_mode") != "excluded"
            ]
            recent_acts = acts_180d[:100]

            if not acts_180d:
                atl = 0.0
                ctl = 0.0
                tsb = 0.0
                status_level = "none"
                status_text = "未同步运动负荷"
            else:
                load_summary = MetricsDomainService.compute_load_and_form(
                    acts_180d, profile=profile, window_days=90, warmup_days=180, today=today
                )
                ctl = round(float(load_summary.get("current_ctl") or 0.0), 1)
                atl = round(float(load_summary.get("current_atl") or 0.0), 1)
                tsb = round(float(load_summary.get("current_tsb") or 0.0), 1)

                if tsb > 5:
                    status_level = "peak"
                    status_text = "巅峰状态 · 适宜测速与冲刺比赛"
                elif tsb >= -30:
                    status_level = "optimal"
                    status_text = "专项适应 · 建议按计划执行专项课"
                elif tsb >= -50:
                    status_level = "tired"
                    status_text = "疲劳累积 · 建议适度穿插轻松慢跑"
                else:
                    status_level = "danger"
                    status_text = "过度训练预警 · 建议彻底休整或低心率排酸"

            recovery_avail = LocalStore.assess_recovery_data_availability(
                uid,
                health_row=h if h else None,
                profile=profile,
                recent_acts=recent_acts[:15],
                health_rows_14d=rows_14d,
                has_older_health_history=has_older_health_hist,
            )
            if recovery_avail.get("recovery_data_available"):
                rhr = h.get("resting_heart_rate")
                hrv = h.get("hrv_last_night_avg")
                sleep = h.get("sleep_score")
            else:
                rhr = None
                hrv = None
                sleep = None

            # 1. Goal planning & progress
            goal_data = LocalStore._format_goal_dict(goals_map.get(uid), today=today)
            monthly_targets = goal_data.get("monthly_targets") or [200.0] * 12
            target_km = float(monthly_targets[current_month_idx] if current_month_idx < len(monthly_targets) else goal_data.get("target_distance") or 200.0)
            completion_rate = round((month_km / target_km) * 100.0, 1) if target_km > 0 else 0.0
            remaining_km = max(0.0, round(target_km - month_km, 1))

            days_in_month = 30
            expected_rate = round((today.day / float(days_in_month)) * 100.0, 1)
            progress_delta = round(completion_rate - expected_rate, 1)

            if target_km <= 0:
                pacing_status = "none"
                pacing_text = "未设跑量目标"
            elif completion_rate >= 100.0:
                pacing_status = "completed"
                pacing_text = "🎉 本月跑量已超额达成"
            elif progress_delta >= 10.0:
                pacing_status = "ahead"
                pacing_text = f"🟢 进度超前 (+{progress_delta}%)"
            elif progress_delta >= -10.0:
                pacing_status = "on_track"
                pacing_text = f"🔵 节奏稳定 (完成 {completion_rate}%)"
            else:
                pacing_status = "lagging"
                pacing_text = f"🟡 进度偏缓 (落后 {abs(progress_delta)}%)"

            days_remaining = max(1, days_in_month - today.day)
            suggested_daily_km = round(remaining_km / float(days_remaining), 1)

            # 2. Athlete profile & verified PBs / age / gender (zero SQL via query_activities=False)
            verified_meta = LocalStore.resolve_verified_runner_profile_and_pbs(
                uid, profile, recent_acts=all_user_acts, query_activities=False
            )
            marathon_pb = verified_meta.get("marathon_pb")
            half_pb = verified_meta.get("half_pb")
            ten_k_pb = verified_meta.get("ten_k_pb")
            gender = verified_meta.get("gender") or "未知"
            gender_label = verified_meta.get("gender_label") or ""
            age = verified_meta.get("age")
            age_group_label = verified_meta.get("age_group_label") or ""
            vo2max = profile.get("vo2max")
            weight = profile.get("weight") or profile.get("weight_kg")
            height = profile.get("height") or profile.get("height_cm")

            # 3. 7-day distance & TRIMP (7 calendar days including today, skipping excluded)
            acts_7d = [
                a for a in acts_180d
                if str(a.get("start_time", ""))[:10] >= seven_days_ago_iso
                and LocalStore.is_running_activity(a.get("sport_type"))
            ]
            km_7d = round(sum(float(a.get("distance_meters") or 0) for a in acts_7d) / 1000.0, 1)
            runs_7d_count = len(acts_7d)

            # 4. Coach diagnostic analysis
            if not acts_180d:
                coach_diagnosis = "暂未检测到近期运动记录上传，建议提醒队员检查手表蓝牙同步并保持 24 小时佩戴。"
                canova_phase = "基础期 (待启动)"
            elif recovery_avail.get("night_wear_missing"):
                coach_diagnosis = recovery_avail.get("coach_warning") or (
                    "⚠️ 该队员近期夜间未佩戴手表（缺失夜间 HRV 与静息心率等恢复数据），暂无法评估身体恢复状态或给出准确的训练强度建议。请督促队员保持 24 小时佩戴手表。"
                )
                canova_phase = "恢复数据缺失 · 待24h佩戴"
            elif tsb > 15:
                coach_diagnosis = f"体能处于极佳巅峰期 (TSB +{tsb})，疲劳完全消除。适宜组织马拉松专项配速测速跑或安排半马/全马冲刺赛。"
                canova_phase = "竞赛冲刺 / 巅峰调整期"
            elif tsb > 5:
                coach_diagnosis = f"身体吸收负荷良好，体能储备扎实 (TSB +{tsb})。可按计划稳步推进中长距离专项进阶训练(Special Block)。"
                canova_phase = "专项进阶期 (Specific Phase)"
            elif tsb >= -30:
                coach_diagnosis = f"当前处于适度负荷吸收区 (TSB {tsb})。训练刺激适中，注意在专项日之间穿插低心率有氧轻松慢跑。"
                canova_phase = "专项准备期 (Fundamental Phase)"
            elif tsb >= -50:
                coach_diagnosis = f"高强度专项课造成一定疲劳积累 (TSB {tsb})。建议调低下一周的跑量增速，加强清晨静息心率与睡眠监控。"
                canova_phase = "负荷累积与消化期"
            else:
                coach_diagnosis = f"TSB 深度过载 ({tsb})，存在训练过度或伤病隐患。强烈建议停止高强度间歇，增加跑休或改为纯排酸慢跑。"
                canova_phase = "伤病防范 / 强制减量期"

            # 5. Upcoming races & training plan execution status
            weekly_target = float(goal_data.get("weekly_target") or round(target_km / 4.0, 1))
            raw_races = races_map.get(uid) or []
            upcoming_races = []
            for r in raw_races:
                r_dict = dict(r)
                is_comp = (r_dict.get("status") == "completed" or bool(r_dict.get("finish_time")) or bool(r_dict.get("is_completed")))
                r_date_str = str(r_dict.get("race_date") or "")[:10]
                if not is_comp and r_date_str >= today_str:
                    upcoming_races.append(r_dict)
            upcoming_races.sort(key=lambda x: str(x.get("race_date") or ""))
            a_races = [r for r in upcoming_races if str(r.get("priority") or "").upper() in ("1", "A")]
            goal_race = a_races[0] if a_races else (upcoming_races[0] if upcoming_races else None)

            raw_active_plan = active_plans_map.get(uid)
            if raw_active_plan:
                reconciled_active = LocalStore.reconcile_training_plan_activities(
                    raw_active_plan,
                    user_id=uid,
                    preloaded_activities=all_user_acts,
                    preloaded_health_rows=user_health_rows,
                    persist=False,
                )
                active_plan = LocalStore._enrich_plan_with_current_week(
                    reconciled_active, profile=profile, latest_health=h
                )
            else:
                active_plan = None

            raw_draft_plan = draft_plans_map.get(uid)
            draft_plan = (
                LocalStore._enrich_plan_with_current_week(raw_draft_plan, profile=profile, latest_health=h)
                if raw_draft_plan
                else None
            )
            display_plan = draft_plan or active_plan

            if draft_plan:
                plan_state = "draft_pending"
            elif active_plan:
                if active_plan.get("review_status") == "published":
                    plan_state = "published"
                else:
                    plan_state = "self_active"
            else:
                plan_state = "none"

            week_execution = None
            exec_source_plan = active_plan or draft_plan
            if exec_source_plan and exec_source_plan.get("schedule_data"):
                sched_obj = exec_source_plan.get("schedule_data") or {}
                weeks_list = sched_obj.get("weeks") or []
                cur_wk_idx = exec_source_plan.get("current_week_index") or 1
                cur_wk = None
                for w_item in weeks_list:
                    if w_item.get("week_index") == cur_wk_idx:
                        cur_wk = w_item
                        break
                if not cur_wk and weeks_list:
                    cur_wk = weeks_list[0]

                if cur_wk:
                    days_arr = cur_wk.get("days") or []
                    planned_km = round(sum(float(d.get("distance_km") or 0.0) for d in days_arr if d.get("workout_type") not in ("rest", "travel")), 1)
                    actual_km = round(sum(
                        float(d.get("actual_distance_km") if d.get("actual_distance_km") is not None else (d.get("distance_km") if d.get("completed") else 0.0) or 0.0)
                        for d in days_arr
                        if d.get("workout_type") not in ("rest", "travel")
                    ), 1)
                    run_days = [d for d in days_arr if d.get("workout_type") not in ("rest", "travel") and float(d.get("distance_km") or 0.0) > 0]
                    workouts_total = len(run_days)
                    workouts_completed = sum(1 for d in run_days if d.get("completed"))
                    workouts_missed = sum(1 for d in run_days if d.get("is_missed"))
                    compliance_rate = round((workouts_completed / workouts_total) * 100.0, 1) if workouts_total > 0 else 0.0
                    mileage_completion_pct = int(round(actual_km * 100.0 / planned_km)) if planned_km > 0 else (100 if actual_km > 0 else 0)

                    rpe_list = [float(d["rpe"]) for d in days_arr if d.get("rpe") is not None and str(d.get("rpe")).strip() != ""]
                    avg_rpe = round(sum(rpe_list) / len(rpe_list), 1) if rpe_list else None
                    max_rpe = int(max(rpe_list)) if rpe_list else None

                    rec_list = [int(d["recovery_pct"]) for d in days_arr if d.get("recovery_pct") is not None and str(d.get("recovery_pct")).strip() != ""]
                    avg_recovery_pct = int(round(sum(rec_list) / len(rec_list))) if rec_list else None

                    auto_strength = sum(
                        1 for d in days_arr
                        if d.get("strength_completed") or d.get("workout_type") == "cross_training"
                        or any(kw in (str(d.get("actual_execution_text") or "") + str(d.get("title") or "") + str(d.get("description") or "")) for kw in ("身训", "力量", "核心", "单腿", "体能"))
                    )
                    wk_sum = cur_wk.get("week_summary") or {}
                    strength_count = cur_wk.get("strength_count") if cur_wk.get("strength_count") is not None else wk_sum.get("strength_count", auto_strength)
                    injury_note = (cur_wk.get("injury_note") or wk_sum.get("injury_note") or "").strip()
                    athlete_weekly_summary = (cur_wk.get("athlete_weekly_summary") or wk_sum.get("athlete_weekly_summary") or "").strip()
                    travel_or_leave_note = (cur_wk.get("travel_or_leave_note") or wk_sum.get("travel_or_leave_note") or "").strip()
                    coach_weekly_diagnosis = (cur_wk.get("coach_weekly_diagnosis") or wk_sum.get("coach_weekly_diagnosis") or "").strip()

                    today_workout = None
                    days_brief = []
                    for d_idx, d in enumerate(days_arr):
                        w_type_d = d.get("workout_type") or "easy_run"
                        p_km_d = float(d.get("distance_km") or 0.0)
                        a_km_d = d.get("actual_distance_km")
                        if w_type_d in ("rest", "travel"):
                            d_status = "rest"
                        elif bool(d.get("completed")):
                            d_status = "completed"
                        elif bool(d.get("is_missed")):
                            d_status = "missed"
                        else:
                            d_status = "pending"
                        d_brief = {
                            "day_index": d_idx,
                            "day_of_week": d.get("day_of_week"),
                            "date": d.get("date"),
                            "status": d_status,
                            "workout_type": w_type_d,
                            "title": d.get("title"),
                            "description": d.get("description") or "",
                            "distance_km": p_km_d,
                            "planned_km": p_km_d,
                            "actual_km": a_km_d if a_km_d is not None else (p_km_d if bool(d.get("completed")) else 0.0),
                            "target_pace": d.get("target_pace"),
                            "target_hr_zone": d.get("target_hr_zone"),
                            "completed": bool(d.get("completed")),
                            "is_missed": bool(d.get("is_missed")),
                            "is_swapped": bool(d.get("is_swapped")),
                            "swapped_from": d.get("swapped_from"),
                            "actual_distance_km": a_km_d,
                            "actual_pace": d.get("actual_pace"),
                            "actual_heartrate": d.get("actual_heartrate"),
                            "actual_execution_text": d.get("actual_execution_text") or "",
                            "rpe": d.get("rpe"),
                            "feeling_tag": d.get("feeling_tag") or "",
                            "athlete_notes": d.get("athlete_notes") or "",
                            "workout_photos": d.get("workout_photos") or ([d["photo_url"]] if d.get("photo_url") else []),
                            "photo_url": (d.get("workout_photos")[0] if d.get("workout_photos") else (d.get("photo_url") or "")),
                            "hrv": d.get("hrv"),
                            "resting_hr": d.get("resting_hr"),
                            "respiratory_rate": d.get("respiratory_rate"),
                            "strain_score": d.get("strain_score"),
                            "recovery_pct": d.get("recovery_pct"),
                            "biometrics_text": d.get("biometrics_text") or "",
                            "hrv_warning": bool(d.get("hrv_warning")),
                            "coach_notes": d.get("coach_notes") or ""
                        }
                        days_brief.append(d_brief)
                        if str(d.get("date") or "") == today_str:
                            today_workout = d_brief

                    wk_num = cur_wk.get("week_index") or 1
                    wk_theme = cur_wk.get("theme") or cur_wk.get("phase") or cur_wk.get("week_title") or f"第{wk_num}周"
                    summary_banner_text = (
                        cur_wk.get("week_summary_text")
                        or wk_sum.get("summary_banner_text")
                        or f"周跑量：{planned_km}公里。执行：{actual_km}公里，完成度{mileage_completion_pct}%；力量：{strength_count}次。"
                    )
                    week_execution = {
                        "week_index": wk_num,
                        "week_number": wk_num,
                        "week_title": cur_wk.get("week_title") or f"第 {wk_num} 周",
                        "theme": wk_theme,
                        "phase": cur_wk.get("phase") or "",
                        "key_focus": cur_wk.get("key_focus") or "",
                        "planned_km": planned_km,
                        "actual_km": actual_km,
                        "mileage_completion_pct": mileage_completion_pct,
                        "strength_count": strength_count,
                        "summary_banner_text": summary_banner_text,
                        "avg_rpe": avg_rpe,
                        "max_rpe": max_rpe,
                        "avg_recovery_pct": avg_recovery_pct,
                        "has_injury_alert": bool(injury_note and injury_note != "无"),
                        "injury_note": injury_note,
                        "athlete_weekly_summary": athlete_weekly_summary,
                        "travel_or_leave_note": travel_or_leave_note,
                        "coach_weekly_diagnosis": coach_weekly_diagnosis,
                        "workouts_total": workouts_total,
                        "workouts_completed": workouts_completed,
                        "workouts_missed": workouts_missed,
                        "compliance_rate": compliance_rate,
                        "today_workout": today_workout,
                        "days_brief": days_brief
                    }

            disp_sched = (display_plan.get("schedule_data") or {}) if display_plan else {}
            has_inj_or_hrv = bool(
                (week_execution and week_execution.get("has_injury_alert"))
                or (week_execution and any(d.get("hrv_warning") for d in (week_execution.get("days_brief") or [])))
            )
            rec_group = LocalStore.recommend_athlete_template_group(
                marathon_pb=verified_meta.get("verified_mp_sec"),
                half_pb=verified_meta.get("verified_hp_sec"),
                ten_k_pb=verified_meta.get("verified_10k_sec"),
                recent_fm_sec=verified_meta.get("best_fm_sec"),
                vo2max=vo2max,
                ctl=ctl,
                month_km=month_km,
                km_7d=km_7d,
                weekly_target=weekly_target,
                age=age,
                gender=gender,
                status_level=status_level,
                has_injury_or_hrv_alert=has_inj_or_hrv
            )

            active_src_info = LocalStore.classify_plan_source(active_plan) if active_plan else None
            draft_src_info = LocalStore.classify_plan_source(draft_plan) if draft_plan else None
            latest_backup = backups_map.get(uid)

            # Keep the athlete's currently active plan as the main execution title when an active plan exists,
            # while exposing the pending draft separately so coaches never confuse a draft with a live plan.
            exec_plan_ref = active_plan or draft_plan
            plan_info = {
                "has_active_plan": bool(active_plan),
                "has_draft_plan": bool(draft_plan),
                "active_plan_id": active_plan["id"] if active_plan else None,
                "draft_plan_id": draft_plan["id"] if draft_plan else None,
                "primary_plan_id": display_plan["id"] if display_plan else None,
                "plan_state": plan_state,
                "title": exec_plan_ref.get("title") if exec_plan_ref else None,
                "active_plan_title": active_plan.get("title") if active_plan else None,
                "active_source_type": active_src_info.get("source_type") if active_src_info else None,
                "active_source_label": active_src_info.get("source_label") if active_src_info else None,
                "draft_plan_title": draft_plan.get("title") if draft_plan else None,
                "draft_source_type": draft_src_info.get("source_type") if draft_src_info else None,
                "draft_source_label": draft_src_info.get("source_label") if draft_src_info else None,
                "can_rollback": bool(latest_backup or draft_plan),
                "latest_backup": latest_backup,
                "goal_type": display_plan.get("goal_type") if display_plan else None,
                "target_race_name": display_plan.get("target_race_name") if display_plan else None,
                "target_date": display_plan.get("target_date") if display_plan else None,
                "weeks_count": display_plan.get("weeks_count") if display_plan else None,
                "days_per_week": display_plan.get("days_per_week") if display_plan else None,
                "current_week_index": display_plan.get("current_week_index") if display_plan else 1,
                "macro_roadmap": disp_sched.get("macro_roadmap") if display_plan else None,
                "template_id": disp_sched.get("template_id"),
                "template_group_code": disp_sched.get("template_group_code"),
                "template_name": disp_sched.get("template_name"),
                "review_status": display_plan.get("review_status") if display_plan else None,
                "reviewed_by_name": (active_plan or display_plan or {}).get("reviewed_by_name"),
                "reviewed_at": (active_plan or display_plan or {}).get("reviewed_at"),
                "coach_review_note": (display_plan or {}).get("coach_review_note") or "",
                "updated_at": display_plan.get("updated_at") if display_plan else None,
                "week_execution": week_execution
            }

            students.append({
                "user_id": uid,
                "display_name": m["display_name"],
                "avatar_url": m["avatar_url"],
                "role": m["role"],
                "training_group": m.get("training_group") or plan_info.get("template_group_code"),
                "privacy_consent": bool(m.get("privacy_consent", 1)),
                "month_km": month_km,
                "target_km": target_km,
                "weekly_target": weekly_target,
                "monthly_targets": monthly_targets,
                "completion_rate": completion_rate,
                "remaining_km": remaining_km,
                "suggested_daily_km": suggested_daily_km,
                "pacing_status": pacing_status,
                "pacing_text": pacing_text,
                "marathon_pb": marathon_pb,
                "half_pb": half_pb,
                "ten_k_pb": ten_k_pb,
                "vo2max": vo2max,
                "km_7d": km_7d,
                "runs_7d_count": runs_7d_count,
                "coach_diagnosis": coach_diagnosis,
                "canova_phase": canova_phase,
                "gender": gender,
                "gender_label": gender_label,
                "age": age,
                "age_group_label": age_group_label,
                "weight": weight,
                "height": height,
                "ctl": ctl,
                "atl": atl,
                "tsb": tsb,
                "status_level": status_level,
                "status_text": status_text,
                "resting_heart_rate": rhr,
                "hrv_ms": hrv,
                "sleep_score": sleep,
                "recovery_data_available": recovery_avail.get("recovery_data_available", False),
                "night_wear_missing": recovery_avail.get("night_wear_missing", False),
                "missing_recovery_fields": recovery_avail.get("missing_recovery_fields", []),
                "recovery_status_label": recovery_avail.get("recovery_status_label", ""),
                "recovery_data_warning": recovery_avail.get("coach_warning") if not recovery_avail.get("recovery_data_available") else None,
                "goal_race": goal_race,
                "upcoming_races": upcoming_races[:3],
                "recommended_group": rec_group,
                "plan_info": plan_info,
                "recent_activities": [
                    {
                        "name": a.get("name") or "跑步",
                        "distance_km": round((a.get("distance_meters") or 0) / 1000.0, 2),
                        "duration_mins": round((a.get("moving_time_seconds") or 0) / 60.0, 1),
                        "avg_hr": a.get("average_heartrate"),
                        "start_time": a.get("start_time"),
                        "trimp": a.get("trimp")
                    } for a in recent_acts[:5]
                ]
            })

        # Sort students by TSB status
        if sort_order == "peak_first":
            status_rank = {"peak": 1, "optimal": 2, "tired": 3, "danger": 4, "none": 5}
            students.sort(key=lambda s: (
                status_rank.get(s.get("status_level"), 99),
                -(s.get("tsb") if s.get("status_level") != "none" else -9999.0)
            ))
        else:
            # Default: danger_first (伤病预警优先，便于教练排查伤病隐患)
            status_rank = {"danger": 1, "tired": 2, "optimal": 3, "peak": 4, "none": 5}
            students.sort(key=lambda s: (
                status_rank.get(s.get("status_level"), 99),
                (s.get("tsb") if s.get("status_level") != "none" else 9999.0)
            ))

        return students

    @staticmethod
    def get_club_leaderboard(club_id: str, time_range: str = "month") -> List[Dict[str, Any]]:
        today = get_beijing_today()
        if time_range == "month":
            start_iso = date(today.year, today.month, 1).isoformat()
        else:
            # 7 days
            start_iso = (today - timedelta(days=7)).isoformat()

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT p.id AS user_id, p.display_name, p.avatar_url, m.role
                FROM club_memberships m
                JOIN profiles p ON m.user_id = p.id
                WHERE m.club_id = ? AND m.status = 'active'
                ORDER BY CASE m.role WHEN 'owner' THEN 1 WHEN 'coach' THEN 2 ELSE 3 END, m.joined_at ASC
                """,
                (club_id,),
            )
            member_rows = [dict(r) for r in cursor.fetchall()]
            if not member_rows:
                return []

            uids = [str(m["user_id"]) for m in member_rows]
            ph = ",".join(["?"] * len(uids))

            cursor.execute(
                f"""
                SELECT user_id, COALESCE(SUM(distance_meters), 0.0) AS total_m
                FROM activities
                WHERE user_id IN ({ph}) AND start_time >= ? AND {RUNNING_SQL_FILTER}
                GROUP BY user_id
                """,
                uids + [start_iso],
            )
            dist_map = {str(r["user_id"]): float(r["total_m"] or 0.0) for r in cursor.fetchall()}

            cursor.execute(
                f"SELECT user_id, target_distance, monthly_targets, weekly_target, weekly_targets_map FROM goals WHERE user_id IN ({ph})",
                uids,
            )
            goal_map = {str(r["user_id"]): dict(r) for r in cursor.fetchall()}

        board = []
        month_idx = today.month - 1
        is_monthly = (time_range == "month")
        monday_iso = (today - timedelta(days=today.weekday())).isoformat()
        for m in member_rows:
            uid = str(m["user_id"])
            dist_km = round(dist_map.get(uid, 0.0) / 1000.0, 1)

            g = goal_map.get(uid) or {}
            if is_monthly:
                target_km = float(g.get("target_distance") or 200.0)
                monthly_targets = g.get("monthly_targets")
                if isinstance(monthly_targets, str) and monthly_targets:
                    try:
                        monthly_targets = json.loads(monthly_targets)
                    except Exception:
                        monthly_targets = None
                if monthly_targets and isinstance(monthly_targets, list) and len(monthly_targets) > month_idx:
                    target_km = float(monthly_targets[month_idx] or target_km or 200.0)
            else:
                target_km = float(g.get("weekly_target") or 50.0)
                wk_map = g.get("weekly_targets_map")
                if isinstance(wk_map, str) and wk_map:
                    try:
                        wk_map = json.loads(wk_map)
                    except Exception:
                        wk_map = None
                if isinstance(wk_map, dict) and wk_map.get(monday_iso):
                    try:
                        target_km = float(wk_map[monday_iso])
                    except Exception:
                        pass
            pct = round((dist_km / target_km) * 100, 1) if target_km > 0 else 0.0

            board.append({
                "user_id": uid,
                "display_name": m["display_name"],
                "avatar_url": m["avatar_url"],
                "role": m["role"],
                "distance_km": dist_km,
                "target_km": target_km,
                "progress_pct": pct,
                "completion_rate": pct,
            })

        # Sort by distance descending
        board.sort(key=lambda x: x["distance_km"], reverse=True)
        for i, item in enumerate(board):
            item["rank"] = i + 1

        return board

    @staticmethod
    def is_club_owner(club_id: str, operator_uid: Optional[str]) -> bool:
        if not operator_uid or not club_id:
            return False
        raw_uid = str(operator_uid).strip()
        canon_uid = LocalStore.resolve_user_id(raw_uid)
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                """
                SELECT 1 FROM clubs WHERE id = ? AND (owner_id = ? OR owner_id = ?)
                UNION ALL
                SELECT 1 FROM club_memberships
                WHERE club_id = ? AND (user_id = ? OR user_id = ?) AND status = 'active' AND role = 'owner'
                LIMIT 1
                """,
                (club_id, raw_uid, canon_uid, club_id, raw_uid, canon_uid),
            ).fetchone()
            return row is not None

    @staticmethod
    def is_club_coach(club_id: str, operator_uid: Optional[str]) -> bool:
        if not operator_uid or not club_id:
            return False
        raw_uid = str(operator_uid).strip()
        canon_uid = LocalStore.resolve_user_id(raw_uid)
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                """
                SELECT 1 FROM club_memberships
                WHERE club_id = ? AND (user_id = ? OR user_id = ?) AND status = 'active' AND role = 'coach'
                LIMIT 1
                """,
                (club_id, raw_uid, canon_uid),
            ).fetchone()
            return row is not None

    @staticmethod
    def is_club_owner_or_coach(club_id: str, operator_uid: Optional[str]) -> bool:
        if not operator_uid or not club_id:
            return False
        raw_uid = str(operator_uid).strip()
        canon_uid = LocalStore.resolve_user_id(raw_uid)
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                """
                SELECT 1 FROM clubs WHERE id = ? AND (owner_id = ? OR owner_id = ?)
                UNION ALL
                SELECT 1 FROM club_memberships
                WHERE club_id = ? AND (user_id = ? OR user_id = ?) AND status = 'active' AND role IN ('owner', 'coach')
                LIMIT 1
                """,
                (club_id, raw_uid, canon_uid, club_id, raw_uid, canon_uid),
            ).fetchone()
            return row is not None

    @staticmethod
    def _generate_team_canova_critique(
        club_name: str,
        period_type: str,
        period_label: str,
        total_km: float,
        avg_pace_str: str,
        attendance_rate: float,
        total_acts_count: int,
        podium: List[Dict[str, Any]],
        longest_run: Optional[Dict[str, Any]] = None,
        active_count: int = 0,
        total_members_count: int = 0,
        team_completion_rate: float = 0.0,
        achieved_members_count: int = 0,
        trail_activities_count: int = 0,
        trail_distance_km: float = 0.0
    ) -> str:
        if total_km == 0 or total_acts_count == 0:
            return "本周期全团暂无跑步打卡记录，建议下周期组织一次周末集体慢跑（5~10km），帮助大家恢复规律出勤节奏。教练建议：恢复期以舒适慢跑为主，循序渐进找回跑感。"

        cycle_word = "本周" if period_type == "week" else "本月"
        next_cycle_word = "下周" if period_type == "week" else "下月"
        avg_km_per_runner = round(total_km / max(1, active_count or 1), 1)
        avg_runs_per_runner = round(total_acts_count / max(1, active_count or 1), 1)

        summary_parts = [
            f"{cycle_word}全团共完成 {total_acts_count} 次打卡、总跑量 {total_km}km（出勤率 {attendance_rate}%，活跃队员人均 {avg_km_per_runner}km / {avg_runs_per_runner}练，均速 {avg_pace_str}）"
        ]
        if team_completion_rate > 0:
            summary_parts.append(f"团队目标完成率 {team_completion_rate}%（{achieved_members_count}人达标）")
        if trail_activities_count > 0 and trail_distance_km > 0:
            summary_parts.append(f"其中含 {trail_activities_count} 次越野跑共 {trail_distance_km}km")
        volume_eval = "，".join(summary_parts) + "。"

        highlights = []
        if podium:
            c = podium[0]
            highlights.append(f"跑量榜首【{c['display_name']}】({c['distance_km']}km)")
        if longest_run and longest_run.get("distance_km", 0) >= 15:
            highlights.append(f"单次最长距离【{longest_run['runner_name']}】({longest_run['distance_km']}km)")
        highlight_str = f"{'、'.join(highlights)}表现突出。" if highlights else ""

        longest_km_val = float((longest_run or {}).get("distance_km") or 0)
        if attendance_rate < 55:
            coach_advice = (
                f"教练建议：当前团队出勤率偏低（{attendance_rate}%），{next_cycle_word}可通过固定周末合练带动更多队员开跑，"
                "先保证每周 2~3 次、每次 5~8km 的轻松有氧跑，把规律出勤习惯建立起来。"
            )
        elif period_type == "week":
            if longest_km_val >= 25:
                coach_advice = (
                    "教练建议：本周多位队员完成了 25km 以上长距离拉练，下周初请先安排 1~2 天跑休或慢速恢复跑，"
                    "待腿部酸胀消退后再进行周中质量课，切忌在疲劳未恢复时硬顶配速。"
                )
            else:
                coach_advice = (
                    "教练建议：本周整体训练节奏稳健，下周建议继续保持“平日轻松跑积累有氧 + 周末 1 次长距离”的排课结构，"
                    "日常慢跑控制好心率与呼吸，把体能留给重点质量课。"
                )
        else:
            coach_advice = (
                f"教练建议：本月活跃队员人均跑量达 {avg_km_per_runner}km，耐力基础扎实；{next_cycle_word}建议将约 80% 跑量维持在轻松可交谈的有氧配速，"
                "每周合理搭配 1 次节奏/间歇课与 1 次周末长距离，平稳推进跑量，避免单周跑量暴增引发伤病。"
            )

        parts = [volume_eval]
        if highlight_str:
            parts.append(highlight_str)
        parts.append(coach_advice)
        return " ".join(parts)

    @staticmethod
    def get_club_periodic_report(
        club_id: str,
        period_type: str = "week",
        year: Optional[int] = None,
        period_index: Optional[int] = None,
        trail_mode: str = "include",
        period_offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generates comprehensive weekly or monthly training report for a club.
        period_type: 'week' or 'month'
        period_index: week number (1..53) or month number (1..12)
        trail_mode:
          - 'include' (default): 包含越野跑（默认）
          - 'exclude_pace': 仅去除越野配速（保留越野跑量）
          - 'exclude_all': 去除越野跑量与配速（仅统计路跑）
        """
        club = LocalStore.get_club(club_id)
        if not club:
            return {"error": "跑团不存在"}

        trail_mode_val = str(trail_mode or "include").strip().lower()
        if trail_mode_val not in ("include", "exclude_pace", "exclude_all"):
            trail_mode_val = "include"
        trail_mode_labels = {
            "include": "包含越野跑（默认）",
            "exclude_pace": "仅去除越野配速（保留越野跑量）",
            "exclude_all": "去除越野跑量与配速（仅统计路跑）",
        }
        trail_mode_label = trail_mode_labels[trail_mode_val]

        today = get_beijing_today()
        now_year = today.year
        now_month = today.month

        # Defensive sanitize of year & period_index & period_offset
        try:
            target_year = int(year) if (year is not None and not hasattr(year, "default")) else now_year
        except (ValueError, TypeError):
            target_year = now_year

        try:
            period_index_val = int(period_index) if (period_index is not None and not hasattr(period_index, "default")) else None
        except (ValueError, TypeError):
            period_index_val = None

        try:
            offset_val = int(period_offset) if (period_offset is not None and not hasattr(period_offset, "default")) else 0
        except (ValueError, TypeError):
            offset_val = 0

        if period_index_val is None and offset_val != 0:
            if str(period_type) == "month":
                total_months = (now_year * 12 + (now_month - 1)) + offset_val
                target_year = total_months // 12
                period_index_val = (total_months % 12) + 1
            else:
                shifted_day = today + timedelta(days=offset_val * 7)
                iso_y, iso_w, _ = shifted_day.isocalendar()
                target_year = iso_y
                period_index_val = iso_w

        if str(period_type) == "month":
            target_month = period_index_val or now_month
            if target_month < 1 or target_month > 12:
                target_month = now_month
            
            start_date_obj = date(target_year, target_month, 1)
            _, last_day = calendar.monthrange(target_year, target_month)
            end_date_obj = date(target_year, target_month, last_day)
            
            start_iso = f"{start_date_obj.isoformat()}T00:00:00"
            if target_month == 12:
                next_month_start = f"{target_year + 1:04d}-01-01T00:00:00"
            else:
                next_month_start = f"{target_year:04d}-{target_month + 1:02d}-01T00:00:00"
            end_iso = next_month_start
            
            period_label = f"{target_year}年{target_month}月月报"
            date_range_str = f"{start_date_obj.strftime('%Y.%m.%d')} ~ {end_date_obj.strftime('%Y.%m.%d')}"
            is_past_period = (target_year < now_year) or (target_year == now_year and target_month < now_month)
        else:
            # period_type == 'week'
            iso_year, iso_week, _ = today.isocalendar()
            target_week = period_index_val or iso_week
            if target_week < 1 or target_week > 53:
                target_week = iso_week
                
            try:
                start_date_obj = date.fromisocalendar(target_year, target_week, 1) # Monday
                end_date_obj = date.fromisocalendar(target_year, target_week, 7)   # Sunday
            except Exception:
                start_date_obj = today - timedelta(days=today.weekday())
                end_date_obj = start_date_obj + timedelta(days=6)
                
            start_iso = f"{start_date_obj.isoformat()}T00:00:00"
            end_iso = f"{(end_date_obj + timedelta(days=1)).isoformat()}T00:00:00"
            
            period_label = f"{target_year}年第{target_week}周周报"
            date_range_str = f"{start_date_obj.strftime('%m月%d日')} ~ {end_date_obj.strftime('%m月%d日')}"
            is_past_period = (target_year < iso_year) or (target_year == iso_year and target_week < iso_week)

        members = LocalStore.get_club_members(club_id)
        uids = [m["user_id"] for m in members]
        club_name = club.get("name", "跑团")
        if not uids:
            return {
                "club_id": club_id,
                "club_name": club_name,
                "period_type": period_type,
                "period_label": period_label,
                "date_range_str": date_range_str,
                "is_past_period": is_past_period,
                "trail_mode": trail_mode_val,
                "trail_mode_label": trail_mode_label,
                "trail_activities_count": 0,
                "trail_distance_km": 0.0,
                "total_distance_km": 0.0,
                "total_target_km": 0.0,
                "team_completion_rate": 0.0,
                "achieved_members_count": 0,
                "total_activities_count": 0,
                "active_members_count": 0,
                "total_members_count": 0,
                "attendance_rate_pct": 0.0,
                "avg_pace_str": "—",
                "total_elevation_gain_m": 0,
                "total_trimp": 0.0,
                "leaderboard": [],
                "member_progress_list": [],
                "podium": [],
                "hardcore_runner": None,
                "longest_run": None,
                "canova_critique": "暂无队员运动打卡数据。",
                "forward_text": f"🏃‍♂️ 【{club_name}】{period_label}暂无打卡数据。"
            }

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            placeholders = ["?"] * len(uids)
            query = f"""
                SELECT a.*, COALESCE(NULLIF(p.display_name, ''), a.user_id) AS display_name, p.avatar_url
                FROM activities a
                LEFT JOIN profiles p ON a.user_id = p.id
                WHERE a.user_id IN ({','.join(placeholders)})
                  AND a.start_time >= ? AND a.start_time < ?
                  AND {RUNNING_SQL_FILTER.replace('sport_type', 'a.sport_type')}
                ORDER BY a.start_time DESC
            """
            cursor.execute(query, uids + [start_iso, end_iso])
            all_act_rows = [dict(r) for r in cursor.fetchall()]

        trail_acts = [a for a in all_act_rows if LocalStore.is_trail_activity(a)]
        trail_activities_count = len(trail_acts)
        trail_distance_km = round(sum(float(a.get("distance_meters") or 0) for a in trail_acts) / 1000.0, 1)

        if trail_mode_val == "exclude_all":
            act_rows = [a for a in all_act_rows if not LocalStore.is_trail_activity(a)]
        else:
            act_rows = all_act_rows

        if trail_mode_val in ("exclude_pace", "exclude_all"):
            pace_act_rows = [a for a in act_rows if not LocalStore.is_trail_activity(a)]
        else:
            pace_act_rows = act_rows

        # Aggregate team stats
        total_distance_m = sum(float(a.get("distance_meters") or 0) for a in act_rows)
        total_moving_s = sum(int(a.get("moving_time_seconds") or 0) for a in act_rows)
        pace_distance_m = sum(float(a.get("distance_meters") or 0) for a in pace_act_rows)
        pace_moving_s = sum(int(a.get("moving_time_seconds") or 0) for a in pace_act_rows)
        total_elev_m = sum(float(a.get("elevation_gain_meters") or 0) for a in act_rows)
        total_trimp = sum(float(a.get("trimp") or 0) for a in act_rows)
        total_acts_count = len(act_rows)

        total_distance_km = round(total_distance_m / 1000.0, 1)
        total_elev_int = int(round(total_elev_m))
        total_trimp_round = round(total_trimp, 1)

        # Team average pace
        if pace_distance_m > 0 and pace_moving_s > 0:
            sec_km = int(round(pace_moving_s / (pace_distance_m / 1000.0)))
            avg_pace_str = f"{sec_km // 60}:{sec_km % 60:02d} /km"
        else:
            avg_pace_str = "—"

        # Member-level stats
        member_stats_map = {}
        for m in members:
            uid = m["user_id"]
            member_stats_map[uid] = {
                "user_id": uid,
                "display_name": m["display_name"],
                "avatar_url": m["avatar_url"],
                "role": m["role"],
                "distance_m": 0.0,
                "moving_s": 0,
                "pace_distance_m": 0.0,
                "pace_moving_s": 0,
                "activities_count": 0,
                "run_days": set(),
                "elevation_m": 0.0,
                "longest_m": 0.0,
                "trimp": 0.0,
            }

        for a in act_rows:
            uid = a["user_id"]
            if uid in member_stats_map:
                dm = float(a.get("distance_meters") or 0)
                ms = int(a.get("moving_time_seconds") or 0)
                el = float(a.get("elevation_gain_meters") or 0)
                tr = float(a.get("trimp") or 0)
                day_str = str(a.get("start_time") or "")[:10]
                is_trail = LocalStore.is_trail_activity(a)

                member_stats_map[uid]["distance_m"] += dm
                member_stats_map[uid]["moving_s"] += ms
                if not (trail_mode_val in ("exclude_pace", "exclude_all") and is_trail):
                    member_stats_map[uid]["pace_distance_m"] += dm
                    member_stats_map[uid]["pace_moving_s"] += ms
                member_stats_map[uid]["activities_count"] += 1
                if day_str:
                    member_stats_map[uid]["run_days"].add(day_str)
                member_stats_map[uid]["elevation_m"] += el
                member_stats_map[uid]["trimp"] += tr
                if dm > member_stats_map[uid]["longest_m"]:
                    member_stats_map[uid]["longest_m"] = dm

        # Format leaderboard and member progress list
        leaderboard = []
        member_progress_list = []
        active_uids = set()
        for uid, stat in member_stats_map.items():
            km = round(stat["distance_m"] / 1000.0, 1)
            if stat["activities_count"] > 0:
                active_uids.add(uid)
            if stat["pace_distance_m"] > 0 and stat["pace_moving_s"] > 0:
                s_km = int(round(stat["pace_moving_s"] / (stat["pace_distance_m"] / 1000.0)))
                p_str = f"{s_km // 60}:{s_km % 60:02d} /km"
            else:
                p_str = "—"
            
            # Retrieve member's goal for this period
            g = LocalStore.get_goal(uid)
            if period_type == "month":
                tgts = g.get("monthly_targets") or [200.0] * 12
                month_idx = target_month - 1
                if isinstance(tgts, list) and 0 <= month_idx < len(tgts):
                    t_val = float(tgts[month_idx] or 0.0)
                else:
                    t_val = float(g.get("target_distance") or 200.0)
                target_km = round(t_val, 1)
            else:
                # Weekly target (respect locked week target from weekly_targets_map)
                w_map = g.get("weekly_targets_map") or {}
                rep_week_key = f"{target_year}-W{target_week:02d}"
                if rep_week_key in w_map and float(w_map[rep_week_key]) > 0:
                    target_km = round(float(w_map[rep_week_key]), 1)
                elif rep_week_key == g.get("current_week_key") and g.get("current_week_target") and float(g["current_week_target"]) > 0:
                    target_km = round(float(g["current_week_target"]), 1)
                else:
                    w_target = g.get("weekly_target")
                    if w_target is not None and float(w_target) > 0:
                        target_km = round(float(w_target), 1)
                    else:
                        m_idx = start_date_obj.month - 1
                        tgts = g.get("monthly_targets") or [200.0] * 12
                        if isinstance(tgts, list) and 0 <= m_idx < len(tgts):
                            m_val = float(tgts[m_idx] or 0.0)
                        else:
                            m_val = float(g.get("target_distance") or 200.0)
                        target_km = round(m_val / 4.0, 1)

            completion_rate = round((km / target_km) * 100.0, 1) if target_km > 0 else 0.0
            is_achieved = (km >= target_km and target_km > 0)
            if is_achieved:
                status_text = "已达标"
            elif is_past_period:
                status_text = "未达标"
            elif target_km > 0:
                status_text = "进行中"
            else:
                status_text = "未设定"

            item_data = {
                "user_id": uid,
                "display_name": stat["display_name"],
                "name": stat["display_name"] or "跑者",
                "avatar_url": stat["avatar_url"],
                "role": stat["role"],
                "distance_km": km,
                "actual_km": km,
                "total_distance_km": km,
                "target_km": target_km,
                "completion_rate": completion_rate,
                "completion_pct": completion_rate,
                "is_achieved": is_achieved,
                "status": status_text,
                "remaining_km": round(max(0.0, target_km - km), 1),
                "runs_count": stat["activities_count"],
                "total_activities": stat["activities_count"],
                "active_days_count": len(stat["run_days"]),
                "avg_pace": p_str,
                "avg_pace_str": p_str,
                "elevation_gain_m": int(round(stat["elevation_m"])),
                "trimp": round(stat["trimp"], 1),
                "longest_km": round(stat["longest_m"] / 1000.0, 2)
            }
            leaderboard.append(item_data)
            member_progress_list.append(dict(item_data))

        # Sort leaderboard by distance descending, then by runs_count
        leaderboard.sort(key=lambda x: (x["distance_km"], x["runs_count"]), reverse=True)
        for i, item in enumerate(leaderboard):
            item["rank"] = i + 1

        # Sort member_progress_list by completion_rate desc, then distance_km desc
        member_progress_list.sort(key=lambda x: (x["completion_rate"], x["distance_km"]), reverse=True)
        for i, item in enumerate(member_progress_list):
            item["progress_rank"] = i + 1

        total_target_km = round(sum(item["target_km"] for item in member_progress_list), 1)
        achieved_members_count = sum(1 for item in member_progress_list if item["is_achieved"])
        team_completion_rate = round(total_distance_km / total_target_km * 100.0, 1) if total_target_km > 0 else 0.0

        active_count = len(active_uids)
        total_members_count = len(members)
        attendance_rate = round(active_count / total_members_count * 100, 1) if total_members_count > 0 else 0.0

        # Podium (Top 3 with distance > 0)
        podium = [dict(item) for item in leaderboard if item["distance_km"] > 0][:3]
        for p in podium:
            p["name"] = p.get("display_name") or "跑者"
            p["total_distance_km"] = p.get("distance_km") or 0.0

        # Highlights: Hardcore runner (most runs) & Longest single run
        hardcore_runner = None
        active_items = [item for item in leaderboard if item["runs_count"] > 0]
        if active_items:
            hardcore_runner = max(active_items, key=lambda x: (x["runs_count"], x["active_days_count"]))

        longest_run = None
        if act_rows:
            best_act = max(act_rows, key=lambda x: float(x.get("distance_meters") or 0))
            best_act_km = round(float(best_act.get("distance_meters") or 0) / 1000.0, 2)
            if best_act_km > 0:
                longest_run = {
                    "user_id": best_act.get("user_id"),
                    "runner_name": best_act.get("display_name"),
                    "activity_name": best_act.get("name"),
                    "distance_km": best_act_km,
                    "avg_pace_str": best_act.get("avg_pace_str"),
                    "start_time": best_act.get("start_time")
                }

        # Renato Canova team critique
        canova_critique = LocalStore._generate_team_canova_critique(
            club_name=club_name,
            period_type=period_type,
            period_label=period_label,
            total_km=total_distance_km,
            avg_pace_str=avg_pace_str,
            attendance_rate=attendance_rate,
            total_acts_count=total_acts_count,
            podium=podium,
            longest_run=longest_run,
            active_count=active_count,
            total_members_count=total_members_count,
            team_completion_rate=team_completion_rate,
            achieved_members_count=achieved_members_count,
            trail_activities_count=trail_activities_count,
            trail_distance_km=trail_distance_km
        )

        # Ready-to-copy WeChat group forwarding text
        forward_lines = [
            f"🏃‍♂️ 【{club_name}】{period_label}战报出炉！🔥",
            f"━━━━━━━━━━━━━━━━━━",
            f"📅 统计周期：{date_range_str}",
        ]
        if trail_mode_val == "exclude_pace":
            forward_lines.append(f"🏔️ 统计口径：{trail_mode_label}（越野 {trail_distance_km} km / {trail_activities_count} 次不计均速）")
        elif trail_mode_val == "exclude_all":
            forward_lines.append(f"🛣️ 统计口径：{trail_mode_label}（已剔除越野 {trail_distance_km} km / {trail_activities_count} 次）")

        forward_lines.extend([
            f"📊 全团总跑量：{total_distance_km} km",
            f"🎯 团队目标完成度：{team_completion_rate}% (目标 {total_target_km} km)",
            f"🏅 目标达标人数：{achieved_members_count}/{total_members_count} 人",
            f"🎯 打卡总人次：{total_acts_count} 次",
            f"👥 队员出勤率：{active_count}/{total_members_count} 人 ({attendance_rate}%)",
            f"⏱️ 全团平均配速：{avg_pace_str}{' (不含越野)' if trail_mode_val in ('exclude_pace', 'exclude_all') else ''}",
            f"⛰️ 累计爬升克服：+{total_elev_int} m",
            f"━━━━━━━━━━━━━━━━━━",
            f"🏆 【荣耀榜单 Top 3】"
        ])

        medals = ["🥇 冠军", "🥈 亚军", "🥉 季军"]
        for i, p in enumerate(podium):
            forward_lines.append(f"{medals[i]}：{p['display_name']} —— {p['distance_km']} km (均速 {p['avg_pace_str']})")
        if not podium:
            forward_lines.append("本周期暂无打卡队员，期待大家的启动！")

        if len(leaderboard) > 3:
            forward_lines.append("\n🎖️ 【跑团前十精英】")
            for item in leaderboard[3:10]:
                if item["distance_km"] > 0:
                    forward_lines.append(f"第{item['rank']}名：{item['display_name']} · {item['distance_km']} km")

        forward_lines.append("━━━━━━━━━━━━━━━━━━")
        forward_lines.append("📋 【全员跑量目标与完成度】")
        for item in member_progress_list:
            if item["is_achieved"]:
                tag = "✅已达标"
            elif is_past_period:
                tag = f"{item['completion_rate']}% (未达标)"
            else:
                tag = f"{item['completion_rate']}%"
            forward_lines.append(f"• {item['display_name']}：实际 {item['distance_km']} km / 目标 {item['target_km']} km ({tag})")

        forward_lines.append("━━━━━━━━━━━━━━━━━━")
        if hardcore_runner and hardcore_runner.get("runs_count", 0) > 0:
            forward_lines.append(f"🌟 毅力先锋：{hardcore_runner['display_name']} (打卡 {hardcore_runner['runs_count']} 次)")
        if longest_run:
            forward_lines.append(f"🚀 最长突破：{longest_run['runner_name']} ({longest_run['distance_km']} km · {longest_run['avg_pace_str']})")

        forward_lines.append("━━━━━━━━━━━━━━━━━━")
        forward_lines.append(f"💡 【Renato Canova 科学耐力团队复盘】\n{canova_critique}")
        forward_lines.append("━━━━━━━━━━━━━━━━━━")
        forward_lines.append("各位跑友请紧扣耐力周期，注意超量恢复，健康奔跑，下周继续刷新更好的自己！💪")

        forward_text = "\n".join(forward_lines)
        qr_info = LocalStore.get_pure_miniapp_qrcode("release")

        return {
            "club_id": club_id,
            "club_name": club_name,
            "period_type": period_type,
            "period_label": period_label,
            "date_range_str": date_range_str,
            "is_past_period": is_past_period,
            "trail_mode": trail_mode_val,
            "trail_mode_label": trail_mode_label,
            "trail_activities_count": trail_activities_count,
            "trail_distance_km": trail_distance_km,
            "start_date": start_date_obj.isoformat(),
            "end_date": end_date_obj.isoformat(),
            "total_distance_km": total_distance_km,
            "total_target_km": total_target_km,
            "team_completion_rate": team_completion_rate,
            "achieved_members_count": achieved_members_count,
            "total_activities_count": total_acts_count,
            "active_members_count": active_count,
            "total_members_count": total_members_count,
            "attendance_rate_pct": attendance_rate,
            "avg_pace_str": avg_pace_str,
            "total_elevation_gain_m": total_elev_int,
            "total_trimp": total_trimp_round,
            "leaderboard": leaderboard,
            "member_progress_list": member_progress_list,
            "podium": podium,
            "hardcore_runner": hardcore_runner,
            "longest_run": longest_run,
            "canova_critique": canova_critique,
            "forward_text": forward_text,
            "qrcode_url": qr_info["qrcode_url"],
            "qrcode_base64": qr_info["qrcode_base64"],
            "qr_path": qr_info["qr_path"],
        }

    @staticmethod
    def get_pure_miniapp_qrcode(env_version: str = "release") -> Dict[str, str]:
        """
        Generates and caches the official WeChat Mini Program entry QR code (wxacode)
        pointing purely to 'pages/index/index' WITHOUT any club invitation parameters.
        """
        import base64
        from utils.wechat import wechat_client

        eff_env = env_version if env_version in ("release", "trial", "develop") else "release"
        filename = f"wxacode_pure_home_{eff_env}.jpg"
        avatar_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "avatars")
        os.makedirs(avatar_dir, exist_ok=True)
        file_path = os.path.join(avatar_dir, filename)
        qr_path = "pages/index/index"

        if not os.path.exists(file_path) or os.path.getsize(file_path) < 500:
            try:
                img_bytes = wechat_client.get_wxacode_by_path(
                    path=qr_path,
                    width=280,
                    env_version=eff_env
                )
                if not img_bytes:
                    img_bytes = wechat_client.get_wxacode_unlimit(
                        scene="from=report",
                        page="pages/index/index",
                        width=280,
                        env_version=eff_env
                    )
                if img_bytes and len(img_bytes) >= 500:
                    with open(file_path, "wb") as f:
                        f.write(img_bytes)
            except Exception as e:
                logger.warning(f"[LocalStore] get_pure_miniapp_qrcode failed: {e}")

        qrcode_b64 = ""
        qrcode_url = ""
        if os.path.exists(file_path) and os.path.getsize(file_path) >= 500:
            qrcode_url = f"https://rgm.vanpower.net/api/avatars/{filename}"
            try:
                with open(file_path, "rb") as f:
                    qrcode_b64 = base64.b64encode(f.read()).decode("ascii")
            except Exception:
                pass

        return {
            "qrcode_url": qrcode_url,
            "qrcode_base64": qrcode_b64,
            "qr_path": qr_path,
        }

    @staticmethod
    def _generate_personal_canova_critique(
        display_name: str,
        period_type: str,
        total_km: float,
        target_km: float,
        completion_rate: float,
        runs_count: int,
        active_days: int,
        avg_pace_str: str,
        avg_hr: Optional[int],
        total_elev_m: int,
        longest_run: Optional[Dict[str, Any]],
        fastest_run: Optional[Dict[str, Any]],
        trail_count: int = 0,
        trail_km: float = 0.0
    ) -> str:
        cycle_word = "本周" if period_type == "week" else "本月"
        next_word = "下周" if period_type == "week" else "下月"
        if total_km <= 0 or runs_count <= 0:
            return (
                f"{cycle_word}暂无跑步打卡记录。教练建议：{next_word}可先安排 2~3 次 5~8km 的轻松慢跑，"
                "不追求配速，先把规律出勤的身体节奏找回来。"
            )

        avg_km = round(total_km / max(1, runs_count), 1)
        hr_text = f"，平均心率 {avg_hr} bpm" if avg_hr and avg_hr > 0 else ""
        target_text = f"（目标 {target_km}km，达成率 {completion_rate}%）" if target_km > 0 else ""
        summary = (
            f"{cycle_word}共出勤 {runs_count} 次（{active_days} 天），累计跑量 {total_km}km{target_text}，"
            f"单次均程 {avg_km}km，平均配速 {avg_pace_str}{hr_text}。"
        )

        highlights = []
        if longest_run and float(longest_run.get("distance_km") or 0) >= 8:
            highlights.append(
                f"最长单次完成了 {longest_run['distance_km']}km（配速 {longest_run.get('avg_pace_str') or '—'}）"
            )
        if fastest_run and fastest_run.get("activity_id") != (longest_run or {}).get("activity_id"):
            highlights.append(
                f"最佳配速课 {fastest_run['distance_km']}km（配速 {fastest_run.get('avg_pace_str') or '—'}）"
            )
        if trail_count > 0 and trail_km > 0:
            highlights.append(f"包含 {trail_count} 次越野跑共 {trail_km}km（累计爬升 +{total_elev_m}m）")
        highlight_str = "；".join(highlights) + "。" if highlights else ""

        longest_km = float((longest_run or {}).get("distance_km") or 0)
        if period_type == "week":
            if longest_km >= 22 or total_km >= 65:
                advice = (
                    "教练建议：本周跑量与长距离负荷饱满，下周前两天建议安排休息或 6分以外的慢速恢复跑，"
                    "让腿部肌肉酸胀充分消退，周中再安排 1 次节奏跑或间歇课，避免疲劳累积。"
                )
            elif runs_count <= 2:
                advice = (
                    f"教练建议：本周打卡 {runs_count} 次，建议下周尽量将跑量均衡拆分到每周 3~4 次，"
                    "避免把里程全部集中在周末单次拉练，既能稳步提升有氧耐力，也能显著降低膝踝劳损风险。"
                )
            else:
                advice = (
                    "教练建议：本周出勤频次与单次距离分配合理，下周请继续保持“平日轻松有氧跑 + 周末 1 次长距离”的训练结构，"
                    "平时轻松跑注意压住心率，把体能留给重点课表。"
                )
        else:
            weekly_avg_runs = round(runs_count / 4.2, 1)
            weekly_avg_km = round(total_km / 4.2, 1)
            if completion_rate >= 100:
                advice = (
                    f"教练建议：本月超额完成目标（周均 {weekly_avg_km}km / {weekly_avg_runs} 练），执行力极佳！"
                    f"{next_word}建议在巩固当前跑量的基础上，坚持约 80% 跑量用轻松可交谈配速完成，每周精选 1 次速度/节奏课与 1 次周末长距离，稳中求进。"
                )
            else:
                advice = (
                    f"教练建议：本月周均出勤约 {weekly_avg_runs} 次（周均 {weekly_avg_km}km）。"
                    f"{next_word}建议优先固定每周 3~4 个跑步日，先保证出勤频次与轻松有氧跑时长，待有氧耐力扎实后再逐步增加长距离距离。"
                )

        return f"{summary}{highlight_str}{advice}"

    @staticmethod
    def get_user_periodic_report(
        uid: str,
        period_type: str = "week",
        year: Optional[int] = None,
        period_index: Optional[int] = None,
        trail_mode: str = "include"
    ) -> Dict[str, Any]:
        """
        Generates a personal weekly or monthly running report for a single user.
        Supports trail_mode: 'include' (default), 'exclude_pace', 'exclude_all'.
        """
        canonical_uid = LocalStore.resolve_user_id(uid)
        profile = LocalStore.get_profile(canonical_uid) or {}
        display_name = profile.get("display_name") or "跑者"
        avatar_url = profile.get("avatar_url") or ""

        trail_mode_val = str(trail_mode or "include").strip().lower()
        if trail_mode_val not in ("include", "exclude_pace", "exclude_all"):
            trail_mode_val = "include"
        trail_mode_labels = {
            "include": "包含越野跑（默认）",
            "exclude_pace": "仅去除越野配速（保留越野跑量）",
            "exclude_all": "去除越野跑量与配速（仅统计路跑）",
        }
        trail_mode_label = trail_mode_labels[trail_mode_val]

        today = get_beijing_today()
        now_year = today.year
        now_month = today.month

        try:
            target_year = int(year) if (year is not None and not hasattr(year, "default")) else now_year
        except (ValueError, TypeError):
            target_year = now_year

        try:
            period_index_val = int(period_index) if (period_index is not None and not hasattr(period_index, "default")) else None
        except (ValueError, TypeError):
            period_index_val = None

        if str(period_type) == "month":
            target_month = period_index_val or now_month
            if target_month < 1 or target_month > 12:
                target_month = now_month
            start_date_obj = date(target_year, target_month, 1)
            _, last_day = calendar.monthrange(target_year, target_month)
            end_date_obj = date(target_year, target_month, last_day)
            start_iso = f"{start_date_obj.isoformat()}T00:00:00"
            if target_month == 12:
                end_iso = f"{target_year + 1:04d}-01-01T00:00:00"
            else:
                end_iso = f"{target_year:04d}-{target_month + 1:02d}-01T00:00:00"
            period_label = f"{target_year}年{target_month}月个人月报"
            date_range_str = f"{start_date_obj.strftime('%Y.%m.%d')} ~ {end_date_obj.strftime('%Y.%m.%d')}"
            is_past_period = (target_year < now_year) or (target_year == now_year and target_month < now_month)
        else:
            iso_year, iso_week, _ = today.isocalendar()
            target_week = period_index_val or iso_week
            if target_week < 1 or target_week > 53:
                target_week = iso_week
            try:
                start_date_obj = date.fromisocalendar(target_year, target_week, 1)
                end_date_obj = date.fromisocalendar(target_year, target_week, 7)
            except Exception:
                start_date_obj = today - timedelta(days=today.weekday())
                end_date_obj = start_date_obj + timedelta(days=6)
            start_iso = f"{start_date_obj.isoformat()}T00:00:00"
            end_iso = f"{(end_date_obj + timedelta(days=1)).isoformat()}T00:00:00"
            period_label = f"{target_year}年第{target_week}周个人周报"
            date_range_str = f"{start_date_obj.strftime('%m月%d日')} ~ {end_date_obj.strftime('%m月%d日')}"
            is_past_period = (target_year < iso_year) or (target_year == iso_year and target_week < iso_week)

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT *
                FROM activities
                WHERE user_id = ?
                  AND start_time >= ? AND start_time < ?
                  AND {RUNNING_SQL_FILTER}
                ORDER BY start_time DESC
                """,
                (canonical_uid, start_iso, end_iso)
            )
            all_act_rows = [dict(r) for r in cursor.fetchall()]

        trail_acts = [a for a in all_act_rows if LocalStore.is_trail_activity(a)]
        trail_activities_count = len(trail_acts)
        trail_distance_km = round(sum(float(a.get("distance_meters") or 0) for a in trail_acts) / 1000.0, 1)

        if trail_mode_val == "exclude_all":
            act_rows = [a for a in all_act_rows if not LocalStore.is_trail_activity(a)]
        else:
            act_rows = all_act_rows

        if trail_mode_val in ("exclude_pace", "exclude_all"):
            pace_act_rows = [a for a in act_rows if not LocalStore.is_trail_activity(a)]
        else:
            pace_act_rows = act_rows

        total_distance_m = sum(float(a.get("distance_meters") or 0) for a in act_rows)
        total_moving_s = sum(int(a.get("moving_time_seconds") or 0) for a in act_rows)
        pace_distance_m = sum(float(a.get("distance_meters") or 0) for a in pace_act_rows)
        pace_moving_s = sum(int(a.get("moving_time_seconds") or 0) for a in pace_act_rows)
        total_elev_m = sum(float(a.get("elevation_gain_meters") or 0) for a in act_rows)
        total_trimp = sum(float(a.get("trimp") or 0) for a in act_rows)
        total_acts_count = len(act_rows)
        active_days_count = len({str(a.get("start_time") or "")[:10] for a in act_rows if a.get("start_time")})

        total_distance_km = round(total_distance_m / 1000.0, 1)
        total_elev_int = int(round(total_elev_m))
        total_trimp_round = round(total_trimp, 1)

        if total_moving_s >= 3600:
            h = total_moving_s // 3600
            m = (total_moving_s % 3600) // 60
            total_moving_time_str = f"{h}小时{m:02d}分"
        elif total_moving_s > 0:
            total_moving_time_str = f"{max(1, total_moving_s // 60)}分钟"
        else:
            total_moving_time_str = "0分钟"

        if pace_distance_m > 0 and pace_moving_s > 0:
            sec_km = int(round(pace_moving_s / (pace_distance_m / 1000.0)))
            avg_pace_str = f"{sec_km // 60}:{sec_km % 60:02d} /km"
        else:
            avg_pace_str = "—"

        hr_acts = [float(a.get("average_heartrate") or 0) for a in act_rows if float(a.get("average_heartrate") or 0) > 0]
        avg_heartrate = int(round(sum(hr_acts) / len(hr_acts))) if hr_acts else None

        # Goal for this period
        g = LocalStore.get_goal(canonical_uid)
        if str(period_type) == "month":
            tgts = g.get("monthly_targets") or [200.0] * 12
            month_idx = target_month - 1
            if isinstance(tgts, list) and 0 <= month_idx < len(tgts):
                t_val = float(tgts[month_idx] or 0.0)
            else:
                t_val = float(g.get("target_distance") or 200.0)
            target_km = round(t_val, 1)
        else:
            w_map = g.get("weekly_targets_map") or {}
            rep_week_key = f"{target_year}-W{target_week:02d}"
            if rep_week_key in w_map and float(w_map[rep_week_key]) > 0:
                target_km = round(float(w_map[rep_week_key]), 1)
            elif rep_week_key == g.get("current_week_key") and g.get("current_week_target") and float(g["current_week_target"]) > 0:
                target_km = round(float(g["current_week_target"]), 1)
            else:
                w_target = g.get("weekly_target")
                if w_target is not None and float(w_target) > 0:
                    target_km = round(float(w_target), 1)
                else:
                    m_idx = start_date_obj.month - 1
                    tgts = g.get("monthly_targets") or [200.0] * 12
                    if isinstance(tgts, list) and 0 <= m_idx < len(tgts):
                        m_val = float(tgts[m_idx] or 0.0)
                    else:
                        m_val = float(g.get("target_distance") or 200.0)
                    target_km = round(m_val / 4.0, 1)

        completion_rate = round((total_distance_km / target_km) * 100.0, 1) if target_km > 0 else 0.0
        remaining_km = round(max(0.0, target_km - total_distance_km), 1)

        longest_run = None
        if act_rows:
            best_act = max(act_rows, key=lambda x: float(x.get("distance_meters") or 0))
            best_km = round(float(best_act.get("distance_meters") or 0) / 1000.0, 2)
            if best_km > 0:
                longest_run = {
                    "activity_id": best_act.get("id"),
                    "activity_name": best_act.get("name") or "跑步训练",
                    "distance_km": best_km,
                    "avg_pace_str": best_act.get("avg_pace_str") or "—",
                    "start_time": str(best_act.get("start_time") or "")[:10],
                }

        fastest_run = None
        eligible_fast = [
            a for a in pace_act_rows
            if float(a.get("distance_meters") or 0) >= 3000 and int(a.get("moving_time_seconds") or 0) > 0
        ]
        if eligible_fast:
            fast_act = min(
                eligible_fast,
                key=lambda x: int(x.get("moving_time_seconds") or 0) / (float(x.get("distance_meters") or 1) / 1000.0)
            )
            fast_km = round(float(fast_act.get("distance_meters") or 0) / 1000.0, 2)
            fastest_run = {
                "activity_id": fast_act.get("id"),
                "activity_name": fast_act.get("name") or "速度训练",
                "distance_km": fast_km,
                "avg_pace_str": fast_act.get("avg_pace_str") or "—",
                "start_time": str(fast_act.get("start_time") or "")[:10],
            }

        activities_list = []
        for a in act_rows[:15]:
            activities_list.append({
                "id": a.get("id"),
                "name": a.get("name") or "跑步",
                "date": str(a.get("start_time") or "")[:10],
                "distance_km": round(float(a.get("distance_meters") or 0) / 1000.0, 2),
                "avg_pace_str": a.get("avg_pace_str") or "—",
                "average_heartrate": a.get("average_heartrate"),
                "elevation_gain_m": int(round(float(a.get("elevation_gain_meters") or 0))),
                "is_trail": LocalStore.is_trail_activity(a),
            })

        canova_critique = LocalStore._generate_personal_canova_critique(
            display_name=display_name,
            period_type=period_type,
            total_km=total_distance_km,
            target_km=target_km,
            completion_rate=completion_rate,
            runs_count=total_acts_count,
            active_days=active_days_count,
            avg_pace_str=avg_pace_str,
            avg_hr=avg_heartrate,
            total_elev_m=total_elev_int,
            longest_run=longest_run,
            fastest_run=fastest_run,
            trail_count=trail_activities_count,
            trail_km=trail_distance_km,
        )

        forward_lines = [
            f"🏃‍♂️ 【{display_name}】{period_label} 🔥",
            "━━━━━━━━━━━━━━━━━━",
            f"📅 统计周期：{date_range_str}",
        ]
        if trail_mode_val != "include":
            forward_lines.append(f"🏔️ 统计口径：{trail_mode_label}")
        forward_lines.extend([
            f"📊 累计跑量：{total_distance_km} km (目标 {target_km} km · 完成度 {completion_rate}%)",
            f"🎯 出勤打卡：{total_acts_count} 次 ({active_days_count} 天) · 累计用时 {total_moving_time_str}",
            f"⏱️ 平均配速：{avg_pace_str}{f' · 平均心率 {avg_heartrate} bpm' if avg_heartrate else ''}",
            f"⛰️ 累计爬升：+{total_elev_int} m",
        ])
        if longest_run:
            forward_lines.append(f"🚀 最长距离：{longest_run['distance_km']} km ({longest_run['avg_pace_str']} · {longest_run['activity_name']})")
        if fastest_run:
            forward_lines.append(f"⚡ 最佳配速：{fastest_run['avg_pace_str']} ({fastest_run['distance_km']} km · {fastest_run['activity_name']})")
        forward_lines.extend([
            "━━━━━━━━━━━━━━━━━━",
            f"💡 【教练周期复盘与建议】\n{canova_critique}",
            "━━━━━━━━━━━━━━━━━━",
            "每一步都算数，继续保持规律出勤与科学奔跑！💪",
        ])

        qr_info = LocalStore.get_pure_miniapp_qrcode("release")

        return {
            "user_id": canonical_uid,
            "display_name": display_name,
            "avatar_url": avatar_url,
            "period_type": period_type,
            "period_label": period_label,
            "date_range_str": date_range_str,
            "is_past_period": is_past_period,
            "trail_mode": trail_mode_val,
            "trail_mode_label": trail_mode_label,
            "trail_activities_count": trail_activities_count,
            "trail_distance_km": trail_distance_km,
            "start_date": start_date_obj.isoformat(),
            "end_date": end_date_obj.isoformat(),
            "total_distance_km": total_distance_km,
            "target_km": target_km,
            "completion_rate": completion_rate,
            "remaining_km": remaining_km,
            "total_activities_count": total_acts_count,
            "active_days_count": active_days_count,
            "total_moving_time_str": total_moving_time_str,
            "avg_pace_str": avg_pace_str,
            "avg_heartrate": avg_heartrate,
            "total_elevation_gain_m": total_elev_int,
            "total_trimp": total_trimp_round,
            "longest_run": longest_run,
            "fastest_run": fastest_run,
            "activities_list": activities_list,
            "canova_critique": canova_critique,
            "forward_text": "\n".join(forward_lines),
            "qrcode_url": qr_info["qrcode_url"],
            "qrcode_base64": qr_info["qrcode_base64"],
            "qr_path": qr_info["qr_path"],
        }

    @staticmethod
    def generate_canova_critique(activity: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> str:
        """
        Generates Renato Canova endurance training philosophy critique based on actual workout metrics,
        personal heart rate reserve (%HRR), age-related recovery, and race terrain (trail vs road).
        """
        dist_m = float(activity.get("distance_meters") or 0)
        dist_km = round(dist_m / 1000.0, 2)
        pace_str = activity.get("avg_pace_str") or "5:30"
        avg_hr = activity.get("average_heartrate")
        trimp = float(activity.get("trimp") or 50)
        elev_gain = float(activity.get("elevation_gain_meters") or activity.get("total_elevation_gain") or activity.get("elevationGain") or 0)
        act_name = str(activity.get("name") or "")

        sport_type = activity.get("sport_type") or activity.get("activity_type")
        act_name_lower = act_name.lower()
        
        # Check non-running sport types and cross-training
        is_swim = (sport_type and sport_type.lower() == "swim") or "泳" in act_name or "swim" in act_name_lower
        is_ride = (sport_type and sport_type.lower() == "ride") or ("骑" in act_name and "跑" not in act_name) or "cycling" in act_name_lower or "bike" in act_name_lower
        is_hike = (sport_type and sport_type.lower() == "hike") or ("徒步" in act_name and "跑" not in act_name)
        is_walk = (sport_type and sport_type.lower() == "walk") or (("健走" in act_name or "散步" in act_name) and "跑" not in act_name)
        is_paddle = (sport_type and sport_type.lower() == "paddleboard") or "桨板" in act_name
        is_strength = (sport_type and sport_type.lower() == "workout" and not is_swim and not is_ride and not is_paddle) or "力量" in act_name or "身训" in act_name or "strength" in act_name_lower

        if is_swim:
            dist_desc = f"{int(dist_m)}米" if dist_m > 0 else "专项"
            return (
                f"【交叉训练 · 游泳 (Cross-Training / Swim)】游泳训练是跑者极佳的无冲击有氧交叉刺激（完成{dist_desc}）。"
                "有效减免下肢各关节与肌腱在铺装路面的离地落地冲击，促进血液循环与淋巴代谢废物排出，并协同增强核心与上肢肌群稳定。"
                " 💡 教练建议：游泳不计入跑量统计，适合作为大强度训练课后或跑休日的主动恢复（Active Recovery）。"
            )
        if is_ride:
            dist_desc = f"{dist_km}km" if dist_km > 0 else ""
            return (
                f"【交叉训练 · 骑行 (Cross-Training / Cycling)】骑行训练可提供低冲击心肺有氧刺激{f'（完成{dist_desc}）' if dist_desc else ''}。"
                "在大幅减轻膝踝关节冲击压力的同时，锻炼股四头肌与臀肌向心做功能力，维持基础心肺耐力。"
                " 💡 教练建议：骑行不计入跑量统计，适合作为减量调整周或轻微不适期的有氧体能维持训练。"
            )
        if is_hike:
            return (
                f"【户外徒步 (Hiking)】徒步活动{f'（克服累计爬升 +{int(elev_gain)}m）' if elev_gain > 0 else ''}。"
                "强化低心率长时间有氧耐力与足踝小肌群稳定性，是跑者提升关节耐受度与有氧底盘的良好补充。"
                " 💡 教练建议：徒步活动不计入跑量统计，注意下山时落脚缓冲与髋膝协同，课后做好小腿与足底筋膜拉伸。"
            )
        if is_walk:
            return (
                "【日常健走 (Walking)】日常步行健走活动，有助于打破久坐僵硬，促进下肢微循环与基础代谢活化。"
                " 💡 教练建议：健走不计入跑步里程统计，保持良好日常活动习惯即可。"
            )
        if is_paddle:
            return (
                "【交叉训练 · 水上运动 (Cross-Training / Paddleboard)】桨板水上活动，深度调动核心肌群与平衡抗扭转本体感觉。"
                " 💡 教练建议：水上活动不计入跑量统计，适合作为跑休期的趣味全身协同训练。"
            )
        if is_strength or (not LocalStore.is_running_activity(sport_type) and ("训" in act_name or "workout" in act_name_lower or "力量" in act_name)):
            return (
                "【力量与体能强化 (Strength & Conditioning)】针对跑者核心骨盆稳定、髋臀外展肌群及下肢肌腱刚性的抗阻力量训练。"
                "不仅能显著提升长跑后程的动作经济性，更是防伤防过度劳损的科学根基。"
                " 💡 教练建议：力量训练不计入跑量统计，建议每周保持 1~2 次专项力量强化，课后注意结缔组织深层滚压。"
            )
        if not LocalStore.is_running_activity(sport_type) and sport_type:
            return (
                f"【交叉运动 · {sport_type}】多元化交叉活动，有助于唤醒不同动力链肌肉群，打破单调跑步重复动作带来的局部肌纤维应力累积。"
                " 💡 教练建议：非跑步运动不计入跑步里程与配速统计，保持多元化身体机能激活。"
            )

        if dist_km < 1.0:
            return "短距离激活训练，建议结合动态拉伸与下肢力量辅助练习。"

        if isinstance(profile, str):
            profile = LocalStore.get_profile(profile)
        if profile is None and activity.get("user_id"):
            profile = LocalStore.get_profile(activity["user_id"])

        max_hr = float((profile.get("max_heart_rate") if profile else None) or 190)
        rest_hr = float((profile.get("resting_heart_rate") if profile else None) or 56)
        hrr = max(20.0, max_hr - rest_hr)

        # Dynamic physiological thresholds
        recovery_ceiling = rest_hr + hrr * 0.62  # Active recovery ceiling
        aerobic_ceiling = rest_hr + hrr * 0.75   # Fundamental aerobic ceiling
        threshold_ceiling = rest_hr + hrr * 0.88 # Lactate threshold ceiling

        from utils.running_metrics import get_age_from_dob
        age = get_age_from_dob(profile.get("date_of_birth") if profile else None)
        age_advice = "（大师组留足48h恢复）" if (age and age >= 50 and dist_km >= 10) else ""

        # Determine runner tier for tone adaptation
        def _parse_pb(v):
            if v is None:
                return None
            if isinstance(v, (int, float)):
                return float(v) if v > 0 else None
            if isinstance(v, str):
                p = v.strip().split(":")
                try:
                    if len(p) == 3:
                        return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])
                    if len(p) == 2:
                        return int(p[0]) * 60 + float(p[1])
                    return float(v)
                except Exception:
                    return None
            return None

        v_meta = LocalStore.resolve_verified_runner_profile_and_pbs(
            str(activity.get("user_id") or ""),
            profile=profile,
            query_activities=False,
        )
        m_pb = v_meta.get("verified_mp_sec")
        h_pb = v_meta.get("verified_hp_sec")
        raw_years = profile.get("years_running") if profile else None
        try:
            years = float(raw_years) if raw_years is not None else 1.0
        except Exception:
            years = 1.0

        is_elite = bool(
            (m_pb and m_pb <= 3 * 3600 + 5 * 60)
            or (h_pb and h_pb <= 85 * 60 and (not m_pb or m_pb <= 3 * 3600 + 15 * 60))
        )
        is_beginner = (years <= 2 or (m_pb and m_pb > 4 * 3600) or (not m_pb and not h_pb)) and not is_elite
        is_intermediate = not is_elite and not is_beginner

        def _pace_to_sec(p_str: Optional[str]) -> Optional[int]:
            if not p_str:
                return None
            clean = str(p_str).replace("/km", "").replace("'", ":").replace("’", ":").replace("″", "").replace('"', "").strip()
            m_match = re.search(r"(\d{1,2})\s*[:分]\s*(\d{1,2})", clean)
            if m_match:
                return int(m_match.group(1)) * 60 + int(m_match.group(2))
            return None

        def _sec_to_pace(sec_val: float) -> str:
            s_int = max(150, int(round(sec_val)))
            return f"{s_int // 60}:{s_int % 60:02d}/km"

        clean_pace_display = str(pace_str).replace("/km", "").strip() + "/km" if pace_str else "5:30/km"
        pace_seconds = _pace_to_sec(pace_str) or 330

        # ── 1. Evaluate Training Plan Workout Execution (focusing on Main Set when Warm-up + Main + Cool-down exists) ──
        plan_exec_block = LocalStore._evaluate_plan_workout_execution(
            activity=activity,
            dist_km=dist_km,
            pace_str=clean_pace_display,
            pace_seconds=pace_seconds,
            avg_hr=avg_hr,
            aerobic_ceiling=aerobic_ceiling,
            threshold_ceiling=threshold_ceiling,
        )

        # ── 2. Build Concrete Progress Encouragement for Beginner / Intermediate Runners (Distance, Pace, HR) ──
        tier_encourage = ""
        if is_elite:
            tier_encourage = " ⚡【精英专项进阶】专项指标达成，紧扣配速收敛。"
        else:
            tier_encourage = LocalStore._build_runner_progress_encouragement(
                activity=activity,
                dist_km=dist_km,
                pace_str=clean_pace_display,
                pace_seconds=pace_seconds,
                avg_hr=avg_hr,
                aerobic_ceiling=aerobic_ceiling,
                is_beginner=is_beginner,
            )

        hr_brief = f"，均心 {int(round(float(avg_hr)))}bpm" if avg_hr else ""

        # Check for Trail / Mountain running
        is_trail = elev_gain >= 200 or "越野" in act_name or "山" in act_name or "trail" in act_name.lower()
        if is_trail:
            if elev_gain >= 500 or dist_km >= 20:
                workout_type = "山地专项耐力"
                analysis = f"{dist_km}km（爬升 +{int(elev_gain)}m{hr_brief}），深度强化股四头肌离心抗疲劳与爬坡能力。"
                advice = f"注意下肢拉伸与蛋白补充{age_advice}。"
            else:
                workout_type = "山地有氧跑"
                analysis = f"{dist_km}km（爬升 +{int(elev_gain)}m，{clean_pace_display}），有效激活踝膝稳定与核心平衡。"
                advice = f"注意下坡缓震与小腿放松{age_advice}。"
            base_text = f"【{workout_type}】{plan_exec_block}" if plan_exec_block else f"【{workout_type}】{analysis}"
            return f"{base_text}{tier_encourage} 💡 {advice}"

        is_name_interval = bool(
            re.search(
                r"(\d+\s*[*xX×]\s*\d+|\d+\s*(?:m|米|km|k)\s*[*xX×+]|\b(?:1st|2nd|3rd|\d+th)\b|间歇|变速|法特莱克)",
                act_name,
                re.I,
            )
        )
        if not plan_exec_block and dist_km < 5.0 and "热身" in act_name:
            workout_type = "热身激活跑"
            analysis = f"{dist_km}km @ {clean_pace_display}{hr_brief}，循序唤醒心肺与肌肉弹性，为后续主课做好准备。"
            advice = "热身充分后即可切入主课强度。"
        elif not plan_exec_block and dist_km < 5.0 and "冷身" in act_name:
            workout_type = "冷身排酸跑"
            analysis = f"{dist_km}km @ {clean_pace_display}{hr_brief}，平缓回落心率，促进乳酸代谢与神经放松。"
            advice = "跑后做好静态拉伸与补水。"
        elif not plan_exec_block and is_name_interval:
            workout_type = "间歇专项刺激"
            analysis = f"{dist_km}km @ {clean_pace_display}{hr_brief}，有效刺激最大摄氧量、步频神经募集与抗乳酸能力。"
            advice = f"注意组间恢复与课后深度泡沫轴放松{age_advice}。"
        elif not plan_exec_block and (
            any(k in act_name for k in ("速耐", "节奏", "门槛", "乳酸"))
            or (dist_km >= 3.0 and avg_hr and avg_hr >= threshold_ceiling)
        ):
            workout_type = "混氧门槛突破" if (avg_hr and avg_hr >= threshold_ceiling) else "专项节奏进阶"
            analysis = f"{dist_km}km @ {clean_pace_display}{hr_brief}，有效推高乳酸清除速率与专项定速巡航能力。"
            advice = f"未来48h以轻松慢跑恢复为主{age_advice}。"
        elif dist_km >= 20:
            if avg_hr and avg_hr < aerobic_ceiling:
                workout_type = "长距离有氧耐力"
                analysis = f"{dist_km}km @ {clean_pace_display}（均心 {int(avg_hr)}bpm < 有氧上限 {int(aerobic_ceiling)}bpm），后程耐力扎实。"
                advice = f"明日建议休整或慢跑排酸{age_advice}。"
            else:
                workout_type = "马拉松专项耐力"
                analysis = f"{dist_km}km @ {clean_pace_display}{hr_brief}，高质量提升后程抗掉速韧性。"
                advice = f"及时补充碳水电解质，隔天再上强度{age_advice}。"
        elif dist_km >= 12:
            if avg_hr and avg_hr >= threshold_ceiling:
                workout_type = "混氧门槛突破"
                analysis = f"{dist_km}km @ {clean_pace_display}（均心 {int(avg_hr)}bpm 达门槛区），有效推高乳酸清除速率。"
                advice = f"未来48h以轻松慢跑恢复为主{age_advice}。"
            else:
                workout_type = "稳态有氧进阶"
                analysis = f"{dist_km}km @ {clean_pace_display}{hr_brief}，心率漂移可控，步频节奏稳健。"
                advice = f"课后做好腘绳肌与小腿拉伸{age_advice}。"
        elif dist_km >= 6:
            if avg_hr and avg_hr < recovery_ceiling:
                workout_type = "低心率恢复跑"
                analysis = f"{dist_km}km @ {clean_pace_display}（均心 {int(avg_hr)}bpm），轻松排酸且无额外神经疲劳。"
                advice = "恢复到位，下堂主课可按计划推进。"
            else:
                workout_type = "基础有氧跑"
                analysis = f"{dist_km}km @ {clean_pace_display}{hr_brief}，平稳巩固有氧底座。"
                advice = f"课后适度拉伸放松{age_advice}。"
        else:
            workout_type = "短程激活跑"
            analysis = f"{dist_km}km @ {clean_pace_display}{hr_brief}，步频轻快，适合神经唤醒或排酸。"
            advice = "跑后做好动态拉伸。"

        base_text = f"【{workout_type}】{plan_exec_block}" if plan_exec_block else f"【{workout_type}】{analysis}"
        return f"{base_text}{tier_encourage} 💡 {advice}"

    @staticmethod
    def _evaluate_plan_workout_execution(
        activity: Dict[str, Any],
        dist_km: float,
        pace_str: str,
        pace_seconds: int,
        avg_hr: Optional[Any],
        aerobic_ceiling: float,
        threshold_ceiling: float,
    ) -> str:
        """
        Matches the activity against the runner's scheduled workout on that date (if any) and evaluates
        execution across Distance, Pace, and Heart Rate. When the scheduled workout contains
        Warm-up + Main Set + Cool-down (热身+主课+冷身), focuses specifically on the Main Set execution.
        If pace / distance / combination has a large discrepancy from the scheduled workout, returns ""
        so Canova Coach directly critiques the workout's actual training effect without schedule comparison.
        """
        uid = activity.get("user_id")
        act_date = str(activity.get("start_time") or "")[:10]
        if not uid or not act_date or len(act_date) < 10:
            return ""

        canonical_uid = LocalStore.resolve_user_id(uid)
        planned_day: Optional[Dict[str, Any]] = None
        same_day_runs: List[Dict[str, Any]] = []

        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT status, schedule_data
                    FROM training_plans
                    WHERE (user_id = ? OR user_id = ?)
                      AND status IN ('active', 'published')
                    ORDER BY CASE WHEN status = 'active' THEN 0 ELSE 1 END, updated_at DESC
                    LIMIT 5
                    """,
                    (canonical_uid, uid),
                )
                for row in cursor.fetchall():
                    try:
                        sched = json.loads(row["schedule_data"] or "{}")
                    except Exception:
                        continue
                    for w in sched.get("weeks") or []:
                        for d in w.get("days") or []:
                            if str(d.get("date") or "")[:10] == act_date:
                                planned_day = d
                                break
                        if planned_day:
                            break
                    if planned_day:
                        break

                if planned_day:
                    cursor.execute(
                        f"""
                        SELECT id, name, start_time, distance_meters, moving_time_seconds,
                               avg_pace_str, average_heartrate, max_heartrate, laps_data, splits_data
                        FROM activities
                        WHERE (user_id = ? OR user_id = ?)
                          AND substr(start_time, 1, 10) = ?
                          AND {RUNNING_SQL_FILTER}
                        ORDER BY start_time ASC
                        """,
                        (canonical_uid, uid, act_date),
                    )
                    same_day_runs = [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logger.debug(f"Plan workout lookup in generate_canova_critique skipped: {e}")
            return ""

        if not planned_day:
            return ""

        w_type = str(planned_day.get("workout_type") or "easy_run").strip().lower()
        plan_title_raw = str(planned_day.get("title") or "今日课表").strip()
        plan_title = re.sub(r"\s*[\(（].*?[\)）]", "", plan_title_raw).strip() or plan_title_raw
        plan_dist = float(planned_day.get("distance_km") or 0.0)
        plan_pace = str(planned_day.get("target_pace") or "").strip()
        plan_hr = str(planned_day.get("target_hr_zone") or "").strip()
        plan_desc = str(planned_day.get("description") or "").strip()

        if (
            w_type in ("rest", "travel", "cross_training", "strength")
            or plan_dist <= 0
            or any(k in plan_title_raw for k in ("完全休息", "跑休", "休整日"))
        ):
            return ""

        def _parse_pace_sec(s: str) -> List[int]:
            matches = re.findall(r"(\d{1,2})\s*[:'’分]\s*(\d{2})", s or "")
            res = []
            for m_p, s_p in matches:
                sec = int(m_p) * 60 + int(s_p)
                if 150 <= sec <= 600:
                    res.append(sec)
            return res

        def _fmt_sec(sec_val: float) -> str:
            s_i = max(150, int(round(sec_val)))
            return f"{s_i // 60}:{s_i % 60:02d}/km"

        combined_text = f"{plan_title} {plan_desc}"
        has_explicit_wucd = any(k in combined_text for k in ("热身", "冷身", "主课", "组 ×", "组×", "×")) or ("+" in plan_desc and ("km" in plan_desc.lower() or "公里" in plan_desc))
        has_warmup_cooldown = has_explicit_wucd

        # Parse warm-up and cool-down distances if explicitly written in description/title
        wu_match = re.search(r"热身\s*(\d+(?:\.\d+)?)\s*(?:km|k|公里)", combined_text, re.IGNORECASE)
        cd_match = re.search(r"(?:(\d+(?:\.\d+)?)\s*(?:km|k|公里)\s*冷身|冷身\s*(\d+(?:\.\d+)?)\s*(?:km|k|公里))", combined_text, re.IGNORECASE)
        wu_km = float(wu_match.group(1)) if wu_match else (2.0 if "热身" in combined_text else 0.0)
        cd_km = float(cd_match.group(1) or cd_match.group(2)) if cd_match else (1.5 if "冷身" in combined_text else 0.0)

        # Extract Main Set clause from description (e.g. between '+' segments)
        main_clause = ""
        if "+" in plan_desc:
            parts = [p.strip() for p in plan_desc.split("+") if p.strip()]
            non_wucd = [p for p in parts if not p.startswith("热身") and "冷身" not in p[:6]]
            if non_wucd:
                main_clause = non_wucd[0].split("。")[0].strip()
        if not main_clause and has_warmup_cooldown:
            main_clause = plan_title

        planned_main_km = max(1.0, round(plan_dist - wu_km - cd_km, 1)) if (wu_km + cd_km) > 0 and plan_dist > (wu_km + cd_km + 1.0) else plan_dist

        from utils.workout_segmentation import (
            _extract_normalized_splits,
            has_large_plan_discrepancy,
            segment_workout_phases,
        )

        merged_act = dict(activity)
        if same_day_runs and activity.get("id"):
            matched_same = next((r for r in same_day_runs if r.get("id") == activity.get("id")), None)
            if matched_same:
                for k_f in ("laps_data", "splits_data"):
                    if not merged_act.get(k_f) and matched_same.get(k_f):
                        merged_act[k_f] = matched_same[k_f]

        raw_track = merged_act.get("gps_track_data")
        if isinstance(raw_track, str) and raw_track.strip():
            try:
                raw_track = json.loads(raw_track)
            except Exception:
                raw_track = None
        primary_laps, _, telemetry = _extract_normalized_splits(
            merged_act, raw_track if isinstance(raw_track, dict) else None
        )
        seg_phases, seg_interval_meta = (
            segment_workout_phases(primary_laps, telemetry, planned_wu_km=wu_km, planned_cd_km=cd_km)
            if len(primary_laps) >= 2
            else ([], None)
        )

        # Evaluate actual execution (handling multi-run split recordings vs single combined recording)
        total_day_km = round(sum(float(r.get("distance_meters") or 0) / 1000.0 for r in same_day_runs), 1) if same_day_runs else dist_km
        eval_dist_km = dist_km
        eval_pace_sec = pace_seconds
        eval_pace_str = pace_str
        eval_hr = int(round(float(avg_hr))) if avg_hr else None
        main_segment_note = ""

        if len(same_day_runs) >= 2:
            # Runner recorded separate activities on the same day (e.g. Warm-up + Main Set + Cool-down)
            def _run_score(r: Dict[str, Any]) -> Tuple[float, float]:
                d_m = float(r.get("distance_meters") or 0)
                p_s = (_parse_pace_sec(str(r.get("avg_pace_str") or "")) or [400])[0]
                return (d_m, -p_s)

            main_run = max(same_day_runs, key=_run_score)
            if activity.get("id") and main_run.get("id") and activity.get("id") != main_run.get("id"):
                return ""
            main_km = round(float(main_run.get("distance_meters") or 0) / 1000.0, 1)
            main_p_str = str(main_run.get("avg_pace_str") or pace_str).replace("/km", "").strip() + "/km"
            main_p_sec = (_parse_pace_sec(main_p_str) or [pace_seconds])[0]
            main_hr_val = main_run.get("average_heartrate") or avg_hr

            eval_dist_km = main_km
            eval_pace_sec = main_p_sec
            eval_pace_str = main_p_str
            eval_hr = int(round(float(main_hr_val))) if main_hr_val else eval_hr
            main_segment_note = f"分段{len(same_day_runs)}趟共{total_day_km}km，主课{main_km}km@{main_p_str}" + (f"、均心{eval_hr}bpm" if eval_hr else "")
            has_warmup_cooldown = True
        elif seg_phases and has_warmup_cooldown:
            m_phs = [p for p in seg_phases if p.get("phase_type") not in ("warmup", "cooldown")] or seg_phases
            seg_main_km = round(sum(float(p.get("distance_km") or 0.0) for p in m_phs), 1)
            seg_main_dur = sum(int(p.get("duration_s") or 0) for p in m_phs)
            seg_main_sec = (
                int(seg_interval_meta["work_pace_sec"])
                if (seg_interval_meta and seg_interval_meta.get("work_pace_sec"))
                else (int(round(seg_main_dur / seg_main_km)) if seg_main_km > 0.1 and seg_main_dur > 0 else pace_seconds)
            )
            seg_main_p_str = _fmt_sec(seg_main_sec)
            eval_dist_km = seg_main_km
            eval_pace_sec = seg_main_sec
            eval_pace_str = seg_main_p_str
            hr_main_desc = f"，均心{eval_hr}bpm" if eval_hr else ""
            main_segment_note = f"主课约{seg_main_km}km（{seg_main_p_str}{hr_main_desc}）"
        elif has_warmup_cooldown and (wu_km + cd_km) > 0 and dist_km > (wu_km + cd_km + 2.0):
            # Single continuous run containing Warm-up + Main Set + Cool-down (no granular laps)
            actual_main_km = round(max(1.0, dist_km - wu_km - cd_km), 1)
            # Estimate Main Set pace by deducting warm-up/cool-down slow jog time (~35s/km slower than overall avg)
            wucd_km = min(dist_km * 0.4, wu_km + cd_km)
            total_sec = dist_km * pace_seconds
            wucd_sec = wucd_km * (pace_seconds + 30)
            est_main_sec = max(165, int(round((total_sec - wucd_sec) / max(1.0, dist_km - wucd_km))))
            est_main_pace_str = _fmt_sec(est_main_sec)
            eval_dist_km = actual_main_km
            eval_pace_sec = est_main_sec
            hr_main_desc = f"，均心{eval_hr}bpm" if eval_hr else ""
            main_segment_note = f"主课约{actual_main_km}km（推算{est_main_pace_str}{hr_main_desc}）"

        # Compare Distance & Check for Large Discrepancies in Pace / Distance / Combination
        ref_total_km = total_day_km if len(same_day_runs) >= 2 else dist_km
        if has_large_plan_discrepancy(
            planned_day=planned_day,
            activity=merged_act,
            eval_total_km=ref_total_km,
            eval_main_km=eval_dist_km if has_warmup_cooldown else ref_total_km,
            planned_main_km=planned_main_km if has_warmup_cooldown else plan_dist,
            eval_pace_sec=eval_pace_sec,
            phases=seg_phases if seg_phases else None,
            interval_meta=seg_interval_meta,
            same_day_runs=same_day_runs,
            aerobic_ceiling=aerobic_ceiling,
            threshold_ceiling=threshold_ceiling,
        ):
            return ""

        dist_pct = int(round((ref_total_km / max(0.5, plan_dist)) * 100))
        if dist_pct >= 80:
            dist_verdict = f"达成率 {dist_pct}%"
        else:
            dist_verdict = f"跑量缩减·达成率 {dist_pct}%"

        # Compare Pace (prioritize Main Set target pace if present in main_clause)
        main_paces = _parse_pace_sec(main_clause) if main_clause else []
        plan_paces = main_paces or _parse_pace_sec(plan_pace)
        pace_verdict = ""
        clean_tgt_p = (plan_pace or "").replace(" /km", "/km")
        if plan_paces:
            fastest_tgt = min(plan_paces)
            slowest_tgt = max(plan_paces)
            if fastest_tgt - 8 <= eval_pace_sec <= slowest_tgt + 10:
                pace_verdict = f"配速达标（目标{clean_tgt_p or _fmt_sec(fastest_tgt)}）"
            elif eval_pace_sec < fastest_tgt - 8:
                diff_s = fastest_tgt - eval_pace_sec
                pace_verdict = f"比目标快{diff_s}秒/km"
            else:
                diff_s = eval_pace_sec - slowest_tgt
                pace_verdict = f"较目标放缓{diff_s}秒/km"
        elif plan_pace and plan_pace != "—":
            pace_verdict = f"配速{eval_pace_str}稳健"

        # Compare Heart Rate
        hr_nums = [int(x) for x in re.findall(r"\b(1[1-9]\d)\b", plan_hr)]
        hr_verdict = ""
        if eval_hr:
            if hr_nums:
                hr_low, hr_high = min(hr_nums), max(hr_nums)
                if len(hr_nums) == 1 and ("<" in plan_hr or "以下" in plan_hr):
                    hr_low = 100
                if hr_low - 4 <= eval_hr <= hr_high + 4:
                    hr_verdict = "心率稳控目标区"
                elif eval_hr < hr_low - 4:
                    hr_verdict = f"心率{eval_hr}bpm储备充裕"
                else:
                    hr_verdict = f"心率{eval_hr}bpm略超上限"
            else:
                hr_verdict = f"均心{eval_hr}bpm"

        if has_warmup_cooldown:
            lead_info = main_segment_note or (f"主课「{main_clause}」" if main_clause else f"主课{planned_main_km}km")
            metrics_parts = [p for p in [dist_verdict, pace_verdict, hr_verdict] if p]
            return f"📋【课表主课执行评估 · 《{plan_title}》】热身+主课+冷身，{lead_info}：{'，'.join(metrics_parts)}。"
        else:
            metrics_parts = [
                f"实跑{ref_total_km}/{plan_dist}km（{dist_verdict}）",
                pace_verdict or f"配速{pace_str}",
                hr_verdict,
            ]
            metrics_parts = [p for p in metrics_parts if p]
            return f"📋【课表执行 · 《{plan_title}》】{'，'.join(metrics_parts)}。"

    @staticmethod
    def _build_runner_progress_encouragement(
        activity: Dict[str, Any],
        dist_km: float,
        pace_str: str,
        pace_seconds: int,
        avg_hr: Optional[Any],
        aerobic_ceiling: float,
        is_beginner: bool,
    ) -> str:
        """
        Generates warm, specific, data-backed encouragement for beginner and intermediate runners,
        highlighting concrete improvements in Distance, Pace, and Heart Rate vs their recent runs.
        """
        uid = activity.get("user_id")
        act_id = activity.get("id")
        act_start = str(activity.get("start_time") or "")
        tier_label = "亮点"

        prev_runs: List[Dict[str, Any]] = []
        if uid:
            try:
                canonical_uid = LocalStore.resolve_user_id(uid)
                with sqlite3.connect(DB_PATH) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    if act_start:
                        cursor.execute(
                            f"""
                            SELECT distance_meters, avg_pace_str, average_heartrate, start_time
                            FROM activities
                            WHERE (user_id = ? OR user_id = ?)
                              AND id != ?
                              AND start_time < ?
                              AND distance_meters >= 2000
                              AND {RUNNING_SQL_FILTER}
                            ORDER BY start_time DESC
                            LIMIT 15
                            """,
                            (canonical_uid, uid, act_id or "", act_start),
                        )
                    else:
                        cursor.execute(
                            f"""
                            SELECT distance_meters, avg_pace_str, average_heartrate, start_time
                            FROM activities
                            WHERE (user_id = ? OR user_id = ?)
                              AND id != ?
                              AND distance_meters >= 2000
                              AND {RUNNING_SQL_FILTER}
                            ORDER BY start_time DESC
                            LIMIT 15
                            """,
                            (canonical_uid, uid, act_id or ""),
                        )
                    prev_runs = [dict(r) for r in cursor.fetchall()]
            except Exception:
                prev_runs = []

        def _parse_p(s: Optional[str]) -> Optional[int]:
            if not s:
                return None
            m = re.search(r"(\d{1,2})\s*[:'’分]\s*(\d{2})", str(s))
            if m:
                val = int(m.group(1)) * 60 + int(m.group(2))
                return val if 150 <= val <= 660 else None
            return None

        def _fmt_p(sec_v: float) -> str:
            s_i = max(150, int(round(sec_v)))
            return f"{s_i // 60}:{s_i % 60:02d}/km"

        if prev_runs:
            prev_dists = [round(float(r["distance_meters"]) / 1000.0, 1) for r in prev_runs if r.get("distance_meters")]
            prev_paces = [p for p in (_parse_p(r.get("avg_pace_str")) for r in prev_runs) if p is not None]
            prev_hrs = [float(r["average_heartrate"]) for r in prev_runs if r.get("average_heartrate") and float(r["average_heartrate"]) > 80]

            avg_prev_dist = round(sum(prev_dists) / len(prev_dists), 1) if prev_dists else dist_km
            max_prev_dist = max(prev_dists) if prev_dists else dist_km
            avg_prev_pace = sum(prev_paces) / len(prev_paces) if prev_paces else float(pace_seconds)
            avg_prev_hr = sum(prev_hrs) / len(prev_hrs) if prev_hrs else None

            # 1. Distance progress
            if dist_km > max_prev_dist + 0.3:
                dist_highlight = f"距离 {dist_km}km 创近期新高（+{round(dist_km - max_prev_dist, 1)}km）"
            elif dist_km >= avg_prev_dist + 0.5:
                dist_highlight = f"距离 {dist_km}km（较近期均值 +{round(dist_km - avg_prev_dist, 1)}km）"
            else:
                dist_highlight = f"距离稳健完成 {dist_km}km"

            # 2. Pace progress
            pace_diff = int(round(avg_prev_pace - pace_seconds))
            if pace_diff >= 3:
                pace_highlight = f"配速较近期均速提速 {pace_diff}秒/km"
            elif abs(pace_diff) < 3:
                pace_highlight = f"配速稳定在 {pace_str}"
            else:
                pace_highlight = f"主动压速 {abs(pace_diff)}秒/km 稳住有氧"

            # 3. Heart rate progress
            if avg_hr and avg_prev_hr:
                hr_val = int(round(float(avg_hr)))
                prev_hr_int = int(round(avg_prev_hr))
                hr_diff = prev_hr_int - hr_val
                if hr_diff >= 2:
                    hr_highlight = f"均心下降 {hr_diff}bpm（{hr_val}bpm）"
                elif pace_diff >= 3 and hr_diff >= -2:
                    hr_highlight = f"提速下均心稳守 {hr_val}bpm"
                elif dist_km > avg_prev_dist + 1.0 and hr_diff >= -3:
                    hr_highlight = f"加量下心率稳控 {hr_val}bpm"
                else:
                    hr_highlight = f"心率稳定 {hr_val}bpm"
            elif avg_hr:
                hr_highlight = f"心率稳控 {int(round(float(avg_hr)))}bpm"
            else:
                hr_highlight = "呼吸步频平稳"

            return f" 🌟【{tier_label}】{dist_highlight}、{pace_highlight}、{hr_highlight}，进步扎实！"

        # First recorded run fallback — concise concrete metrics
        hr_clause = f"均心 {int(round(float(avg_hr)))}bpm" if avg_hr else f"有氧上限约 {int(aerobic_ceiling)}bpm"
        return f" 🌟【{tier_label}】扎实完成 {dist_km}km（{pace_str}，{hr_clause}），立下清晰个人基线，继续加油！"

    @staticmethod
    def _query_activity_likers(cursor: sqlite3.Cursor, activity_id: str) -> List[Dict[str, Any]]:
        cursor.execute(
            """
            SELECT l.user_id,
                   COALESCE(NULLIF(p.display_name, ''), NULLIF(p.real_name, ''), '跑友') AS display_name,
                   COALESCE(NULLIF(p.avatar_url, ''), 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80') AS avatar_url,
                   l.created_at
            FROM activity_likes l
            LEFT JOIN profiles p ON l.user_id = p.id
            WHERE l.activity_id = ?
            ORDER BY l.created_at ASC, l.rowid ASC
            """,
            (activity_id,),
        )
        out_likers = []
        for r in cursor.fetchall():
            d = dict(r)
            d["created_at"] = to_beijing_iso(d.get("created_at"))
            out_likers.append(d)
        return out_likers

    @staticmethod
    def toggle_activity_like(activity_id: str, user_id: str) -> Dict[str, Any]:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM activity_likes WHERE activity_id = ? AND (user_id = ? OR user_id = ?)",
                (activity_id, canonical_uid, user_id),
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "DELETE FROM activity_likes WHERE activity_id = ? AND (user_id = ? OR user_id = ?)",
                    (activity_id, canonical_uid, user_id),
                )
                liked = False
            else:
                like_id = f"like_{activity_id}_{canonical_uid}"
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO activity_likes (id, activity_id, user_id, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (like_id, activity_id, canonical_uid, get_beijing_iso()),
                )
                liked = True
            conn.commit()

            likers = LocalStore._query_activity_likers(cursor, activity_id)
            likes_count = len(likers)

            return {"liked": liked, "likes_count": likes_count, "likers": likers}

    @staticmethod
    def add_activity_comment(
        activity_id: str,
        user_id: str,
        author_name: str,
        author_avatar: str,
        content: str,
        parent_id: Optional[str] = None,
        reply_to_user_id: Optional[str] = None,
        reply_to_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            eff_parent_id = parent_id
            eff_reply_uid = reply_to_user_id
            eff_reply_name = reply_to_name

            if parent_id:
                cursor.execute(
                    """
                    SELECT c.id, c.parent_id, c.user_id,
                           COALESCE(NULLIF(p.display_name, ''), c.author_name, '跑友') AS author_name
                    FROM activity_comments c
                    LEFT JOIN profiles p ON c.user_id = p.id
                    WHERE c.id = ?
                    """,
                    (parent_id,),
                )
                parent_row = cursor.fetchone()
                if parent_row:
                    # Keep thread 2-level rooted at the top-level comment while preserving who was replied to
                    eff_parent_id = parent_row["parent_id"] or parent_row["id"]
                    if not eff_reply_uid:
                        eff_reply_uid = parent_row["user_id"]
                    if not eff_reply_name:
                        eff_reply_name = parent_row["author_name"]

            comment_id = f"cmt_{int(datetime.utcnow().timestamp()*1000)}_{uuid.uuid4().hex[:4]}"
            now_str = get_beijing_iso()
            cursor.execute(
                """
                INSERT INTO activity_comments (
                    id, activity_id, user_id, author_name, author_avatar,
                    content, parent_id, reply_to_user_id, reply_to_name, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    comment_id,
                    activity_id,
                    user_id,
                    author_name,
                    author_avatar,
                    content,
                    eff_parent_id,
                    eff_reply_uid,
                    eff_reply_name,
                    now_str,
                ),
            )
            conn.commit()

            return {
                "id": comment_id,
                "activity_id": activity_id,
                "user_id": user_id,
                "author_name": author_name,
                "author_avatar": author_avatar,
                "content": content,
                "parent_id": eff_parent_id,
                "reply_to_user_id": eff_reply_uid,
                "reply_to_name": eff_reply_name,
                "created_at": now_str,
            }

    @staticmethod
    def delete_activity_comment(comment_id: str, user_id: Optional[str] = None) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute(
                    "DELETE FROM activity_comments WHERE (id = ? AND user_id = ?) OR parent_id = ?",
                    (comment_id, user_id, comment_id),
                )
            else:
                cursor.execute(
                    "DELETE FROM activity_comments WHERE id = ? OR parent_id = ?",
                    (comment_id, comment_id),
                )
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def get_activity_social(activity_id: str, current_uid: Optional[str] = None) -> Dict[str, Any]:
        eff_uid = LocalStore.resolve_user_id(current_uid) if current_uid else None
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            likers = LocalStore._query_activity_likers(cursor, activity_id)
            likes_count = len(likers)

            has_liked = False
            if current_uid:
                has_liked = any(
                    l["user_id"] in (current_uid, eff_uid) for l in likers
                )

            cursor.execute(
                """
                SELECT c.id, c.activity_id, c.user_id,
                       COALESCE(NULLIF(p.display_name, ''), c.author_name) AS author_name,
                       COALESCE(NULLIF(p.avatar_url, ''), c.author_avatar) AS author_avatar,
                       c.content, c.parent_id, c.reply_to_user_id, c.reply_to_name, c.created_at
                FROM activity_comments c
                LEFT JOIN profiles p ON c.user_id = p.id
                WHERE c.activity_id = ?
                ORDER BY c.created_at ASC, c.rowid ASC
                """,
                (activity_id,),
            )
            comments = []
            for r in cursor.fetchall():
                cd = dict(r)
                cd["created_at"] = to_beijing_iso(cd.get("created_at"))
                comments.append(cd)

            return {
                "likes_count": likes_count,
                "has_liked": has_liked,
                "likers": likers,
                "comments": comments,
            }

    @staticmethod
    def _needs_canova_critique_refresh(ai_journal: Optional[str]) -> bool:
        if not ai_journal or not ai_journal.strip():
            return True
        if "📋【课表核对】" in ai_journal or "跑量缩减·达成率" in ai_journal:
            return True
        if "📋【" in ai_journal:
            m_pct = re.search(r"达成率\s*(\d+)%", ai_journal)
            if m_pct and (int(m_pct.group(1)) < 75 or int(m_pct.group(1)) > 125):
                return True
            m_pace_diff = re.search(r"(?:比目标快|较目标放缓|偏快|偏慢)\s*(\d+)\s*秒", ai_journal)
            if m_pace_diff and int(m_pace_diff.group(1)) > 20:
                return True
            if re.search(r"分段\s*(?:[4-9]|\d{2,})\s*趟", ai_journal):
                return True
        if any(tag in ai_journal for tag in ("分段表现：", "🏆【赛事复盘", "📋【课表")):
            return False
        # Refresh legacy critiques or verbose v1 critiques so feed displays the streamlined format
        verbose_markers = (
            "每一步都在重塑更好的自己",
            "每一次踏上跑道都有真实数据印证你的成长",
            "💡 教练建议：",
            "入门进阶亮点",
            "专项成长亮点",
            "Aerobic",
            "Endurance",
            "Recovery Run",
            "Progression",
            "Activation Run",
        )
        if any(m in ai_journal for m in verbose_markers):
            return True
        if (
            "亮点】" not in ai_journal
            and "📋【" not in ai_journal
            and "🏆【赛事复盘" not in ai_journal
            and "【精英专项进阶】" not in ai_journal
        ):
            return True
        return False

    @staticmethod
    def _slim_feed_gps_track(raw_track: Any) -> Optional[Dict[str, Any]]:
        return _build_slim_route_preview(raw_track)

    @staticmethod
    def _batch_get_activity_social(
        activity_ids: List[str],
        current_uid: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Fetches likes and threaded comments for all activity_ids in 2 batch SQL queries instead of N+1."""
        result: Dict[str, Dict[str, Any]] = {
            aid: {"likes_count": 0, "has_liked": False, "likers": [], "comments": []}
            for aid in activity_ids
        }
        if not activity_ids:
            return result

        eff_uid = LocalStore.resolve_user_id(current_uid) if current_uid else None
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            for chunk_start in range(0, len(activity_ids), 300):
                chunk = activity_ids[chunk_start:chunk_start + 300]
                ph = ",".join(["?"] * len(chunk))

                cursor.execute(
                    f"""
                    SELECT l.activity_id,
                           l.user_id,
                           COALESCE(NULLIF(p.display_name, ''), '跑友') AS display_name,
                           COALESCE(NULLIF(p.avatar_url, ''), 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80') AS avatar_url,
                           l.created_at
                    FROM activity_likes l
                    LEFT JOIN profiles p ON l.user_id = p.id
                    WHERE l.activity_id IN ({ph})
                    ORDER BY l.created_at ASC, l.rowid ASC
                    """,
                    chunk,
                )
                for r in cursor.fetchall():
                    aid = r["activity_id"]
                    entry = result.get(aid)
                    if entry is not None:
                        liker = {
                            "user_id": r["user_id"],
                            "display_name": r["display_name"],
                            "avatar_url": r["avatar_url"],
                            "created_at": to_beijing_iso(r["created_at"]),
                        }
                        entry["likers"].append(liker)
                        entry["likes_count"] += 1
                        if current_uid and r["user_id"] in (current_uid, eff_uid):
                            entry["has_liked"] = True

                cursor.execute(
                    f"""
                    SELECT c.id, c.activity_id, c.user_id,
                           COALESCE(NULLIF(p.display_name, ''), c.author_name) AS author_name,
                           COALESCE(NULLIF(p.avatar_url, ''), c.author_avatar) AS author_avatar,
                           c.content, c.parent_id, c.reply_to_user_id, c.reply_to_name, c.created_at
                    FROM activity_comments c
                    LEFT JOIN profiles p ON c.user_id = p.id
                    WHERE c.activity_id IN ({ph})
                    ORDER BY c.created_at ASC, c.rowid ASC
                    """,
                    chunk,
                )
                for r in cursor.fetchall():
                    aid = r["activity_id"]
                    entry = result.get(aid)
                    if entry is not None:
                        cd = dict(r)
                        cd["created_at"] = to_beijing_iso(cd.get("created_at"))
                        entry["comments"].append(cd)

        return result

    @staticmethod
    def _get_club_active_member_uids(cursor: sqlite3.Cursor, club_id: str) -> List[str]:
        cursor.execute(
            """
            SELECT m.user_id
            FROM club_memberships m
            JOIN profiles p ON m.user_id = p.id
            WHERE m.club_id = ? AND m.status = 'active'
            """,
            (club_id,),
        )
        return [str(r[0]) for r in cursor.fetchall() if r[0]]

    @staticmethod
    def _enrich_club_feed_rows(
        rows: List[Dict[str, Any]],
        current_uid: Optional[str],
        club_id: str,
    ) -> List[Dict[str, Any]]:
        if not rows:
            return []
        act_ids = [str(r["id"]) for r in rows if r.get("id")]
        social_map = LocalStore._batch_get_activity_social(act_ids, current_uid)
        profile_cache: Dict[str, Dict[str, Any]] = {}
        critique_updates: List[Tuple[str, str]] = []
        enriched: List[Dict[str, Any]] = []

        for act in rows:
            act_id = str(act["id"])
            owner_uid = str(act.get("user_id") or "")
            owner_prof_id = act.pop("_owner_profile_id", None)
            h_gps = act.pop("_owner_hide_gps", None)
            h_bio = act.pop("_owner_hide_bio", None)
            if owner_uid and owner_prof_id and (h_gps is not None or h_bio is not None):
                prof_stub = {"id": str(owner_prof_id), "hide_gps_route": bool(h_gps), "hide_biometrics": bool(h_bio)}
                profile_cache[owner_uid] = prof_stub
                profile_cache[str(owner_prof_id)] = prof_stub

            ai_journal = act.get("ai_journal")
            if LocalStore._needs_canova_critique_refresh(ai_journal):
                try:
                    ai_journal = LocalStore.generate_canova_critique(act)
                    act["ai_journal"] = ai_journal
                    critique_updates.append((ai_journal, act_id))
                except Exception as ex:
                    logger.warning(f"Generate critique in _enrich_club_feed_rows failed: {ex}")

            raw_gps = act.get("gps_track_data")
            slim_gps = LocalStore._slim_feed_gps_track(raw_gps)
            act["has_gps_track"] = bool(
                slim_gps
                or raw_gps
                or act.get("map_image_url")
                or (
                    act_id.startswith(("garmin_", "coros_"))
                    and (LocalStore.is_running_activity(act.get("sport_type")) or act.get("sport_type") in ["Ride", "Hike", "Walk"])
                )
            )
            act["gps_track_data"] = slim_gps
            act.pop("laps_data", None)
            act.pop("splits_data", None)
            act.pop("segment_analysis_json", None)

            social = social_map.get(act_id) or {"likes_count": 0, "has_liked": False, "likers": [], "comments": []}
            act["likes_count"] = social["likes_count"]
            act["has_liked"] = social["has_liked"]
            act["likers"] = social["likers"]
            act["comments"] = social["comments"]
            LocalStore.apply_activity_privacy_filter(act, current_uid, club_id=club_id, profile_cache=profile_cache)
            enriched.append(act)

        if critique_updates:
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.executemany("UPDATE activities SET ai_journal = ? WHERE id = ?", critique_updates)
                    conn.commit()
            except Exception as u_ex:
                logger.warning(f"Batch critique update skipped: {u_ex}")

        return enriched

    @staticmethod
    def get_club_recent_activities(
        club_id: str,
        current_uid: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        before_time: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            uids = LocalStore._get_club_active_member_uids(cursor, club_id)
            if not uids:
                return [], 0
            placeholders = ["?"] * len(uids)

            # Get total count of club activities for pagination
            cursor.execute(f"SELECT COUNT(*) FROM activities WHERE user_id IN ({','.join(placeholders)}) AND {RUNNING_SQL_FILTER}", uids)
            total_row = cursor.fetchone()
            total = total_row[0] if total_row else 0

            params = list(uids)
            time_filter = ""
            if before_time:
                time_filter = "AND a.start_time < ?"
                params.append(before_time)

            params.extend([max(1, limit), max(0, offset)])
            query = f"""
                SELECT a.id, a.user_id, a.name, a.sport_type, a.start_time, a.distance_meters,
                       a.moving_time_seconds, a.elapsed_time_seconds, a.elevation_gain_meters,
                       a.average_heartrate, a.max_heartrate, a.average_cadence, a.avg_pace_str,
                       a.calories, a.aerobic_training_effect, a.anaerobic_training_effect, a.trimp,
                       a.ai_journal, COALESCE(a.route_preview_json, a.gps_track_data) AS gps_track_data, a.map_image_url, a.exclude_mode,
                       COALESCE(NULLIF(p.display_name, ''), a.user_id) AS display_name, p.avatar_url,
                       p.id AS _owner_profile_id,
                       COALESCE(p.hide_gps_route, 0) AS _owner_hide_gps,
                       COALESCE(p.hide_biometrics, 0) AS _owner_hide_bio
                FROM activities a
                LEFT JOIN profiles p ON a.user_id = p.id
                WHERE a.user_id IN ({','.join(placeholders)})
                  AND {RUNNING_SQL_FILTER.replace('sport_type', 'a.sport_type')}
                {time_filter}
                ORDER BY a.start_time DESC
                LIMIT ? OFFSET ?
            """
            cursor.execute(query, params)
            rows = [dict(r) for r in cursor.fetchall()]

        enriched = LocalStore._enrich_club_feed_rows(rows, current_uid, club_id)
        return enriched, total

    @staticmethod
    def get_club_month_activities(
        club_id: str,
        current_uid: Optional[str] = None,
        year: Optional[int] = None,
        month: Optional[int] = None
    ) -> Tuple[List[Dict[str, Any]], int, int]:
        """
        Returns all activities of the specified (or current) month for the club.
        Returns (enriched_activities, month_total, total_all_time).
        """
        today = get_beijing_today()
        target_year = year or today.year
        target_month = month or today.month

        month_start = f"{target_year:04d}-{target_month:02d}-01"
        if target_month == 12:
            next_month_start = f"{target_year + 1:04d}-01-01"
        else:
            next_month_start = f"{target_year:04d}-{target_month + 1:02d}-01"

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            uids = LocalStore._get_club_active_member_uids(cursor, club_id)
            if not uids:
                return [], 0, 0
            placeholders = ["?"] * len(uids)

            # Total count all time
            cursor.execute(f"SELECT COUNT(*) FROM activities WHERE user_id IN ({','.join(placeholders)}) AND {RUNNING_SQL_FILTER}", uids)
            total_row = cursor.fetchone()
            total_all_time = total_row[0] if total_row else 0

            # Total count for the month
            cursor.execute(f"""
                SELECT COUNT(*) FROM activities 
                WHERE user_id IN ({','.join(placeholders)})
                  AND start_time >= ? AND start_time < ?
                  AND {RUNNING_SQL_FILTER}
            """, uids + [month_start, next_month_start])
            month_row = cursor.fetchone()
            month_total = month_row[0] if month_row else 0

            # Fetch lightweight columns for the month (ordered by start_time DESC)
            query = f"""
                SELECT a.id, a.user_id, a.name, a.sport_type, a.start_time, a.distance_meters,
                       a.moving_time_seconds, a.elapsed_time_seconds, a.elevation_gain_meters,
                       a.average_heartrate, a.max_heartrate, a.average_cadence, a.avg_pace_str,
                       a.calories, a.aerobic_training_effect, a.anaerobic_training_effect, a.trimp,
                       a.ai_journal, COALESCE(a.route_preview_json, a.gps_track_data) AS gps_track_data, a.map_image_url, a.exclude_mode,
                       COALESCE(NULLIF(p.display_name, ''), a.user_id) AS display_name, p.avatar_url,
                       p.id AS _owner_profile_id,
                       COALESCE(p.hide_gps_route, 0) AS _owner_hide_gps,
                       COALESCE(p.hide_biometrics, 0) AS _owner_hide_bio
                FROM activities a
                LEFT JOIN profiles p ON a.user_id = p.id
                WHERE a.user_id IN ({','.join(placeholders)})
                  AND a.start_time >= ? AND a.start_time < ?
                  AND {RUNNING_SQL_FILTER.replace('sport_type', 'a.sport_type')}
                ORDER BY a.start_time DESC
            """
            cursor.execute(query, uids + [month_start, next_month_start])
            rows = [dict(r) for r in cursor.fetchall()]

        enriched = LocalStore._enrich_club_feed_rows(rows, current_uid, club_id)
        return enriched, month_total, total_all_time

    @staticmethod
    def get_user_club_feed_summary(user_id: str) -> Dict[str, Any]:
        """
        Compiles a fast summary of the user's primary club check-in feed for the MiniApp Home shortcut card:
        - today_checkin_count, week_checkin_count, month_checkin_count
        - coach_critique_count (AI Canova + Coach comments)
        - interaction_count (likes + comments)
        - latest_checkins (up to 3 recent teammate check-ins with avatars)
        """
        eff_uid = LocalStore.resolve_user_id(user_id)
        clubs = LocalStore.get_user_clubs(eff_uid)
        target_club = clubs[0] if clubs else None
        club_id = target_club["id"] if target_club else "club_rgm_flagship"
        club_name = target_club["name"] if target_club else "RGM 先锋跑团"

        today = get_beijing_today()
        today_str = today.isoformat()
        week_start_str = (today - timedelta(days=today.weekday())).isoformat()
        month_start_str = f"{today.year:04d}-{today.month:02d}-01"

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            uids = LocalStore._get_club_active_member_uids(cursor, club_id)
            if not uids:
                return {
                    "club_id": club_id,
                    "club_name": club_name,
                    "has_club": bool(target_club),
                    "today_checkin_count": 0,
                    "week_checkin_count": 0,
                    "month_checkin_count": 0,
                    "coach_critique_count": 0,
                    "interaction_count": 0,
                    "latest_checkins": [],
                }
            placeholders = ",".join(["?"] * len(uids))

            cursor.execute(
                f"""
                SELECT COUNT(*) FROM activities
                WHERE user_id IN ({placeholders})
                  AND substr(start_time, 1, 10) = ?
                  AND {RUNNING_SQL_FILTER}
                """,
                uids + [today_str],
            )
            today_count = (cursor.fetchone() or [0])[0]

            cursor.execute(
                f"""
                SELECT COUNT(*) FROM activities
                WHERE user_id IN ({placeholders})
                  AND substr(start_time, 1, 10) >= ?
                  AND {RUNNING_SQL_FILTER}
                """,
                uids + [week_start_str],
            )
            week_count = (cursor.fetchone() or [0])[0]

            cursor.execute(
                f"""
                SELECT COUNT(*),
                       SUM(CASE WHEN ai_journal IS NOT NULL AND TRIM(ai_journal) != '' THEN 1 ELSE 0 END)
                FROM activities
                WHERE user_id IN ({placeholders})
                  AND substr(start_time, 1, 10) >= ?
                  AND {RUNNING_SQL_FILTER}
                """,
                uids + [month_start_str],
            )
            m_row = cursor.fetchone()
            month_count = (m_row[0] or 0) if m_row else 0
            coach_critique_count = (m_row[1] or month_count) if m_row else 0

            cursor.execute(
                f"""
                SELECT a.id, a.user_id, a.name, a.start_time, a.distance_meters, a.avg_pace_str,
                       COALESCE(NULLIF(p.display_name, ''), '跑友') AS display_name,
                       COALESCE(NULLIF(p.avatar_url, ''), 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80') AS avatar_url
                FROM activities a
                LEFT JOIN profiles p ON a.user_id = p.id
                WHERE a.user_id IN ({placeholders})
                  AND {RUNNING_SQL_FILTER.replace('sport_type', 'a.sport_type')}
                ORDER BY a.start_time DESC
                LIMIT 3
                """,
                uids,
            )
            latest_rows = [dict(r) for r in cursor.fetchall()]

            cursor.execute(
                f"""
                SELECT
                  (SELECT COUNT(*) FROM activity_likes l JOIN activities a ON l.activity_id = a.id WHERE a.user_id IN ({placeholders}) AND substr(a.start_time, 1, 10) >= ?)
                  +
                  (SELECT COUNT(*) FROM activity_comments c JOIN activities a ON c.activity_id = a.id WHERE a.user_id IN ({placeholders}) AND substr(a.start_time, 1, 10) >= ?)
                """,
                uids + [month_start_str] + uids + [month_start_str],
            )
            inter_row = cursor.fetchone()
            interaction_count = (inter_row[0] or 0) if inter_row else 0

        latest_checkins = []
        for r in latest_rows:
            latest_checkins.append(
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "display_name": r["display_name"],
                    "avatar_url": r["avatar_url"],
                    "distance_km": round(float(r.get("distance_meters") or 0) / 1000.0, 1),
                    "avg_pace_str": r.get("avg_pace_str") or "",
                    "start_time": r.get("start_time") or "",
                }
            )

        return {
            "club_id": club_id,
            "club_name": club_name,
            "has_club": bool(target_club),
            "today_checkin_count": today_count,
            "week_checkin_count": week_count,
            "month_checkin_count": month_count,
            "coach_critique_count": max(coach_critique_count, month_count),
            "interaction_count": interaction_count,
            "latest_checkins": latest_checkins,
        }

    @staticmethod
    def get_all_garmin_connected_users() -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, email, display_name, garmin_email, garmin_domain, garmin_last_sync_at 
                FROM profiles 
                WHERE garmin_connected = 1 AND garmin_encrypted_password IS NOT NULL
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_all_coros_connected_users() -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, email, display_name, coros_account, coros_domain, coros_last_sync_at 
                FROM profiles 
                WHERE coros_connected = 1 AND coros_encrypted_password IS NOT NULL
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_all_syncable_users() -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, email, display_name, 
                       garmin_connected, garmin_email, garmin_domain, garmin_last_sync_at,
                       coros_connected, coros_account, coros_domain, coros_last_sync_at
                FROM profiles 
                WHERE (garmin_connected = 1 AND garmin_encrypted_password IS NOT NULL)
                   OR (coros_connected = 1 AND coros_encrypted_password IS NOT NULL)
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    # ── Scientific Training Plans (Race Prep & Fitness Maintenance) ──

    @staticmethod
    def classify_plan_source(plan: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """
        Classifies a training plan into a clear human-readable source category so coaches and runners
        can immediately distinguish AI Canova plans vs Coach Template plans vs Coach Imported Weekly Schedules.
        """
        if not plan or not isinstance(plan, dict):
            return {"source_type": "unknown", "source_label": "未知方案"}
        sched = plan.get("schedule_data") or {}
        if isinstance(sched, str):
            try:
                sched = json.loads(sched)
            except Exception:
                sched = {}
        tpl_id = str(sched.get("template_id") or "")
        title_str = str(plan.get("title") or "")
        ov_str = str(plan.get("overview_summary") or "")
        if tpl_id.startswith("imported_") or "助教/主教练已按组别统一导入派发" in ov_str or "周训练计划" in title_str:
            return {"source_type": "imported_week", "source_label": "📸 教练识图周课表"}
        if tpl_id or sched.get("template_group_code"):
            return {"source_type": "coach_template", "source_label": f"📚 教练模版 ({sched.get('template_group_code') or '分组'})"}
        if plan.get("review_status") == "published":
            return {"source_type": "coach_published", "source_label": "🧢 教练审定周期计划"}
        return {"source_type": "ai_canova", "source_label": "🤖 AI 科学周期计划"}

    @staticmethod
    def record_plan_backup(
        user_id: str,
        action_type: str,
        action_label: str,
        operator_uid: Optional[str] = None,
        club_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        previous_active_plan: Optional[Dict[str, Any]] = None,
        created_plan_id: Optional[str] = None,
        created_status: str = "active",
    ) -> str:
        """
        Saves a point-in-time snapshot of the user's previous active training plan before any
        overwrite, template assignment, schedule import, or AI regeneration so it can be rolled back in 1 click.
        """
        canonical_uid = LocalStore.resolve_user_id(user_id)
        if previous_active_plan is None:
            previous_active_plan = LocalStore.get_user_active_training_plan(canonical_uid, reconcile=False)
        now_iso = get_beijing_iso()
        backup_id = f"tpbak_{int(datetime.utcnow().timestamp()*1000)}_{uuid.uuid4().hex[:6]}"
        prev_id = previous_active_plan.get("id") if isinstance(previous_active_plan, dict) else None
        prev_json = json.dumps(previous_active_plan, ensure_ascii=False) if isinstance(previous_active_plan, dict) else None
        eff_club = club_id or (previous_active_plan.get("club_id") if isinstance(previous_active_plan, dict) else None)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO training_plan_backups (
                    id, batch_id, user_id, club_id, action_type, action_label,
                    previous_active_plan_id, previous_active_plan_json,
                    created_plan_id, created_status, operator_uid, created_at, restored_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    backup_id,
                    batch_id,
                    canonical_uid,
                    eff_club,
                    action_type,
                    action_label,
                    prev_id,
                    prev_json,
                    created_plan_id,
                    created_status,
                    operator_uid or canonical_uid,
                    now_iso,
                ),
            )
            conn.commit()
        return backup_id

    @staticmethod
    def upsert_training_plan(plan_data: Dict[str, Any], skip_backup: bool = False) -> Dict[str, Any]:
        now_iso = datetime.utcnow().isoformat() + "Z"
        plan_id = plan_data.get("id") or f"plan_{int(datetime.utcnow().timestamp()*1000)}"
        plan_status = plan_data.get("status", "active")
        review_status = plan_data.get("review_status") or ("draft" if plan_status == "draft" else "self_created")
        target_uid = LocalStore.resolve_user_id(plan_data.get("user_id") or "")

        if plan_status == "active" and not skip_backup and target_uid:
            prev_active = LocalStore.get_user_active_training_plan(target_uid, reconcile=False)
            if prev_active and prev_active.get("id") != plan_id:
                try:
                    LocalStore.record_plan_backup(
                        user_id=target_uid,
                        action_type="upsert_active_plan",
                        action_label=f"切换/生成新计划：{plan_data.get('title') or '训练计划'}",
                        operator_uid=plan_data.get("last_modified_by") or plan_data.get("creator_id") or target_uid,
                        club_id=plan_data.get("club_id"),
                        previous_active_plan=prev_active,
                        created_plan_id=plan_id,
                        created_status="active",
                    )
                except Exception as be:
                    logger.warning(f"Failed to record automatic plan backup on upsert: {be}")

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # If new plan is active, archive other active plans for this user
            if plan_status == "active":
                cursor.execute("""
                    UPDATE training_plans 
                    SET status = 'archived', updated_at = ? 
                    WHERE (user_id = ? OR user_id = ?) AND status = 'active' AND id != ?
                """, (now_iso, target_uid, plan_data["user_id"], plan_id))
            elif plan_status == "draft":
                # Keep only the latest draft per user
                cursor.execute("""
                    UPDATE training_plans 
                    SET status = 'archived', updated_at = ? 
                    WHERE (user_id = ? OR user_id = ?) AND status = 'draft' AND id != ?
                """, (now_iso, target_uid, plan_data["user_id"], plan_id))

            sched = plan_data.get("schedule_data")
            if isinstance(sched, (dict, list)):
                sched_str = json.dumps(sched, ensure_ascii=False)
            else:
                sched_str = sched or "{}"

            created_at = plan_data.get("created_at") or now_iso
            updated_at = now_iso

            cursor.execute("""
                INSERT OR REPLACE INTO training_plans (
                    id, user_id, club_id, title, goal_type, maintenance_focus,
                    target_race_id, target_race_name, target_date, start_date, end_date,
                    weeks_count, days_per_week, preferred_long_run_day, status,
                    review_status, reviewed_by, reviewed_by_name, reviewed_at, coach_review_note,
                    overview_summary, schedule_data, creator_id, last_modified_by,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_id,
                plan_data.get("user_id"),
                plan_data.get("club_id"),
                plan_data.get("title", "个性化周期训练计划"),
                plan_data.get("goal_type", "race_prep"),
                plan_data.get("maintenance_focus"),
                plan_data.get("target_race_id"),
                plan_data.get("target_race_name"),
                plan_data.get("target_date"),
                plan_data.get("start_date"),
                plan_data.get("end_date"),
                plan_data.get("weeks_count", 8),
                plan_data.get("days_per_week", 4),
                plan_data.get("preferred_long_run_day", "Sunday"),
                plan_status,
                review_status,
                plan_data.get("reviewed_by"),
                plan_data.get("reviewed_by_name"),
                plan_data.get("reviewed_at"),
                plan_data.get("coach_review_note"),
                plan_data.get("overview_summary", ""),
                sched_str,
                plan_data.get("creator_id", plan_data.get("user_id")),
                plan_data.get("last_modified_by", plan_data.get("user_id")),
                created_at,
                updated_at
            ))
            conn.commit()

        return LocalStore.get_training_plan(plan_id) or plan_data

    save_training_plan = upsert_training_plan

    @staticmethod
    def get_db_path() -> str:
        return DB_PATH

    @staticmethod
    def compute_physiological_recovery_pct(
        hm: Dict[str, Any],
        baseline_rhr: Optional[float] = None,
        baseline_hrv: Optional[float] = None,
    ) -> Optional[int]:
        """
        Computes a composite daily physiological Recovery % (10–99%), modeled on
        Whoop Recovery & Garmin Training Readiness:
        1. HRV Ratio vs 7-day baseline (weight 0.40):
           S_hrv = clamp(72 + (hrv / baseline_hrv - 1.0) * 160, 15, 98)
        2. Sleep Quality Score (weight 0.30):
           sleep_score (0–100) or derived from sleep_duration_hours
        3. Body Battery / Stamina Recharge (weight 0.20):
           body_battery_max (ignored if < 30 when HRV or Sleep is present, to avoid
           early-morning pre-sync partial battery values like 18%; capped at 96)
        4. Resting Heart Rate Deviation vs baseline (weight 0.10):
           S_rhr = clamp(75 - (rhr - baseline_rhr) * 4.5, 20, 96)
        """
        if not hm or not isinstance(hm, dict):
            return None

        # Require actual overnight wear (overnight HRV recorded) and a valid 7-day HRV baseline.
        # Never compute a physiological recovery % from daytime-only metrics or when multi-day non-wear
        # has broken the 7-day HRV baseline (e.g. hrv_status == 'NONE').
        has_overnight_hrv = bool(
            hm.get("hrv_last_night_avg") is not None and float(hm.get("hrv_last_night_avg") or 0) > 0
        )
        if not has_overnight_hrv:
            return None

        raw_hrv_status = str(hm.get("hrv_status") or "").strip().upper()
        if raw_hrv_status in ("NONE", "UNAVAILABLE", "POOR_QUALITY", "MISSING"):
            return None

        components = []

        # 1. HRV Component (weight 0.40)
        hrv_last = hm.get("hrv_last_night_avg")
        hrv_base = hm.get("hrv_weekly_avg") or baseline_hrv
        if hrv_last is not None and float(hrv_last or 0) > 0:
            hrv_val = float(hrv_last)
            if hrv_base is not None and float(hrv_base or 0) > 0:
                ratio = hrv_val / float(hrv_base)
                s_hrv = max(15.0, min(98.0, 72.0 + (ratio - 1.0) * 160.0))
            else:
                return None
            components.append((s_hrv, 0.40))

        # 2. Sleep Component (weight 0.30)
        sleep_sc = hm.get("sleep_score")
        sleep_hrs = hm.get("sleep_duration_hours")
        if sleep_hrs is None and hm.get("sleep_duration_seconds"):
            try:
                sleep_hrs = float(hm["sleep_duration_seconds"]) / 3600.0
            except Exception:
                sleep_hrs = None
        if sleep_sc is not None and float(sleep_sc or 0) > 0:
            s_sleep = max(20.0, min(98.0, float(sleep_sc)))
            components.append((s_sleep, 0.30))
        elif sleep_hrs is not None and float(sleep_hrs or 0) > 0:
            s_sleep = max(25.0, min(95.0, (float(sleep_hrs) / 8.0) * 85.0))
            components.append((s_sleep, 0.25))

        # 3. Body Battery / Stamina Component (weight 0.20)
        bb_max = hm.get("body_battery_max")
        if bb_max is not None and float(bb_max or 0) > 0:
            bb_val = float(bb_max)
            if bb_val >= 30.0 or not components:
                s_bb = max(15.0, min(96.0, bb_val))
                components.append((s_bb, 0.20))

        # 4. Resting Heart Rate Component (weight 0.10)
        rhr = hm.get("resting_heart_rate")
        if rhr is not None and float(rhr or 0) > 0:
            rhr_val = float(rhr)
            if baseline_rhr is not None and float(baseline_rhr or 0) > 0:
                delta_rhr = rhr_val - float(baseline_rhr)
                s_rhr = max(20.0, min(96.0, 75.0 - delta_rhr * 4.5))
                components.append((s_rhr, 0.10))
            elif not components:
                s_rhr = max(30.0, min(92.0, 85.0 - (rhr_val - 50.0) * 1.5))
                components.append((s_rhr, 0.10))

        if not components:
            return None

        total_weight = sum(w for _, w in components)
        if total_weight <= 0:
            return None

        weighted_score = sum(s * w for s, w in components) / total_weight
        return int(max(10, min(99, round(weighted_score))))

    @staticmethod
    def reconcile_training_plan_activities(
        plan: Dict[str, Any],
        user_id: Optional[str] = None,
        preloaded_activities: Optional[List[Dict[str, Any]]] = None,
        preloaded_health_rows: Optional[List[Dict[str, Any]]] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """
        Automatically aligns runner's synced activities with daily workouts in the training plan:
        1. If an activity exists on that day: auto marks completed: True, auto_matched: True, actual_distance_km, actual_pace, actual_heartrate.
        2. If workout_type == 'rest' and date < today: marks completed: True, auto_rest: True.
        3. If workout_type != 'rest' and date < today and not completed: marks is_missed: True (Red 'X' indicator).
        4. If date >= today: normal pending state (is_missed: False).
        Preserves manual overrides if user explicitly checked or unchecked.
        """
        if not plan or not plan.get("schedule_data"):
            return plan

        sched = plan.get("schedule_data")
        if isinstance(sched, str):
            try:
                sched = json.loads(sched)
                plan["schedule_data"] = sched
            except Exception:
                return plan

        weeks = sched.get("weeks") or []
        if not weeks:
            return plan

        uid = user_id or plan.get("user_id")
        if not uid:
            return plan
        if preloaded_activities is not None and preloaded_health_rows is not None:
            canonical_uid = str(uid)
        else:
            canonical_uid = LocalStore.resolve_user_id(uid)

        start_date_str = str(plan.get("start_date") or "")
        now_beijing = datetime.utcnow() + timedelta(hours=8)
        today_str = now_beijing.strftime("%Y-%m-%d")

        health_by_day: Dict[str, Dict[str, Any]] = {}
        if preloaded_activities is not None and preloaded_health_rows is not None:
            act_rows = [
                a for a in preloaded_activities
                if a.get("exclude_mode") != "excluded"
                and LocalStore.is_running_activity(a.get("sport_type"))
                and (not start_date_str or str(a.get("start_time") or "") >= start_date_str)
            ]
            act_rows.sort(key=lambda a: str(a.get("start_time") or ""))
            for hm_row in preloaded_health_rows:
                hm_d = LocalStore.sanitize_daily_health_row(dict(hm_row)) or {}
                dt_key = str(hm_d.get("date") or "")[:10]
                if dt_key:
                    health_by_day[dt_key] = hm_d
        else:
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    if start_date_str:
                        cursor.execute(f"""
                            SELECT id, name, sport_type, start_time, distance_meters, 
                                   moving_time_seconds, avg_pace_str, average_heartrate, trimp
                            FROM activities
                            WHERE (user_id = ? OR user_id = ?) AND start_time >= ?
                              AND {RUNNING_SQL_FILTER}
                            ORDER BY start_time ASC
                        """, (canonical_uid, uid, start_date_str))
                    else:
                        cursor.execute(f"""
                            SELECT id, name, sport_type, start_time, distance_meters, 
                                   moving_time_seconds, avg_pace_str, average_heartrate, trimp
                            FROM activities
                            WHERE (user_id = ? OR user_id = ?)
                              AND {RUNNING_SQL_FILTER}
                            ORDER BY start_time ASC
                        """, (canonical_uid, uid))
                    act_rows = [dict(r) for r in cursor.fetchall()]

                    try:
                        cursor.execute("""
                            SELECT date, resting_heart_rate, sleep_score, sleep_duration_hours,
                                   sleep_duration_seconds, body_battery_max,
                                   hrv_status, hrv_weekly_avg, hrv_last_night_avg
                            FROM daily_health
                            WHERE user_id = ? OR user_id = ?
                            ORDER BY date ASC
                        """, (canonical_uid, uid))
                        for hm_row in cursor.fetchall():
                            hm_d = LocalStore.sanitize_daily_health_row(dict(hm_row)) or {}
                            dt_key = str(hm_d.get("date") or "")[:10]
                            if dt_key:
                                health_by_day[dt_key] = hm_d
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Error querying activities for plan reconciliation: {e}")
                act_rows = []

        cutoff_14d_str = (now_beijing.date() - timedelta(days=13)).isoformat()
        cutoff_7d_str = (now_beijing.date() - timedelta(days=6)).isoformat()
        recent_14d_valid = [
            v for dt_k, v in health_by_day.items()
            if dt_k >= cutoff_14d_str and v.get("overnight_wear_valid")
        ]
        recent_7d_valid = [
            v for dt_k, v in health_by_day.items()
            if dt_k >= cutoff_7d_str and v.get("overnight_wear_valid")
        ]
        has_reliable_baseline = len(recent_7d_valid) >= 5 or len(recent_14d_valid) >= 10

        rhr_samples = [
            float(v["resting_heart_rate"])
            for v in recent_14d_valid
            if v.get("resting_heart_rate") and float(v["resting_heart_rate"]) > 0
        ]
        baseline_rhr = (sum(rhr_samples) / len(rhr_samples)) if (has_reliable_baseline and len(rhr_samples) >= 5) else None

        hrv_samples = [
            float(v.get("hrv_weekly_avg") or v.get("hrv_last_night_avg"))
            for v in recent_14d_valid
            if (v.get("hrv_weekly_avg") or v.get("hrv_last_night_avg"))
            and float(v.get("hrv_weekly_avg") or v.get("hrv_last_night_avg") or 0) > 0
        ]
        baseline_hrv = (sum(hrv_samples) / len(hrv_samples)) if (has_reliable_baseline and len(hrv_samples) >= 5) else None

        acts_by_day: Dict[str, List[Dict[str, Any]]] = {}
        for a in act_rows:
            st = str(a.get("start_time") or "")[:10]
            if st:
                if st not in acts_by_day:
                    acts_by_day[st] = []
                acts_by_day[st].append(a)

        changed = False
        for w in weeks:
            days_in_wk = w.get("days") or []
            for d_idx, day in enumerate(days_in_wk):
                if "day_index" not in day:
                    day["day_index"] = d_idx
                d_date = str(day.get("date") or "")
                w_type = day.get("workout_type") or "easy_run"
                is_rest = (w_type in ("rest", "travel"))
                dist_km = float(day.get("distance_km") or 0.0)

                # Reconcile morning / watch health metrics (HRV, RHR, Composite Recovery%)
                hm = health_by_day.get(d_date)
                is_manual_bio = bool(day.get("manual_biometrics_override") or day.get("respiratory_rate") is not None)
                if hm and hm.get("overnight_wear_valid"):
                    hrv_v = hm.get("hrv_last_night_avg")
                    if hrv_v and (day.get("hrv") is None or not is_manual_bio):
                        new_hrv = int(round(float(hrv_v)))
                        if day.get("hrv") != new_hrv:
                            day["hrv"] = new_hrv
                            changed = True
                    if hm.get("resting_heart_rate") and (day.get("resting_hr") is None or not is_manual_bio):
                        new_rhr = int(hm["resting_heart_rate"])
                        if day.get("resting_hr") != new_rhr:
                            day["resting_hr"] = new_rhr
                            changed = True
                    if day.get("recovery_pct") is None or not is_manual_bio:
                        comp_rec = (
                            LocalStore.compute_physiological_recovery_pct(
                                hm, baseline_rhr=baseline_rhr, baseline_hrv=baseline_hrv
                            )
                            if has_reliable_baseline
                            else None
                        )
                        if day.get("recovery_pct") != comp_rec:
                            day["recovery_pct"] = comp_rec
                            changed = True
                elif not is_manual_bio:
                    for stale_bio_k in ("hrv", "resting_hr", "recovery_pct"):
                        if day.get(stale_bio_k) is not None:
                            day[stale_bio_k] = None
                            changed = True

                matching_acts = acts_by_day.get(d_date, [])
                if matching_acts:
                    total_m = sum(float(a.get("distance_meters") or 0.0) for a in matching_acts)
                    actual_km = round(total_m / 1000.0, 1)
                    primary_act = matching_acts[-1]
                    pace = primary_act.get("avg_pace_str") or "—"
                    hr = primary_act.get("average_heartrate")
                    day_trimp = sum(float(a.get("trimp") or 45.0) for a in matching_acts)

                    if not day.get("completed"):
                        day["completed"] = True
                        changed = True
                    if day.get("is_missed"):
                        day["is_missed"] = False
                        changed = True
                    if not day.get("auto_matched"):
                        day["auto_matched"] = True
                        changed = True
                    if day.get("actual_distance_km") != actual_km:
                        day["actual_distance_km"] = actual_km
                        changed = True
                    if day.get("actual_pace") != pace:
                        day["actual_pace"] = pace
                        changed = True
                    if hr and day.get("actual_heartrate") != hr:
                        day["actual_heartrate"] = hr
                        changed = True
                    if day.get("strain_score") is None:
                        day["strain_score"] = round(min(21.0, day_trimp / 8.5 + 3.0), 1)
                        changed = True
                    if not day.get("manual_execution_text"):
                        pace_clean = str(pace).replace(" /km", "").replace("/km", "").strip()
                        hr_suffix = f", hr{int(round(float(hr)))}" if hr else ""
                        if len(matching_acts) == 1:
                            auto_exec_str = f"{actual_km}km*{pace_clean}{hr_suffix}"
                        else:
                            seg_strs = [
                                f"{round(float(a.get('distance_meters') or 0)/1000.0, 1)}km*{str(a.get('avg_pace_str') or '').replace('/km','').strip()}"
                                for a in matching_acts
                            ]
                            auto_exec_str = "+".join(seg_strs) + hr_suffix
                        if day.get("actual_execution_text") != auto_exec_str:
                            day["actual_execution_text"] = auto_exec_str
                            changed = True
                else:
                    if day.get("manual_completed"):
                        if not day.get("completed"):
                            day["completed"] = True
                            changed = True
                        if day.get("is_missed"):
                            day["is_missed"] = False
                            changed = True
                    elif day.get("manual_override") or day.get("is_swapped"):
                        pass
                    else:
                        if d_date and d_date < today_str:
                            if is_rest:
                                if not day.get("completed"):
                                    day["completed"] = True
                                    day["auto_rest"] = True
                                    changed = True
                                if day.get("is_missed"):
                                    day["is_missed"] = False
                                    changed = True
                            else:
                                if dist_km > 0:
                                    if day.get("completed"):
                                        day["completed"] = False
                                        changed = True
                                    if not day.get("is_missed"):
                                        day["is_missed"] = True
                                        changed = True
                        else:
                            if day.get("is_missed"):
                                day["is_missed"] = False
                                changed = True

            # Enrich week_summary for W19 table view
            existing_ws = w.get("week_summary") if isinstance(w.get("week_summary"), dict) else {}
            planned_wk_km = round(sum(float(d.get("distance_km") or 0.0) for d in days_in_wk if d.get("workout_type") not in ("rest", "travel")), 1)
            actual_wk_km = round(sum(
                float(d.get("actual_distance_km") if d.get("actual_distance_km") is not None else (d.get("distance_km") if d.get("completed") and d.get("workout_type") not in ("rest", "travel") else 0.0) or 0.0)
                for d in days_in_wk
            ), 1)
            comp_pct = int(round(actual_wk_km * 100.0 / planned_wk_km)) if planned_wk_km > 0 else (100 if actual_wk_km > 0 else 0)
            auto_str_cnt = sum(
                1 for d in days_in_wk
                if d.get("strength_completed") or d.get("workout_type") == "cross_training"
                or any(kw in (str(d.get("actual_execution_text") or "") + str(d.get("title") or "") + str(d.get("description") or "")) for kw in ("身训", "力量", "核心", "单腿"))
            )
            str_override = existing_ws.get("strength_count_override") if existing_ws.get("strength_count_override") is not None else w.get("strength_count")
            eff_str_cnt = int(str_override) if str_override is not None else auto_str_cnt

            rpe_vals = [float(d["rpe"]) for d in days_in_wk if d.get("rpe") is not None and str(d.get("rpe")).strip() != ""]
            rec_vals = [int(d["recovery_pct"]) for d in days_in_wk if d.get("recovery_pct") is not None and str(d.get("recovery_pct")).strip() != ""]

            inj_note = str(existing_ws.get("injury_note") if existing_ws.get("injury_note") is not None else (w.get("injury_note") or "")).strip()
            ath_sum = str(existing_ws.get("athlete_weekly_summary") if existing_ws.get("athlete_weekly_summary") is not None else (w.get("athlete_weekly_summary") or "")).strip()
            trv_note = str(existing_ws.get("travel_or_leave_note") if existing_ws.get("travel_or_leave_note") is not None else (w.get("travel_or_leave_note") or "")).strip()
            c_diag = str(existing_ws.get("coach_weekly_diagnosis") if existing_ws.get("coach_weekly_diagnosis") is not None else (w.get("coach_weekly_diagnosis") or "")).strip()
            has_inj_alert = bool(inj_note and inj_note not in ("无", "正常", "无伤痛", "没有", "none"))

            auto_sum_line = f"周跑量：{planned_wk_km:g}公里。执行：{actual_wk_km:g}公里，完成度{comp_pct}%；力量：{eff_str_cnt}次。"

            w["week_summary"] = {
                **existing_ws,
                "planned_mileage_km": planned_wk_km,
                "actual_mileage_km": actual_wk_km,
                "completion_pct": comp_pct,
                "strength_count": eff_str_cnt,
                "avg_rpe": round(sum(rpe_vals) / len(rpe_vals), 1) if rpe_vals else None,
                "max_rpe": int(max(rpe_vals)) if rpe_vals else None,
                "avg_recovery_pct": int(round(sum(rec_vals) / len(rec_vals))) if rec_vals else None,
                "injury_note": inj_note,
                "has_injury_alert": has_inj_alert,
                "athlete_weekly_summary": ath_sum,
                "travel_or_leave_note": trv_note,
                "coach_weekly_diagnosis": c_diag,
                "summary_header_line": existing_ws.get("custom_summary_line") or auto_sum_line,
                "week_review_status": existing_ws.get("week_review_status") or w.get("week_review_status") or ("published" if plan.get("review_status") == "published" else "draft"),
            }

        plan_id = plan.get("id")
        if changed and plan_id and persist:
            try:
                now_iso = datetime.utcnow().isoformat() + "Z"
                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE training_plans 
                        SET schedule_data = ?, updated_at = ?
                        WHERE id = ?
                    """, (json.dumps(sched, ensure_ascii=False), now_iso, plan_id))
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to auto-save reconciled plan {plan_id}: {e}")

        return plan

    @staticmethod
    def _enrich_plan_with_current_week(
        plan: Optional[Dict[str, Any]],
        profile: Optional[Dict[str, Any]] = None,
        latest_health: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not plan:
            return None
        sched = plan.get("schedule_data") or {}
        if isinstance(sched, str):
            try:
                sched = json.loads(sched)
                plan["schedule_data"] = sched
            except Exception:
                sched = {}

        # Always align plan VO2Max with the runner's direct watch/profile VO2Max when available
        uid = plan.get("user_id")
        if uid and uid != "__template_preview__" and isinstance(sched, dict):
            try:
                prof = profile if profile is not None else (LocalStore.get_profile(uid) or {})
                hlth = latest_health if latest_health is not None else (LocalStore.get_latest_health(uid) or {})
                watch_vo2 = hlth.get("vo2_max") or prof.get("vo2max")
                if watch_vo2 is not None and float(watch_vo2) > 0:
                    vo2_val = round(float(watch_vo2), 1)
                    has_watch = bool(
                        prof.get("garmin_connected")
                        or prof.get("coros_connected")
                        or prof.get("apple_health_connected")
                        or prof.get("huawei_health_connected")
                        or hlth.get("vo2_max")
                    )
                    snap = sched.get("current_fitness_snapshot")
                    if isinstance(snap, dict):
                        snap["vo2max"] = vo2_val
                        snap["vo2max_source"] = "watch" if has_watch else "profile"
                    if plan.get("overview_summary") and "VO2Max" in str(plan["overview_summary"]):
                        plan["overview_summary"] = re.sub(
                            r"VO2Max\s+\d+(?:\.\d+)?",
                            f"VO2Max {vo2_val}",
                            str(plan["overview_summary"]),
                        )
                    if sched.get("goal_summary") and "VO2Max" in str(sched["goal_summary"]):
                        sched["goal_summary"] = re.sub(
                            r"VO2Max\s+\d+(?:\.\d+)?",
                            f"VO2Max {vo2_val}",
                            str(sched["goal_summary"]),
                        )
            except Exception as ve:
                logger.debug(f"Enrich plan watch vo2max sync skipped: {ve}")

        weeks = sched.get("weeks") or []
        if not weeks:
            plan["current_week_index"] = 1
            plan["current_week_dates"] = []
            return plan

        today_iso = get_beijing_today().isoformat()
        current_week_idx = None
        current_week_dates = []

        for w in weeks:
            days = w.get("days") or []
            # 1. Exact match on any day's date
            if any(str(d.get("date") or "") == today_iso for d in days):
                current_week_idx = w.get("week_index")
                dates = [str(d.get("date") or "") for d in days if d.get("date")]
                if dates:
                    current_week_dates = [dates[0], dates[-1]]
                break
            # 2. Between min and max date of the week
            dates = [str(d.get("date") or "") for d in days if d.get("date")]
            if dates and min(dates) <= today_iso <= max(dates):
                current_week_idx = w.get("week_index")
                current_week_dates = [dates[0], dates[-1]]
                break

        # 3. If today is before the first week
        if current_week_idx is None:
            first_days = weeks[0].get("days") or []
            first_dates = [str(d.get("date") or "") for d in first_days if d.get("date")]
            if first_dates and today_iso < min(first_dates):
                current_week_idx = weeks[0].get("week_index", 1)
                current_week_dates = [first_dates[0], first_dates[-1]] if first_dates else []

        # 4. If today is after the last week
        if current_week_idx is None:
            last_days = weeks[-1].get("days") or []
            last_dates = [str(d.get("date") or "") for d in last_days if d.get("date")]
            if last_dates and today_iso > max(last_dates):
                current_week_idx = weeks[-1].get("week_index", len(weeks))
                current_week_dates = [last_dates[0], last_dates[-1]] if last_dates else []

        plan["current_week_index"] = current_week_idx or 1
        plan["current_week_dates"] = current_week_dates
        src_meta = LocalStore.classify_plan_source(plan)
        plan["source_type"] = src_meta["source_type"]
        plan["source_label"] = src_meta["source_label"]
        return plan

    @staticmethod
    def get_training_plan(plan_id: str, reconcile: bool = True) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM training_plans WHERE id = ?", (plan_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
        if res.get("schedule_data"):
            try:
                res["schedule_data"] = json.loads(res["schedule_data"])
            except Exception:
                pass
        if reconcile:
            res = LocalStore.reconcile_training_plan_activities(res, res.get("user_id"))
        return LocalStore._enrich_plan_with_current_week(res)

    @staticmethod
    def get_user_active_training_plan(user_id: str, reconcile: bool = True) -> Optional[Dict[str, Any]]:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM training_plans 
                WHERE (user_id = ? OR user_id = ?) AND status = 'active'
                ORDER BY updated_at DESC LIMIT 1
            """, (canonical_uid, user_id))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
        if res.get("schedule_data"):
            try:
                res["schedule_data"] = json.loads(res["schedule_data"])
            except Exception:
                pass
        if reconcile:
            res = LocalStore.reconcile_training_plan_activities(res, canonical_uid)
        return LocalStore._enrich_plan_with_current_week(res)

    @staticmethod
    def get_user_draft_training_plan(user_id: str, reconcile: bool = False) -> Optional[Dict[str, Any]]:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM training_plans 
                WHERE (user_id = ? OR user_id = ?) AND status = 'draft'
                ORDER BY updated_at DESC LIMIT 1
            """, (canonical_uid, user_id))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
        if res.get("schedule_data"):
            try:
                res["schedule_data"] = json.loads(res["schedule_data"])
            except Exception:
                pass
        if reconcile:
            res = LocalStore.reconcile_training_plan_activities(res, canonical_uid)
        return LocalStore._enrich_plan_with_current_week(res)

    @staticmethod
    def publish_training_plan(
        plan_id: str,
        operator_uid: str,
        coach_review_note: Optional[str] = None,
        title: Optional[str] = None,
        overview_summary: Optional[str] = None,
        schedule_data: Optional[Dict[str, Any]] = None,
        plan_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        plan = None
        if plan_id and not str(plan_id).startswith("preview_"):
            plan = LocalStore.get_training_plan(plan_id, reconcile=False)

        if not plan and isinstance(plan_payload, dict):
            upsert_data = copy.deepcopy(plan_payload)
            if not upsert_data.get("id") or str(upsert_data.get("id")).startswith("preview_"):
                upsert_data.pop("id", None)
            if schedule_data is not None:
                upsert_data["schedule_data"] = schedule_data
            upsert_data["creator_id"] = upsert_data.get("creator_id") or operator_uid
            upsert_data["last_modified_by"] = operator_uid
            plan = LocalStore.upsert_training_plan(upsert_data)
            if plan:
                plan_id = plan.get("id")

        if not plan:
            return None

        coach_profile = LocalStore.get_profile(operator_uid) or {}
        coach_name = coach_profile.get("display_name") or coach_profile.get("real_name") or "跑团教练"
        now_iso = datetime.utcnow().isoformat() + "Z"
        athlete_uid = plan.get("user_id")

        sched = schedule_data if isinstance(schedule_data, dict) else (plan.get("schedule_data") or {})
        if isinstance(sched, str):
            try:
                sched = json.loads(sched)
            except Exception:
                sched = {}
        sched = copy.deepcopy(sched)

        new_title = title if title is not None else plan.get("title")
        new_overview = overview_summary if overview_summary is not None else plan.get("overview_summary")
        new_note = coach_review_note if coach_review_note is not None else (plan.get("coach_review_note") or "")

        sched["coach_review"] = {
            "reviewed_by": operator_uid,
            "reviewed_by_name": coach_name,
            "reviewed_at": now_iso,
            "coach_review_note": new_note
        }
        weeks_list = sched.get("weeks") or []
        new_weeks_count = len(weeks_list) if weeks_list else int(plan.get("weeks_count") or 4)
        last_days = weeks_list[-1].get("days") if weeks_list else []
        new_end_date = last_days[-1].get("date") if last_days else plan.get("end_date")

        # Record a snapshot of the athlete's previous active plan before publishing/archiving
        prev_active = LocalStore.get_user_active_training_plan(athlete_uid, reconcile=False)
        if prev_active and prev_active.get("id") != plan_id:
            try:
                LocalStore.record_plan_backup(
                    user_id=athlete_uid,
                    action_type="publish_plan",
                    action_label=f"教练审定发布：{new_title}",
                    operator_uid=operator_uid,
                    club_id=plan.get("club_id"),
                    previous_active_plan=prev_active,
                    created_plan_id=plan_id,
                    created_status="active",
                )
            except Exception as be:
                logger.warning(f"Failed to record backup before publish_training_plan: {be}")

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Archive other active plans for this athlete
            cursor.execute("""
                UPDATE training_plans
                SET status = 'archived', updated_at = ?
                WHERE user_id = ? AND status = 'active' AND id != ?
            """, (now_iso, athlete_uid, plan_id))

            cursor.execute("""
                UPDATE training_plans
                SET title = ?, overview_summary = ?, status = 'active',
                    review_status = 'published', reviewed_by = ?, reviewed_by_name = ?,
                    reviewed_at = ?, coach_review_note = ?, schedule_data = ?,
                    weeks_count = ?, end_date = ?,
                    last_modified_by = ?, updated_at = ?
                WHERE id = ?
            """, (
                new_title,
                new_overview,
                operator_uid,
                coach_name,
                now_iso,
                new_note,
                json.dumps(sched, ensure_ascii=False),
                new_weeks_count,
                new_end_date,
                operator_uid,
                now_iso,
                plan_id
            ))
            conn.commit()

        # Notify the athlete
        try:
            note_snippet = f" 教练寄语：「{new_note}」" if new_note else ""
            LocalStore.create_system_notification(
                user_id=athlete_uid,
                title=f"🧢 教练 {coach_name} 已为您审核发布训练计划",
                content=f"您的专属周期课表《{new_title}》已由教练审核定稿并正式发布！{note_snippet}请前往【训练 - 训练课表】查看每周安排并按计划执行。",
                activity_id=plan_id,
                notif_type="coach_plan_published"
            )
        except Exception as e:
            logger.warning(f"Failed to send plan publish notification: {e}")

        return LocalStore.get_training_plan(plan_id, reconcile=True)

    @staticmethod
    def batch_adjust_plan_week(
        plan_id: str,
        week_index: int,
        action: str,
        operator_uid: str,
        scale_factor: Optional[float] = None,
        week_title: Optional[str] = None,
        phase: Optional[str] = None,
        key_focus: Optional[str] = None,
        preview_only: bool = False,
        schedule_data: Optional[Dict[str, Any]] = None,
        plan_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        plan = None
        if plan_id and not str(plan_id).startswith("preview_"):
            plan = LocalStore.get_training_plan(plan_id, reconcile=False)
        if not plan and isinstance(plan_payload, dict):
            plan = copy.deepcopy(plan_payload)
        if not plan:
            return None

        sched = copy.deepcopy(schedule_data if isinstance(schedule_data, dict) else (plan.get("schedule_data") or {}))
        weeks = sched.get("weeks") or []
        target_week = None
        for w in weeks:
            if w.get("week_index") == week_index:
                target_week = w
                break
        if not target_week and 0 <= week_index - 1 < len(weeks):
            target_week = weeks[week_index - 1]
        if not target_week:
            return None

        days = target_week.get("days") or []
        if action == "scale_volume" and scale_factor and scale_factor > 0:
            for d in days:
                if d.get("workout_type") not in ("rest", "cross_training", "race"):
                    old_km = float(d.get("distance_km") or 0.0)
                    if old_km > 0:
                        # Round to nearest 0.5 km
                        new_km = max(2.0, round(old_km * scale_factor * 2.0) / 2.0)
                        d["distance_km"] = new_km
                        d["last_modified_by"] = operator_uid
        elif action == "downgrade_intensity":
            for d in days:
                if d.get("workout_type") in ("interval", "tempo", "trail_climb"):
                    old_title = d.get("title") or ""
                    d["workout_type"] = "easy_run"
                    d["title"] = f"有氧恢复慢跑 (原：{old_title[:12]})"
                    d["target_hr_zone"] = "心率 Z1-Z2 (轻松有氧排酸)"
                    old_km = float(d.get("distance_km") or 0.0)
                    if old_km > 8.0:
                        d["distance_km"] = round(old_km * 0.8 * 2.0) / 2.0
                    existing_note = d.get("coach_notes") or ""
                    if "降级为有氧恢复跑" not in existing_note:
                        d["coach_notes"] = (existing_note + " 教练考虑到近期疲劳负荷，将本节强度课调整为低心率有氧慢跑。").strip()
                    d["last_modified_by"] = operator_uid
        elif action == "update_meta":
            if week_title is not None:
                target_week["week_title"] = week_title
            if phase is not None:
                target_week["phase"] = phase
            if key_focus is not None:
                target_week["key_focus"] = key_focus

        try:
            total_km = sum(float(d.get("distance_km") or 0.0) for d in days)
            target_week["weekly_mileage_km"] = round(total_km, 1)
        except Exception:
            pass

        if preview_only:
            preview_plan = copy.deepcopy(plan)
            preview_plan["schedule_data"] = sched
            preview_plan["is_preview"] = True
            athlete_uid = preview_plan.get("user_id")
            if athlete_uid:
                preview_plan = LocalStore.reconcile_training_plan_activities(preview_plan, athlete_uid)
            return LocalStore._enrich_plan_with_current_week(preview_plan)

        now_iso = datetime.utcnow().isoformat() + "Z"
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE training_plans 
                SET schedule_data = ?, last_modified_by = ?, updated_at = ?
                WHERE id = ?
            """, (json.dumps(sched, ensure_ascii=False), operator_uid, now_iso, plan_id))
            conn.commit()

        return LocalStore.get_training_plan(plan_id, reconcile=True)

    @staticmethod
    def get_user_training_plans(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, club_id, title, goal_type, maintenance_focus,
                       target_race_name, target_date, start_date, end_date,
                       weeks_count, days_per_week, preferred_long_run_day, status,
                       review_status, reviewed_by, reviewed_by_name, reviewed_at, coach_review_note,
                       overview_summary, schedule_data, creator_id, last_modified_by, created_at, updated_at
                FROM training_plans 
                WHERE user_id = ? OR user_id = ?
                ORDER BY updated_at DESC LIMIT ?
            """, (canonical_uid, user_id, limit))
            rows = cursor.fetchall()
            out = []
            for r in rows:
                d = dict(r)
                src = LocalStore.classify_plan_source(d)
                d["source_type"] = src["source_type"]
                d["source_label"] = src["source_label"]
                d.pop("schedule_data", None)
                out.append(d)
            return out

    @staticmethod
    def get_user_plan_backups(
        user_id: str,
        limit: int = 10,
        include_restored: bool = True,
    ) -> List[Dict[str, Any]]:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if include_restored:
                cursor.execute(
                    """
                    SELECT id, batch_id, user_id, club_id, action_type, action_label,
                           previous_active_plan_id, previous_active_plan_json,
                           created_plan_id, created_status, operator_uid, created_at, restored_at
                    FROM training_plan_backups
                    WHERE user_id = ? OR user_id = ?
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (canonical_uid, user_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, batch_id, user_id, club_id, action_type, action_label,
                           previous_active_plan_id, previous_active_plan_json,
                           created_plan_id, created_status, operator_uid, created_at, restored_at
                    FROM training_plan_backups
                    WHERE (user_id = ? OR user_id = ?) AND restored_at IS NULL
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (canonical_uid, user_id, limit),
                )
            rows = cursor.fetchall()

        results = []
        for r in rows:
            item = dict(r)
            prev_title = None
            prev_source_label = None
            raw_json = item.pop("previous_active_plan_json", None)
            if raw_json:
                try:
                    prev_obj = json.loads(raw_json)
                    prev_title = prev_obj.get("title")
                    prev_src = LocalStore.classify_plan_source(prev_obj)
                    prev_source_label = prev_src.get("source_label")
                except Exception:
                    pass
            item["previous_title"] = prev_title
            item["previous_plan_title"] = prev_title
            item["previous_source_label"] = prev_source_label
            item["created_at"] = to_beijing_iso(item.get("created_at"))
            item["restored_at"] = to_beijing_iso(item.get("restored_at"))
            results.append(item)
        return results

    @staticmethod
    def get_club_plan_batches(club_id: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Lists recent batch schedule imports / template assignments so coaches can see what was dispatched
        and undo an entire batch in 1 click.
        """
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if club_id:
                cursor.execute(
                    """
                    SELECT batch_id, club_id, action_type, action_label, created_status,
                           operator_uid, MIN(created_at) AS created_at,
                           COUNT(*) AS affected_count,
                           SUM(CASE WHEN restored_at IS NOT NULL THEN 1 ELSE 0 END) AS restored_count,
                           GROUP_CONCAT(user_id, ',') AS user_ids_csv
                    FROM training_plan_backups
                    WHERE batch_id IS NOT NULL AND batch_id != '' AND restored_at IS NULL
                      AND (club_id = ? OR club_id IS NULL)
                    GROUP BY batch_id
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (club_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT batch_id, club_id, action_type, action_label, created_status,
                           operator_uid, MIN(created_at) AS created_at,
                           COUNT(*) AS affected_count,
                           SUM(CASE WHEN restored_at IS NOT NULL THEN 1 ELSE 0 END) AS restored_count,
                           GROUP_CONCAT(user_id, ',') AS user_ids_csv
                    FROM training_plan_backups
                    WHERE batch_id IS NOT NULL AND batch_id != '' AND restored_at IS NULL
                    GROUP BY batch_id
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            rows = cursor.fetchall()

        batches = []
        for r in rows:
            d = dict(r)
            uids = [u for u in (d.pop("user_ids_csv", "") or "").split(",") if u]
            names = []
            affected_users = []
            for u in uids[:12]:
                prof = LocalStore.get_profile(u) or {}
                nm = prof.get("display_name") or u
                names.append(nm)
                affected_users.append({"user_id": u, "display_name": nm, "new_plan_title": d.get("action_label") or "周课表"})
            d["student_names"] = names
            d["affected_users_count"] = int(d.get("affected_count") or len(uids))
            d["affected_users"] = affected_users
            d["is_restored"] = int(d.get("restored_count") or 0) >= int(d.get("affected_count") or 1)
            d["created_at"] = to_beijing_iso(d.get("created_at"))
            batches.append(d)
        return batches

    @staticmethod
    def rollback_user_training_plan(
        user_id: str,
        operator_uid: Optional[str] = None,
        backup_id: Optional[str] = None,
        target_plan_id: Optional[str] = None,
        discard_draft_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Rolls back or switches an athlete's training plan:
        1) `discard_draft_only=True`: archives/removes the pending draft plan without touching the active plan.
        2) `target_plan_id` provided: switches the athlete's active plan to `target_plan_id` (recording a backup first).
        3) `backup_id` (or latest un-restored backup): restores the exact snapshot from `training_plan_backups`.
        """
        canonical_uid = LocalStore.resolve_user_id(user_id)
        now_iso = datetime.utcnow().isoformat() + "Z"

        if discard_draft_only:
            draft = LocalStore.get_user_draft_training_plan(canonical_uid, reconcile=False)
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE training_plans
                    SET status = 'archived', updated_at = ?
                    WHERE (user_id = ? OR user_id = ?) AND status = 'draft'
                    """,
                    (now_iso, canonical_uid, user_id),
                )
                if draft and draft.get("id"):
                    cursor.execute(
                        """
                        UPDATE training_plan_backups
                        SET restored_at = ?
                        WHERE created_plan_id = ? AND restored_at IS NULL
                        """,
                        (now_iso, draft["id"]),
                    )
                conn.commit()
            active_plan = LocalStore.get_user_active_training_plan(canonical_uid, reconcile=True)
            return {
                "success": True,
                "action": "discard_draft",
                "message": "已撤回待审草案，队员当前正在执行的课表保持不变。",
                "active_plan": active_plan,
                "draft_plan": None,
            }

        if target_plan_id:
            target = LocalStore.get_training_plan(target_plan_id, reconcile=False)
            if not target:
                raise ValueError("未找到目标训练方案")
            cur_active = LocalStore.get_user_active_training_plan(canonical_uid, reconcile=False)
            if cur_active and cur_active.get("id") != target_plan_id:
                LocalStore.record_plan_backup(
                    user_id=canonical_uid,
                    action_type="switch_plan",
                    action_label=f"切换至方案：{target.get('title')}",
                    operator_uid=operator_uid or canonical_uid,
                    club_id=target.get("club_id"),
                    previous_active_plan=cur_active,
                    created_plan_id=target_plan_id,
                    created_status="active",
                )
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE training_plans
                    SET status = 'archived', updated_at = ?
                    WHERE (user_id = ? OR user_id = ?) AND status = 'active' AND id != ?
                    """,
                    (now_iso, canonical_uid, user_id, target_plan_id),
                )
                cursor.execute(
                    """
                    UPDATE training_plans
                    SET status = 'active', updated_at = ?
                    WHERE id = ?
                    """,
                    (now_iso, target_plan_id),
                )
                conn.commit()
            restored = LocalStore.get_user_active_training_plan(canonical_uid, reconcile=True)
            return {
                "success": True,
                "action": "switch_plan",
                "message": f"已切换并恢复为方案：《{restored.get('title') if restored else target.get('title')}》",
                "active_plan": restored,
                "draft_plan": LocalStore.get_user_draft_training_plan(canonical_uid, reconcile=False),
            }

        # Default: restore from backup_id or latest un-restored backup
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if backup_id:
                cursor.execute("SELECT * FROM training_plan_backups WHERE id = ?", (backup_id,))
            else:
                cursor.execute(
                    """
                    SELECT * FROM training_plan_backups
                    WHERE (user_id = ? OR user_id = ?) AND restored_at IS NULL
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (canonical_uid, user_id),
                )
            bak_row = cursor.fetchone()

        if not bak_row:
            # Fallback: if no backup row exists, check if there is a draft we can discard or an archived plan we can restore
            draft = LocalStore.get_user_draft_training_plan(canonical_uid, reconcile=False)
            if draft:
                return LocalStore.rollback_user_training_plan(
                    user_id=canonical_uid,
                    operator_uid=operator_uid,
                    discard_draft_only=True,
                )
            raise ValueError("暂无可回退的历史版本记录")

        bak = dict(bak_row)
        created_pid = bak.get("created_plan_id")
        created_st = bak.get("created_status")
        prev_json = bak.get("previous_active_plan_json")

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # If the operation created a draft, archive that draft
            if created_st == "draft" and created_pid:
                cursor.execute(
                    "UPDATE training_plans SET status = 'archived', updated_at = ? WHERE id = ?",
                    (now_iso, created_pid),
                )
            elif created_pid:
                cursor.execute(
                    "UPDATE training_plans SET status = 'archived', updated_at = ? WHERE id = ? AND status = 'active'",
                    (now_iso, created_pid),
                )
            cursor.execute(
                "UPDATE training_plan_backups SET restored_at = ? WHERE id = ?",
                (now_iso, bak["id"]),
            )
            conn.commit()

        if prev_json:
            try:
                prev_plan_data = json.loads(prev_json)
                prev_plan_data["status"] = "active"
                LocalStore.upsert_training_plan(prev_plan_data, skip_backup=True)
            except Exception as pe:
                logger.error(f"Failed to restore previous_active_plan_json for {canonical_uid}: {pe}")

        restored_active = LocalStore.get_user_active_training_plan(canonical_uid, reconcile=True)
        return {
            "success": True,
            "action": "rollback_backup",
            "backup_id": bak["id"],
            "message": f"已成功回退！恢复为原课表：《{restored_active.get('title') if restored_active else '无课表'}》",
            "active_plan": restored_active,
            "draft_plan": LocalStore.get_user_draft_training_plan(canonical_uid, reconcile=False),
        }

    @staticmethod
    def rollback_plan_batch(batch_id: str, operator_uid: Optional[str] = None) -> Dict[str, Any]:
        """
        Rolls back an entire batch assignment (either imported weekly schedule or batch template assignment)
        across all affected club members in one click.
        """
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM training_plan_backups WHERE batch_id = ? AND restored_at IS NULL",
                (batch_id,),
            )
            rows = [dict(r) for r in cursor.fetchall()]

        if not rows:
            return {
                "success": True,
                "batch_id": batch_id,
                "rolled_back_count": 0,
                "message": "该批次记录已回退或不存在待回退项。",
            }

        rolled_back = []
        for r in rows:
            try:
                res = LocalStore.rollback_user_training_plan(
                    user_id=r["user_id"],
                    operator_uid=operator_uid,
                    backup_id=r["id"],
                )
                rolled_back.append({
                    "user_id": r["user_id"],
                    "active_title": (res.get("active_plan") or {}).get("title"),
                })
            except Exception as e:
                logger.warning(f"Failed to rollback batch item {r['id']} for {r['user_id']}: {e}")

        return {
            "success": True,
            "batch_id": batch_id,
            "rolled_back_count": len(rolled_back),
            "rolled_back_users": rolled_back,
            "message": f"⏪ 已成功一键撤回本批次派发（共恢复 {len(rolled_back)} 名队员的原课表状态）！",
        }

    @staticmethod
    def update_training_plan_workout(
        plan_id: str, 
        week_index: int, 
        day_index: int, 
        workout_update: Dict[str, Any], 
        operator_uid: str,
        preview_only: bool = False,
        schedule_data: Optional[Dict[str, Any]] = None,
        plan_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        plan = None
        if plan_id and not str(plan_id).startswith("preview_"):
            plan = LocalStore.get_training_plan(plan_id, reconcile=False)
        if not plan and isinstance(plan_payload, dict):
            plan = copy.deepcopy(plan_payload)
        if not plan:
            return None

        sched = copy.deepcopy(schedule_data if isinstance(schedule_data, dict) else (plan.get("schedule_data") or {}))
        weeks = sched.get("weeks") or []
        target_week = None
        for w in weeks:
            if w.get("week_index") == week_index:
                target_week = w
                break
        
        if not target_week and 0 <= week_index - 1 < len(weeks):
            target_week = weeks[week_index - 1]

        if not target_week:
            return None

        days = target_week.get("days") or []
        target_day = None
        if 0 <= day_index < len(days):
            target_day = days[day_index]
        else:
            # Match by date if passed
            up_date = workout_update.get("date")
            if up_date:
                for d in days:
                    if d.get("date") == up_date:
                        target_day = d
                        break

        if not target_day:
            return None

        # Check if this week has already started (week start date <= today)
        today_str = get_beijing_today().isoformat()
        week_first_date_str = str((days[0].get("date") if days else "") or "")[:10]
        is_week_started = bool(week_first_date_str and week_first_date_str <= today_str)
        is_self_athlete_op = (
            LocalStore.resolve_user_id(operator_uid) == LocalStore.resolve_user_id(plan.get("user_id") or "")
            and not bool(workout_update.get("is_coach_edit"))
            and not preview_only
        )

        # Handle day swap (e.g. "和周五对换") or undo swap ("取消对换") if requested
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        label_to_idx = {
            "周一": 0, "周1": 0, "周二": 1, "周2": 1, "周三": 2, "周3": 2,
            "周四": 3, "周4": 3, "周五": 4, "周5": 4, "周六": 5, "周6": 5,
            "周日": 6, "周7": 6, "周天": 6,
        }

        def _get_day_label(d_obj: dict, idx: int) -> str:
            lbl = d_obj.get("day_of_week") or d_obj.get("day_label")
            if lbl and str(lbl).strip() not in ("周1", "周2", "周3", "周4", "周5", "周6", "周7"):
                return str(lbl).strip()
            return weekday_names[idx] if 0 <= idx < len(weekday_names) else f"周{idx + 1}"

        def _strip_swap_tags(note_str: Any) -> str:
            if not note_str:
                return ""
            return re.sub(r"\s*[（(]已与[^）)]*对换课表[）)]", "", str(note_str)).strip()

        def _clear_rest_swap_exec(d_obj: dict) -> None:
            exec_t = str(d_obj.get("actual_execution_text") or "").strip()
            if re.match(r"^跑休[，,]?\s*和.*对换$", exec_t):
                d_obj["actual_execution_text"] = ""
                d_obj["manual_execution_override"] = False

        def _find_paired_swap_idx(d_obj: dict, self_idx: int) -> Optional[int]:
            p_idx = d_obj.get("swapped_with_day_index")
            if p_idx is not None:
                try:
                    p_int = int(p_idx)
                    if 0 <= p_int < len(days) and p_int != self_idx:
                        return p_int
                except Exception:
                    pass
            sf = str(d_obj.get("swapped_from") or "").strip()
            if sf in label_to_idx and label_to_idx[sf] != self_idx and 0 <= label_to_idx[sf] < len(days):
                return label_to_idx[sf]
            for text_src in (d_obj.get("athlete_notes"), d_obj.get("actual_execution_text")):
                if not text_src:
                    continue
                m = re.search(r"(?:已与|和)(周[一二三四五六日天1-7])对换", str(text_src))
                if m and m.group(1) in label_to_idx:
                    cand = label_to_idx[m.group(1)]
                    if 0 <= cand < len(days) and cand != self_idx:
                        return cand
            for idx_o, d_o in enumerate(days):
                if idx_o != self_idx and d_o.get("swapped_with_day_index") == self_idx:
                    return idx_o
            return None

        swap_keys = [
            "workout_type", "title", "distance_km", "duration_minutes",
            "target_pace", "target_hr_zone", "description", "coach_notes"
        ]

        def _undo_pair_swap(idx_a: int, idx_b: Optional[int]) -> None:
            day_a = days[idx_a]
            day_b = days[idx_b] if (idx_b is not None and 0 <= idx_b < len(days) and idx_b != idx_a) else None
            orig_a = day_a.get("_original_prescription")
            orig_b = day_b.get("_original_prescription") if day_b else None
            if isinstance(orig_a, dict) and orig_a:
                for k in swap_keys:
                    if k in orig_a:
                        day_a[k] = copy.deepcopy(orig_a.get(k))
            if day_b is not None:
                if isinstance(orig_b, dict) and orig_b:
                    for k in swap_keys:
                        if k in orig_b:
                            day_b[k] = copy.deepcopy(orig_b.get(k))
                elif not (isinstance(orig_a, dict) and orig_a):
                    # Legacy swapped pair without _original_prescription: swap their prescriptions back
                    for k in swap_keys:
                        day_a[k], day_b[k] = day_b.get(k), day_a.get(k)
            for d_clean in ([day_a, day_b] if day_b is not None else [day_a]):
                d_clean["is_swapped"] = False
                d_clean.pop("swapped_from", None)
                d_clean.pop("swapped_with_day_index", None)
                d_clean.pop("_original_prescription", None)
                d_clean["athlete_notes"] = _strip_swap_tags(d_clean.get("athlete_notes"))
                _clear_rest_swap_exec(d_clean)

        swap_idx = workout_update.get("swap_with_day_index")
        if swap_idx is not None:
            try:
                swap_idx = int(swap_idx)
            except Exception:
                swap_idx = None
        undo_swap = bool(workout_update.get("undo_swap")) or (
            workout_update.get("is_swapped") is False and swap_idx is None and (
                target_day.get("is_swapped") or "对换课表" in str(target_day.get("athlete_notes") or "")
            )
        )
        paired_idx = _find_paired_swap_idx(target_day, day_index)
        did_swap_or_undo = False

        # Preserve any user-edited self-feel note (stripped of auto swap tags) before swap/undo
        if "athlete_notes" in workout_update and workout_update["athlete_notes"] is not None:
            if undo_swap or (swap_idx is not None and 0 <= swap_idx < len(days) and swap_idx != day_index):
                target_day["athlete_notes"] = _strip_swap_tags(workout_update["athlete_notes"])

        if undo_swap or (swap_idx is not None and swap_idx == paired_idx and (target_day.get("is_swapped") or paired_idx is not None)):
            # Undoing an existing swap (either explicitly via undo_swap=True or by selecting the paired day again)
            _undo_pair_swap(day_index, paired_idx if paired_idx is not None else swap_idx)
            did_swap_or_undo = True
        elif swap_idx is not None and 0 <= swap_idx < len(days) and swap_idx != day_index:
            # If either day was previously swapped with another day, cleanly restore that pair first
            if paired_idx is not None and paired_idx != swap_idx:
                _undo_pair_swap(day_index, paired_idx)
            other_paired_idx = _find_paired_swap_idx(days[swap_idx], swap_idx)
            if other_paired_idx is not None and other_paired_idx != day_index:
                _undo_pair_swap(swap_idx, other_paired_idx)

            other_day = days[swap_idx]
            if not target_day.get("_original_prescription"):
                target_day["_original_prescription"] = {k: copy.deepcopy(target_day.get(k)) for k in swap_keys}
            if not other_day.get("_original_prescription"):
                other_day["_original_prescription"] = {k: copy.deepcopy(other_day.get(k)) for k in swap_keys}

            for k in swap_keys:
                target_day[k], other_day[k] = other_day.get(k), target_day.get(k)

            _clear_rest_swap_exec(target_day)
            _clear_rest_swap_exec(other_day)

            cur_label = _get_day_label(target_day, day_index)
            other_label = _get_day_label(other_day, swap_idx)
            target_day["is_swapped"] = True
            target_day["swapped_from"] = other_label
            target_day["swapped_with_day_index"] = swap_idx
            other_day["is_swapped"] = True
            other_day["swapped_from"] = cur_label
            other_day["swapped_with_day_index"] = day_index

            note_cur = _strip_swap_tags(target_day.get("athlete_notes"))
            if target_day.get("workout_type") == "rest":
                target_day["actual_execution_text"] = f"跑休，和{other_label}对换"
                target_day["manual_execution_override"] = True
                target_day["athlete_notes"] = note_cur
            else:
                swap_tag = f"（已与{other_label}对换课表）"
                target_day["athlete_notes"] = f"{note_cur} {swap_tag}".strip()

            note_other = _strip_swap_tags(other_day.get("athlete_notes"))
            if other_day.get("workout_type") == "rest":
                other_day["actual_execution_text"] = f"跑休，和{cur_label}对换"
                other_day["manual_execution_override"] = True
                other_day["athlete_notes"] = note_other
            else:
                swap_tag_other = f"（已与{cur_label}对换课表）"
                other_day["athlete_notes"] = f"{note_other} {swap_tag_other}".strip()
            did_swap_or_undo = True

        # Apply updates (including W19 daily biometrics, execution text, RPE, and self-feel notes)
        old_rec_pct = target_day.get("recovery_pct")
        prescription_keys = {"workout_type", "title", "distance_km", "duration_minutes", "target_pace", "target_hr_zone", "description"}
        skip_on_swap_keys = set(swap_keys) | {"is_swapped", "athlete_notes", "actual_execution_text"}
        allowed_keys = [
            "workout_type", "title", "distance_km", "duration_minutes", "target_pace", "target_hr_zone",
            "description", "completed", "coach_notes",
            "hrv", "resting_hr", "respiratory_rate", "strain_score", "recovery_pct",
            "actual_execution_text", "rpe", "feeling_tag", "athlete_notes",
            "workout_photos", "photo_url", "strength_completed", "is_swapped"
        ]
        for key in allowed_keys:
            if key in workout_update and workout_update[key] is not None:
                # Never overwrite the newly swapped/restored workout fields with stale pre-swap form values!
                if did_swap_or_undo and key in skip_on_swap_keys:
                    continue
                # Once a week has started, the athlete's planned workout prescription is locked
                # (only unstarted future weeks or day swaps allow modifying planned prescription fields)
                if is_self_athlete_op and is_week_started and not did_swap_or_undo and key in prescription_keys:
                    continue
                target_day[key] = workout_update[key]

        if "recovery_pct" in workout_update and workout_update["recovery_pct"] is not None:
            if workout_update["recovery_pct"] != old_rec_pct:
                target_day["manual_biometrics_override"] = True
        elif ("hrv" in workout_update or "resting_hr" in workout_update) and target_day.get("recovery_pct") is None:
            comp_manual = LocalStore.compute_physiological_recovery_pct(
                {
                    "hrv_last_night_avg": target_day.get("hrv"),
                    "resting_heart_rate": target_day.get("resting_hr"),
                }
            )
            if comp_manual is not None:
                target_day["recovery_pct"] = comp_manual

        if not did_swap_or_undo and "actual_execution_text" in workout_update and workout_update["actual_execution_text"] is not None:
            exec_txt = str(workout_update["actual_execution_text"]).strip()
            target_day["actual_execution_text"] = exec_txt
            target_day["manual_execution_override"] = bool(exec_txt)
            if exec_txt and "completed" not in workout_update:
                if not exec_txt.startswith("跑休") and not exec_txt.startswith("休息"):
                    target_day["completed"] = True
                    target_day["manual_completed"] = True
                    target_day["is_missed"] = False
                if any(kw in exec_txt for kw in ("身训", "力量", "核心", "臀腿")):
                    target_day["strength_completed"] = True

        if "completed" in workout_update and workout_update["completed"] is not None:
            if workout_update["completed"]:
                target_day["completed"] = True
                target_day["manual_completed"] = True
                target_day["manual_override"] = False
                target_day["is_missed"] = False
            else:
                target_day["completed"] = False
                target_day["manual_completed"] = False
                target_day["manual_override"] = True
                now_beijing = datetime.utcnow() + timedelta(hours=8)
                today_str = now_beijing.strftime("%Y-%m-%d")
                d_date = str(target_day.get("date") or "")
                if d_date and d_date < today_str and target_day.get("workout_type") != "rest":
                    target_day["is_missed"] = True

        target_day["last_modified_by"] = operator_uid
        target_day["last_modified_at"] = datetime.utcnow().isoformat() + "Z"

        # Recalculate weekly mileage
        try:
            total_km = sum(float(d.get("distance_km") or 0.0) for d in days)
            target_week["weekly_mileage_km"] = round(total_km, 1)
        except Exception:
            pass

        if preview_only:
            preview_plan = copy.deepcopy(plan)
            preview_plan["schedule_data"] = sched
            preview_plan["is_preview"] = True
            athlete_uid = preview_plan.get("user_id")
            if athlete_uid:
                preview_plan = LocalStore.reconcile_training_plan_activities(preview_plan, athlete_uid)
            return LocalStore._enrich_plan_with_current_week(preview_plan)

        now_iso = datetime.utcnow().isoformat() + "Z"
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE training_plans 
                SET schedule_data = ?, last_modified_by = ?, updated_at = ?
                WHERE id = ?
            """, (json.dumps(sched, ensure_ascii=False), operator_uid, now_iso, plan_id))
            conn.commit()

        return LocalStore.get_training_plan(plan_id, reconcile=True)

    @staticmethod
    def update_training_plan_week_summary(
        plan_id: str,
        week_index: int,
        summary_update: Dict[str, Any],
        operator_uid: str
    ) -> Optional[Dict[str, Any]]:
        plan = LocalStore.get_training_plan(plan_id, reconcile=False)
        if not plan:
            return None

        sched = plan.get("schedule_data") or {}
        if isinstance(sched, str):
            try:
                sched = json.loads(sched)
            except Exception:
                sched = {}

        if "macro_roadmap" in summary_update and summary_update["macro_roadmap"] is not None:
            sched["macro_roadmap"] = str(summary_update["macro_roadmap"]).strip()

        weeks = sched.get("weeks") or []
        target_week = None
        for w in weeks:
            if w.get("week_index") == week_index:
                target_week = w
                break
        if not target_week and 0 <= week_index - 1 < len(weeks):
            target_week = weeks[week_index - 1]
        if not target_week:
            return None

        ws = target_week.get("week_summary")
        if not isinstance(ws, dict):
            ws = {}

        for key in [
            "injury_note",
            "athlete_weekly_summary",
            "travel_or_leave_note",
            "coach_weekly_diagnosis",
            "strength_count_override",
            "custom_summary_line"
        ]:
            if key in summary_update and summary_update[key] is not None:
                ws[key] = summary_update[key]

        ws["updated_by"] = operator_uid
        ws["updated_at"] = datetime.utcnow().isoformat() + "Z"
        target_week["week_summary"] = ws

        now_iso = datetime.utcnow().isoformat() + "Z"
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE training_plans
                SET schedule_data = ?, last_modified_by = ?, updated_at = ?
                WHERE id = ?
            """, (json.dumps(sched, ensure_ascii=False), operator_uid, now_iso, plan_id))
            conn.commit()

        return LocalStore.get_training_plan(plan_id, reconcile=True)

    @staticmethod
    def roll_next_week_schedule(
        plan_id: str,
        source_week_index: int,
        operator_uid: str,
        coach_diagnosis: Optional[str] = None,
        mileage_delta_pct: Optional[float] = None,
        focus_override: Optional[str] = None,
        weekday_group_workout: Optional[str] = None,
        weekend_long_run_km: Optional[float] = None,
        preview_only: bool = False,
        schedule_data: Optional[Dict[str, Any]] = None,
        plan_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generates or updates Week (source_week_index + 1) based on Week (source_week_index)'s
        execution, HRV/recovery, RPE, injury notes, and the coach's weekly diagnosis,
        matching the Word + Excel weekly rolling coaching workflow.
        """
        plan = None
        if plan_id and not str(plan_id).startswith("preview_"):
            plan = LocalStore.get_training_plan(plan_id, reconcile=True)
        if not plan and isinstance(plan_payload, dict):
            plan = copy.deepcopy(plan_payload)
        if not plan:
            return None

        sched = copy.deepcopy(schedule_data if isinstance(schedule_data, dict) else (plan.get("schedule_data") or {}))
        if isinstance(sched, str):
            try:
                sched = json.loads(sched)
            except Exception:
                sched = {}

        weeks = sched.get("weeks") or []
        if not weeks:
            return None

        source_week = None
        source_pos = 0
        for idx, w in enumerate(weeks):
            if w.get("week_index") == source_week_index:
                source_week = w
                source_pos = idx
                break
        if not source_week:
            if 0 <= source_week_index - 1 < len(weeks):
                source_week = weeks[source_week_index - 1]
                source_pos = source_week_index - 1
            else:
                source_week = weeks[-1]
                source_pos = len(weeks) - 1

        ws = source_week.get("week_summary") or {}
        if coach_diagnosis is not None and str(coach_diagnosis).strip():
            ws["coach_weekly_diagnosis"] = str(coach_diagnosis).strip()
            source_week["week_summary"] = ws

        diag_text = str(ws.get("coach_weekly_diagnosis") or coach_diagnosis or "").strip()
        injury_text = str(ws.get("injury_note") or "").strip()
        has_injury = bool(ws.get("has_injury_alert"))
        avg_rpe = float(ws.get("avg_rpe") or 0.0)
        max_rpe = float(ws.get("max_rpe") or 0.0)
        avg_rec = float(ws.get("avg_recovery_pct") or 0.0)
        completion_pct = int(ws.get("completion_pct") or 0)

        # Determine adaptive mileage multiplier if not explicitly set
        if mileage_delta_pct is not None:
            scale = max(0.5, min(1.35, 1.0 + (float(mileage_delta_pct) / 100.0)))
            rule_tag = f"按教练指定比例 ({mileage_delta_pct:+.0f}%)"
        else:
            if has_injury or (avg_rec > 0 and avg_rec < 45) or max_rpe >= 9.0:
                scale = 0.88
                rule_tag = "检测到伤痛或高疲劳/低恢复度，自动减量 12% 保护"
            elif completion_pct >= 95 and (avg_rpe == 0 or avg_rpe <= 7.5) and (avg_rec == 0 or avg_rec >= 60):
                scale = 1.06
                rule_tag = "上周完成度高且体感平稳，渐进超负荷 +6%"
            else:
                scale = 1.0
                rule_tag = "保持稳态周跑量负荷"

        # Parse explicit long run distance from coach_diagnosis if e.g. "30km长距离" or "长距离28公里"
        import re
        parsed_long_km = weekend_long_run_km
        if not parsed_long_km and diag_text:
            m_lr = re.search(r'(\d{2}(?:\.\d+)?)\s*(?:km|公里|K)\s*(?:长距离|LSD|有氧长跑)?', diag_text, re.IGNORECASE)
            if m_lr:
                try:
                    val = float(m_lr.group(1))
                    if 16.0 <= val <= 42.5:
                        parsed_long_km = val
                except Exception:
                    pass

        needs_strength = any(k in diag_text for k in ("力量", "身训", "弹性", "核心", "臀腿"))

        # Check if next week exists; if not, append a new week to support continuous weekly rolling
        next_pos = source_pos + 1
        if next_pos < len(weeks):
            target_week = weeks[next_pos]
        else:
            target_week = copy.deepcopy(source_week)
            new_w_idx = int(source_week.get("week_index") or len(weeks)) + 1
            target_week["week_index"] = new_w_idx
            target_week["week_title"] = f"第 {new_w_idx} 周 · 滚动进阶周期"
            # Advance dates by 7 days
            src_days = source_week.get("days") or []
            new_days = []
            for d_i, sd in enumerate(src_days):
                nd = copy.deepcopy(sd)
                old_date_str = str(sd.get("date") or "")
                try:
                    dt_obj = datetime.strptime(old_date_str[:10], "%Y-%m-%d").date() + timedelta(days=7)
                    nd["date"] = dt_obj.isoformat()
                except Exception:
                    pass
                # Reset execution fields for the new week
                for reset_k in [
                    "completed", "manual_completed", "manual_override", "is_missed",
                    "matched_activities", "actual_distance_km", "actual_duration_str",
                    "actual_avg_pace", "actual_avg_hr", "completion_rate_pct",
                    "hrv", "resting_hr", "respiratory_rate", "strain_score", "recovery_pct",
                    "actual_execution_text", "manual_execution_override", "rpe",
                    "athlete_notes", "strength_completed", "is_swapped"
                ]:
                    nd.pop(reset_k, None)
                nd["completed"] = False
                new_days.append(nd)
            target_week["days"] = new_days
            target_week["week_summary"] = {}
            weeks.append(target_week)

        # Now apply rolling adjustments onto target_week
        t_days = target_week.get("days") or []
        src_days = source_week.get("days") or []
        for idx, td in enumerate(t_days):
            # If target day has no workout structure yet, inherit base structure from source week day
            sd = src_days[idx] if idx < len(src_days) else {}
            w_type = td.get("workout_type") or sd.get("workout_type") or "easy_run"
            base_km = float(sd.get("distance_km") or td.get("distance_km") or 0.0)

            if w_type not in ("rest", "cross_training", "race") and base_km > 0:
                scaled_km = max(3.0, round(base_km * scale * 2.0) / 2.0)
                td["distance_km"] = scaled_km

            # If injury/low recovery, soften mid-week intensity
            if has_injury and w_type in ("interval", "tempo"):
                td["workout_type"] = "easy_run"
                td["title"] = f"恢复慢跑+力训保护 (原:{(td.get('title') or '强度课')[:10]})"
                td["target_hr_zone"] = "Z1-Z2 低心率有氧"
                td["coach_notes"] = f"考虑到上周伤痛反馈（{injury_text}），本周将间歇/节奏课降级为有氧恢复跑。"

            # Apply club weekday group workout if provided (typically Tuesday idx=1 or Thursday idx=3)
            if weekday_group_workout and idx == 1:
                td["title"] = weekday_group_workout
                td["workout_type"] = "interval" if "速度" in weekday_group_workout or "间歇" in weekday_group_workout else "tempo"
                td["description"] = f"{weekday_group_workout}（跑团统一合练课表）"

            # Apply strength emphasis if coach diagnosis highlighted leg strength / elasticity
            if needs_strength and idx in (1, 3):
                cur_title = str(td.get("title") or "")
                if "身训" not in cur_title and "力量" not in cur_title:
                    td["title"] = f"{cur_title}+臀腿身训".strip("+")
                cur_desc = str(td.get("description") or "")
                if "臀腿" not in cur_desc and "力量" not in cur_desc:
                    td["description"] = (cur_desc + "；跑后加做2组臀腿离心与核心弹跳训练，强化落地弹性。").strip("；")

            # Apply weekend long run override if parsed or specified
            if parsed_long_km and (w_type == "long_run" or idx in (5, 6) and float(td.get("distance_km") or 0) >= 14):
                td["workout_type"] = "long_run"
                td["distance_km"] = round(float(parsed_long_km), 1)
                td["title"] = f"周末重点有氧长距离 {td['distance_km']:g}km"
                td["description"] = f"按教练周度复盘导向完成 {td['distance_km']:g} 公里有氧耐力长距离，前半程压住配速，后程保持核心稳定与落地弹性。"
                parsed_long_km = None  # only apply to the primary long run day

            td["last_modified_by"] = operator_uid

        if focus_override:
            target_week["key_focus"] = focus_override
        elif diag_text:
            target_week["key_focus"] = f"承接W{source_week.get('week_index')}复盘：{diag_text[:48]}"
        else:
            target_week["key_focus"] = f"承接W{source_week.get('week_index')}（{rule_tag}）"

        target_week["rolled_from_week"] = source_week.get("week_index")
        target_week["rolling_rule_applied"] = rule_tag

        try:
            total_km = sum(float(d.get("distance_km") or 0.0) for d in t_days)
            target_week["weekly_mileage_km"] = round(total_km, 1)
        except Exception:
            pass

        # Update plan end_date and weeks_count if we appended a new week
        new_weeks_count = len(weeks)
        last_days = weeks[-1].get("days") or []
        new_end_date = last_days[-1].get("date") if last_days else plan.get("end_date")

        if preview_only:
            preview_plan = copy.deepcopy(plan)
            preview_plan["schedule_data"] = sched
            preview_plan["weeks_count"] = new_weeks_count
            preview_plan["end_date"] = new_end_date
            preview_plan["is_preview"] = True
            athlete_uid = preview_plan.get("user_id")
            if athlete_uid:
                preview_plan = LocalStore.reconcile_training_plan_activities(preview_plan, athlete_uid)
            return LocalStore._enrich_plan_with_current_week(preview_plan)

        now_iso = datetime.utcnow().isoformat() + "Z"
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE training_plans
                SET schedule_data = ?, weeks_count = ?, end_date = ?, last_modified_by = ?, updated_at = ?
                WHERE id = ?
            """, (
                json.dumps(sched, ensure_ascii=False),
                new_weeks_count,
                new_end_date,
                operator_uid,
                now_iso,
                plan_id
            ))
            conn.commit()

        return LocalStore.get_training_plan(plan_id, reconcile=True)

    @staticmethod
    def broadcast_club_workout_to_members(
        club_id: str,
        operator_uid: str,
        day_index: int,
        workout_template: Dict[str, Any],
        user_ids: Optional[List[str]] = None,
        target_week_mode: str = "current"
    ) -> Dict[str, Any]:
        """
        Broadcasts a shared club workout (e.g. Tuesday 交大合练 or Saturday Soar长距离合练)
        into the active/pending training plans of multiple club members at once.
        """
        if not (0 <= day_index <= 6):
            return {"updated_count": 0, "updated_plan_ids": []}

        if not user_ids:
            club_members = LocalStore.get_club_members(club_id) or []
            user_ids = [m["user_id"] for m in club_members if m.get("user_id")]
        if not user_ids:
            return {"updated_count": 0, "updated_plan_ids": []}

        resolved_uids = list({LocalStore.resolve_user_id(u) for u in user_ids} | set(user_ids))
        placeholders = ",".join(["?"] * len(resolved_uids))
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT id, user_id, schedule_data, start_date
                FROM training_plans
                WHERE status IN ('active', 'draft') AND user_id IN ({placeholders})
                ORDER BY CASE WHEN status = 'active' THEN 0 ELSE 1 END, updated_at DESC
            """, resolved_uids)
            rows = [dict(r) for r in cursor.fetchall()]

        seen_users = set()
        updated_plan_ids = []
        now_beijing = datetime.utcnow() + timedelta(hours=8)
        today_str = now_beijing.strftime("%Y-%m-%d")

        for r in rows:
            uid = r["user_id"]
            if uid in seen_users:
                continue
            seen_users.add(uid)
            pid = r["id"]
            try:
                sched = json.loads(r["schedule_data"] or "{}")
            except Exception:
                continue
            weeks = sched.get("weeks") or []
            if not weeks:
                continue

            # Find current week index
            cur_w_idx = 1
            for w in weeks:
                days = w.get("days") or []
                if days:
                    d_start = str(days[0].get("date") or "")
                    d_end = str(days[-1].get("date") or "")
                    if d_start <= today_str <= d_end:
                        cur_w_idx = int(w.get("week_index") or 1)
                        break

            target_w_idx = cur_w_idx + 1 if target_week_mode == "next" else cur_w_idx
            if target_w_idx > len(weeks):
                target_w_idx = len(weeks)

            updated = LocalStore.update_training_plan_workout(
                plan_id=pid,
                week_index=target_w_idx,
                day_index=day_index,
                workout_update=workout_template,
                operator_uid=operator_uid
            )
            if updated:
                updated_plan_ids.append(pid)

        return {
            "updated_count": len(updated_plan_ids),
            "updated_plan_ids": updated_plan_ids,
            "day_index": day_index,
            "target_week_mode": target_week_mode
        }

    @staticmethod
    def _normalize_template_dict(tpl: Dict[str, Any], is_custom: bool = False) -> Dict[str, Any]:
        pz = dict(tpl.get("pace_zones") or {})
        easy_v = pz.get("easy") or pz.get("easy_pace") or "5:20-5:45/km"
        mar_v = pz.get("marathon") or pz.get("marathon_pace") or "4:40-4:55/km"
        tmp_v = pz.get("tempo") or pz.get("threshold_pace") or "4:25-4:35/km"
        int_v = pz.get("interval") or pz.get("interval_pace") or "4:00-4:10/km"
        long_v = pz.get("long_run") or pz.get("core_workout") or "18-24km LSD"
        pz.update({
            "easy": easy_v,
            "easy_pace": easy_v,
            "marathon": mar_v,
            "marathon_pace": mar_v,
            "tempo": tmp_v,
            "threshold_pace": tmp_v,
            "interval": int_v,
            "interval_pace": int_v,
            "long_run": long_v,
            "core_workout": pz.get("core_workout") or f"{int_v} · {long_v}",
        })
        t_level = tpl.get("target_level") or tpl.get("target_pb_label") or "全马专项进阶"
        i_tag = tpl.get("intensity_tag") or tpl.get("intensity_badge") or "专项配速与耐力训练"
        c_note = tpl.get("coach_review_note") or tpl.get("description") or ""
        desc = tpl.get("description") or c_note
        is_cust = bool(tpl.get("is_custom", is_custom))
        try:
            from utils.canova_template_progression import stage_outline
            _is_taper = tpl.get("id") == "group_e_taper" or "taper" in str(tpl.get("category") or "")
            canova_outline = {str(n): stage_outline(n, is_taper=_is_taper) for n in (4, 6, 8, 12)}
        except Exception:
            canova_outline = {}
        return {
            **tpl,
            "canova_outline": canova_outline,
            "is_custom": is_cust,
            "is_builtin": not is_cust,
            "is_private_to_coach": is_cust,
            "scope_label": "🔒 仅本人可见 · 跨跑团通用" if is_cust else "🌐 系统公共标准模版",
            "category": tpl.get("category") or ("custom" if is_cust else "road_marathon"),
            "target_level": t_level,
            "target_pb_label": t_level,
            "intensity_tag": i_tag,
            "intensity_badge": i_tag,
            "coach_review_note": c_note,
            "description": desc,
            "pace_zones": pz,
        }

    @staticmethod
    def get_coach_training_templates(
        club_id: Optional[str] = None,
        operator_uid: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Returns structured training plan templates grouped by pace, target finish time, weekly volume, and scenario:
        - 8 Built-in System Templates (Road Marathon 240/A/B/C/D/E, Gobi Challenge A-Team, Ultra Trail 50K-100K):
          shared across all coaches.
        - Coach Custom Templates (`coach_custom_templates`):
          strictly private to the individual coach (`operator_uid` / `creator_id`) who created/saved them,
          and available across ALL running clubs that this coach manages.
        """
        builtin_templates = [
            {
                "id": "group_s_sub240",
                "group_code": "240组",
                "category": "road_marathon",
                "name": "240组 · 全马240/245大神精英组 (双阈值+高强长间歇+32k专项)",
                "short_name": "👑 240组 · 全马240精英",
                "badge_color": "amber",
                "target_level": "全马 2:30-2:48 · 半马 1:12-1:18",
                "intensity_tag": "大神高阶 · 2000m长间歇 + 16k马配巡航 + 32k渐进大课",
                "weekly_km": 98.0,
                "days_per_week": 6,
                "pace_zones": {
                    "easy": "4:20-4:40/km",
                    "marathon": "3:42-3:50/km",
                    "tempo": "3:30-3:36/km",
                    "interval": "3:15-3:22/km (2000m×5组)",
                    "long_run": "32km (前20k@4:05 + 后12k@3:44/km)"
                },
                "macro_roadmap": "阶段大纲：第1-2周 高容量有氧与双阈值巩固 (95-100km) → 第3周 2000m长间歇与32km比赛配速混氧大课 (108km) → 第4周 赛前减量超量恢复 (75km)",
                "coach_review_note": "【240精英组课表】高跑量高强度周期务必监控晨起HRV与静息心率；周二长间歇与周四马配巡航强调动作经济性，周日32km后12km严格切入345目标马配。",
                "days_template": [
                    {
                        "day_index": 1,
                        "day_of_week": "周一",
                        "workout_type": "easy_run",
                        "title": "主动排酸恢复慢跑 + 深度筋膜松解",
                        "distance_km": 12.0,
                        "target_pace": "4:30-4:45/km",
                        "target_hr_zone": "Zone 1-2 (<138 bpm)",
                        "description": "周末32km大课后主动恢复慢跑12km，全程压住心率放松步频，跑后30分钟泡沫轴与拉伸。"
                    },
                    {
                        "day_index": 2,
                        "day_of_week": "周二",
                        "workout_type": "interval",
                        "title": "操场VO2Max长间歇 (2000m×5组) + 专项身训",
                        "distance_km": 18.0,
                        "target_pace": "3:16-3:22/km",
                        "target_hr_zone": "Zone 4-5 (172-182 bpm)",
                        "description": "慢跑热身3km + 行进间技术体操 + (2000米@6分36秒 慢跑400m间休2分15秒)×5组 + 200m×4快步频 + 冷身2km。"
                    },
                    {
                        "day_index": 3,
                        "day_of_week": "周三",
                        "workout_type": "easy_run",
                        "title": "中长距离有氧稳态跑 + 髋核心抗阻力量",
                        "distance_km": 16.0,
                        "target_pace": "4:20-4:35/km",
                        "target_hr_zone": "Zone 2 (140-150 bpm)",
                        "description": "有氧稳态巡航16km，巩固毛细血管密度；晚间完成单腿硬拉、保加利亚分腿蹲与核心抗旋训练2组。"
                    },
                    {
                        "day_index": 4,
                        "day_of_week": "周四",
                        "workout_type": "tempo_run",
                        "title": "乳酸阈巡航节奏跑 14km (LT2专项)",
                        "distance_km": 18.0,
                        "target_pace": "3:32-3:38/km",
                        "target_hr_zone": "Zone 3-4 (164-172 bpm)",
                        "description": "热身2km + 14km连续乳酸阈节奏跑(配速335左右，练习高速巡航下的呼吸节奏与补给吞咽) + 冷身2km。"
                    },
                    {
                        "day_index": 5,
                        "day_of_week": "周五",
                        "workout_type": "rest",
                        "title": "跑休 · 糖原超量填充与睡眠恢复",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "Zone 1",
                        "description": "完全跑休或轻柔拉伸，监测晨起HRV与静息心率，确保周五晚深度睡眠。"
                    },
                    {
                        "day_index": 6,
                        "day_of_week": "周六",
                        "workout_type": "easy_run",
                        "title": "赛前唤醒有氧跑 + 100m冲刺跑×6",
                        "distance_km": 12.0,
                        "target_pace": "4:25-4:40/km",
                        "target_hr_zone": "Zone 2",
                        "description": "轻松有氧慢跑10km + 6组100米轻快冲刺激活快肌纤维募集，为周日32km专项课做准备。"
                    },
                    {
                        "day_index": 7,
                        "day_of_week": "周日",
                        "workout_type": "long_run",
                        "title": "Canova专项渐进长距离 32km (前20k有氧+后12k马配)",
                        "distance_km": 32.0,
                        "target_pace": "4:05 渐进至 3:44/km",
                        "target_hr_zone": "Zone 2 渐进至 Zone 3-4",
                        "description": "前20km按4:00-4:08/km稳态有氧巡航，后12km提速至3:42-3:46/km目标全马配速巡航；每5km严格按比赛节奏补胶补水。"
                    }
                ]
            },
            {
                "id": "group_a_sub300",
                "group_code": "A组",
                "name": "A组 · 精英破三/310组 (高强间歇+混氧专项)",
                "short_name": "🔥 A组 · 破三/310",
                "badge_color": "rose",
                "target_level": "全马 2:50-3:15 · 半马 1:20-1:32",
                "intensity_tag": "高强度 · 1000m间歇 + 乳酸阈巡航 + 26k渐进LSD",
                "weekly_km": 76.0,
                "days_per_week": 6,
                "pace_zones": {
                    "easy": "4:50-5:10/km",
                    "marathon": "4:00-4:12/km",
                    "tempo": "3:50-4:00/km",
                    "interval": "3:32-3:42/km (1000m 3分36秒)",
                    "long_run": "4:35-4:55 渐进至 4:08/km"
                },
                "macro_roadmap": "阶段大纲：第1-2周 有氧容量与乳酸阈巡航 (74-78km) → 第3周 高强间歇与专项混氧长距离 (82km) → 第4周 周期减量超量吸收 (60km)",
                "coach_review_note": "【A组·精英破三课表】周二操场间歇与周四节奏跑务必卡准目标配速区间，轻松跑严格压心率在 Zone 2，切勿把恢复跑跑成节奏跑。",
                "days_template": [
                    {
                        "day_index": 1,
                        "day_of_week": "周一",
                        "workout_type": "easy_run",
                        "title": "恢复排酸慢跑 + 泡沫轴拉伸",
                        "distance_km": 8.0,
                        "target_pace": "5:00-5:15/km",
                        "target_hr_zone": "Zone 1-2 (<138 bpm)",
                        "description": "周末长距离后主动排酸慢跑8km，全程放松步频，跑后20分钟泡沫轴深度放松小腿与股四头肌。"
                    },
                    {
                        "day_index": 2,
                        "day_of_week": "周二",
                        "workout_type": "interval",
                        "title": "操场VO2Max高强间歇合练 + 身训2组",
                        "distance_km": 14.0,
                        "target_pace": "3:35-3:42/km",
                        "target_hr_zone": "Zone 4-5 (168-178 bpm)",
                        "description": "慢跑热身3km + 动态身训2组 + (1000米×3分36秒 慢跑间休2分钟)×6组 + 慢跑冷身2km。"
                    },
                    {
                        "day_index": 3,
                        "day_of_week": "周三",
                        "workout_type": "easy_run",
                        "title": "有氧稳态慢跑 + 核心抗阻力量",
                        "distance_km": 12.0,
                        "target_pace": "4:50-5:05/km",
                        "target_hr_zone": "Zone 2 (138-148 bpm)",
                        "description": "有氧轻松跑12km，保持呼吸平稳；跑后完成单腿硬拉、臀桥与核心平板支撑2组。"
                    },
                    {
                        "day_index": 4,
                        "day_of_week": "周四",
                        "workout_type": "tempo_run",
                        "title": "乳酸阈巡航节奏跑 (LT2 专项)",
                        "distance_km": 16.0,
                        "target_pace": "3:52-4:00/km",
                        "target_hr_zone": "Zone 3-4 (160-168 bpm)",
                        "description": "热身2km + 12km连续乳酸阈节奏跑(配速355左右，均匀控速) + 冷身2km。"
                    },
                    {
                        "day_index": 5,
                        "day_of_week": "周五",
                        "workout_type": "rest",
                        "title": "跑休 · 睡眠与糖原恢复",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "Zone 1",
                        "description": "完全跑休，关注晨起HRV与静息心率恢复，保证充足睡眠。"
                    },
                    {
                        "day_index": 6,
                        "day_of_week": "周六",
                        "workout_type": "easy_run",
                        "title": "长距离前唤醒慢跑 + 100m冲刺×4",
                        "distance_km": 10.0,
                        "target_pace": "4:55-5:10/km",
                        "target_hr_zone": "Zone 2",
                        "description": "轻松有氧慢跑9km + 4组100米轻快跨步跑激活神经，不累积疲劳。"
                    },
                    {
                        "day_index": 7,
                        "day_of_week": "周日",
                        "workout_type": "long_run",
                        "title": "Canova 渐进混氧长距离 LSD",
                        "distance_km": 26.0,
                        "target_pace": "4:45 渐进至 4:08/km",
                        "target_hr_zone": "Zone 2-3 (145-162 bpm)",
                        "description": "前16km按4:45/km有氧稳态巡航，后10km渐进提速至4:08-4:12/km目标全马配速，每5km演练能量胶与补水。"
                    }
                ]
            },
            {
                "id": "group_b_sub330",
                "group_code": "B组",
                "name": "B组 · 进取破330组 (速度感知+有氧耐力 · 晓韵同款)",
                "short_name": "⚡ B组 · 破330",
                "badge_color": "amber",
                "target_level": "全马 3:15-3:35 · 半马 1:33-1:42",
                "intensity_tag": "中高强度 · 400m间歇 + 15k耐力 + 18k周末LSD",
                "weekly_km": 56.0,
                "days_per_week": 5,
                "pace_zones": {
                    "easy": "5:35-5:55/km",
                    "marathon": "4:45-4:58/km",
                    "tempo": "4:32-4:45/km",
                    "interval": "4:05-4:15/km (400m 1分38秒)",
                    "long_run": "5:25-5:45 渐进至 4:55/km"
                },
                "macro_roadmap": "阶段大纲：第1-2周 有氧耐力筑基与跑姿身训 (54-56km) → 第3周 混氧间歇与长距离强化 (60km) → 第4周 周期减量调整周 (45km)",
                "coach_review_note": "【B组·进取330课表】重点抓周二合练400m间歇节奏感与周四15km有氧心率稳定，每周至少完成1次核心/下肢身训。",
                "days_template": [
                    {
                        "day_index": 1,
                        "day_of_week": "周一",
                        "workout_type": "easy_run",
                        "title": "有氧轻松慢跑 + 身训2组",
                        "distance_km": 5.0,
                        "target_pace": "5:45-6:00/km",
                        "target_hr_zone": "Zone 2 (<140 bpm)",
                        "description": "慢跑5km（545-600配速）排酸唤醒 + 核心与下肢稳定性身训2组。"
                    },
                    {
                        "day_index": 2,
                        "day_of_week": "周二",
                        "workout_type": "interval",
                        "title": "操场间歇速度合练 (400m×5×2大组)",
                        "distance_km": 12.0,
                        "target_pace": "400m 1分38秒",
                        "target_hr_zone": "Zone 4 (162-172 bpm)",
                        "description": "慢跑热身2km + 身训2组 + (400米×1分38秒 间休1分20秒)×5组×2大组（组间休3分钟）+ 慢跑冷身2km。"
                    },
                    {
                        "day_index": 3,
                        "day_of_week": "周三",
                        "workout_type": "rest",
                        "title": "跑休 · 筋膜放松与恢复",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "Zone 1",
                        "description": "间歇课后跑休一天，结合晨起HRV与恢复%评估疲劳，泡沫轴放松大腿前侧与小腿。"
                    },
                    {
                        "day_index": 4,
                        "day_of_week": "周四",
                        "workout_type": "easy_run",
                        "title": "中长距离有氧耐力跑 15km",
                        "distance_km": 15.0,
                        "target_pace": "5:40-6:00/km",
                        "target_hr_zone": "Zone 2 (132-145 bpm)",
                        "description": "15km有氧稳态耐力跑，全程压住心率不漂移，强化有氧脂肪供能效率。"
                    },
                    {
                        "day_index": 5,
                        "day_of_week": "周五",
                        "workout_type": "rest",
                        "title": "跑休 (可与周六灵活调休对换)",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "Zone 1",
                        "description": "跑休蓄能；若周末有出行安排，可将本休整日与周五/周六课表灵活对换。"
                    },
                    {
                        "day_index": 6,
                        "day_of_week": "周六",
                        "workout_type": "easy_run",
                        "title": "轻松慢跑 + 力量训练1次",
                        "distance_km": 6.0,
                        "target_pace": "5:45-6:00/km",
                        "target_hr_zone": "Zone 2",
                        "description": "轻松跑6km活动关节 + 臀中肌与核心抗阻力量训练1次（计入周力量打卡）。"
                    },
                    {
                        "day_index": 7,
                        "day_of_week": "周日",
                        "workout_type": "long_run",
                        "title": "周末有氧长距离 LSD 18km",
                        "distance_km": 18.0,
                        "target_pace": "5:25-5:45/km",
                        "target_hr_zone": "Zone 2-3 (138-152 bpm)",
                        "description": "18km周末长距离耐力课，前12km稳守540配速，后6km若体感轻松可自然渐进至505-515配速。"
                    }
                ]
            },
            {
                "id": "group_c_sub400",
                "group_code": "C组",
                "name": "C组 · 稳健破四/345组 (有氧扩容+M配速稳态)",
                "short_name": "🛡️ C组 · 破四/345",
                "badge_color": "emerald",
                "target_level": "全马 3:40-4:05 · 半马 1:43-1:55",
                "intensity_tag": "中等强度 · 速度感知 + M配速稳态 + 16k长距离",
                "weekly_km": 45.0,
                "days_per_week": 4,
                "pace_zones": {
                    "easy": "6:00-6:20/km",
                    "marathon": "5:20-5:38/km",
                    "tempo": "5:05-5:18/km",
                    "interval": "4:40-4:52/km (400m 1分52秒)",
                    "long_run": "5:50-6:15/km"
                },
                "macro_roadmap": "阶段大纲：第1-2周 低心率有氧底座扩容 (43-45km) → 第3周 马拉松配速稳态拉练 (49km) → 第4周 吸收排酸周 (36km)",
                "coach_review_note": "【C组·稳健破四课表】核心是把有氧底座做厚、周末长距离后半程不掉速，周四稳态跑控制在微喘可交谈状态。",
                "days_template": [
                    {
                        "day_index": 1,
                        "day_of_week": "周一",
                        "workout_type": "rest",
                        "title": "跑休 · 下肢恢复与拉伸",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "Zone 1",
                        "description": "完全休息，让周末长距离后的肌纤维充分超量恢复。"
                    },
                    {
                        "day_index": 2,
                        "day_of_week": "周二",
                        "workout_type": "interval",
                        "title": "操场速度感知间歇课 (400m×8组)",
                        "distance_km": 9.0,
                        "target_pace": "400m 1分52秒",
                        "target_hr_zone": "Zone 3-4 (155-166 bpm)",
                        "description": "慢跑热身2km + 身训2组 + (400米×1分52秒 间休1分30秒)×8组 + 慢跑冷身1.5km。"
                    },
                    {
                        "day_index": 3,
                        "day_of_week": "周三",
                        "workout_type": "rest",
                        "title": "跑休 + 核心与臀中肌力量",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "Zone 1",
                        "description": "不安排路跑，居家完成25分钟核心、靠墙静蹲与臀中肌训练1次。"
                    },
                    {
                        "day_index": 4,
                        "day_of_week": "周四",
                        "workout_type": "tempo_run",
                        "title": "马拉松目标配速稳态跑 10km",
                        "distance_km": 10.0,
                        "target_pace": "5:20-5:30/km",
                        "target_hr_zone": "Zone 3 (148-158 bpm)",
                        "description": "2km轻松热身 + 6km按5:20-5:30/km稳态巡航 + 2km慢跑冷身。"
                    },
                    {
                        "day_index": 5,
                        "day_of_week": "周五",
                        "workout_type": "rest",
                        "title": "跑休 · 周末大课前蓄能",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "Zone 1",
                        "description": "跑休一天，保证睡眠与碳水摄入。"
                    },
                    {
                        "day_index": 6,
                        "day_of_week": "周六",
                        "workout_type": "easy_run",
                        "title": "低心率有氧轻松跑 10km",
                        "distance_km": 10.0,
                        "target_pace": "6:00-6:20/km",
                        "target_hr_zone": "Zone 2 (132-144 bpm)",
                        "description": "轻松舒适慢跑10km，全程可完整交谈，巩固有氧毛细血管密度。"
                    },
                    {
                        "day_index": 7,
                        "day_of_week": "周日",
                        "workout_type": "long_run",
                        "title": "周末有氧耐力长距离 LSD 16km",
                        "distance_km": 16.0,
                        "target_pace": "5:55-6:15/km",
                        "target_hr_zone": "Zone 2 (135-148 bpm)",
                        "description": "16km有氧长距离，前半程严格压住配速不快于600，每5km补水，培养后半程耐力。"
                    }
                ]
            },
            {
                "id": "group_d_base",
                "group_code": "D组",
                "name": "D组 · 完赛筑基/戈壁备战组 (低心率有氧+防伤核心)",
                "short_name": "🌱 D组 · 完赛筑基",
                "badge_color": "sky",
                "target_level": "全马 4:15-5:00 · 半马 2:00+ / 戈壁挑战",
                "intensity_tag": "中低强度 · 低心率慢跑 + 变速跑 + 膝踝防伤力量",
                "weekly_km": 32.0,
                "days_per_week": 4,
                "pace_zones": {
                    "easy": "6:35-7:05/km",
                    "marathon": "6:00-6:25/km",
                    "tempo": "5:45-6:05/km",
                    "interval": "5:15-5:35/km (200m轻快跑)",
                    "long_run": "6:35-7:05/km"
                },
                "macro_roadmap": "阶段大纲：第1-2周 跑姿经济性与膝踝稳定性力量筑基 (30-32km) → 第3周 连续有氧耐力拉练 (35km) → 第4周 恢复巩固周 (26km)",
                "coach_review_note": "【D组·有氧筑基课表】不追求绝对配速，以跑完规定距离/时长且心率平稳为第一目标，每周务必完成2次下肢与核心防伤训练。",
                "days_template": [
                    {
                        "day_index": 1,
                        "day_of_week": "周一",
                        "workout_type": "rest",
                        "title": "跑休 · 足底与小腿放松",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "Zone 1",
                        "description": "完全休息，用筋膜球滚压足底筋膜与小腿三头肌。"
                    },
                    {
                        "day_index": 2,
                        "day_of_week": "周二",
                        "workout_type": "interval",
                        "title": "有氧慢跑 + 200m轻快变速跑×6组",
                        "distance_km": 7.0,
                        "target_pace": "6:30/km + 200m轻快",
                        "target_hr_zone": "Zone 2-3",
                        "description": "慢跑4km热身 + 身训2组 + (200米轻快跑 + 200米慢走恢复)×6组，改善跑姿步频与心肺弹性。"
                    },
                    {
                        "day_index": 3,
                        "day_of_week": "周三",
                        "workout_type": "rest",
                        "title": "跑休 + 膝踝稳定性身训2组",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "Zone 1",
                        "description": "居家完成靠墙静蹲、蚌式开合、提踵与平板支撑2组，强化膝踝关节保护。"
                    },
                    {
                        "day_index": 4,
                        "day_of_week": "周四",
                        "workout_type": "easy_run",
                        "title": "低心率燃脂有氧慢跑 8km",
                        "distance_km": 8.0,
                        "target_pace": "6:35-7:00/km",
                        "target_hr_zone": "Zone 2 (<142 bpm)",
                        "description": "8km低心率稳态慢跑，保持高步频(175+)小步幅，减小膝关节冲击。"
                    },
                    {
                        "day_index": 5,
                        "day_of_week": "周五",
                        "workout_type": "rest",
                        "title": "跑休 · 睡眠恢复",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "Zone 1",
                        "description": "完全休息，为周末耐力课储备体能。"
                    },
                    {
                        "day_index": 6,
                        "day_of_week": "周六",
                        "workout_type": "easy_run",
                        "title": "轻松恢复跑 5km + 核心训练",
                        "distance_km": 5.0,
                        "target_pace": "6:40-7:05/km",
                        "target_hr_zone": "Zone 2",
                        "description": "轻松慢跑5km + 15分钟核心力量与跑后全身拉伸。"
                    },
                    {
                        "day_index": 7,
                        "day_of_week": "周日",
                        "workout_type": "long_run",
                        "title": "周末有氧耐力慢跑 LSD 12km",
                        "distance_km": 12.0,
                        "target_pace": "6:40-7:05/km",
                        "target_hr_zone": "Zone 2 (132-145 bpm)",
                        "description": "12km周末长距离有氧耐力课，不追配速，中途可每4km补水一次，安全顺利完课。"
                    }
                ]
            },
            {
                "id": "group_e_taper",
                "group_code": "E组",
                "name": "E组 · 赛前减量 / 伤痛疲劳恢复周模版",
                "short_name": "🧘 E组 · 减量恢复",
                "badge_color": "purple",
                "target_level": "全组别通用 · 赛前减量 / HRV偏低或轻微伤痛调整",
                "intensity_tag": "低强度恢复 · 跑量削减40% + 神经唤醒 + 深度排酸",
                "weekly_km": 26.0,
                "days_per_week": 4,
                "pace_zones": {
                    "easy": "比日常轻松跑慢 15-20秒/km",
                    "marathon": "目标配速短距离体验",
                    "tempo": "暂停高强乳酸阈课",
                    "interval": "400m×4组 轻度神经激活",
                    "long_run": "10km 轻松有氧维持跑感"
                },
                "macro_roadmap": "阶段大纲：深度消除累积疲劳，优先保证睡眠、HRV回升与肌糖原超量储备，轻度短冲维持肌肉张力",
                "coach_review_note": "【减量恢复课表】本周核心任务是休息与排酸吸收，严禁私自加量或盲目冲配速，如有任何部位酸痛立即跑休。",
                "days_template": [
                    {
                        "day_index": 1,
                        "day_of_week": "周一",
                        "workout_type": "rest",
                        "title": "完全跑休 · 深度睡眠恢复",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "Zone 1",
                        "description": "彻底休息，保证8小时充足睡眠，促进自主神经HRV恢复。"
                    },
                    {
                        "day_index": 2,
                        "day_of_week": "周二",
                        "workout_type": "easy_run",
                        "title": "轻度神经唤醒慢跑 + 400m×3",
                        "distance_km": 6.0,
                        "target_pace": "轻松配速",
                        "target_hr_zone": "Zone 2",
                        "description": "慢跑4km + 3组400米按目标马拉松配速轻快跑（间休2分钟）+ 1km冷身，保持跑感不累。"
                    },
                    {
                        "day_index": 3,
                        "day_of_week": "周三",
                        "workout_type": "rest",
                        "title": "跑休 · 泡沫轴与温水泡脚",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "Zone 1",
                        "description": "完全跑休，进行温和拉伸与筋膜放松。"
                    },
                    {
                        "day_index": 4,
                        "day_of_week": "周四",
                        "workout_type": "easy_run",
                        "title": "极低心率排酸慢跑 6km",
                        "distance_km": 6.0,
                        "target_pace": "恢复配速",
                        "target_hr_zone": "Zone 1-2 (<135 bpm)",
                        "description": "6km极轻松排酸跑，若身体有任何疲劳感可随时减至4km。"
                    },
                    {
                        "day_index": 5,
                        "day_of_week": "周五",
                        "workout_type": "rest",
                        "title": "跑休 · 糖原储备",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "Zone 1",
                        "description": "完全休息，补充优质碳水与电解质。"
                    },
                    {
                        "day_index": 6,
                        "day_of_week": "周六",
                        "workout_type": "easy_run",
                        "title": "唤醒慢跑 4km + 100m冲刺×3",
                        "distance_km": 4.0,
                        "target_pace": "轻松配速",
                        "target_hr_zone": "Zone 2",
                        "description": "4km唤醒跑，活动关节与心肺。"
                    },
                    {
                        "day_index": 7,
                        "day_of_week": "周日",
                        "workout_type": "long_run",
                        "title": "减量周中等距离有氧跑 10km",
                        "distance_km": 10.0,
                        "target_pace": "轻松有氧配速",
                        "target_hr_zone": "Zone 2 (<140 bpm)",
                        "description": "10km轻松有氧跑，点到为止，跑后立即拉伸补充能量。"
                    }
                ]
            },
            {
                "id": "group_gobi_a",
                "group_code": "戈赛A组",
                "category": "gobi_desert",
                "name": "戈赛A组 · 戈壁挑战赛高水平竞赛组 (多日背靠背+抗风阻负重专项)",
                "short_name": "🏜️ 戈赛A组 · 戈壁竞赛组",
                "badge_color": "amber",
                "target_level": "商学院戈壁挑战赛A队主力 · 4天121km多日高强竞速",
                "intensity_tag": "戈壁专项 · 周末26k+22k背靠背拉练 + 1200m间歇 + 负重抗风阻",
                "weekly_km": 88.0,
                "days_per_week": 6,
                "pace_zones": {
                    "easy": "4:35-4:55/km",
                    "marathon": "3:55-4:08/km (戈壁巡航)",
                    "tempo": "3:42-3:50/km (顶风抗阻)",
                    "interval": "3:28-3:35/km (1200m×6组)",
                    "long_run": "背靠背 Day1 26km + Day2 22km"
                },
                "macro_roadmap": "阶段大纲：储蓄期(月跑量320km+) → 专项背靠背强化期(模拟戈壁4天连续作战+高温补给演练) → 赛前10天减量超量恢复 → 戈壁正赛冲冠",
                "coach_review_note": "【戈壁挑战赛A队竞赛课表】核心在于周末连续两天背靠背(Back-to-Back)长距离抗疲劳能力与软沙石路面踝膝稳定性，务必背水袋包实测盐丸与能量胶补给。",
                "days_template": [
                    {
                        "day_index": 1,
                        "day_of_week": "周一",
                        "workout_type": "easy_run",
                        "title": "背靠背拉练后排酸慢跑 + 足底与小腿深层松解",
                        "distance_km": 8.0,
                        "target_pace": "4:50-5:10/km",
                        "target_hr_zone": "Zone 1-2 (<138 bpm)",
                        "description": "周末双长距离后主动排酸慢跑8km，重点放松比目鱼肌、跟腱与足底筋膜。"
                    },
                    {
                        "day_index": 2,
                        "day_of_week": "周二",
                        "workout_type": "interval",
                        "title": "操场1200m长间歇×6组 + 戈壁防崴脚踝膝稳定身训",
                        "distance_km": 14.0,
                        "target_pace": "3:28-3:35/km",
                        "target_hr_zone": "Zone 4-5 (168-178 bpm)",
                        "description": "热身3km + (1200米@4分12秒 间休90秒)×6组 + 软垫单腿平衡闭眼提踵、臀中肌与核心抗风阻身训2组。"
                    },
                    {
                        "day_index": 3,
                        "day_of_week": "周三",
                        "workout_type": "easy_run",
                        "title": "有氧稳态巡航 + 臀腿离心力量训练",
                        "distance_km": 12.0,
                        "target_pace": "4:40-4:55/km",
                        "target_hr_zone": "Zone 2 (140-150 bpm)",
                        "description": "有氧巡航12km；跑后完成负重深蹲、保加利亚分腿蹲与农夫行走3组，强化戈壁软沙路面推进力。"
                    },
                    {
                        "day_index": 4,
                        "day_of_week": "周四",
                        "workout_type": "tempo_run",
                        "title": "Fartlek法特莱克变速节奏跑 16km (模拟戈壁地形切换)",
                        "distance_km": 16.0,
                        "target_pace": "3:45-4:10/km 交替",
                        "target_hr_zone": "Zone 3-4 (158-170 bpm)",
                        "description": "热身2km + 12km变速节奏跑(每2km@3:45/km快配 + 1km@4:12/km不降速恢复，模拟雅丹/盐碱地/软沙交替) + 冷身2km。"
                    },
                    {
                        "day_index": 5,
                        "day_of_week": "周五",
                        "workout_type": "rest",
                        "title": "跑休 · 糖原与电解质超量储备",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "Zone 1",
                        "description": "完全跑休，整理周末背靠背强制装备与水袋包，保证8小时睡眠。"
                    },
                    {
                        "day_index": 6,
                        "day_of_week": "周六",
                        "workout_type": "long_run",
                        "title": "戈壁背靠背 Day 1：负重渐进长距离 26km",
                        "distance_km": 26.0,
                        "target_pace": "4:20 渐进至 3:55/km",
                        "target_hr_zone": "Zone 2-3",
                        "description": "穿戴参赛水袋包(负重1.5kg)完成26km拉练，后8km顶至戈壁竞赛巡航配速，每30分钟强制补水与电解质盐丸。"
                    },
                    {
                        "day_index": 7,
                        "day_of_week": "周日",
                        "workout_type": "long_run",
                        "title": "戈壁背靠背 Day 2：疲劳态稳态长距离 22km",
                        "distance_km": 22.0,
                        "target_pace": "4:10-4:25/km",
                        "target_hr_zone": "Zone 2-3",
                        "description": "在周六26km肌肉未完全恢复状态下连续出发22km，专练戈壁第3、第4竞赛日的抗掉速意志与脂肪供能效率。"
                    }
                ]
            },
            {
                "id": "group_trail_ultra",
                "group_code": "越野组",
                "category": "ultra_trail",
                "name": "越野组 · 50K-100K长距离山野越野组 (垂直爬升+下坡离心抗震专项)",
                "short_name": "⛰️ 越野组 · 50K-100K长距离越野",
                "badge_color": "emerald",
                "target_level": "50km-100km长距离越野赛 · 周累计爬升 2200m-3000m+",
                "intensity_tag": "山野专项 · 陡坡间歇 + 下坡离心股四头肌抗震 + 28k山野拉练",
                "weekly_km": 68.0,
                "days_per_week": 5,
                "pace_zones": {
                    "easy": "5:20-5:50/km (平路有氧)",
                    "marathon": "等强配速 EP 4:50-5:15/km",
                    "tempo": "6%-10%坡度门槛巡航 40分钟",
                    "interval": "陡坡冲刺 3分钟×8组 (RPE 8-9)",
                    "long_run": "山野拉练 28-35km (爬升1500m+)"
                },
                "macro_roadmap": "阶段大纲：平路有氧与下肢抗震筑基 → 垂直爬升与高强度上下坡技术专项 → 背靠背夜跑头灯与肠胃补给实测 → 赛前减量储能",
                "coach_review_note": "【长距离越野专项课表】百公里越野决胜于下坡股四头肌抗离心崩溃能力与后半程肠胃补给耐受度；周中务必保质完成坡度间歇与离心力量，周末进山严守安全强制装备。",
                "days_template": [
                    {
                        "day_index": 1,
                        "day_of_week": "周一",
                        "workout_type": "rest",
                        "title": "跑休 · 膝踝关节与股四头肌筋膜松解",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "Zone 1",
                        "description": "周末进山拉练后完全跑休，重点泡沫轴松解髂胫束、股四头肌外侧与小腿三头肌。"
                    },
                    {
                        "day_index": 2,
                        "day_of_week": "周二",
                        "workout_type": "interval",
                        "title": "陡坡VO2Max间歇 (3min×8组) + 下坡离心抗震力量",
                        "distance_km": 12.0,
                        "target_pace": "坡度8%-12% 强力推坡",
                        "target_hr_zone": "Zone 4 (165-175 bpm)",
                        "description": "热身2km + 陡坡(或跑步机10%坡度)3分钟强力上坡×8组(慢跑下坡恢复) + 跑后慢速离心单腿下台阶、靠墙静蹲与脚踝稳定性训练3组。"
                    },
                    {
                        "day_index": 3,
                        "day_of_week": "周三",
                        "workout_type": "easy_run",
                        "title": "平路低心率恢复有氧跑 10km",
                        "distance_km": 10.0,
                        "target_pace": "5:25-5:45/km",
                        "target_hr_zone": "Zone 2 (<142 bpm)",
                        "description": "平路高步频小步幅轻松跑10km，促进下肢血液循环排酸。"
                    },
                    {
                        "day_index": 4,
                        "day_of_week": "周四",
                        "workout_type": "tempo_run",
                        "title": "起伏坡道/台阶混氧节奏跑 14km + 双杖推进核心",
                        "distance_km": 14.0,
                        "target_pace": "等强配速 4:40-4:55/km",
                        "target_hr_zone": "Zone 3-4 (155-166 bpm)",
                        "description": "选择有连续起伏坡道或天桥/台阶路线完成14km混氧跑，练习上坡切换碎步与平路快速衔接；晚间加练上肢推举与背阔肌发力。"
                    },
                    {
                        "day_index": 5,
                        "day_of_week": "周五",
                        "workout_type": "rest",
                        "title": "跑休 · 强制装备检查与足部防起泡护理",
                        "distance_km": 0.0,
                        "target_pace": "—",
                        "target_hr_zone": "Zone 1",
                        "description": "完全跑休，检查越野背包、救生毯、头灯电量与登山杖锁扣，修剪脚趾甲。"
                    },
                    {
                        "day_index": 6,
                        "day_of_week": "周六",
                        "workout_type": "long_run",
                        "title": "山野长距离越野拉练 24km (累计爬升1500m+)",
                        "distance_km": 24.0,
                        "target_pace": "按地形心率控制 (山野4-5小时)",
                        "target_hr_zone": "Zone 2-3",
                        "description": "进山实操24km(爬升1500m+)：上坡熟练双杖省力推进，技术下坡高频小步轻落地；严格执行每小时摄入50-60g碳水(能量胶/固态食物)肠胃训练。"
                    },
                    {
                        "day_index": 7,
                        "day_of_week": "周日",
                        "workout_type": "easy_run",
                        "title": "背靠背疲劳态排酸有氧跑 8km",
                        "distance_km": 8.0,
                        "target_pace": "5:40-6:05/km",
                        "target_hr_zone": "Zone 2",
                        "description": "周六进山次日完成8km平路恢复跑，强化百公里后半程双腿沉重状态下的动作控制。"
                    }
                ]
            }
        ]

        custom_list: List[Dict[str, Any]] = []
        raw_uid = (operator_uid or "").strip()
        if raw_uid:
            canonical_uid = LocalStore.resolve_user_id(raw_uid)
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    # Coach custom templates are strictly private to the creator coach (`creator_id`)
                    # and portable across ALL running clubs managed by that coach.
                    cursor.execute(
                        "SELECT * FROM coach_custom_templates WHERE creator_id IN (?, ?) ORDER BY updated_at DESC",
                        (raw_uid, canonical_uid)
                    )
                    for row in cursor.fetchall():
                        r = dict(row)
                        try:
                            pz = json.loads(r.get("pace_zones") or "{}")
                        except Exception:
                            pz = {}
                        try:
                            dt = json.loads(r.get("days_template") or "[]")
                        except Exception:
                            dt = []
                        custom_list.append(
                            LocalStore._normalize_template_dict({
                                "id": r["id"],
                                "club_id": r.get("club_id"),
                                "creator_id": r.get("creator_id"),
                                "group_code": r["group_code"],
                                "category": r.get("category") or "custom",
                                "name": r["name"],
                                "short_name": r["short_name"],
                                "badge_color": r.get("badge_color") or "amber",
                                "target_level": r.get("target_level") or "",
                                "intensity_tag": r.get("intensity_tag") or "",
                                "weekly_km": float(r.get("weekly_km") or 50.0),
                                "days_per_week": int(r.get("days_per_week") or 5),
                                "pace_zones": pz,
                                "macro_roadmap": r.get("macro_roadmap") or "",
                                "coach_review_note": r.get("coach_review_note") or "",
                                "days_template": dt,
                                "created_at": r.get("created_at"),
                                "updated_at": r.get("updated_at"),
                            }, is_custom=True)
                        )
            except Exception as e:
                logger.warning(f"Failed to load custom coach templates: {e}")

        normalized_builtins = [LocalStore._normalize_template_dict(t, is_custom=False) for t in builtin_templates]
        return custom_list + normalized_builtins

    @staticmethod
    def save_coach_custom_template(
        operator_uid: str,
        club_id: Optional[str] = None,
        template_id: Optional[str] = None,
        group_code: str = "自定义组",
        category: str = "custom",
        name: Optional[str] = None,
        short_name: Optional[str] = None,
        badge_color: str = "amber",
        target_level: str = "专项定制组别",
        intensity_tag: str = "教练定制配速与强度",
        weekly_km: Optional[float] = None,
        days_per_week: Optional[int] = None,
        pace_zones: Optional[Dict[str, Any]] = None,
        macro_roadmap: str = "",
        coach_review_note: str = "",
        days_template: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Creates or updates a coach custom training template (e.g. Sub-240 Elite, Gobi Challenge A+, Ultra Trail 100K).
        The custom template belongs exclusively to `operator_uid` and can be used across all running clubs this coach manages.
        If template_id is a built-in template ID, belongs to another coach, or is None, a new custom template ID is generated.
        """
        raw_uid = (operator_uid or "").strip()
        canonical_uid = LocalStore.resolve_user_id(raw_uid) if raw_uid else ""
        eff_creator = canonical_uid or raw_uid

        builtin_ids = {
            "group_s_sub240", "group_a_sub300", "group_b_sub330",
            "group_c_sub400", "group_d_base", "group_e_taper",
            "group_gobi_a", "group_trail_ultra"
        }
        is_updating_existing = False
        if template_id and template_id not in builtin_ids:
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT creator_id FROM coach_custom_templates WHERE id = ?", (template_id,))
                existing_row = cur.fetchone()
                if existing_row and existing_row[0] in (raw_uid, canonical_uid, eff_creator):
                    is_updating_existing = True
                elif not existing_row:
                    # Allow explicit custom ID if it doesn't collide with another coach's template
                    is_updating_existing = True

        final_id = template_id if is_updating_existing else f"custom_tpl_{uuid.uuid4().hex[:10]}"

        clean_code = (group_code or "专项组").strip()[:16]
        clean_short = (short_name or f"✨ {clean_code}").strip()
        clean_name = (name or f"{clean_code} · {target_level}").strip()

        days_list = list(days_template or [])
        days_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        norm_days = []
        calc_weekly_km = 0.0
        calc_run_days = 0
        for idx in range(7):
            src = days_list[idx] if idx < len(days_list) else {}
            w_type = src.get("workout_type") or "easy_run"
            dist = round(float(src.get("distance_km") or 0.0), 1)
            if w_type == "rest" or dist <= 0:
                dist = 0.0
            else:
                calc_weekly_km += dist
                calc_run_days += 1
            norm_days.append({
                "day_index": idx + 1,
                "day_of_week": days_labels[idx],
                "workout_type": w_type,
                "title": src.get("title") or ("休息日" if dist == 0 else "训练课"),
                "distance_km": dist,
                "target_pace": src.get("target_pace") or ("—" if dist == 0 else "有氧配速"),
                "target_hr_zone": src.get("target_hr_zone") or ("Zone 1" if dist == 0 else "Zone 2"),
                "description": src.get("description") or "",
            })

        eff_weekly_km = round(float(weekly_km if weekly_km is not None else calc_weekly_km), 1)
        eff_days_pw = int(days_per_week if days_per_week is not None else max(1, calc_run_days))
        eff_pz = pace_zones or {
            "easy": "5:00-5:30/km",
            "marathon": "4:30-4:45/km",
            "tempo": "4:15-4:25/km",
            "interval": "3:55-4:05/km",
            "long_run": "20-26km LSD"
        }

        now_iso = datetime.utcnow().isoformat() + "Z"
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO coach_custom_templates (
                    id, club_id, creator_id, group_code, category, name, short_name,
                    badge_color, target_level, intensity_tag, weekly_km, days_per_week,
                    pace_zones, macro_roadmap, coach_review_note, days_template, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    group_code = excluded.group_code,
                    category = excluded.category,
                    name = excluded.name,
                    short_name = excluded.short_name,
                    badge_color = excluded.badge_color,
                    target_level = excluded.target_level,
                    intensity_tag = excluded.intensity_tag,
                    weekly_km = excluded.weekly_km,
                    days_per_week = excluded.days_per_week,
                    pace_zones = excluded.pace_zones,
                    macro_roadmap = excluded.macro_roadmap,
                    coach_review_note = excluded.coach_review_note,
                    days_template = excluded.days_template,
                    updated_at = excluded.updated_at
            """, (
                final_id, club_id or "", eff_creator, clean_code, category or "custom",
                clean_name, clean_short, badge_color or "amber", target_level, intensity_tag,
                eff_weekly_km, eff_days_pw, json.dumps(eff_pz, ensure_ascii=False),
                macro_roadmap, coach_review_note, json.dumps(norm_days, ensure_ascii=False),
                now_iso, now_iso
            ))
            conn.commit()

        return LocalStore._normalize_template_dict({
            "id": final_id,
            "club_id": club_id or "",
            "creator_id": eff_creator,
            "group_code": clean_code,
            "category": category or "custom",
            "name": clean_name,
            "short_name": clean_short,
            "badge_color": badge_color or "amber",
            "target_level": target_level,
            "intensity_tag": intensity_tag,
            "weekly_km": eff_weekly_km,
            "days_per_week": eff_days_pw,
            "pace_zones": eff_pz,
            "macro_roadmap": macro_roadmap,
            "coach_review_note": coach_review_note,
            "days_template": norm_days,
            "created_at": now_iso,
            "updated_at": now_iso,
        }, is_custom=True)

    @staticmethod
    def delete_coach_custom_template(template_id: str, operator_uid: Optional[str] = None) -> bool:
        raw_uid = (operator_uid or "").strip()
        canonical_uid = LocalStore.resolve_user_id(raw_uid) if raw_uid else ""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if raw_uid:
                cursor.execute(
                    "DELETE FROM coach_custom_templates WHERE id = ? AND creator_id IN (?, ?)",
                    (template_id, raw_uid, canonical_uid)
                )
            else:
                cursor.execute("DELETE FROM coach_custom_templates WHERE id = ?", (template_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def _parse_duration_sec(val: Any) -> Optional[int]:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            iv = int(val)
            return iv if iv > 0 else None
        s = str(val).strip()
        if not s:
            return None
        if s.isdigit():
            iv = int(s)
            return iv if iv > 0 else None
        # Support Chinese format like '3小时30分' or '3小时45分12秒'
        if "小时" in s or "分" in s:
            try:
                import re
                m_hr = re.search(r"(\d+)\s*小时", s)
                m_min = re.search(r"(\d+)\s*分", s)
                m_sec = re.search(r"(\d+)\s*秒", s)
                hrs = int(m_hr.group(1)) if m_hr else 0
                mins = int(m_min.group(1)) if m_min else 0
                secs = int(m_sec.group(1)) if m_sec else 0
                tot = hrs * 3600 + mins * 60 + secs
                return tot if tot > 0 else None
            except Exception:
                pass
        parts = s.split(":")
        try:
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(float(parts[2]))
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(float(parts[1]))
        except Exception:
            return None
        return None

    @staticmethod
    def _format_duration_hms(sec: Optional[int]) -> Optional[str]:
        if not sec or sec <= 0:
            return None
        s = int(sec)
        h = s // 3600
        m = (s % 3600) // 60
        rem = s % 60
        if h > 0:
            return f"{h}:{m:02d}:{rem:02d}"
        return f"{m}:{rem:02d}"

    @staticmethod
    def resolve_verified_runner_profile_and_pbs(
        uid: str,
        profile: Optional[Dict[str, Any]] = None,
        recent_acts: Optional[List[Dict[str, Any]]] = None,
        query_activities: bool = True,
    ) -> Dict[str, Any]:
        """
        Extracts verified runner PBs (filtering out legacy SQLite schema default placeholders
        like 10800/5100/2400/1140), supplements with activity-verified best FM/HM/10K times,
        and resolves age & gender for scientific group recommendation.
        """
        prof = profile if profile is not None else (LocalStore.get_profile(uid) or {})
        raw_mp = LocalStore._parse_duration_sec(prof.get("marathon_pb"))
        raw_hp = LocalStore._parse_duration_sec(prof.get("half_pb"))
        raw_tk = LocalStore._parse_duration_sec(prof.get("ten_k_pb"))
        raw_fk = LocalStore._parse_duration_sec(prof.get("five_k_pb"))
        org_mp = LocalStore._parse_duration_sec(prof.get("org_marathon_pb"))

        # Detect legacy SQLite schema default placeholders:
        # 1) Production legacy schema default: (10800, 5100, 2400, 1140)
        # 2) Partial Garmin PR sync where half_pb was updated (e.g. > 5600s) but marathon_pb remained 10800
        # 3) Local schema default (11370, 5457, 2426, 1164) on non-Alex profiles
        # 4) Partial manual update where marathon_pb was updated (e.g. 4:20:00) while half_pb/ten_k_pb/five_k_pb stayed at schema defaults
        is_non_alex = (
            uid not in ("u_df65d9a588c9", "user_001")
            and str(prof.get("display_name") or "") != "Alex"
        )
        has_default_tk_fk = (raw_tk in (2400, 2426) and raw_fk in (1140, 1164) and is_non_alex)
        is_legacy_10800_tuple = (raw_mp == 10800 and raw_hp == 5100 and raw_tk == 2400 and raw_fk == 1140)
        is_legacy_11370_tuple = (
            raw_mp == 11370 and raw_hp == 5457 and raw_tk == 2426 and raw_fk == 1164 and is_non_alex
        )
        mp_is_placeholder = (
            is_legacy_10800_tuple
            or is_legacy_11370_tuple
            or (raw_mp in (10800, 11370) and has_default_tk_fk)
            or (raw_mp == 10800 and raw_hp is not None and raw_hp > 5600)
        )
        hp_is_placeholder = (
            is_legacy_10800_tuple
            or is_legacy_11370_tuple
            or (raw_hp in (5100, 5457) and has_default_tk_fk)
            or (raw_hp == 5100 and raw_tk is not None and raw_tk > 2800)
        )
        tk_is_placeholder = is_legacy_10800_tuple or is_legacy_11370_tuple or has_default_tk_fk
        fk_is_placeholder = (
            is_legacy_10800_tuple
            or is_legacy_11370_tuple
            or has_default_tk_fk
            or (raw_fk in (1140, 1164) and is_non_alex)
        )

        # Compute best verified continuous outdoor FM / HM / 10K / 5K & peak VDOT from full history (or recent_acts)
        best_fm_sec: Optional[int] = None
        best_hm_sec: Optional[int] = None
        best_10k_sec: Optional[int] = None
        best_5k_sec: Optional[int] = None
        best_long_continuous_vdot: float = 0.0
        try:
            from utils.running_metrics import calculate_vdot

            act_rows = []
            if query_activities:
                with sqlite3.connect(DB_PATH) as conn:
                    c = conn.cursor()
                    c.execute(
                        """
                        SELECT sport_type, name, distance_meters, moving_time_seconds,
                               elapsed_time_seconds, average_heartrate, average_cadence, exclude_mode
                        FROM activities
                        WHERE user_id = ? AND distance_meters >= 4850 AND moving_time_seconds >= 800
                        """,
                        (uid,),
                    )
                    act_rows = c.fetchall()
            if not act_rows and recent_acts is not None:
                for a in recent_acts:
                    act_rows.append((
                        a.get("sport_type"),
                        a.get("name"),
                        a.get("distance_meters"),
                        a.get("moving_time_seconds"),
                        a.get("elapsed_time_seconds"),
                        a.get("average_heartrate"),
                        a.get("average_cadence"),
                        a.get("exclude_mode"),
                    ))

            for sp_type, act_name, dist_m, mov_s, elp_s, avg_hr, avg_cad, ex_mode in act_rows:
                if ex_mode in ("excluded", "ignore_vdot"):
                    continue
                if not LocalStore.is_running_activity(sp_type):
                    continue
                sp_low = str(sp_type or "").lower()
                nm_low = str(act_name or "").lower()
                # Exclude uncalibrated indoor treadmills from historical continuous PB extraction
                if "treadmill" in sp_low or "indoor" in sp_low or "跑步机" in nm_low or "室内" in nm_low:
                    continue

                dist = float(dist_m or 0.0)
                mov_sec = float(mov_s or 0.0)
                elp_sec = float(elp_s or 0.0)
                if dist < 4850.0 or mov_sec < 800.0:
                    continue

                # Continuous effort check: reject paused interval workouts or GPS auto-pause glitches
                if elp_sec > 0:
                    if elp_sec > mov_sec * 1.09 and (elp_sec - mov_sec) > 180.0:
                        continue
                    secs = max(mov_sec, elp_sec - 60.0)
                else:
                    secs = mov_sec

                pace_s_km = secs / (dist / 1000.0)
                if not (165.0 <= pace_s_km <= 480.0):
                    continue

                cad_val = float(avg_cad or 0.0)
                hr_val = float(avg_hr or 0.0)
                # Filter out cycling / vehicle / walking glitches masquerading as runs
                if cad_val > 0 and cad_val < 142.0:
                    continue
                if pace_s_km < 270.0 and 0 < hr_val < 122.0:
                    continue

                if 41500.0 <= dist <= 44500.0 and pace_s_km >= 190.0:
                    norm_fm = int(round(secs * 42195.0 / dist))
                    if best_fm_sec is None or norm_fm < best_fm_sec:
                        best_fm_sec = norm_fm
                elif 20800.0 <= dist <= 22800.0 and pace_s_km >= 175.0:
                    norm_hm = int(round(secs * 21097.5 / dist))
                    if best_hm_sec is None or norm_hm < best_hm_sec:
                        best_hm_sec = norm_hm
                elif 9700.0 <= dist <= 16500.0 and pace_s_km >= 170.0:
                    norm_10k = int(round(secs * 10000.0 / dist))
                    if best_10k_sec is None or norm_10k < best_10k_sec:
                        best_10k_sec = norm_10k
                elif 4850.0 <= dist <= 6000.0 and pace_s_km >= 165.0:
                    norm_5k = int(round(secs * 5000.0 / dist))
                    if best_5k_sec is None or norm_5k < best_5k_sec:
                        best_5k_sec = norm_5k

                if 15000.0 <= dist <= 44500.0:
                    lv = calculate_vdot(dist, secs)
                    if lv > best_long_continuous_vdot:
                        best_long_continuous_vdot = lv
        except Exception:
            pass

        verified_mp_sec = org_mp or (None if mp_is_placeholder else raw_mp) or best_fm_sec
        verified_hp_sec = (None if hp_is_placeholder else raw_hp) or best_hm_sec
        verified_10k_sec = (None if tk_is_placeholder else raw_tk) or best_10k_sec
        verified_5k_sec = (None if fk_is_placeholder else raw_fk) or best_5k_sec

        peak_vdot: Optional[float] = None
        peak_endurance_vdot: Optional[float] = None
        try:
            from utils.running_metrics import calculate_vdot

            v_mp = calculate_vdot(42195.0, float(verified_mp_sec)) if (verified_mp_sec and 7200 <= verified_mp_sec <= 30000) else 0.0
            v_hp = calculate_vdot(21097.5, float(verified_hp_sec)) if (verified_hp_sec and 3000 <= verified_hp_sec <= 15000) else 0.0
            endurance_pb_v = max(v_mp, v_hp)

            v_tk = calculate_vdot(10000.0, float(verified_10k_sec)) if (verified_10k_sec and 1200 <= verified_10k_sec <= 7200) else 0.0
            v_act_tk = calculate_vdot(10000.0, float(best_10k_sec)) if (best_10k_sec and 1200 <= best_10k_sec <= 7200) else 0.0
            if endurance_pb_v > 0 and v_tk > endurance_pb_v + 3.5 and v_act_tk < v_tk - 3.0:
                verified_10k_sec = best_10k_sec
                v_tk = v_act_tk

            v_fk = calculate_vdot(5000.0, float(verified_5k_sec)) if (verified_5k_sec and 600 <= verified_5k_sec <= 3600) else 0.0
            v_act_fk = calculate_vdot(5000.0, float(best_5k_sec)) if (best_5k_sec and 600 <= best_5k_sec <= 3600) else 0.0
            if endurance_pb_v > 0 and v_fk > endurance_pb_v + 4.0 and v_act_fk < v_fk - 3.0:
                verified_5k_sec = best_5k_sec
                v_fk = v_act_fk

            raw_peak = max(0.0, v_mp, v_hp, v_tk, v_fk, best_long_continuous_vdot)
            raw_end_peak = max(
                0.0,
                v_mp,
                v_hp * 0.975 if v_hp > 0 else 0.0,
                best_long_continuous_vdot * 0.97 if best_long_continuous_vdot > 0 else 0.0,
                v_tk * 0.95 if v_tk > 0 else 0.0,
                v_fk * 0.925 if v_fk > 0 else 0.0,
            )
            if raw_peak > 0:
                peak_vdot = round(raw_peak, 1)
            if raw_end_peak > 0:
                peak_endurance_vdot = round(raw_end_peak, 1)
        except Exception:
            pass

        # Resolve Age
        age: Optional[int] = None
        if prof.get("age") is not None:
            try:
                age = int(prof["age"])
            except Exception:
                pass
        if age is None:
            dob_str = str(prof.get("date_of_birth") or "").strip()[:10]
            if dob_str and len(dob_str) >= 4 and dob_str[:4].isdigit():
                try:
                    by = int(dob_str[:4])
                    today_d = date.today()
                    age = today_d.year - by
                    if len(dob_str) >= 10:
                        bm = int(dob_str[5:7])
                        bd = int(dob_str[8:10])
                        if (today_d.month, today_d.day) < (bm, bd):
                            age -= 1
                except Exception:
                    pass
        if age is None:
            idc = str(prof.get("id_card") or "").strip()
            if len(idc) == 18 and idc[6:10].isdigit():
                try:
                    age = date.today().year - int(idc[6:10])
                except Exception:
                    pass
        if age is not None and (age < 12 or age > 95):
            age = None

        # Resolve Gender
        raw_g = str(prof.get("gender") or "").strip().lower()
        if raw_g in ("female", "女", "f", "2", "woman"):
            gender = "female"
            gender_label = "女"
        elif raw_g in ("male", "男", "m", "1", "man"):
            gender = "male"
            gender_label = "男"
        else:
            gender = "unknown"
            gender_label = ""

        if age is not None:
            if age >= 55:
                age_group_label = "55+长青大师"
            elif age >= 50:
                age_group_label = "50+资深大师"
            elif age >= 40:
                age_group_label = "40+大师组"
            else:
                age_group_label = "青壮年组"
        else:
            age_group_label = ""

        return {
            "verified_mp_sec": verified_mp_sec,
            "verified_hp_sec": verified_hp_sec,
            "verified_10k_sec": verified_10k_sec,
            "verified_5k_sec": verified_5k_sec,
            "best_fm_sec": best_fm_sec,
            "best_hm_sec": best_hm_sec,
            "best_10k_sec": best_10k_sec,
            "best_5k_sec": best_5k_sec,
            "peak_vdot": peak_vdot,
            "peak_endurance_vdot": peak_endurance_vdot,
            "marathon_pb": LocalStore._format_duration_hms(verified_mp_sec),
            "half_pb": LocalStore._format_duration_hms(verified_hp_sec),
            "ten_k_pb": LocalStore._format_duration_hms(verified_10k_sec),
            "age": age,
            "age_group_label": age_group_label,
            "gender": gender,
            "gender_label": gender_label,
        }

    @staticmethod
    def recommend_athlete_template_group(
        marathon_pb: Optional[Any] = None,
        half_pb: Optional[Any] = None,
        ctl: float = 0.0,
        weekly_target: float = 45.0,
        status_level: str = "optimal",
        has_injury_or_hrv_alert: bool = False,
        ten_k_pb: Optional[Any] = None,
        recent_fm_sec: Optional[Any] = None,
        vo2max: Optional[float] = None,
        month_km: Optional[float] = None,
        km_7d: Optional[float] = None,
        age: Optional[int] = None,
        gender: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Recommends a conservative, scientifically grounded pace & intensity template group (240组/A/B/C/D/E)
        incorporating:
        1. Dual-Gate Verification (Verified Speed/PB capability AND current aerobic load CTL/month_km),
        2. Age Protection (Masters 45-49, Senior Masters 50-54, Grand Masters 55+ recovery & tendon safety),
        3. Gender Physiological & Absolute-Pace Calibration (preventing female runners from being pushed
           into overly aggressive male-pace/volume groups, plus recommended volume scaling).
        """
        mp_sec = LocalStore._parse_duration_sec(marathon_pb)
        hp_sec = LocalStore._parse_duration_sec(half_pb)
        tk_sec = LocalStore._parse_duration_sec(ten_k_pb)
        rec_fm = LocalStore._parse_duration_sec(recent_fm_sec)
        vo2 = float(vo2max) if vo2max is not None else None

        raw_g = str(gender or "").strip().lower()
        is_female = raw_g in ("female", "女", "f", "2")
        is_male = raw_g in ("male", "男", "m", "1")
        g_label = "女" if is_female else ("男" if is_male else "")
        demo_parts = []
        if g_label:
            demo_parts.append(g_label)
        if age is not None and 12 <= int(age) <= 95:
            age_val = int(age)
            demo_parts.append(f"{age_val}岁")
        else:
            age_val = None
        demo_prefix = f"{'·'.join(demo_parts)} | " if demo_parts else ""

        if has_injury_or_hrv_alert or status_level == "danger":
            return {
                "template_id": "group_e_taper",
                "group_code": "E组",
                "group_name": "🧘 E组 · 减量恢复",
                "recommended_scale": 0.8,
                "demographic_tag": "·".join(demo_parts),
                "reason": f"{demo_prefix}近期存在伤痛上报或TSB/HRV深度疲劳预警，优先分配E组减量恢复周模版(80%负荷)"
            }

        # Effective marathon time (if recent FM is much slower than old historical PB, blend/prefer current fitness)
        eff_mp_sec = mp_sec
        if mp_sec and rec_fm and rec_fm > mp_sec + 1200:
            # Historical PB is >20 min faster than recent marathon; avoid grouping by outdated peak
            eff_mp_sec = int(round(mp_sec * 0.35 + rec_fm * 0.65))
        elif mp_sec and vo2 is not None and vo2 <= 49.0 and mp_sec < 12000:
            # Historical sub-3:20 PB but current watch VO2max <= 49 indicates current fitness is closer to 3:40-3:55
            eff_mp_sec = max(mp_sec, 13200)

        # Step 1: Determine Verified Speed/Ability Tier (0=D组, 1=C组, 2=B组, 3=A组, 4=240组)
        has_any_speed_metric = any(x is not None for x in (eff_mp_sec, hp_sec, tk_sec, vo2))
        ability_notes = []
        if eff_mp_sec:
            ability_notes.append(f"全马{LocalStore._format_duration_hms(mp_sec)}")
        if hp_sec:
            ability_notes.append(f"半马{LocalStore._format_duration_hms(hp_sec)}")
        elif tk_sec:
            ability_notes.append(f"10K {LocalStore._format_duration_hms(tk_sec)}")
        if vo2:
            ability_notes.append(f"VO2max {int(round(vo2))}")

        if has_any_speed_metric:
            # Tier 4 (240组): Verified FM <= 2:45:00 (9900s) OR (HM <= 1:16:30 [4590s] AND 10K <= 34:30 [2070s])
            if (eff_mp_sec and 7200 < eff_mp_sec <= 9900) or (hp_sec and 3600 < hp_sec <= 4590 and (tk_sec is None or tk_sec <= 2070)):
                speed_tier = 4
            # Tier 3 (A组·破三): Verified FM <= 3:04:00 (11040s) OR (HM <= 1:26:30 [5190s] AND (eff_mp_sec is None or eff_mp_sec <= 11400))
            elif (eff_mp_sec and 7200 < eff_mp_sec <= 11040) or (hp_sec and 3600 < hp_sec <= 5190 and (eff_mp_sec is None or eff_mp_sec <= 11400)):
                speed_tier = 3
            # Tier 2 (B组·破330): Verified FM <= 3:32:00 (12720s) OR HM <= 1:39:30 (5970s) OR (10K <= 43:30 [2610s] AND (vo2 or 0) >= 54)
            elif (
                (eff_mp_sec and 7200 < eff_mp_sec <= 12720)
                or (hp_sec and 3600 < hp_sec <= 5970)
                or (tk_sec and 1800 < tk_sec <= 2610 and (vo2 or 0) >= 54)
            ):
                speed_tier = 2
            # Tier 1 (C组·破四): Verified FM <= 4:05:00 (14700s) OR HM <= 2:00:00 (7200s) OR (10K <= 52:00 [3120s] AND ((vo2 or 0) >= 44 or ctl >= 40))
            elif (
                (eff_mp_sec and 7200 < eff_mp_sec <= 14700)
                or (hp_sec and 3600 < hp_sec <= 7200)
                or (tk_sec and 1800 < tk_sec <= 3120 and ((vo2 or 0) >= 44 or ctl >= 40))
            ):
                speed_tier = 1
            else:
                speed_tier = 0
        else:
            # No verified PB/activity speed metric: never aggressively push into 240组/A组!
            # Only if caller explicitly passed high CTL & no month_km context (e.g. unit test), cap at B/C/D
            if month_km is None and ctl >= 70 and weekly_target >= 65:
                speed_tier = 2
            elif ctl >= 45 and (month_km is None or month_km >= 120):
                speed_tier = 1
            else:
                speed_tier = 0

        # Step 2: Current Aerobic Load Gate (prevent injury when recent mileage/CTL is low)
        # When month_km is known (real club cockpit), enforce strict recent training load verification
        if month_km is not None:
            if ctl < 22.0 or (month_km < 65.0 and (km_7d or 0.0) < 18.0):
                load_tier = 0
            elif ctl < 44.0 or (month_km < 115.0 and (km_7d or 0.0) < 28.0):
                # Allow a verified Sub-3 runner (speed_tier >= 3) with moderate CTL (35-44) to step down 1 tier to B组 instead of C组
                load_tier = 2 if (speed_tier >= 3 and ctl >= 35.0 and month_km >= 100.0) else 1
            elif ctl < 64.0 or (month_km < 150.0 and (km_7d or 0.0) < 38.0):
                load_tier = 2
            elif ctl < 88.0 or month_km < 220.0:
                load_tier = 3
            else:
                load_tier = 4
        else:
            # Standalone call without month_km: still require CTL or realistic weekly_target support
            if ctl > 0:
                if ctl < 22.0:
                    load_tier = 0
                elif ctl < 42.0:
                    load_tier = 1
                elif ctl < 62.0:
                    load_tier = 2
                elif ctl < 88.0:
                    load_tier = 3
                else:
                    load_tier = 4
            else:
                load_tier = speed_tier if speed_tier <= 2 else 2

        final_tier = min(speed_tier, load_tier)
        recommended_scale = 1.0
        adjustment_reasons = []

        if final_tier < speed_tier:
            adjustment_reasons.append(f"近期有氧负荷偏温和(CTL {ctl:.1f}{f'·月跑{int(round(month_km))}km' if month_km is not None else ''})，防伤降档过渡")

        # Step 3: Gender Physiological & Absolute-Pace Calibration
        if is_female:
            # Standard A组 intervals (3'42"/km) & 76km/wk volume are calibrated to male Sub-2:55 absolute pace.
            # Female runners with 3:03-3:28 PB are elite women, but in absolute training pace they fit B组 (or A组 only if <=3:00 & CTL>=72 & age<48)
            if final_tier >= 3:
                if not (eff_mp_sec and eff_mp_sec <= 10800 and ctl >= 72.0 and (age_val or 35) < 48):
                    final_tier = 2
                    recommended_scale = min(recommended_scale, 0.9)
                    adjustment_reasons.append("兼顾女性生理绝对配速区间与高强恢复负荷，稳健调配至B组")
            elif final_tier == 2:
                # For female B组, require verified FM <= 3:30 or HM <= 1:39:30 and CTL >= 48
                if not (((eff_mp_sec and eff_mp_sec <= 12600) or (hp_sec and hp_sec <= 5970)) and (ctl >= 48.0 or (month_km is None and weekly_target >= 55))):
                    final_tier = 1
                    adjustment_reasons.append("结合女性有氧进阶节奏，避免越级拉伤，稳健推荐C组")
                else:
                    recommended_scale = min(recommended_scale, 0.9)

            if age_val and age_val >= 42 and final_tier >= 1:
                recommended_scale = min(recommended_scale, 0.9)

        # Step 4: Age-Based Masters Recovery & Tendon Safety Calibration
        if age_val is not None:
            if age_val >= 55:
                # 55+ Grand Masters (长青大师组): never push into 240组/A组; if VO2max < 53 or recent pace > 3:30, cap at C组
                if final_tier >= 2:
                    if (vo2 is not None and vo2 < 53.0) or (rec_fm and rec_fm > 12600) or (hp_sec and hp_sec > 5760):
                        final_tier = 1
                        adjustment_reasons.append(f"兼顾{age_val}岁长青大师组跟腱/心肺恢复安全，降档至C组")
                    else:
                        final_tier = min(final_tier, 2)
                        adjustment_reasons.append(f"考虑{age_val}岁长青大师组恢复周期，控制高强间歇上限")
                recommended_scale = min(recommended_scale, 0.85 if final_tier >= 2 else 0.9)
            elif age_val >= 50:
                # 50-54 Senior Masters (资深大师组): cap at B组 unless active Sub-2:52 + CTL >= 85
                if final_tier >= 3 and not (eff_mp_sec and eff_mp_sec <= 10320 and ctl >= 85.0):
                    final_tier = 2
                    adjustment_reasons.append(f"考虑{age_val}岁资深大师组恢复周期与防伤要求，稳健降档至B组")
                recommended_scale = min(recommended_scale, 0.9)
            elif age_val >= 45:
                # 45-49 Masters (大师组): conservative volume scaling on high-intensity groups
                if final_tier >= 3 and ctl < 70.0:
                    final_tier = 2
                    adjustment_reasons.append(f"兼顾{age_val}岁大师组恢复节奏与当前CTL({ctl:.1f})，稳健推荐B组")
                if final_tier >= 2:
                    recommended_scale = min(recommended_scale, 0.9)

        # Step 5: Build Group Output & Coach-Readable Rationale
        scale_note = f"(建议{int(round(recommended_scale * 100))}%跑量系数)" if recommended_scale < 1.0 else ""
        ability_str = "·".join(ability_notes) if ability_notes else "暂无验证PB"
        load_str = f"CTL {ctl:.1f}" + (f"·月跑{int(round(month_km))}km" if month_km is not None else f"·周目标{int(weekly_target)}km")
        adj_str = f"；{'，'.join(adjustment_reasons)}" if adjustment_reasons else ""

        tier_map = {
            4: ("group_s_sub240", "240组", "👑 240组 · 全马240精英", f"{demo_prefix}顶尖专项能力({ability_str})且负荷充沛({load_str}){adj_str}，匹配240组{scale_note}"),
            3: ("group_a_sub300", "A组", "🔥 A组 · 破三/310", f"{demo_prefix}破三专项能力({ability_str})与体能储备扎实({load_str}){adj_str}，匹配A组{scale_note}"),
            2: ("group_b_sub330", "B组", "⚡ B组 · 破330", f"{demo_prefix}能力与负荷均衡({ability_str} | {load_str}){adj_str}，稳健匹配B组{scale_note}"),
            1: ("group_c_sub400", "C组", "🛡️ C组 · 破四/345", f"{demo_prefix}有氧耐力稳健({ability_str} | {load_str}){adj_str}，匹配C组破四模版{scale_note}"),
            0: ("group_d_base", "D组", "🌱 D组 · 完赛筑基", f"{demo_prefix}当前处于有氧筑基阶段({ability_str} | {load_str}){adj_str}，遵循防伤原则推荐D组{scale_note}"),
        }
        tpl_id, g_code, g_name, reason_text = tier_map.get(final_tier, tier_map[0])
        return {
            "template_id": tpl_id,
            "group_code": g_code,
            "group_name": g_name,
            "recommended_scale": recommended_scale,
            "demographic_tag": "·".join(demo_parts),
            "reason": reason_text,
        }

    @staticmethod
    def assign_template_to_athletes(
        template_id: str,
        user_ids: List[str],
        operator_uid: str,
        club_id: Optional[str] = None,
        apply_mode: str = "full_plan",
        target_week_index: Optional[int] = None,
        weeks_count: int = 4,
        volume_scale: float = 1.0,
        as_draft: bool = True,
        custom_days: Optional[List[Dict[str, Any]]] = None,
        custom_weeks: Optional[List[Dict[str, Any]]] = None,
        custom_title: Optional[str] = None,
        coach_review_note: Optional[str] = None,
        macro_roadmap: Optional[str] = None,
        preview_only: bool = False,
        base_plan: Optional[Dict[str, Any]] = None,
        canova_progression: bool = True,
    ) -> Dict[str, Any]:
        """
        Assigns a pace & intensity group template (built-in or coach-private custom template) to one or multiple athletes.
        - canova_progression=True (default): every week follows a Renato Canova funnel stage
          (基础适应 → 有氧延伸 → 模版基准 → 波浪减量 → 专项交替 → 专项高峰 → 减量锐化 → 周期检验),
          so Tue/Wed/Thu/Sat/Sun sessions change week by week instead of repeating the template verbatim.
          The "模版基准周" keeps the template (or coach-edited) days exactly as designed.
        - apply_mode == 'full_plan': Creates/updates a 4-week progressive plan for each athlete
          (as_draft=True allows coach to fine-tune each runner individually before publishing;
           as_draft=False publishes directly).
        - apply_mode == 'single_week': Replaces only target_week_index (or current week) in each athlete's existing plan,
          falling back to creating a full plan if the athlete has no plan yet.
        """
        templates = LocalStore.get_coach_training_templates(club_id=club_id, operator_uid=operator_uid)
        tpl = next((t for t in templates if t["id"] == template_id), None)
        if not tpl:
            tpl = templates[1]  # Default to Group B

        base_days = custom_days if (custom_days and len(custom_days) == 7) else tpl["days_template"]
        eff_scale = max(0.5, min(1.5, float(volume_scale or 1.0)))
        eff_roadmap = (macro_roadmap if macro_roadmap is not None else tpl.get("macro_roadmap")) or ""
        eff_coach_note = (coach_review_note if coach_review_note is not None else tpl.get("coach_review_note")) or ""

        today = date.today()
        start_monday = today - timedelta(days=today.weekday())
        days_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        from utils.canova_template_progression import (
            build_template_week_day,
            canova_stage_sequence,
            stage_outline,
            stage_week_meta,
        )

        is_taper_tpl = tpl["id"] == "group_e_taper" or "taper" in str(tpl.get("category") or "")

        def _build_week_from_template(
            w_idx: int,
            w_monday: date,
            wk_mult: float,
            phase_name: str,
            theme_suffix: str,
            stage_idx: Optional[int] = None,
            stage_rnd: int = 0,
            key_focus: Optional[str] = None,
        ) -> Dict[str, Any]:
            """
            Builds one plan week from the 7-day template.
            When `stage_idx` is given (Canova progression enabled), each training day's title,
            structure, pace and description evolve according to the Canova funnel stage instead
            of repeating the template week verbatim.
            """
            w_days = []
            for d_i in range(7):
                src_d = base_days[d_i] if d_i < len(base_days) else {}
                w_type = src_d.get("workout_type") or "easy_run"
                raw_km = float(src_d.get("distance_km") or 0.0)
                if w_type in ("rest", "travel") or raw_km <= 0:
                    dist_km = 0.0
                else:
                    dist_km = round(max(2.0, raw_km * eff_scale * wk_mult * 2.0) / 2.0, 1)
                    if w_type == "long_run":
                        dist_km = min(dist_km, 38.0)
                variant = None
                if stage_idx is not None:
                    try:
                        variant = build_template_week_day(
                            tpl=tpl,
                            src_d=src_d,
                            d_i=d_i,
                            base_days=base_days,
                            stage_idx=stage_idx,
                            rnd=stage_rnd,
                            dist_km=dist_km,
                        )
                    except Exception as e:
                        logger.warning(f"Canova template variant failed (tpl={tpl.get('id')}, day={d_i}): {e}")
                        variant = None
                cur_d_str = (w_monday + timedelta(days=d_i)).isoformat()
                w_days.append({
                    "day_index": d_i + 1,
                    "day_of_week": days_labels[d_i],
                    "date": cur_d_str,
                    "workout_type": w_type,
                    "title": (variant or {}).get("title") or src_d.get("title") or ("休息日" if dist_km == 0 else "训练课"),
                    "distance_km": dist_km,
                    "duration_minutes": int(round(dist_km * 6)),
                    "target_pace": (variant or {}).get("target_pace") or src_d.get("target_pace") or ("—" if dist_km == 0 else tpl["pace_zones"]["easy"]),
                    "target_hr_zone": (variant or {}).get("target_hr_zone") or src_d.get("target_hr_zone") or ("Zone 1" if dist_km == 0 else "Zone 2"),
                    "description": (variant or {}).get("description") or src_d.get("description") or "",
                    "completed": False,
                    "coach_notes": ""
                })
            tot_km = round(sum(d["distance_km"] for d in w_days), 1)
            week_obj = {
                "week_index": w_idx,
                "week_title": f"第 {w_idx} 周 · {tpl['group_code']}{theme_suffix}",
                "theme": f"{tpl['group_code']}{theme_suffix}",
                "phase": phase_name,
                "weekly_mileage_km": tot_km,
                "total_distance_km": tot_km,
                "planned_Actual_km": tot_km,
                "key_focus": key_focus or eff_coach_note,
                "days": w_days
            }
            if stage_idx is not None:
                week_obj["canova_stage"] = stage_idx
            return week_obj

        def _build_canova_week(w_idx: int, w_monday: date, total_weeks: int) -> Dict[str, Any]:
            if is_taper_tpl:
                st, rnd = (w_idx - 1) % 4, 0
            else:
                seq = canova_stage_sequence(total_weeks)
                st, rnd = seq[min(max(w_idx, 1), len(seq)) - 1]
            meta = stage_week_meta(st, rnd, is_taper=is_taper_tpl)
            return _build_week_from_template(
                w_idx=w_idx,
                w_monday=w_monday,
                wk_mult=meta["mult"],
                phase_name=meta["phase"],
                theme_suffix=f" · {meta['theme']}",
                stage_idx=st,
                stage_rnd=rnd,
                key_focus=f"【{meta['theme']}】{meta['focus']}",
            )

        batch_id = f"batch_tpl_{int(datetime.utcnow().timestamp()*1000)}" if not preview_only else None
        assigned_results = []
        for raw_uid in (user_ids or []):
            uid = LocalStore.resolve_user_id(raw_uid)
            profile = LocalStore.get_profile(uid) or {}
            runner_name = profile.get("display_name") or uid

            existing_draft = LocalStore.get_user_draft_training_plan(uid, reconcile=False)
            existing_active = LocalStore.get_user_active_training_plan(uid, reconcile=False)
            target_plan = copy.deepcopy(base_plan) if isinstance(base_plan, dict) else (
                (existing_draft or existing_active) if as_draft else (existing_active or existing_draft)
            )

            if apply_mode == "single_week" and target_plan and target_plan.get("schedule_data"):
                sched = copy.deepcopy(target_plan["schedule_data"])
                weeks = sched.get("weeks") or []
                w_idx_to_replace = int(target_week_index or target_plan.get("current_week_index") or 1)
                found_w = False
                for i, w in enumerate(weeks):
                    if int(w.get("week_index") or (i + 1)) == w_idx_to_replace:
                        # Determine Monday date of that week
                        existing_days = w.get("days") or []
                        try:
                            w_mon = datetime.strptime(str(existing_days[0].get("date"))[:10], "%Y-%m-%d").date()
                        except Exception:
                            w_mon = start_monday + timedelta(weeks=i)
                        if canova_progression:
                            new_w = _build_canova_week(w_idx_to_replace, w_mon, max(len(weeks), w_idx_to_replace))
                        else:
                            new_w = _build_week_from_template(
                                w_idx=w_idx_to_replace,
                                w_monday=w_mon,
                                wk_mult=1.0,
                                phase_name=f"{tpl['group_code']}模版课表",
                                theme_suffix=f"配速模版 ({tpl['target_level'].split('·')[0].strip()})"
                            )
                        # Preserve any existing athlete self-reports/biometrics on that week
                        for d_i in range(min(len(existing_days), len(new_w["days"]))):
                            old_d = existing_days[d_i]
                            for keep_k in ("completed", "actual_distance_km", "actual_execution_text", "rpe", "athlete_notes", "hrv", "resting_hr", "respiratory_rate", "strain_score", "recovery_pct", "strength_completed"):
                                if old_d.get(keep_k) is not None:
                                    new_w["days"][d_i][keep_k] = old_d[keep_k]
                        weeks[i] = new_w
                        found_w = True
                        break
                if not found_w:
                    w_mon = start_monday + timedelta(weeks=len(weeks))
                    if canova_progression:
                        new_w = _build_canova_week(w_idx_to_replace, w_mon, max(len(weeks) + 1, w_idx_to_replace))
                    else:
                        new_w = _build_week_from_template(
                            w_idx=w_idx_to_replace,
                            w_monday=w_mon,
                            wk_mult=1.0,
                            phase_name=f"{tpl['group_code']}模版课表",
                            theme_suffix=f"配速模版 ({tpl['target_level'].split('·')[0].strip()})"
                        )
                    weeks.append(new_w)

                sched["weeks"] = weeks
                sched["template_id"] = tpl["id"]
                sched["template_group_code"] = tpl["group_code"]
                sched["template_name"] = tpl["short_name"]
                if eff_roadmap:
                    sched["macro_roadmap"] = eff_roadmap

                if preview_only:
                    preview_plan = copy.deepcopy(target_plan)
                    preview_plan["schedule_data"] = sched
                    if eff_coach_note:
                        preview_plan["coach_review_note"] = eff_coach_note
                    preview_plan["is_preview"] = True
                    preview_plan = LocalStore.reconcile_training_plan_activities(preview_plan, uid)
                    updated_plan = LocalStore._enrich_plan_with_current_week(preview_plan)
                elif as_draft:
                    # Never overwrite the athlete's active plan in-place when saving as draft!
                    draft_id = (
                        existing_draft["id"]
                        if existing_draft and existing_draft.get("id")
                        else f"plan_draft_{int(datetime.utcnow().timestamp()*1000)}_{uuid.uuid4().hex[:4]}"
                    )
                    draft_payload = {
                        **copy.deepcopy(target_plan),
                        "id": draft_id,
                        "user_id": uid,
                        "club_id": club_id or target_plan.get("club_id"),
                        "status": "draft",
                        "review_status": "draft",
                        "coach_review_note": eff_coach_note or target_plan.get("coach_review_note"),
                        "schedule_data": sched,
                        "last_modified_by": operator_uid,
                    }
                    updated_plan = LocalStore.upsert_training_plan(draft_payload, skip_backup=True)
                    try:
                        LocalStore.record_plan_backup(
                            user_id=uid,
                            action_type="assign_template_draft",
                            action_label=f"模版草案（单周）：{tpl['short_name']}",
                            operator_uid=operator_uid,
                            club_id=club_id,
                            batch_id=batch_id,
                            previous_active_plan=existing_active,
                            created_plan_id=draft_id,
                            created_status="draft",
                        )
                    except Exception as be:
                        logger.warning(f"Failed to record template draft backup: {be}")
                else:
                    try:
                        LocalStore.record_plan_backup(
                            user_id=uid,
                            action_type="assign_template_publish",
                            action_label=f"模版派发（单周）：{tpl['short_name']}",
                            operator_uid=operator_uid,
                            club_id=club_id,
                            batch_id=batch_id,
                            previous_active_plan=existing_active,
                            created_plan_id=target_plan["id"],
                            created_status="active",
                        )
                    except Exception as be:
                        logger.warning(f"Failed to record template publish backup: {be}")
                    now_iso = datetime.utcnow().isoformat() + "Z"
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE training_plans
                            SET schedule_data = ?, coach_review_note = COALESCE(?, coach_review_note), updated_at = ?
                            WHERE id = ?
                        """, (json.dumps(sched, ensure_ascii=False), eff_coach_note, now_iso, target_plan["id"]))
                        conn.commit()
                    updated_plan = LocalStore.get_training_plan(target_plan["id"], reconcile=True)
                assigned_results.append({
                    "user_id": uid,
                    "display_name": runner_name,
                    "plan_id": updated_plan.get("id") if updated_plan else target_plan.get("id"),
                    "status": "draft" if as_draft else (updated_plan.get("status") if updated_plan else "active"),
                    "template_group_code": tpl["group_code"],
                    "plan": updated_plan
                })
                continue

            # Full multi-week plan generation from template
            eff_weeks_cnt = max(1, min(12, int(weeks_count or 4)))
            week_progressions = [
                (1.00, "基础适应周", "模版基准周"),
                (1.05, "专项强化周", "容量巩固周"),
                (1.10, "负荷高峰周", "混氧突破周"),
                (0.82, "减量吸收周", "超量恢复周"),
            ]
            built_weeks = []
            if custom_weeks and isinstance(custom_weeks, list) and len(custom_weeks) > 0:
                eff_weeks_cnt = max(1, min(12, len(custom_weeks)))
                for w_i, cw in enumerate(custom_weeks[:12]):
                    w_mon = start_monday + timedelta(weeks=w_i)
                    src_days = cw.get("days") or []
                    norm_days = []
                    for d_i in range(7):
                        sd = src_days[d_i] if d_i < len(src_days) else {}
                        w_t = sd.get("workout_type") or "easy_run"
                        dk = 0.0 if w_t in ("rest", "travel") else round(max(0.0, float(sd.get("distance_km") or 0.0)), 1)
                        cur_d_str = (w_mon + timedelta(days=d_i)).isoformat()
                        norm_days.append({
                            "day_index": d_i + 1,
                            "day_of_week": days_labels[d_i],
                            "date": cur_d_str,
                            "workout_type": w_t,
                            "title": sd.get("title") or ("休息日" if dk == 0 else "训练课"),
                            "distance_km": dk,
                            "duration_minutes": int(round(dk * 6)),
                            "target_pace": sd.get("target_pace") or ("—" if dk == 0 else tpl["pace_zones"]["easy"]),
                            "target_hr_zone": sd.get("target_hr_zone") or ("Zone 1" if dk == 0 else "Zone 2"),
                            "description": sd.get("description") or "",
                            "completed": False,
                            "coach_notes": sd.get("coach_notes") or "",
                        })
                    tot_km = round(sum(d["distance_km"] for d in norm_days), 1)
                    built_weeks.append({
                        "week_index": w_i + 1,
                        "week_title": cw.get("week_title") or f"第 {w_i + 1} 周 · {cw.get('theme') or tpl['group_code']}",
                        "theme": cw.get("theme") or f"{tpl['group_code']} · 第{w_i + 1}周",
                        "phase": cw.get("phase") or "周期训练",
                        "weekly_mileage_km": tot_km,
                        "total_distance_km": tot_km,
                        "planned_Actual_km": tot_km,
                        "key_focus": cw.get("key_focus") or eff_coach_note,
                        "days": norm_days,
                    })
            else:
                for w_i in range(eff_weeks_cnt):
                    if canova_progression:
                        built_weeks.append(
                            _build_canova_week(w_i + 1, start_monday + timedelta(weeks=w_i), eff_weeks_cnt)
                        )
                        continue
                    mult, ph_name, th_suf = week_progressions[w_i % len(week_progressions)]
                    if tpl["id"] == "group_e_taper":
                        mult = 1.0
                        ph_name = "减量排酸恢复期"
                        th_suf = "减量恢复周"
                    w_mon = start_monday + timedelta(weeks=w_i)
                    built_weeks.append(
                        _build_week_from_template(
                            w_idx=w_i + 1,
                            w_monday=w_mon,
                            wk_mult=mult,
                            phase_name=ph_name,
                            theme_suffix=th_suf
                        )
                    )

            plan_title = custom_title or f"{runner_name} · 【{tpl['group_code']}】{tpl['name'].split('·')[-1].strip()}"
            overview_str = (
                f"基于跑团【{tpl['short_name']}】标准模版分配（适配：{tpl['target_level']}，基准周跑量 {round(tpl['weekly_km'] * eff_scale, 1)}km）。"
                f"教练可根据队员当周体能、HRV与个人时间安排对单日课表进行个别微调。"
            )
            plan_roadmap = eff_roadmap
            if canova_progression:
                outline_str = " → ".join(stage_outline(eff_weeks_cnt, is_taper=is_taper_tpl))
                overview_str += f"按 Canova 漏斗周期逐周递进：{outline_str}。"
                if macro_roadmap is None:
                    plan_roadmap = f"Canova {eff_weeks_cnt}周递进：{outline_str}"
            schedule_data = {
                "macro_cycle_name": plan_title,
                "goal_summary": overview_str,
                "macro_roadmap": plan_roadmap,
                "canova_progression": bool(canova_progression),
                "template_id": tpl["id"],
                "template_group_code": tpl["group_code"],
                "template_name": tpl["short_name"],
                "pace_zones": tpl["pace_zones"],
                "coach_review": {
                    "reviewed_by": operator_uid,
                    "coach_review_note": eff_coach_note,
                    "assigned_from_template": tpl["id"]
                },
                "weeks": built_weeks
            }

            plan_dict_payload = {
                "id": target_plan.get("id") if target_plan and target_plan.get("id") else f"preview_{int(datetime.utcnow().timestamp()*1000)}",
                "user_id": uid,
                "club_id": club_id,
                "title": plan_title,
                "goal_type": "race_prep",
                "target_race_name": tpl["short_name"],
                "target_date": (start_monday + timedelta(weeks=eff_weeks_cnt)).isoformat(),
                "weeks_count": eff_weeks_cnt,
                "days_per_week": tpl["days_per_week"],
                "start_date": start_monday.isoformat(),
                "end_date": (start_monday + timedelta(weeks=eff_weeks_cnt, days=-1)).isoformat(),
                "status": "draft" if as_draft else "active",
                "review_status": "draft" if as_draft else "published",
                "coach_review_note": eff_coach_note,
                "overview_summary": overview_str,
                "schedule_data": schedule_data,
                "creator_id": operator_uid,
                "last_modified_by": operator_uid,
            }
            if preview_only:
                plan_dict_payload["is_preview"] = True
                if uid == "__template_preview__":
                    saved_plan = LocalStore._enrich_plan_with_current_week(plan_dict_payload)
                else:
                    saved_plan = LocalStore.reconcile_training_plan_activities(plan_dict_payload, uid)
                    saved_plan = LocalStore._enrich_plan_with_current_week(saved_plan)
            else:
                plan_dict_payload.pop("id", None)
                saved_plan = LocalStore.upsert_training_plan(plan_dict_payload, skip_backup=True)
                try:
                    LocalStore.record_plan_backup(
                        user_id=uid,
                        action_type="assign_template_draft" if as_draft else "assign_template_publish",
                        action_label=f"模版{'草案' if as_draft else '派发'}：{tpl['short_name']}",
                        operator_uid=operator_uid,
                        club_id=club_id,
                        batch_id=batch_id,
                        previous_active_plan=existing_active,
                        created_plan_id=saved_plan.get("id") if saved_plan else None,
                        created_status="draft" if as_draft else "active",
                    )
                except Exception as be:
                    logger.warning(f"Failed to record template full-plan backup: {be}")
                if not as_draft and saved_plan and saved_plan.get("id"):
                    saved_plan = LocalStore.publish_training_plan(
                        plan_id=saved_plan["id"],
                        operator_uid=operator_uid,
                        coach_review_note=eff_coach_note,
                        title=plan_title,
                        overview_summary=overview_str
                    )
            assigned_results.append({
                "user_id": uid,
                "display_name": runner_name,
                "plan_id": saved_plan.get("id") if saved_plan else None,
                "status": "draft" if as_draft else "active",
                "template_group_code": tpl["group_code"],
                "plan": saved_plan
            })

        return {
            "batch_id": batch_id,
            "template_id": tpl["id"],
            "template_name": tpl["short_name"],
            "group_code": tpl["group_code"],
            "assigned_count": len(assigned_results),
            "as_draft": as_draft,
            "apply_mode": apply_mode,
            "preview_weeks": (assigned_results[0].get("plan", {}).get("schedule_data", {}).get("weeks", []) if assigned_results else []),
            "assigned_plans": assigned_results
        }

    @staticmethod
    def batch_assign_imported_weekly_schedule(
        club_id: Optional[str],
        operator_uid: str,
        plan_title: str,
        source_week_index: int = 1,
        target_monday: Optional[str] = None,
        coach_review_note: Optional[str] = None,
        as_draft: bool = False,
        save_as_templates: bool = False,
        group_assignments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Batch-assigns a multi-group weekly schedule imported from a coach screenshot/Excel table.
        - Preserves the coach's exact daily workouts (canova_progression=False).
        - Aligns the 7 days to `target_monday` (e.g., next Monday or the schedule's explicit Monday date).
        - Updates each assigned athlete's `club_memberships.training_group` so their group is remembered for future weeks.
        - Optionally saves each group as a private coach custom template for future reuse.
        - Automatically records a snapshot in `training_plan_backups` with `batch_id` so the entire batch
          or any individual runner's plan can be rolled back in 1 click.
        - When `as_draft=True`, saves into a separate `status='draft'` record without modifying the athlete's `active` plan.
        """
        today = date.today()
        cur_mon = today - timedelta(days=today.weekday())
        next_mon = cur_mon + timedelta(days=7)
        w_monday = next_mon
        if target_monday:
            try:
                w_monday = datetime.strptime(str(target_monday)[:10], "%Y-%m-%d").date()
            except Exception:
                w_monday = next_mon

        w_sunday = w_monday + timedelta(days=6)
        days_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        eff_note = (coach_review_note or "").strip() or "请按所属分组配速执行，跑后及时完成体能练习与拉伸。"
        eff_title_base = (plan_title or "跑团周训练计划").strip()
        src_wk_num = max(1, int(source_week_index or 1))
        batch_id = f"batch_imp_{int(datetime.utcnow().timestamp()*1000)}"

        saved_templates = []
        assigned_results = []
        group_summary = []

        for grp in (group_assignments or []):
            g_code = (grp.get("group_code") or "标准组").strip()
            g_name = (grp.get("group_name") or g_code).strip()
            badge_color = grp.get("badge_color") or "amber"
            raw_days = grp.get("days") or []
            raw_uids = grp.get("user_ids") or []

            norm_days = []
            for d_i in range(7):
                sd = raw_days[d_i] if d_i < len(raw_days) else {}
                w_t = sd.get("workout_type") or "easy_run"
                dk = 0.0 if w_t in ("rest", "travel") else round(max(0.0, float(sd.get("distance_km") or 0.0)), 1)
                dur_m = 0 if dk == 0 else int(sd.get("duration_minutes") or round(dk * 5.5))
                cur_d_str = (w_monday + timedelta(days=d_i)).isoformat()
                norm_days.append({
                    "day_index": d_i + 1,
                    "day_of_week": days_labels[d_i],
                    "date": cur_d_str,
                    "workout_type": w_t,
                    "title": sd.get("title") or ("休息日" if dk == 0 else "训练课"),
                    "distance_km": dk,
                    "duration_minutes": dur_m,
                    "target_pace": sd.get("target_pace") or ("—" if dk == 0 else "配速自控"),
                    "target_hr_zone": sd.get("target_hr_zone") or ("Zone 1" if dk == 0 else "Zone 2"),
                    "description": sd.get("description") or "",
                    "completed": False,
                    "coach_notes": sd.get("coach_notes") or "",
                })

            tot_km = round(sum(d["distance_km"] for d in norm_days if d["workout_type"] not in ("rest", "travel")), 1)
            run_days_cnt = sum(1 for d in norm_days if d["workout_type"] not in ("rest", "travel") and d["distance_km"] > 0)

            if save_as_templates and operator_uid:
                try:
                    short_tpl_name = f"📋 {g_code} · {eff_title_base[:14]}"
                    tpl_saved = LocalStore.save_coach_custom_template(
                        operator_uid=operator_uid,
                        club_id=club_id,
                        group_code=g_code,
                        category="custom",
                        name=f"{eff_title_base} · {g_name}",
                        short_name=short_tpl_name,
                        badge_color=badge_color,
                        target_level=f"{g_name} · 周跑量 {tot_km}km",
                        intensity_tag=grp.get("pace_summary") or "按课表分组配速",
                        weekly_km=tot_km,
                        days_per_week=run_days_cnt,
                        pace_zones={
                            "easy": "配速自控",
                            "marathon": grp.get("pace_summary") or "按组别配速",
                            "tempo": next((d["target_pace"] for d in norm_days if d["workout_type"] == "tempo_run"), "—"),
                            "interval": next((d["target_pace"] for d in norm_days if d["workout_type"] == "interval"), "—"),
                            "long_run": next((d["target_pace"] for d in norm_days if d["workout_type"] == "long_run"), "—"),
                        },
                        macro_roadmap=f"导入自：{eff_title_base} ({w_monday.isoformat()} ~ {w_sunday.isoformat()})",
                        coach_review_note=eff_note,
                        days_template=norm_days,
                    )
                    saved_templates.append(tpl_saved)
                except Exception as te:
                    logger.warning(f"Failed to save imported group {g_code} as custom template: {te}")

            grp_assigned_cnt = 0
            for raw_u in raw_uids:
                uid = LocalStore.resolve_user_id(raw_u)
                if not uid:
                    continue
                if club_id:
                    try:
                        LocalStore.update_member_training_group(club_id, uid, g_code)
                    except Exception as ge:
                        logger.warning(f"Failed to update training_group for {uid}: {ge}")

                profile = LocalStore.get_profile(uid) or {}
                runner_name = profile.get("display_name") or uid

                existing_draft = LocalStore.get_user_draft_training_plan(uid, reconcile=False)
                existing_active = LocalStore.get_user_active_training_plan(uid, reconcile=False)
                base_source_plan = (existing_draft or existing_active) if as_draft else (existing_active or existing_draft)

                new_week_obj = {
                    "week_index": src_wk_num,
                    "week_title": f"第 {src_wk_num} 周 · {g_code} ({w_monday.strftime('%m/%d')}-{w_sunday.strftime('%m/%d')})",
                    "theme": f"{eff_title_base} · {g_code}",
                    "phase": f"教练周课表 · {g_code}",
                    "weekly_mileage_km": tot_km,
                    "total_distance_km": tot_km,
                    "planned_Actual_km": tot_km,
                    "key_focus": eff_note,
                    "days": copy.deepcopy(norm_days),
                }

                member_plan_title = f"{runner_name} · 【{g_code}】{eff_title_base}"
                overview_str = (
                    f"【{eff_title_base} · {g_code}】周跑量 {tot_km}km（{w_monday.isoformat()} 至 {w_sunday.isoformat()}）。"
                    f"助教/主教练已按组别统一导入派发，跑后请及时同步手表并打卡体能训练。"
                )

                if base_source_plan and isinstance(base_source_plan.get("schedule_data"), dict):
                    sched = copy.deepcopy(base_source_plan["schedule_data"])
                    weeks = list(sched.get("weeks") or [])
                    target_mon_iso = w_monday.isoformat()
                    replaced = False
                    for idx, w_item in enumerate(weeks):
                        w_days = w_item.get("days") or []
                        first_d = str(w_days[0].get("date") or "")[:10] if w_days else ""
                        if first_d == target_mon_iso:
                            for d_i in range(min(len(w_days), len(new_week_obj["days"]))):
                                old_d = w_days[d_i]
                                for keep_k in (
                                    "completed", "actual_distance_km", "actual_execution_text",
                                    "rpe", "athlete_notes", "hrv", "resting_hr", "respiratory_rate",
                                    "strain_score", "recovery_pct", "strength_completed", "workout_photos", "photo_url"
                                ):
                                    if old_d.get(keep_k) is not None:
                                        new_week_obj["days"][d_i][keep_k] = old_d[keep_k]
                            new_week_obj["week_index"] = w_item.get("week_index") or (idx + 1)
                            weeks[idx] = new_week_obj
                            replaced = True
                            break

                    if not replaced:
                        weeks.append(new_week_obj)
                        def _wk_sort_key(w_obj: Dict[str, Any]) -> str:
                            ds = w_obj.get("days") or []
                            return str(ds[0].get("date") or "9999-99-99")[:10] if ds else "9999-99-99"
                        weeks.sort(key=_wk_sort_key)
                        for idx, w_obj in enumerate(weeks):
                            w_obj["week_index"] = idx + 1

                    sched["weeks"] = weeks
                    sched["canova_progression"] = False
                    sched["template_id"] = f"imported_{g_code}"
                    sched["template_group_code"] = g_code
                    sched["template_name"] = f"{g_code} · {eff_title_base}"
                    sched["macro_cycle_name"] = member_plan_title
                    sched["goal_summary"] = overview_str

                    if as_draft:
                        # Strictly isolate draft from the athlete's active plan!
                        draft_id = (
                            existing_draft["id"]
                            if existing_draft and existing_draft.get("id")
                            else f"plan_draft_{int(datetime.utcnow().timestamp()*1000)}_{uuid.uuid4().hex[:4]}"
                        )
                        draft_payload = {
                            **copy.deepcopy(base_source_plan),
                            "id": draft_id,
                            "user_id": uid,
                            "club_id": club_id or base_source_plan.get("club_id"),
                            "title": member_plan_title,
                            "overview_summary": overview_str,
                            "coach_review_note": eff_note,
                            "weeks_count": len(weeks),
                            "days_per_week": run_days_cnt,
                            "status": "draft",
                            "review_status": "draft",
                            "schedule_data": sched,
                            "last_modified_by": operator_uid,
                        }
                        saved_plan = LocalStore.upsert_training_plan(draft_payload, skip_backup=True)
                        try:
                            LocalStore.record_plan_backup(
                                user_id=uid,
                                action_type="import_weekly_schedule_draft",
                                action_label=f"识图导入草案：{eff_title_base} ({g_code})",
                                operator_uid=operator_uid,
                                club_id=club_id,
                                batch_id=batch_id,
                                previous_active_plan=existing_active,
                                created_plan_id=draft_id,
                                created_status="draft",
                            )
                        except Exception as be:
                            logger.warning(f"Failed to record import draft backup: {be}")
                    else:
                        target_active_id = (existing_active or base_source_plan)["id"]
                        try:
                            LocalStore.record_plan_backup(
                                user_id=uid,
                                action_type="import_weekly_schedule_publish",
                                action_label=f"识图正式派发：{eff_title_base} ({g_code})",
                                operator_uid=operator_uid,
                                club_id=club_id,
                                batch_id=batch_id,
                                previous_active_plan=existing_active,
                                created_plan_id=target_active_id,
                                created_status="active",
                            )
                        except Exception as be:
                            logger.warning(f"Failed to record import publish backup: {be}")

                        now_iso = datetime.utcnow().isoformat() + "Z"
                        with sqlite3.connect(DB_PATH) as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                """
                                UPDATE training_plans
                                SET title = ?, overview_summary = ?, schedule_data = ?,
                                    coach_review_note = ?, weeks_count = ?, days_per_week = ?,
                                    last_modified_by = ?, updated_at = ?
                                WHERE id = ?
                                """,
                                (
                                    member_plan_title,
                                    overview_str,
                                    json.dumps(sched, ensure_ascii=False),
                                    eff_note,
                                    len(weeks),
                                    run_days_cnt,
                                    operator_uid,
                                    now_iso,
                                    target_active_id,
                                ),
                            )
                            # Archive any stale draft for this athlete so there is no ambiguity
                            cursor.execute(
                                """
                                UPDATE training_plans
                                SET status = 'archived', updated_at = ?
                                WHERE (user_id = ? OR user_id = ?) AND status = 'draft' AND id != ?
                                """,
                                (now_iso, uid, raw_u, target_active_id),
                            )
                            conn.commit()

                        saved_plan = LocalStore.publish_training_plan(
                            plan_id=target_active_id,
                            operator_uid=operator_uid,
                            coach_review_note=eff_note,
                            title=member_plan_title,
                            overview_summary=overview_str,
                        )
                else:
                    schedule_data = {
                        "macro_cycle_name": member_plan_title,
                        "goal_summary": overview_str,
                        "macro_roadmap": f"{eff_title_base} ({w_monday.isoformat()} ~ {w_sunday.isoformat()})",
                        "canova_progression": False,
                        "template_id": f"imported_{g_code}",
                        "template_group_code": g_code,
                        "template_name": f"{g_code} · {eff_title_base}",
                        "coach_review": {
                            "reviewed_by": operator_uid,
                            "coach_review_note": eff_note,
                        },
                        "weeks": [new_week_obj],
                    }
                    plan_payload = {
                        "user_id": uid,
                        "club_id": club_id,
                        "title": member_plan_title,
                        "goal_type": "race_prep",
                        "target_race_name": eff_title_base,
                        "target_date": w_sunday.isoformat(),
                        "weeks_count": 1,
                        "days_per_week": run_days_cnt,
                        "start_date": w_monday.isoformat(),
                        "end_date": w_sunday.isoformat(),
                        "status": "draft" if as_draft else "active",
                        "review_status": "draft" if as_draft else "published",
                        "coach_review_note": eff_note,
                        "overview_summary": overview_str,
                        "schedule_data": schedule_data,
                        "creator_id": operator_uid,
                        "last_modified_by": operator_uid,
                    }
                    saved_plan = LocalStore.upsert_training_plan(plan_payload, skip_backup=True)
                    try:
                        LocalStore.record_plan_backup(
                            user_id=uid,
                            action_type="import_weekly_schedule_draft" if as_draft else "import_weekly_schedule_publish",
                            action_label=f"识图{'导入草案' if as_draft else '正式派发'}：{eff_title_base} ({g_code})",
                            operator_uid=operator_uid,
                            club_id=club_id,
                            batch_id=batch_id,
                            previous_active_plan=existing_active,
                            created_plan_id=saved_plan.get("id") if saved_plan else None,
                            created_status="draft" if as_draft else "active",
                        )
                    except Exception as be:
                        logger.warning(f"Failed to record import new-plan backup: {be}")
                    if not as_draft and saved_plan and saved_plan.get("id"):
                        saved_plan = LocalStore.publish_training_plan(
                            plan_id=saved_plan["id"],
                            operator_uid=operator_uid,
                            coach_review_note=eff_note,
                            title=member_plan_title,
                            overview_summary=overview_str,
                        )

                grp_assigned_cnt += 1
                assigned_results.append({
                    "user_id": uid,
                    "display_name": runner_name,
                    "group_code": g_code,
                    "plan_id": saved_plan.get("id") if saved_plan else None,
                    "status": "draft" if as_draft else "active",
                    "weekly_km": tot_km,
                })

            group_summary.append({
                "group_code": g_code,
                "group_name": g_name,
                "weekly_km": tot_km,
                "assigned_count": grp_assigned_cnt,
            })

        return {
            "batch_id": batch_id,
            "plan_title": eff_title_base,
            "target_monday": w_monday.isoformat(),
            "target_sunday": w_sunday.isoformat(),
            "as_draft": as_draft,
            "total_assigned_count": len(assigned_results),
            "group_summary": group_summary,
            "assigned_plans": assigned_results,
            "saved_templates_count": len(saved_templates),
        }


    @staticmethod
    def delete_training_plan(plan_id: str) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM training_plans WHERE id = ?", (plan_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def extract_runner_race_history(user_id: str, days: int = 540) -> Dict[str, Any]:
        """
        Extracts real race performances, trials, and long runs from activities over the last 12-18 months (default 540 days).
        """
        canonical_uid = LocalStore.resolve_user_id(user_id)
        cutoff_date = (date.today() - timedelta(days=days)).isoformat()
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT id, name, sport_type, start_time, distance_meters, moving_time_seconds, 
                       elapsed_time_seconds, avg_pace_str, elevation_gain_meters, 
                       average_heartrate, max_heartrate, trimp
                FROM activities
                WHERE (user_id = ? OR user_id = ?) AND start_time >= ?
                  AND {RUNNING_SQL_FILTER}
                ORDER BY start_time DESC
            """, (canonical_uid, user_id, cutoff_date))
            rows = [dict(r) for r in cursor.fetchall()]

            cursor.execute("""
                SELECT id, name, race_type, race_date, target_time, priority
                FROM race_plans
                WHERE user_id = ? OR user_id = ?
                ORDER BY race_date DESC
            """, (canonical_uid, user_id))
            registered_races = [dict(r) for r in cursor.fetchall()]

        from utils.running_metrics import format_duration
        total_activities = len(rows)
        total_distance_km = round(sum(float(r["distance_meters"] or 0) for r in rows) / 1000.0, 1)

        long_runs = []
        max_dist_m = 0.0
        races_detected = []
        trail_runs = []

        race_keywords = ["马拉松", "半马", "全马", "越野", "比赛", "race", "marathon", "50k", "100k", "pb", "团赛", "选拔", "戈壁", "戈1", "戈2"]
        trail_keywords = ["越野", "trail", "山", "坡", "攀", "50k", "100k"]

        for r in rows:
            dist_m = float(r["distance_meters"] or 0)
            if dist_m > max_dist_m:
                max_dist_m = dist_m

            name_lower = (r["name"] or "").lower()
            elev = float(r["elevation_gain_meters"] or 0)

            # Long run classification (>=14.5km)
            if dist_m >= 14500:
                long_runs.append({
                    "date": str(r["start_time"])[:10],
                    "name": r["name"],
                    "distance_km": round(dist_m / 1000.0, 1),
                    "moving_time": format_duration(r["moving_time_seconds"]),
                    "avg_pace": r["avg_pace_str"],
                    "avg_hr": r["average_heartrate"],
                    "elevation_gain_m": round(elev, 1)
                })

            # Race or competitive test detection
            is_race = any(k in name_lower for k in race_keywords) or dist_m >= 40000 or (dist_m >= 20000 and "测" in name_lower)
            if is_race:
                races_detected.append({
                    "date": str(r["start_time"])[:10],
                    "name": r["name"],
                    "distance_km": round(dist_m / 1000.0, 1),
                    "moving_time": format_duration(r["moving_time_seconds"]),
                    "avg_pace": r["avg_pace_str"],
                    "avg_hr": r["average_heartrate"],
                    "elevation_gain_m": round(elev, 1)
                })

            # Trail / climbing run
            if any(k in name_lower for k in trail_keywords) or elev >= 200:
                trail_runs.append({
                    "date": str(r["start_time"])[:10],
                    "name": r["name"],
                    "distance_km": round(dist_m / 1000.0, 1),
                    "avg_pace": r["avg_pace_str"],
                    "avg_hr": r["average_heartrate"],
                    "elevation_gain_m": round(elev, 1)
                })

        return {
            "period_days": days,
            "total_activities_count": total_activities,
            "total_distance_km": total_distance_km,
            "max_single_distance_km": round(max_dist_m / 1000.0, 1),
            "long_runs_count": len(long_runs),
            "recent_races": races_detected[:10],
            "recent_long_runs": long_runs[:10],
            "trail_climbing_runs": trail_runs[:8],
            "registered_race_targets": registered_races
        }

    # ── Grand Community / Organization Hierarchy Methods ──

    @staticmethod
    def _normalize_field_rules(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        default_by_field = {d["field"]: copy.deepcopy(d) for d in DEFAULT_ORG_FIELD_RULES}
        normalized: List[Dict[str, Any]] = []
        seen_fields = set()
        for raw in (rules or []):
            if not isinstance(raw, dict):
                continue
            f_key = (raw.get("field") or raw.get("field_key") or "").strip()
            if not f_key:
                continue
            base = copy.deepcopy(default_by_field.get(f_key, {}))
            base.update(raw)
            base["field"] = f_key
            base["field_key"] = f_key

            raw_mode = str(raw.get("mode") or "").strip().lower()
            is_hidden = (
                raw_mode == "hidden"
                or raw.get("hidden") is True
                or raw.get("visible") is False
            )
            if is_hidden:
                base["mode"] = "hidden"
                base["hidden"] = True
                base["required"] = False
            elif bool(raw.get("required")) or (raw_mode == "required" and "required" not in raw):
                base["mode"] = "required"
                base["hidden"] = False
                base["required"] = True
            else:
                base["mode"] = "optional"
                base["hidden"] = False
                base["required"] = False

            normalized.append(base)
            seen_fields.add(f_key)

        for d in DEFAULT_ORG_FIELD_RULES:
            if d["field"] not in seen_fields:
                item = copy.deepcopy(d)
                item["field_key"] = item["field"]
                normalized.append(item)
        return normalized

    @staticmethod
    def is_org_organizer(org_id: str, operator_uid: Optional[str]) -> bool:
        if not operator_uid:
            return False
        op = operator_uid.strip()
        if op in ("admin", "super_admin"):
            return True
        canonical_uid = LocalStore.resolve_user_id(op)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT owner_id FROM organizations WHERE id = ?", (org_id,))
            org_row = cursor.fetchone()
            if not org_row:
                return False
            if org_row["owner_id"] in (op, canonical_uid):
                return True
            cursor.execute(
                "SELECT role FROM organization_members WHERE org_id = ? AND user_id IN (?, ?)",
                (org_id, op, canonical_uid),
            )
            mem_rows = cursor.fetchall()
            return any((r["role"] in ("owner", "admin")) for r in mem_rows)

    @staticmethod
    def get_org_field_rules(org_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT settings FROM organizations WHERE id = ?", (org_id,))
            row = cursor.fetchone()
            if not row:
                return LocalStore._normalize_field_rules(copy.deepcopy(DEFAULT_ORG_FIELD_RULES))
            settings_str = row["settings"]
            if settings_str:
                try:
                    s_dict = json.loads(settings_str)
                    if isinstance(s_dict, dict) and "field_rules" in s_dict and isinstance(s_dict["field_rules"], list):
                        return LocalStore._normalize_field_rules(s_dict["field_rules"])
                except Exception:
                    pass
            return LocalStore._normalize_field_rules(copy.deepcopy(DEFAULT_ORG_FIELD_RULES))

    @staticmethod
    def update_org_field_rules(org_id: str, field_rules: List[Dict[str, Any]], operator_uid: Optional[str] = None) -> List[Dict[str, Any]]:
        if operator_uid and not LocalStore.is_org_organizer(org_id, operator_uid):
            raise PermissionError("只有大群主理人、大群管理员或超级管理员有权修改大群准入字段规则！")
        normalized = LocalStore._normalize_field_rules(field_rules)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT settings FROM organizations WHERE id = ?", (org_id,))
            row = cursor.fetchone()
            if not row:
                return []
            s_dict = {}
            if row[0]:
                try:
                    s_dict = json.loads(row[0])
                except Exception:
                    s_dict = {}
            if not isinstance(s_dict, dict):
                s_dict = {}
            s_dict["field_rules"] = normalized
            cursor.execute("UPDATE organizations SET settings = ? WHERE id = ?", (json.dumps(s_dict, ensure_ascii=False), org_id))
            conn.commit()
            return normalized

    @staticmethod
    def is_field_missing(field_name: str, field_type: str, val: Any, extra_data: Optional[Dict[str, Any]] = None) -> bool:
        if val is None:
            return True
        s_val = str(val).strip()
        if not s_val:
            return True
        if field_name == "real_name" and s_val in ("跑者", "跑友", "微信用户", "未实名"):
            return True
        if field_name == "date_of_birth" and s_val in ("--", "0000-00-00"):
            return True
        if field_name == "class_name":
            if s_val in ("复旦戈友", "复旦商学院", "未设班级", "在读/毕业"):
                return True
        if field_name == "gobi_experience" and s_val in ("未登记", "未设置"):
            return True
        if field_type == "boolean" and not val:
            return True
        return False

    @staticmethod
    def check_org_member_status(org_id: str, user_id: str) -> Dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM organization_members WHERE org_id = ? AND user_id = ?", (org_id, user_id))
            row = cursor.fetchone()
            if not row:
                return {
                    "is_member": False,
                    "status": "none",
                    "is_valid": False,
                    "days_remaining": 0,
                    "missing_fields": []
                }

            member = dict(row)
            status = member.get("status") or "temporary"
            role = member.get("role") or "member"
            joined_at_str = member.get("joined_at")

            dec_name = decrypt_pii(member.get("real_name")) or ""
            dec_dob = decrypt_pii(member.get("date_of_birth")) or ""
            dec_phone = decrypt_pii(member.get("phone")) or ""
            dec_id_card = decrypt_pii(member.get("id_card")) or ""
            gender = member.get("gender") or ""
            class_name = member.get("class_name") or ""

            extra_data = {}
            if member.get("extra_data"):
                try:
                    extra_data = json.loads(member["extra_data"])
                except Exception:
                    extra_data = {}

            field_values = {
                "real_name": dec_name,
                "gender": gender,
                "date_of_birth": dec_dob,
                "class_name": class_name,
                "phone": dec_phone,
                "id_card": dec_id_card,
                **extra_data
            }

            rules = LocalStore.get_org_field_rules(org_id)
            missing_fields = []
            for r in rules:
                if r.get("required") and not r.get("hidden") and r.get("mode") != "hidden":
                    f = r["field"]
                    val = field_values.get(f)
                    f_type = r.get("type", "text")
                    if LocalStore.is_field_missing(f, f_type, val, extra_data):
                        missing_fields.append({"field": f, "label": r.get("label", f)})

            # ── If required fields are missing: status CANNOT be confirmed (even for owner/admin during onboarding/testing)! ──
            if len(missing_fields) > 0:
                joined_at_dt = None
                if joined_at_str:
                    joined_at_dt = parse_iso_datetime(joined_at_str)

                now_utc = datetime.now(timezone.utc)
                if joined_at_dt:
                    if joined_at_dt.tzinfo is None:
                        joined_at_dt = joined_at_dt.replace(tzinfo=timezone.utc)
                    elapsed_seconds = (now_utc - joined_at_dt).total_seconds()
                    elapsed_days = elapsed_seconds / 86400.0
                    remaining_days = max(0, math.ceil(14.0 - elapsed_days))
                    is_expired = elapsed_days >= 14.0
                else:
                    elapsed_days = 0
                    remaining_days = 14
                    is_expired = False

                target_status = "expired" if is_expired else "temporary"
                if status != target_status or member.get("confirmed_by") is not None:
                    cursor.execute("""
                        UPDATE organization_members 
                        SET status = ?, confirmed_at = NULL, confirmed_by = NULL 
                        WHERE org_id = ? AND user_id = ?
                    """, (target_status, org_id, user_id))
                    conn.commit()

                if target_status == "expired" and role not in ("owner", "admin"):
                    cursor.execute("""
                        DELETE FROM club_memberships
                        WHERE user_id = ?
                          AND role != 'owner'
                          AND club_id IN (SELECT id FROM clubs WHERE org_id = ?)
                    """, (user_id, org_id))
                    removed_n = cursor.rowcount or 0
                    conn.commit()
                    if status != "expired":
                        LocalStore._notify_org_member_expired(cursor, conn, org_id, user_id, removed_n, missing_fields)

                return {
                    "is_member": True,
                    "status": target_status,
                    "role": role,
                    "is_valid": (target_status != "expired"),
                    "days_remaining": remaining_days if target_status != "expired" else 0,
                    "deadline_at": LocalStore._org_profile_deadline_iso(joined_at_str),
                    "missing_fields": missing_fields
                }

            # ── All required fields are filled ──
            if role in ("owner", "admin"):
                if status != "confirmed":
                    cursor.execute("UPDATE organization_members SET status = 'confirmed' WHERE org_id = ? AND user_id = ?", (org_id, user_id))
                    conn.commit()
                    status = "confirmed"
                return {
                    "is_member": True,
                    "status": "confirmed",
                    "role": role,
                    "is_valid": True,
                    "days_remaining": None,
                    "missing_fields": []
                }

            # ── All required fields are filled ──
            if status == "confirmed" and member.get("confirmed_by"):
                return {
                    "is_member": True,
                    "status": "confirmed",
                    "role": role,
                    "is_valid": True,
                    "days_remaining": None,
                    "missing_fields": []
                }

            joined_at_dt = None
            if joined_at_str:
                joined_at_dt = parse_iso_datetime(joined_at_str)

            now_utc = datetime.now(timezone.utc)
            if joined_at_dt:
                if joined_at_dt.tzinfo is None:
                    joined_at_dt = joined_at_dt.replace(tzinfo=timezone.utc)
                elapsed_seconds = (now_utc - joined_at_dt).total_seconds()
                elapsed_days = elapsed_seconds / 86400.0
                remaining_days = max(0, math.ceil(14.0 - elapsed_days))
                is_expired = elapsed_days >= 14.0
            else:
                elapsed_days = 0
                remaining_days = 14
                is_expired = False

            if is_expired:
                if status != "expired":
                    cursor.execute("UPDATE organization_members SET status = 'expired' WHERE org_id = ? AND user_id = ?", (org_id, user_id))
                removed_n = 0
                if role not in ("owner", "admin"):
                    cursor.execute("""
                        DELETE FROM club_memberships
                        WHERE user_id = ?
                          AND role != 'owner'
                          AND club_id IN (SELECT id FROM clubs WHERE org_id = ?)
                    """, (user_id, org_id))
                    removed_n = cursor.rowcount or 0
                conn.commit()
                if status != "expired" and role not in ("owner", "admin"):
                    LocalStore._notify_org_member_expired(cursor, conn, org_id, user_id, removed_n, [])
                return {
                    "is_member": True,
                    "status": "expired",
                    "role": role,
                    "is_valid": False,
                    "days_remaining": 0,
                    "deadline_at": LocalStore._org_profile_deadline_iso(joined_at_str),
                    "missing_fields": []
                }

            if status != "pending":
                cursor.execute("UPDATE organization_members SET status = 'pending' WHERE org_id = ? AND user_id = ?", (org_id, user_id))
                conn.commit()

            return {
                "is_member": True,
                "status": "pending",
                "role": role,
                "is_valid": True,
                "days_remaining": remaining_days,
                "deadline_at": LocalStore._org_profile_deadline_iso(joined_at_str),
                "missing_fields": []
            }

    # ── 大群资料补填期限（默认 14 天）──
    ORG_PROFILE_DEADLINE_DAYS = 14

    @staticmethod
    def _org_profile_deadline_iso(joined_at_str: Optional[str]) -> Optional[str]:
        """Returns the ISO deadline (joined_at + 14 days) by which a member must complete & pass profile review."""
        if not joined_at_str:
            return None
        try:
            jdt = parse_iso_datetime(joined_at_str)
            if not jdt:
                return None
            if jdt.tzinfo is None:
                jdt = jdt.replace(tzinfo=timezone.utc)
            return (jdt + timedelta(days=LocalStore.ORG_PROFILE_DEADLINE_DAYS)).isoformat().replace("+00:00", "Z")
        except Exception:
            return None

    @staticmethod
    def _insert_notification_raw(cursor, user_id: str, title: str, content: str, notif_type: str, ref_id: Optional[str] = None):
        nid = f"notif_{notif_type}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT OR IGNORE INTO system_notifications
            (id, user_id, activity_id, title, content, type, wechat_sent, wechat_errmsg, is_read, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, NULL, 0, ?)
        """, (nid, user_id, ref_id, title, content, notif_type, get_beijing_iso()))

    @staticmethod
    def _notify_org_member_expired(cursor, conn, org_id: str, user_id: str, removed_count: int, missing_fields: List[Dict[str, Any]]):
        """Notifies a runner (once, on transition) that the profile deadline has passed and they were removed from all sub-clubs."""
        try:
            cursor.execute("SELECT name FROM organizations WHERE id = ?", (org_id,))
            r = cursor.fetchone()
            org_name = (r[0] if r else None) or "大群"
            missing_txt = "、".join([m.get("label", m.get("field", "")) for m in (missing_fields or [])][:6])
            reason = f"未补齐必填资料（{missing_txt}）" if missing_txt else "资料未在期限内通过管理员审核"
            content = (
                f"您加入【{org_name}】已超过 {LocalStore.ORG_PROFILE_DEADLINE_DAYS} 天，因{reason}，"
                f"已按群规自动移出【{org_name}】下属的全部跑团"
                + (f"（共 {removed_count} 个）" if removed_count else "")
                + "。补齐资料后可联系大群管理员恢复资格。"
            )
            LocalStore._insert_notification_raw(cursor, user_id, "⛔ 大群资料补填期限已到", content, "org_profile_expired", org_id)
            conn.commit()
        except Exception as e:
            logger.warning(f"[org] expired notification failed: {e}")

    @staticmethod
    def remove_expired_org_members_from_sub_clubs(org_id: str) -> Dict[str, Any]:
        """
        Recalculates member statuses in `org_id` and removes any expired organization members
        from all sub-clubs (`club_memberships` where `clubs.org_id == org_id` and `role != 'owner'`).
        Preserves user profiles, running activities, and memberships in independent clubs.
        """
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM organization_members WHERE org_id = ?", (org_id,))
            member_uids = [r["user_id"] for r in cursor.fetchall()]

            cursor.execute("""
                SELECT cm.id as cm_id, cm.club_id, c.name as club_name, cm.user_id, cm.role as club_role
                FROM club_memberships cm
                JOIN clubs c ON cm.club_id = c.id
                WHERE c.org_id = ? AND cm.role != 'owner'
            """, (org_id,))
            before_sub_memberships = [dict(r) for r in cursor.fetchall()]

        all_uids_to_check = set(member_uids) | {sm["user_id"] for sm in before_sub_memberships}
        expired_uids = set()
        for uid in all_uids_to_check:
            st = LocalStore.check_org_member_status(org_id, uid)
            if st.get("status") == "expired":
                expired_uids.add(uid)

        removed_records = []
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            for sm in before_sub_memberships:
                uid = sm["user_id"]
                if uid in expired_uids:
                    cursor.execute("DELETE FROM club_memberships WHERE id = ?", (sm["cm_id"],))
                    removed_records.append(sm)
            conn.commit()

        return {
            "org_id": org_id,
            "expired_org_member_count": len(expired_uids),
            "expired_user_ids": sorted(list(expired_uids)),
            "removed_sub_club_memberships": removed_records,
            "removed_count": len(removed_records)
        }

    @staticmethod
    def validate_sub_club_join_eligibility(club_dict: Dict[str, Any], user_id: str, auto_join_org: bool = False):
        """
        Sub-club entry rule (优化后):
          - 大群成员只要处于 temporary / pending / confirmed 状态即可【直接入团】，无需大群或跑团管理员批准；
          - 资料须在加入大群后 14 天内补齐并通过审核，逾期 (expired) 将被自动移出大群下全部跑团；
          - auto_join_org=True（凭跑团邀请链接/小程序码/跑团邀请码入团）时，未入大群者自动以「临时成员」身份加入大群，
            免大群邀请码、个人资料可稍后补填。
        """
        org_id = club_dict.get("org_id")
        if not org_id:
            return

        eff_uid = LocalStore.resolve_user_id(user_id)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM organizations WHERE id = ?", (org_id,))
            org_row = cursor.fetchone()
            org_name = org_row["name"] if org_row else "大群体"

        status_info = LocalStore.check_org_member_status(org_id, eff_uid)
        if not status_info.get("is_member"):
            if auto_join_org:
                LocalStore.join_organization(user_id=eff_uid, org_id=org_id, skip_code_check=True)
                status_info = LocalStore.check_org_member_status(org_id, eff_uid)
            else:
                raise ValueError(f"加入【{club_dict.get('name')}】失败：该跑团隶属于【{org_name}】大群。请通过跑团邀请链接 / 小程序码一键加入，或先加入【{org_name}】大群！")

        status = status_info.get("status")
        if status in ("expired", "suspended") or (status_info.get("is_member") and not status_info.get("is_valid", True)):
            raise ValueError(
                f"加入【{club_dict.get('name')}】失败：您在【{org_name}】的资料补填期限（{LocalStore.ORG_PROFILE_DEADLINE_DAYS} 天）已过，已被移出下属跑团。"
                f"请前往「我的 → 大群资料」补齐必填资料，并联系大群管理员恢复资格。"
            )
        # temporary / pending / confirmed → 直接入团，无需审批

    @staticmethod
    def is_active_club_inviter(club_id: str, inviter_uid: Optional[str]) -> bool:
        """True if inviter is an active member (any role) of the club, or its owner."""
        if not inviter_uid or not club_id:
            return False
        inv = LocalStore.resolve_user_id(inviter_uid)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT owner_id FROM clubs WHERE id = ?", (club_id,))
            r = cursor.fetchone()
            if r and r[0] == inv:
                return True
            cursor.execute(
                "SELECT 1 FROM club_memberships WHERE club_id = ? AND user_id = ? AND status = 'active'",
                (club_id, inv),
            )
            return cursor.fetchone() is not None

    @staticmethod
    def is_active_org_inviter(org_id: str, inviter_uid: Optional[str]) -> bool:
        """True if inviter is a non-expired member (or owner) of the organization."""
        if not inviter_uid or not org_id:
            return False
        inv = LocalStore.resolve_user_id(inviter_uid)
        org = LocalStore.get_organization(org_id) or {}
        if org.get("owner_id") == inv:
            return True
        st = LocalStore.check_org_member_status(org_id, inv)
        return bool(st.get("is_member") and st.get("is_valid", False))

    @staticmethod
    def enforce_org_profile_deadlines() -> Dict[str, Any]:
        """
        Daily sweep across all organizations:
          1. Sends reminders to temporary/pending members at 7 / 3 / 1 days before the profile deadline (once per mark).
          2. Recomputes statuses and removes expired members from ALL sub-clubs of the organization (with notification).
        """
        summary = {"orgs": 0, "reminders": 0, "removed": 0}
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM organizations")
            orgs = [dict(r) for r in cursor.fetchall()]

        for org in orgs:
            org_id = org["id"]
            org_name = org.get("name") or "大群"
            summary["orgs"] += 1
            try:
                res = LocalStore.remove_expired_org_members_from_sub_clubs(org_id)
                summary["removed"] += res.get("removed_count", 0)
            except Exception as e:
                logger.warning(f"[org-deadline] remove expired failed for {org_id}: {e}")

            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT user_id FROM organization_members WHERE org_id = ? AND status IN ('temporary', 'pending') AND role NOT IN ('owner', 'admin')",
                    (org_id,),
                )
                uids = [r["user_id"] for r in cursor.fetchall()]

            for uid in uids:
                try:
                    st = LocalStore.check_org_member_status(org_id, uid)
                    days = st.get("days_remaining")
                    if st.get("status") not in ("temporary", "pending") or days not in (7, 3, 1):
                        continue
                    ref_id = f"{org_id}:d{days}"
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT 1 FROM system_notifications WHERE user_id = ? AND type = 'org_profile_deadline' AND activity_id = ?",
                            (uid, ref_id),
                        )
                        if cursor.fetchone():
                            continue
                        if st.get("status") == "temporary":
                            missing = "、".join([m.get("label", "") for m in st.get("missing_fields", [])][:6]) or "必填资料"
                            content = (
                                f"您在【{org_name}】的个人资料还差：{missing}。请在 {days} 天内补齐并通过审核，"
                                f"逾期将按群规自动移出【{org_name}】下属的全部跑团。"
                            )
                        else:
                            content = (
                                f"您在【{org_name}】的资料已提交，正等待大群管理员审核（剩余 {days} 天）。"
                                f"如需加快审核可联系大群管理员，逾期未通过将被移出下属跑团。"
                            )
                        LocalStore._insert_notification_raw(
                            cursor, uid, f"⏰ 大群资料补填剩余 {days} 天", content, "org_profile_deadline", ref_id
                        )
                        conn.commit()
                        summary["reminders"] += 1
                except Exception as e:
                    logger.warning(f"[org-deadline] reminder failed for {uid}@{org_id}: {e}")

            # Remind admins of pending reviews that are close to expiring (members shouldn't be penalized for slow review)
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT user_id, joined_at FROM organization_members WHERE org_id = ? AND status = 'pending'",
                        (org_id,),
                    )
                    near = []
                    for r in cursor.fetchall():
                        jdt = parse_iso_datetime(r["joined_at"]) if r["joined_at"] else None
                        if not jdt:
                            continue
                        if jdt.tzinfo is None:
                            jdt = jdt.replace(tzinfo=timezone.utc)
                        left = LocalStore.ORG_PROFILE_DEADLINE_DAYS - (datetime.now(timezone.utc) - jdt).total_seconds() / 86400.0
                        if 0 < left <= 3:
                            near.append(r["user_id"])
                    if near:
                        today_ref = f"{org_id}:review:{date.today().isoformat()}"
                        cursor.execute("""
                            SELECT m.user_id FROM organization_members m WHERE m.org_id = ? AND m.role IN ('owner', 'admin')
                            UNION SELECT o.owner_id FROM organizations o WHERE o.id = ? AND o.owner_id IS NOT NULL
                        """, (org_id, org_id))
                        admin_uids = {row[0] for row in cursor.fetchall() if row[0]}
                        for a_uid in admin_uids:
                            cursor.execute(
                                "SELECT 1 FROM system_notifications WHERE user_id = ? AND type = 'org_review_urgent' AND activity_id = ?",
                                (a_uid, today_ref),
                            )
                            if cursor.fetchone():
                                continue
                            LocalStore._insert_notification_raw(
                                cursor, a_uid, "📋 待审核队员即将到期",
                                f"【{org_name}】有 {len(near)} 位队员已提交资料但尚未审核，3 天内到期后将被自动移出下属跑团，请尽快审核。",
                                "org_review_urgent", today_ref,
                            )
                        conn.commit()
            except Exception as e:
                logger.warning(f"[org-deadline] admin reminder failed for {org_id}: {e}")

        return summary

    @staticmethod
    def validate_sub_club_access(club_id_or_dict: Any, user_id: Optional[str]):
        """
        Validates whether a runner is permitted to browse or use content, metrics, feeds,
        and activities of a sub-club.
        If the club belongs to an organization (org_id is present):
          - If user_id is provided:
            - Check org member status.
            - If user has not joined the org at all, or if user's status in the org is expired/suspended:
              raise ValueError with detailed reason, blocking browsing and using sub-club.
        """
        if not user_id:
            return

        club_dict = None
        if isinstance(club_id_or_dict, dict):
            club_dict = club_id_or_dict
        elif isinstance(club_id_or_dict, str):
            club_dict = LocalStore.get_club(club_id_or_dict)

        if not club_dict:
            return

        org_id = club_dict.get("org_id")
        if not org_id:
            return

        eff_uid = LocalStore.resolve_user_id(user_id)
        if eff_uid in ("admin", "super_admin") or club_dict.get("owner_id") == eff_uid:
            return

        status_info = LocalStore.check_org_member_status(org_id, eff_uid)
        if not status_info.get("is_member"):
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM organizations WHERE id = ?", (org_id,))
                org_row = cursor.fetchone()
                org_name = org_row["name"] if org_row else "大群体"
            raise ValueError(
                f"访问受限：跑团【{club_dict.get('name')}】隶属于【{org_name}】大群，仅对【{org_name}】大群成员开放。请先加入大群！"
            )

        status = status_info.get("status")
        is_valid = status_info.get("is_valid", True)
        if status in ("expired", "suspended") or (status_info.get("is_member") and not is_valid):
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM organizations WHERE id = ?", (org_id,))
                org_row = cursor.fetchone()
                org_name = org_row["name"] if org_row else "大群体"

            raise ValueError(
                f"访问被暂停：跑团【{club_dict.get('name')}】隶属于【{org_name}】大群。您在大群的2周临时访问期已过（超期未完成所有必填字段并获管理员确认）。已暂停浏览使用该大团及其从属跑团的一切内容和活动！请前往个人中心补齐必填资料并联系管理员确认。"
            )

    @staticmethod
    def get_organization(org_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d.pop("invite_code", None)
                if not d.get("join_mode"):
                    d["join_mode"] = "invite"
                d["field_rules"] = LocalStore.get_org_field_rules(org_id)
                return d
            return None

    @staticmethod
    def get_organization_admin(org_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT o.*,
                       p.display_name as owner_name,
                       p.avatar_url as owner_avatar,
                       p.email as owner_email,
                       (SELECT COUNT(*) FROM organization_members m WHERE m.org_id = o.id) as member_count,
                       (SELECT COUNT(*) FROM clubs c WHERE c.org_id = o.id) as sub_clubs_count
                FROM organizations o
                LEFT JOIN profiles p ON o.owner_id = p.id
                WHERE o.id = ?
            """, (org_id,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                if not d.get("join_mode"):
                    d["join_mode"] = "invite"
                d["field_rules"] = LocalStore.get_org_field_rules(org_id)
                return d
            return None

    @staticmethod
    def get_organization_by_code(code: str) -> Optional[Dict[str, Any]]:
        if not code:
            return None
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM organizations WHERE UPPER(invite_code) = ?", (code.strip().upper(),))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d.pop("invite_code", None)
                if not d.get("join_mode"):
                    d["join_mode"] = "invite"
                d["field_rules"] = LocalStore.get_org_field_rules(d["id"])
                return d
            return None

    @staticmethod
    def join_organization(
        user_id: str,
        invite_code: Optional[str] = None,
        org_id: Optional[str] = None,
        real_name: Optional[str] = None,
        gender: Optional[str] = "male",
        date_of_birth: Optional[str] = None,
        class_name: Optional[str] = None,
        phone: Optional[str] = None,
        id_card: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        program: Optional[str] = None,
        class_detail: Optional[str] = None,
        gobi_experience: Optional[str] = None,
        skip_code_check: bool = False
    ) -> Dict[str, Any]:
        """
        Validates invite code or free join mode, registers member into organization_members with encrypted sensitive fields,
        and dynamically determines status (temporary / pending / confirmed) based on field rules.
        skip_code_check=True: invited via a valid member's link / mini-program QR code → org invite code is not required.
        """
        clean_code = (invite_code or "").strip().upper()
        clean_name = (real_name or "").strip()
        clean_dob = (date_of_birth or "").strip()
        clean_phone = (phone or "").strip()
        clean_id_card = (id_card or "").strip()
        clean_program = (program or (extra_data.get("program") if extra_data else None) or "").strip()
        clean_class_detail = (class_detail or (extra_data.get("class_detail") if extra_data else None) or "").strip()
        if clean_program:
            clean_class = f"{clean_program} {clean_class_detail}".strip()
        else:
            clean_class = (class_name or "").strip()
        clean_gobi = (gobi_experience or (extra_data.get("gobi_experience") if extra_data else None) or "").strip()
        clean_gender = (gender or "male").strip()

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            org_row = None
            if clean_code:
                cursor.execute("SELECT * FROM organizations WHERE UPPER(invite_code) = ?", (clean_code,))
                org_row = cursor.fetchone()
                if not org_row and skip_code_check and org_id:
                    cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id.strip(),))
                    org_row = cursor.fetchone()
                if not org_row:
                    raise ValueError("无效的大组织邀请码，请向组织管理员核实后重新输入！")
            elif org_id:
                cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id.strip(),))
                org_row = cursor.fetchone()
                if not org_row:
                    raise ValueError("未找到对应的大群体组织！")
                org_dict = dict(org_row)
                if (org_dict.get("join_mode") or "invite") != "free" and not skip_code_check:
                    raise ValueError(f"【{org_dict.get('name', '大群')}】已开启【凭专属邀请码入会】，请输入邀请码！")
            else:
                cursor.execute("SELECT * FROM organizations")
                all_orgs = cursor.fetchall()
                free_orgs = [o for o in all_orgs if (dict(o).get("join_mode") == "free")]
                if len(free_orgs) == 1:
                    org_row = free_orgs[0]
                elif len(all_orgs) == 1 and (dict(all_orgs[0]).get("join_mode") == "free"):
                    org_row = all_orgs[0]
                else:
                    raise ValueError("请输入大群专属邀请码或选择对应允许自由入会的大群！")

            org = dict(org_row)
            org_id = org["id"]
            membership_id = f"{org_id}_{user_id}"
            now = datetime.utcnow().isoformat() + "Z"

            cursor.execute("SELECT * FROM organization_members WHERE id = ?", (membership_id,))
            existing_row = cursor.fetchone()
            existing = dict(existing_row) if existing_row else None

            if not clean_name and existing:
                clean_name = decrypt_pii(existing["real_name"]) or ""
            if not clean_dob and existing:
                clean_dob = decrypt_pii(existing["date_of_birth"]) or ""
            if not clean_phone and existing:
                clean_phone = decrypt_pii(existing["phone"]) or ""
            if not clean_id_card and existing:
                clean_id_card = decrypt_pii(existing["id_card"]) or ""
            if not clean_class and existing:
                clean_class = existing["class_name"] or ""
            if not clean_gender and existing:
                clean_gender = existing["gender"] or "male"

            if not clean_name:
                cursor.execute("SELECT display_name FROM profiles WHERE id = ?", (user_id,))
                p_tmp = cursor.fetchone()
                clean_name = p_tmp["display_name"] if p_tmp and p_tmp["display_name"] else "跑友"

            role = "owner" if org.get("owner_id") == user_id else (existing["role"] if existing else "member")

            merged_extra = {}
            if existing and existing["extra_data"]:
                try:
                    merged_extra = json.loads(existing["extra_data"])
                except Exception:
                    merged_extra = {}
            if extra_data:
                merged_extra.update(extra_data)

            if clean_program:
                merged_extra["program"] = clean_program
            if clean_class_detail:
                merged_extra["class_detail"] = clean_class_detail
            if clean_gobi:
                merged_extra["gobi_experience"] = clean_gobi
            elif not clean_gobi and merged_extra.get("gobi_experience"):
                clean_gobi = str(merged_extra["gobi_experience"]).strip()

            # Check field rules
            rules = LocalStore.get_org_field_rules(org_id)
            field_values = {
                "real_name": clean_name,
                "gender": clean_gender,
                "date_of_birth": clean_dob,
                "class_name": clean_class,
                "gobi_experience": clean_gobi or merged_extra.get("gobi_experience", ""),
                "phone": clean_phone,
                "id_card": clean_id_card,
                **merged_extra
            }
            missing_fields = []
            for r in rules:
                if r.get("required") and not r.get("hidden") and r.get("mode") != "hidden":
                    f = r["field"]
                    val = field_values.get(f)
                    f_type = r.get("type", "text")
                    if LocalStore.is_field_missing(f, f_type, val, merged_extra):
                        missing_fields.append({"field": f, "label": r.get("label", f)})

            if role in ("owner", "admin"):
                status = "confirmed"
            elif len(missing_fields) > 0:
                status = "temporary"
            elif existing and existing["status"] == "confirmed" and existing.get("confirmed_by"):
                status = "confirmed"
            else:
                status = "pending"

            # If rejoining after expiry: only a COMPLETE profile resets the clock (→ pending review).
            # Re-joining via invite link without completing the profile must NOT grant a fresh 14-day window.
            if existing and existing["status"] == "expired":
                if len(missing_fields) == 0 or role in ("owner", "admin"):
                    joined_at = now
                else:
                    joined_at = existing["joined_at"] or now
                    status = "expired"
            elif existing and existing["joined_at"]:
                joined_at = existing["joined_at"]
            else:
                joined_at = now

            confirmed_at = (
                now if (status == "confirmed" and role in ("owner", "admin"))
                else (existing["confirmed_at"] if existing and status == "confirmed" else None)
            )
            confirmed_by = (
                (org.get("owner_id") or "admin") if (status == "confirmed" and role in ("owner", "admin"))
                else (existing["confirmed_by"] if existing and status == "confirmed" else None)
            )

            enc_real_name = encrypt_pii(clean_name)
            enc_dob = encrypt_pii(clean_dob)
            enc_phone = encrypt_pii(clean_phone) if clean_phone else ""
            enc_id_card = encrypt_pii(clean_id_card) if clean_id_card else ""
            extra_str = json.dumps(merged_extra, ensure_ascii=False)

            cursor.execute("""
                INSERT OR REPLACE INTO organization_members (
                    id, org_id, user_id, real_name, gender, date_of_birth, class_name, phone, id_card, role, status, joined_at, confirmed_at, confirmed_by, extra_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                membership_id, org_id, user_id, enc_real_name, clean_gender, enc_dob, clean_class,
                enc_phone, enc_id_card, role, status, joined_at, confirmed_at, confirmed_by, extra_str
            ))

            # Sync real_name, gender, date_of_birth, phone, id_card into profiles table
            cursor.execute("SELECT display_name FROM profiles WHERE id = ?", (user_id,))
            p_row = cursor.fetchone()
            if p_row:
                cur_name = p_row["display_name"]
                new_name = cur_name if cur_name and cur_name not in ["跑者", "微信用户"] else clean_name
                cursor.execute("""
                    UPDATE profiles 
                    SET display_name = ?, gender = ?, date_of_birth = ?, real_name = ?,
                        phone = CASE WHEN ? != '' THEN ? ELSE phone END,
                        id_card = CASE WHEN ? != '' THEN ? ELSE id_card END
                    WHERE id = ?
                """, (new_name, clean_gender, enc_dob, enc_real_name, enc_phone, enc_phone, enc_id_card, enc_id_card, user_id))

            conn.commit()

            # ── Notify org admins if member joins directly with 'pending' status ──
            if status == "pending":
                try:
                    cursor.execute("""
                        SELECT m.user_id FROM organization_members m
                        WHERE m.org_id = ? AND m.role IN ('owner', 'admin')
                        UNION
                        SELECT o.owner_id FROM organizations o
                        WHERE o.id = ? AND o.owner_id IS NOT NULL
                    """, (org_id, org_id))
                    admin_rows = cursor.fetchall()
                    admin_uids = list({r[0] for r in admin_rows if r[0]})
                    notif_id_base = int(time.time() * 1000)
                    now_notif = get_beijing_iso()
                    display_name = clean_name or user_id
                    for i, admin_uid in enumerate(admin_uids):
                        nid = f"notif_org_{notif_id_base + i}"
                        cursor.execute("""
                            INSERT OR IGNORE INTO system_notifications
                            (id, user_id, activity_id, title, content, type, wechat_sent, wechat_errmsg, is_read, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, 0, NULL, 0, ?)
                        """, (
                            nid,
                            admin_uid,
                            org_id,
                            "📋 新成员待审核",
                            f"【{display_name}】已完整填写必填资料并加入大群，请前往后台审核确认其成员资格。",
                            "org_review_ready",
                            now_notif
                        ))
                    conn.commit()
                except Exception as notif_err:
                    logger.warning(f"[join_organization] admin notif failed: {notif_err}")

            joined_dt = parse_iso_datetime(joined_at)
            elapsed_days = (datetime.now(timezone.utc) - joined_dt).total_seconds() / 86400.0 if joined_dt else 0
            remaining_days = max(0, math.ceil(14.0 - elapsed_days)) if status in ("temporary", "pending") else None

            return {
                "org_id": org_id,
                "org_name": org["name"],
                "org_logo": org["logo_url"],
                "real_name": clean_name,
                "class_name": clean_class,
                "program": merged_extra.get("program", ""),
                "class_detail": merged_extra.get("class_detail", ""),
                "gobi_experience": clean_gobi or merged_extra.get("gobi_experience", ""),
                "gender": clean_gender,
                "date_of_birth": clean_dob,
                "phone": clean_phone,
                "id_card": clean_id_card,
                "status": status,
                "role": role,
                "days_remaining": remaining_days,
                "deadline_at": LocalStore._org_profile_deadline_iso(joined_at) if status in ("temporary", "pending", "expired") else None,
                "missing_fields": missing_fields,
                "extra_data": merged_extra
            }

    @staticmethod
    def update_org_member_profile(org_id: str, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            membership_id = f"{org_id}_{user_id}"
            cursor.execute("SELECT * FROM organization_members WHERE id = ?", (membership_id,))
            existing = cursor.fetchone()
            if not existing:
                raise ValueError("您尚未加入该大群体")

            member = dict(existing)
            status_info = LocalStore.check_org_member_status(org_id, user_id)
            is_currently_expired = (status_info.get("status") == "expired") or (member.get("status") == "expired")

            clean_name = data.get("real_name")
            if clean_name is not None:
                clean_name = clean_name.strip()
            else:
                clean_name = decrypt_pii(member.get("real_name")) or ""

            clean_dob = data.get("date_of_birth")
            if clean_dob is not None:
                clean_dob = clean_dob.strip()
            else:
                clean_dob = decrypt_pii(member.get("date_of_birth")) or ""

            clean_phone = data.get("phone")
            if clean_phone is not None:
                clean_phone = clean_phone.strip()
            else:
                clean_phone = decrypt_pii(member.get("phone")) or ""

            clean_id_card = data.get("id_card")
            if clean_id_card is not None:
                clean_id_card = clean_id_card.strip()
            else:
                clean_id_card = decrypt_pii(member.get("id_card")) or ""

            merged_extra = {}
            if member.get("extra_data"):
                try:
                    merged_extra = json.loads(member["extra_data"])
                except Exception:
                    merged_extra = {}
            if data.get("extra_data"):
                merged_extra.update(data["extra_data"])

            clean_program = data.get("program")
            if clean_program is not None:
                clean_program = clean_program.strip()
                merged_extra["program"] = clean_program
            else:
                clean_program = merged_extra.get("program", "")

            clean_class_detail = data.get("class_detail")
            if clean_class_detail is not None:
                clean_class_detail = clean_class_detail.strip()
                merged_extra["class_detail"] = clean_class_detail
            else:
                clean_class_detail = merged_extra.get("class_detail", "")

            clean_gobi = data.get("gobi_experience")
            if clean_gobi is not None:
                clean_gobi = clean_gobi.strip()
                merged_extra["gobi_experience"] = clean_gobi
            else:
                clean_gobi = merged_extra.get("gobi_experience", "")

            for extra_k in ["emergency_contact", "clothing_size", "shoe_size", "health_declaration"]:
                if data.get(extra_k) is not None:
                    merged_extra[extra_k] = data[extra_k]

            clean_class = data.get("class_name")
            if clean_program:
                clean_class = f"{clean_program} {clean_class_detail}".strip()
            elif clean_class is not None:
                clean_class = clean_class.strip()
            else:
                clean_class = member.get("class_name") or ""

            clean_gender = data.get("gender")
            if clean_gender is not None:
                clean_gender = clean_gender.strip()
            else:
                clean_gender = member.get("gender") or "male"

            rules = LocalStore.get_org_field_rules(org_id)
            field_values = {
                "real_name": clean_name,
                "gender": clean_gender,
                "date_of_birth": clean_dob,
                "class_name": clean_class,
                "gobi_experience": clean_gobi or merged_extra.get("gobi_experience", ""),
                "phone": clean_phone,
                "id_card": clean_id_card,
                **merged_extra
            }
            missing_fields = []
            for r in rules:
                if r.get("required") and not r.get("hidden") and r.get("mode") != "hidden":
                    f = r["field"]
                    val = field_values.get(f)
                    f_type = r.get("type", "text")
                    if LocalStore.is_field_missing(f, f_type, val, merged_extra):
                        missing_fields.append({"field": f, "label": r.get("label", f)})

            role = member.get("role") or "member"
            current_status = member.get("status")
            if role in ("owner", "admin"):
                status = "confirmed"
            elif len(missing_fields) > 0:
                # If already expired, retain expired status until all required fields are filled!
                status = "expired" if is_currently_expired else "temporary"
            elif current_status == "confirmed" and member.get("confirmed_by"):
                status = "confirmed"
            else:
                # All required fields completed! If was expired, status promotes to pending for admin verification!
                status = "pending"

            confirmed_at = member.get("confirmed_at") if status == "confirmed" else None
            confirmed_by = member.get("confirmed_by") if status == "confirmed" else None

            enc_real_name = encrypt_pii(clean_name)
            enc_dob = encrypt_pii(clean_dob)
            enc_phone = encrypt_pii(clean_phone) if clean_phone else ""
            enc_id_card = encrypt_pii(clean_id_card) if clean_id_card else ""
            extra_str = json.dumps(merged_extra, ensure_ascii=False)

            now_iso = datetime.utcnow().isoformat() + "Z"
            # If an expired runner completes all required fields, refresh joined_at to now so 14-day clock resets for pending review!
            if is_currently_expired and status == "pending":
                cursor.execute("""
                    UPDATE organization_members
                    SET real_name = ?, gender = ?, date_of_birth = ?, class_name = ?,
                        phone = ?, id_card = ?, status = ?, confirmed_at = ?, confirmed_by = ?, extra_data = ?, joined_at = ?
                    WHERE id = ?
                """, (enc_real_name, clean_gender, enc_dob, clean_class, enc_phone, enc_id_card, status, confirmed_at, confirmed_by, extra_str, now_iso, membership_id))
            else:
                cursor.execute("""
                    UPDATE organization_members
                    SET real_name = ?, gender = ?, date_of_birth = ?, class_name = ?,
                        phone = ?, id_card = ?, status = ?, confirmed_at = ?, confirmed_by = ?, extra_data = ?
                    WHERE id = ?
                """, (enc_real_name, clean_gender, enc_dob, clean_class, enc_phone, enc_id_card, status, confirmed_at, confirmed_by, extra_str, membership_id))

            cursor.execute("""
                UPDATE profiles
                SET real_name = ?, gender = ?, date_of_birth = ?,
                    phone = CASE WHEN ? != '' THEN ? ELSE phone END,
                    id_card = CASE WHEN ? != '' THEN ? ELSE id_card END
                WHERE id = ?
            """, (enc_real_name, clean_gender, enc_dob, enc_phone, enc_phone, enc_id_card, enc_id_card, user_id))

            conn.commit()

            # ── Notify org admins when member status upgrades temporary/expired → pending ──
            if (current_status in ("temporary", "expired") or is_currently_expired) and status == "pending":
                try:
                    # Find org owner + admin user_ids
                    cursor.execute("""
                        SELECT m.user_id FROM organization_members m
                        WHERE m.org_id = ? AND m.role IN ('owner', 'admin')
                        UNION
                        SELECT o.owner_id FROM organizations o
                        WHERE o.id = ? AND o.owner_id IS NOT NULL
                    """, (org_id, org_id))
                    admin_rows = cursor.fetchall()
                    admin_uids = list({r[0] for r in admin_rows if r[0]})
                    notif_id_base = int(time.time() * 1000)
                    now_notif = get_beijing_iso()
                    display_name = clean_name or user_id
                    title = "📋 队员申请恢复资格" if is_currently_expired else "📋 新成员待审核"
                    content = (
                        f"【{display_name}】已补全所有实名必填资料并申请恢复入会资格，请前往大群管理后台审核批准。"
                        if is_currently_expired
                        else f"【{display_name}】已补全所有必填资料，请前往大群后台审核确认其成员资格。"
                    )
                    for i, admin_uid in enumerate(admin_uids):
                        nid = f"notif_org_{notif_id_base + i}"
                        cursor.execute("""
                            INSERT OR IGNORE INTO system_notifications
                            (id, user_id, activity_id, title, content, type, wechat_sent, wechat_errmsg, is_read, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, 0, NULL, 0, ?)
                        """, (
                            nid,
                            admin_uid,
                            org_id,
                            title,
                            content,
                            "org_review_ready",
                            now_notif
                        ))
                    conn.commit()
                except Exception as notif_err:
                    logger.warning(f"[update_org_member_profile] admin notif failed: {notif_err}")

            joined_at = now_iso if (is_currently_expired and status == "pending") else member.get("joined_at")
            joined_dt = parse_iso_datetime(joined_at)
            elapsed_days = (datetime.now(timezone.utc) - joined_dt).total_seconds() / 86400.0 if joined_dt else 0
            remaining_days = max(0, math.ceil(14.0 - elapsed_days)) if status in ("temporary", "pending") else None

            return {
                "org_id": org_id,
                "user_id": user_id,
                "real_name": clean_name,
                "class_name": clean_class,
                "program": merged_extra.get("program", ""),
                "class_detail": merged_extra.get("class_detail", ""),
                "gobi_experience": clean_gobi or merged_extra.get("gobi_experience", ""),
                "gender": clean_gender,
                "date_of_birth": clean_dob,
                "phone": clean_phone,
                "id_card": clean_id_card,
                "status": status,
                "days_remaining": remaining_days,
                "missing_fields": missing_fields,
                "extra_data": merged_extra
            }

    @staticmethod
    def assign_member_to_sub_club(user_id: str, club_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clubs WHERE id = ?", (club_id,))
            club = cursor.fetchone()
            if not club:
                return None
            club_dict = dict(club)
            c_status = club_dict.get("status") or "active"
            if c_status == "paused":
                raise ValueError(f"跑团【{club_dict.get('name')}】当前处于暂停状态，暂不接受指派新队员！")
            if c_status == "locked":
                raise ValueError(f"跑团【{club_dict.get('name')}】当前处于锁定状态，禁止变更队员！")

            org_id = club_dict.get("org_id")
            now = datetime.utcnow().isoformat() + "Z"
            
            # If club belongs to an org, ensure member is confirmed in that org
            if org_id:
                cursor.execute("SELECT * FROM organization_members WHERE org_id = ? AND user_id = ?", (org_id, user_id))
                om = cursor.fetchone()
                if om:
                    cursor.execute("UPDATE organization_members SET status = 'confirmed', confirmed_at = ?, confirmed_by = 'admin' WHERE org_id = ? AND user_id = ?", (now, org_id, user_id))

            membership_id = f"{club_id}_{user_id}"
            canonical_uid = LocalStore.resolve_user_id(user_id)
            cursor.execute(
                "SELECT 1 FROM club_memberships WHERE club_id = ? AND user_id IN (?, ?) AND status = 'active'",
                (club_id, user_id, canonical_uid),
            )
            was_already_active = bool(cursor.fetchone())
            cursor.execute("""
                INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                VALUES (?, ?, ?, COALESCE((SELECT role FROM club_memberships WHERE id = ?), 'member'), 'active', ?, 1)
            """, (membership_id, club_id, user_id, membership_id, now))
            conn.commit()
        if not was_already_active:
            LocalStore._notify_club_members_of_new_join(club_id, user_id)
        return club_dict

    @staticmethod
    def get_user_organizations(user_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT o.id, o.name, o.logo_url, o.description, o.city, o.join_mode, o.invite_code, o.owner_id,
                       (SELECT COUNT(*) FROM organization_members om WHERE om.org_id = o.id) as member_count,
                       (SELECT COUNT(*) FROM clubs sc WHERE sc.org_id = o.id) as sub_clubs_count,
                       m.real_name, m.gender, m.date_of_birth, m.class_name, m.phone, m.id_card,
                       COALESCE(m.role, CASE WHEN o.owner_id = ? THEN 'owner' ELSE 'member' END) as role,
                       COALESCE(m.status, 'confirmed') as status,
                       COALESCE(m.joined_at, o.created_at) as joined_at,
                       m.confirmed_at, m.extra_data
                FROM organizations o
                LEFT JOIN organization_members m ON m.org_id = o.id AND m.user_id = ?
                WHERE m.user_id = ? OR o.owner_id = ?
                ORDER BY joined_at ASC
            """, (user_id, user_id, user_id, user_id))
            rows = cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["join_mode"] = d.get("join_mode") or "invite"
                d["field_rules"] = LocalStore.get_org_field_rules(d["id"])
                is_organizer = (
                    d.get("role") in ("owner", "admin") or
                    d.get("owner_id") == user_id or
                    user_id in ("admin", "super_admin")
                )
                d["is_organizer"] = is_organizer
                if not is_organizer:
                    d.pop("invite_code", None)

                d["real_name"] = decrypt_pii(d.get("real_name"))
                d["date_of_birth"] = decrypt_pii(d.get("date_of_birth"))
                d["phone"] = decrypt_pii(d.get("phone"))
                d["id_card"] = decrypt_pii(d.get("id_card"))
                d["age_group"] = compute_age_group(d.get("date_of_birth"))
                dob_val = d.get("date_of_birth") or ""
                d["birth_year"] = dob_val[:4] if len(dob_val) >= 4 and dob_val[:4].isdigit() else ""
                
                # Check status and expiry
                status_info = LocalStore.check_org_member_status(d["id"], user_id)
                d["status"] = status_info.get("status")
                d["days_remaining"] = status_info.get("days_remaining")
                d["remaining_days"] = status_info.get("days_remaining")
                d["deadline_at"] = status_info.get("deadline_at")
                d["missing_fields"] = status_info.get("missing_fields", [])
                d["missing_required_fields"] = [m.get("label") or m.get("field") for m in status_info.get("missing_fields", [])]
                d["is_valid"] = status_info.get("is_valid", True)
                d["is_expired"] = bool(status_info.get("status") == "expired")

                extra = {}
                if d.get("extra_data"):
                    try:
                        extra = json.loads(d["extra_data"])
                    except Exception:
                        pass
                d["extra_data"] = extra
                d["program"] = extra.get("program", "")
                d["class_detail"] = extra.get("class_detail", "")
                d["gobi_experience"] = extra.get("gobi_experience", "")
                d["emergency_contact"] = extra.get("emergency_contact", "")
                d["clothing_size"] = extra.get("clothing_size", "")
                d["jersey_size"] = extra.get("jersey_size") or extra.get("clothing_size", "")
                d["shoe_size"] = extra.get("shoe_size", "")
                d["running_shoe_size"] = extra.get("running_shoe_size") or extra.get("shoe_size", "")
                d["marathon_pb"] = extra.get("marathon_pb", "")
                d["full_marathon_pb"] = extra.get("full_marathon_pb") or extra.get("marathon_pb", "")
                d["health_declaration"] = extra.get("health_declaration_text") or ("本人确认身体健康，无不适合高强度跑步的疾病。" if extra.get("health_declaration") else "")

                result.append(d)
            return result

    @staticmethod
    def get_org_sub_clubs(org_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.*,
                       p.display_name as owner_name,
                       p.avatar_url as owner_avatar,
                       (SELECT COUNT(*) FROM club_memberships m WHERE m.club_id = c.id AND m.status = 'active') as member_count
                FROM clubs c
                LEFT JOIN profiles p ON c.owner_id = p.id
                WHERE c.org_id = ?
                ORDER BY c.created_at ASC
            """, (org_id,))
            rows = cursor.fetchall()
            
            user_club_ids = set()
            if user_id:
                cursor.execute("SELECT club_id FROM club_memberships WHERE user_id = ? AND status = 'active'", (user_id,))
                user_club_ids = {r[0] for r in cursor.fetchall()}

            status_info = None
            if user_id:
                status_info = LocalStore.check_org_member_status(org_id, user_id)

            result = []
            for r in rows:
                d = dict(r)
                d.pop("invite_code", None)
                d["is_member"] = d["id"] in user_club_ids
                c_status = d.get("status") or "active"
                if c_status == "paused":
                    d["can_join"] = False
                    d["join_restriction_reason"] = "跑团已暂停运行，暂不接受新成员加入"
                elif c_status == "locked":
                    d["can_join"] = False
                    d["join_restriction_reason"] = "跑团已锁定，禁止新成员加入"
                elif status_info:
                    st = status_info.get("status")
                    # 优化：临时 / 待审核成员也可直接加入下属跑团（无需审批），仅逾期成员受限
                    d["can_join"] = bool(st in ("confirmed", "temporary", "pending"))
                    d["user_org_status"] = st
                    d["user_org_days_remaining"] = status_info.get("days_remaining")
                    d["user_org_deadline_at"] = status_info.get("deadline_at")
                    if st == "expired":
                        d["join_restriction_reason"] = (
                            f"大群资料补填期限（{LocalStore.ORG_PROFILE_DEADLINE_DAYS} 天）已过，请补齐资料并联系管理员恢复资格"
                        )
                    elif st not in ("confirmed", "temporary", "pending"):
                        d["join_restriction_reason"] = "请先加入大群"
                    else:
                        d["join_restriction_reason"] = None
                else:
                    d["can_join"] = False
                    d["join_restriction_reason"] = "请先加入大群"
                result.append(d)
            return result

    @staticmethod
    def get_org_members(org_id: str, search: Optional[str] = None, class_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = """
                SELECT m.id, m.org_id, m.user_id, m.real_name, m.gender, m.date_of_birth, m.class_name,
                       m.phone, m.id_card, m.role, m.status, m.joined_at, m.confirmed_at, m.extra_data,
                       p.avatar_url, p.display_name, p.marathon_pb, p.half_pb
                FROM organization_members m
                LEFT JOIN profiles p ON m.user_id = p.id
                WHERE m.org_id = ?
            """
            params = [org_id]
            if class_filter:
                query += " AND m.class_name = ?"
                params.append(class_filter.strip())

            query += " ORDER BY CASE m.role WHEN 'owner' THEN 1 WHEN 'admin' THEN 2 ELSE 3 END, m.joined_at DESC"
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            
            result = []
            for r in rows:
                d = dict(r)
                d["real_name"] = decrypt_pii(d.get("real_name"))
                d["date_of_birth"] = decrypt_pii(d.get("date_of_birth"))
                d["phone"] = decrypt_pii(d.get("phone"))
                d["id_card"] = decrypt_pii(d.get("id_card"))
                d["age_group"] = compute_age_group(d.get("date_of_birth"))
                dob_val = d.get("date_of_birth") or ""
                d["birth_year"] = dob_val[:4] if len(dob_val) >= 4 and dob_val[:4].isdigit() else ""

                status_info = LocalStore.check_org_member_status(org_id, d["user_id"])
                d["status"] = status_info.get("status")
                d["days_remaining"] = status_info.get("days_remaining")
                d["missing_fields"] = status_info.get("missing_fields", [])
                d["missing_required_fields"] = [f.get("label", f.get("field")) for f in d["missing_fields"]]
                d["is_valid"] = status_info.get("is_valid", True)

                extra = {}
                if d.get("extra_data"):
                    try:
                        extra = json.loads(d["extra_data"])
                    except Exception:
                        pass
                d["extra_data"] = extra
                d["program"] = extra.get("program", "")
                d["class_detail"] = extra.get("class_detail", "")
                d["gobi_experience"] = extra.get("gobi_experience", "")

                if search:
                    s = search.strip().lower()
                    rn = (d.get("real_name") or "").lower()
                    cn = (d.get("class_name") or "").lower()
                    dn = (d.get("display_name") or "").lower()
                    ge = (d.get("gobi_experience") or "").lower()
                    pr = (d.get("program") or "").lower()
                    if s not in rn and s not in cn and s not in dn and s not in ge and s not in pr:
                        continue

                cursor.execute("""
                    SELECT c.id, c.name 
                    FROM club_memberships cm
                    JOIN clubs c ON cm.club_id = c.id
                    WHERE cm.user_id = ? AND c.org_id = ? AND cm.status = 'active'
                """, (d["user_id"], org_id))
                d["sub_clubs"] = [dict(sc) for sc in cursor.fetchall()]
                result.append(d)
            return result

    @staticmethod
    def assign_org_member_to_sub_club(
        org_id: str,
        target_uid: str,
        club_id: str,
        operator_uid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Allows Org Owner/Admin to assign an org member directly into a sub-club of that org."""
        if operator_uid and not LocalStore.is_org_organizer(org_id, operator_uid):
            raise PermissionError("无权限：仅大群主理人、大群管理员或超级管理员可调配下属跑团成员")
        org = LocalStore.get_organization(org_id)
        if not org:
            raise ValueError("大群不存在")
        club = LocalStore.get_club(club_id)
        if not club or club.get("org_id") != org_id:
            raise ValueError("目标跑团不存在或不属于本大群")
        LocalStore._insert_active_club_membership(club_id, target_uid, True)
        return {
            "success": True,
            "org_id": org_id,
            "club_id": club_id,
            "club_name": club.get("name"),
            "user_id": target_uid,
            "message": f"已将成员划拨加入下属跑团【{club.get('name')}】！",
        }

    @staticmethod
    def get_org_periodic_report(
        org_id: str,
        operator_uid: Optional[str] = None,
        period_type: str = "week",
        year: Optional[int] = None,
        period_index: Optional[int] = None,
        trail_mode: str = "include",
        period_offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generates a cross-club periodic report for an Organization (Grand Community):
        - Deduplicated organization-wide KPIs (total km, avg km, attendance rate, watch binding rate, LSD counts)
        - Sub-club PK leaderboard (`sub_club_rankings`: per-club member count, attendance, total km, avg km, achievement rate, top 3 runners, full club member drill-down)
        - Deduplicated full member leaderboard (`member_rankings` with sub-club badges, class, Gobi group, PB)
        - Unaffiliated members radar (`unaffiliated_members` who joined the org but haven't joined any sub-club)
        - Ready-to-forward WeChat text (`forward_text`) and official MiniApp QR code (`qrcode_url`, `qrcode_base64`).
        """
        org = LocalStore.get_organization(org_id)
        if not org:
            raise ValueError("大群不存在")
        if operator_uid and not LocalStore.is_org_organizer(org_id, operator_uid):
            raise PermissionError("无权限：仅大群主理人、大群管理员或超级管理员可查看大群全域报表")

        trail_mode_val = str(trail_mode or "include").strip().lower()
        if trail_mode_val not in ("include", "exclude_pace", "exclude_all"):
            trail_mode_val = "include"
        trail_mode_labels = {
            "include": "包含越野跑（默认）",
            "exclude_pace": "仅去除越野配速（保留越野跑量）",
            "exclude_all": "去除越野跑量与配速（仅统计路跑）",
        }
        trail_mode_label = trail_mode_labels[trail_mode_val]

        today = get_beijing_today()
        now_year = today.year
        now_month = today.month

        try:
            target_year = int(year) if (year is not None and not hasattr(year, "default")) else now_year
        except (ValueError, TypeError):
            target_year = now_year

        try:
            period_index_val = int(period_index) if (period_index is not None and not hasattr(period_index, "default")) else None
        except (ValueError, TypeError):
            period_index_val = None

        try:
            offset_val = int(period_offset) if (period_offset is not None and not hasattr(period_offset, "default")) else 0
        except (ValueError, TypeError):
            offset_val = 0

        if period_index_val is None and offset_val != 0:
            if str(period_type) == "month":
                total_months = (now_year * 12 + (now_month - 1)) + offset_val
                target_year = total_months // 12
                period_index_val = (total_months % 12) + 1
            else:
                shifted_day = today + timedelta(days=offset_val * 7)
                iso_y, iso_w, _ = shifted_day.isocalendar()
                target_year = iso_y
                period_index_val = iso_w

        if str(period_type) == "month":
            target_month = period_index_val or now_month
            if target_month < 1 or target_month > 12:
                target_month = now_month
            start_date_obj = date(target_year, target_month, 1)
            _, last_day = calendar.monthrange(target_year, target_month)
            end_date_obj = date(target_year, target_month, last_day)
            start_iso = f"{start_date_obj.isoformat()}T00:00:00"
            if target_month == 12:
                end_iso = f"{target_year + 1:04d}-01-01T00:00:00"
            else:
                end_iso = f"{target_year:04d}-{target_month + 1:02d}-01T00:00:00"
            period_label = f"{target_year}年{target_month}月全域月报"
            date_range_str = f"{start_date_obj.strftime('%Y.%m.%d')} ~ {end_date_obj.strftime('%Y.%m.%d')}"
            is_past_period = (target_year < now_year) or (target_year == now_year and target_month < now_month)
        else:
            iso_year, iso_week, _ = today.isocalendar()
            target_week = period_index_val or iso_week
            if target_week < 1 or target_week > 53:
                target_week = iso_week
            try:
                start_date_obj = date.fromisocalendar(target_year, target_week, 1)
                end_date_obj = date.fromisocalendar(target_year, target_week, 7)
            except Exception:
                start_date_obj = today - timedelta(days=today.weekday())
                end_date_obj = start_date_obj + timedelta(days=6)
            start_iso = f"{start_date_obj.isoformat()}T00:00:00"
            end_iso = f"{(end_date_obj + timedelta(days=1)).isoformat()}T00:00:00"
            period_label = f"{target_year}年第{target_week}周全域周报"
            date_range_str = f"{start_date_obj.strftime('%m月%d日')} ~ {end_date_obj.strftime('%m月%d日')}"
            is_past_period = (target_year < iso_year) or (target_year == iso_year and target_week < iso_week)

        org_members = LocalStore.get_org_members(org_id)
        sub_clubs = LocalStore.get_org_sub_clubs(org_id)

        # Collect all unique user IDs across org_members AND sub_club members
        sub_club_members_map: Dict[str, List[Dict[str, Any]]] = {}
        user_sub_clubs_map: Dict[str, List[Dict[str, str]]] = {}
        all_uid_meta: Dict[str, Dict[str, Any]] = {}

        for om in org_members:
            uid = om["user_id"]
            disp = (om.get("real_name") or om.get("display_name") or f"戈友_{uid[-4:]}").strip()
            all_uid_meta[uid] = {
                "user_id": uid,
                "display_name": disp,
                "real_name": om.get("real_name") or "",
                "avatar_url": om.get("avatar_url") or "",
                "class_name": om.get("class_name") or "",
                "gobi_experience": om.get("gobi_experience") or "",
                "org_role": om.get("role") or "member",
                "org_status": om.get("status") or "confirmed",
                "marathon_pb": om.get("marathon_pb") or "",
                "half_pb": om.get("half_pb") or "",
                "is_org_member": True,
            }
            user_sub_clubs_map[uid] = list(om.get("sub_clubs") or [])

        for sc in sub_clubs:
            cid = sc["id"]
            cname = sc["name"]
            cm_list = LocalStore.get_club_members(cid)
            sub_club_members_map[cid] = cm_list
            for cm in cm_list:
                uid = cm["user_id"]
                if uid not in user_sub_clubs_map:
                    user_sub_clubs_map[uid] = []
                if not any(x["id"] == cid for x in user_sub_clubs_map[uid]):
                    user_sub_clubs_map[uid].append({"id": cid, "name": cname})
                if uid not in all_uid_meta:
                    all_uid_meta[uid] = {
                        "user_id": uid,
                        "display_name": cm.get("display_name") or f"跑者_{uid[-4:]}",
                        "real_name": "",
                        "avatar_url": cm.get("avatar_url") or "",
                        "class_name": "",
                        "gobi_experience": "",
                        "org_role": "member",
                        "org_status": "confirmed",
                        "marathon_pb": cm.get("marathon_pb") or "",
                        "half_pb": cm.get("half_pb") or "",
                        "is_org_member": False,
                    }

        all_uids = list(all_uid_meta.keys())

        # Fetch watch connection status & goals & activities for all_uids
        watch_map: Dict[str, bool] = {}
        act_rows: List[Dict[str, Any]] = []
        pace_act_rows: List[Dict[str, Any]] = []
        if all_uids:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                placeholders = ",".join(["?"] * len(all_uids))
                cursor.execute(
                    f"""
                    SELECT id, garmin_connected, coros_connected, apple_watch_connected, huawei_connected, suunto_connected
                    FROM profiles
                    WHERE id IN ({placeholders})
                    """,
                    all_uids,
                )
                for pr in cursor.fetchall():
                    watch_map[pr["id"]] = bool(
                        pr["garmin_connected"]
                        or pr["coros_connected"]
                        or pr["apple_watch_connected"]
                        or pr["huawei_connected"]
                        or pr["suunto_connected"]
                    )

                cursor.execute(
                    f"""
                    SELECT a.*
                    FROM activities a
                    WHERE a.user_id IN ({placeholders})
                      AND a.start_time >= ? AND a.start_time < ?
                      AND {RUNNING_SQL_FILTER.replace('sport_type', 'a.sport_type')}
                    ORDER BY a.start_time DESC
                    """,
                    all_uids + [start_iso, end_iso],
                )
                raw_acts = [dict(r) for r in cursor.fetchall()]

            if trail_mode_val == "exclude_all":
                act_rows = [a for a in raw_acts if not LocalStore.is_trail_activity(a)]
            else:
                act_rows = raw_acts

            if trail_mode_val in ("exclude_pace", "exclude_all"):
                pace_act_rows = [a for a in act_rows if not LocalStore.is_trail_activity(a)]
            else:
                pace_act_rows = act_rows

        # Compute per-user stats
        user_stats: Dict[str, Dict[str, Any]] = {}
        for uid, meta in all_uid_meta.items():
            g = LocalStore.get_goal(uid)
            tgts = g.get("monthly_targets") or [200.0] * 12
            m_idx = (start_date_obj.month - 1) if start_date_obj else (now_month - 1)
            month_tgt = float(tgts[m_idx] if m_idx < len(tgts) else 200.0)
            if month_tgt <= 0:
                month_tgt = 200.0
            period_tgt = round(month_tgt, 1) if str(period_type) == "month" else round(month_tgt / 4.33, 1)
            clubs_for_u = user_sub_clubs_map.get(uid) or []
            user_stats[uid] = {
                **meta,
                "watch_connected": bool(watch_map.get(uid, False)),
                "sub_clubs": clubs_for_u,
                "sub_club_ids": [c["id"] for c in clubs_for_u],
                "sub_club_names": [c["name"] for c in clubs_for_u],
                "is_unaffiliated": len(clubs_for_u) == 0,
                "distance_m": 0.0,
                "moving_s": 0,
                "pace_distance_m": 0.0,
                "pace_moving_s": 0,
                "runs_count": 0,
                "longest_m": 0.0,
                "lsd_15k_count": 0,
                "lsd_25k_count": 0,
                "target_km": period_tgt,
            }

        for a in act_rows:
            uid = a["user_id"]
            if uid not in user_stats:
                continue
            dm = float(a.get("distance_meters") or 0.0)
            ms = int(a.get("moving_time_seconds") or 0)
            st = user_stats[uid]
            st["distance_m"] += dm
            st["moving_s"] += ms
            st["runs_count"] += 1
            if dm > st["longest_m"]:
                st["longest_m"] = dm
            if dm >= 15000.0:
                st["lsd_15k_count"] += 1
            if dm >= 25000.0:
                st["lsd_25k_count"] += 1

        for a in pace_act_rows:
            uid = a["user_id"]
            if uid not in user_stats:
                continue
            st = user_stats[uid]
            st["pace_distance_m"] += float(a.get("distance_meters") or 0.0)
            st["pace_moving_s"] += int(a.get("moving_time_seconds") or 0)

        for uid, st in user_stats.items():
            dkm = round(st["distance_m"] / 1000.0, 1)
            st["distance_km"] = dkm
            st["longest_run_km"] = round(st["longest_m"] / 1000.0, 1)
            if st["pace_distance_m"] > 0 and st["pace_moving_s"] > 0:
                sec_km = int(round(st["pace_moving_s"] / (st["pace_distance_m"] / 1000.0)))
                st["avg_pace_str"] = f"{sec_km // 60}:{sec_km % 60:02d}"
            else:
                st["avg_pace_str"] = "—"
            st["avg_pace"] = st["avg_pace_str"]
            st["watch_bound"] = bool(st.get("watch_connected"))
            st["watch_brand"] = st.get("watch_brand") or ("已绑定" if st["watch_bound"] else "")
            tgt = st["target_km"] or 45.0
            comp = round((dkm / tgt) * 100.0, 1) if tgt > 0 else 0.0
            st["completion_rate"] = comp
            st["is_achieved"] = dkm >= tgt and tgt > 0

        # 1. Sub-club PK rankings
        sub_club_rankings: List[Dict[str, Any]] = []
        for sc in sub_clubs:
            cid = sc["id"]
            cm_list = sub_club_members_map.get(cid) or []
            c_uids = [m["user_id"] for m in cm_list]
            c_stats_list = [user_stats[u] for u in c_uids if u in user_stats]
            c_stats_list.sort(key=lambda x: (x["distance_km"], x["completion_rate"]), reverse=True)

            m_cnt = len(c_stats_list)
            act_cnt = sum(1 for x in c_stats_list if x["runs_count"] > 0)
            ach_cnt = sum(1 for x in c_stats_list if x["is_achieved"])
            tot_km = round(sum(x["distance_km"] for x in c_stats_list), 1)
            tot_tgt = round(sum(x["target_km"] for x in c_stats_list), 1)
            tot_runs = sum(x["runs_count"] for x in c_stats_list)
            lsd_15k_c = sum(x["lsd_15k_count"] for x in c_stats_list)
            lsd_25k_c = sum(x["lsd_25k_count"] for x in c_stats_list)
            avg_km = round(tot_km / m_cnt, 1) if m_cnt > 0 else 0.0
            att_rate = round((act_cnt / m_cnt) * 100.0, 1) if m_cnt > 0 else 0.0
            ach_rate = round((ach_cnt / m_cnt) * 100.0, 1) if m_cnt > 0 else 0.0
            comp_rate = round((tot_km / tot_tgt) * 100.0, 1) if tot_tgt > 0 else 0.0
            top_r_list = [
                {
                    "user_id": x["user_id"],
                    "display_name": x["display_name"],
                    "avatar_url": x["avatar_url"],
                    "distance_km": x["distance_km"],
                }
                for x in c_stats_list[:3]
                if x["distance_km"] > 0
            ]

            sub_club_rankings.append({
                "club_id": cid,
                "club_name": sc.get("name") or "分跑团",
                "city": sc.get("city") or "上海",
                "logo_url": sc.get("logo_url") or "",
                "owner_name": sc.get("owner_name") or "团长",
                "status": sc.get("status") or "active",
                "member_count": m_cnt,
                "active_member_count": act_cnt,
                "active_count": act_cnt,
                "attendance_rate_pct": att_rate,
                "attendance_rate": att_rate,
                "achieved_member_count": ach_cnt,
                "achieved_count": ach_cnt,
                "achievement_rate_pct": ach_rate,
                "achievement_rate": ach_rate,
                "total_distance_km": tot_km,
                "avg_distance_km": avg_km,
                "total_target_km": tot_tgt,
                "team_completion_rate": comp_rate,
                "total_runs_count": tot_runs,
                "lsd_15k_count": lsd_15k_c,
                "lsd_25k_count": lsd_25k_c,
                "top_runners": top_r_list,
                "top_members": top_r_list,
                "members_detail": c_stats_list,
            })

        # Default sort sub-clubs by avg_distance_km desc, then total_distance_km desc
        sub_club_rankings.sort(
            key=lambda c: (c["avg_distance_km"], c["total_distance_km"], c["attendance_rate_pct"]),
            reverse=True,
        )
        for idx, c in enumerate(sub_club_rankings):
            c["rank"] = idx + 1

        # 2. Deduplicated member rankings & unaffiliated members
        member_rankings = list(user_stats.values())
        member_rankings.sort(key=lambda x: (x["distance_km"], x["completion_rate"]), reverse=True)
        for idx, m in enumerate(member_rankings):
            m["rank"] = idx + 1

        unaffiliated_members = [m for m in member_rankings if m["is_unaffiliated"]]

        # 3. Organization-wide deduplicated KPIs
        total_members_count = len(member_rankings)
        active_members_count = sum(1 for m in member_rankings if m["runs_count"] > 0)
        achieved_members_count = sum(1 for m in member_rankings if m["is_achieved"])
        watch_bound_count = sum(1 for m in member_rankings if m["watch_connected"])
        total_distance_km = round(sum(m["distance_km"] for m in member_rankings), 1)
        total_target_km = round(sum(m["target_km"] for m in member_rankings), 1)
        total_runs_count = sum(m["runs_count"] for m in member_rankings)
        lsd_15k_total = sum(m["lsd_15k_count"] for m in member_rankings)
        lsd_25k_total = sum(m["lsd_25k_count"] for m in member_rankings)
        avg_distance_km = round(total_distance_km / total_members_count, 1) if total_members_count > 0 else 0.0
        attendance_rate_pct = round((active_members_count / total_members_count) * 100.0, 1) if total_members_count > 0 else 0.0
        watch_bound_rate_pct = round((watch_bound_count / total_members_count) * 100.0, 1) if total_members_count > 0 else 0.0
        org_completion_rate = round((total_distance_km / total_target_km) * 100.0, 1) if total_target_km > 0 else 0.0

        tot_pace_m = sum(m["pace_distance_m"] for m in member_rankings)
        tot_pace_s = sum(m["pace_moving_s"] for m in member_rankings)
        if tot_pace_m > 0 and tot_pace_s > 0:
            sec_km = int(round(tot_pace_s / (tot_pace_m / 1000.0)))
            avg_pace_str = f"{sec_km // 60}:{sec_km % 60:02d} /km"
        else:
            avg_pace_str = "—"

        # 4. Build WeChat Group Forward Text
        org_name = org.get("name") or "大群"
        lines = [
            f"🏛️ 【{org_name}】{period_label} · 分跑团 PK 战报",
            f"📅 统计周期：{date_range_str}（已按人跨团去重）",
            f"━━━━━━━━━━━━━━━━━━",
            f"📊 全群总跑量：{total_distance_km} km（人均 {avg_distance_km} km）",
            f"🏃 出勤活跃率：{active_members_count}/{total_members_count} 人（{attendance_rate_pct}%）",
            f"🏅 达标总人数：{achieved_members_count} 人 | 15km+ LSD：{lsd_15k_total} 人次",
            f"━━━━━━━━━━━━━━━━━━",
            f"🏆 【下属分跑团 PK 排行榜】",
        ]
        if sub_club_rankings:
            for c in sub_club_rankings:
                medal = "🥇" if c["rank"] == 1 else ("🥈" if c["rank"] == 2 else ("🥉" if c["rank"] == 3 else f"#{c['rank']}"))
                lines.append(
                    f"{medal} {c['club_name']}：人均 {c['avg_distance_km']} km | 总跑量 {c['total_distance_km']} km | 出勤 {c['active_member_count']}/{c['member_count']}人 ({c['attendance_rate_pct']}%)"
                )
        else:
            lines.append("暂无下属分跑团数据")

        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append("👑 【全群个人里程 TOP 5】")
        active_top = [m for m in member_rankings if m["distance_km"] > 0][:5]
        if active_top:
            for idx, m in enumerate(active_top):
                club_tag = " / ".join(m["sub_club_names"]) if m["sub_club_names"] else "未入分团"
                lines.append(f"{idx + 1}. {m['display_name']}（{club_tag}）：{m['distance_km']} km（{m['runs_count']}次 · 配速 {m['avg_pace_str']}）")
        else:
            lines.append("本期暂无个人打卡记录")

        forward_text = "\n".join(lines)
        qr_info = LocalStore.get_pure_miniapp_qrcode("release")

        ach_rate_org = round((achieved_members_count / total_members_count) * 100.0, 1) if total_members_count > 0 else 0.0
        return {
            "org_id": org_id,
            "org_name": org_name,
            "period_type": period_type,
            "period_label": period_label,
            "date_range_str": date_range_str,
            "start_date": start_date_obj.isoformat(),
            "end_date": end_date_obj.isoformat(),
            "is_past_period": is_past_period,
            "trail_mode": trail_mode_val,
            "trail_mode_label": trail_mode_label,
            "sub_clubs_count": len(sub_clubs),
            "total_members_count": total_members_count,
            "affiliated_members_count": total_members_count - len(unaffiliated_members),
            "unaffiliated_members_count": len(unaffiliated_members),
            "watch_bound_count": watch_bound_count,
            "watch_bound_rate_pct": watch_bound_rate_pct,
            "active_members_count": active_members_count,
            "attendance_rate_pct": attendance_rate_pct,
            "achieved_members_count": achieved_members_count,
            "total_distance_km": total_distance_km,
            "avg_distance_km": avg_distance_km,
            "total_target_km": total_target_km,
            "org_completion_rate": org_completion_rate,
            "total_runs_count": total_runs_count,
            "lsd_15k_total": lsd_15k_total,
            "lsd_25k_total": lsd_25k_total,
            "avg_pace_str": avg_pace_str,
            "summary": {
                "total_distance_km": total_distance_km,
                "avg_distance_km": avg_distance_km,
                "total_runs": total_runs_count,
                "sub_clubs_count": len(sub_clubs),
                "total_members": total_members_count,
                "unaffiliated_count": len(unaffiliated_members),
                "attendance_rate": attendance_rate_pct,
                "active_members": active_members_count,
                "target_km_threshold": 30 if period_type == "week" else 120,
                "achieved_count": achieved_members_count,
                "achievement_rate": ach_rate_org,
                "lsd_15k_count": lsd_15k_total,
                "lsd_25k_count": lsd_25k_total,
                "watch_bound_rate": watch_bound_rate_pct,
            },
            "sub_club_rankings": sub_club_rankings,
            "member_rankings": member_rankings,
            "unaffiliated_members": unaffiliated_members,
            "podium": active_top[:3],
            "forward_text": forward_text,
            "wechat_summary_text": forward_text,
            "qrcode_url": qr_info.get("qrcode_url", ""),
            "qrcode_base64": qr_info.get("qrcode_base64", ""),
        }

    @staticmethod
    def create_org_event(org_id: str, operator_uid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Allows Org Owner or Org Admin to create a cross-club event (group_run or distance_challenge)
        that automatically appears across all (or selected) sub-clubs of the organization.
        """
        if not LocalStore.is_org_organizer(org_id, operator_uid):
            raise PermissionError("无权限：仅大群主理人、大群管理员或超级管理员可发起跨跑团联合活动")
        org = LocalStore.get_organization(org_id)
        if not org:
            raise ValueError("大群不存在")

        sub_clubs = LocalStore.get_org_sub_clubs(org_id)
        host_club_id = (data.get("host_club_id") or "").strip()
        if not host_club_id:
            host_club_id = sub_clubs[0]["id"] if sub_clubs else f"org_host_{org_id}"

        raw_scope = data.get("scope_club_ids")
        if isinstance(raw_scope, list) and len(raw_scope) > 0:
            scope_str = json.dumps(raw_scope, ensure_ascii=False)
        elif isinstance(raw_scope, str) and raw_scope.strip():
            scope_str = raw_scope.strip()
        else:
            scope_str = "all"

        event_payload = {
            **data,
            "creator_id": operator_uid,
            "org_id": org_id,
            "is_org_event": True,
            "scope_club_ids": scope_str,
            "visibility_mode": data.get("visibility_mode") or "public",
        }
        first_event_id = LocalStore.create_club_event(host_club_id, event_payload)
        return {
            "success": True,
            "event_id": first_event_id,
            "event": {"id": first_event_id, "org_id": org_id, "host_club_id": host_club_id},
            "org_id": org_id,
            "host_club_id": host_club_id,
            "scope_club_ids": scope_str,
            "message": f"已成功发布【{org.get('name')}】跨跑团联合活动，已自动同步至下属跑团置顶展示！",
        }

    @staticmethod
    def get_org_events(org_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Returns all cross-club events for the organization, enriched with per-sub-club participation
        and mileage contribution breakdown (`club_breakdown`).
        """
        org = LocalStore.get_organization(org_id)
        if not org:
            raise ValueError("大群不存在")

        sub_clubs = LocalStore.get_org_sub_clubs(org_id)
        sub_club_ids = [sc["id"] for sc in sub_clubs]
        sub_club_name_map = {sc["id"]: sc["name"] for sc in sub_clubs}

        # Map each user in sub-clubs to their sub-club IDs and names
        user_clubs_map: Dict[str, List[Dict[str, str]]] = {}
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            for col_sql in [
                "ALTER TABLE club_events ADD COLUMN org_id TEXT DEFAULT NULL",
                "ALTER TABLE club_events ADD COLUMN is_org_event INTEGER DEFAULT 0",
                "ALTER TABLE club_events ADD COLUMN scope_club_ids TEXT DEFAULT 'all'",
            ]:
                try:
                    cursor.execute(col_sql)
                except Exception:
                    pass

            if sub_club_ids:
                ph = ",".join(["?"] * len(sub_club_ids))
                cursor.execute(
                    f"""
                    SELECT cm.user_id, cm.club_id, c.name as club_name
                    FROM club_memberships cm
                    JOIN clubs c ON cm.club_id = c.id
                    WHERE cm.club_id IN ({ph}) AND cm.status = 'active'
                    """,
                    sub_club_ids,
                )
                for r in cursor.fetchall():
                    uid = r["user_id"]
                    user_clubs_map.setdefault(uid, []).append({"id": r["club_id"], "name": r["club_name"]})

            if sub_club_ids:
                ph = ",".join(["?"] * len(sub_club_ids))
                cursor.execute(
                    f"""
                    SELECT * FROM club_events
                    WHERE org_id = ? OR club_id IN ({ph})
                    ORDER BY created_at DESC
                    """,
                    [org_id] + sub_club_ids,
                )
            else:
                cursor.execute("SELECT * FROM club_events WHERE org_id = ? ORDER BY created_at DESC", (org_id,))
            event_rows = [dict(r) for r in cursor.fetchall()]

        org_events: List[Dict[str, Any]] = []
        sub_club_events: List[Dict[str, Any]] = []

        for ev_row in event_rows:
            eid = ev_row["id"]
            cid = ev_row["club_id"]
            try:
                detail = LocalStore.get_club_event_detail(cid, eid, user_id=user_id)
            except Exception:
                detail = ev_row

            is_org_evt = bool(ev_row.get("is_org_event") or ev_row.get("org_id") == org_id)
            detail["is_org_event"] = is_org_evt
            detail["org_id"] = ev_row.get("org_id") or org_id
            detail["org_name"] = org.get("name")
            detail["host_club_name"] = sub_club_name_map.get(cid) or org.get("name")

            raw_scope = (ev_row.get("scope_club_ids") or "all").strip()
            if raw_scope == "all" or not raw_scope:
                detail["scope_club_ids"] = "all"
                detail["scope_club_names"] = [sc["name"] for sc in sub_clubs]
            else:
                try:
                    s_ids = json.loads(raw_scope)
                    detail["scope_club_ids"] = s_ids
                    detail["scope_club_names"] = [sub_club_name_map.get(x, x) for x in s_ids]
                except Exception:
                    detail["scope_club_ids"] = "all"
                    detail["scope_club_names"] = [sc["name"] for sc in sub_clubs]

            # Build per-sub-club breakdown for participants
            club_breakdown_map: Dict[str, Dict[str, Any]] = {
                sc["id"]: {
                    "club_id": sc["id"],
                    "club_name": sc["name"],
                    "participant_count": 0,
                    "registered_count": 0,
                    "completed_count": 0,
                    "total_actual_km": 0.0,
                    "total_km": 0.0,
                }
                for sc in sub_clubs
            }
            for p in detail.get("participants") or []:
                p_uid = p.get("user_id")
                p_clubs = user_clubs_map.get(p_uid) or []
                p["sub_club_names"] = [c["name"] for c in p_clubs]
                act_km = float(p.get("actual_distance_km") or p.get("manual_distance_km") or 0.0)
                for c in p_clubs:
                    if c["id"] in club_breakdown_map:
                        b = club_breakdown_map[c["id"]]
                        b["participant_count"] += 1
                        b["registered_count"] = b["participant_count"]
                        if act_km > 0:
                            b["completed_count"] += 1
                            b["total_actual_km"] = round(b["total_actual_km"] + act_km, 1)
                            b["total_km"] = b["total_actual_km"]

            breakdown_list = list(club_breakdown_map.values())
            breakdown_list.sort(key=lambda x: (x["total_actual_km"], x["participant_count"]), reverse=True)
            detail["club_breakdown"] = breakdown_list
            detail["participants_count"] = detail.get("participant_count") or len(detail.get("participants") or [])

            if is_org_evt:
                org_events.append(detail)
            else:
                sub_club_events.append(detail)

        return {
            "org_id": org_id,
            "org_name": org.get("name"),
            "org_events": org_events,
            "sub_club_events": sub_club_events,
            "sub_clubs": [{"id": sc["id"], "name": sc["name"], "member_count": sc.get("member_count", 0)} for sc in sub_clubs],
        }

    @staticmethod
    def purge_user_privacy_data(user_id: str) -> Dict[str, Any]:
        """
        Permanently wipes all sensitive personally identifiable information (PII) for the given user:
        - profiles: real_name, id_card, date_of_birth, phone, email, bio, wecom_webhook_url,
          Garmin & Coros credentials/tokens.
        - organization_members: removes member registration records.
        - resets display_name to anonymous '跑者_xxxx', avatar to default.
        - preserves activities, logs, and athletic mileage for club/team statistics.
        """
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, garmin_email, coros_account FROM profiles WHERE id = ?", (user_id,))
            old_row = cursor.fetchone()
            if not old_row:
                return {"success": False, "message": "用户不存在"}
            old_garmin_email = old_row["garmin_email"] or ""
            old_coros_account = old_row["coros_account"] or ""

            anon_name = f"跑者_{user_id[-4:]}" if len(user_id) >= 4 else "跑者_8888"
            default_avatar = "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80"

            cursor.execute("""
                UPDATE profiles
                SET real_name = '',
                    id_card = '',
                    date_of_birth = '',
                    phone = '',
                    email = '',
                    password_hash = '',
                    bio = '',
                    wecom_webhook_url = '',
                    garmin_connected = 0,
                    garmin_email = '',
                    garmin_encrypted_password = '',
                    coros_connected = 0,
                    coros_account = '',
                    coros_encrypted_password = '',
                    display_name = ?,
                    avatar_url = ?
                WHERE id = ?
            """, (anon_name, default_avatar, user_id))

            # Delete organization memberships so identity is erased from org rosters
            cursor.execute("DELETE FROM organization_members WHERE user_id = ?", (user_id,))

            conn.commit()

        # Remove local token files (Garmin / COROS / user_id-matched) if any exist
        try:
            from utils.garmin_adapter import remove_cached_garmin_tokens
            from utils.coros_adapter import remove_cached_coros_tokens
            remove_cached_garmin_tokens(old_garmin_email)
            remove_cached_coros_tokens(old_coros_account)
        except Exception as te:
            logger.warning(f"[privacy] Token cleanup notice: {te}")

        token_dir = os.path.join(DB_DIR, "tokens")
        if os.path.exists(token_dir):
            for fname in os.listdir(token_dir):
                if user_id in fname:
                    try:
                        os.remove(os.path.join(token_dir, fname))
                    except Exception:
                        pass

        return {
            "success": True,
            "message": "所有个人隐私数据（真实姓名、身份证号、出生日期、手机号及绑定手表凭证）已彻底安全清除！",
            "anonymized_display_name": anon_name
        }

    @staticmethod
    def confirm_org_member(org_id: str, target_uid: str, operator_uid: Optional[str] = None) -> bool:
        status_info = LocalStore.check_org_member_status(org_id, target_uid)
        if not status_info.get("is_member"):
            return False
        missing = status_info.get("missing_fields", [])
        if len(missing) > 0:
            missing_labels = [m.get("label", m.get("field")) for m in missing]
            raise ValueError(f"该队员必填资料尚未补齐（缺：{'、'.join(missing_labels)}），暂无法核验转正！")

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat() + "Z"
            cursor.execute("""
                UPDATE organization_members 
                SET status = 'confirmed', confirmed_at = ?, confirmed_by = ?
                WHERE org_id = ? AND user_id = ?
            """, (now, operator_uid or "admin", org_id, target_uid))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def grant_member_grace_period(org_id: str, target_uid: str) -> bool:
        """
        Allows Admin or Owner to grant a fresh 14-day temporary grace period to an expired member.
        """
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat() + "Z"
            cursor.execute("""
                UPDATE organization_members
                SET status = 'temporary', joined_at = ?, confirmed_at = NULL, confirmed_by = NULL
                WHERE org_id = ? AND user_id = ?
            """, (now, org_id, target_uid))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def update_org_member_role(org_id: str, target_uid: str, new_role: str, operator_uid: Optional[str] = None) -> bool:
        """
        Allows Organization Owner or Super Admin to appoint/revoke Admin role for an organization member.
        """
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT owner_id FROM organizations WHERE id = ?", (org_id,))
            org = cursor.fetchone()
            if not org:
                raise ValueError("组织不存在")

            owner_id = org["owner_id"]
            if operator_uid not in (owner_id, "super_admin", "admin"):
                cursor.execute("SELECT role FROM organization_members WHERE org_id = ? AND user_id = ?", (org_id, operator_uid))
                op_row = cursor.fetchone()
                if not op_row or op_row["role"] != "owner":
                    raise ValueError("只有大群主理人或超级管理员有权委派或调整大群管理员角色")

            if target_uid == owner_id and new_role != "owner":
                raise ValueError("不能修改大群主理人的身份角色")

            if new_role not in ("admin", "member"):
                raise ValueError("目标角色必须为 admin 或 member")

            cursor.execute("SELECT * FROM organization_members WHERE org_id = ? AND user_id = ?", (org_id, target_uid))
            target_mem = cursor.fetchone()
            if not target_mem:
                raise ValueError("未找到该大群成员")

            cursor.execute("""
                UPDATE organization_members
                SET role = ?
                WHERE org_id = ? AND user_id = ?
            """, (new_role, org_id, target_uid))
            conn.commit()
            return True

    @staticmethod
    def list_all_organizations() -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT o.*,
                       p.display_name as owner_name,
                       p.avatar_url as owner_avatar,
                       p.email as owner_email,
                       (SELECT COUNT(*) FROM organization_members m WHERE m.org_id = o.id) as member_count,
                       (SELECT COUNT(*) FROM clubs c WHERE c.org_id = o.id) as sub_clubs_count
                FROM organizations o
                LEFT JOIN profiles p ON o.owner_id = p.id
                ORDER BY o.created_at ASC
            """)
            items = [dict(r) for r in cursor.fetchall()]
            for item in items:
                item["field_rules"] = LocalStore.get_org_field_rules(item["id"])
            return items

    @staticmethod
    def create_organization(name: str, invite_code: str, description: Optional[str] = None, city: str = "上海", logo_url: Optional[str] = None, owner_id: Optional[str] = None, join_mode: str = "invite") -> Dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            org_id = f"org_{int(datetime.utcnow().timestamp()*1000)}"
            code = (invite_code or "").strip().upper()
            logo = logo_url or "https://rgm.vanpower.net/api/avatars/rgm-logo.png"
            created_at = datetime.utcnow().isoformat() + "Z"
            cursor.execute("""
                INSERT INTO organizations (id, name, logo_url, description, city, invite_code, owner_id, created_at, join_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (org_id, name.strip(), logo, description, city, code, owner_id, created_at, join_mode))

            if owner_id:
                cursor.execute("SELECT display_name FROM profiles WHERE id = ?", (owner_id,))
                p_tmp = cursor.fetchone()
                o_name = p_tmp[0] if p_tmp and p_tmp[0] else "大群主理人"
                enc_name = encrypt_pii(o_name)
                cursor.execute("""
                    INSERT OR IGNORE INTO organization_members (
                        id, org_id, user_id, real_name, gender, date_of_birth, class_name, role, status, joined_at, confirmed_at, confirmed_by
                    ) VALUES (?, ?, ?, ?, 'male', '1988-08-08', '大群主理人', 'owner', 'confirmed', ?, ?, 'admin')
                """, (f"{org_id}_{owner_id}", org_id, owner_id, enc_name, created_at, created_at))

            conn.commit()
            return {
                "id": org_id,
                "name": name.strip(),
                "invite_code": code,
                "join_mode": join_mode,
                "description": description,
                "logo_url": logo,
                "city": city,
                "owner_id": owner_id,
                "created_at": created_at
            }

    @staticmethod
    def update_organization(org_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            allowed = ["name", "description", "city", "logo_url", "invite_code", "owner_id", "join_mode"]
            set_clauses = []
            params = []
            for k in allowed:
                if k in data and data[k] is not None:
                    val = data[k]
                    if k == "invite_code":
                        val = str(val).strip().upper()
                    elif isinstance(val, str):
                        val = val.strip()
                    set_clauses.append(f"{k} = ?")
                    params.append(val)
            if not set_clauses:
                return LocalStore.get_organization_admin(org_id)
            params.append(org_id)
            cursor.execute(f"UPDATE organizations SET {', '.join(set_clauses)} WHERE id = ?", tuple(params))
            conn.commit()
            return LocalStore.get_organization_admin(org_id)

    @staticmethod
    def update_organization_join_mode(
        org_id: str,
        operator_uid: str,
        join_mode: Optional[str] = None,
        invite_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Allows organization organizer (owner / admin) to switch between 'free' and 'invite',
        and update/generate invite_code.
        """
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
            org_row = cursor.fetchone()
            if not org_row:
                raise ValueError("大群体组织不存在！")
            org = dict(org_row)

            # Permission check: operator must be owner or admin of this org, or system admin
            cursor.execute("SELECT role FROM organization_members WHERE org_id = ? AND user_id = ?", (org_id, operator_uid))
            mem_row = cursor.fetchone()
            mem_role = mem_row["role"] if mem_row else None

            is_sys_admin = (operator_uid in ("admin", "super_admin"))
            is_org_owner = (org.get("owner_id") == operator_uid) or (mem_role == "owner")
            is_org_admin = (mem_role == "admin") or is_org_owner or is_sys_admin

            if not is_org_admin:
                raise PermissionError("只有大群组织者（主理人或管理员）有权修改入会规则与专属邀请码！")

            set_clauses = []
            params = []

            if join_mode:
                if join_mode not in ("free", "invite"):
                    raise ValueError("入会规则仅支持 'free' (自由入会) 或 'invite' (凭专属邀请码入会)")
                set_clauses.append("join_mode = ?")
                params.append(join_mode)

            if invite_code is not None:
                clean_code = invite_code.strip().upper()
                if not clean_code:
                    raise ValueError("专属邀请码不能为空！")
                if len(clean_code) < 3 or len(clean_code) > 20:
                    raise ValueError("邀请码长度建议在 3 到 20 位之间！")

                # Check uniqueness against other organizations
                cursor.execute("SELECT id FROM organizations WHERE UPPER(invite_code) = ? AND id != ?", (clean_code, org_id))
                if cursor.fetchone():
                    raise ValueError(f"该专属邀请码【{clean_code}】已被其他大群使用，请更换一个！")
                # Check uniqueness against clubs
                cursor.execute("SELECT id FROM clubs WHERE UPPER(invite_code) = ?", (clean_code,))
                if cursor.fetchone():
                    raise ValueError(f"该专属邀请码【{clean_code}】已被跑团使用，请更换一个！")

                set_clauses.append("invite_code = ?")
                params.append(clean_code)

            if set_clauses:
                params.append(org_id)
                cursor.execute(f"UPDATE organizations SET {', '.join(set_clauses)} WHERE id = ?", tuple(params))
                conn.commit()

            cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
            updated_org = dict(cursor.fetchone())
            updated_org["field_rules"] = LocalStore.get_org_field_rules(org_id)
            return updated_org

    @staticmethod
    def create_system_notification(
        user_id: str,
        title: str,
        content: str,
        activity_id: Optional[str] = None,
        notif_type: str = "coach_critique",
        wechat_sent: int = 0,
        wechat_errmsg: Optional[str] = None
    ) -> Dict[str, Any]:
        notif_id = f"notif_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
        now_str = get_beijing_iso()
        canonical_uid = LocalStore.resolve_user_id(user_id)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO system_notifications (id, user_id, activity_id, title, content, type, wechat_sent, wechat_errmsg, is_read, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """, (notif_id, canonical_uid, activity_id, title, content, notif_type, wechat_sent, wechat_errmsg, now_str))
            conn.commit()
            return {
                "id": notif_id,
                "user_id": canonical_uid,
                "activity_id": activity_id,
                "title": title,
                "content": content,
                "type": notif_type,
                "wechat_sent": wechat_sent,
                "wechat_errmsg": wechat_errmsg,
                "is_read": 0,
                "created_at": now_str
            }

    @staticmethod
    def get_user_notifications(user_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, activity_id, title, content, type, wechat_sent, wechat_errmsg, is_read, created_at
                FROM system_notifications
                WHERE user_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
            """, (canonical_uid, limit))
            notifs = []
            for r in cursor.fetchall():
                nd = dict(r)
                nd["created_at"] = to_beijing_iso(nd.get("created_at"))
                notifs.append(nd)
            return notifs

    @staticmethod
    def mark_notification_as_read(notif_id: str, user_id: str) -> bool:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE system_notifications SET is_read = 1 WHERE id = ? AND user_id = ?
            """, (notif_id, canonical_uid))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def mark_all_notifications_read(user_id: str) -> int:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE system_notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0
            """, (canonical_uid,))
            conn.commit()
            return cursor.rowcount

    @staticmethod
    def get_unread_notifications_count(user_id: str) -> int:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM system_notifications WHERE user_id = ? AND is_read = 0
            """, (canonical_uid,))
            row = cursor.fetchone()
            return row[0] if row else 0

    @staticmethod
    def get_user_activity_count(user_id: str) -> int:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM activities WHERE user_id = ?", (canonical_uid,))
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    @staticmethod
    def get_user_onboarding_status(user_id: str) -> Dict[str, Any]:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        profile = LocalStore.get_profile(canonical_uid) or {}

        # Step 1: Profile (Name and at least gender or physical metrics)
        has_name = bool(profile.get("display_name") and profile.get("display_name") != "微信跑者")
        has_gender = bool(profile.get("gender"))
        has_detail = bool(profile.get("date_of_birth") or profile.get("height_cm") or profile.get("weight_kg"))
        profile_done = has_name and (has_gender or has_detail)

        # Step 2: Club (Joined at least 1 club, or explicitly chose solo runner)
        user_clubs = LocalStore.get_user_clubs(canonical_uid)
        is_solo = bool(profile.get("is_solo_runner"))
        club_done = len(user_clubs) > 0 or is_solo

        # Step 3: Device (Watch: Garmin, COROS, Apple Watch, Huawei Watch, or Suunto connected, or explicitly skipped)
        has_garmin = bool(profile.get("garmin_connected"))
        has_coros = bool(profile.get("coros_connected"))
        has_apple_watch = bool(profile.get("apple_watch_connected"))
        has_huawei = bool(profile.get("huawei_connected"))
        has_suunto = bool(profile.get("suunto_connected"))
        device_skipped = bool(profile.get("device_skipped"))
        device_done = has_garmin or has_coros or has_apple_watch or has_huawei or has_suunto or device_skipped

        # Step 4: History (Imported activities, or explicitly skipped)
        act_count = LocalStore.get_user_activity_count(canonical_uid)
        history_skipped = bool(profile.get("history_skipped"))
        history_done = act_count > 0 or history_skipped

        # Step 5: Training Goals (Explicitly saved in goals table)
        goal = LocalStore.get_goal(canonical_uid)
        target_dist = float(goal.get("target_distance") or 200.0)
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT target_distance FROM goals WHERE user_id = ? OR user_id = ?", (canonical_uid, user_id))
            goal_row = c.fetchone()
        goals_done = bool(goal_row and float(goal_row[0] or 0) > 0)

        steps = {
            "profile": profile_done,
            "club": club_done,
            "device": device_done,
            "history": history_done,
            "goals": goals_done
        }
        completed_count = sum(1 for v in steps.values() if v)
        explicit_completed = bool(profile.get("onboarding_completed"))
        is_completed = explicit_completed or (completed_count == 5)

        return {
            "is_completed": is_completed,
            "completed_count": completed_count,
            "total_steps": 5,
            "percent": int((completed_count / 5.0) * 100),
            "steps": steps,
            "details": {
                "display_name": profile.get("display_name") or "微信跑者",
                "avatar_url": profile.get("avatar_url") or "",
                "gender": profile.get("gender") or "male",
                "date_of_birth": profile.get("date_of_birth") or "",
                "height_cm": profile.get("height_cm") or 175.0,
                "weight_kg": profile.get("weight_kg") or 65.0,
                "years_running": profile.get("years_running") or 1,
                "has_club": len(user_clubs) > 0,
                "user_clubs": [{"id": c["id"], "name": c["name"]} for c in user_clubs],
                "is_solo_runner": is_solo,
                "garmin_connected": has_garmin,
                "coros_connected": has_coros,
                "apple_watch_connected": has_apple_watch,
                "huawei_connected": has_huawei,
                "huawei_account": profile.get("huawei_account") or "",
                "suunto_connected": has_suunto,
                "suunto_account": profile.get("suunto_account") or "",
                "device_skipped": device_skipped,
                "activity_count": act_count,
                "history_skipped": history_skipped,
                "target_distance": target_dist or 200.0,
                "hide_gps_route": bool(profile.get("hide_gps_route")),
                "hide_biometrics": bool(profile.get("hide_biometrics")),
            }
        }

    @staticmethod
    def update_onboarding_action(user_id: str, action: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        updates = {}
        if action == "skip_club_solo":
            updates["is_solo_runner"] = 1
        elif action == "skip_device":
            updates["device_skipped"] = 1
        elif action == "skip_history":
            updates["history_skipped"] = 1
        elif action == "complete_onboarding":
            updates["onboarding_completed"] = 1
            if payload:
                for k in ("is_solo_runner", "device_skipped", "history_skipped", "onboarding_completed", "hide_gps_route", "hide_biometrics"):
                    if k in payload:
                        updates[k] = payload[k]

        if updates:
            LocalStore.upsert_profile(canonical_uid, updates)

        return LocalStore.get_user_onboarding_status(canonical_uid)

    @staticmethod
    def create_support_ticket(
        user_id: str,
        category: str,
        content: str,
        contact_info: Optional[str] = None,
        client_env: Optional[str] = None,
        device_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        profile = LocalStore.get_profile(canonical_uid) or {}
        clubs = LocalStore.get_user_clubs(canonical_uid) or []
        act_count = LocalStore.get_user_activity_count(canonical_uid)

        connected_watch = "未连接"
        if profile.get("garmin_connected"):
            connected_watch = f"Garmin ({profile.get('garmin_email') or ''} / {profile.get('garmin_domain') or 'garmin.cn'})"
        elif profile.get("coros_connected"):
            connected_watch = f"COROS ({profile.get('coros_account') or ''})"
        elif profile.get("apple_watch_connected"):
            connected_watch = "Apple Watch"
        elif profile.get("huawei_connected"):
            connected_watch = f"华为手表 ({profile.get('huawei_account') or '华为运动健康'})"
        elif profile.get("suunto_connected"):
            connected_watch = f"颂拓 Suunto ({profile.get('suunto_account') or 'Suunto App'})"

        diag: Dict[str, Any] = {
            "uid": canonical_uid,
            "display_name": profile.get("display_name") or "微信跑者",
            "phone": profile.get("phone") or "",
            "watch": connected_watch,
            "watch_status": connected_watch,
            "clubs": [c.get("name") for c in clubs if c.get("name")],
            "activity_count": act_count,
            "client_env": client_env or "mp-weixin",
        }
        if isinstance(device_info, dict):
            for k, v in device_info.items():
                if v and k not in diag:
                    diag[k] = v

        now_iso = get_beijing_iso()
        ticket_id = f"tkt_{int(time.time())}_{hashlib.md5(f'{canonical_uid}:{now_iso}'.encode()).hexdigest()[:6]}"

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO support_tickets
                (id, user_id, display_name, category, content, contact_info, diagnostic_context, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)
                """,
                (
                    ticket_id,
                    canonical_uid,
                    diag["display_name"],
                    category or "general",
                    content.strip(),
                    (contact_info or "").strip(),
                    json.dumps(diag, ensure_ascii=False),
                    now_iso,
                ),
            )
            conn.commit()

        return {
            "id": ticket_id,
            "user_id": canonical_uid,
            "display_name": diag["display_name"],
            "category": category or "general",
            "content": content.strip(),
            "contact_info": (contact_info or "").strip(),
            "diagnostic": diag,
            "device_info": diag,
            "clubs": diag["clubs"],
            "status": "open",
            "admin_reply": None,
            "replied_at": None,
            "created_at": now_iso,
        }

    @staticmethod
    def get_user_support_tickets(user_id: str) -> List[Dict[str, Any]]:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM support_tickets
                WHERE user_id = ? OR user_id = ?
                ORDER BY created_at DESC
                LIMIT 30
                """,
                (canonical_uid, user_id),
            )
            rows = cursor.fetchall()
            out = []
            for r in rows:
                d = dict(r)
                try:
                    diag = json.loads(d.get("diagnostic_context") or "{}")
                except Exception:
                    diag = {}
                d["diagnostic"] = diag
                d["device_info"] = diag
                d["clubs"] = diag.get("clubs") or []
                d["created_at"] = to_beijing_iso(d.get("created_at"))
                d["replied_at"] = to_beijing_iso(d.get("replied_at"))
                out.append(d)
            return out

    @staticmethod
    def list_all_support_tickets(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if status_filter and status_filter in ("open", "resolved"):
                cursor.execute(
                    "SELECT * FROM support_tickets WHERE status = ? ORDER BY created_at DESC LIMIT 200",
                    (status_filter,),
                )
            else:
                cursor.execute("SELECT * FROM support_tickets ORDER BY CASE WHEN status = 'open' THEN 0 ELSE 1 END, created_at DESC LIMIT 200")
            rows = cursor.fetchall()
            out = []
            for r in rows:
                d = dict(r)
                try:
                    diag = json.loads(d.get("diagnostic_context") or "{}")
                except Exception:
                    diag = {}
                d["diagnostic"] = diag
                d["device_info"] = diag
                d["clubs"] = diag.get("clubs") or []
                d["created_at"] = to_beijing_iso(d.get("created_at"))
                d["replied_at"] = to_beijing_iso(d.get("replied_at"))
                out.append(d)
            return out

    @staticmethod
    def reply_support_ticket(ticket_id: str, admin_reply: str, status: str = "resolved") -> Optional[Dict[str, Any]]:
        now_iso = get_beijing_iso()
        clean_status = status if status in ("open", "resolved") else "resolved"
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE support_tickets
                SET admin_reply = ?, status = ?, replied_at = ?
                WHERE id = ?
                """,
                (admin_reply.strip(), clean_status, now_iso, ticket_id),
            )
            conn.commit()
            cursor.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["diagnostic"] = json.loads(d.get("diagnostic_context") or "{}")
            except Exception:
                d["diagnostic"] = {}
            return d

    # ── Mentorship (师傅/徒弟 1对1 结对，1位师傅最多带3位队员，同大群内支持跨跑团) & Data Confidentiality ──

    @staticmethod
    def is_mentor_of_runner(mentor_uid: Optional[str], mentee_uid: Optional[str]) -> bool:
        """Checks whether mentor_uid is the active 1-on-1 mentor (师傅) of mentee_uid."""
        if not mentor_uid or not mentee_uid:
            return False
        m_uid = LocalStore.resolve_user_id(mentor_uid)
        s_uid = LocalStore.resolve_user_id(mentee_uid)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1 FROM mentor_relationships
                WHERE (mentor_id = ? OR mentor_id = ?)
                  AND (mentee_id = ? OR mentee_id = ?)
                  AND status = 'active'
                LIMIT 1
                """,
                (m_uid, mentor_uid, s_uid, mentee_uid),
            )
            return cursor.fetchone() is not None

    @staticmethod
    def is_coach_of_runner(coach_uid: Optional[str], runner_uid: Optional[str], club_id: Optional[str] = None) -> bool:
        """Checks whether coach_uid is a certified coach (role='coach') in any club that runner_uid belongs to."""
        if not coach_uid or not runner_uid:
            return False
        c_uid = LocalStore.resolve_user_id(coach_uid)
        r_uid = LocalStore.resolve_user_id(runner_uid)
        if c_uid in LocalStore.SUPER_ADMIN_UIDS or coach_uid in LocalStore.SUPER_ADMIN_UIDS:
            return True
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if club_id:
                cursor.execute(
                    """
                    SELECT 1 FROM club_memberships
                    WHERE club_id = ? AND (user_id = ? OR user_id = ?) AND role = 'coach'
                    LIMIT 1
                    """,
                    (club_id, c_uid, coach_uid),
                )
                if cursor.fetchone() is not None:
                    return True
            cursor.execute(
                """
                SELECT 1 FROM club_memberships cm_coach
                INNER JOIN club_memberships cm_runner ON cm_coach.club_id = cm_runner.club_id
                WHERE (cm_coach.user_id = ? OR cm_coach.user_id = ?)
                  AND cm_coach.role = 'coach'
                  AND (cm_runner.user_id = ? OR cm_runner.user_id = ?)
                LIMIT 1
                """,
                (c_uid, coach_uid, r_uid, runner_uid),
            )
            return cursor.fetchone() is not None

    @staticmethod
    def can_view_confidential_runner_data(
        viewer_uid: Optional[str],
        target_uid: Optional[str],
        club_id: Optional[str] = None
    ) -> bool:
        """
        Determines whether viewer_uid can view target_uid's confidential GPS routes and HRV/biometric data.
        Authorized viewers:
        1. The runner themselves
        2. The runner's certified Coach (教练)
        3. The runner's bound 1-on-1 Mentor (师傅)
        4. Platform Super Admin
        """
        if not viewer_uid or not target_uid:
            return False
        v_uid = LocalStore.resolve_user_id(viewer_uid)
        t_uid = LocalStore.resolve_user_id(target_uid)
        if v_uid == t_uid or viewer_uid == target_uid:
            return True
        if v_uid in LocalStore.SUPER_ADMIN_UIDS or viewer_uid in LocalStore.SUPER_ADMIN_UIDS:
            return True
        if LocalStore.is_mentor_of_runner(v_uid, t_uid):
            return True
        if LocalStore.is_coach_of_runner(v_uid, t_uid, club_id=club_id):
            return True
        return False

    @staticmethod
    def apply_activity_privacy_filter(
        act: Dict[str, Any],
        viewer_uid: Optional[str],
        club_id: Optional[str] = None,
        profile_cache: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Enforces hide_gps_route and hide_biometrics on an activity dictionary when viewed in club feeds.
        Only the runner themselves, their Coach (教练), and their Mentor (师傅) can see confidential fields.
        """
        if not act:
            return act
        owner_uid = act.get("user_id")
        if not owner_uid:
            return act

        if profile_cache is not None and owner_uid in profile_cache:
            owner_prof = profile_cache[owner_uid]
            canonical_owner = str(owner_prof.get("id") or owner_uid)
        else:
            canonical_owner = LocalStore.resolve_user_id(owner_uid)
            if profile_cache is not None and canonical_owner in profile_cache:
                owner_prof = profile_cache[canonical_owner]
            else:
                owner_prof = LocalStore.get_profile(canonical_owner) or {}
                if profile_cache is not None:
                    profile_cache[canonical_owner] = owner_prof
                    profile_cache[owner_uid] = owner_prof

        hide_gps = bool(owner_prof.get("hide_gps_route"))
        hide_bio = bool(owner_prof.get("hide_biometrics"))
        act["owner_hide_gps_route"] = hide_gps
        act["owner_hide_biometrics"] = hide_bio

        if not hide_gps and not hide_bio:
            act["is_gps_hidden"] = False
            act["is_biometrics_hidden"] = False
            return act

        perm_key = f"__perm:{viewer_uid or ''}:{canonical_owner}:{club_id or ''}"
        if profile_cache is not None and perm_key in profile_cache:
            can_view = bool(profile_cache[perm_key].get("allow"))
        else:
            can_view = LocalStore.can_view_confidential_runner_data(viewer_uid, canonical_owner, club_id=club_id)
            if profile_cache is not None:
                profile_cache[perm_key] = {"allow": can_view}
        if hide_gps and not can_view:
            act["gps_track_data"] = None
            act["map_image_url"] = None
            act["has_gps_track"] = False
            act["is_gps_hidden"] = True
        else:
            act["is_gps_hidden"] = False

        if hide_bio and not can_view:
            act["average_heartrate"] = None
            act["max_heartrate"] = None
            act["trimp"] = None
            act["is_biometrics_hidden"] = True
        else:
            act["is_biometrics_hidden"] = False

        if (hide_gps or hide_bio) and not can_view:
            act["segment_analysis_json"] = None
            act["segment_analysis"] = None
            act["laps_data"] = None
            act["splits_data"] = None
            act["is_segment_hidden"] = True
        else:
            act["is_segment_hidden"] = False

        return act

    @staticmethod
    def _get_user_orgs_and_clubs(uid: str) -> Tuple[set, set]:
        """Returns (org_ids_set, club_ids_set) for a user across organization_members and club_members."""
        canonical_uid = LocalStore.resolve_user_id(uid)
        clubs = LocalStore.get_user_clubs(canonical_uid) or []
        club_ids = {c["id"] for c in clubs if c.get("id")}
        org_ids = {c["org_id"] for c in clubs if c.get("org_id")}
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT org_id FROM organization_members WHERE (user_id = ? OR user_id = ?) AND status != 'removed'",
                (canonical_uid, uid),
            )
            for row in cursor.fetchall():
                if row and row[0]:
                    org_ids.add(row[0])
        return org_ids, club_ids

    @staticmethod
    def bind_mentor_mentee(
        mentor_uid: str,
        mentee_uid: str,
        org_id: Optional[str] = None,
        club_id: Optional[str] = None,
        operator_uid: Optional[str] = None,
        via_invite: bool = False
    ) -> Dict[str, Any]:
        """
        Establishes a 1-on-1 mentorship relationship between mentor_uid (师傅) and mentee_uid (队员/徒弟).
        Rules:
        1. Mentor != Mentee
        2. 1-on-1 per mentee: Each mentee can have at most 1 active mentor at a time.
        3. Max 3 mentees per mentor: Each mentor can have at most 3 active mentees simultaneously.
        4. Cross-club within same Grand Org (`org_id`) OR within the same Club (`club_id`).
        """
        m_uid = LocalStore.resolve_user_id(mentor_uid)
        s_uid = LocalStore.resolve_user_id(mentee_uid)
        if not m_uid or not s_uid:
            raise ValueError("缺少师傅或队员的用户标识")
        if m_uid == s_uid:
            raise ValueError("不能将自己结对为自己的师傅或徒弟")

        # Ensure both users have profiles
        m_prof = LocalStore.get_profile(m_uid) or {"id": m_uid, "display_name": "师傅"}
        s_prof = LocalStore.get_profile(s_uid) or {"id": s_uid, "display_name": "队员"}
        m_name = m_prof.get("display_name") or "师傅"
        s_name = s_prof.get("display_name") or "队员"

        # If invited via WeChat card with a club_id and the newcomer hasn't joined that club yet, auto-join them
        if via_invite and club_id:
            m_orgs_tmp, m_clubs_tmp = LocalStore._get_user_orgs_and_clubs(m_uid)
            s_orgs_tmp, s_clubs_tmp = LocalStore._get_user_orgs_and_clubs(s_uid)
            if not (m_orgs_tmp & s_orgs_tmp) and not (m_clubs_tmp & s_clubs_tmp):
                target_join_uid = s_uid if club_id in m_clubs_tmp else (m_uid if club_id in s_clubs_tmp else None)
                if target_join_uid:
                    try:
                        LocalStore.join_club_by_id(
                            user_id=target_join_uid,
                            club_id=club_id,
                            privacy_consent=True,
                            via_invite=True,
                            inviter_uid=m_uid if target_join_uid == s_uid else s_uid,
                        )
                    except Exception as ex:
                        logger.warning(f"[mentorship] Auto join club on mentorship invite skipped: {ex}")

        m_orgs, m_clubs = LocalStore._get_user_orgs_and_clubs(m_uid)
        s_orgs, s_clubs = LocalStore._get_user_orgs_and_clubs(s_uid)
        shared_orgs = m_orgs & s_orgs
        shared_clubs = m_clubs & s_clubs

        if not shared_orgs and not shared_clubs:
            raise ValueError("师徒结对需在同一个大群（支持大群内跨跑团结对）或同一个跑团内进行")

        eff_org_id = org_id if (org_id and org_id in shared_orgs) else (next(iter(shared_orgs)) if shared_orgs else None)
        eff_club_id = club_id if (club_id and club_id in shared_clubs) else (next(iter(shared_clubs)) if shared_clubs else None)

        now_iso = datetime.utcnow().isoformat() + "Z"
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check if already bound to each other
            cursor.execute(
                """
                SELECT * FROM mentor_relationships
                WHERE mentor_id = ? AND mentee_id = ? AND status = 'active'
                LIMIT 1
                """,
                (m_uid, s_uid),
            )
            existing_same = cursor.fetchone()
            if existing_same:
                return {
                    "success": True,
                    "already_bound": True,
                    "relationship": dict(existing_same),
                    "message": f"【{m_name}】与【{s_name}】已是结对师徒关系！"
                }

            # Rule: Mentee can have at most 1 active mentor
            cursor.execute(
                """
                SELECT mr.*, COALESCE(NULLIF(p.display_name, ''), mr.mentor_id) AS mentor_name
                FROM mentor_relationships mr
                LEFT JOIN profiles p ON mr.mentor_id = p.id
                WHERE mr.mentee_id = ? AND mr.status = 'active'
                LIMIT 1
                """,
                (s_uid,),
            )
            existing_mentor_row = cursor.fetchone()
            if existing_mentor_row:
                ex_m_name = existing_mentor_row["mentor_name"] or "其他师傅"
                raise ValueError(f"每位队员只能结对 1 位师傅（【{s_name}】当前已拜师：{ex_m_name}），如需更换请先解除原师徒关系")

            # Rule: Mentor can have at most 3 active mentees
            cursor.execute(
                "SELECT COUNT(*) FROM mentor_relationships WHERE mentor_id = ? AND status = 'active'",
                (m_uid,),
            )
            current_mentees_count = int(cursor.fetchone()[0] or 0)
            if current_mentees_count >= 3:
                raise ValueError(f"每位师傅最多可同时带教 3 位队员（【{m_name}】当前已满 {current_mentees_count}/3 位）")

            rel_id = f"mtr_{int(time.time()*1000)}_{hashlib.md5(f'{m_uid}:{s_uid}'.encode()).hexdigest()[:6]}"
            cursor.execute(
                """
                INSERT INTO mentor_relationships (id, org_id, club_id, mentor_id, mentee_id, status, created_at, created_by)
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (rel_id, eff_org_id, eff_club_id, m_uid, s_uid, now_iso, operator_uid or m_uid),
            )
            conn.commit()

        # Send warm notifications
        try:
            LocalStore.create_system_notification(
                user_id=s_uid,
                title="🥋 师徒结对成功",
                content=f"您已与师傅【{m_name}】正式结为师徒！师傅现可查看您的全部训练与休息恢复数据，陪伴您科学无伤备战。",
                notif_type="mentorship_bound"
            )
            LocalStore.create_system_notification(
                user_id=m_uid,
                title="🥋 新增结对徒弟",
                content=f"您已与队员【{s_name}】正式结为师徒（当前带教 {current_mentees_count + 1}/3 位）！可在跑团页「我的师徒」随时查看其训练与恢复状态。",
                notif_type="mentorship_bound"
            )
        except Exception as e:
            logger.warning(f"[mentorship] Notification failed: {e}")

        return {
            "success": True,
            "already_bound": False,
            "relationship": {
                "id": rel_id,
                "org_id": eff_org_id,
                "club_id": eff_club_id,
                "mentor_id": m_uid,
                "mentor_name": m_name,
                "mentee_id": s_uid,
                "mentee_name": s_name,
                "status": "active",
                "created_at": now_iso,
            },
            "message": f"恭喜！【{m_name}】（师傅）与【{s_name}】（队员）已成功结为 1对1 师徒！"
        }

    @staticmethod
    def unbind_mentor_mentee(
        mentor_uid: str,
        mentee_uid: str,
        operator_uid: Optional[str] = None
    ) -> Dict[str, Any]:
        """Unbinds an active mentorship relationship between mentor_uid and mentee_uid."""
        m_uid = LocalStore.resolve_user_id(mentor_uid)
        s_uid = LocalStore.resolve_user_id(mentee_uid)
        op_uid = LocalStore.resolve_user_id(operator_uid) if operator_uid else m_uid

        if op_uid not in (m_uid, s_uid) and op_uid not in LocalStore.SUPER_ADMIN_UIDS:
            if not LocalStore.is_user_coach_or_owner(op_uid):
                raise PermissionError("仅师徒本人、跑团团长或大群管理员可解除师徒关系")

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE mentor_relationships
                SET status = 'unbound'
                WHERE (mentor_id = ? OR mentor_id = ?)
                  AND (mentee_id = ? OR mentee_id = ?)
                  AND status = 'active'
                """,
                (m_uid, mentor_uid, s_uid, mentee_uid),
            )
            conn.commit()
            changed = cursor.rowcount > 0

        if not changed:
            raise ValueError("未找到生效中的师徒关系")

        return {
            "success": True,
            "message": "师徒结对关系已解除"
        }

    @staticmethod
    def _build_mentee_training_and_rest_summary(mentee_uid: str, rel_row: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Compiles a comprehensive Training + Rest/Recovery summary for a mentee (队员/徒弟),
        including confidential GPS & HRV/Resting HR/Sleep/Recovery metrics.
        """
        uid = LocalStore.resolve_user_id(mentee_uid)
        profile = LocalStore.get_profile(uid) or {}
        today = get_beijing_today()
        month_start = date(today.year, today.month, 1).isoformat()

        # Clubs & Org names
        user_clubs = LocalStore.get_user_clubs(uid) or []
        clubs_names = [c.get("name") for c in user_clubs if c.get("name")]
        org_names = list({c.get("org_name") for c in user_clubs if c.get("org_name")})

        # Monthly & 7-day mileage
        month_m = LocalStore.get_month_distance_meters(uid, month_start)
        month_km = round(month_m / 1000.0, 1)
        goal_data = LocalStore.get_goal(uid) or {}
        monthly_targets = goal_data.get("monthly_targets") or [200.0] * 12
        cur_m_idx = today.month - 1
        target_km = float(monthly_targets[cur_m_idx] if cur_m_idx < len(monthly_targets) else goal_data.get("target_distance") or 200.0)
        completion_rate = round((month_km / target_km) * 100.0, 1) if target_km > 0 else 0.0

        recent_acts = LocalStore.get_recent_activities(uid, limit=60) or []
        seven_days_ago_iso = (today - timedelta(days=7)).isoformat()
        acts_7d = [
            a for a in recent_acts
            if str(a.get("start_time", ""))[:10] >= seven_days_ago_iso
            and LocalStore.is_running_activity(a.get("sport_type"))
        ]
        km_7d = round(sum(float(a.get("distance_meters") or 0) for a in acts_7d) / 1000.0, 1)
        runs_7d_count = len(acts_7d)

        # CTL / ATL / TSB
        if not recent_acts:
            ctl, atl, tsb = 0.0, 0.0, 0.0
            status_level, status_text = "none", "待同步首跑"
        else:
            from utils.running_metrics import compute_ctl_atl_tsb
            daily_trimp_map = {(today - timedelta(days=i)).isoformat(): 0.0 for i in range(90, -1, -1)}
            for a in recent_acts:
                st = str(a.get("start_time", ""))[:10]
                if st in daily_trimp_map:
                    daily_trimp_map[st] += float(a.get("trimp") or 0.0)
            series = sorted(daily_trimp_map.items(), key=lambda x: x[0])
            c_list = compute_ctl_atl_tsb(series)
            latest_m = c_list[-1] if c_list else {"ctl": 0.0, "atl": 0.0, "tsb": 0.0}
            ctl = round(float(latest_m.get("ctl") or 0.0), 1)
            atl = round(float(latest_m.get("atl") or 0.0), 1)
            tsb = round(ctl - atl, 1)
            if tsb > 5:
                status_level, status_text = "peak", "🟢 巅峰状态"
            elif tsb >= -30:
                status_level, status_text = "optimal", "🔵 专项适应"
            elif tsb >= -50:
                status_level, status_text = "tired", "🟡 疲劳累积"
            else:
                status_level, status_text = "danger", "🔴 过载预警"

        # Latest Rest & Recovery Metrics (daily_health) — strictly recent & authentic overnight wear only
        h = LocalStore.get_latest_health(uid) or {}
        recovery_avail = LocalStore.assess_recovery_data_availability(
            uid, health_row=h, profile=profile, recent_acts=recent_acts
        )
        if recovery_avail.get("recovery_data_available"):
            rhr = h.get("resting_heart_rate")
            hrv_ms = h.get("hrv_last_night_avg")
            hrv_weekly = h.get("hrv_weekly_avg")
            hrv_status = h.get("hrv_status") or "BALANCED"
            sleep_score = h.get("sleep_score")
            sleep_hrs = h.get("sleep_duration_hours")
            sleep_sec = h.get("sleep_duration_seconds")
            body_battery = h.get("body_battery_max")
            stress_avg = h.get("stress_avg")
        else:
            rhr = None
            hrv_ms = None
            hrv_weekly = None
            hrv_status = "MISSING"
            sleep_score = None
            sleep_hrs = None
            sleep_sec = None
            body_battery = None
            stress_avg = h.get("stress_avg")

        sleep_text = None
        if sleep_sec and float(sleep_sec) > 0:
            hrs = int(float(sleep_sec) // 3600)
            mins = int((float(sleep_sec) % 3600) // 60)
            sleep_text = f"{hrs}h {mins}m"
        elif sleep_hrs and float(sleep_hrs) > 0:
            hrs = int(float(sleep_hrs))
            mins = int(round((float(sleep_hrs) % 1) * 60))
            sleep_text = f"{hrs}h {mins}m"

        recovery_pct = LocalStore.compute_physiological_recovery_pct(h) if (h and recovery_avail.get("recovery_data_available")) else None

        # Active/Draft Plan & Week Execution
        active_plan = LocalStore.get_user_active_training_plan(uid, reconcile=True)
        draft_plan = LocalStore.get_user_draft_training_plan(uid, reconcile=False)
        exec_plan = active_plan or draft_plan
        today_str = today.isoformat()
        today_workout = None
        week_execution = None

        if exec_plan and exec_plan.get("schedule_data"):
            sched_obj = exec_plan.get("schedule_data") or {}
            weeks_list = sched_obj.get("weeks") or []
            cur_wk_idx = exec_plan.get("current_week_index") or 1
            cur_wk = next((w for w in weeks_list if w.get("week_index") == cur_wk_idx), weeks_list[0] if weeks_list else None)
            if cur_wk:
                days_arr = cur_wk.get("days") or []
                planned_km = round(sum(float(d.get("distance_km") or 0.0) for d in days_arr if d.get("workout_type") not in ("rest", "travel")), 1)
                actual_km = round(sum(
                    float(d.get("actual_distance_km") if d.get("actual_distance_km") is not None else (d.get("distance_km") if d.get("completed") else 0.0) or 0.0)
                    for d in days_arr if d.get("workout_type") not in ("rest", "travel")
                ), 1)
                run_days = [d for d in days_arr if d.get("workout_type") not in ("rest", "travel") and float(d.get("distance_km") or 0.0) > 0]
                workouts_total = len(run_days)
                workouts_completed = sum(1 for d in run_days if d.get("completed"))
                mileage_completion_pct = int(round(actual_km * 100.0 / planned_km)) if planned_km > 0 else (100 if actual_km > 0 else 0)

                days_brief = []
                for d_idx, d in enumerate(days_arr):
                    w_type_d = d.get("workout_type") or "easy_run"
                    p_km_d = float(d.get("distance_km") or 0.0)
                    a_km_d = d.get("actual_distance_km")
                    if w_type_d in ("rest", "travel"):
                        d_status = "rest"
                    elif bool(d.get("completed")):
                        d_status = "completed"
                    elif bool(d.get("is_missed")):
                        d_status = "missed"
                    else:
                        d_status = "pending"
                    d_item = {
                        "day_index": d_idx,
                        "day_of_week": d.get("day_of_week"),
                        "date": d.get("date"),
                        "status": d_status,
                        "workout_type": w_type_d,
                        "title": d.get("title"),
                        "description": d.get("description") or "",
                        "planned_km": p_km_d,
                        "actual_km": a_km_d if a_km_d is not None else (p_km_d if bool(d.get("completed")) else 0.0),
                        "target_pace": d.get("target_pace"),
                        "actual_pace": d.get("actual_pace"),
                        "actual_heartrate": d.get("actual_heartrate"),
                        "rpe": d.get("rpe"),
                        "feeling_tag": d.get("feeling_tag") or "",
                        "athlete_notes": d.get("athlete_notes") or "",
                        "workout_photos": d.get("workout_photos") or ([d["photo_url"]] if d.get("photo_url") else []),
                        "photo_url": (d.get("workout_photos")[0] if d.get("workout_photos") else (d.get("photo_url") or "")),
                        "hrv": d.get("hrv"),
                        "resting_hr": d.get("resting_hr"),
                        "recovery_pct": d.get("recovery_pct"),
                        "completed": bool(d.get("completed")),
                    }
                    days_brief.append(d_item)
                    if str(d.get("date") or "") == today_str:
                        today_workout = d_item
                        if recovery_avail.get("recovery_data_available") and recovery_pct is None and d.get("recovery_pct") is not None:
                            recovery_pct = d.get("recovery_pct")

                week_execution = {
                    "week_index": cur_wk.get("week_index") or 1,
                    "week_title": cur_wk.get("week_title") or f"第 {cur_wk.get('week_index') or 1} 周",
                    "planned_km": planned_km,
                    "actual_km": actual_km,
                    "mileage_completion_pct": mileage_completion_pct,
                    "workouts_total": workouts_total,
                    "workouts_completed": workouts_completed,
                    "today_workout": today_workout,
                    "days_brief": days_brief,
                }

        latest_act = None
        if recent_acts:
            a0 = recent_acts[0]
            dist_m0 = float(a0.get("distance_meters") or 0.0)
            has_gps0 = bool(a0.get("gps_track_data") or a0.get("map_image_url") or str(a0.get("id")).startswith(("garmin_", "coros_")))
            latest_act = {
                "id": a0.get("id"),
                "name": a0.get("name") or "跑步",
                "start_time": a0.get("start_time"),
                "distance_km": round(dist_m0 / 1000.0, 2),
                "moving_time_seconds": a0.get("moving_time_seconds") or 0,
                "avg_pace_str": a0.get("avg_pace_str") or "—",
                "average_heartrate": a0.get("average_heartrate"),
                "trimp": a0.get("trimp"),
                "has_gps_track": has_gps0,
            }

        rhr_int = int(rhr) if rhr is not None and float(rhr or 0) > 0 else None
        hrv_int = int(round(float(hrv_ms))) if hrv_ms is not None and float(hrv_ms or 0) > 0 else None
        hrv_wk_int = int(round(float(hrv_weekly))) if hrv_weekly is not None and float(hrv_weekly or 0) > 0 else None
        sleep_score_int = int(sleep_score) if sleep_score is not None and float(sleep_score or 0) > 0 else None
        sleep_hours_val = (
            round(float(sleep_sec) / 3600.0, 1)
            if (sleep_sec and float(sleep_sec) > 0)
            else (round(float(sleep_hrs), 1) if (sleep_hrs and float(sleep_hrs) > 0) else None)
        )
        vo2max_val = profile.get("vo2max")
        vdot_val = round(float(vo2max_val), 1) if vo2max_val and float(vo2max_val or 0) > 0 else None
        club_name_str = " · ".join(clubs_names) if clubs_names else (" · ".join(org_names) if org_names else "同大群跨团")

        rest_and_recovery_obj = {
            "status_code": status_level,
            "status_label": status_text,
            "tsb": tsb,
            "ctl": ctl,
            "atl": atl,
            "resting_hr": rhr_int,
            "hrv": hrv_int,
            "hrv_weekly_avg": hrv_wk_int,
            "sleep_score": sleep_score_int,
            "sleep_hours": sleep_hours_val,
            "sleep_duration_text": sleep_text,
            "recovery_pct": recovery_pct,
            "injury_notes": profile.get("injury_history") or "",
        }

        training_obj = {
            "today_workout": {
                **(today_workout or {}),
                "type": (today_workout or {}).get("title") or (today_workout or {}).get("workout_type") or "休息恢复",
                "target_km": (today_workout or {}).get("planned_km") or 0,
                "completed": bool((today_workout or {}).get("completed")),
            } if today_workout else None,
            "week_number": (week_execution or {}).get("week_index") or 1,
            "week_actual_km": (week_execution or {}).get("actual_km") if week_execution else km_7d,
            "week_planned_km": (week_execution or {}).get("planned_km") if week_execution else round(target_km / 4.0, 1),
            "week_compliance_pct": (week_execution or {}).get("mileage_completion_pct") if week_execution else completion_rate,
            "weekly_workouts": [
                {
                    **d,
                    "day": d.get("day_of_week") or f"D{d.get('day_index', 0) + 1}",
                    "type": d.get("title") or d.get("workout_type") or "常规训练",
                    "target_km": d.get("planned_km") or 0,
                }
                for d in ((week_execution or {}).get("days_brief") or [])
            ],
        }

        return {
            "user_id": uid,
            "mentee_uid": uid,
            "display_name": profile.get("display_name") or "跑者",
            "avatar_url": profile.get("avatar_url") or "",
            "gender": profile.get("gender") or "male",
            "vo2max": vo2max_val,
            "vdot": vdot_val,
            "club_name": club_name_str,
            "clubs_names": clubs_names,
            "org_names": org_names,
            "target_race_name": (exec_plan or {}).get("race_name") or goal_data.get("target_race_name") or "日常科学进阶",
            "target_finish_time": (exec_plan or {}).get("target_time") or goal_data.get("target_finish_time") or "健康无伤完赛",
            "relationship_id": rel_row.get("id") if rel_row else None,
            "bound_at": rel_row.get("created_at") if rel_row else None,
            "hide_gps_route": bool(profile.get("hide_gps_route")),
            "hide_biometrics": bool(profile.get("hide_biometrics")),
            # Nested structures for frontend cards & modal
            "rest_and_recovery": rest_and_recovery_obj,
            "training": training_obj,
            # Flat training metrics
            "month_km": month_km,
            "target_km": target_km,
            "completion_rate": completion_rate,
            "km_7d": km_7d,
            "runs_7d_count": runs_7d_count,
            "ctl": ctl,
            "atl": atl,
            "tsb": tsb,
            "status_level": status_level,
            "status_text": status_text,
            "today_workout": today_workout,
            "week_execution": week_execution,
            "latest_activity": latest_act,
            # Flat Rest & Recovery metrics
            "resting_heart_rate": rhr_int,
            "hrv_ms": hrv_int,
            "hrv_weekly_avg": hrv_wk_int,
            "hrv_status": hrv_status,
            "sleep_score": sleep_score_int,
            "sleep_duration_text": sleep_text,
            "body_battery_max": int(body_battery) if body_battery is not None and float(body_battery or 0) > 0 else None,
            "stress_avg": int(stress_avg) if stress_avg is not None and float(stress_avg or 0) > 0 else None,
            "recovery_pct": recovery_pct,
            "recovery_data_available": recovery_avail.get("recovery_data_available", False),
            "night_wear_missing": recovery_avail.get("night_wear_missing", False),
            "missing_recovery_fields": recovery_avail.get("missing_recovery_fields", []),
            "recovery_status_label": recovery_avail.get("recovery_status_label", ""),
            "recovery_data_warning": recovery_avail.get("coach_warning") if not recovery_avail.get("recovery_data_available") else None,
        }

    @staticmethod
    def get_mentorship_overview(
        uid: str,
        org_id: Optional[str] = None,
        club_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Returns the user's mentorship status:
        - my_mentor: The user's 1-on-1 Mentor (师傅), if bound (max 1).
        - my_mentees: List of up to 3 Mentees (徒弟/队员) with full Training + Rest/Recovery summaries.
        - candidates / eligible_candidates: Eligible runners across the same Grand Org (`org_id`, cross-club) or same `club_id`.
        """
        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. My Mentor (as mentee)
            cursor.execute(
                """
                SELECT * FROM mentor_relationships
                WHERE (mentee_id = ? OR mentee_id = ?) AND status = 'active'
                ORDER BY created_at DESC LIMIT 1
                """,
                (canonical_uid, uid),
            )
            mentor_rel = cursor.fetchone()

            # 2. My Mentees (as mentor, max 3)
            cursor.execute(
                """
                SELECT * FROM mentor_relationships
                WHERE (mentor_id = ? OR mentor_id = ?) AND status = 'active'
                ORDER BY created_at ASC LIMIT 3
                """,
                (canonical_uid, uid),
            )
            mentee_rels = [dict(r) for r in cursor.fetchall()]

            # All active relationships for candidate availability lookup
            cursor.execute("SELECT mentor_id, mentee_id FROM mentor_relationships WHERE status = 'active'")
            all_active_rels = cursor.fetchall()

        mentor_counts: Dict[str, int] = {}
        mentee_to_mentor: Dict[str, str] = {}
        for r in all_active_rels:
            m_id = LocalStore.resolve_user_id(r["mentor_id"])
            s_id = LocalStore.resolve_user_id(r["mentee_id"])
            mentor_counts[m_id] = mentor_counts.get(m_id, 0) + 1
            mentee_to_mentor[s_id] = m_id

        my_mentor = None
        if mentor_rel:
            m_rel_dict = dict(mentor_rel)
            m_uid = LocalStore.resolve_user_id(m_rel_dict["mentor_id"])
            m_prof = LocalStore.get_profile(m_uid) or {}
            m_clubs = LocalStore.get_user_clubs(m_uid) or []
            m_clubs_names = [c.get("name") for c in m_clubs if c.get("name")]
            m_org_names = list({c.get("org_name") for c in m_clubs if c.get("org_name")})
            m_vo2 = m_prof.get("vo2max")
            my_mentor = {
                "user_id": m_uid,
                "mentor_uid": m_uid,
                "display_name": m_prof.get("display_name") or "师傅",
                "avatar_url": m_prof.get("avatar_url") or "",
                "vo2max": m_vo2,
                "vdot": round(float(m_vo2), 1) if m_vo2 and float(m_vo2 or 0) > 0 else None,
                "club_name": " · ".join(m_clubs_names) if m_clubs_names else (" · ".join(m_org_names) if m_org_names else "同大群戈友"),
                "clubs_names": m_clubs_names,
                "org_names": m_org_names,
                "relationship_id": m_rel_dict.get("id"),
                "bound_at": m_rel_dict.get("created_at"),
                "mentee_count": mentor_counts.get(m_uid, 1),
            }

        my_mentees = []
        for rel in mentee_rels:
            s_uid = LocalStore.resolve_user_id(rel["mentee_id"])
            my_mentees.append(LocalStore._build_mentee_training_and_rest_summary(s_uid, rel_row=rel))

        # 3. Build cross-club (same Grand Org) + same-club candidate pool
        user_orgs, user_clubs = LocalStore._get_user_orgs_and_clubs(canonical_uid)
        target_orgs = {org_id} if (org_id and org_id in user_orgs) else user_orgs
        target_clubs = set(user_clubs)
        if club_id:
            target_clubs.add(club_id)

        candidate_map: Dict[str, Dict[str, Any]] = {}
        org_real_names: Dict[str, str] = {}
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Find all clubs belonging to target_orgs so we support cross-club within the same Grand Org
            if target_orgs:
                placeholders_org = ",".join(["?"] * len(target_orgs))
                cursor.execute(
                    f"SELECT id, name, org_id FROM clubs WHERE org_id IN ({placeholders_org}) AND COALESCE(status, 'active') != 'deleted'",
                    list(target_orgs),
                )
                for c_row in cursor.fetchall():
                    target_clubs.add(c_row["id"])

                # Also collect confirmed/active Grand Org members and their real_name
                cursor.execute(
                    f"""
                    SELECT om.user_id, om.org_id, om.real_name AS org_real_name, om.status,
                           p.display_name, p.avatar_url, p.vo2max, p.real_name AS prof_real_name
                    FROM organization_members om
                    LEFT JOIN profiles p ON om.user_id = p.id
                    WHERE om.org_id IN ({placeholders_org})
                      AND COALESCE(om.status, '') NOT IN ('removed', 'expired')
                    """,
                    list(target_orgs),
                )
                for om_row in cursor.fetchall():
                    c_uid = LocalStore.resolve_user_id(om_row["user_id"])
                    if not c_uid:
                        continue
                    raw_rn = om_row["org_real_name"] or om_row["prof_real_name"] or ""
                    dec_rn = (decrypt_pii(raw_rn) or "").strip() if raw_rn else ""
                    if dec_rn and not dec_rn.startswith("enc:"):
                        org_real_names[c_uid] = dec_rn
                    if c_uid == canonical_uid:
                        continue
                    if c_uid not in candidate_map:
                        has_m = c_uid in mentee_to_mentor
                        m_cnt = mentor_counts.get(c_uid, 0)
                        vo2_val = om_row["vo2max"]
                        candidate_map[c_uid] = {
                            "user_id": c_uid,
                            "base_display_name": om_row["display_name"] or dec_rn or "跑友",
                            "real_name": dec_rn,
                            "avatar_url": om_row["avatar_url"] or "",
                            "vo2max": vo2_val,
                            "vdot": round(float(vo2_val), 1) if vo2_val and float(vo2_val or 0) > 0 else None,
                            "clubs_names": [],
                            "org_id": om_row["org_id"],
                            "has_mentor": has_m,
                            "mentee_count": m_cnt,
                            "can_be_mentor": m_cnt < 3,
                            "can_be_mentee": not has_m,
                        }

            if target_clubs:
                placeholders_club = ",".join(["?"] * len(target_clubs))
                cursor.execute(
                    f"""
                    SELECT cm.user_id, cm.club_id, cm.role,
                           c.name AS club_name, c.org_id,
                           p.display_name, p.avatar_url, p.vo2max, p.real_name AS prof_real_name
                    FROM club_memberships cm
                    INNER JOIN clubs c ON cm.club_id = c.id
                    LEFT JOIN profiles p ON cm.user_id = p.id
                    WHERE cm.club_id IN ({placeholders_club})
                    """,
                    list(target_clubs),
                )
                for row in cursor.fetchall():
                    c_uid = LocalStore.resolve_user_id(row["user_id"])
                    if not c_uid or c_uid == canonical_uid:
                        continue
                    raw_rn = row["prof_real_name"] or ""
                    dec_rn = org_real_names.get(c_uid) or ((decrypt_pii(raw_rn) or "").strip() if raw_rn else "")
                    if dec_rn.startswith("enc:"):
                        dec_rn = ""
                    if c_uid not in candidate_map:
                        has_m = c_uid in mentee_to_mentor
                        m_cnt = mentor_counts.get(c_uid, 0)
                        vo2_val = row["vo2max"]
                        candidate_map[c_uid] = {
                            "user_id": c_uid,
                            "base_display_name": row["display_name"] or dec_rn or "跑友",
                            "real_name": dec_rn,
                            "avatar_url": row["avatar_url"] or "",
                            "vo2max": vo2_val,
                            "vdot": round(float(vo2_val), 1) if vo2_val and float(vo2_val or 0) > 0 else None,
                            "clubs_names": [row["club_name"]] if row["club_name"] else [],
                            "org_id": row["org_id"],
                            "has_mentor": has_m,
                            "mentee_count": m_cnt,
                            "can_be_mentor": m_cnt < 3,
                            "can_be_mentee": not has_m,
                        }
                    else:
                        if not candidate_map[c_uid].get("real_name") and dec_rn:
                            candidate_map[c_uid]["real_name"] = dec_rn
                        if not candidate_map[c_uid].get("avatar_url") and row["avatar_url"]:
                            candidate_map[c_uid]["avatar_url"] = row["avatar_url"]
                        if candidate_map[c_uid].get("vo2max") is None and row["vo2max"] is not None:
                            vo2_val = row["vo2max"]
                            candidate_map[c_uid]["vo2max"] = vo2_val
                            candidate_map[c_uid]["vdot"] = round(float(vo2_val), 1) if float(vo2_val or 0) > 0 else None
                        if row["club_name"] and row["club_name"] not in candidate_map[c_uid]["clubs_names"]:
                            candidate_map[c_uid]["clubs_names"].append(row["club_name"])

        candidates = []
        for cand in candidate_map.values():
            base_name = (cand.pop("base_display_name", None) or "跑友").strip()
            r_name = (cand.get("real_name") or "").strip()
            if r_name and r_name != base_name and r_name not in base_name:
                cand["display_name"] = f"{base_name} ({r_name})"
            else:
                cand["display_name"] = base_name
            c_names = cand.get("clubs_names") or []
            cand["club_name"] = " · ".join(c_names[:2]) if c_names else "同大群队友"
            candidates.append(cand)

        candidates.sort(key=lambda x: (not x["can_be_mentee"], x["display_name"]))
        remaining_slots = max(0, 3 - len(my_mentees))

        return {
            "user_id": canonical_uid,
            "my_mentor": my_mentor,
            "my_mentees": my_mentees,
            "mentee_count": len(my_mentees),
            "max_mentees": 3,
            "remaining_slots": remaining_slots,
            "remaining_mentee_slots": remaining_slots,
            "candidates": candidates,
            "eligible_candidates": candidates,
        }

    @staticmethod
    def get_mentee_full_detail(viewer_uid: str, mentee_uid: str) -> Dict[str, Any]:
        """
        Returns complete Training + Rest/Recovery data for mentee_uid.
        Strictly requires viewer_uid to be the bound 1-on-1 Mentor (师傅), certified Coach (教练),
        the runner themselves, or Super Admin.
        """
        v_uid = LocalStore.resolve_user_id(viewer_uid)
        s_uid = LocalStore.resolve_user_id(mentee_uid)
        if not LocalStore.can_view_confidential_runner_data(v_uid, s_uid):
            raise PermissionError("仅该队员结对的师傅或认证教练有权查看其完整训练与休息恢复数据")

        summary = LocalStore._build_mentee_training_and_rest_summary(s_uid)
        active_plan = LocalStore.get_user_active_training_plan(s_uid, reconcile=True)
        draft_plan = LocalStore.get_user_draft_training_plan(s_uid, reconcile=False)

        # Fetch last 14 days of rest & recovery logs from daily_health
        rest_logs = []
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT date, resting_heart_rate, sleep_score, sleep_duration_hours, sleep_duration_seconds,
                       nap_duration_seconds, body_battery_max, body_battery_min,
                       hrv_status, hrv_weekly_avg, hrv_last_night_avg, stress_avg, steps, active_calories
                FROM daily_health
                WHERE user_id = ? OR user_id = ?
                ORDER BY date DESC
                LIMIT 14
                """,
                (s_uid, mentee_uid),
            )
            for row in cursor.fetchall():
                d = LocalStore.sanitize_daily_health_row(dict(row)) or {}
                sleep_sec = d.get("sleep_duration_seconds")
                sleep_hrs = d.get("sleep_duration_hours")
                sleep_text = None
                if sleep_sec and float(sleep_sec) > 0:
                    hrs = int(float(sleep_sec) // 3600)
                    mins = int((float(sleep_sec) % 3600) // 60)
                    sleep_text = f"{hrs}h {mins}m"
                elif sleep_hrs and float(sleep_hrs) > 0:
                    hrs = int(float(sleep_hrs))
                    mins = int(round((float(sleep_hrs) % 1) * 60))
                    sleep_text = f"{hrs}h {mins}m"
                d["sleep_duration_text"] = sleep_text
                d["recovery_pct"] = LocalStore.compute_physiological_recovery_pct(d)
                rest_logs.append(d)

        # Fetch recent 15 running activities (unredacted for Mentor/Coach)
        raw_acts = LocalStore.get_recent_activities(s_uid, limit=15) or []
        recent_activities = []
        for a in raw_acts:
            dist_m = float(a.get("distance_meters") or 0.0)
            has_gps = bool(a.get("gps_track_data") or a.get("map_image_url") or str(a.get("id")).startswith(("garmin_", "coros_")))
            st_str = a.get("start_time") or ""
            pace_str = a.get("avg_pace_str") or "—"
            recent_activities.append({
                "id": a.get("id"),
                "name": a.get("name") or "跑步",
                "start_time": st_str,
                "start_date_local": st_str,
                "distance_km": round(dist_m / 1000.0, 2),
                "moving_time_seconds": a.get("moving_time_seconds") or 0,
                "avg_pace_str": pace_str,
                "avg_pace": pace_str,
                "average_heartrate": a.get("average_heartrate"),
                "max_heartrate": a.get("max_heartrate"),
                "elevation_gain_meters": round(float(a.get("elevation_gain_meters") or a.get("total_elevation_gain") or 0.0), 1),
                "trimp": a.get("trimp"),
                "ai_journal": a.get("ai_journal") or "",
                "has_gps_track": has_gps,
                "map_image_url": a.get("map_image_url"),
            })

        return {
            **summary,
            "summary": summary,
            "active_plan": active_plan or draft_plan,
            "rest_recovery_logs": rest_logs,
            "recent_activities": recent_activities,
        }

    # ── Official Pacer Evaluation & Club Pacer Assignment Helpers ──

    @staticmethod
    def get_cached_race_intel(cache_key: str) -> Optional[Dict[str, Any]]:
        if not cache_key:
            return None
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT * FROM race_intel_cache WHERE cache_key = ?", (cache_key,))
                row = cursor.fetchone()
                if not row:
                    return None
                d = dict(row)
                info = json.loads(d.get("race_info_json") or "{}")
                if not info:
                    return None
                return {
                    "event_name": d.get("event_name") or cache_key,
                    "race_category": d.get("race_category") or "road",
                    "race_info": info,
                    "source": d.get("source") or "cache",
                    "updated_at": d.get("updated_at"),
                }
            except Exception:
                return None

    @staticmethod
    def set_cached_race_intel(
        cache_key: str,
        event_name: str,
        race_category: str,
        race_info: Dict[str, Any],
        source: str = "official_web_search",
    ) -> None:
        if not cache_key or not race_info:
            return
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO race_intel_cache (
                        cache_key, event_name, race_category, race_info_json, source, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cache_key,
                        event_name or cache_key,
                        race_category or "road",
                        json.dumps(race_info, ensure_ascii=False),
                        source,
                        datetime.utcnow().isoformat() + "Z",
                    ),
                )
                conn.commit()
            except Exception as e:
                logger.warning(f"[race_intel_cache] Failed to persist {cache_key}: {e}")

    @staticmethod
    def get_user_group_run_pacer_records(uid: str) -> List[Dict[str, Any]]:
        """
        Fetches all club offline group-run / LSD events where the runner participated
        as a pacer ('🐰 领跑兔' / '领跑' / 'pacer'), including bound watch activity data.
        """
        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    SELECT
                        p.id AS participant_id,
                        p.event_id,
                        p.club_id,
                        p.pace_group,
                        p.runner_role,
                        p.manual_distance_km,
                        p.manual_pace_str,
                        p.activity_id,
                        e.title AS event_title,
                        e.start_date,
                        e.meet_time,
                        e.target_km AS event_target_km,
                        e.pace_requirement,
                        a.distance_meters AS act_distance_meters,
                        a.moving_time_seconds AS act_moving_time_seconds,
                        a.avg_pace_str AS act_avg_pace_str,
                        a.start_time AS act_start_time
                    FROM club_event_participants p
                    LEFT JOIN club_events e ON p.event_id = e.id
                    LEFT JOIN activities a ON p.activity_id = a.id
                    WHERE (p.user_id = ? OR p.user_id = ?)
                      AND p.status = 'joined'
                      AND (
                          p.runner_role LIKE '%兔%'
                          OR p.runner_role LIKE '%领跑%'
                          OR LOWER(p.runner_role) LIKE '%pacer%'
                      )
                    ORDER BY COALESCE(e.meet_time, e.start_date, p.joined_at) DESC
                    """,
                    (canonical_uid, uid),
                )
                return [dict(r) for r in cursor.fetchall()]
            except Exception as e:
                logger.warning(f"[pacer_records] Query failed for {canonical_uid}: {e}")
                return []

    @staticmethod
    def assign_event_pacer_by_coach(
        club_id: str,
        event_id: str,
        operator_uid: str,
        target_uid: str,
        pace_group: str = "",
        note: str = "",
    ) -> Dict[str, Any]:
        """
        Allows a club owner or coach to assign a candidate runner as '🐰 领跑兔' for a club event,
        upserting into club_event_participants and sending an in-app notification.
        """
        op_uid = LocalStore.resolve_user_id(operator_uid)
        tg_uid = LocalStore.resolve_user_id(target_uid)

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check operator permission: club owner, club coach, or platform super admin
            is_authorized = op_uid in LocalStore.SUPER_ADMIN_UIDS or operator_uid in LocalStore.SUPER_ADMIN_UIDS
            if not is_authorized:
                cursor.execute("SELECT owner_id, name FROM clubs WHERE id = ?", (club_id,))
                club_row = cursor.fetchone()
                if club_row and LocalStore.resolve_user_id(club_row["owner_id"] or "") == op_uid:
                    is_authorized = True
                else:
                    cursor.execute(
                        "SELECT role FROM club_memberships WHERE club_id = ? AND (user_id = ? OR user_id = ?) AND status = 'active'",
                        (club_id, op_uid, operator_uid),
                    )
                    m_row = cursor.fetchone()
                    if m_row and m_row["role"] in ("owner", "coach"):
                        is_authorized = True

            if not is_authorized:
                raise ValueError("仅跑团团长或认证教练可指派活动领跑兔")

            cursor.execute("SELECT id, title, meet_time, start_date, club_id FROM club_events WHERE id = ?", (event_id,))
            ev_row = cursor.fetchone()
            if not ev_row or ev_row["club_id"] != club_id:
                raise ValueError("未找到对应的跑团约跑活动")
            ev_dict = dict(ev_row)

            cursor.execute("SELECT name FROM clubs WHERE id = ?", (club_id,))
            c_info = cursor.fetchone()
            club_name = c_info["name"] if c_info else "跑团"

            cursor.execute("SELECT display_name FROM profiles WHERE id = ?", (op_uid,))
            op_prof = cursor.fetchone()
            coach_name = (op_prof["display_name"] if op_prof and op_prof["display_name"] else "教练")

            eff_group = (pace_group or "").strip() or "🏃 定速领跑组"
            role_label = "🐰 领跑兔"
            now_iso = datetime.utcnow().isoformat() + "Z"

            cursor.execute(
                "SELECT id, checkin_note FROM club_event_participants WHERE event_id = ? AND (user_id = ? OR user_id = ?)",
                (event_id, tg_uid, target_uid),
            )
            existing = cursor.fetchone()
            eff_note = (note or "").strip()
            if existing:
                merged_note = eff_note if eff_note else (existing["checkin_note"] or f"教练指派 {eff_group} 领跑兔")
                cursor.execute(
                    """
                    UPDATE club_event_participants
                    SET status = 'joined', pace_group = ?, runner_role = ?, checkin_note = ?
                    WHERE id = ?
                    """,
                    (eff_group, role_label, merged_note, existing["id"]),
                )
                part_id = existing["id"]
            else:
                part_id = f"part_{int(time.time() * 1000)}_{uuid.uuid4().hex[:4]}"
                cursor.execute(
                    """
                    INSERT INTO club_event_participants (
                        id, event_id, club_id, user_id, joined_at, status, pace_group, runner_role, checkin_note
                    ) VALUES (?, ?, ?, ?, ?, 'joined', ?, ?, ?)
                    """,
                    (
                        part_id,
                        event_id,
                        club_id,
                        tg_uid,
                        now_iso,
                        eff_group,
                        role_label,
                        eff_note or f"教练指派 {eff_group} 领跑兔",
                    ),
                )
            conn.commit()

        when_txt = str(ev_dict.get("meet_time") or ev_dict.get("start_date") or "近期")[:16]
        notif_title = f"🐰 {club_name}邀您担任领跑兔"
        notif_body = (
            f"{coach_name}根据官方兔子胜任力评估，指派您担任活动【{ev_dict.get('title') or '跑团约跑'}】"
            f"（{when_txt}）的【{eff_group}】🐰 领跑兔。"
            + (f" 教练寄语：{eff_note}" if eff_note else " 请在跑团约跑页查看详情并做好匀速领跑准备！")
        )
        notif = LocalStore.create_system_notification(
            user_id=tg_uid,
            title=notif_title,
            content=notif_body,
            notif_type="pacer_invite",
        )
        return {
            "success": True,
            "participant_id": part_id,
            "event_id": event_id,
            "event_title": ev_dict.get("title"),
            "target_uid": tg_uid,
            "pace_group": eff_group,
            "runner_role": role_label,
            "notification_id": notif.get("id"),
            "message": f"已成功指派为【{ev_dict.get('title')} · {eff_group}】🐰 领跑兔，并已发送站内通知",
        }

    # ── MiniApp Full-Chain Behavior Telemetry & Conversion Funnel Analytics ──

    PAGE_TITLES_MAP: Dict[str, str] = {
        "pages/index/index": "首页（数据总览）",
        "pages/coach/coach": "训练（周期课表与教练）",
        "pages/team/team": "跑团（主页与大群）",
        "pages/team/rank": "英雄榜与打卡动态",
        "pages/rank/rank": "英雄榜与打卡动态（分包）",
        "pages/team/group-run": "约跑集结与完赛战报",
        "pages/group-run/group-run": "约跑集结（分包）",
        "pages/profile/profile": "我的（资料与设备绑定）",
        "pages/team/cockpit": "教练工作台",
        "pages/analysis/analysis": "身体数据与跑力分析",
        "pages/activities/activities": "全部跑步记录",
        "pages/onboarding/onboarding": "新手跑者4步设定引导",
        "pages/manual/manual": "帮助与常见问题",
        "pages/share/share": "邀请与海报落地页",
        "pages/goals/goals": "跑量目标设定",
    }

    LAUNCH_SCENE_MAP: Dict[int, str] = {
        1001: "发现栏小程序主入口",
        1005: "微信顶部搜索框",
        1006: "发现栏小程序搜索",
        1007: "好友单聊分享卡片",
        1008: "微信群聊分享卡片",
        1011: "扫描二维码",
        1012: "长按图片识别二维码",
        1013: "相册选取二维码",
        1014: "微信订阅消息/服务通知",
        1020: "公众号主页关联小程序",
        1023: "安卓系统桌面图标",
        1035: "公众号自定义菜单",
        1036: "App分享消息卡片",
        1043: "公众号模板消息",
        1044: "带shareTicket群聊卡片",
        1047: "扫描小程序码（太阳码）",
        1048: "长按识别小程序码（战报海报）",
        1049: "相册选取小程序码（战报海报）",
        1053: "搜一搜结果页",
        1065: "URL Scheme 外部唤起",
        1074: "公众号会话下发消息",
        1089: "微信下拉「最近使用」",
        1090: "右上角菜单重新进入",
        1104: "微信下拉「我的小程序」",
        1154: "朋友圈内打开单页模式",
        1155: "朋友圈单页模式点进小程序",
        1168: "移动应用直接运行小程序",
    }

    @staticmethod
    def resolve_page_title(page_path: Optional[str], fallback: Optional[str] = None) -> str:
        clean = str(page_path or "").strip().lstrip("/").split("?")[0]
        if not clean:
            return fallback or "未知页面"
        return LocalStore.PAGE_TITLES_MAP.get(clean) or fallback or clean

    @staticmethod
    def resolve_scene_label(scene: Optional[int], fallback: Optional[str] = None) -> str:
        if scene is None:
            return fallback or "直接打开"
        try:
            s_int = int(scene)
        except Exception:
            return fallback or str(scene)
        return LocalStore.LAUNCH_SCENE_MAP.get(s_int) or fallback or f"场景 #{s_int}"

    @staticmethod
    def is_synthetic_test_user(profile: Dict[str, Any]) -> bool:
        """
        Distinguishes synthetic pytest / automated fixture accounts from real runners.
        """
        uid = str(profile.get("id") or "").strip()
        name = str(profile.get("display_name") or "").strip()
        email = str(profile.get("email") or "").strip().lower()
        openid = str(profile.get("wechat_openid") or "").strip()
        invited_by = str(profile.get("invited_by") or "").strip()

        if openid.startswith("ogD"):
            return False
        if email.endswith(("@test.com", "@example.com")):
            return True

        synthetic_prefixes = (
            "u_test",
            "test_",
            "race_test",
            "u_vdot",
            "u_elite",
            "u_peer_",
            "u_runner_",
            "u_coach_",
            "u_owner_",
            "u_solo_",
            "u_free_",
            "u_inv",
            "u_coros_",
            "u_garmin_",
            "u_org_",
            "u_unbind_",
            "u_priv_",
            "u_iso_",
            "u_plan_",
            "u_race_",
            "u_month_",
            "u_seg_",
            "u_elev_",
            "u_sync_",
            "u_bio_",
            "u_notif_",
            "u_ios_",
            "u_sched_",
            "u_self_",
            "u_club_",
            "u_adm_",
            "u_wx_inv",
            "u_react_runner_",
            "u_guest_17",
            "u_member_17",
            "coach_owner_",
            "club_runner_",
            "u_tsb_",
            "u_rep_",
            "u_feed_",
            "u_imposter",
            "u_daytime_only_",
            "u_apl_",
            "u_demo_",
            "runner_00",
        )
        if uid.startswith(synthetic_prefixes) or "_test" in uid or "_slim_" in uid:
            return True
        if invited_by.startswith("u_inviter_17"):
            return True
        if name.startswith("新跑友_") or name in (
            "校准测试跑者",
            "伤后恢复精英跑者",
            "普通队友小周",
            "隐私跑者小李",
            "主教练老王",
            "团长老张",
            "未填资料过期跑友",
            "未填全跑友",
            "戈友申请人",
            "仅跑步戴表跑者",
        ):
            return True
        if re.search(r"_17[89]\d{7,}", uid):
            return True
        return False

    _last_telemetry_prune_ts: float = 0.0

    @staticmethod
    def _close_stale_telemetry_sessions(cursor) -> None:
        """Auto-closes OS-killed or abandoned sessions that have had no activity for >= 30 minutes."""
        stale_cutoff = (datetime.now(_CN_TZ) - timedelta(minutes=30)).isoformat(timespec="seconds")
        cursor.execute(
            """
            UPDATE miniapp_sessions
            SET ended_at = last_event_at
            WHERE ended_at IS NULL
              AND last_event_at < ?
            """,
            (stale_cutoff,),
        )

    @staticmethod
    def ingest_telemetry_batch(
        payload: Dict[str, Any],
        verified_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Persists a batch of user behavior events from the MiniApp and updates session rollup stats.
        User identity is strictly populated from verified_user_id (Bearer JWT) — never from unverified body fields.
        Events carrying their own session_id (e.g. flushed from crash-recovery queue) are grouped into their original session.
        """
        raw_sid = str(payload.get("session_id") or "").strip()[:80]
        if not raw_sid:
            return {"accepted": 0, "session_id": ""}

        clean_verified_uid = str(verified_user_id or "").strip()[:80]
        eff_uid = (
            LocalStore.resolve_user_id(clean_verified_uid)
            if clean_verified_uid and not clean_verified_uid.startswith("u_wx_c_")
            else (clean_verified_uid or None)
        )
        client_uuid = str(payload.get("client_uuid") or "").strip()[:80] or None

        raw_scene = payload.get("scene")
        scene_int: Optional[int] = None
        if raw_scene is not None and str(raw_scene).strip() != "":
            try:
                scene_int = int(raw_scene)
            except Exception:
                scene_int = None
        scene_label = LocalStore.resolve_scene_label(scene_int, str(payload.get("scene_label") or "").strip()[:60] or None)

        entry_page = str(payload.get("entry_page") or "").strip().lstrip("/")[:120] or None
        inviter_uid = str(payload.get("inviter_uid") or "").strip()[:80] or None
        device_model = str(payload.get("device_model") or "").strip()[:80] or None
        platform = str(payload.get("platform") or "").strip()[:40] or None
        raw_ver = str(payload.get("app_version") or "").strip()[:30]
        raw_env = str(payload.get("env_version") or "").strip()[:20]
        if raw_ver and raw_env and raw_env != "release":
            app_version = f"{raw_ver}-{raw_env}"[:30]
        else:
            app_version = raw_ver or raw_env or None

        events = payload.get("events")
        if not isinstance(events, list):
            events = []
        events = events[:120]

        grouped_events: Dict[str, List[Dict[str, Any]]] = {}
        for ev in events:
            if not isinstance(ev, dict):
                continue
            ev_sid = str(ev.get("session_id") or raw_sid).strip()[:80] or raw_sid
            grouped_events.setdefault(ev_sid, []).append(ev)
        if not grouped_events:
            grouped_events[raw_sid] = []

        now_iso = get_beijing_iso()
        inserted_count = 0
        primary_sess_uid = eff_uid
        newly_bound_primary_uid = False

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Periodic 120-day retention cleanup (at most once every 6 hours)
            now_epoch = time.time()
            if now_epoch - LocalStore._last_telemetry_prune_ts > 21600:
                LocalStore._last_telemetry_prune_ts = now_epoch
                retention_cutoff = (datetime.now(_CN_TZ) - timedelta(days=120)).isoformat(timespec="seconds")
                cursor.execute("DELETE FROM miniapp_events WHERE created_at < ?", (retention_cutoff,))
                cursor.execute("DELETE FROM miniapp_sessions WHERE started_at < ?", (retention_cutoff,))

            LocalStore._close_stale_telemetry_sessions(cursor)

            for sid, sid_events in grouped_events.items():
                is_primary_sid = sid == raw_sid
                existing_sess = cursor.execute(
                    "SELECT * FROM miniapp_sessions WHERE session_id = ?",
                    (sid,),
                ).fetchone()

                sess_started = existing_sess["started_at"] if existing_sess else now_iso
                existing_uid = existing_sess["user_id"] if existing_sess else None
                existing_client = existing_sess["client_uuid"] if existing_sess else None

                # Only bind/backfill verified uid onto anonymous session if client_uuid matches (or existing session had none)
                can_bind_uid = bool(
                    eff_uid
                    and (not existing_uid or existing_uid == eff_uid)
                    and (not existing_client or (bool(client_uuid) and existing_client == client_uuid))
                )
                sess_uid = eff_uid if can_bind_uid else existing_uid
                if is_primary_sid:
                    primary_sess_uid = sess_uid
                    if can_bind_uid and existing_sess and not existing_sess["user_id"]:
                        newly_bound_primary_uid = True

                sess_client = client_uuid or existing_client
                sess_scene = (
                    scene_int
                    if (is_primary_sid and scene_int is not None)
                    else (existing_sess["scene"] if existing_sess else None)
                )
                sess_scene_label = (
                    existing_sess["scene_label"]
                    if (existing_sess and existing_sess["scene_label"] and (not is_primary_sid or scene_int is None))
                    else (scene_label if is_primary_sid else "直接打开")
                )
                sess_entry = (
                    existing_sess["entry_page"]
                    if (existing_sess and existing_sess["entry_page"])
                    else (entry_page if is_primary_sid else None)
                )
                sess_exit = existing_sess["exit_page"] if existing_sess else sess_entry
                sess_inviter = inviter_uid or (existing_sess["inviter_uid"] if existing_sess else None)
                sess_model = device_model or (existing_sess["device_model"] if existing_sess else None)
                sess_plat = platform or (existing_sess["platform"] if existing_sess else None)
                sess_ver = app_version or (existing_sess["app_version"] if existing_sess else None)
                sess_ended = existing_sess["ended_at"] if existing_sess else None
                sess_dur_ms = int(existing_sess["duration_ms"] or 0) if existing_sess else 0
                sess_max_scroll = int(existing_sess["max_scroll_pct"] or 0) if existing_sess else 0
                sess_had_err = int(existing_sess["had_error"] or 0) if existing_sess else 0

                event_rows_to_insert = []
                for ev in sid_events:
                    ev_type = str(ev.get("event_type") or "button_click").strip()[:40]
                    ev_name = str(ev.get("event_name") or ev_type).strip()[:80]
                    p_path = str(ev.get("page_path") or "").strip().lstrip("/").split("?")[0][:120] or None
                    p_title = (
                        LocalStore.resolve_page_title(p_path, str(ev.get("page_title") or "").strip()[:60] or None)
                        if p_path
                        else (str(ev.get("page_title") or "").strip()[:60] or None)
                    )
                    ev_label = str(ev.get("event_label") or "").strip()[:120] or ev_name

                    try:
                        stay_ms = max(0, int(ev.get("stay_ms") or 0))
                    except Exception:
                        stay_ms = 0

                    raw_sp = ev.get("scroll_pct")
                    scroll_pct: Optional[int] = None
                    if raw_sp is not None and raw_sp != "":
                        try:
                            scroll_pct = max(0, min(100, int(raw_sp)))
                        except Exception:
                            scroll_pct = None

                    try:
                        client_ts = int(ev.get("client_ts") or int(time.time() * 1000))
                    except Exception:
                        client_ts = int(time.time() * 1000)

                    props_raw = ev.get("props")
                    props_str: Optional[str] = None
                    if isinstance(props_raw, dict) and props_raw:
                        try:
                            props_str = json.dumps(props_raw, ensure_ascii=False)[:2000]
                        except Exception:
                            props_str = None
                    elif isinstance(props_raw, str) and props_raw.strip():
                        props_str = props_raw.strip()[:2000]

                    if p_path and not sess_entry:
                        sess_entry = p_path
                    if p_path:
                        sess_exit = p_path
                    if scroll_pct is not None and scroll_pct > sess_max_scroll:
                        sess_max_scroll = scroll_pct
                    if ev_type == "api_issue" or ev_name.endswith("_error") or ev_name.endswith("_fail"):
                        sess_had_err = 1
                    if ev_type in ("session_end", "app_background"):
                        if stay_ms > sess_dur_ms:
                            sess_dur_ms = stay_ms
                        if ev_type == "session_end":
                            now_ms = int(time.time() * 1000)
                            if client_ts > 0 and abs(now_ms - client_ts) <= 14 * 86400 * 1000:
                                bj_dt = datetime.fromtimestamp(client_ts / 1000.0, tz=_CN_TZ)
                                sess_ended = bj_dt.isoformat(timespec="seconds")
                            else:
                                sess_ended = now_iso

                    raw_eid = str(ev.get("event_id") or "").strip()[:120]
                    ev_id = raw_eid or f"det:{ev_type}:{ev_name}:{client_ts}:{p_path or ''}"[:120]

                    event_rows_to_insert.append((
                        sid,
                        ev_id,
                        sess_uid,
                        sess_client,
                        ev_type,
                        ev_name,
                        ev_label,
                        p_path,
                        p_title,
                        stay_ms,
                        scroll_pct,
                        props_str,
                        client_ts,
                        now_iso,
                    ))

                if event_rows_to_insert:
                    before_changes = conn.total_changes
                    cursor.executemany(
                        """
                        INSERT OR IGNORE INTO miniapp_events (
                            session_id, event_id, user_id, client_uuid, event_type, event_name, event_label,
                            page_path, page_title, stay_ms, scroll_pct, props_json, client_ts, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        event_rows_to_insert,
                    )
                    inserted_count += max(0, conn.total_changes - before_changes)

                if can_bind_uid and sess_uid:
                    cursor.execute(
                        "UPDATE miniapp_events SET user_id = ? WHERE session_id = ? AND (user_id IS NULL OR user_id = '')",
                        (sess_uid, sid),
                    )

                rollup = cursor.execute(
                    """
                    SELECT
                        SUM(CASE WHEN event_type = 'page_enter' THEN 1 ELSE 0 END) AS page_enters,
                        COUNT(DISTINCT CASE WHEN page_path IS NOT NULL AND page_path != '' THEN page_path END) AS distinct_pages,
                        SUM(CASE WHEN event_type IN ('button_click', 'modal_open', 'funnel_step', 'subview_enter') THEN 1 ELSE 0 END) AS clicks,
                        SUM(CASE WHEN event_type = 'page_leave' THEN stay_ms ELSE 0 END) AS sum_page_stay_ms,
                        MAX(scroll_pct) AS max_scroll,
                        MIN(client_ts) AS min_ts,
                        MAX(client_ts) AS max_ts
                    FROM miniapp_events
                    WHERE session_id = ?
                    """,
                    (sid,),
                ).fetchone()

                page_cnt = max(
                    int((rollup["page_enters"] if rollup else 0) or 0),
                    int((rollup["distinct_pages"] if rollup else 0) or 0),
                )
                click_cnt = int((rollup["clicks"] if rollup else 0) or 0)
                sum_stay = int((rollup["sum_page_stay_ms"] if rollup else 0) or 0)
                span_ms = 0
                if rollup and rollup["min_ts"] and rollup["max_ts"] and rollup["max_ts"] > rollup["min_ts"]:
                    span_ms = int(rollup["max_ts"] - rollup["min_ts"])
                computed_dur_ms = max(sess_dur_ms, sum_stay, min(span_ms, 7200000))
                if rollup and rollup["max_scroll"] is not None and int(rollup["max_scroll"]) > sess_max_scroll:
                    sess_max_scroll = int(rollup["max_scroll"])

                cursor.execute(
                    """
                    INSERT INTO miniapp_sessions (
                        session_id, user_id, client_uuid, scene, scene_label, entry_page, exit_page,
                        inviter_uid, device_model, platform, app_version, started_at, last_event_at,
                        ended_at, duration_ms, page_count, click_count, max_scroll_pct, had_error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        user_id = COALESCE(excluded.user_id, miniapp_sessions.user_id),
                        client_uuid = COALESCE(excluded.client_uuid, miniapp_sessions.client_uuid),
                        scene = COALESCE(miniapp_sessions.scene, excluded.scene),
                        scene_label = COALESCE(miniapp_sessions.scene_label, excluded.scene_label),
                        entry_page = COALESCE(miniapp_sessions.entry_page, excluded.entry_page),
                        exit_page = COALESCE(excluded.exit_page, miniapp_sessions.exit_page),
                        inviter_uid = COALESCE(miniapp_sessions.inviter_uid, excluded.inviter_uid),
                        device_model = COALESCE(excluded.device_model, miniapp_sessions.device_model),
                        platform = COALESCE(excluded.platform, miniapp_sessions.platform),
                        app_version = COALESCE(excluded.app_version, miniapp_sessions.app_version),
                        last_event_at = excluded.last_event_at,
                        ended_at = COALESCE(excluded.ended_at, miniapp_sessions.ended_at),
                        duration_ms = excluded.duration_ms,
                        page_count = excluded.page_count,
                        click_count = excluded.click_count,
                        max_scroll_pct = excluded.max_scroll_pct,
                        had_error = MAX(miniapp_sessions.had_error, excluded.had_error)
                    """,
                    (
                        sid,
                        sess_uid,
                        sess_client,
                        sess_scene,
                        sess_scene_label,
                        sess_entry,
                        sess_exit,
                        sess_inviter,
                        sess_model,
                        sess_plat,
                        sess_ver,
                        sess_started,
                        now_iso,
                        sess_ended,
                        computed_dur_ms,
                        page_cnt,
                        click_cnt,
                        sess_max_scroll,
                        sess_had_err,
                    ),
                )
            conn.commit()

        if primary_sess_uid and eff_uid and primary_sess_uid == eff_uid and not eff_uid.startswith("u_wx_c_"):
            try:
                LocalStore._bridge_web_qr_from_telemetry(
                    raw_sid,
                    events,
                    eff_uid,
                    inspect_history=newly_bound_primary_uid,
                )
            except Exception as bridge_err:
                logging.getLogger("local_store").warning(f"[web_qr_bridge] non-fatal error: {bridge_err}")

        return {
            "accepted": inserted_count,
            "session_id": raw_sid,
            "user_id": primary_sess_uid,
        }

    @staticmethod
    def _bridge_web_qr_from_telemetry(
        session_id: str,
        events: List[Dict[str, Any]],
        eff_uid: str,
        inspect_history: bool = False,
    ) -> None:
        """
        Cryptographically verified Web QR login bridge for live Mini-Program builds (including 3.9.2):
        When a signed-JWT authenticated user scans a dynamic `wxacode` (`scene=wlogin_<16hex>`)
        and taps to enter the Mini-Program from `pages/share/share`, marks/confirms the one-time Web QR session.
        """
        if not eff_uid or eff_uid.startswith("u_wx_c_"):
            return

        from urllib.parse import unquote

        share_entry_clicks = {
            "share_cta_home",
            "share_nav_coach",
            "share_nav_team",
            "share_nav_analysis",
            "share_nav_profile",
            "share_nav_manual",
            "web_qr_login_confirm",
        }
        wlogin_scene = ""
        has_entry_action = False
        has_dismiss = False

        for ev in events:
            if not isinstance(ev, dict):
                continue
            ev_type = str(ev.get("event_type") or "").strip()
            ev_name = str(ev.get("event_name") or "").strip()
            if ev_name == "web_qr_login_dismiss":
                has_dismiss = True
            props = ev.get("props") if isinstance(ev.get("props"), dict) else {}
            q = props.get("query") if isinstance(props.get("query"), dict) else {}
            raw_q_scene = unquote(str(q.get("scene") or "").strip())
            if re.fullmatch(r"wlogin_[0-9a-f]{16}", raw_q_scene):
                wlogin_scene = raw_q_scene
            if ev_type == "button_click" and ev_name in share_entry_clicks:
                has_entry_action = True
            elif ev_type == "page_enter":
                from_page = str(props.get("from_page") or "").strip().lstrip("/")
                if from_page == "pages/share/share":
                    has_entry_action = True

        if (not wlogin_scene and has_entry_action and session_id) or (inspect_history and session_id):
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                prior_rows = conn.execute(
                    """
                    SELECT event_type, event_name, props_json
                    FROM miniapp_events
                    WHERE session_id = ? AND user_id = ?
                    ORDER BY id DESC
                    LIMIT 20
                    """,
                    (session_id, eff_uid),
                ).fetchall()
            for prow in prior_rows:
                p_type = str(prow["event_type"] or "")
                p_name = str(prow["event_name"] or "")
                if p_name == "web_qr_login_dismiss":
                    has_dismiss = True
                if p_type == "button_click" and p_name in share_entry_clicks:
                    has_entry_action = True
                raw_pj = prow["props_json"]
                if not raw_pj:
                    continue
                try:
                    pj = json.loads(raw_pj)
                    if not isinstance(pj, dict):
                        continue
                    if p_type == "page_enter" and str(pj.get("from_page") or "").strip().lstrip("/") == "pages/share/share":
                        has_entry_action = True
                    if not wlogin_scene:
                        pq = pj.get("query") if isinstance(pj.get("query"), dict) else {}
                        cand = unquote(str(pq.get("scene") or "").strip())
                        if re.fullmatch(r"wlogin_[0-9a-f]{16}", cand):
                            wlogin_scene = cand
                except Exception:
                    pass

        if not wlogin_scene:
            return

        qr_sess = LocalStore.get_web_qr_session(wlogin_scene)
        if not qr_sess or qr_sess.get("status") not in ("pending", "scanned"):
            return

        prof = LocalStore.get_profile(eff_uid) or {}
        d_name = str(prof.get("display_name") or "").strip()
        avatar = str(prof.get("avatar_url") or "").strip()

        if has_entry_action and not has_dismiss:
            LocalStore.confirm_web_qr_session(
                wlogin_scene,
                user_id=eff_uid,
                display_name=d_name,
                avatar_url=avatar,
            )
        else:
            LocalStore.mark_web_qr_scanned(
                wlogin_scene,
                display_name=d_name,
                avatar_url=avatar,
            )

    @staticmethod
    def get_behavior_analytics_overview(days: int = 14) -> Dict[str, Any]:
        """
        Aggregates per-user MiniApp session, page stay, scroll depth, button click,
        page transition, and recent session list over the past N days.
        """
        eff_days = max(1, min(90, int(days or 14)))
        cutoff_iso = (datetime.now(_CN_TZ) - timedelta(days=eff_days)).isoformat(timespec="seconds")

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            LocalStore._close_stale_telemetry_sessions(c)
            conn.commit()

            sess_rows = c.execute(
                """
                SELECT s.*,
                       p.display_name,
                       p.avatar_url,
                       p.garmin_connected,
                       p.coros_connected,
                       p.huawei_connected,
                       p.apple_watch_connected,
                       p.suunto_connected
                FROM miniapp_sessions s
                LEFT JOIN profiles p ON p.id = s.user_id
                WHERE s.started_at >= ?
                ORDER BY s.started_at DESC
                """,
                (cutoff_iso,),
            ).fetchall()

            total_sessions = len(sess_rows)
            unique_visitors = len({
                (r["user_id"] or r["client_uuid"] or r["session_id"])
                for r in sess_rows
            })
            total_dur_ms = sum(int(r["duration_ms"] or 0) for r in sess_rows)
            total_pages = sum(int(r["page_count"] or 0) for r in sess_rows)
            total_scroll = sum(int(r["max_scroll_pct"] or 0) for r in sess_rows)
            bounce_cnt = sum(
                1 for r in sess_rows
                if int(r["page_count"] or 0) <= 1 and int(r["duration_ms"] or 0) < 10000 and int(r["click_count"] or 0) == 0
            )
            err_sess_cnt = sum(1 for r in sess_rows if int(r["had_error"] or 0) > 0)

            total_events_row = c.execute(
                "SELECT COUNT(*) AS cnt FROM miniapp_events WHERE created_at >= ?",
                (cutoff_iso,),
            ).fetchone()
            total_events = int(total_events_row["cnt"] or 0) if total_events_row else 0

            # Per-page stay duration & scroll depth stats
            page_leave_rows = c.execute(
                """
                SELECT
                    page_path,
                    MAX(page_title) AS page_title,
                    COUNT(*) AS leave_cnt,
                    COUNT(DISTINCT COALESCE(user_id, client_uuid, session_id)) AS uv,
                    AVG(CASE WHEN stay_ms > 0 THEN stay_ms END) AS avg_stay_ms,
                    AVG(CASE WHEN scroll_pct > 0 THEN scroll_pct END) AS avg_scroll_pct,
                    SUM(CASE WHEN scroll_pct >= 85 THEN 1 ELSE 0 END) AS deep_read_cnt
                FROM miniapp_events
                WHERE created_at >= ?
                  AND event_type IN ('page_leave', 'page_enter')
                  AND page_path IS NOT NULL AND page_path != ''
                GROUP BY page_path
                """,
                (cutoff_iso,),
            ).fetchall()

            page_enter_counts = {
                r["page_path"]: int(r["cnt"] or 0)
                for r in c.execute(
                    """
                    SELECT page_path, COUNT(*) AS cnt
                    FROM miniapp_events
                    WHERE created_at >= ? AND event_type = 'page_enter' AND page_path IS NOT NULL
                    GROUP BY page_path
                    """,
                    (cutoff_iso,),
                ).fetchall()
            }
            entry_counts: Dict[str, int] = {}
            exit_counts: Dict[str, int] = {}
            for sr in sess_rows:
                ep = sr["entry_page"]
                xp = sr["exit_page"]
                if ep:
                    entry_counts[ep] = entry_counts.get(ep, 0) + 1
                if xp:
                    exit_counts[xp] = exit_counts.get(xp, 0) + 1

            pages_stats = []
            for pr in page_leave_rows:
                pp = pr["page_path"]
                pv = max(page_enter_counts.get(pp, 0), int(pr["leave_cnt"] or 0))
                ex_cnt = exit_counts.get(pp, 0)
                leave_c = int(pr["leave_cnt"] or 0)
                pages_stats.append({
                    "page_path": pp,
                    "page_title": LocalStore.resolve_page_title(pp, pr["page_title"]),
                    "pv": pv,
                    "uv": int(pr["uv"] or 0),
                    "avg_stay_sec": round(float(pr["avg_stay_ms"] or 0.0) / 1000.0, 1),
                    "avg_scroll_pct": round(float(pr["avg_scroll_pct"] or 0.0), 1),
                    "deep_read_pct": round(int(pr["deep_read_cnt"] or 0) * 100.0 / leave_c, 1) if leave_c > 0 else 0.0,
                    "entry_count": entry_counts.get(pp, 0),
                    "exit_count": ex_cnt,
                    "exit_rate_pct": round(ex_cnt * 100.0 / pv, 1) if pv > 0 else 0.0,
                })
            pages_stats.sort(key=lambda x: -x["pv"])

            # Per-page visited session counts so module exposure rates use same-page sessions as denominator
            page_sess_rows = c.execute(
                """
                SELECT
                    page_path,
                    COUNT(DISTINCT session_id) AS page_sessions
                FROM miniapp_events
                WHERE created_at >= ?
                  AND page_path IS NOT NULL
                  AND page_path != ''
                GROUP BY page_path
                """,
                (cutoff_iso,),
            ).fetchall()
            page_session_map = {
                str(r["page_path"]): int(r["page_sessions"] or 0) for r in page_sess_rows
            }

            # Module exposure stats (IntersectionObserver module_view)
            mod_rows = c.execute(
                """
                SELECT
                    event_name,
                    MAX(event_label) AS event_label,
                    MAX(page_path) AS page_path,
                    COUNT(*) AS views,
                    COUNT(DISTINCT session_id) AS unique_sessions,
                    COUNT(DISTINCT COALESCE(user_id, client_uuid, session_id)) AS unique_users
                FROM miniapp_events
                WHERE created_at >= ?
                  AND event_type = 'module_view'
                GROUP BY event_name
                ORDER BY unique_sessions DESC, views DESC
                LIMIT 30
                """,
                (cutoff_iso,),
            ).fetchall()
            module_exposures = []
            for r in mod_rows:
                u_sess = int(r["unique_sessions"] or 0)
                p_path = r["page_path"] or ""
                p_sess = max(u_sess, page_session_map.get(p_path, 0)) if p_path else total_sessions
                denom = p_sess if p_sess > 0 else total_sessions
                module_exposures.append(
                    {
                        "event_name": r["event_name"],
                        "event_label": r["event_label"] or r["event_name"],
                        "page_path": p_path or None,
                        "page_title": LocalStore.resolve_page_title(p_path),
                        "views": int(r["views"] or 0),
                        "unique_sessions": u_sess,
                        "page_sessions": denom,
                        "exposure_pct": round(u_sess * 100.0 / denom, 1) if denom > 0 else 0.0,
                        "unique_users": int(r["unique_users"] or 0),
                    }
                )

            # Top buttons / modals / subviews clicked
            btn_rows = c.execute(
                """
                SELECT
                    event_name,
                    MAX(event_label) AS event_label,
                    event_type,
                    MAX(page_path) AS page_path,
                    COUNT(*) AS clicks,
                    COUNT(DISTINCT COALESCE(user_id, client_uuid, session_id)) AS unique_users
                FROM miniapp_events
                WHERE created_at >= ?
                  AND event_type IN ('button_click', 'modal_open', 'subview_enter', 'funnel_step')
                GROUP BY event_name, event_type
                ORDER BY clicks DESC
                LIMIT 30
                """,
                (cutoff_iso,),
            ).fetchall()
            top_buttons = [
                {
                    "event_name": r["event_name"],
                    "event_label": r["event_label"] or r["event_name"],
                    "event_type": r["event_type"],
                    "page_path": r["page_path"],
                    "page_title": LocalStore.resolve_page_title(r["page_path"]),
                    "clicks": int(r["clicks"] or 0),
                    "unique_users": int(r["unique_users"] or 0),
                }
                for r in btn_rows
            ]

            # Page-to-page navigation transitions
            enter_seq_rows = c.execute(
                """
                SELECT session_id, page_path
                FROM miniapp_events
                WHERE created_at >= ?
                  AND event_type = 'page_enter'
                  AND page_path IS NOT NULL AND page_path != ''
                ORDER BY session_id, client_ts ASC, id ASC
                """,
                (cutoff_iso,),
            ).fetchall()
            trans_counter: Dict[Tuple[str, str], int] = {}
            prev_sid = None
            prev_page = None
            for er in enter_seq_rows:
                sid = er["session_id"]
                cur_p = er["page_path"]
                if sid == prev_sid and prev_page and prev_page != cur_p:
                    key = (prev_page, cur_p)
                    trans_counter[key] = trans_counter.get(key, 0) + 1
                prev_sid = sid
                prev_page = cur_p

            page_transitions = [
                {
                    "from_page": k[0],
                    "from_title": LocalStore.resolve_page_title(k[0]),
                    "to_page": k[1],
                    "to_title": LocalStore.resolve_page_title(k[1]),
                    "count": cnt,
                }
                for k, cnt in sorted(trans_counter.items(), key=lambda x: -x[1])[:20]
            ]

            # API errors / slow requests captured on client
            issue_rows = c.execute(
                """
                SELECT event_name, MAX(event_label) AS event_label, MAX(page_path) AS page_path,
                       COUNT(*) AS count, MAX(props_json) AS sample_props
                FROM miniapp_events
                WHERE created_at >= ? AND event_type = 'api_issue'
                GROUP BY event_name, event_label
                ORDER BY count DESC
                LIMIT 15
                """,
                (cutoff_iso,),
            ).fetchall()
            api_issues = []
            for ir in issue_rows:
                sample = {}
                if ir["sample_props"]:
                    try:
                        sample = json.loads(ir["sample_props"])
                    except Exception:
                        sample = {}
                api_issues.append({
                    "event_name": ir["event_name"],
                    "event_label": ir["event_label"],
                    "page_path": ir["page_path"],
                    "page_title": LocalStore.resolve_page_title(ir["page_path"]),
                    "count": int(ir["count"] or 0),
                    "sample": sample,
                })

            # Recent sessions list (for per-user timeline replay)
            recent_sessions = []
            for sr in sess_rows[:60]:
                watch_brand = None
                if sr["garmin_connected"]:
                    watch_brand = "佳明"
                elif sr["coros_connected"]:
                    watch_brand = "高驰"
                elif sr["huawei_connected"]:
                    watch_brand = "华为"
                elif sr["apple_watch_connected"]:
                    watch_brand = "Apple"
                elif sr["suunto_connected"]:
                    watch_brand = "颂拓"

                recent_sessions.append({
                    "session_id": sr["session_id"],
                    "user_id": sr["user_id"],
                    "client_uuid": sr["client_uuid"],
                    "display_name": sr["display_name"] or ("未登录访客" if not sr["user_id"] else sr["user_id"][-6:]),
                    "avatar_url": sr["avatar_url"] or "",
                    "watch_brand": watch_brand,
                    "scene": sr["scene"],
                    "scene_label": sr["scene_label"] or "直接打开",
                    "entry_page": sr["entry_page"],
                    "entry_title": LocalStore.resolve_page_title(sr["entry_page"]),
                    "exit_page": sr["exit_page"],
                    "exit_title": LocalStore.resolve_page_title(sr["exit_page"]),
                    "device_model": sr["device_model"] or "",
                    "platform": sr["platform"] or "",
                    "started_at": to_beijing_iso(sr["started_at"]),
                    "last_event_at": to_beijing_iso(sr["last_event_at"]),
                    "ended_at": to_beijing_iso(sr["ended_at"]) if sr["ended_at"] else None,
                    "duration_sec": round(float(sr["duration_ms"] or 0) / 1000.0, 1),
                    "page_count": int(sr["page_count"] or 0),
                    "click_count": int(sr["click_count"] or 0),
                    "max_scroll_pct": int(sr["max_scroll_pct"] or 0),
                    "had_error": bool(sr["had_error"]),
                })

        return {
            "days": eff_days,
            "summary": {
                "total_sessions": total_sessions,
                "unique_visitors": unique_visitors,
                "total_events": total_events,
                "avg_session_duration_sec": round((total_dur_ms / 1000.0) / total_sessions, 1) if total_sessions > 0 else 0.0,
                "avg_pages_per_session": round(total_pages / total_sessions, 2) if total_sessions > 0 else 0.0,
                "avg_scroll_pct": round(total_scroll / total_sessions, 1) if total_sessions > 0 else 0.0,
                "bounce_sessions_pct": round(bounce_cnt * 100.0 / total_sessions, 1) if total_sessions > 0 else 0.0,
                "error_sessions_count": err_sess_cnt,
            },
            "pages": pages_stats,
            "module_exposures": module_exposures,
            "top_buttons": top_buttons,
            "page_transitions": page_transitions,
            "api_issues": api_issues,
            "recent_sessions": recent_sessions,
        }

    @staticmethod
    def get_session_timeline(session_id: str) -> Optional[Dict[str, Any]]:
        """
        Returns the complete chronological event timeline for a single user session.
        """
        sid = str(session_id or "").strip()
        if not sid:
            return None

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            LocalStore._close_stale_telemetry_sessions(c)
            conn.commit()
            sess = c.execute(
                """
                SELECT s.*, p.display_name, p.avatar_url, p.garmin_connected, p.coros_connected,
                       p.huawei_connected, p.apple_watch_connected, p.suunto_connected
                FROM miniapp_sessions s
                LEFT JOIN profiles p ON p.id = s.user_id
                WHERE s.session_id = ?
                """,
                (sid,),
            ).fetchone()
            if not sess:
                return None

            ev_rows = c.execute(
                """
                SELECT *
                FROM miniapp_events
                WHERE session_id = ?
                ORDER BY client_ts ASC, id ASC
                """,
                (sid,),
            ).fetchall()

        base_ts = int(ev_rows[0]["client_ts"] or 0) if ev_rows else 0
        events_out = []
        for er in ev_rows:
            props = {}
            if er["props_json"]:
                try:
                    props = json.loads(er["props_json"])
                except Exception:
                    props = {}
            cts = int(er["client_ts"] or 0)
            offset_sec = round(max(0, cts - base_ts) / 1000.0, 1) if base_ts > 0 and cts > 0 else 0.0
            events_out.append({
                "id": er["id"],
                "event_type": er["event_type"],
                "event_name": er["event_name"],
                "event_label": er["event_label"] or er["event_name"],
                "page_path": er["page_path"],
                "page_title": LocalStore.resolve_page_title(er["page_path"], er["page_title"]) if er["page_path"] else (er["page_title"] or ""),
                "stay_sec": round(float(er["stay_ms"] or 0) / 1000.0, 1),
                "scroll_pct": int(er["scroll_pct"]) if er["scroll_pct"] is not None else None,
                "props": props,
                "client_ts": cts,
                "offset_sec": offset_sec,
                "created_at": to_beijing_iso(er["created_at"]),
            })

        return {
            "session": {
                "session_id": sess["session_id"],
                "user_id": sess["user_id"],
                "client_uuid": sess["client_uuid"],
                "display_name": sess["display_name"] or ("未登录访客" if not sess["user_id"] else sess["user_id"][-6:]),
                "avatar_url": sess["avatar_url"] or "",
                "scene": sess["scene"],
                "scene_label": sess["scene_label"] or "直接打开",
                "entry_page": sess["entry_page"],
                "entry_title": LocalStore.resolve_page_title(sess["entry_page"]),
                "exit_page": sess["exit_page"],
                "exit_title": LocalStore.resolve_page_title(sess["exit_page"]),
                "inviter_uid": sess["inviter_uid"],
                "device_model": sess["device_model"] or "",
                "platform": sess["platform"] or "",
                "app_version": sess["app_version"] or "",
                "started_at": to_beijing_iso(sess["started_at"]),
                "ended_at": to_beijing_iso(sess["ended_at"]) if sess["ended_at"] else None,
                "duration_sec": round(float(sess["duration_ms"] or 0) / 1000.0, 1),
                "page_count": int(sess["page_count"] or 0),
                "click_count": int(sess["click_count"] or 0),
                "max_scroll_pct": int(sess["max_scroll_pct"] or 0),
                "had_error": bool(sess["had_error"]),
            },
            "events": events_out,
        }

    @staticmethod
    def get_user_journey(user_id: str, limit_sessions: int = 20) -> Dict[str, Any]:
        """
        Returns all recent MiniApp sessions and summary stats for a specific runner.
        """
        eff_uid = LocalStore.resolve_user_id(user_id)
        prof = LocalStore.get_profile(eff_uid) or {}
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            rows = c.execute(
                """
                SELECT session_id
                FROM miniapp_sessions
                WHERE user_id = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (eff_uid, max(1, min(50, int(limit_sessions or 20)))),
            ).fetchall()

        sessions = []
        for r in rows:
            tl = LocalStore.get_session_timeline(r["session_id"])
            if tl:
                sessions.append(tl)

        return {
            "user": {
                "id": eff_uid,
                "display_name": prof.get("display_name") or eff_uid,
                "avatar_url": prof.get("avatar_url") or "",
                "created_at": to_beijing_iso(prof.get("created_at")),
            },
            "total_sessions": len(sessions),
            "sessions": sessions,
        }

    @staticmethod
    def get_conversion_funnel_analytics() -> Dict[str, Any]:
        """
        Computes real-user product conversion funnel across existing business tables
        (automatically excluding synthetic pytest fixtures).
        """
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            all_profiles = [dict(r) for r in c.execute("SELECT * FROM profiles").fetchall()]
            real_profiles = [p for p in all_profiles if not LocalStore.is_synthetic_test_user(p)]
            real_uids = {p["id"] for p in real_profiles}

            act_uids = {
                r["user_id"]
                for r in c.execute("SELECT DISTINCT user_id FROM activities WHERE user_id IS NOT NULL").fetchall()
                if r["user_id"] in real_uids
            }
            club_uids = {
                r["user_id"]
                for r in c.execute("SELECT DISTINCT user_id FROM club_memberships WHERE user_id IS NOT NULL").fetchall()
                if r["user_id"] in real_uids
            }
            org_uids = {
                r["user_id"]
                for r in c.execute("SELECT DISTINCT user_id FROM organization_members WHERE user_id IS NOT NULL").fetchall()
                if r["user_id"] in real_uids
            }
            plan_uids = {
                r["user_id"]
                for r in c.execute("SELECT DISTINCT user_id FROM training_plans WHERE user_id IS NOT NULL").fetchall()
                if r["user_id"] in real_uids
            }
            like_uids = {
                r["user_id"]
                for r in c.execute("SELECT DISTINCT user_id FROM activity_likes WHERE user_id IS NOT NULL").fetchall()
                if r["user_id"] in real_uids
            }
            comment_uids = {
                r["user_id"]
                for r in c.execute("SELECT DISTINCT user_id FROM activity_comments WHERE user_id IS NOT NULL").fetchall()
                if r["user_id"] in real_uids
            }
            event_part_uids = {
                r["user_id"]
                for r in c.execute("SELECT DISTINCT user_id FROM club_event_participants WHERE user_id IS NOT NULL").fetchall()
                if r["user_id"] in real_uids
            }
            inviter_uids = {
                r["inviter_uid"]
                for r in c.execute("SELECT DISTINCT inviter_uid FROM user_referrals WHERE inviter_uid IS NOT NULL").fetchall()
                if r["inviter_uid"] in real_uids
            }

        total_real = len(real_profiles)
        denom = max(1, total_real)

        named_users = sum(
            1 for p in real_profiles
            if p.get("display_name") and not str(p.get("display_name")).startswith(("跑者_", "微信跑者", "新跑友"))
        )
        onboard_done = sum(1 for p in real_profiles if p.get("onboarding_completed"))
        device_skipped = sum(1 for p in real_profiles if p.get("device_skipped"))
        history_skipped = sum(1 for p in real_profiles if p.get("history_skipped"))

        garmin_cnt = sum(1 for p in real_profiles if p.get("garmin_connected"))
        coros_cnt = sum(1 for p in real_profiles if p.get("coros_connected"))
        huawei_cnt = sum(1 for p in real_profiles if p.get("huawei_connected"))
        apple_cnt = sum(1 for p in real_profiles if p.get("apple_watch_connected"))
        suunto_cnt = sum(1 for p in real_profiles if p.get("suunto_connected"))
        any_watch = sum(
            1 for p in real_profiles
            if any([
                p.get("garmin_connected"),
                p.get("coros_connected"),
                p.get("huawei_connected"),
                p.get("apple_watch_connected"),
                p.get("suunto_connected"),
            ])
        )

        community_joined = len(club_uids | org_uids)
        social_engaged = len(like_uids | comment_uids | event_part_uids | inviter_uids)

        steps = [
            {
                "key": "registered",
                "label": "1. 注册登录真实用户",
                "count": total_real,
                "pct_of_total": 100.0 if total_real > 0 else 0.0,
                "hint": f"已自动过滤测试账号 {len(all_profiles) - total_real} 个",
            },
            {
                "key": "community_joined",
                "label": "2. 加入跑团或大群体",
                "count": community_joined,
                "pct_of_total": round(community_joined * 100.0 / denom, 1),
                "hint": f"入跑团 {len(club_uids)} 人 · 入大群 {len(org_uids)} 人",
            },
            {
                "key": "custom_profile",
                "label": "3. 完善真实/个性昵称（非默认「跑者_xxxx」）",
                "count": named_users,
                "pct_of_total": round(named_users * 100.0 / denom, 1),
                "hint": f"仍有 {total_real - named_users} 人停留在系统默认随机昵称",
            },
            {
                "key": "watch_connected",
                "label": "4. 成功绑定运动手表",
                "count": any_watch,
                "pct_of_total": round(any_watch * 100.0 / denom, 1),
                "hint": f"高驰 {coros_cnt} · 佳明 {garmin_cnt} · Apple {apple_cnt} · 华为 {huawei_cnt} · 颂拓 {suunto_cnt}",
            },
            {
                "key": "has_activities",
                "label": "5. 拥有至少 1 条跑步记录",
                "count": len(act_uids),
                "pct_of_total": round(len(act_uids) * 100.0 / denom, 1),
                "hint": "完成设备同步或导入轨迹/截图",
            },
            {
                "key": "has_training_plan",
                "label": "6. 生成周期训练课表",
                "count": len(plan_uids),
                "pct_of_total": round(len(plan_uids) * 100.0 / denom, 1),
                "hint": "使用教练或课表系统备战",
            },
            {
                "key": "social_engaged",
                "label": "7. 深度社区互动（约跑/点赞/评论/拉新）",
                "count": social_engaged,
                "pct_of_total": round(social_engaged * 100.0 / denom, 1),
                "hint": f"约跑 {len(event_part_uids)} · 评论 {len(comment_uids)} · 点赞 {len(like_uids)} · 拉新 {len(inviter_uids)}",
            },
        ]

        return {
            "total_profiles_in_db": len(all_profiles),
            "synthetic_excluded": len(all_profiles) - total_real,
            "total_real_users": total_real,
            "onboarding_completed_count": onboard_done,
            "device_skipped_count": device_skipped,
            "history_skipped_count": history_skipped,
            "watch_breakdown": {
                "any": any_watch,
                "coros": coros_cnt,
                "garmin": garmin_cnt,
                "apple_watch": apple_cnt,
                "huawei": huawei_cnt,
                "suunto": suunto_cnt,
            },
            "steps": steps,
        }




