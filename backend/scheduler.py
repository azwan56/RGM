"""
Background Scheduler — daily auto-sync for all Strava-connected users.

Uses APScheduler to run periodic jobs:
  - Daily sync at 04:00 UTC (12:00 CST) — syncs current period data
  - Weekly yearly leaderboard refresh on Monday 05:00 UTC
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional
import logging

logger = logging.getLogger("scheduler")

_scheduler: Optional[BackgroundScheduler] = None
_last_sync_result: dict = {}


def _get_user_tz_name(user_data, uid, db) -> str:
    """Determine the user's timezone from recent activities, fallback to Asia/Singapore."""
    from collections import Counter
    recent_acts = [d.to_dict() for d in
                   db.collection("users").document(uid)
                   .collection("activities")
                   .order_by("start_date_local", direction="DESCENDING")
                   .limit(10).stream()]
    tz_names = [a.get("timezone", "") for a in recent_acts if a.get("timezone", "")]
    if tz_names:
        clean_tzs = []
        for tz in tz_names:
            if " " in tz:
                clean_tzs.append(tz.split(" ", 1)[1])
            else:
                clean_tzs.append(tz)
        if clean_tzs:
            return Counter(clean_tzs).most_common(1)[0][0]
    return "Asia/Singapore"


def run_daily_sync() -> dict:
    """
    Iterates through all Strava-connected users and triggers a sync
    for each. Returns a summary of results.
    """
    global _last_sync_result
    from firebase_config import db
    from routers.sync import (
        get_period_start, _build_act_doc, _update_yearly_leaderboard,
        pace_str,
    )
    import requests
    import os

    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    if not client_id or not client_secret:
        logger.error("[scheduler] Strava credentials missing, skipping sync")
        return {"error": "Strava credentials missing"}

    # Find all Strava-connected users
    users = db.collection("users").where("strava_connected", "==", True).stream()
    user_list = [(doc.id, doc.to_dict()) for doc in users]

    results = {"synced": 0, "failed": 0, "skipped": 0, "errors": [], "started_at": datetime.now().isoformat()}

    for uid, user_data in user_list:
        refresh_token = user_data.get("strava_refresh_token")
        if not refresh_token:
            results["skipped"] += 1
            continue

        try:
            # Refresh token (skip throttle for auth requests)
            from utils.strava_rate_limiter import strava_request, get_rate_limit_status
            from utils.strava_config import STRAVA_OAUTH_TOKEN_URL, STRAVA_API_BASE
            token_resp = strava_request("POST", STRAVA_OAUTH_TOKEN_URL, data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }, timeout=15, skip_throttle=True)

            if not token_resp.ok:
                results["failed"] += 1
                results["errors"].append(f"{uid}: token refresh failed ({token_resp.status_code})")
                continue

            new_token = token_resp.json()
            access_token = new_token["access_token"]

            # Update tokens in Firestore
            user_ref = db.collection("users").document(uid)
            user_ref.update({
                "strava_access_token": access_token,
                "strava_refresh_token": new_token["refresh_token"],
                "strava_expires_at": new_token["expires_at"],
            })

            # Goal period
            goal_snap = user_ref.collection("goals").document("current").get()
            period = "monthly"
            target_dist = 0
            if goal_snap.exists:
                gd = goal_snap.to_dict()
                period = gd.get("period", "monthly")
                target_dist = gd.get("target_distance", 0)

            period_start = get_period_start(period)
            epoch_start = int(period_start.timestamp())

            # Fetch activities
            headers = {"Authorization": f"Bearer {access_token}"}
            act_resp = strava_request(
                "GET",
                f"{STRAVA_API_BASE}/athlete/activities",
                params={"after": epoch_start, "per_page": 200},
                headers=headers,
                timeout=20,
            )

            if not act_resp.ok:
                results["failed"] += 1
                results["errors"].append(f"{uid}: activities fetch failed ({act_resp.status_code})")
                continue

            activities = act_resp.json()

            # Process activities (runs + cross-training)
            from routers.sync import SYNCABLE_TYPES
            total_dist, total_time, hr_sum, hr_cnt, run_count = 0.0, 0, 0, 0, 0
            batch = db.batch()

            for act in activities:
                act_type = act.get("type", "")
                if act_type not in SYNCABLE_TYPES:
                    continue

                # Save all syncable activities to Firestore
                act_ref = user_ref.collection("activities").document(str(act["id"]))
                batch.set(act_ref, _build_act_doc(act, period, period_start), merge=True)

                # Only count runs for leaderboard stats
                if act_type != "Run":
                    continue
                run_count += 1
                dist = act.get("distance", 0)
                t = act.get("moving_time", 0)
                avg_hr = act.get("average_heartrate") or 0
                total_dist += dist
                total_time += t
                if act.get("has_heartrate") and avg_hr:
                    hr_sum += avg_hr
                    hr_cnt += 1

            batch.commit()

            # Update leaderboard
            km = total_dist / 1000
            pct = round((km / target_dist) * 100) if target_dist > 0 else 0
            display_name = (
                user_data.get("display_name")
                or user_data.get("strava_name")
                or (user_data.get("email", "").split("@")[0] if user_data.get("email") else None)
                or f"Runner #{uid[:6]}"
            )

            db.collection("leaderboard").document(uid).set({
                "uid": uid,
                "display_name": display_name,
                "email": user_data.get("email", ""),
                "total_distance_km": round(km, 2),
                "avg_pace": pace_str(total_dist, total_time),
                "avg_heart_rate": round(hr_sum / hr_cnt) if hr_cnt else 0,
                "goal_completion_percentage": min(pct, 100),
                "run_count": run_count,
                "period": period,
                "period_start": period_start.isoformat(),
                "last_sync": datetime.now().isoformat(),
            })  # Full set (not merge) — prevents stale data from persisting

            _update_yearly_leaderboard(uid, user_data, display_name)
            results["synced"] += 1
            logger.info(f"[scheduler] Synced {uid}: {round(km, 1)}km, {run_count} runs")

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{uid}: {str(e)}")
            logger.error(f"[scheduler] Failed to sync {uid}: {e}")

    results["finished_at"] = datetime.now().isoformat()
    results["total_users"] = len(user_list)
    # Log Strava rate limit status after sync
    try:
        rl_status = get_rate_limit_status()
        results["strava_rate_limit"] = rl_status
        o = rl_status["overall"]
        r = rl_status["read"]
        logger.info(
            f"[scheduler] Strava rate limit — "
            f"Overall: {o['usage_daily']}/{o['limit_daily']} daily ({o['pct_used_daily']}%), "
            f"Read: {r['usage_daily']}/{r['limit_daily']} daily ({r['pct_used_daily']}%)"
        )
    except Exception:
        pass
    _last_sync_result = results
    logger.info(f"[scheduler] Daily sync complete: {results['synced']}/{len(user_list)} synced, "
                f"{results['failed']} failed, {results['skipped']} skipped")
    return results


