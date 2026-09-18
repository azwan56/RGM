#!/usr/bin/env python3
"""
Recalculates COROS activities with corrected workoutTime (active moving time)
excluding pause/rest intervals, updates avg_pace_str, TRIMP, and refreshes Canova critiques.
"""
import os
import sys
import argparse
import logging

# Ensure backend path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.local_store import LocalStore
from utils.coros_adapter import CorosAdapter
from utils.running_metrics import calculate_trimp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("recalculate_coros_activities")


def sync_and_recalculate_user_coros(uid: str, days: int = 90) -> int:
    profile = LocalStore.get_profile(uid)
    if not profile or not profile.get("coros_connected"):
        logger.warning(f"User {uid} is not connected to COROS.")
        return 0

    account = profile.get("coros_account")
    pwd = profile.get("coros_encrypted_password")
    domain = profile.get("coros_domain") or "teamcnapi.coros.com"
    if not account or not pwd:
        logger.warning(f"User {uid} missing COROS account credentials.")
        return 0

    adapter = CorosAdapter(account=account, password=pwd, domain=domain)
    if not adapter.login():
        logger.error(f"Failed to log in to COROS for user {uid} ({account}).")
        return 0

    logger.info(f"Fetching recent COROS activities for {account}...")
    acts = adapter.fetch_recent_activities(limit=100)
    logger.info(f"Retrieved {len(acts)} activities from COROS.")

    rest_hr = profile.get("resting_heart_rate") or 60
    max_hr = profile.get("max_heart_rate") or 190
    gender = profile.get("gender") or "male"

    updated = 0
    for act in acts:
        act["user_id"] = uid
        moving_mins = (act.get("moving_time_seconds") or 0) / 60.0
        avg_hr = act.get("average_heartrate")
        if avg_hr and avg_hr > rest_hr:
            act["trimp"] = calculate_trimp(moving_mins, avg_hr, rest_hr, max_hr, gender)
        else:
            act["trimp"] = round(moving_mins * 0.8, 1)

        # Clear old ai_journal so Canova critique will be regenerated with new pace
        act["ai_journal"] = None
        LocalStore.upsert_activity(act)
        updated += 1
        logger.info(f"Updated activity {act.get('id')}: {act.get('name')}, Moving: {act.get('moving_time_seconds')}s, Pace: {act.get('avg_pace_str')}")

    logger.info(f"Successfully updated {updated} COROS activities for user {uid}.")
    return updated


def main():
    parser = argparse.ArgumentParser(description="Recalculate COROS activities with accurate moving pace.")
    parser.add_argument("--uid", type=str, help="User ID to recalculate (optional, defaults to all connected COROS users)")
    args = parser.parse_args()

    if args.uid:
        sync_and_recalculate_user_coros(args.uid)
    else:
        syncable = LocalStore.get_all_syncable_users()
        coros_users = [u for u in syncable if u.get("coros_connected")]
        logger.info(f"Found {len(coros_users)} COROS-connected users to process.")
        for u in coros_users:
            sync_and_recalculate_user_coros(u["id"])


if __name__ == "__main__":
    main()
