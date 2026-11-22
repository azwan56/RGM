#!/usr/bin/env python3
"""
restore_coros_users.py
Parameter-driven maintenance utility to restore COROS runner profiles, memberships,
and activities from an external untracked JSON manifest (never store real PII in git).

Usage:
    python3 scripts/restore_coros_users.py --input-json /secure/coros_users.json [--db-path backend/data/rgm.db]
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

from utils.coros_adapter import CorosAdapter
from utils.encryption import encrypt_pii, encrypt_string
from utils.local_store import DB_PATH, db_connect
from utils.running_metrics import calculate_trimp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("restore_coros_users")


def restore_users(users: list, target_db: str = DB_PATH):
    if not users:
        logger.warning("No users provided in input JSON; nothing to restore.")
        return
    logger.info(f"Restoring {len(users)} COROS users into database: {target_db}")
    now_iso = datetime.utcnow().isoformat() + "Z"

    with db_connect(target_db) as conn:
        c = conn.cursor()

        for u in users:
            uid = u["id"]
            logger.info(f"Processing user: {uid}...")

            enc_rname = encrypt_pii(u.get("real_name"))
            enc_phone = encrypt_pii(u.get("phone")) if u.get("phone") else None
            enc_dob = encrypt_pii(u.get("date_of_birth")) if u.get("date_of_birth") else None
            enc_pwd = encrypt_string("coros_cached")

            c.execute("SELECT id FROM profiles WHERE id = ?", (uid,))
            exists = c.fetchone()
            if not exists:
                c.execute(
                    """
                    INSERT INTO profiles (
                        id, display_name, real_name, wechat_openid, email, phone,
                        coros_connected, coros_account, coros_encrypted_password, coros_domain,
                        avatar_url, gender, date_of_birth, height_cm, weight_kg, vo2max,
                        max_heart_rate, resting_heart_rate, class_name, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uid,
                        u["display_name"],
                        enc_rname,
                        u.get("wechat_openid"),
                        u.get("email"),
                        enc_phone,
                        1,
                        u["coros_account"],
                        enc_pwd,
                        u.get("coros_domain") or "teamcnapi.coros.com",
                        u.get("avatar_url") or "",
                        u.get("gender") or "male",
                        enc_dob,
                        u.get("height_cm"),
                        u.get("weight_kg"),
                        u.get("vo2max"),
                        u.get("max_heart_rate") or 190,
                        u.get("resting_heart_rate") or 56,
                        u.get("class_name") or "",
                        now_iso,
                    ),
                )
            else:
                c.execute(
                    """
                    UPDATE profiles SET
                        display_name = ?, real_name = ?, wechat_openid = COALESCE(?, wechat_openid),
                        email = COALESCE(?, email), phone = COALESCE(?, phone),
                        coros_connected = 1, coros_account = ?, coros_encrypted_password = ?,
                        coros_domain = ?, avatar_url = COALESCE(?, avatar_url),
                        gender = COALESCE(?, gender), date_of_birth = COALESCE(?, date_of_birth),
                        height_cm = COALESCE(?, height_cm), weight_kg = COALESCE(?, weight_kg),
                        vo2max = COALESCE(?, vo2max), max_heart_rate = COALESCE(?, max_heart_rate),
                        resting_heart_rate = COALESCE(?, resting_heart_rate), class_name = COALESCE(?, class_name)
                    WHERE id = ?
                    """,
                    (
                        u["display_name"],
                        enc_rname,
                        u.get("wechat_openid"),
                        u.get("email"),
                        enc_phone,
                        u["coros_account"],
                        enc_pwd,
                        u.get("coros_domain") or "teamcnapi.coros.com",
                        u.get("avatar_url"),
                        u.get("gender"),
                        enc_dob,
                        u.get("height_cm"),
                        u.get("weight_kg"),
                        u.get("vo2max"),
                        u.get("max_heart_rate"),
                        u.get("resting_heart_rate"),
                        u.get("class_name"),
                        uid,
                    ),
                )

            c.execute("SELECT user_id FROM goals WHERE user_id = ?", (uid,))
            if not c.fetchone():
                m_targets = [float(u.get("target_distance") or 200.0)] * 12
                c.execute(
                    """
                    INSERT INTO goals (user_id, target_distance, weekly_target, period_type, monthly_targets)
                    VALUES (?, ?, ?, 'monthly', ?)
                    """,
                    (uid, float(u.get("target_distance") or 200.0), float(u.get("weekly_target") or 50.0), json.dumps(m_targets)),
                )

            for club_id in u.get("club_ids", []):
                c.execute(
                    """
                    INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                    VALUES (?, ?, ?, 'member', 'active', ?, 1)
                    """,
                    (f"{club_id}_{uid}", club_id, uid, now_iso),
                )

            for org_id in u.get("org_ids", []):
                c.execute("SELECT id FROM organization_members WHERE org_id = ? AND user_id = ?", (org_id, uid))
                if not c.fetchone():
                    c.execute(
                        """
                        INSERT INTO organization_members (
                            id, org_id, user_id, real_name, gender, date_of_birth, class_name, phone, role, status, joined_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'member', 'temporary', ?)
                        """,
                        (
                            f"{org_id}_{uid}",
                            org_id,
                            uid,
                            enc_rname or "",
                            u.get("gender") or "male",
                            enc_dob or "",
                            u.get("class_name") or "",
                            enc_phone or "",
                            now_iso,
                        ),
                    )
        conn.commit()

    for u in users:
        uid = u["id"]
        account = u["coros_account"]
        domain = u.get("coros_domain") or "teamcnapi.coros.com"
        rest_hr = int(u.get("resting_heart_rate") or 56)
        max_hr = int(u.get("max_heart_rate") or 190)
        gender = u.get("gender") or "male"

        try:
            adapter = CorosAdapter(account=account, password="", domain=domain)
            if not adapter.login():
                logger.warning(f"Could not login to COROS for user {uid}")
                continue

            acts = adapter.fetch_activities_by_date(start_date=u.get("start_date") or f"{datetime.utcnow().year}-01-01")
            if not acts:
                acts = adapter.fetch_recent_activities(limit=100)

            with db_connect(target_db) as conn:
                c = conn.cursor()
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
                            act_id,
                            uid,
                            act.get("name"),
                            act.get("sport_type") or "running",
                            act.get("start_time"),
                            act.get("distance_meters"),
                            act.get("moving_time_seconds"),
                            act.get("elapsed_time_seconds"),
                            act.get("elevation_gain_meters") or 0.0,
                            act.get("average_heartrate"),
                            act.get("max_heartrate"),
                            act.get("average_cadence"),
                            act.get("avg_pace_str"),
                            act.get("calories"),
                            act.get("aerobic_training_effect"),
                            act.get("anaerobic_training_effect"),
                            trimp_val,
                            act.get("map_image_url"),
                        ),
                    )
                conn.commit()
        except Exception as e:
            logger.error(f"Error syncing activities for {uid}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restore COROS users from an external JSON file")
    parser.add_argument("--input-json", required=True, help="Path to JSON array of user records")
    parser.add_argument("--db-path", default=DB_PATH, help="Target SQLite DB path")
    args = parser.parse_args()
    with open(args.input_json, "r", encoding="utf-8") as f:
        user_list = json.load(f)
    restore_users(user_list, args.db_path)
