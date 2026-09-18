#!/usr/bin/env python3
"""
Recalculates COROS activities with corrected workoutTime (active moving time)
excluding pause/rest intervals, updates avg_pace_str, TRIMP, and refreshes Canova critiques.
"""
import os
import sys
import argparse
import logging
from datetime import date

# Ensure backend path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.local_store import LocalStore
from utils.coros_adapter import CorosAdapter
from utils.running_metrics import calculate_trimp
from utils.encryption import decrypt_string

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("recalculate_coros_activities")


def sync_and_recalculate_user_coros(uid: str, start_year: int = 2026) -> int:
    profile = LocalStore.get_profile(uid)
    if not profile or not profile.get("coros_connected"):
        logger.warning(f"User {uid} is not connected to COROS.")
        return 0

    account = profile.get("coros_account")
    enc_pwd = profile.get("coros_encrypted_password")
    domain = profile.get("coros_domain") or "teamcnapi.coros.com"
    if not account or not enc_pwd:
        logger.warning(f"User {uid} missing COROS account credentials.")
        return 0

    pwd = decrypt_string(enc_pwd)
    if not pwd:
        logger.warning(f"User {uid} unable to decrypt password.")
        return 0

    adapter = CorosAdapter(account=account, password=pwd, domain=domain)
    if not adapter.login():
        logger.error(f"Failed to log in to COROS for user {uid} ({account}).")
        return 0

    logger.info(f"Fetching COROS activities since {start_year}-01-01 for {account}...")
    acts = adapter.fetch_activities_by_date(start_date=f"{start_year}-01-01")
    if not acts:
        logger.info(f"fetch_activities_by_date returned 0, falling back to fetch_recent_activities...")
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
        if updated <= 5 or act.get("id") == "coros_480279389475471569":
            logger.info(f"Updated {act.get('id')}: {act.get('name')}, Moving: {act.get('moving_time_seconds')}s, Elapsed: {act.get('elapsed_time_seconds')}s, Pace: {act.get('avg_pace_str')}, TRIMP: {act.get('trimp')}")

    logger.info(f"Successfully updated {updated} COROS activities for user {uid}.")
    return updated


def main():
    parser = argparse.ArgumentParser(description="Recalculate COROS activities with accurate moving pace.")
    parser.add_argument("--uid", type=str, help="User ID to recalculate (optional, defaults to all connected COROS users)")
    parser.add_argument("--year", type=int, default=2026, help="Start year (default 2026)")
    args = parser.parse_args()

    if args.uid:
        sync_and_recalculate_user_coros(args.uid, start_year=args.year)
    else:
        syncable = LocalStore.get_all_syncable_users()
        coros_users = [u for u in syncable if u.get("coros_connected")]
        logger.info(f"Found {len(coros_users)} COROS-connected users to process.")
        for u in coros_users:
            sync_and_recalculate_user_coros(u["id"], start_year=args.year)


if __name__ == "__main__":
    main()