def run_rest_day_reminders() -> dict:
    """
    Runs hourly. For each Strava-connected user, checks if it's 06:00 in their local time.
    If so, checks whether they had any run recorded for the previous calendar day.
    If not, sends a rest-day reminder.
    """
    from firebase_config import db
    from utils.discord import send_rest_day_discord_notification, send_rest_day_wecom_notification

    users = db.collection("users").where("strava_connected", "==", True).stream()
    user_list = [(doc.id, doc.to_dict()) for doc in users]

    results = {"reminded": 0, "skipped": 0, "errors": []}

    for uid, user_data in user_list:
        try:
            # Skip users who have opted out of rest-day reminders
            if not user_data.get("rest_day_reminder", True):
                results["skipped"] += 1
                continue

            tz_name = _get_user_tz_name(user_data, uid, db)
            tz = ZoneInfo(tz_name)
            local_now = datetime.now(tz)

            # Only process if it's 06:00 local time
            if local_now.hour != 6:
                continue

            yesterday = (local_now - timedelta(days=1)).date()
            yesterday_str = yesterday.isoformat()  # "YYYY-MM-DD"

            logger.info(f"[scheduler] Rest-day reminder check for {uid} in {tz_name} for {yesterday_str}")

            # Check Firestore activities for any run dated yesterday
            acts = (
                db.collection("users").document(uid)
                .collection("activities")
                .order_by("start_date_local", direction="DESCENDING")
                .limit(10)
                .stream()
            )
            had_run = any(
                a.to_dict().get("start_date_local", "")[:10] == yesterday_str
                for a in acts
            )

            if had_run:
                results["skipped"] += 1
                logger.debug(f"[scheduler] {uid} ran yesterday — no reminder needed")
                continue

            # Send reminders (both platforms; each silently skips if no webhook configured)
            send_rest_day_discord_notification(user_data, uid, yesterday_str)
            send_rest_day_wecom_notification(user_data, uid, yesterday_str)
            results["reminded"] += 1
            logger.info(f"[scheduler] Rest-day reminder sent to uid={uid}")

        except Exception as e:
            results["errors"].append(f"{uid}: {e}")
            logger.error(f"[scheduler] Rest-day reminder failed for uid={uid}: {e}")

    logger.info(
        f"[scheduler] Rest-day reminders done — "
        f"{results['reminded']} reminded, {results['skipped']} skipped, "
        f"{len(results['errors'])} errors"
    )
    return results


