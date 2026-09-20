#!/usr/bin/env python3
"""
restore_sun_jin.py
Restores Jin SUN (user_id: 'SUN JIN', garmin: '514816123@qq.com')
- Connects Garmin using cached token
- Updates biometrics & profile
- Sets up monthly running goal
- Syncs all 2026 activities into 'activities' table with TRIMP
- Confirms memberships in clubs and org_fudan_gobi
"""

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "backend"))

from utils.local_store import LocalStore, DB_PATH
from utils.garmin_adapter import GarminAdapter
from utils.running_metrics import calculate_trimp
from utils.encryption import encrypt_pii, encrypt_string

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("restore_sun_jin")


def restore_sun_jin(target_db: str = DB_PATH):
    logger.info(f"Restoring Sun Jin into database: {target_db}")
    conn = sqlite3.connect(target_db)
    now_iso = datetime.utcnow().isoformat() + "Z"
    uid = "SUN JIN"
    garmin_email = "514816123@qq.com"
    garmin_domain = "garmin.com"

    # 1. Login with GarminAdapter
    adapter = GarminAdapter(email=garmin_email, password="", domain=garmin_domain)
    if not adapter.login():
        logger.error(f"Failed to login to Garmin for {garmin_email}")
        return

    # 2. Fetch Profile Info
    g_info = adapter.fetch_user_profile_info()
    logger.info(f"Fetched Garmin profile: {g_info}")

    enc_rname = encrypt_pii("孙进")
    enc_pwd = encrypt_string("garmin_cached")
    avatar = g_info.get("avatar_url") or "https://s3.amazonaws.com/garmin-connect-prod/profile_images/9f539f50-8d6e-42da-a247-fd9786d10ff5-105024472.png"
    dob = g_info.get("date_of_birth") or "1971-03-27"
    height = g_info.get("height_cm") or 181.0
    weight = g_info.get("weight_kg") or 83.0
    vo2max = g_info.get("vo2max") or 46.0

    with conn:
        c = conn.cursor()
        # Upsert profile
        c.execute("SELECT id FROM profiles WHERE id = ?", (uid,))
        if not c.fetchone():
            c.execute("""
                INSERT INTO profiles (
                    id, display_name, real_name, email,
                    garmin_connected, garmin_email, garmin_domain, garmin_encrypted_password,
                    avatar_url, gender, date_of_birth, height_cm, weight_kg, vo2max,
                    class_name, created_at, garmin_last_sync_at
                ) VALUES (
                    ?, 'Jin SUN', ?, ?,
                    1, ?, ?, ?,
                    ?, 'male', ?, ?, ?, ?,
                    '复旦戈友', ?, ?
                )
            """, (uid, enc_rname, garmin_email, garmin_email, garmin_domain, enc_pwd, avatar, dob, height, weight, vo2max, now_iso, now_iso))
        else:
            c.execute("""
                UPDATE profiles SET
                    display_name = 'Jin SUN', real_name = ?, email = COALESCE(email, ?),
                    garmin_connected = 1, garmin_email = ?, garmin_domain = ?,
                    garmin_encrypted_password = ?, avatar_url = ?, gender = 'male',
                    date_of_birth = ?, height_cm = ?, weight_kg = ?, vo2max = ?,
                    class_name = '复旦戈友', garmin_last_sync_at = ?
                WHERE id = ?
            """, (enc_rname, garmin_email, garmin_email, garmin_domain, enc_pwd, avatar, dob, height, weight, vo2max, now_iso, uid))

        # Setup Goals
        c.execute("SELECT user_id FROM goals WHERE user_id = ?", (uid,))
        m_targets = [200.0] * 12
        if not c.fetchone():
            c.execute("""
                INSERT INTO goals (user_id, target_distance, weekly_target, period_type, monthly_targets)
                VALUES (?, 200.0, 50.0, 'monthly', ?)
            """, (uid, json.dumps(m_targets)))
        else:
            c.execute("""
                UPDATE goals SET target_distance = 200.0, weekly_target = 50.0, monthly_targets = ?
                WHERE user_id = ?
            """, (json.dumps(m_targets), uid))

        # Ensure Club Memberships
        c.execute("""
            INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
            VALUES (?, 'club_fudan_gobi_main', ?, 'member', 'active', ?, 1)
        """, (f"club_fudan_gobi_main_{uid}", uid, now_iso))

        c.execute("""
            INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
            VALUES (?, 'club_rgm_flagship', ?, 'member', 'active', ?, 1)
        """, (f"club_rgm_flagship_{uid}", uid, now_iso))

        # Ensure Org Membership
        c.execute("SELECT id FROM organization_members WHERE org_id = 'org_fudan_gobi' AND user_id = ?", (uid,))
        if not c.fetchone():
            c.execute("""
                INSERT INTO organization_members (
                    id, org_id, user_id, real_name, gender, date_of_birth, class_name, phone, role, status, joined_at, confirmed_at, confirmed_by
                ) VALUES (
                    ?, 'org_fudan_gobi', ?, '孙进', 'male', ?, '复旦戈友', '', 'member', 'confirmed', ?, ?, 'u_df65d9a588c9'
                )
            """, (f"org_fudan_gobi_{uid}", uid, dob, now_iso, now_iso))
        else:
            c.execute("""
                UPDATE organization_members SET
                    real_name = '孙进', gender = 'male', date_of_birth = ?, class_name = '复旦戈友', status = 'confirmed'
                WHERE org_id = 'org_fudan_gobi' AND user_id = ?
            """, (dob, uid))

    # 3. Fetch all 2026 activities from Garmin
    logger.info("Fetching all 2026 activities from Garmin Connect...")
    acts = adapter.fetch_activities_by_date(start_date="2026-01-01")
    if not acts:
        acts = adapter.fetch_recent_activities(limit=100)
    logger.info(f"Retrieved {len(acts)} activities for Sun Jin.")

    rest_hr = 55
    max_hr = 185
    gender = "male"

    with conn:
        c = conn.cursor()
        saved = 0
        for act in acts:
            act_id = act.get("id")
            if not act_id:
                continue
            moving_mins = (act.get("moving_time_seconds") or 0) / 60.0
            avg_hr = act.get("average_heartrate")
            if avg_hr and avg_hr > rest_hr:
                trimp_val = calculate_trimp(moving_mins, avg_hr, rest_hr, max_hr, gender)
            else:
                trimp_val = round(moving_mins * 0.8, 1)

            c.execute("""
                INSERT OR REPLACE INTO activities (
                    id, user_id, name, sport_type, start_time, distance_meters,
                    moving_time_seconds, elapsed_time_seconds, elevation_gain_meters,
                    average_heartrate, max_heartrate, average_cadence, avg_pace_str,
                    calories, aerobic_training_effect, anaerobic_training_effect,
                    trimp, map_image_url
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?
                )
            """, (
                act_id, uid, act.get("name"), act.get("sport_type") or "running",
                act.get("start_time"), act.get("distance_meters"),
                act.get("moving_time_seconds"), act.get("elapsed_time_seconds"),
                act.get("elevation_gain_meters") or 0.0,
                act.get("average_heartrate"), act.get("max_heartrate"),
                act.get("average_cadence"), act.get("avg_pace_str"),
                act.get("calories"), act.get("aerobic_training_effect"),
                act.get("anaerobic_training_effect"),
                trimp_val, act.get("map_image_url")
            ))
            saved += 1

    logger.info(f"Successfully saved {saved} activities for Sun Jin into {target_db}.")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    restore_sun_jin(db)
