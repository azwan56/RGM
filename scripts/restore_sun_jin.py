#!/usr/bin/env python3
"""
restore_sun_jin.py -> Generic Garmin Runner Restoration Utility
Restores a Garmin runner profile, memberships, and cached-token activities from CLI/JSON args
without hardcoding personal PII in source control.

Usage:
    python3 scripts/restore_sun_jin.py --input-json /secure/garmin_runner.json [--db-path backend/data/rgm.db]
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "backend"))

from utils.encryption import encrypt_pii, encrypt_string
from utils.garmin_adapter import GarminAdapter
from utils.local_store import DB_PATH, db_connect
from utils.running_metrics import calculate_trimp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("restore_garmin_runner")


def restore_garmin_runner(cfg: dict, target_db: str = DB_PATH):
    uid = cfg["uid"]
    garmin_email = cfg["garmin_email"]
    garmin_domain = cfg.get("garmin_domain") or "garmin.cn"
    display_name = cfg.get("display_name") or f"跑者_{uid[-4:]}"
    real_name = cfg.get("real_name") or ""
    gender = cfg.get("gender") or "male"
    class_name = cfg.get("class_name") or ""

    logger.info(f"Restoring Garmin runner {uid} into database: {target_db}")
    now_iso = datetime.utcnow().isoformat() + "Z"

    adapter = GarminAdapter(email=garmin_email, password="", domain=garmin_domain)
    if not adapter.login():
        logger.error(f"Failed to login to Garmin for {uid}")
        return

    g_info = adapter.fetch_user_profile_info()
    enc_rname = encrypt_pii(real_name) if real_name else ""
    enc_pwd = encrypt_string("garmin_cached")
    dob_raw = g_info.get("date_of_birth") or cfg.get("date_of_birth") or ""
    enc_dob = encrypt_pii(dob_raw) if dob_raw else ""
    avatar = g_info.get("avatar_url") or "/api/avatars/default-runner.svg"
    height = g_info.get("height_cm") or cfg.get("height_cm") or 175.0
    weight = g_info.get("weight_kg") or cfg.get("weight_kg") or 65.0
    vo2max = g_info.get("vo2max") or cfg.get("vo2max")

    with db_connect(target_db) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM profiles WHERE id = ?", (uid,))
        if not c.fetchone():
            c.execute(
                """
                INSERT INTO profiles (
                    id, display_name, real_name, email,
                    garmin_connected, garmin_email, garmin_domain, garmin_encrypted_password,
                    avatar_url, gender, date_of_birth, height_cm, weight_kg, vo2max,
                    class_name, created_at, garmin_last_sync_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uid, display_name, enc_rname, garmin_email,
                    garmin_email, garmin_domain, enc_pwd, avatar, gender,
                    enc_dob, height, weight, vo2max, class_name, now_iso, now_iso,
                ),
            )
        else:
            c.execute(
                """
                UPDATE profiles SET
                    display_name = ?, real_name = COALESCE(NULLIF(?, ''), real_name),
                    email = COALESCE(email, ?), garmin_connected = 1, garmin_email = ?,
                    garmin_domain = ?, garmin_encrypted_password = ?, avatar_url = ?,
                    gender = ?, date_of_birth = COALESCE(NULLIF(?, ''), date_of_birth),
                    height_cm = ?, weight_kg = ?, vo2max = COALESCE(?, vo2max),
                    class_name = COALESCE(NULLIF(?, ''), class_name), garmin_last_sync_at = ?
                WHERE id = ?
                """,
                (
                    display_name, enc_rname, garmin_email, garmin_email,
                    garmin_domain, enc_pwd, avatar, gender, enc_dob,
                    height, weight, vo2max, class_name, now_iso, uid,
                ),
            )

        m_targets = [float(cfg.get("target_distance") or 200.0)] * 12
        c.execute("SELECT user_id FROM goals WHERE user_id = ?", (uid,))
        if not c.fetchone():
            c.execute(
                "INSERT INTO goals (user_id, target_distance, weekly_target, period_type, monthly_targets) VALUES (?, ?, ?, 'monthly', ?)",
                (uid, m_targets[0], float(cfg.get("weekly_target") or 50.0), json.dumps(m_targets)),
            )

        for club_id in cfg.get("club_ids", []):
            c.execute(
                "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent) VALUES (?, ?, ?, 'member', 'active', ?, 1)",
                (f"{club_id}_{uid}", club_id, uid, now_iso),
            )

        for org_id in cfg.get("org_ids", []):
            c.execute("SELECT id FROM organization_members WHERE org_id = ? AND user_id = ?", (org_id, uid))
            if not c.fetchone():
                c.execute(
                    """
                    INSERT INTO organization_members (
                        id, org_id, user_id, real_name, gender, date_of_birth, class_name, phone, role, status, joined_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, '', 'member', 'temporary', ?)
                    """,
                    (f"{org_id}_{uid}", org_id, uid, enc_rname, gender, enc_dob, class_name, now_iso),
                )
        conn.commit()

    acts = adapter.fetch_activities_by_date(start_date=cfg.get("start_date") or f"{datetime.utcnow().year}-01-01")
    if not acts:
        acts = adapter.fetch_recent_activities(limit=100)

    rest_hr = int(cfg.get("resting_heart_rate") or 55)
    max_hr = int(cfg.get("max_heart_rate") or 185)
    with db_connect(target_db) as conn:
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
                trimp_val = round(moving_mins * 0.85, 1)

            c.execute(
                """
                INSERT OR REPLACE INTO activities (
                    id, user_id, name, sport_type, start_time, distance_meters,
                    moving_time_seconds, elapsed_time_seconds, elevation_gain_meters,
                    average_heartrate, max_heartrate, average_cadence, avg_pace_str,
                    calories, aerobic_training_effect, anaerobic_training_effect,
                    trimp, map_image_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    act_id, uid, act.get("name"), act.get("sport_type") or "running",
                    act.get("start_time"), act.get("distance_meters"),
                    act.get("moving_time_seconds"), act.get("elapsed_time_seconds"),
                    act.get("elevation_gain_meters") or 0.0,
                    act.get("average_heartrate"), act.get("max_heartrate"),
                    act.get("average_cadence"), act.get("avg_pace_str"),
                    act.get("calories"), act.get("aerobic_training_effect"),
                    act.get("anaerobic_training_effect"),
                    trimp_val, act.get("map_image_url"),
                ),
            )
            saved += 1
        conn.commit()
    logger.info(f"Saved {saved} activities for {uid}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restore a Garmin runner from an external JSON config")
    parser.add_argument("--input-json", required=True, help="Path to runner JSON config")
    parser.add_argument("--db-path", default=DB_PATH, help="Target SQLite DB path")
    args = parser.parse_args()
    with open(args.input_json, "r", encoding="utf-8") as f:
        cfg_data = json.load(f)
    restore_garmin_runner(cfg_data, args.db_path)
