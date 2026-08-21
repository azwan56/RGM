"""
Background Task Scheduler (APScheduler)
Executes:
1. Periodic Garmin activity & health sync for all active users (e.g. every 30 minutes)
2. Weekly review report generation (every Sunday midnight)
3. Leaderboard rank caching
"""

import logging
import time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import settings
from db import supabase_admin
from utils.local_store import LocalStore

logger = logging.getLogger("rgm_scheduler")
scheduler = BackgroundScheduler()

def sync_all_connected_users():
    """Iterates through all users with garmin_connected=True and triggers sync."""
    try:
        # 1. Fetch from LocalStore
        users = LocalStore.get_all_garmin_connected_users()
        user_map = {u["id"]: u for u in users}

        # 2. Also check Supabase if available
        if supabase_admin:
            try:
                res = supabase_admin.table("profiles").select("id, display_name").eq("garmin_connected", True).execute()
                for su in (res.data or []):
                    if su["id"] not in user_map:
                        user_map[su["id"]] = su
            except Exception:
                pass

        all_users = list(user_map.values())
        if not all_users:
            logger.info("[scheduler] No connected Garmin users to sync.")
            return

        logger.info(f"[scheduler] ⏳ Starting automatic polling sync for {len(all_users)} Garmin user(s)...")

        from routers.sync import sync_single_user
        for idx, u in enumerate(all_users):
            uid = u["id"]
            try:
                logger.info(f"[scheduler] [{idx+1}/{len(all_users)}] Auto-syncing Garmin for user {uid} ({u.get('display_name')})...")
                res = sync_single_user(uid)
                if res.get("success"):
                    logger.info(f"[scheduler] ✅ User {uid} auto-sync success: {res.get('synced_activities', 0)} activities synced.")
                else:
                    logger.warning(f"[scheduler] ⚠️ User {uid} auto-sync notice: {res.get('error')}")
            except Exception as e:
                logger.error(f"[scheduler] ❌ Failed to auto-sync user {uid}: {e}")
            
            # Stagger between users to avoid Garmin rate limits
            if idx < len(all_users) - 1:
                time.sleep(5)

        logger.info("[scheduler] 🎉 Automatic polling sync cycle completed.")
    except Exception as e:
        logger.error(f"[scheduler] Batch auto-sync exception: {e}")

def start_scheduler():
    if not settings.ENABLE_SCHEDULER:
        logger.info("[scheduler] Scheduler disabled by configuration.")
        return

    interval_minutes = getattr(settings, "GARMIN_SYNC_INTERVAL_MINUTES", 30)

    # Run Garmin sync every interval_minutes (default 30 min)
    scheduler.add_job(
        sync_all_connected_users,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="periodic_garmin_sync",
        replace_existing=True
    )

    scheduler.start()
    logger.info(f"[scheduler] Background scheduler started: Polling Garmin every {interval_minutes} minutes.")
