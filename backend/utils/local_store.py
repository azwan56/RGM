import sqlite3
import os
import json
import uuid
import random
import string
import logging
import time
import calendar
import copy
import math
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date, timedelta, timezone
from utils.encryption import encrypt_pii, decrypt_pii, compute_age_group

logger = logging.getLogger("local_store")

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "rgm.db")

DEFAULT_ORG_FIELD_RULES = [
    {"field": "real_name", "label": "真实姓名", "required": True, "type": "text"},
    {"field": "gender", "label": "性别", "required": True, "type": "select", "options": ["male", "female"]},
    {"field": "date_of_birth", "label": "出生日期", "required": True, "type": "date"},
    {"field": "class_name", "label": "班级/届别", "required": True, "type": "text"},
    {"field": "phone", "label": "手机号码", "required": False, "type": "phone"},
    {"field": "id_card", "label": "证件号码(身份证/护照)", "required": False, "type": "id_card"},
    {"field": "emergency_contact", "label": "紧急联系人及电话", "required": False, "type": "text"},
    {"field": "clothing_size", "label": "队服尺码", "required": False, "type": "text"},
    {"field": "shoe_size", "label": "跑鞋尺码", "required": False, "type": "text"},
    {"field": "marathon_pb", "label": "全马PB成绩", "required": False, "type": "text"},
    {"field": "health_declaration", "label": "健康状况声明", "required": False, "type": "boolean"},
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

def get_beijing_now() -> datetime:
    """Returns current datetime in China Standard Time (UTC+8)."""
    return datetime.utcnow() + timedelta(hours=8)

def get_beijing_today() -> date:
    """Returns today's date in China Standard Time (UTC+8)."""
    return (datetime.utcnow() + timedelta(hours=8)).date()

def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                email TEXT,
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
                marathon_pb INTEGER DEFAULT 11370,
                half_pb INTEGER DEFAULT 5457,
                ten_k_pb INTEGER DEFAULT 2426,
                five_k_pb INTEGER DEFAULT 1164,
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
                hrv_status TEXT,
                hrv_weekly_avg REAL,
                hrv_last_night_avg REAL,
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                user_id TEXT PRIMARY KEY,
                target_distance REAL DEFAULT 200.0,
                weekly_target REAL DEFAULT 50.0,
                period_type TEXT DEFAULT 'monthly',
                monthly_targets TEXT,
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)
        try:
            cursor.execute("ALTER TABLE goals ADD COLUMN weekly_target REAL DEFAULT 50.0")
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
        ]:
            try:
                cursor.execute(f"ALTER TABLE race_plans ADD COLUMN {col_def}")
            except Exception:
                pass

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
                created_at TEXT,
                FOREIGN KEY(activity_id) REFERENCES activities(id),
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)

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
                overview_summary TEXT,
                schedule_data TEXT,
                creator_id TEXT NOT NULL,
                last_modified_by TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)

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

        # Seed default Fudan Gobi Organization if none exists
        cursor.execute("SELECT COUNT(*) FROM organizations WHERE id = 'org_fudan_gobi'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT OR IGNORE INTO organizations (id, name, logo_url, description, city, invite_code, owner_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "org_fudan_gobi",
                "复旦戈",
                "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=300&auto=format&fit=crop&q=80",
                "复旦大学戈壁挑战赛大群体 · 汇聚商学院EMBA/MBA及泛复旦戈友，下设各个戈友跑团与训练营。",
                "上海",
                "FDGOBI",
                "u_df65d9a588c9",
                datetime.utcnow().isoformat() + "Z"
            ))

        # Seed default field rules for organizations if settings or field_rules missing
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
                "复旦戈友先锋跑团",
                "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=300&auto=format&fit=crop&q=80",
                "复旦大学戈壁挑战赛日常拉练与备战总跑团，面向全体复旦戈友队员。",
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
                "RGM 巅峰先锋跑团",
                "https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80",
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
                datetime.utcnow().isoformat() + "Z"
            ))

        conn.commit()

init_db()

