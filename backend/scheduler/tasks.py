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
from apscheduler.triggers.interval import IntervalTrigger
from config import settings
from db import supabase_admin
from utils.local_store import LocalStore

logger = logging.getLogger("rgm_scheduler")
scheduler = BackgroundScheduler()
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
            
            # Stagger between users to avoid Garmin rate limits
            if idx < len(all_users) - 1:
                time.sleep(5)

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

    from apscheduler.triggers.cron import CronTrigger
    interval_minutes = getattr(settings, "GARMIN_SYNC_INTERVAL_MINUTES", 30)

    # 0. 大群资料补填期限：每天 09:00 / 21:00 (北京时间) 提醒并清理逾期队员
    scheduler.add_job(
        enforce_org_profile_deadlines_job,
        trigger=CronTrigger(hour="9,21", minute=5),  # 容器时区 Asia/Shanghai → 北京 09:05 / 21:05
        id="org_profile_deadline_sweep",
        replace_existing=True
    )

    # 1. Run Garmin/COROS sync every interval_minutes (default 30 min)
    scheduler.add_job(
        sync_all_connected_users,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="periodic_garmin_sync",
        replace_existing=True
    )

    # 2. High-frequency early morning pre-push sync (05:00 - 09:59 every 15 min)
    # so overnight sleep, HRV, and RHR are ready before the user's morning recovery push
    scheduler.add_job(
        sync_all_connected_users,
        trigger=CronTrigger(hour="5-9", minute="0,15,30,45"),
        id="morning_pre_push_sync",
        replace_existing=True
    )

    # 3. Daytime & post-nap / evening activity sync (12:00 - 22:59 every 15 min)
    # so midday naps, daytime steps/calories, stress, and heart rate fluctuations update automatically
    scheduler.add_job(
        sync_all_connected_users,
        trigger=CronTrigger(hour="12-22", minute="0,15,30,45"),
        id="daytime_activity_nap_stress_sync",
        replace_existing=True
    )

    scheduler.start()
    logger.info(f"[scheduler] Background scheduler started: Polling watches every {interval_minutes} min + 15-min morning (05:00-09:59) & daytime/nap (12:00-22:59) windows.")
