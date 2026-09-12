#!/usr/bin/env python3
"""
Backfills elevation_gain_meters and refreshes Canova critique for activities.
"""
import os
import sys
import sqlite3
import logging

# Ensure backend path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.local_store import LocalStore, DB_PATH
from utils.garmin_adapter import GarminAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill_elevation")


def backfill_user_garmin_elevation(user_id: str):
    profile = LocalStore.get_profile(user_id)
    if not profile or not profile.get("garmin_connected"):
        logger.warning(f"User {user_id} not connected to Garmin.")
        return

    email = profile["garmin_email"]
    pwd = profile["garmin_encrypted_password"]
    domain = profile.get("garmin_domain") or "garmin.com"
    adapter = GarminAdapter(email=email, password=pwd, domain=domain)
    if not adapter.login():
        logger.error(f"Failed to login to Garmin for {email}")
        return

    # Fetch activities for the past 90 days
    logger.info(f"Fetching recent Garmin activities for {email}...")
    garmin_acts = adapter.client.get_activities(0, 100)
    logger.info(f"Retrieved {len(garmin_acts)} activities from Garmin Connect.")

    updated_count = 0
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        for g_act in garmin_acts:
            raw_id = g_act.get("activityId")
            if not raw_id:
                continue
            act_id = f"garmin_{raw_id}"
            
            elev = g_act.get("elevationGain") or g_act.get("totalElevationGain")
            if elev is None:
                continue
            elev_gain = round(float(elev), 1)

            # Check existing row
            cursor.execute("SELECT id, name, elevation_gain_meters, ai_journal, distance_meters, avg_pace_str, average_heartrate, trimp FROM activities WHERE id = ?", (act_id,))
            row = cursor.fetchone()
            if not row:
                continue

            current_elev = row["elevation_gain_meters"]
            ai_journal = row["ai_journal"] or ""

            # Needs update if elevation is missing or 0 or critique has +0m
            if current_elev is None or current_elev == 0 or "+0m" in ai_journal:
                # Update elevation
                act_dict = dict(row)
                act_dict["elevation_gain_meters"] = elev_gain
                act_dict["total_elevation_gain"] = elev_gain

                # Re-generate critique if it was mountain trail run or had +0m
                new_critique = ai_journal
                if "+0m" in ai_journal or elev_gain > 50 or "越野" in row["name"] or "山" in row["name"]:
                    new_critique = LocalStore.generate_canova_critique(act_dict, profile=profile)

                cursor.execute("""
                    UPDATE activities 
                    SET elevation_gain_meters = ?, ai_journal = ?
                    WHERE id = ?
                """, (elev_gain, new_critique, act_id))
                updated_count += 1
                logger.info(f"Updated {act_id} ({row['name']}): elev={elev_gain}m, critique refreshed.")

        conn.commit()
    logger.info(f"Successfully backfilled {updated_count} activities for {user_id}.")


if __name__ == "__main__":
    target_uid = sys.argv[1] if len(sys.argv) > 1 else "u_df65d9a588c9"
    backfill_user_garmin_elevation(target_uid)
