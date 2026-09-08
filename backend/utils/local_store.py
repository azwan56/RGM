import sqlite3
import os
import json
import uuid
import random
import string
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta

logger = logging.getLogger("local_store")

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "rgm.db")

def generate_invite_code(length: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace("O", "").replace("0", "").replace("I", "").replace("1", "")
    return "".join(random.choice(chars) for _ in range(length))

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
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)

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
                FOREIGN KEY(user_id) REFERENCES profiles(id)
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

        # ── Multi-Tenant Running Clubs Schema ──
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clubs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                logo_url TEXT,
                description TEXT,
                city TEXT DEFAULT '上海',
                invite_code TEXT UNIQUE,
                owner_id TEXT,
                created_at TEXT,
                settings TEXT,
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
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM profiles WHERE id = ? OR email = ? OR display_name = ?", (uid, uid, uid))
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
        return uid

    @staticmethod
    def get_profile(uid: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profiles WHERE id = ? OR email = ? OR display_name = ?", (uid, uid, uid))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["garmin_connected"] = bool(d.get("garmin_connected"))
                d["coros_connected"] = bool(d.get("coros_connected"))
                return d
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
                return d
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
                return d
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
                return d
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
                result.append(d)
            return result

    @staticmethod
    def delete_profile(uid: str):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM profiles WHERE id = ?", (uid,))
            cursor.execute("DELETE FROM club_memberships WHERE user_id = ?", (uid,))
            conn.commit()

    @staticmethod
    def upsert_profile(uid: str, data: Dict[str, Any]):
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

            cursor.execute("SELECT * FROM profiles WHERE id = ?", (uid,))
            existing = cursor.fetchone()
            if existing:
                fields = []
                values = []
                for k, v in data.items():
                    if k != "id" and k in existing_cols:
                        fields.append(f"{k} = ?")
                        values.append(v)
                if fields:
                    values.append(uid)
                    cursor.execute(f"UPDATE profiles SET {', '.join(fields)} WHERE id = ?", values)
            else:
                data["id"] = uid
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
                "ai_journal", "laps_data", "splits_data"
            ]
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
        start_date = date.today() - timedelta(days=days)
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
        today = date.today()
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
    def get_month_distance_meters(uid: str, month_start: str) -> float:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(distance_meters) FROM activities WHERE user_id = ? AND start_time >= ?", (uid, month_start))
            res = cursor.fetchone()
            return float(res[0]) if res and res[0] is not None else 0.0

    @staticmethod
    def get_weekly_stats(uid: str, target_km: Optional[float] = None) -> Dict[str, Any]:
        canonical_uid = LocalStore.resolve_user_id(uid)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            today = date.today()
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

        now_beijing = datetime.utcnow() + timedelta(hours=8)
        today_iso = now_beijing.strftime("%Y-%m-%d")

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
            
            today = date.today()
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

            today = date.today()
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
                        "sleep_score": int(sleep_score) if sleep_score is not None else None
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
                if p.get("race_date"):
                    try:
                        r_date = datetime.strptime(p["race_date"][:10], "%Y-%m-%d").date()
                        days_left = (r_date - today).days
                        p["days_left"] = max(0, days_left)
                    except Exception:
                        p["days_left"] = 0
                plans.append(p)
            
            return plans

    @staticmethod
    def upsert_race_plan(uid: str, plan_data: Dict[str, Any]):
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

            cursor.execute("""
                INSERT OR REPLACE INTO race_plans (id, user_id, name, race_type, race_date, target_time, priority, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_id,
                uid,
                plan_data.get("name") or "未命名赛事",
                plan_data.get("race_type") or "全马",
                plan_data.get("race_date") or date.today().isoformat(),
                plan_data.get("target_time") or "3:30:00",
                pri,
                datetime.utcnow().isoformat() + "Z"
            ))
            conn.commit()
            return plan_id

    @staticmethod
    def update_race_plan_priority(uid: str, race_identifier: str, priority: int) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE race_plans 
                SET priority = ? 
                WHERE user_id = ? AND (id = ? OR name = ?)
            """, (priority, uid, race_identifier, race_identifier))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def delete_race_plan(uid: str, race_id: str):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM race_plans WHERE id = ? AND user_id = ?", (race_id, uid))
            conn.commit()

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
    def create_club(owner_id: str, name: str, description: Optional[str] = None, city: str = "上海", logo_url: Optional[str] = None) -> Dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            club_id = f"club_{int(datetime.utcnow().timestamp()*1000)}"
            code = generate_invite_code()
            logo = logo_url or "https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80"
            created_at = datetime.utcnow().isoformat() + "Z"

            cursor.execute("""
                INSERT INTO clubs (id, name, logo_url, description, city, invite_code, owner_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (club_id, name, logo, description, city, code, owner_id, created_at))

            cursor.execute("""
                INSERT INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                VALUES (?, ?, ?, 'owner', 'active', ?, 1)
            """, (f"{club_id}_{owner_id}", club_id, owner_id, created_at))

            conn.commit()
            return {
                "id": club_id,
                "name": name,
                "logo_url": logo,
                "description": description,
                "city": city,
                "invite_code": code,
                "owner_id": owner_id,
                "created_at": created_at
            }

    @staticmethod
    def get_club(club_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clubs WHERE id = ?", (club_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    get_club_by_id = get_club

    @staticmethod
    def get_user_clubs(uid: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.*, m.role, m.joined_at, m.privacy_consent
                FROM club_memberships m
                JOIN clubs c ON m.club_id = c.id
                WHERE m.user_id = ? AND m.status = 'active'
                ORDER BY m.joined_at ASC
            """, (uid,))
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
                       p.display_name as owner_name, 
                       p.avatar_url as owner_avatar,
                       p.email as owner_email,
                       (SELECT COUNT(*) FROM club_memberships m WHERE m.club_id = c.id AND m.status = 'active') as member_count
                FROM clubs c
                LEFT JOIN profiles p ON c.owner_id = p.id
                ORDER BY c.created_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def update_club(club_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            allowed = ["name", "description", "city", "logo_url", "invite_code"]
            set_clauses = []
            params = []
            for k in allowed:
                if k in data and data[k] is not None:
                    set_clauses.append(f"{k} = ?")
                    params.append(data[k])
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
        elev_gain = float(activity.get("elevation_gain_meters") or 0)
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
            age_advice = f"（鉴于跑者周岁已满 {age} 岁，大负荷后结缔组织与肌糖原再生需充裕时间，建议保证 48~72 小时超量恢复窗口并强化核心抗阻）"

        # Check for Trail / Mountain running
        is_trail = elev_gain >= 200 or "越野" in act_name or "山" in act_name or "trail" in act_name.lower()
        if is_trail:
            if elev_gain >= 500 or dist_km >= 20:
                workout_type = "Renato Canova 山地大爬升专项耐力 (Mountain D+ Specific Endurance)"
                analysis = f"本次克服累计爬升 +{int(elev_gain)}m，推进 {dist_km}km，均心率 {avg_hr or '—'}bpm。不仅考验心肺氧转，更是对股四头肌离心抗撕裂能力与长陡坡快步走 (Power Hiking) 专项神经肌肉募集的深度刺激。"
                advice = f"山地下坡离心收缩对下肢肌纤维微损伤较深，建议课后 30 分钟内足量补充蛋白质与电解质，做好大腿前侧与髂胫束筋膜滚压放松。{age_advice}"
            else:
                workout_type = "山地起伏路有氧感知 (Trail Undulation Aerobic)"
                analysis = f"山地起伏推进 {dist_km}km (爬升 +{int(elev_gain)}m)，均速 {pace_str}。有效激活非铺装路面下肢踝关节本体感觉与核心抗扭转平衡。"
                advice = f"越野重在时间负荷与心率稳态，注意下坡落脚缓震，避免关节硬着陆。{age_advice}"
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
                advice = f"核心耐力储备极佳！明日建议安排彻底休整或 6~8km 超低心率排酸慢跑。{age_advice}"
            else:
                workout_type = "马拉松专项耐力刺激 (Specific Marathon Endurance)"
                analysis = f"本次高质量推进 {dist_km}km，配速 {pace_str}，心率维持在 {avg_hr or '中高'}bpm。属于典型的 Canova 专项耐力构建课，有效推升后程抗疲劳韧性。"
                advice = f"肌糖原消耗深度较大，建议 30 分钟内足量补充优质碳水与电解质，后天再安排主课。{age_advice}"
        elif dist_km >= 12:
            if avg_hr and avg_hr >= threshold_ceiling:
                workout_type = "快速持续跑 / 混氧门槛突破 (Fast Continuous Progression)"
                analysis = f"本次推进 {dist_km}km，配速达 {pace_str}，平均心率 {avg_hr}bpm 触达乳酸门槛区。乳酸清除速率与摄氧效率兼备，有效推高乳酸门槛巡航速度。"
                advice = f"高强度课完成质量极高！接下来 48 小时应以低心率慢跑排酸为主，避免连续大负荷。{age_advice}"
            else:
                workout_type = "稳态专项有氧进阶 (Aerobic Endurance Progression)"
                analysis = f"完成 {dist_km}km 专项课，配速 {pace_str}，心率负荷处于稳态吸收区间（TRIMP: {trimp}）。心率漂移可控，肌肉收缩力与步频节奏协调。"
                advice = f"训练节奏保持得非常好，建议课后做好腘绳肌与小腿放松。{age_advice}"
        elif dist_km >= 6:
            if avg_hr and avg_hr < recovery_ceiling:
                workout_type = "低心率排酸主动恢复 (Active Recovery Run)"
                analysis = f"轻松完成 {dist_km}km，平均心率 {avg_hr}bpm (低于恢复阈值 {int(recovery_ceiling)}bpm)。有效促进下肢微循环，加速代谢废物清除，无额外中枢神经疲劳负担。"
                advice = "极佳的恢复跑执行力！身体已充分就绪，下一堂主课可按计划冲击目标配速。"
            else:
                workout_type = "日常基础有氧构建 (General Aerobic Foundation)"
                analysis = f"跑程 {dist_km}km，配速 {pace_str}，平均心率 {avg_hr or '—'}bpm。步态节奏平稳，有效维持有氧基础与下肢肌腱刚性。"
                advice = f"课表执行到位，明天可根据体感自由选择休整或轻度慢跑。{age_advice}"
        else:
            workout_type = "短程激活与速度感知 (Short Activation Run)"
            analysis = f"短程奔跑 {dist_km}km，步频顺畅，适合赛前神经激活或大强度课后的排酸调整。"
            advice = f"适度热身与拉伸，保持良好身体机能。{age_advice}"

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
                SELECT id, activity_id, user_id, author_name, author_avatar, content, created_at 
                FROM activity_comments 
                WHERE activity_id = ? 
                ORDER BY created_at ASC
            """, (activity_id,))
            comments = [dict(r) for r in cursor.fetchall()]

            return {
                "likes_count": likes_count,
                "has_liked": has_liked,
                "comments": comments
            }

    @staticmethod
    def get_club_recent_activities(club_id: str, current_uid: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        members = LocalStore.get_club_members(club_id)
        uids = [m["user_id"] for m in members]
        if not uids:
            return []

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            placeholders = ["?"] * len(uids)
            query = f"""
                SELECT a.*, p.display_name, p.avatar_url 
                FROM activities a
                JOIN profiles p ON a.user_id = p.id
                WHERE a.user_id IN ({','.join(placeholders)})
                ORDER BY a.start_time DESC
                LIMIT ?
            """
            cursor.execute(query, uids + [limit])
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

        return enriched

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
            return res

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
            return res

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

