#!/usr/bin/env python3
"""
restore_coros_users.py
Restores Coros runners:
- 高九凯 (u_wx_26a168a65f, 245280294@qq.com)
- 王鹏飞 (u_wx_82320f8a14, 18912367150)
- LM (u_wx_d595452dbe, 13910958525)

Restores their profiles, biometrics, goals, memberships in '复旦戈闵文跑团',
'RGM先锋跑团', and '复旦戈' (org_fudan_gobi), and syncs all their Coros activities
since 2026-01-01.
"""

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime

# Setup path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "backend"))

from utils.local_store import LocalStore, DB_PATH
from utils.coros_adapter import CorosAdapter
from utils.running_metrics import calculate_trimp
from utils.encryption import encrypt_pii, encrypt_string

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("restore_coros_users")

COROS_USERS = [
    {
        "id": "u_wx_26a168a65f",
        "display_name": "高九凯",
        "real_name": "高九凯",
        "wechat_openid": "wx_74f49014ae1a0bd87432",
        "email": "245280294@qq.com",
        "coros_account": "245280294@qq.com",
        "coros_domain": "teamcnapi.coros.com",
        "coros_connected": 1,
        "avatar_url": "https://oss.coros.com/avatar/202505/17467646677POGXIOXGJVDW1AF64DW",
        "gender": "male",
        "date_of_birth": "1990-06-22",
        "height_cm": 168.0,
        "weight_kg": 60.0,
        "vo2max": 62.0,
        "max_heart_rate": 187,
        "resting_heart_rate": 46,
        "class_name": "复旦戈友",
        "target_distance": 200.0,
        "weekly_target": 50.0
    },
    {
        "id": "u_wx_82320f8a14",
        "display_name": "Tony 王鹏飞",
        "real_name": "王鹏飞",
        "wechat_openid": "ogDgjxjSeC5Zo2e7IGfXYKKDgeHU",
        "phone": "18912367150",
        "email": None,
        "coros_account": "18912367150",
        "coros_domain": "teamcnapi.coros.com",
        "coros_connected": 1,
        "avatar_url": "https://oss.coros.com/avatar/202109/1632698666LN0JFXEDZNG839AURLTQ",
        "gender": "male",
        "date_of_birth": "1988-12-10",
        "height_cm": 172.0,
        "weight_kg": 60.0,
        "vo2max": 65.0,
        "max_heart_rate": 187,
        "resting_heart_rate": 50,
        "class_name": "复旦戈友",
        "target_distance": 200.0,
        "weekly_target": 50.0
    },
    {
        "id": "u_wx_d595452dbe",
        "display_name": "LM",
        "real_name": "LM",
        "wechat_openid": "ogDgjxkWMSmSRz82fjz7U1WEh3OQ",
        "phone": "13910958525",
        "email": None,
        "coros_account": "13910958525",
        "coros_domain": "teamcnapi.coros.com",
        "coros_connected": 1,
        "avatar_url": "https://oss.coros.com/avatar/202601/1767616466VM3SJDBGEY53MUD86WHN",
        "gender": "female",
        "date_of_birth": "1982-01-17",
        "height_cm": 162.0,
        "weight_kg": 52.0,
        "vo2max": 44.0,
        "max_heart_rate": 182,
        "resting_heart_rate": 49,
        "class_name": "复旦戈友",
        "target_distance": 150.0,
        "weekly_target": 35.0
    }
]