def run_weekly_reports(force: bool = False) -> dict:
    """
    Runs hourly. For each Strava-connected user, checks if it's Monday 01:00-05:00 in their local time.
    If so, generates a comprehensive weekly training report for the previous week
    and sends it via Discord and WeCom. Also emails it if the user's goal period is 'weekly'.
    """
    import asyncio
    from firebase_config import db
    from routers.coach import generate_auto_weekly_report
    from utils.discord import send_weekly_report_discord_notification, send_weekly_report_wecom_notification
    from utils.email import send_report_email

    users = db.collection("users").where("strava_connected", "==", True).stream()
    user_list = [(doc.id, doc.to_dict()) for doc in users]

    results = {"generated": 0, "failed": 0, "skipped": 0, "errors": [], "force": force}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for uid, user_data in user_list:
        try:
            tz_name = _get_user_tz_name(user_data, uid, db)
            tz = ZoneInfo(tz_name)
            local_now = datetime.now(tz)

            # Time check: skip if not Monday 1-5 AM local time (unless force=True)
            if not force:
                if local_now.weekday() != 0 or local_now.hour not in (1, 2, 3, 4, 5):
                    continue

            # Avoid duplicates
            last_week_monday = (local_now.date() - timedelta(days=local_now.weekday() + 7))
            week_number = last_week_monday.isocalendar()[1]
            week_year = last_week_monday.isocalendar()[0]
            
            doc_id = f"{week_year}-W{week_number:02d}"
            report_doc = db.collection("users").document(uid).collection("weekly_reports").document(doc_id).get()
            if report_doc.exists:
                continue

            logger.info(f"[scheduler] Triggering weekly report for uid={uid} in {tz_name}")

            # Generate the report
            res = loop.run_until_complete(generate_auto_weekly_report(uid, tz_name=tz_name))
            
            if "error" in res:
                if res["error"] == "上周暂无训练记录":
                    logger.info(f"[scheduler] {uid} had no runs last week, skipped.")
                else:
                    results["failed"] += 1
                    results["errors"].append(f"{uid}: {res['error']}")
                continue

            report = res.get("review", {})
            if not report:
                continue

            # Send notifications
            send_weekly_report_discord_notification(user_data, uid, report)
            send_weekly_report_wecom_notification(user_data, uid, report)
            
            # Send Email IF user's goal period is 'weekly'
            goal_snap = db.collection("users").document(uid).collection("goals").document("current").get()
            period = "monthly"
            if goal_snap.exists:
                period = goal_snap.to_dict().get("period", "monthly")
                
            if period == "weekly" and user_data.get("email"):
                send_report_email(
                    to_email=user_data["email"],
                    user_name=user_data.get("strava_name") or user_data.get("display_name"),
                    period_name="周",
                    report=report
                )
            
            results["generated"] += 1
            logger.info(f"[scheduler] Weekly report generated and sent for uid={uid}")

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{uid}: {str(e)}")
            logger.error(f"[scheduler] Weekly report failed for uid={uid}: {e}")

    loop.close()
    
    logger.info(
        f"[scheduler] Weekly reports done — "
        f"{results['generated']} generated, {results['failed']} failed, "
        f"{len(results['errors'])} errors"
    )
    return results


