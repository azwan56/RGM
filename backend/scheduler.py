"""
Background Scheduler — daily auto-sync for all Strava-connected users.

Uses APScheduler to run periodic jobs:
  - Daily sync at 04:00 UTC (12:00 CST) — syncs current period data
  - Weekly yearly leaderboard refresh on Monday 05:00 UTC
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger("scheduler")

_scheduler: Optional[BackgroundScheduler] = None
_last_sync_result: dict = {}


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
            # Refresh token
            token_resp = requests.post("https://www.strava.com/oauth/token", data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }, timeout=15)

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
            act_resp = requests.get(
                "https://www.strava.com/api/v3/athlete/activities",
                params={"after": epoch_start, "per_page": 200},
                headers=headers,
                timeout=20,
            )

            if not act_resp.ok:
                results["failed"] += 1
                results["errors"].append(f"{uid}: activities fetch failed ({act_resp.status_code})")
                continue

            activities = act_resp.json()

            # Process runs
            total_dist, total_time, hr_sum, hr_cnt, run_count = 0.0, 0, 0, 0, 0
            batch = db.batch()

            for act in activities:
                if act.get("type") != "Run":
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
                act_ref = user_ref.collection("activities").document(str(act["id"]))
                batch.set(act_ref, _build_act_doc(act, period, period_start), merge=True)

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
            }, merge=True)

            _update_yearly_leaderboard(uid, user_data, display_name)
            results["synced"] += 1
            logger.info(f"[scheduler] Synced {uid}: {round(km, 1)}km, {run_count} runs")

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{uid}: {str(e)}")
            logger.error(f"[scheduler] Failed to sync {uid}: {e}")

    results["finished_at"] = datetime.now().isoformat()
    results["total_users"] = len(user_list)
    _last_sync_result = results
    logger.info(f"[scheduler] Daily sync complete: {results['synced']}/{len(user_list)} synced, "
                f"{results['failed']} failed, {results['skipped']} skipped")
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

    _scheduler.start()
    logger.info("[scheduler] Background scheduler started — daily sync at 04:00 UTC")


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
