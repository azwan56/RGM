"""
Background Task Scheduler (APScheduler)
Executes:
1. Periodic Garmin activity & health sync for all active users (e.g. every 30 minutes)
2. Weekly review report generation (every Sunday midnight)
3. Leaderboard rank caching
"""

import logging
import threading
import time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from config import settings
from db import supabase_admin
from utils.local_store import LocalStore

logger = logging.getLogger("rgm_scheduler")
scheduler = BackgroundScheduler(
    job_defaults={
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": 300,
    }
)
_sync_batch_lock = threading.Lock()

def sync_all_connected_users():
    """Iterates through all users with garmin_connected=True or coros_connected=True and triggers sync."""
    if not _sync_batch_lock.acquire(blocking=False):
        logger.info("[scheduler] Previous automatic sync batch still running; skipping overlapping trigger.")
        return
    try:
        # 1. Fetch from LocalStore
        users = LocalStore.get_all_syncable_users()
        user_map = {u["id"]: u for u in users}

        # 2. Also check Supabase if available
        if supabase_admin:
            try:
                res_g = supabase_admin.table("profiles").select("id, display_name").eq("garmin_connected", True).execute()
                for su in (res_g.data or []):
                    if su["id"] not in user_map:
                        user_map[su["id"]] = su
                res_c = supabase_admin.table("profiles").select("id, display_name").eq("coros_connected", True).execute()
                for su in (res_c.data or []):
                    if su["id"] not in user_map:
                        user_map[su["id"]] = su
            except Exception:
                pass

        all_users = list(user_map.values())
        if not all_users:
            logger.info("[scheduler] No connected Garmin/COROS users to sync.")
            return

        logger.info(f"[scheduler] ⏳ Starting automatic polling sync for {len(all_users)} device user(s)...")

        from routers.sync import sync_single_user
        for idx, u in enumerate(all_users):
            uid = u["id"]
            try:
                logger.info(f"[scheduler] [{idx+1}/{len(all_users)}] Auto-syncing devices for user {uid} ({u.get('display_name')})...")
                res = sync_single_user(uid)
                if res.get("success"):
                    logger.info(f"[scheduler] ✅ User {uid} auto-sync success: {res.get('synced_activities', 0)} activities synced.")
                else:
                    logger.warning(f"[scheduler] ⚠️ User {uid} auto-sync notice: {res.get('error')}")
            except Exception as e:
                logger.error(f"[scheduler] ❌ Failed to auto-sync user {uid}: {e}")
            
            # Gentle stagger between users to respect Garmin/COROS rate limits without blocking the cycle
            if idx < len(all_users) - 1:
                time.sleep(1.5)

        logger.info("[scheduler] 🎉 Automatic polling sync cycle completed.")
    except Exception as e:
        logger.error(f"[scheduler] Batch auto-sync exception: {e}")
    finally:
        _sync_batch_lock.release()

def enforce_org_profile_deadlines_job():
    """Daily: remind members to complete 大群资料 (7/3/1 days left) and remove expired members from all sub-clubs."""
    try:
        res = LocalStore.enforce_org_profile_deadlines()
        logger.info(f"[scheduler] 🏛️ Org profile deadline sweep done: {res}")
    except Exception as e:
        logger.error(f"[scheduler] Org profile deadline sweep failed: {e}")


def start_scheduler():
    if not settings.ENABLE_SCHEDULER:
        logger.info("[scheduler] Scheduler disabled by configuration.")
        return

    # 0. 大群资料补填期限：每天 09:05 / 21:05 (北京时间) 提醒并清理逾期队员
    scheduler.add_job(
        enforce_org_profile_deadlines_job,
        trigger=CronTrigger(hour="9,21", minute=5),
        id="org_profile_deadline_sweep",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # 1. Unified non-overlapping active-hours watch sync (05:00 - 22:59 every 15 min)
    scheduler.add_job(
        sync_all_connected_users,
        trigger=CronTrigger(hour="5-22", minute="0,15,30,45"),
        id="periodic_watch_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # 2. Low-frequency overnight watch sync (01:00 & 03:00 at minute 0)
    scheduler.add_job(
        sync_all_connected_users,
        trigger=CronTrigger(hour="1,3", minute=0),
        id="overnight_watch_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    if not scheduler.running:
        scheduler.start()
    logger.info("[scheduler] Background scheduler started: Unified watch sync active (05:00-22:45 q15m + 01:00/03:00 overnight).")