def run_monthly_reports(force: bool = False) -> dict:
    """
    Runs hourly. For each Strava-connected user, checks if it's the 1st of the month 
    between 01:00-05:00 in their local time.
    If so, generates a comprehensive monthly training report for the previous month
    and emails it IF the user's goal period is 'monthly'.
    """
    import asyncio
    from firebase_config import db
    from routers.coach import generate_auto_monthly_report
    from utils.email import send_report_email

    users = db.collection("users").where("strava_connected", "==", True).stream()
    user_list = [(doc.id, doc.to_dict()) for doc in users]

    results = {"generated": 0, "failed": 0, "skipped": 0, "errors": [], "force": force}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for uid, user_data in user_list:
        try:
            # Only process if goal period is monthly
            goal_snap = db.collection("users").document(uid).collection("goals").document("current").get()
            period = "monthly"
            if goal_snap.exists:
                period = goal_snap.to_dict().get("period", "monthly")
                
            if period != "monthly":
                continue

            tz_name = _get_user_tz_name(user_data, uid, db)
            tz = ZoneInfo(tz_name)
            local_now = datetime.now(tz)

            # Time check: skip if not 1st of month 1-5 AM local time (unless force=True)
            if not force:
                if local_now.day != 1 or local_now.hour not in (1, 2, 3, 4, 5):
                    continue

            # Avoid duplicates
            first_of_current = local_now.date().replace(day=1)
            last_day_prev = first_of_current - timedelta(days=1)
            month_number = last_day_prev.month
            month_year = last_day_prev.year
            
            doc_id = f"{month_year}-{month_number:02d}"
            report_doc = db.collection("users").document(uid).collection("monthly_reports").document(doc_id).get()
            if report_doc.exists:
                continue

            logger.info(f"[scheduler] Triggering monthly report for uid={uid} in {tz_name}")

            # Generate the report
            res = loop.run_until_complete(generate_auto_monthly_report(uid, tz_name=tz_name))
            
            if "error" in res:
                if res["error"] == "上月暂无训练记录":
                    logger.info(f"[scheduler] {uid} had no runs last month, skipped.")
                else:
                    results["failed"] += 1
                    results["errors"].append(f"{uid}: {res['error']}")
                continue

            report = res.get("review", {})
            if not report:
                continue
                
            # Send Email
            if user_data.get("email"):
                send_report_email(
                    to_email=user_data["email"],
                    user_name=user_data.get("strava_name") or user_data.get("display_name"),
                    period_name="月",
                    report=report
                )
            
            results["generated"] += 1
            logger.info(f"[scheduler] Monthly report generated and sent for uid={uid}")

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{uid}: {str(e)}")
            logger.error(f"[scheduler] Monthly report failed for uid={uid}: {e}")

    loop.close()
    
    logger.info(
        f"[scheduler] Monthly reports done — "
        f"{results['generated']} generated, {results['failed']} failed, "
        f"{len(results['errors'])} errors"
    )
    return results


def start_scheduler():
    """Initialize and start the APScheduler background scheduler."""
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler(timezone="UTC")

    # Daily sync at 04:00 UTC (12:00 CST)
    _scheduler.add_job(
        run_daily_sync,
        trigger=CronTrigger(hour=4, minute=0),
        id="daily_sync",
        name="Daily Strava Sync",
        replace_existing=True,
        misfire_grace_time=3600,  # 1 hour grace period
    )

    # Rest-day reminder (runs hourly, checks per-user local time for 06:00)
    _scheduler.add_job(
        run_rest_day_reminders,
        trigger=CronTrigger(minute=0),
        id="rest_day_reminder",
        name="Rest Day Reminder",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    
    # Weekly report (runs hourly, checks per-user local time for Monday 01:00)
    _scheduler.add_job(
        run_weekly_reports,
        trigger=CronTrigger(minute=0),
        id="weekly_reports",
        name="Weekly Reports",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    
    # Monthly report (runs hourly, checks per-user local time for 1st of month 01:00)
    _scheduler.add_job(
        run_monthly_reports,
        trigger=CronTrigger(minute=0),
        id="monthly_reports",
        name="Monthly Reports",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.start()
    logger.info(
        "[scheduler] Background scheduler started — "
        "daily sync at 04:00 UTC, rest-day reminder hourly, "
        "weekly/monthly reports hourly (checks per-user local time)"
    )


def get_scheduler_status() -> dict:
    """Returns current scheduler state and job info."""
    if _scheduler is None:
        return {"status": "not_started", "jobs": []}

    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": str(job.next_run_time) if job.next_run_time else None,
        })

    return {
        "status": "running" if _scheduler.running else "stopped",
        "jobs": jobs,
        "last_sync_result": _last_sync_result or None,
    }