def restore_users(target_db: str = DB_PATH):
    logger.info(f"Restoring Coros users into database: {target_db}")
    conn = sqlite3.connect(target_db)
    now_iso = datetime.utcnow().isoformat() + "Z"

    with conn:
        c = conn.cursor()

        for u in COROS_USERS:
            uid = u["id"]
            logger.info(f"Processing user: {u['display_name']} ({uid})...")

            # 1. Upsert Profile
            enc_rname = encrypt_pii(u.get("real_name"))
            enc_phone = encrypt_pii(u.get("phone")) if u.get("phone") else None
            enc_pwd = encrypt_string("coros_cached")

            # Check if profile exists
            c.execute("SELECT id FROM profiles WHERE id = ?", (uid,))
            exists = c.fetchone()
            if not exists:
                c.execute("""
                    INSERT INTO profiles (
                        id, display_name, real_name, wechat_openid, email, phone,
                        coros_connected, coros_account, coros_encrypted_password, coros_domain,
                        avatar_url, gender, date_of_birth, height_cm, weight_kg, vo2max,
                        max_heart_rate, resting_heart_rate, class_name, created_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?
                    )
                """, (
                    uid, u["display_name"], enc_rname, u["wechat_openid"], u.get("email"), enc_phone,
                    1, u["coros_account"], enc_pwd, u["coros_domain"],
                    u["avatar_url"], u["gender"], u["date_of_birth"], u["height_cm"], u["weight_kg"], u["vo2max"],
                    u["max_heart_rate"], u["resting_heart_rate"], u["class_name"], now_iso
                ))
            else:
                c.execute("""
                    UPDATE profiles SET
                        display_name = ?, real_name = ?, wechat_openid = ?, email = COALESCE(?, email),
                        phone = COALESCE(?, phone), coros_connected = 1, coros_account = ?,
                        coros_encrypted_password = ?, coros_domain = ?, avatar_url = ?,
                        gender = ?, date_of_birth = ?, height_cm = ?, weight_kg = ?,
                        vo2max = ?, max_heart_rate = ?, resting_heart_rate = ?, class_name = ?
                    WHERE id = ?
                """, (
                    u["display_name"], enc_rname, u["wechat_openid"], u.get("email"),
                    enc_phone, u["coros_account"], enc_pwd, u["coros_domain"], u["avatar_url"],
                    u["gender"], u["date_of_birth"], u["height_cm"], u["weight_kg"],
                    u["vo2max"], u["max_heart_rate"], u["resting_heart_rate"], u["class_name"],
                    uid
                ))

            # 2. Setup Goals
            c.execute("SELECT user_id FROM goals WHERE user_id = ?", (uid,))
            if not c.fetchone():
                m_targets = [u["target_distance"]] * 12
                c.execute("""
                    INSERT INTO goals (user_id, target_distance, weekly_target, period_type, monthly_targets)
                    VALUES (?, ?, ?, 'monthly', ?)
                """, (uid, u["target_distance"], u["weekly_target"], json.dumps(m_targets)))

            # 3. Add to 'club_fudan_gobi_main' (复旦戈闵文跑团)
            c.execute("""
                INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                VALUES (?, 'club_fudan_gobi_main', ?, 'member', 'active', ?, 1)
            """, (f"club_fudan_gobi_main_{uid}", uid, now_iso))

            # 4. Add to 'club_rgm_flagship' (RGM先锋跑团)
            c.execute("""
                INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                VALUES (?, 'club_rgm_flagship', ?, 'member', 'active', ?, 1)
            """, (f"club_rgm_flagship_{uid}", uid, now_iso))

            # 5. Add to 'org_fudan_gobi' (复旦戈)
            c.execute("SELECT id FROM organization_members WHERE org_id = 'org_fudan_gobi' AND user_id = ?", (uid,))
            if not c.fetchone():
                c.execute("""
                    INSERT INTO organization_members (
                        id, org_id, user_id, real_name, gender, date_of_birth, class_name, phone, role, status, joined_at, confirmed_at, confirmed_by
                    ) VALUES (
                        ?, 'org_fudan_gobi', ?, ?, ?, ?, ?, ?, 'member', 'confirmed', ?, ?, 'u_df65d9a588c9'
                    )
                """, (
                    f"org_fudan_gobi_{uid}", uid, u["real_name"], u["gender"], u["date_of_birth"],
                    u["class_name"], u.get("phone") or "", now_iso, now_iso
                ))

            # 6. If Gao Jiukai, restore his Shanghai Marathon training plan if missing
            if uid == "u_wx_26a168a65f":
                c.execute("SELECT id FROM training_plans WHERE id = 'plan_1788877384684'")
                if not c.fetchone():
                    c.execute("""
                        INSERT INTO training_plans (
                            id, user_id, club_id, title, goal_type, target_race_name, target_date,
                            start_date, end_date, weeks_count, status, creator_id, created_at, updated_at
                        ) VALUES (
                            'plan_1788877384684', 'u_wx_26a168a65f', 'club_fudan_gobi_main',
                            '高九凯 · 上海马拉松 8周科学训练计划', 'target_race', '上海马拉松',
                            '2026-11-29', '2026-09-07', '2026-11-01', 8, 'active', 'u_df65d9a588c9', ?, ?
                        )
                    """, (now_iso, now_iso))
                    logger.info("Restored training plan for 高九凯.")

    logger.info("Users, profiles, goals, and memberships successfully restored.")

    # 7. Sync Activities from Coros
    logger.info("Fetching and syncing activities from Coros...")
    for u in COROS_USERS:
        uid = u["id"]
        account = u["coros_account"]
        domain = u["coros_domain"]
        rest_hr = u["resting_heart_rate"]
        max_hr = u["max_heart_rate"]
        gender = u["gender"]

        try:
            adapter = CorosAdapter(account=account, password="", domain=domain)
            if not adapter.login():
                logger.warning(f"Could not login to COROS for {account}")
                continue

            logger.info(f"Fetching activities for {u['display_name']} ({account})...")
            acts = adapter.fetch_activities_by_date(start_date="2026-01-01")
            if not acts:
                acts = adapter.fetch_recent_activities(limit=100)
            logger.info(f"Retrieved {len(acts)} activities for {u['display_name']}.")

            with conn:
                c = conn.cursor()
                synced_count = 0
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
                    synced_count += 1
                logger.info(f"Saved {synced_count} activities for {u['display_name']}.")

        except Exception as e:
            logger.error(f"Error syncing activities for {u['display_name']}: {e}")

    # Summary
    with conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM profiles")
        total_p = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM activities")
        total_a = c.fetchone()[0]
        logger.info(f"Restoration complete! Total profiles: {total_p}, Total activities: {total_a}")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    restore_users(db)
