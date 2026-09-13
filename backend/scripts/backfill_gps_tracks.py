"""
Script to backfill GPS polyline tracks and elevation profiles for historical activities.
Focuses on Garmin runs (e.g. Wugong Mountain 59km, recent training runs).
"""

import sys
import os
import json
import logging
import sqlite3

# Adjust pythonpath so backend modules can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.local_store import LocalStore, DB_PATH
from utils.encryption import decrypt_string
from utils.garmin_adapter import GarminAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill_gps")

def backfill_garmin_gps_tracks(limit: int = 20):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Find all garmin activities that do not yet have gps_track_data
        c.execute("""
            SELECT id, user_id, name, sport_type, start_time, distance_meters, elevation_gain_meters
            FROM activities
            WHERE id LIKE 'garmin_%' AND (gps_track_data IS NULL OR gps_track_data = '')
            ORDER BY start_time DESC
            LIMIT ?
        """, (limit,))
        activities = [dict(r) for r in c.fetchall()]

    if not activities:
        logger.info("No Garmin activities found needing GPS backfill.")
        return

    logger.info(f"Found {len(activities)} Garmin activities to inspect for GPS track backfill.")

    # Group activities by user
    user_acts = {}
    for act in activities:
        uid = act.get("user_id")
        if uid:
            user_acts.setdefault(uid, []).append(act)

    for uid, acts in user_acts.items():
        profile = LocalStore.get_profile(uid)
        if not profile or not profile.get("garmin_connected") or not profile.get("garmin_encrypted_password"):
            logger.warning(f"User {uid} does not have active Garmin credentials, skipping {len(acts)} acts.")
            continue

        try:
            pwd = decrypt_string(profile["garmin_encrypted_password"])
            domain = profile.get("garmin_domain") or "garmin.cn"
            adapter = GarminAdapter(profile["garmin_email"], pwd, domain=domain)
            if not adapter.login():
                logger.error(f"Failed to log in to Garmin for user {uid}")
                continue

            for act in acts:
                act_id = act["id"]
                logger.info(f"--> Fetching GPS track for {act_id} ({act.get('name')}, {act.get('distance_meters', 0)/1000:.1f}km)...")
                track_data = adapter.fetch_activity_gps_track(act_id)
                if track_data and track_data.get("points"):
                    track_json = json.dumps(track_data, ensure_ascii=False)
                    with sqlite3.connect(DB_PATH) as conn:
                        conn.cursor().execute(
                            "UPDATE activities SET gps_track_data = ? WHERE id = ?",
                            (track_json, act_id)
                        )
                        conn.commit()
                    logger.info(f"✓ Saved {len(track_data['points'])} GPS points, {len(track_data.get('elevation_profile', []))} elevation points for {act_id}")
                else:
                    logger.info(f"- No GPS polyline available for {act_id} (may be indoor/manual)")

        except Exception as e:
            logger.error(f"Error processing activities for user {uid}: {e}", exc_info=True)


def backfill_coros_map_images():
    """
    Backfills map_image_url for all historical COROS activities from COROS cloud API.
    """
    import requests
    from utils.coros_adapter import CorosAdapter

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT DISTINCT user_id 
            FROM activities 
            WHERE id LIKE 'coros_%' AND (map_image_url IS NULL OR map_image_url = '')
        """)
        uids = [r[0] for r in c.fetchall()]

    if not uids:
        logger.info("No COROS activities needing map image backfill.")
        return

    logger.info(f"Found {len(uids)} COROS user(s) needing map image backfill.")

    for uid in uids:
        profile = LocalStore.get_profile(uid)
        if not profile or not profile.get("coros_connected") or not profile.get("coros_encrypted_password"):
            continue

        try:
            pwd = decrypt_string(profile["coros_encrypted_password"])
            domain = profile.get("coros_domain") or "teamcnapi.coros.com"
            adapter = CorosAdapter(profile["coros_account"], pwd, domain=domain)
            if not adapter.login():
                logger.error(f"Failed to log in to COROS for user {uid}")
                continue

            url = f"{adapter.base_url}/activity/query"
            page_number = 1
            total_updated = 0

            while True:
                url = f"{adapter.base_url}/activity/query?modeList=100,101,102,103&pageNumber={page_number}&size=100"
                resp = requests.get(url, headers=adapter._get_headers(), timeout=15)
                if resp.status_code != 200:
                    break
                data = resp.json()
                data_list = (data.get("data") or {}).get("dataList") or []
                if not data_list:
                    break


                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()
                    for item in data_list:
                        raw_id = item.get("labelId") or item.get("activityId") or item.get("hId")
                        img_url = item.get("imageUrl")
                        if raw_id and img_url:
                            act_id = f"coros_{raw_id}"
                            cursor.execute(
                                "UPDATE activities SET map_image_url = ? WHERE id = ? AND (map_image_url IS NULL OR map_image_url = '')",
                                (img_url, act_id)
                            )
                            total_updated += cursor.rowcount
                    conn.commit()

                if len(data_list) < 100:
                    break
                page_number += 1
                if page_number > 20:
                    break

            logger.info(f"✓ Successfully backfilled {total_updated} COROS map image URLs for user {uid}")
        except Exception as e:
            logger.error(f"Error backfilling COROS activities for user {uid}: {e}", exc_info=True)


if __name__ == "__main__":
    backfill_coros_map_images()
    backfill_garmin_gps_tracks(limit=50)

