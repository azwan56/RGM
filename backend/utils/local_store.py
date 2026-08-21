import sqlite3
import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta

logger = logging.getLogger("local_store")

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "rgm.db")

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
                period_type TEXT DEFAULT 'monthly',
                monthly_targets TEXT,
                FOREIGN KEY(user_id) REFERENCES profiles(id)
            )
        """)

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
        conn.commit()

init_db()

class LocalStore:
    @staticmethod
    def get_profile(uid: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profiles WHERE id = ?", (uid,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["garmin_connected"] = bool(d.get("garmin_connected"))
                return d
            return None

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
            row_data = []
            for col in cols:
                val = act.get(col)
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                row_data.append(val)
            placeholders = ["?"] * len(cols)
            cursor.execute(f"INSERT OR REPLACE INTO activities ({', '.join(cols)}) VALUES ({', '.join(placeholders)})", row_data)
            conn.commit()

    @staticmethod
    def get_recent_activities(uid: str, limit: int = 15) -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM activities WHERE user_id = ? ORDER BY start_time DESC LIMIT ?", (uid, limit))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_month_distance_meters(uid: str, month_start: str) -> float:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(distance_meters) FROM activities WHERE user_id = ? AND start_time >= ?", (uid, month_start))
            res = cursor.fetchone()
            return float(res[0]) if res and res[0] is not None else 0.0

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
                SELECT SUM(distance_meters), COUNT(id), AVG(average_speed_mps) 
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
            for m in range(1, 13):
                m_start = f"{year:04d}-{m:02d}-01"
                next_y = year if m < 12 else year + 1
                next_m = m + 1 if m < 12 else 1
                m_end = f"{next_y:04d}-{next_m:02d}-01"
                cursor.execute("SELECT SUM(distance_meters) FROM activities WHERE user_id = ? AND start_time >= ? AND start_time < ?", (uid, m_start, m_end))
                m_res = cursor.fetchone()
                m_dist = float(m_res[0]) if m_res and m_res[0] is not None else 0.0
                m_km = round(m_dist / 1000.0, 1)
                if m_km > best_month_km:
                    best_month_km = m_km
                    best_month_name = f"{m}月"

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
                }
            }

    @staticmethod
    def upsert_daily_health(uid: str, metrics: Dict[str, Any]):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            date_str = metrics.get("date") or datetime.utcnow().strftime("%Y-%m-%d")
            entry_id = f"{uid}_{date_str}"
            cursor.execute("""
                INSERT OR REPLACE INTO daily_health 
                (id, user_id, date, resting_heart_rate, vo2_max, sleep_duration_seconds, sleep_duration_hours, sleep_score, body_battery_max, body_battery_min, hrv_status, hrv_weekly_avg, hrv_last_night_avg)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            cursor.execute("SELECT * FROM daily_health WHERE user_id = ? ORDER BY date DESC LIMIT 1", (uid,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {
                "resting_heart_rate": 56,
                "sleep_duration_hours": 8.5,
                "sleep_score": 69,
                "body_battery_max": 54,
                "hrv_status": "UNBALANCED",
                "hrv_last_night_avg": 29.0,
                "hrv_weekly_avg": 32.0,
                "date": date.today().isoformat()
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
            existing_map = {r["date"]: dict(r) for r in rows}

            trend = []
            import math
            for i in range(29, -1, -1):
                d = today - timedelta(days=i)
                d_str = d.isoformat()
                short_d = d.strftime("%m-%d")
                
                if d_str in existing_map:
                    item = existing_map[d_str]
                    rhr = item.get("resting_heart_rate") or (54 + int(math.sin(i)*4))
                    hrv = item.get("hrv_last_night_avg") or item.get("hrv_weekly_avg") or (32 + int(math.cos(i)*8))
                    bb = item.get("body_battery_max") or (65 + int(math.sin(i*0.8)*18))
                    sleep_score = item.get("sleep_score") or (75 + int(math.cos(i*0.5)*15))
                else:
                    rhr = 53 + int(abs(math.sin(i * 0.7)) * 6)
                    hrv = 30 + int(math.cos(i * 0.9) * 10)
                    bb = 60 + int(math.sin(i * 0.6) * 22)
                    sleep_score = 72 + int(math.cos(i * 0.5) * 16)

                trend.append({
                    "date": d_str,
                    "date_label": short_d,
                    "resting_heart_rate": int(rhr),
                    "hrv": max(15, int(hrv)),
                    "body_battery": max(20, min(100, int(bb))),
                    "sleep_score": max(40, min(100, int(sleep_score)))
                })
            return trend

    @staticmethod
    def get_goal(uid: str) -> Dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM goals WHERE user_id = ?", (uid,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                if d.get("monthly_targets"):
                    try:
                        d["monthly_targets"] = json.loads(d["monthly_targets"])
                    except Exception:
                        d["monthly_targets"] = [200.0] * 12
                return d
            return {
                "target_distance": 200.0,
                "period_type": "monthly",
                "monthly_targets": [200.0] * 12
            }

    @staticmethod
    def upsert_goal(uid: str, data: Dict[str, Any]):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            targets_json = json.dumps(data.get("monthly_targets") or [200.0] * 12)
            cursor.execute("""
                INSERT OR REPLACE INTO goals (user_id, target_distance, period_type, monthly_targets)
                VALUES (?, ?, ?, ?)
            """, (
                uid,
                float(data.get("target_distance") or 200.0),
                data.get("period_type", "monthly"),
                targets_json
            ))
            conn.commit()

    @staticmethod
    def get_race_plans(uid: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM race_plans WHERE user_id = ? ORDER BY race_date ASC", (uid,))
            rows = cursor.fetchall()
            plans = []
            today = date.today()
            for r in rows:
                p = dict(r)
                if p.get("race_date"):
                    try:
                        r_date = datetime.strptime(p["race_date"][:10], "%Y-%m-%d").date()
                        days_left = (r_date - today).days
                        p["days_left"] = max(0, days_left)
                    except Exception:
                        p["days_left"] = 0
                plans.append(p)
            
            if not plans:
                default_races = [
                    {
                        "id": "race_2",
                        "user_id": uid,
                        "name": "武功山",
                        "race_type": "越野跑 50K",
                        "race_date": "2026-09-12",
                        "target_time": "8:00:00",
                        "days_left": (date(2026, 9, 12) - today).days
                    },
                    {
                        "id": "race_1",
                        "user_id": uid,
                        "name": "Chiang Dao 160",
                        "race_type": "越野跑 100英里",
                        "race_date": "2026-12-04",
                        "target_time": "40:00:00",
                        "days_left": (date(2026, 12, 4) - today).days
                    }
                ]
                return default_races
            return plans

    @staticmethod
    def upsert_race_plan(uid: str, plan_data: Dict[str, Any]):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            plan_id = plan_data.get("id") or f"race_{int(datetime.utcnow().timestamp()*1000)}"
            cursor.execute("""
                INSERT OR REPLACE INTO race_plans (id, user_id, name, race_type, race_date, target_time, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_id,
                uid,
                plan_data.get("name") or "未命名赛事",
                plan_data.get("race_type") or "全马",
                plan_data.get("race_date") or date.today().isoformat(),
                plan_data.get("target_time") or "3:30:00",
                datetime.utcnow().isoformat() + "Z"
            ))
            conn.commit()
            return plan_id

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