class LocalStore:
    @staticmethod
    def resolve_user_id(uid: str) -> str:
        """Resolves canonical user_id from profiles table if uid is email or display_name."""
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
        return uid

    @staticmethod
    def _decrypt_profile_dict(d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not d:
            return d
        res = dict(d)
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
                return LocalStore._decrypt_profile_dict(d)
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

            cursor.execute("PRAGMA table_info(profiles)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            for col in data.keys():
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
                for k, v in data.items():
                    if k != "id" and k in existing_cols:
                        fields.append(f"{k} = ?")
                        values.append(v)
                if fields:
                    values.append(eff_uid)
                    cursor.execute(f"UPDATE profiles SET {', '.join(fields)} WHERE id = ?", values)
            else:
                data["id"] = eff_uid
                if "created_at" not in data:
                    data["created_at"] = datetime.utcnow().isoformat() + "Z"
                valid_data = {k: v for k, v in data.items() if k in existing_cols or k == "id"}
                cols = list(valid_data.keys())
                placeholders = ["?"] * len(cols)
                cursor.execute(f"INSERT INTO profiles ({', '.join(cols)}) VALUES ({', '.join(placeholders)})", list(valid_data.values()))
            conn.commit()

    @staticmethod
    def upsert_activity(act: Dict[str, Any]):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cols = [
                "id", "user_id", "name", "sport_type", "start_time", "distance_meters",
                "moving_time_seconds", "elapsed_time_seconds", "elevation_gain_meters",
                "average_heartrate", "max_heartrate", "average_cadence", "avg_pace_str",
                "calories", "aerobic_training_effect", "anaerobic_training_effect", "trimp",
                "ai_journal", "laps_data", "splits_data", "gps_track_data", "map_image_url"
            ]
            act_id = act.get("id")
            cursor.execute("SELECT id, gps_track_data, map_image_url FROM activities WHERE id = ?", (act_id,))
            existing_row = cursor.fetchone()
            is_new = existing_row is None

            if not is_new and existing_row:
                if not act.get("gps_track_data") and existing_row[1]:
                    act["gps_track_data"] = existing_row[1]
                if not act.get("map_image_url") and existing_row[2]:
                    act["map_image_url"] = existing_row[2]

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

            row_data = []
            for col in cols:
                val = act.get(col)
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                row_data.append(val)
            placeholders = ["?"] * len(cols)
            cursor.execute(f"INSERT OR REPLACE INTO activities ({', '.join(cols)}) VALUES ({', '.join(placeholders)})", row_data)
            conn.commit()

        # Trigger training plan auto-reconciliation if active plan exists
        try:
            uid = act.get("user_id")
            if uid:
                active_plan = LocalStore.get_user_active_training_plan(uid, reconcile=False)
                if active_plan:
                    LocalStore.reconcile_training_plan_activities(active_plan, uid)
        except Exception as e:
            logger.warning(f"Plan reconciliation after upsert_activity skipped: {e}")

        # If this is a new activity and has Canova critique, dispatch push notification
        if is_new and act.get("ai_journal") and act.get("user_id"):
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
    def get_recent_activities(uid: str, limit: int = 15) -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM activities WHERE user_id = ? ORDER BY start_time DESC LIMIT ?", (uid, limit))
            rows = [dict(r) for r in cursor.fetchall()]

        for r in rows:
            if not r.get("ai_journal") or not str(r["ai_journal"]).strip():
                critique = LocalStore.generate_canova_critique(r)
                r["ai_journal"] = critique
                with sqlite3.connect(DB_PATH) as conn:
                    conn.cursor().execute("UPDATE activities SET ai_journal = ? WHERE id = ?", (critique, r["id"]))
                    conn.commit()

        return rows

    @staticmethod
    def get_activity_gps_track(activity_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, sport_type, start_time, distance_meters, elevation_gain_meters, 
                       avg_pace_str, average_heartrate, map_image_url, gps_track_data, ai_journal
                FROM activities 
                WHERE id = ?
            """, (activity_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            if res.get("gps_track_data"):
                try:
                    res["gps_track_data"] = json.loads(res["gps_track_data"])
                except Exception:
                    pass
            return res

    @staticmethod
    def get_training_load(uid: str, days: int = 60) -> Dict[str, Any]:
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
                SELECT start_time, distance_meters, moving_time_seconds, average_heartrate, trimp
                FROM activities
                WHERE (user_id = ? OR user_id = ?) AND start_time >= ?
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
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(distance_meters) FROM activities WHERE user_id = ? AND start_time >= ?", (uid, month_start))
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
            cursor.execute("""
                SELECT * FROM activities 
                WHERE user_id = ? AND start_time >= ? AND start_time < ? 
                ORDER BY start_time DESC
            """, (canonical_uid, start_date, end_date))
            rows = [dict(r) for r in cursor.fetchall()]

        # Generate Canova critiques if missing
        for r in rows:
            if not r.get("ai_journal") or not str(r["ai_journal"]).strip():
                try:
                    critique = LocalStore.generate_canova_critique(r)
                    r["ai_journal"] = critique
                    with sqlite3.connect(DB_PATH) as conn:
                        conn.cursor().execute("UPDATE activities SET ai_journal = ? WHERE id = ?", (critique, r["id"]))
                        conn.commit()
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

            # 1. Resolve weekly target distance
            if target_km is None or target_km <= 0:
                cursor.execute("SELECT weekly_target, target_distance FROM goals WHERE user_id = ? OR user_id = ?", (canonical_uid, uid))
                grow = cursor.fetchone()
                if grow and grow[0] is not None and float(grow[0]) > 0:
                    target_km = float(grow[0])
                elif grow and grow[1] is not None and float(grow[1]) > 0:
                    target_km = round(float(grow[1]) / 4.0, 1)
                else:
                    target_km = 50.0

            # 2. Total week distance & runs
            cursor.execute("""
                SELECT SUM(distance_meters), COUNT(id)
                FROM activities
                WHERE (user_id = ? OR user_id = ?) AND start_time >= ? AND start_time < ?
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
            cursor.execute("""
                SELECT substr(start_time, 1, 10) as act_date, SUM(distance_meters), COUNT(id)
                FROM activities
                WHERE (user_id = ? OR user_id = ?) AND start_time >= ? AND start_time < ?
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
        plan = LocalStore.get_user_active_training_plan(canonical_uid)
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
                        "is_missed": bool(day.get("is_missed"))
                    }
        return None

    @staticmethod
    def get_monthly_trend(uid: str, num_months: int = 6) -> Dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            today = get_beijing_today()
            months = []
            for i in range(num_months - 1, -1, -1):
                m = today.month - i
                y = today.year
                while m <= 0:
                    m += 12
                    y -= 1
                months.append((y, m))

            trend = []
            for (y, m) in months:
                label = f"{y}/{m}月"
                start_iso = f"{y:04d}-{m:02d}-01"
                next_y = y if m < 12 else y + 1
                next_m = m + 1 if m < 12 else 1
                end_iso = f"{next_y:04d}-{next_m:02d}-01"

                cursor.execute("""
                    SELECT SUM(distance_meters), COUNT(id) 
                    FROM activities 
                    WHERE user_id = ? AND start_time >= ? AND start_time < ?
                """, (uid, start_iso, end_iso))
                res = cursor.fetchone()
                dist_m = float(res[0]) if res and res[0] is not None else 0.0
                count = int(res[1]) if res and res[1] is not None else 0
                dist_km = round(dist_m / 1000.0, 1)

                trend.append({
                    "month_label": label,
                    "year": y,
                    "month": m,
                    "distance_km": dist_km,
                    "count": count,
                    "is_current": (y == today.year and m == today.month)
                })

            cur_km = trend[-1]["distance_km"] if trend else 0.0
            prev_km = trend[-2]["distance_km"] if len(trend) >= 2 else 0.0
            pct_change = round(((cur_km - prev_km) / prev_km) * 100, 1) if prev_km > 0 else 0.0

            return {
                "trend": trend,
                "current_month_km": cur_km,
                "prev_month_km": prev_km,
                "pct_change": pct_change,
                "recent_3_months": trend[-3:] if len(trend) >= 3 else trend
            }

    @staticmethod
    def get_yearly_stats(uid: str, year: int = 2026) -> Dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            start_iso = f"{year:04d}-01-01"
            end_iso = f"{year + 1:04d}-01-01"

            cursor.execute("""
                SELECT SUM(distance_meters), COUNT(id) 
                FROM activities 
                WHERE user_id = ? AND start_time >= ? AND start_time < ?
            """, (uid, start_iso, end_iso))
            res = cursor.fetchone()
            total_m = float(res[0]) if res and res[0] is not None else 0.0
            total_runs = int(res[1]) if res and res[1] is not None else 0
            total_km = round(total_m / 1000.0, 1)

            target_year_km = 3400.0
            cursor.execute("SELECT monthly_targets, target_distance FROM goals WHERE user_id = ?", (uid,))
            g_row = cursor.fetchone()
            if g_row:
                try:
                    targets = json.loads(g_row["monthly_targets"])
                    if isinstance(targets, list) and len(targets) > 0:
                        target_year_km = sum(float(t) for t in targets)
                except Exception:
                    pass

            today = get_beijing_today()
            passed_months = today.month
            avg_monthly_km = round(total_km / max(1, passed_months), 1)
            projected_year_km = round(avg_monthly_km * 12, 1)
            progress_pct = round((total_km / target_year_km) * 100, 1) if target_year_km > 0 else 0.0

            best_month_name = f"{today.month}月"
            best_month_km = 0.0
            monthly_breakdown = []
            for m in range(1, 13):
                m_start = f"{year:04d}-{m:02d}-01"
                next_y = year if m < 12 else year + 1
                next_m = m + 1 if m < 12 else 1
                m_end = f"{next_y:04d}-{next_m:02d}-01"
                cursor.execute("""
                    SELECT SUM(distance_meters), COUNT(id) 
                    FROM activities 
                    WHERE user_id = ? AND start_time >= ? AND start_time < ?
                """, (uid, m_start, m_end))
                m_res = cursor.fetchone()
                m_dist = float(m_res[0]) if m_res and m_res[0] is not None else 0.0
                m_count = int(m_res[1]) if m_res and m_res[1] is not None else 0
                m_km = round(m_dist / 1000.0, 1)
                if m_km > best_month_km:
                    best_month_km = m_km
                    best_month_name = f"{m}月"

                monthly_breakdown.append({
                    "month": m,
                    "month_label": f"{m}月",
                    "distance_km": m_km,
                    "runs_count": m_count,
                    "is_current": (year == today.year and m == today.month),
                    "is_past": (year < today.year or (year == today.year and m <= today.month))
                })

            return {
                "year": year,
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
                    "avg_pace": "7:41"
                },
                "monthly_breakdown": monthly_breakdown
            }

    @staticmethod
    def upsert_daily_health(uid: str, metrics: Dict[str, Any]):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            date_str = metrics.get("date") or datetime.utcnow().strftime("%Y-%m-%d")
            entry_id = f"{uid}_{date_str}"
            cursor.execute("""
                INSERT INTO daily_health 
                (id, user_id, date, resting_heart_rate, vo2_max, sleep_duration_seconds, sleep_duration_hours, sleep_score, body_battery_max, body_battery_min, hrv_status, hrv_weekly_avg, hrv_last_night_avg)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    resting_heart_rate = COALESCE(excluded.resting_heart_rate, daily_health.resting_heart_rate),
                    vo2_max = COALESCE(excluded.vo2_max, daily_health.vo2_max),
                    sleep_duration_seconds = COALESCE(excluded.sleep_duration_seconds, daily_health.sleep_duration_seconds),
                    sleep_duration_hours = COALESCE(excluded.sleep_duration_hours, daily_health.sleep_duration_hours),
                    sleep_score = COALESCE(excluded.sleep_score, daily_health.sleep_score),
                    body_battery_max = COALESCE(excluded.body_battery_max, daily_health.body_battery_max),
                    body_battery_min = COALESCE(excluded.body_battery_min, daily_health.body_battery_min),
                    hrv_status = COALESCE(excluded.hrv_status, daily_health.hrv_status),
                    hrv_weekly_avg = COALESCE(excluded.hrv_weekly_avg, daily_health.hrv_weekly_avg),
                    hrv_last_night_avg = COALESCE(excluded.hrv_last_night_avg, daily_health.hrv_last_night_avg)
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
                metrics.get("hrv_status"),
                metrics.get("hrv_weekly_avg"),
                metrics.get("hrv_last_night_avg")
            ))
            conn.commit()

    @staticmethod
    def get_latest_health(uid: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # 1. First look for the most recent day that has actual physiological data
            cursor.execute("""
                SELECT * FROM daily_health 
                WHERE user_id = ? 
                  AND (resting_heart_rate IS NOT NULL OR sleep_score IS NOT NULL OR hrv_last_night_avg IS NOT NULL OR body_battery_max IS NOT NULL OR vo2_max IS NOT NULL)
                ORDER BY date DESC LIMIT 1
            """, (uid,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                # If sleep_score is missing in the latest row, check if there is a recent non-null sleep record
                if d.get("sleep_score") is None:
                    cursor.execute("""
                        SELECT sleep_score, sleep_duration_seconds, sleep_duration_hours 
                        FROM daily_health 
                        WHERE user_id = ? AND sleep_score IS NOT NULL 
                        ORDER BY date DESC LIMIT 1
                    """, (uid,))
                    s_row = cursor.fetchone()
                    if s_row:
                        d["sleep_score"] = s_row["sleep_score"]
                        d["sleep_duration_seconds"] = s_row["sleep_duration_seconds"]
                        d["sleep_duration_hours"] = s_row["sleep_duration_hours"]

                # If hrv_last_night_avg is missing in the latest row, fallback to most recent night HRV
                if d.get("hrv_last_night_avg") is None:
                    cursor.execute("""
                        SELECT hrv_last_night_avg, hrv_weekly_avg, hrv_status
                        FROM daily_health 
                        WHERE user_id = ? AND hrv_last_night_avg IS NOT NULL 
                        ORDER BY date DESC LIMIT 1
                    """, (uid,))
                    h_row = cursor.fetchone()
                    if h_row:
                        d["hrv_last_night_avg"] = h_row["hrv_last_night_avg"]
                        if d.get("hrv_weekly_avg") is None:
                            d["hrv_weekly_avg"] = h_row["hrv_weekly_avg"]
                        if not d.get("hrv_status"):
                            d["hrv_status"] = h_row["hrv_status"]
                return d
            # 2. If all rows are empty, return the most recent row
            cursor.execute("SELECT * FROM daily_health WHERE user_id = ? ORDER BY date DESC LIMIT 1", (uid,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

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

            existing_map = {r["date"]: dict(r) for r in rows}
            trend = []
            for i in range(29, -1, -1):
                d = today - timedelta(days=i)
                d_str = d.isoformat()
                short_d = d.strftime("%m-%d")
                
                if d_str in existing_map:
                    item = existing_map[d_str]
                    rhr = item.get("resting_heart_rate")
                    hrv = item.get("hrv_last_night_avg") or item.get("hrv_weekly_avg")
                    bb = item.get("body_battery_max")
                    sleep_score = item.get("sleep_score")

                    trend.append({
                        "date": d_str,
                        "date_label": short_d,
                        "resting_heart_rate": int(rhr) if rhr is not None else None,
                        "hrv": int(hrv) if hrv is not None else None,
                        "body_battery": int(bb) if bb is not None else None,
                        "sleep_score": int(sleep_score) if sleep_score is not None else None,
                        "sleep_duration_hours": float(item.get("sleep_duration_hours")) if item.get("sleep_duration_hours") is not None else None,
                        "sleep_duration_seconds": int(item.get("sleep_duration_seconds")) if item.get("sleep_duration_seconds") is not None else None
                    })

            return trend

    @staticmethod
    def get_goal(uid: str) -> Dict[str, Any]:
        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM goals WHERE user_id = ? OR user_id = ?", (canonical_uid, uid))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                if d.get("monthly_targets"):
                    try:
                        d["monthly_targets"] = json.loads(d["monthly_targets"])
                    except Exception:
                        d["monthly_targets"] = [200.0] * 12
                # Ensure weekly_target is populated
                if d.get("weekly_target") is not None and float(d["weekly_target"]) > 0:
                    d["weekly_target"] = float(d["weekly_target"])
                else:
                    d["weekly_target"] = round(float(d.get("target_distance") or 200.0) / 4.0, 1)
                return d
            return {
                "target_distance": 200.0,
                "weekly_target": 50.0,
                "period_type": "monthly",
                "monthly_targets": [200.0] * 12
            }

    @staticmethod
    def upsert_goal(uid: str, data: Dict[str, Any]):
        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            targets_json = json.dumps(data.get("monthly_targets") or [200.0] * 12)
            target_dist = float(data.get("target_distance") or 200.0)
            weekly_target = float(data.get("weekly_target") or round(target_dist / 4.0, 1) or 50.0)
            cursor.execute("""
                INSERT INTO goals (user_id, target_distance, period_type, monthly_targets, weekly_target)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    target_distance = excluded.target_distance,
                    period_type = excluded.period_type,
                    monthly_targets = excluded.monthly_targets,
                    weekly_target = excluded.weekly_target
            """, (
                canonical_uid,
                target_dist,
                data.get("period_type", "monthly"),
                targets_json,
                weekly_target
            ))
            conn.commit()

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
                
                # Photos list
                raw_photos = p.get("photos")
                if raw_photos:
                    try:
                        p["photos"] = json.loads(raw_photos) if isinstance(raw_photos, str) else raw_photos
                    except Exception:
                        p["photos"] = [p["photo_url"]] if p.get("photo_url") else []
                else:
                    p["photos"] = [p["photo_url"]] if p.get("photo_url") else []

                # Completed status & countdown calculation
                is_completed = (status == "completed" or bool(finish_time))
                p["is_completed"] = is_completed

                if p.get("race_date"):
                    try:
                        r_date = datetime.strptime(p["race_date"][:10], "%Y-%m-%d").date()
                        days_left = (r_date - today).days
                        p["days_left"] = max(0, days_left)
                        p["is_past"] = days_left < 0
                    except Exception:
                        p["days_left"] = 0
                        p["is_past"] = False
                else:
                    p["days_left"] = 0
                    p["is_past"] = False

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

                # Deserialize race_info JSON
                raw_ri = p.get("race_info")
                if raw_ri:
                    try:
                        p["race_info"] = json.loads(raw_ri)
                    except Exception:
                        p["race_info"] = {}
                else:
                    p["race_info"] = {}
                plans.append(p)
            
            return plans

    @staticmethod
    def upsert_race_plan(uid: str, plan_data: Dict[str, Any]):
        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            plan_id = plan_data.get("id") or f"race_{int(datetime.utcnow().timestamp()*1000)}_{uuid.uuid4().hex[:6]}"
            raw_pri = str(plan_data.get("priority", 1)).upper()
            if raw_pri in ["A", "1"]:
                pri = 1
            elif raw_pri in ["B", "2"]:
                pri = 2
            elif raw_pri in ["C", "3"]:
                pri = 3
            else:
                pri = 1

            status = plan_data.get("status") or "upcoming"
            finish_time = plan_data.get("finish_time") or None
            finish_notes = plan_data.get("finish_notes") or None
            photo_url = plan_data.get("photo_url") or None
            photos = plan_data.get("photos")
            if photos is not None:
                photos_json = json.dumps(photos, ensure_ascii=False)
            elif photo_url:
                photos_json = json.dumps([photo_url], ensure_ascii=False)
            else:
                photos_json = None

            cursor.execute("""
                INSERT OR REPLACE INTO race_plans (
                    id, user_id, name, race_type, race_date, target_time, priority, created_at, race_info,
                    status, finish_time, finish_notes, photo_url, photos
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_id,
                canonical_uid,
                plan_data.get("name") or "未命名赛事",
                plan_data.get("race_type") or "全马",
                plan_data.get("race_date") or date.today().isoformat(),
                plan_data.get("target_time") or "3:30:00",
                pri,
                datetime.utcnow().isoformat() + "Z",
                json.dumps(plan_data.get("race_info") or {}, ensure_ascii=False) if plan_data.get("race_info") is not None else None,
                status,
                finish_time,
                finish_notes,
                photo_url,
                photos_json
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
    ) -> bool:
        """Marks a race as completed or upcoming, updating finish time, notes, and photo."""
        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Fetch existing photos
            cursor.execute(
                "SELECT photo_url, photos FROM race_plans WHERE (user_id = ? OR user_id = ?) AND (id = ? OR name = ?)",
                (canonical_uid, uid, race_id, race_id)
            )
            row = cursor.fetchone()
            if not row:
                return False
            existing_photo_url, existing_photos_raw = row
            final_photo_url = photo_url if photo_url is not None else existing_photo_url
            photos_list = []
            if existing_photos_raw:
                try:
                    photos_list = json.loads(existing_photos_raw)
                except Exception:
                    photos_list = []
            if final_photo_url and final_photo_url not in photos_list:
                photos_list.append(final_photo_url)

            cursor.execute("""
                UPDATE race_plans
                SET status = ?, finish_time = COALESCE(?, finish_time), finish_notes = COALESCE(?, finish_notes),
                    photo_url = COALESCE(?, photo_url), photos = ?
                WHERE (user_id = ? OR user_id = ?) AND (id = ? OR name = ?)
            """, (
                status,
                finish_time,
                finish_notes,
                final_photo_url,
                json.dumps(photos_list, ensure_ascii=False) if photos_list else None,
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
    def find_matched_activity_for_race(uid: str, race_date: str) -> Optional[Dict[str, Any]]:
        """
        Finds a Garmin/COROS activity matching the given race date (within date or ±1 day).
        Useful for one-click autofilling actual finish time and metrics into race plan.
        """
        canonical_uid = LocalStore.resolve_user_id(uid)
        date_clean = (race_date or "")[:10]
        if not date_clean:
            return None
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Match exact date first
            cursor.execute("""
                SELECT id, name, sport_type, start_time, distance_meters, moving_time_seconds, 
                       elapsed_time_seconds, avg_pace_str, elevation_gain_meters, average_heartrate
                FROM activities
                WHERE (user_id = ? OR user_id = ?) AND start_time LIKE ?
                ORDER BY distance_meters DESC
                LIMIT 1
            """, (canonical_uid, uid, f"{date_clean}%"))
            row = cursor.fetchone()
            if not row:
                # Try ±1 day
                try:
                    d_obj = datetime.strptime(date_clean, "%Y-%m-%d").date()
                    prev_d = (d_obj - timedelta(days=1)).isoformat()
                    next_d = (d_obj + timedelta(days=1)).isoformat()
                    cursor.execute("""
                        SELECT id, name, sport_type, start_time, distance_meters, moving_time_seconds, 
                               elapsed_time_seconds, avg_pace_str, elevation_gain_meters, average_heartrate
                        FROM activities
                        WHERE (user_id = ? OR user_id = ?) AND (start_time LIKE ? OR start_time LIKE ?)
                        ORDER BY distance_meters DESC
                        LIMIT 1
                    """, (canonical_uid, uid, f"{prev_d}%", f"{next_d}%"))
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

    # ── Multi-Tenant Running Clubs API Methods ──

    @staticmethod
    def create_club(owner_id: str, name: str, description: Optional[str] = None, city: str = "上海", logo_url: Optional[str] = None, org_id: Optional[str] = None, join_mode: str = "free") -> Dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            club_id = f"club_{int(datetime.utcnow().timestamp()*1000)}"
            code = generate_invite_code()
            logo = logo_url or "https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80"
            created_at = datetime.utcnow().isoformat() + "Z"

            cursor.execute("""
                INSERT INTO clubs (id, org_id, name, logo_url, description, city, invite_code, owner_id, created_at, join_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (club_id, org_id, name, logo, description, city, code, owner_id, created_at, join_mode))

            cursor.execute("""
                INSERT INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                VALUES (?, ?, ?, 'owner', 'active', ?, 1)
            """, (f"{club_id}_{owner_id}", club_id, owner_id, created_at))

            conn.commit()
            return {
                "id": club_id,
                "org_id": org_id,
                "name": name,
                "logo_url": logo,
                "description": description,
                "city": city,
                "invite_code": code,
                "owner_id": owner_id,
                "created_at": created_at,
                "join_mode": join_mode
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
            return [dict(r) for r in rows]

    @staticmethod
    def join_club_by_code(user_id: str, invite_code: str, privacy_consent: bool = True) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clubs WHERE UPPER(invite_code) = ?", (invite_code.strip().upper(),))
            club = cursor.fetchone()
            if not club:
                return None
            
            club_dict = dict(club)
            LocalStore.validate_sub_club_join_eligibility(club_dict, user_id)

            club_id = club_dict["id"]
            membership_id = f"{club_id}_{user_id}"
            joined_at = datetime.utcnow().isoformat() + "Z"

            cursor.execute("""
                INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                VALUES (?, ?, ?, COALESCE((SELECT role FROM club_memberships WHERE id = ?), 'member'), 'active', ?, ?)
            """, (membership_id, club_id, user_id, membership_id, joined_at, int(privacy_consent)))
            conn.commit()

            return club_dict

    @staticmethod
    def join_club_by_id(user_id: str, club_id: str, privacy_consent: bool = True, invite_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clubs WHERE id = ?", (club_id.strip(),))
            club = cursor.fetchone()
            if not club:
                return None
            
            club_dict = dict(club)
            LocalStore.validate_sub_club_join_eligibility(club_dict, user_id)

            # If club requires invite code, validate it
            if club_dict.get("join_mode") == "invite":
                provided_code = (invite_code or "").strip().upper()
                expected_code = (club_dict.get("invite_code") or "").strip().upper()
                if not provided_code:
                    raise ValueError(f"跑团【{club_dict.get('name')}】已设置凭专属邀请码入团，请输入专属邀请码！")
                if provided_code != expected_code:
                    raise ValueError("跑团邀请码错误，请向团长核对后重新输入！")

            membership_id = f"{club_id}_{user_id}"
            joined_at = datetime.utcnow().isoformat() + "Z"

            cursor.execute("""
                INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                VALUES (?, ?, ?, COALESCE((SELECT role FROM club_memberships WHERE id = ?), 'member'), 'active', ?, ?)
            """, (membership_id, club_id, user_id, membership_id, joined_at, int(privacy_consent)))
            conn.commit()

            return club_dict

    @staticmethod
    def get_club_members(club_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.id as user_id, p.display_name, p.avatar_url, p.marathon_pb, p.half_pb,
                       m.role, m.joined_at, m.privacy_consent
                FROM club_memberships m
                JOIN profiles p ON m.user_id = p.id
                WHERE m.club_id = ? AND m.status = 'active'
                ORDER BY CASE m.role WHEN 'owner' THEN 1 WHEN 'coach' THEN 2 ELSE 3 END, m.joined_at ASC
            """, (club_id,))
            rows = cursor.fetchall()
        today = date.today()
        month_start = date(today.year, today.month, 1).isoformat()
        current_month_idx = today.month - 1
        res = []
        for r in rows:
            d = dict(r)
            uid = d["user_id"]
            dist_m = LocalStore.get_month_distance_meters(uid, month_start)
            d["month_km"] = round(dist_m / 1000.0, 1)
            g = LocalStore.get_goal(uid)
            tgts = g.get("monthly_targets") or [200.0] * 12
            d["target_km"] = float(tgts[current_month_idx] if current_month_idx < len(tgts) else g.get("target_distance") or 200.0)
            d["completion_rate"] = round((d["month_km"] / d["target_km"]) * 100.0, 1) if d["target_km"] > 0 else 0.0
            res.append(d)
        return res

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
    def remove_club_member(club_id: str, user_id: str):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM club_memberships WHERE club_id = ? AND user_id = ?", (club_id, user_id))
            conn.commit()

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
    def list_public_clubs(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        raw = LocalStore.list_all_clubs()
        user_club_ids = set()
        if user_id:
            user_clubs = LocalStore.get_user_clubs(user_id)
            user_club_ids = {c["id"] for c in user_clubs}
        
        sanitized = []
        for c in raw:
            item = dict(c)
            item.pop("invite_code", None) # Strictly hide invite_code from public
            item["is_member"] = item["id"] in user_club_ids
            sanitized.append(item)
        return sanitized

    @staticmethod
    def update_club(club_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            allowed = ["name", "description", "city", "logo_url", "invite_code", "org_id", "join_mode"]
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
            cursor.execute(f"UPDATE clubs SET {', '.join(set_clauses)} WHERE id = ?", tuple(params))
            conn.commit()
            return LocalStore.get_club(club_id)

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
                       created_at
                FROM profiles
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["garmin_connected"] = bool(d.get("garmin_connected"))
                d["coros_connected"] = bool(d.get("coros_connected"))
                result.append(d)
            return result

    @staticmethod
    def get_club_events(club_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM club_events WHERE club_id = ? ORDER BY start_date DESC", (club_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def create_club_event(club_id: str, data: Dict[str, Any]) -> str:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            event_id = f"event_{int(datetime.utcnow().timestamp()*1000)}"
            cursor.execute("""
                INSERT INTO club_events (id, club_id, title, event_type, start_date, end_date, target_km, rules, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                club_id,
                data.get("title") or "跑团月度挑战",
                data.get("event_type") or "distance_challenge",
                data.get("start_date") or date.today().isoformat(),
                data.get("end_date") or (date.today() + timedelta(days=30)).isoformat(),
                float(data.get("target_km") or 200.0),
                data.get("rules") or "完赛即可获得专属电子勋章",
                datetime.utcnow().isoformat() + "Z"
            ))
            conn.commit()
            return event_id

    @staticmethod
    def update_club_event(club_id: str, event_id: str, data: Dict[str, Any]):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE club_events 
                SET title = ?, event_type = ?, start_date = ?, end_date = ?, target_km = ?, rules = ?
                WHERE id = ? AND club_id = ?
            """, (
                data.get("title") or "跑团月度挑战",
                data.get("event_type") or "distance_challenge",
                data.get("start_date") or date.today().isoformat(),
                data.get("end_date") or (date.today() + timedelta(days=30)).isoformat(),
                float(data.get("target_km") or 200.0),
                data.get("rules") or "完赛即可获得专属电子勋章",
                event_id,
                club_id
            ))
            conn.commit()

    @staticmethod
    def delete_club_event(club_id: str, event_id: str):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM club_events WHERE id = ? AND club_id = ?", (event_id, club_id))
            conn.commit()

    @staticmethod
    def get_coach_students_metrics(club_id: str, coach_id: str) -> List[Dict[str, Any]]:
        """
        Calculates TSB fatigue, Resting Heart Rate, Night HRV, and risk levels for all authorized students in the club.
        """
        members = LocalStore.get_club_members(club_id)
        students = []
        today = date.today()
        month_start = date(today.year, today.month, 1).isoformat()

        for m in members:
            uid = m["user_id"]
            # Fetch health and training load
            h = LocalStore.get_latest_health(uid) or {}
            month_dist_m = LocalStore.get_month_distance_meters(uid, month_start)
            month_km = round(month_dist_m / 1000.0, 1)

            # Calculate CTL/ATL/TSB using the scientific Banister TRIMP + EWMA model
            recent_acts = LocalStore.get_recent_activities(uid, limit=100)
            if not recent_acts or len(recent_acts) == 0:
                atl = 0.0
                ctl = 0.0
                tsb = 0.0
                status_level = "none"
                status_text = "未同步运动负荷"
            else:
                from utils.running_metrics import compute_ctl_atl_tsb
                daily_trimp_map = { (today - timedelta(days=i)).isoformat(): 0.0 for i in range(90, -1, -1) }
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

                # Risk classification
                if tsb > 5:
                    status_level = "peak" # 🟢 巅峰 (Green)
                    status_text = "巅峰状态 · 适宜测速与冲刺比赛"
                elif tsb >= -30:
                    status_level = "optimal" # 🔵 适应 (Blue)
                    status_text = "专项适应 · 建议按计划执行专项课"
                elif tsb >= -50:
                    status_level = "tired" # 🟡 疲劳 (Yellow)
                    status_text = "疲劳累积 · 建议适度穿插轻松慢跑"
                else:
                    status_level = "danger" # 🔴 伤病预警 (Red)
                    status_text = "过度训练预警 · 建议彻底休整或低心率排酸"

            rhr = h.get("resting_heart_rate")
            if rhr is None:
                with sqlite3.connect(DB_PATH) as conn:
                    c = conn.cursor()
                    c.execute("SELECT resting_heart_rate FROM daily_health WHERE user_id = ? AND resting_heart_rate IS NOT NULL ORDER BY date DESC LIMIT 1", (uid,))
                    r = c.fetchone()
                    if r and r[0]:
                        rhr = r[0]

            hrv = h.get("hrv_last_night_avg") or h.get("hrv_weekly_avg")
            if hrv is None:
                with sqlite3.connect(DB_PATH) as conn:
                    c = conn.cursor()
                    c.execute("SELECT hrv_last_night_avg, hrv_weekly_avg FROM daily_health WHERE user_id = ? AND (hrv_last_night_avg IS NOT NULL OR hrv_weekly_avg IS NOT NULL) ORDER BY date DESC LIMIT 1", (uid,))
                    r = c.fetchone()
                    if r:
                        hrv = r[0] or r[1]

            sleep = h.get("sleep_score")
            if sleep is None:
                with sqlite3.connect(DB_PATH) as conn:
                    c = conn.cursor()
                    c.execute("SELECT sleep_score FROM daily_health WHERE user_id = ? AND sleep_score IS NOT NULL ORDER BY date DESC LIMIT 1", (uid,))
                    r = c.fetchone()
                    if r and r[0]:
                        sleep = r[0]

            # 1. Goal planning & progress
            goal_data = LocalStore.get_goal(uid)
            current_month_idx = today.month - 1
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

            # 2. Athlete profile
            profile = LocalStore.get_profile(uid) or {}
            marathon_pb = profile.get("marathon_pb")
            half_pb = profile.get("half_pb")
            gender = profile.get("gender") or "未知"
            weight = profile.get("weight")
            height = profile.get("height")

            # 3. 7-day distance & TRIMP
            seven_days_ago_iso = (today - timedelta(days=7)).isoformat()
            acts_7d = [a for a in recent_acts if str(a.get("start_time", ""))[:10] >= seven_days_ago_iso]
            km_7d = round(sum(float(a.get("distance_meters") or 0) for a in acts_7d) / 1000.0, 1)
            runs_7d_count = len(acts_7d)

            # 4. Coach diagnostic analysis
            if not recent_acts or len(recent_acts) == 0:
                coach_diagnosis = "暂未检测到近期运动记录上传，建议提醒队员检查手表蓝牙同步。"
                canova_phase = "基础期 (待启动)"
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

            students.append({
                "user_id": uid,
                "display_name": m["display_name"],
                "avatar_url": m["avatar_url"],
                "role": m["role"],
                "privacy_consent": bool(m.get("privacy_consent", 1)),
                "month_km": month_km,
                "target_km": target_km,
                "monthly_targets": monthly_targets,
                "completion_rate": completion_rate,
                "remaining_km": remaining_km,
                "suggested_daily_km": suggested_daily_km,
                "pacing_status": pacing_status,
                "pacing_text": pacing_text,
                "marathon_pb": marathon_pb,
                "half_pb": half_pb,
                "km_7d": km_7d,
                "runs_7d_count": runs_7d_count,
                "coach_diagnosis": coach_diagnosis,
                "canova_phase": canova_phase,
                "gender": gender,
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

        return students

    @staticmethod
    def get_club_leaderboard(club_id: str, time_range: str = "month") -> List[Dict[str, Any]]:
        members = LocalStore.get_club_members(club_id)
        today = date.today()
        if time_range == "month":
            start_iso = date(today.year, today.month, 1).isoformat()
        else:
            # 7 days
            start_iso = (today - timedelta(days=7)).isoformat()

        board = []
        for m in members:
            uid = m["user_id"]
            dist_m = LocalStore.get_month_distance_meters(uid, start_iso)
            dist_km = round(dist_m / 1000.0, 1)
            
            goal = LocalStore.get_goal(uid)
            monthly_targets = goal.get("monthly_targets")
            if monthly_targets and isinstance(monthly_targets, list) and len(monthly_targets) >= today.month:
                target_km = float(monthly_targets[today.month - 1] or goal.get("target_distance") or 200.0)
            else:
                target_km = float(goal.get("target_distance") or 200.0)
            pct = round((dist_km / target_km) * 100, 1) if target_km > 0 else 0.0

            board.append({
                "user_id": uid,
                "display_name": m["display_name"],
                "avatar_url": m["avatar_url"],
                "role": m["role"],
                "distance_km": dist_km,
                "target_km": target_km,
                "progress_pct": pct
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
        club = LocalStore.get_club(club_id)
        if not club:
            return False
        if club.get("owner_id") == operator_uid:
            return True
        members = LocalStore.get_club_members(club_id)
        return any(m["user_id"] == operator_uid and m["role"] == "owner" for m in members)

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
        longest_run: Optional[Dict[str, Any]] = None
    ) -> str:
        if total_km == 0:
            return "本周期全团处于休整调整期，建议下周期安排短程激活与低心率慢跑，循序渐进唤醒肌神经募集。"
        
        cycle_name = "周度" if period_type == "week" else "月度"
        
        # Determine team volume evaluation (concise: ~35-40 chars)
        if total_km >= 500 or (period_type == "week" and total_km >= 200):
            volume_eval = f"全团推进 {total_km}km (出勤率 {attendance_rate}%)，有氧底座储备扎实，微血管增生充分。"
        else:
            volume_eval = f"全团完成 {total_km}km，打卡 {total_acts_count} 次 (出勤率 {attendance_rate}%)，基础有氧稳步筑牢。"

        # Top performer & longest run mention (concise: ~30-40 chars)
        highlights = []
        if podium:
            c = podium[0]
            highlights.append(f"领跑【{c['display_name']}】({c['distance_km']}km)")
        if longest_run and longest_run.get("distance_km", 0) >= 15:
            highlights.append(f"最长突破【{longest_run['runner_name']}】({longest_run['distance_km']}km)")
        
        highlight_str = f"{'与'.join(highlights)}树立中坚榜样。" if highlights else ""

        # Advice for next period based on Canova philosophy (~40-50 chars)
        if period_type == "week":
            coach_advice = "教练建议：大负荷后保证48小时结缔组织超量恢复，严格遵循80/20极化法则，低心率慢跑稳固微循环。"
        else:
            coach_advice = "教练建议：进入新月度后逐步向专项配速收敛，强化巡航节律与抗疲劳韧性，赛前安排科学减量。"

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
        period_index: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generates comprehensive weekly or monthly training report for a club.
        period_type: 'week' or 'month'
        period_index: week number (1..53) or month number (1..12)
        """
        club = LocalStore.get_club(club_id)
        if not club:
            return {"error": "跑团不存在"}

        today = get_beijing_today()
        now_year = today.year
        now_month = today.month
        target_year = year or now_year

        if period_type == "month":
            target_month = period_index or now_month
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
        else:
            # period_type == 'week'
            iso_year, iso_week, _ = today.isocalendar()
            target_week = period_index or iso_week
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
                "total_distance_km": 0.0,
                "total_activities_count": 0,
                "active_members_count": 0,
                "total_members_count": 0,
                "attendance_rate_pct": 0.0,
                "avg_pace_str": "—",
                "total_elevation_gain_m": 0,
                "total_trimp": 0.0,
                "leaderboard": [],
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
                ORDER BY a.start_time DESC
            """
            cursor.execute(query, uids + [start_iso, end_iso])
            act_rows = [dict(r) for r in cursor.fetchall()]

        # Aggregate team stats
        total_distance_m = sum(float(a.get("distance_meters") or 0) for a in act_rows)
        total_moving_s = sum(int(a.get("moving_time_seconds") or 0) for a in act_rows)
        total_elev_m = sum(float(a.get("elevation_gain_meters") or 0) for a in act_rows)
        total_trimp = sum(float(a.get("trimp") or 0) for a in act_rows)
        total_acts_count = len(act_rows)

        total_distance_km = round(total_distance_m / 1000.0, 1)
        total_elev_int = int(round(total_elev_m))
        total_trimp_round = round(total_trimp, 1)

        # Team average pace
        if total_distance_m > 0 and total_moving_s > 0:
            sec_km = int(round(total_moving_s / (total_distance_m / 1000.0)))
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

                member_stats_map[uid]["distance_m"] += dm
                member_stats_map[uid]["moving_s"] += ms
                member_stats_map[uid]["activities_count"] += 1
                if day_str:
                    member_stats_map[uid]["run_days"].add(day_str)
                member_stats_map[uid]["elevation_m"] += el
                member_stats_map[uid]["trimp"] += tr
                if dm > member_stats_map[uid]["longest_m"]:
                    member_stats_map[uid]["longest_m"] = dm

        # Format leaderboard
        leaderboard = []
        active_uids = set()
        for uid, stat in member_stats_map.items():
            km = round(stat["distance_m"] / 1000.0, 1)
            if stat["activities_count"] > 0:
                active_uids.add(uid)
            if stat["distance_m"] > 0 and stat["moving_s"] > 0:
                s_km = int(round(stat["moving_s"] / (stat["distance_m"] / 1000.0)))
                p_str = f"{s_km // 60}:{s_km % 60:02d} /km"
            else:
                p_str = "—"
            
            leaderboard.append({
                "user_id": uid,
                "display_name": stat["display_name"],
                "avatar_url": stat["avatar_url"],
                "role": stat["role"],
                "distance_km": km,
                "runs_count": stat["activities_count"],
                "active_days_count": len(stat["run_days"]),
                "avg_pace_str": p_str,
                "elevation_gain_m": int(round(stat["elevation_m"])),
                "trimp": round(stat["trimp"], 1),
                "longest_km": round(stat["longest_m"] / 1000.0, 2)
            })

        # Sort leaderboard by distance descending, then by runs_count
        leaderboard.sort(key=lambda x: (x["distance_km"], x["runs_count"]), reverse=True)
        for i, item in enumerate(leaderboard):
            item["rank"] = i + 1

        active_count = len(active_uids)
        total_members_count = len(members)
        attendance_rate = round(active_count / total_members_count * 100, 1) if total_members_count > 0 else 0.0

        # Podium (Top 3 with distance > 0)
        podium = [item for item in leaderboard if item["distance_km"] > 0][:3]

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
            longest_run=longest_run
        )

        # Ready-to-copy WeChat group forwarding text
        forward_lines = [
            f"🏃‍♂️ 【{club_name}】{period_label}战报出炉！🔥",
            f"━━━━━━━━━━━━━━━━━━",
            f"📅 统计周期：{date_range_str}",
            f"📊 全团总跑量：{total_distance_km} km",
            f"🎯 打卡总人次：{total_acts_count} 次",
            f"👥 队员出勤率：{active_count}/{total_members_count} 人 ({attendance_rate}%)",
            f"⏱️ 全团平均配速：{avg_pace_str}",
            f"⛰️ 累计爬升克服：+{total_elev_int} m",
            f"━━━━━━━━━━━━━━━━━━",
            f"🏆 【荣耀榜单 Top 3】"
        ]

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
        if hardcore_runner and hardcore_runner.get("runs_count", 0) > 0:
            forward_lines.append(f"🌟 毅力先锋：{hardcore_runner['display_name']} (打卡 {hardcore_runner['runs_count']} 次)")
        if longest_run:
            forward_lines.append(f"🚀 最长突破：{longest_run['runner_name']} ({longest_run['distance_km']} km · {longest_run['avg_pace_str']})")

        forward_lines.append("━━━━━━━━━━━━━━━━━━")
        forward_lines.append(f"💡 【Renato Canova 科学耐力团队复盘】\n{canova_critique}")
        forward_lines.append("━━━━━━━━━━━━━━━━━━")
        forward_lines.append("各位跑友请紧扣耐力周期，注意超量恢复，健康奔跑，下周继续刷新更好的自己！💪")

        forward_text = "\n".join(forward_lines)

        return {
            "club_id": club_id,
            "club_name": club_name,
            "period_type": period_type,
            "period_label": period_label,
            "date_range_str": date_range_str,
            "start_date": start_date_obj.isoformat(),
            "end_date": end_date_obj.isoformat(),
            "total_distance_km": total_distance_km,
            "total_activities_count": total_acts_count,
            "active_members_count": active_count,
            "total_members_count": total_members_count,
            "attendance_rate_pct": attendance_rate,
            "avg_pace_str": avg_pace_str,
            "total_elevation_gain_m": total_elev_int,
            "total_trimp": total_trimp_round,
            "leaderboard": leaderboard,
            "podium": podium,
            "hardcore_runner": hardcore_runner,
            "longest_run": longest_run,
            "canova_critique": canova_critique,
            "forward_text": forward_text
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

        if dist_km < 1.0:
            return "短距离激活训练，建议结合动态拉伸与下肢力量辅助练习。"

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
        age_advice = ""
        if age and age >= 50:
            age_advice = "（大师组队员大负荷后结缔组织与肌糖原再生需充裕时间，建议保证 48~72 小时超量恢复窗口并强化核心抗阻力量）"

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

        m_pb = _parse_pb(profile.get("marathon_pb") if profile else None)
        h_pb = _parse_pb(profile.get("half_pb") or profile.get("half_marathon_pb") if profile else None)
        raw_years = profile.get("years_running") or 1 if profile else 1
        try:
            years = float(raw_years)
        except Exception:
            years = 1.0

        is_elite = bool((m_pb and m_pb <= 3 * 3600 + 15 * 60) or (h_pb and h_pb <= 88 * 60))
        is_beginner = (years <= 1 or (m_pb and m_pb > 4 * 3600 + 15 * 60) or (not m_pb and not h_pb)) and not is_elite

        tier_encourage = ""
        if is_beginner:
            tier_encourage = " 🌟 每一步都在重塑更好的自己，平时牢记 80/20 极化原则保持低心率慢跑积累，不急于求成！"
        elif is_elite:
            tier_encourage = " ⚡ 专项指标达成，紧扣下一阶段配速收敛与边际增益。"

        # Check for Trail / Mountain running
        is_trail = elev_gain >= 200 or "越野" in act_name or "山" in act_name or "trail" in act_name.lower()
        if is_trail:
            if elev_gain >= 500 or dist_km >= 20:
                workout_type = "Renato Canova 山地大爬升专项耐力 (Mountain D+ Specific Endurance)"
                analysis = f"本次克服累计爬升 +{int(elev_gain)}m，推进 {dist_km}km，均心率 {avg_hr or '—'}bpm。不仅考验心肺氧转，更是对股四头肌离心抗撕裂能力与长陡坡快步走 (Power Hiking) 专项神经肌肉募集的深度刺激。"
                advice = f"山地下坡离心收缩对下肢肌纤维微损伤较深，建议课后 30 分钟内足量补充蛋白质与电解质，做好大腿前侧与髂胫束筋膜滚压放松。{age_advice}{tier_encourage}"
            else:
                workout_type = "山地起伏路有氧感知 (Trail Undulation Aerobic)"
                analysis = f"山地起伏推进 {dist_km}km (爬升 +{int(elev_gain)}m)，均速 {pace_str}。有效激活非铺装路面下肢踝关节本体感觉与核心抗扭转平衡。"
                advice = f"越野重在时间负荷与心率稳态，注意下坡落脚缓震，避免关节硬着陆。{age_advice}{tier_encourage}"
            return f"【{workout_type}】{analysis} 💡 教练建议：{advice}"

        pace_seconds = 330
        if ":" in pace_str:
            try:
                parts = pace_str.split(":")
                pace_seconds = int(parts[0]) * 60 + int(parts[1])
            except Exception:
                pass

        if dist_km >= 20:
            if avg_hr and avg_hr < aerobic_ceiling:
                workout_type = "Renato Canova 基础长距离耐力课 (Fundamental Aerobic Long Run)"
                analysis = f"本次完成 {dist_km}km，配速 {pace_str}，平均心率 {avg_hr}bpm (低于个人的有氧上限 {int(aerobic_ceiling)}bpm)。极佳的有氧基础支撑，微血管网与慢肌纤维氧化供能得到充分激活。"
                advice = f"核心耐力储备极佳！明日建议安排彻底休整或 6~8km 超低心率排酸慢跑。{age_advice}{tier_encourage}"
            else:
                workout_type = "马拉松专项耐力刺激 (Specific Marathon Endurance)"
                analysis = f"本次高质量推进 {dist_km}km，配速 {pace_str}，心率维持在 {avg_hr or '中高'}bpm。属于典型的 Canova 专项耐力构建课，有效推升后程抗疲劳韧性。"
                advice = f"肌糖原消耗深度较大，建议 30 分钟内足量补充优质碳水与电解质，后天再安排主课。{age_advice}{tier_encourage}"
        elif dist_km >= 12:
            if avg_hr and avg_hr >= threshold_ceiling:
                workout_type = "快速持续跑 / 混氧门槛突破 (Fast Continuous Progression)"
                analysis = f"本次推进 {dist_km}km，配速达 {pace_str}，平均心率 {avg_hr}bpm 触达乳酸门槛区。乳酸清除速率与摄氧效率兼备，有效推高乳酸门槛巡航速度。"
                advice = f"高强度课完成质量极高！接下来 48 小时应以低心率慢跑排酸为主，避免连续大负荷。{age_advice}{tier_encourage}"
            else:
                workout_type = "稳态专项有氧进阶 (Aerobic Endurance Progression)"
                analysis = f"完成 {dist_km}km 专项课，配速 {pace_str}，心率负荷处于稳态吸收区间（TRIMP: {trimp}）。心率漂移可控，肌肉收缩力与步频节奏协调。"
                advice = f"训练节奏保持得非常好，建议课后做好腘绳肌与小腿放松。{age_advice}{tier_encourage}"
        elif dist_km >= 6:
            if avg_hr and avg_hr < recovery_ceiling:
                workout_type = "低心率排酸主动恢复 (Active Recovery Run)"
                analysis = f"轻松完成 {dist_km}km，平均心率 {avg_hr}bpm (低于恢复阈值 {int(recovery_ceiling)}bpm)。有效促进下肢微循环，加速代谢废物清除，无额外中枢神经疲劳负担。"
                advice = f"极佳的恢复跑执行力！身体已充分就绪，下一堂主课可按计划冲击目标配速。{tier_encourage}"
            else:
                workout_type = "日常基础有氧构建 (General Aerobic Foundation)"
                analysis = f"跑程 {dist_km}km，配速 {pace_str}，平均心率 {avg_hr or '—'}bpm。步态节奏平稳，有效维持有氧基础与下肢肌腱刚性。"
                advice = f"课表执行到位，明天可根据体感自由选择休整或轻度慢跑。{age_advice}{tier_encourage}"
        else:
            workout_type = "短程激活与速度感知 (Short Activation Run)"
            analysis = f"短程奔跑 {dist_km}km，步频顺畅，适合赛前神经激活或大强度课后的排酸调整。"
            advice = f"适度热身与拉伸，保持良好身体机能。{age_advice}{tier_encourage}"

        return f"【{workout_type}】{analysis} 💡 教练建议：{advice}"

    @staticmethod
    def toggle_activity_like(activity_id: str, user_id: str) -> Dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM activity_likes WHERE activity_id = ? AND user_id = ?", (activity_id, user_id))
            row = cursor.fetchone()
            if row:
                cursor.execute("DELETE FROM activity_likes WHERE activity_id = ? AND user_id = ?", (activity_id, user_id))
                liked = False
            else:
                like_id = f"like_{activity_id}_{user_id}"
                cursor.execute("""
                    INSERT INTO activity_likes (id, activity_id, user_id, created_at)
                    VALUES (?, ?, ?, ?)
                """, (like_id, activity_id, user_id, datetime.utcnow().isoformat() + "Z"))
                liked = True
            conn.commit()

            cursor.execute("SELECT COUNT(*) FROM activity_likes WHERE activity_id = ?", (activity_id,))
            likes_count = cursor.fetchone()[0]

            return {"liked": liked, "likes_count": likes_count}

    @staticmethod
    def add_activity_comment(activity_id: str, user_id: str, author_name: str, author_avatar: str, content: str) -> Dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            comment_id = f"cmt_{int(datetime.utcnow().timestamp()*1000)}"
            now_str = datetime.utcnow().isoformat() + "Z"
            cursor.execute("""
                INSERT INTO activity_comments (id, activity_id, user_id, author_name, author_avatar, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (comment_id, activity_id, user_id, author_name, author_avatar, content, now_str))
            conn.commit()

            return {
                "id": comment_id,
                "activity_id": activity_id,
                "user_id": user_id,
                "author_name": author_name,
                "author_avatar": author_avatar,
                "content": content,
                "created_at": now_str
            }

    @staticmethod
    def delete_activity_comment(comment_id: str, user_id: Optional[str] = None) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute("DELETE FROM activity_comments WHERE id = ? AND user_id = ?", (comment_id, user_id))
            else:
                cursor.execute("DELETE FROM activity_comments WHERE id = ?", (comment_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def get_activity_social(activity_id: str, current_uid: Optional[str] = None) -> Dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM activity_likes WHERE activity_id = ?", (activity_id,))
            likes_count = cursor.fetchone()[0]

            has_liked = False
            if current_uid:
                cursor.execute("SELECT 1 FROM activity_likes WHERE activity_id = ? AND user_id = ?", (activity_id, current_uid))
                has_liked = cursor.fetchone() is not None

            cursor.execute("""
                SELECT c.id, c.activity_id, c.user_id, 
                       COALESCE(NULLIF(p.display_name, ''), c.author_name) AS author_name,
                       COALESCE(NULLIF(p.avatar_url, ''), c.author_avatar) AS author_avatar,
                       c.content, c.created_at 
                FROM activity_comments c
                LEFT JOIN profiles p ON c.user_id = p.id
                WHERE c.activity_id = ? 
                ORDER BY c.created_at ASC
            """, (activity_id,))
            comments = [dict(r) for r in cursor.fetchall()]

            return {
                "likes_count": likes_count,
                "has_liked": has_liked,
                "comments": comments
            }

    @staticmethod
    def get_club_recent_activities(
        club_id: str,
        current_uid: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        before_time: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        members = LocalStore.get_club_members(club_id)
        uids = [m["user_id"] for m in members]
        if not uids:
            return [], 0

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            placeholders = ["?"] * len(uids)

            # Get total count of club activities for pagination
            cursor.execute(f"SELECT COUNT(*) FROM activities WHERE user_id IN ({','.join(placeholders)})", uids)
            total_row = cursor.fetchone()
            total = total_row[0] if total_row else 0

            params = list(uids)
            time_filter = ""
            if before_time:
                time_filter = "AND a.start_time < ?"
                params.append(before_time)

            params.extend([max(1, limit), max(0, offset)])
            query = f"""
                SELECT a.*, COALESCE(NULLIF(p.display_name, ''), a.user_id) AS display_name, p.avatar_url 
                FROM activities a
                LEFT JOIN profiles p ON a.user_id = p.id
                WHERE a.user_id IN ({','.join(placeholders)})
                {time_filter}
                ORDER BY a.start_time DESC
                LIMIT ? OFFSET ?
            """
            cursor.execute(query, params)
            rows = [dict(r) for r in cursor.fetchall()]

        # Ensure AI critique and attach social data
        enriched = []
        for act in rows:
            act_id = act["id"]
            ai_journal = act.get("ai_journal")
            if not ai_journal or not ai_journal.strip():
                ai_journal = LocalStore.generate_canova_critique(act)
                act["ai_journal"] = ai_journal
                # Persist generated critique
                with sqlite3.connect(DB_PATH) as conn:
                    conn.cursor().execute("UPDATE activities SET ai_journal = ? WHERE id = ?", (ai_journal, act_id))
                    conn.commit()

            social = LocalStore.get_activity_social(act_id, current_uid)
            act["likes_count"] = social["likes_count"]
            act["has_liked"] = social["has_liked"]
            act["comments"] = social["comments"]
            enriched.append(act)

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
        members = LocalStore.get_club_members(club_id)
        uids = [m["user_id"] for m in members]
        if not uids:
            return [], 0, 0

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
            placeholders = ["?"] * len(uids)

            # Total count all time
            cursor.execute(f"SELECT COUNT(*) FROM activities WHERE user_id IN ({','.join(placeholders)})", uids)
            total_row = cursor.fetchone()
            total_all_time = total_row[0] if total_row else 0

            # Total count for the month
            cursor.execute(f"""
                SELECT COUNT(*) FROM activities 
                WHERE user_id IN ({','.join(placeholders)})
                  AND start_time >= ? AND start_time < ?
            """, uids + [month_start, next_month_start])
            month_row = cursor.fetchone()
            month_total = month_row[0] if month_row else 0

            # Fetch all activities for the month (ordered by start_time DESC)
            query = f"""
                SELECT a.*, COALESCE(NULLIF(p.display_name, ''), a.user_id) AS display_name, p.avatar_url 
                FROM activities a
                LEFT JOIN profiles p ON a.user_id = p.id
                WHERE a.user_id IN ({','.join(placeholders)})
                  AND a.start_time >= ? AND a.start_time < ?
                ORDER BY a.start_time DESC
            """
            cursor.execute(query, uids + [month_start, next_month_start])
            rows = [dict(r) for r in cursor.fetchall()]

        # Ensure AI critique and attach social data
        enriched = []
        for act in rows:
            act_id = act["id"]
            ai_journal = act.get("ai_journal")
            if not ai_journal or not ai_journal.strip():
                try:
                    ai_journal = LocalStore.generate_canova_critique(act)
                    act["ai_journal"] = ai_journal
                    with sqlite3.connect(DB_PATH) as conn:
                        conn.cursor().execute("UPDATE activities SET ai_journal = ? WHERE id = ?", (ai_journal, act_id))
                        conn.commit()
                except Exception as ex:
                    logger.warning(f"Generate critique in get_club_month_activities failed: {ex}")

            social = LocalStore.get_activity_social(act_id, current_uid)
            act["likes_count"] = social["likes_count"]
            act["has_liked"] = social["has_liked"]
            act["comments"] = social["comments"]
            enriched.append(act)

        return enriched, month_total, total_all_time

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
    def upsert_training_plan(plan_data: Dict[str, Any]) -> Dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            now_iso = datetime.utcnow().isoformat() + "Z"
            plan_id = plan_data.get("id") or f"plan_{int(datetime.utcnow().timestamp()*1000)}"

            # If new plan is active, optionally archive other active plans for this user
            if plan_data.get("status") == "active":
                cursor.execute("""
                    UPDATE training_plans 
                    SET status = 'archived', updated_at = ? 
                    WHERE user_id = ? AND status = 'active' AND id != ?
                """, (now_iso, plan_data["user_id"], plan_id))

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
                    overview_summary, schedule_data, creator_id, last_modified_by,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                plan_data.get("status", "active"),
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
    def reconcile_training_plan_activities(plan: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
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
        canonical_uid = LocalStore.resolve_user_id(uid)

        start_date_str = str(plan.get("start_date") or "")
        now_beijing = datetime.utcnow() + timedelta(hours=8)
        today_str = now_beijing.strftime("%Y-%m-%d")

        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                if start_date_str:
                    cursor.execute("""
                        SELECT id, name, sport_type, start_time, distance_meters, 
                               moving_time_seconds, avg_pace_str, average_heartrate
                        FROM activities
                        WHERE (user_id = ? OR user_id = ?) AND start_time >= ?
                        ORDER BY start_time ASC
                    """, (canonical_uid, uid, start_date_str))
                else:
                    cursor.execute("""
                        SELECT id, name, sport_type, start_time, distance_meters, 
                               moving_time_seconds, avg_pace_str, average_heartrate
                        FROM activities
                        WHERE user_id = ? OR user_id = ?
                        ORDER BY start_time ASC
                    """, (canonical_uid, uid))
                act_rows = [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error querying activities for plan reconciliation: {e}")
            act_rows = []

        acts_by_day: Dict[str, List[Dict[str, Any]]] = {}
        for a in act_rows:
            st = str(a.get("start_time") or "")[:10]
            if st:
                if st not in acts_by_day:
                    acts_by_day[st] = []
                acts_by_day[st].append(a)

        changed = False
        for w in weeks:
            for day in (w.get("days") or []):
                d_date = str(day.get("date") or "")
                w_type = day.get("workout_type") or "easy_run"
                is_rest = (w_type == "rest")
                dist_km = float(day.get("distance_km") or 0.0)

                matching_acts = acts_by_day.get(d_date, [])
                if matching_acts:
                    total_m = sum(float(a.get("distance_meters") or 0.0) for a in matching_acts)
                    actual_km = round(total_m / 1000.0, 1)
                    primary_act = matching_acts[-1]
                    pace = primary_act.get("avg_pace_str") or "—"
                    hr = primary_act.get("average_heartrate")

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
                else:
                    if day.get("manual_completed"):
                        if not day.get("completed"):
                            day["completed"] = True
                            changed = True
                        if day.get("is_missed"):
                            day["is_missed"] = False
                            changed = True
                    elif day.get("manual_override"):
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

        plan_id = plan.get("id")
        if changed and plan_id:
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
    def _enrich_plan_with_current_week(plan: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not plan:
            return None
        sched = plan.get("schedule_data") or {}
        if isinstance(sched, str):
            try:
                sched = json.loads(sched)
                plan["schedule_data"] = sched
            except Exception:
                sched = {}
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
                # Fallback to latest plan
                cursor.execute("""
                    SELECT * FROM training_plans 
                    WHERE user_id = ? OR user_id = ?
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
    def get_user_training_plans(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        canonical_uid = LocalStore.resolve_user_id(user_id)
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, club_id, title, goal_type, maintenance_focus,
                       target_race_name, target_date, start_date, end_date,
                       weeks_count, days_per_week, preferred_long_run_day, status,
                       overview_summary, creator_id, last_modified_by, created_at, updated_at
                FROM training_plans 
                WHERE user_id = ? OR user_id = ?
                ORDER BY updated_at DESC LIMIT ?
            """, (canonical_uid, user_id, limit))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def update_training_plan_workout(
        plan_id: str, 
        week_index: int, 
        day_index: int, 
        workout_update: Dict[str, Any], 
        operator_uid: str
    ) -> Optional[Dict[str, Any]]:
        plan = LocalStore.get_training_plan(plan_id, reconcile=False)
        if not plan:
            return None

        sched = plan.get("schedule_data") or {}
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

        # Apply updates
        for key in ["workout_type", "title", "distance_km", "target_pace", "target_hr_zone", "description", "completed", "coach_notes"]:
            if key in workout_update:
                target_day[key] = workout_update[key]

        if "completed" in workout_update:
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

        now_iso = datetime.utcnow().isoformat() + "Z"
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE training_plans 
                SET schedule_data = ?, last_modified_by = ?, updated_at = ?
                WHERE id = ?
            """, (json.dumps(sched, ensure_ascii=False), operator_uid, now_iso, plan_id))
            conn.commit()

        return LocalStore.get_training_plan(plan_id, reconcile=False)

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
            cursor.execute("""
                SELECT id, name, sport_type, start_time, distance_meters, moving_time_seconds, 
                       elapsed_time_seconds, avg_pace_str, elevation_gain_meters, 
                       average_heartrate, max_heartrate, trimp
                FROM activities
                WHERE (user_id = ? OR user_id = ?) AND start_time >= ?
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
    def get_org_field_rules(org_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT settings FROM organizations WHERE id = ?", (org_id,))
            row = cursor.fetchone()
            if not row:
                return copy.deepcopy(DEFAULT_ORG_FIELD_RULES)
            settings_str = row["settings"]
            if settings_str:
                try:
                    s_dict = json.loads(settings_str)
                    if isinstance(s_dict, dict) and "field_rules" in s_dict and isinstance(s_dict["field_rules"], list):
                        return s_dict["field_rules"]
                except Exception:
                    pass
            return copy.deepcopy(DEFAULT_ORG_FIELD_RULES)

    @staticmethod
    def update_org_field_rules(org_id: str, field_rules: List[Dict[str, Any]]) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT settings FROM organizations WHERE id = ?", (org_id,))
            row = cursor.fetchone()
            if not row:
                return False
            s_dict = {}
            if row[0]:
                try:
                    s_dict = json.loads(row[0])
                except Exception:
                    s_dict = {}
            if not isinstance(s_dict, dict):
                s_dict = {}
            s_dict["field_rules"] = field_rules
            cursor.execute("UPDATE organizations SET settings = ? WHERE id = ?", (json.dumps(s_dict, ensure_ascii=False), org_id))
            conn.commit()
            return True

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
                if r.get("required"):
                    f = r["field"]
                    val = field_values.get(f)
                    if val is None or str(val).strip() == "" or (r.get("type") == "boolean" and not val):
                        missing_fields.append({"field": f, "label": r.get("label", f)})

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
                    "missing_fields": missing_fields
                }

            if status == "confirmed":
                return {
                    "is_member": True,
                    "status": "confirmed",
                    "role": role,
                    "is_valid": True,
                    "days_remaining": None,
                    "missing_fields": missing_fields
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
                    conn.commit()
                return {
                    "is_member": True,
                    "status": "expired",
                    "role": role,
                    "is_valid": False,
                    "days_remaining": 0,
                    "missing_fields": missing_fields
                }

            current_status = "temporary" if len(missing_fields) > 0 else "pending"
            if member.get("status") != current_status:
                cursor.execute("UPDATE organization_members SET status = ? WHERE org_id = ? AND user_id = ?", (current_status, org_id, user_id))
                conn.commit()

            return {
                "is_member": True,
                "status": current_status,
                "role": role,
                "is_valid": True,
                "days_remaining": remaining_days,
                "missing_fields": missing_fields
            }

    @staticmethod
    def validate_sub_club_join_eligibility(club_dict: Dict[str, Any], user_id: str):
        org_id = club_dict.get("org_id")
        if not org_id:
            return

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM organizations WHERE id = ?", (org_id,))
            org_row = cursor.fetchone()
            org_name = org_row["name"] if org_row else "大群体"

        status_info = LocalStore.check_org_member_status(org_id, user_id)
        if not status_info.get("is_member"):
            raise ValueError(f"加入【{club_dict.get('name')}】失败：该跑团隶属于【{org_name}】大群。您尚未加入该大群，请先加入大群并完成实名资料审核！")

        status = status_info.get("status")
        if status == "expired":
            raise ValueError(f"加入【{club_dict.get('name')}】失败：您在【{org_name}】大群的临时身份已过期（超过2周未获审核）。无法加入下属跑团，请联系管理员或重新认证！")
        elif status == "temporary":
            missing = "、".join([m["label"] for m in status_info.get("missing_fields", [])]) or "必填资料"
            raise ValueError(f"加入【{club_dict.get('name')}】失败：该跑团隶属于【{org_name}】大群。您当前为临时人员，尚未填写全部必填资料（缺少：{missing}）并获得管理员审核批准，暂无法加入下属跑团！")
        elif status == "pending":
            raise ValueError(f"加入【{club_dict.get('name')}】失败：该跑团隶属于【{org_name}】大群。您的入群资料已提交，正等待大群管理员审核批准，审批通过后方可加入下属跑团！")
        elif status != "confirmed":
            raise ValueError(f"加入【{club_dict.get('name')}】失败：根据【{org_name}】群规，必须在完成全部必填资料并获得管理员核验批准后方可加入下属跑团（当前状态：{status}）。")

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
                d["field_rules"] = LocalStore.get_org_field_rules(d["id"])
                return d
            return None

    @staticmethod
    def join_organization(
        user_id: str,
        invite_code: str,
        real_name: Optional[str] = None,
        gender: Optional[str] = "male",
        date_of_birth: Optional[str] = None,
        class_name: Optional[str] = None,
        phone: Optional[str] = None,
        id_card: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validates invite code, registers member into organization_members with encrypted sensitive fields,
        and dynamically determines status (temporary / pending / confirmed) based on field rules.
        """
        clean_code = (invite_code or "").strip().upper()
        clean_name = (real_name or "").strip()
        clean_dob = (date_of_birth or "").strip()
        clean_phone = (phone or "").strip()
        clean_id_card = (id_card or "").strip()
        clean_class = (class_name or "").strip()
        clean_gender = (gender or "male").strip()

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM organizations WHERE UPPER(invite_code) = ?", (clean_code,))
            org_row = cursor.fetchone()
            if not org_row:
                raise ValueError("无效的大组织邀请码，请向组织管理员核实后重新输入！")
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

            # Check field rules
            rules = LocalStore.get_org_field_rules(org_id)
            field_values = {
                "real_name": clean_name,
                "gender": clean_gender,
                "date_of_birth": clean_dob,
                "class_name": clean_class,
                "phone": clean_phone,
                "id_card": clean_id_card,
                **merged_extra
            }
            missing_fields = []
            for r in rules:
                if r.get("required"):
                    f = r["field"]
                    val = field_values.get(f)
                    if val is None or str(val).strip() == "" or (r.get("type") == "boolean" and not val):
                        missing_fields.append({"field": f, "label": r.get("label", f)})

            if role in ("owner", "admin") or (existing and existing["status"] == "confirmed"):
                status = "confirmed"
            elif len(missing_fields) > 0:
                status = "temporary"
            else:
                status = "pending"

            # If rejoining after expiry, give fresh joined_at
            if existing and existing["status"] == "expired":
                joined_at = now
            elif existing and existing["joined_at"]:
                joined_at = existing["joined_at"]
            else:
                joined_at = now

            confirmed_at = now if status == "confirmed" else (existing["confirmed_at"] if existing and status == "confirmed" else None)
            confirmed_by = (org.get("owner_id") or "admin") if status == "confirmed" else (existing["confirmed_by"] if existing and status == "confirmed" else None)

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

            joined_dt = parse_iso_datetime(joined_at)
            elapsed_days = (datetime.now(timezone.utc) - joined_dt).total_seconds() / 86400.0 if joined_dt else 0
            remaining_days = max(0, math.ceil(14.0 - elapsed_days)) if status in ("temporary", "pending") else None

            return {
                "org_id": org_id,
                "org_name": org["name"],
                "org_logo": org["logo_url"],
                "real_name": clean_name,
                "class_name": clean_class,
                "gender": clean_gender,
                "date_of_birth": clean_dob,
                "phone": clean_phone,
                "id_card": clean_id_card,
                "status": status,
                "role": role,
                "days_remaining": remaining_days,
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
            if status_info.get("status") == "expired":
                raise ValueError("您在大群体的临时访问权限已过期（超过2周未完成审核）。如需继续参与，请联系管理员或重新输入邀请码加入！")

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

            clean_class = data.get("class_name")
            if clean_class is not None:
                clean_class = clean_class.strip()
            else:
                clean_class = member.get("class_name") or ""

            clean_gender = data.get("gender")
            if clean_gender is not None:
                clean_gender = clean_gender.strip()
            else:
                clean_gender = member.get("gender") or "male"

            merged_extra = {}
            if member.get("extra_data"):
                try:
                    merged_extra = json.loads(member["extra_data"])
                except Exception:
                    merged_extra = {}
            if data.get("extra_data"):
                merged_extra.update(data["extra_data"])

            rules = LocalStore.get_org_field_rules(org_id)
            field_values = {
                "real_name": clean_name,
                "gender": clean_gender,
                "date_of_birth": clean_dob,
                "class_name": clean_class,
                "phone": clean_phone,
                "id_card": clean_id_card,
                **merged_extra
            }
            missing_fields = []
            for r in rules:
                if r.get("required"):
                    f = r["field"]
                    val = field_values.get(f)
                    if val is None or str(val).strip() == "" or (r.get("type") == "boolean" and not val):
                        missing_fields.append({"field": f, "label": r.get("label", f)})

            role = member.get("role") or "member"
            current_status = member.get("status")
            if role in ("owner", "admin") or current_status == "confirmed":
                status = "confirmed"
            elif len(missing_fields) > 0:
                status = "temporary"
            else:
                status = "pending"

            enc_real_name = encrypt_pii(clean_name)
            enc_dob = encrypt_pii(clean_dob)
            enc_phone = encrypt_pii(clean_phone) if clean_phone else ""
            enc_id_card = encrypt_pii(clean_id_card) if clean_id_card else ""
            extra_str = json.dumps(merged_extra, ensure_ascii=False)

            cursor.execute("""
                UPDATE organization_members
                SET real_name = ?, gender = ?, date_of_birth = ?, class_name = ?,
                    phone = ?, id_card = ?, status = ?, extra_data = ?
                WHERE id = ?
            """, (enc_real_name, clean_gender, enc_dob, clean_class, enc_phone, enc_id_card, status, extra_str, membership_id))

            cursor.execute("""
                UPDATE profiles
                SET real_name = ?, gender = ?, date_of_birth = ?,
                    phone = CASE WHEN ? != '' THEN ? ELSE phone END,
                    id_card = CASE WHEN ? != '' THEN ? ELSE id_card END
                WHERE id = ?
            """, (enc_real_name, clean_gender, enc_dob, enc_phone, enc_phone, enc_id_card, enc_id_card, user_id))

            conn.commit()

            joined_at = member.get("joined_at")
            joined_dt = parse_iso_datetime(joined_at)
            elapsed_days = (datetime.now(timezone.utc) - joined_dt).total_seconds() / 86400.0 if joined_dt else 0
            remaining_days = max(0, math.ceil(14.0 - elapsed_days)) if status in ("temporary", "pending") else None

            return {
                "org_id": org_id,
                "user_id": user_id,
                "real_name": clean_name,
                "class_name": clean_class,
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
            org_id = club_dict.get("org_id")
            now = datetime.utcnow().isoformat() + "Z"
            
            # If club belongs to an org, ensure member is confirmed in that org
            if org_id:
                cursor.execute("SELECT * FROM organization_members WHERE org_id = ? AND user_id = ?", (org_id, user_id))
                om = cursor.fetchone()
                if om:
                    cursor.execute("UPDATE organization_members SET status = 'confirmed', confirmed_at = ?, confirmed_by = 'admin' WHERE org_id = ? AND user_id = ?", (now, org_id, user_id))

            membership_id = f"{club_id}_{user_id}"
            cursor.execute("""
                INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                VALUES (?, ?, ?, COALESCE((SELECT role FROM club_memberships WHERE id = ?), 'member'), 'active', ?, 1)
            """, (membership_id, club_id, user_id, membership_id, now))
            conn.commit()
            return club_dict

    @staticmethod
    def get_user_organizations(user_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT o.id, o.name, o.logo_url, o.description, o.city,
                       m.real_name, m.gender, m.date_of_birth, m.class_name, m.phone, m.id_card, m.role, m.status, m.joined_at, m.confirmed_at, m.extra_data
                FROM organization_members m
                JOIN organizations o ON m.org_id = o.id
                WHERE m.user_id = ?
                ORDER BY m.joined_at ASC
            """, (user_id,))
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
                
                # Check status and expiry
                status_info = LocalStore.check_org_member_status(d["id"], user_id)
                d["status"] = status_info.get("status")
                d["days_remaining"] = status_info.get("days_remaining")
                d["missing_fields"] = status_info.get("missing_fields", [])
                d["is_valid"] = status_info.get("is_valid", True)
                d["is_expired"] = bool(status_info.get("status") == "expired")

                extra = {}
                if d.get("extra_data"):
                    try:
                        extra = json.loads(d["extra_data"])
                    except Exception:
                        pass
                d["extra_data"] = extra

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
                if status_info:
                    st = status_info.get("status")
                    d["can_join"] = bool(st == "confirmed")
                    d["user_org_status"] = st
                    d["user_org_days_remaining"] = status_info.get("days_remaining")
                    if st != "confirmed":
                        if st == "temporary":
                            missing_labels = "、".join([m["label"] for m in status_info.get("missing_fields", [])]) or "必填字段"
                            d["join_restriction_reason"] = f"临时人员，缺少必填资料（{missing_labels}）"
                        elif st == "pending":
                            d["join_restriction_reason"] = "已填齐资料，等待大群管理员审核中"
                        elif st == "expired":
                            d["join_restriction_reason"] = "大群临时权限已到期"
                        else:
                            d["join_restriction_reason"] = "尚未完成大群实名审核"
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
                d["is_valid"] = status_info.get("is_valid", True)

                extra = {}
                if d.get("extra_data"):
                    try:
                        extra = json.loads(d["extra_data"])
                    except Exception:
                        pass
                d["extra_data"] = extra

                if search:
                    s = search.strip().lower()
                    rn = (d.get("real_name") or "").lower()
                    cn = (d.get("class_name") or "").lower()
                    dn = (d.get("display_name") or "").lower()
                    if s not in rn and s not in cn and s not in dn:
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
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM profiles WHERE id = ?", (user_id,))
            if not cursor.fetchone():
                return {"success": False, "message": "用户不存在"}

            anon_name = f"跑者_{user_id[-4:]}" if len(user_id) >= 4 else "跑者_8888"
            default_avatar = "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80"

            cursor.execute("""
                UPDATE profiles
                SET real_name = '',
                    id_card = '',
                    date_of_birth = '',
                    phone = '',
                    email = '',
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

        # Remove local token files if any exist
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
            return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def create_organization(name: str, invite_code: str, description: Optional[str] = None, city: str = "上海", logo_url: Optional[str] = None, owner_id: Optional[str] = None) -> Dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            org_id = f"org_{int(datetime.utcnow().timestamp()*1000)}"
            code = (invite_code or "").strip().upper()
            logo = logo_url or "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=300&auto=format&fit=crop&q=80"
            created_at = datetime.utcnow().isoformat() + "Z"
            cursor.execute("""
                INSERT INTO organizations (id, name, logo_url, description, city, invite_code, owner_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (org_id, name.strip(), logo, description, city, code, owner_id, created_at))
            conn.commit()
            return {
                "id": org_id,
                "name": name.strip(),
                "invite_code": code,
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
            allowed = ["name", "description", "city", "logo_url", "invite_code", "owner_id"]
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
    def create_system_notification(
        user_id: str,
        title: str,
        content: str,
        activity_id: Optional[str] = None,
        notif_type: str = "coach_critique",
        wechat_sent: int = 0,
        wechat_errmsg: Optional[str] = None
    ) -> Dict[str, Any]:
        notif_id = f"notif_{int(time.time() * 1000)}"
        now_str = datetime.utcnow().isoformat() + "Z"
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
                ORDER BY created_at DESC
                LIMIT ?
            """, (canonical_uid, limit))
            return [dict(r) for r in cursor.fetchall()]

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


