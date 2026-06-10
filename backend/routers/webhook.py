"""
Strava Webhook Router — handles push events for real-time activity sync.

GET  /api/webhook/strava  — Subscription validation (hub.challenge echo)
POST /api/webhook/strava  — Event receiver (activity create/update/delete)
"""

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from firebase_config import db
import os
import requests
from datetime import datetime
from utils.strava_config import STRAVA_OAUTH_TOKEN_URL, STRAVA_API_BASE

router = APIRouter()

VERIFY_TOKEN = os.getenv("STRAVA_WEBHOOK_VERIFY_TOKEN", "")


# ── GET: Subscription Validation ─────────────────────────────────────────────

@router.get("/strava")
def webhook_validation(request: Request):
    """
    Strava sends a GET request with hub.challenge to validate the callback URL.
    We must echo hub.challenge back in JSON to confirm the subscription.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and VERIFY_TOKEN and token == VERIFY_TOKEN and challenge:
        print(f"[webhook] Subscription validated: challenge={challenge}")
        return {"hub.challenge": challenge}

    return JSONResponse(status_code=403, content={"error": "Verification failed"})


# ── POST: Event Receiver ─────────────────────────────────────────────────────

@router.post("/strava")
def webhook_event(request_body: dict, background_tasks: BackgroundTasks):
    """
    Receives Strava webhook events. Must respond 200 within 2 seconds.
    Actual processing is done asynchronously in the background.
    """
    object_type = request_body.get("object_type")
    aspect_type = request_body.get("aspect_type")
    object_id = request_body.get("object_id")
    owner_id = request_body.get("owner_id")  # strava_athlete_id
    event_time = request_body.get("event_time")

    print(f"[webhook] Event: {aspect_type} {object_type} id={object_id} owner={owner_id}")

    updates = request_body.get("updates", {})

    if object_type == "athlete" and aspect_type == "update" and updates.get("authorized") == "false":
        background_tasks.add_task(_process_athlete_deauth, owner_id)
    elif object_type == "activity" and aspect_type == "delete":
        background_tasks.add_task(_process_activity_delete, owner_id, object_id)
    elif object_type == "activity" and aspect_type in ("create", "update"):
        # If the activity was made private, treat it as a delete to comply with transparency
        if aspect_type == "update" and updates.get("visibility") == "private":
            background_tasks.add_task(_process_activity_delete, owner_id, object_id)
        else:
            background_tasks.add_task(_process_activity_event, owner_id, object_id, aspect_type)

    return {"status": "ok"}


# ── Background Processing ────────────────────────────────────────────────────

from typing import Optional

def _find_uid_by_strava_id(strava_athlete_id: int) -> Optional[str]:
    """Finds the Firebase UID for a given Strava athlete ID."""
    docs = (db.collection("users")
              .where("strava_athlete_id", "==", strava_athlete_id)
              .limit(1)
              .stream())
    for doc in docs:
        return doc.id
    return None


def _recalculate_leaderboards(uid: str, user_ref):
    """Re-aggregates all activities for the current month/week and yearly leaderboards.

    Uses start_date_local range queries (consistent with sync.py) instead of
    period_start exact match — the latter breaks after full-history syncs
    because all historical activities share the same period_start value.
    """
    try:
        from routers.sync import get_period_start, _update_yearly_leaderboard, pace_str
        import calendar
        from zoneinfo import ZoneInfo

        user_doc = user_ref.get()
        if not user_doc.exists: return
        user_data = user_doc.to_dict()

        display_name = (
            user_data.get("display_name")
            or user_data.get("strava_name")
            or user_data.get("email", "").split("@")[0]
            or f"Runner #{uid[:6]}"
        )

        goal_snap = user_ref.collection("goals").document("current").get()
        period = "monthly"
        target_dist = 0
        if goal_snap.exists:
            goal_data = goal_snap.to_dict()
            period = goal_data.get("period", "monthly")
            target_dist = goal_data.get("target_distance", 0)

        # ── Monthly leaderboard (always based on current calendar month) ──
        month_start_str = get_period_start("monthly").strftime("%Y-%m-%dT%H:%M:%S")
        month_acts = (user_ref.collection("activities")
                      .where("start_date_local", ">=", month_start_str)
                      .stream())

        lb_dist, lb_time, lb_hr_sum, lb_hr_cnt, lb_runs, lb_elev = 0.0, 0, 0.0, 0, 0, 0.0
        for adoc in month_acts:
            ad = adoc.to_dict()
            # Only count runs for leaderboard (skip cross-training)
            if ad.get("activity_type", "run") != "run":
                continue
            lb_runs += 1
            lb_dist += ad.get("distance_km", 0) or 0
            lb_time += ad.get("moving_time", 0) or 0
            lb_elev += ad.get("total_elevation_gain", 0) or 0
            hr = ad.get("avg_heart_rate", 0) or 0
            if hr > 0:
                lb_hr_sum += hr
                lb_hr_cnt += 1

        lb_pace = pace_str(lb_dist * 1000, lb_time)
        lb_avg_hr = round(lb_hr_sum / lb_hr_cnt) if lb_hr_cnt > 0 else 0

        # Estimate monthly goal for weekly-plan users
        now = datetime.now(ZoneInfo("Asia/Singapore"))
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        monthly_target_dist = target_dist
        if period == "weekly" and target_dist > 0:
            monthly_target_dist = target_dist * (days_in_month / 7.0)
        pct = round((lb_dist / monthly_target_dist) * 100) if monthly_target_dist > 0 else 0

        db.collection("leaderboard").document(uid).set({
            "uid": uid,
            "display_name": display_name,
            "email": user_data.get("email", ""),
            "total_distance_km": round(lb_dist, 2),
            "total_elevation_gain": round(lb_elev, 1),
            "avg_pace": lb_pace,
            "avg_heart_rate": lb_avg_hr,
            "goal_completion_percentage": min(pct, 100),
            "run_count": lb_runs,
            "period": "monthly",
            "period_start": get_period_start("monthly").isoformat(),
            "last_sync": datetime.now().isoformat(),
        })  # Full set (not merge) to prevent stale data

        # ── Weekly leaderboard ──
        week_start_str = get_period_start("weekly").strftime("%Y-%m-%dT%H:%M:%S")
        week_acts = (user_ref.collection("activities")
                     .where("start_date_local", ">=", week_start_str)
                     .stream())

        wk_dist, wk_time, wk_hr_sum, wk_hr_cnt, wk_runs, wk_elev = 0.0, 0, 0.0, 0, 0, 0.0
        for adoc in week_acts:
            ad = adoc.to_dict()
            # Only count runs for leaderboard (skip cross-training)
            if ad.get("activity_type", "run") != "run":
                continue
            wk_runs += 1
            wk_dist += ad.get("distance_km", 0) or 0
            wk_time += ad.get("moving_time", 0) or 0
            wk_elev += ad.get("total_elevation_gain", 0) or 0
            hr = ad.get("avg_heart_rate", 0) or 0
            if hr > 0:
                wk_hr_sum += hr
                wk_hr_cnt += 1

        wk_pace = pace_str(wk_dist * 1000, wk_time)
        wk_avg_hr = round(wk_hr_sum / wk_hr_cnt) if wk_hr_cnt > 0 else 0
        wk_goal_pct = round((wk_dist / target_dist) * 100) if period == "weekly" and target_dist > 0 else 0

        db.collection("leaderboard_weekly").document(uid).set({
            "uid": uid,
            "display_name": display_name,
            "email": user_data.get("email", ""),
            "total_distance_km": round(wk_dist, 2),
            "total_elevation_gain": round(wk_elev, 1),
            "avg_pace": wk_pace,
            "avg_heart_rate": wk_avg_hr,
            "goal_completion_percentage": min(wk_goal_pct, 100),
            "run_count": wk_runs,
            "period": "weekly",
            "period_start": get_period_start("weekly").isoformat(),
            "last_sync": datetime.now().isoformat(),
        })  # Full set (not merge)

        _update_yearly_leaderboard(uid, user_data, display_name)
    except Exception as e:
        print(f"[webhook] leaderboard update failed: {e}")


def _process_athlete_deauth(strava_athlete_id: int):
    """Handles an athlete revoking access to the app from Strava."""
    uid = _find_uid_by_strava_id(strava_athlete_id)
    if not uid: return
    try:
        db.collection("users").document(uid).update({
            "strava_access_token": "",
            "strava_refresh_token": "",
            "strava_expires_at": 0,
        })
        print(f"[webhook] Successfully deauthorized uid={uid}")
    except Exception as e:
        print(f"[webhook] Deauthorization error for uid={uid}: {e}")


def _process_activity_delete(strava_athlete_id: int, activity_id: int):
    """Handles deletion of an activity on Strava (or becoming private)."""
    uid = _find_uid_by_strava_id(strava_athlete_id)
    if not uid: return
    try:
        user_ref = db.collection("users").document(uid)
        act_ref = user_ref.collection("activities").document(str(activity_id))
        
        if act_ref.get().exists:
            act_ref.delete()
            print(f"[webhook] Deleted activity {activity_id} for uid={uid}")
            _recalculate_leaderboards(uid, user_ref)
    except Exception as e:
        print(f"[webhook] Deletion handling failed for uid={uid} event={activity_id}: {e}")


def _process_activity_event(strava_athlete_id: int, activity_id: int, aspect_type: str):
    """
    Background task: resolves Strava athlete ID → Firebase UID,
    then triggers a sync for that user.
    """
    try:
        uid = _find_uid_by_strava_id(strava_athlete_id)
        if not uid:
            print(f"[webhook] No user found for strava_athlete_id={strava_athlete_id}")
            return

        # Log the webhook event (read once to avoid double Firestore read)
        try:
            log_ref = (db.collection("users").document(uid)
                         .collection("meta").document("webhook_log"))
            log_snap = log_ref.get()
            prev_total = (log_snap.to_dict() or {}).get("total_events", 0) if log_snap.exists else 0
            log_ref.set({
                "last_event": aspect_type,
                "last_activity_id": activity_id,
                "last_event_time": datetime.now().isoformat(),
                "total_events": prev_total + 1,
            }, merge=True)
        except Exception as e:
            print(f"[webhook] Log write failed: {e}")

        # Refresh token and fetch the specific activity
        user_ref = db.collection("users").document(uid)
        user_doc = user_ref.get()
        if not user_doc.exists:
            return

        user_data = user_doc.to_dict()
        refresh_token = user_data.get("strava_refresh_token")
        if not refresh_token:
            return

        client_id = os.getenv("STRAVA_CLIENT_ID")
        client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        if not client_id or not client_secret:
            return

        # Refresh access token (skip_throttle=True: token refresh is critical)
        from utils.strava_rate_limiter import strava_request
        token_resp = strava_request("POST", STRAVA_OAUTH_TOKEN_URL, data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }, skip_throttle=True)
        if not token_resp.ok:
            print(f"[webhook] Token refresh failed for uid={uid}")
            return

        new_token = token_resp.json()
        access_token = new_token["access_token"]
        user_ref.update({
            "strava_access_token": access_token,
            "strava_refresh_token": new_token["refresh_token"],
            "strava_expires_at": new_token["expires_at"],
        })

        # Fetch the specific activity
        act_resp = strava_request(
            "GET",
            f"{STRAVA_API_BASE}/activities/{activity_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        if not act_resp.ok:
            if act_resp.status_code == 404:
                # If 404, it might have been deleted right before sync. Conform to compliance: delete it locally.
                print(f"[webhook] Activity {activity_id} returned 404. Falling back to delete.")
                _process_activity_delete(strava_athlete_id, activity_id)
            else:
                print(f"[webhook] Failed to fetch activity {activity_id}: {act_resp.status_code}")
            return

        act = act_resp.json()
        act_type = act.get("type", "")
        from routers.sync import SYNCABLE_TYPES
        if act_type not in SYNCABLE_TYPES:
            print(f"[webhook] Skipping unsupported activity type {act_type} for {activity_id}")
            return
        is_run = (act_type == "Run")
            
        # Ensure compliance by strictly dropping private visibility runs
        if act.get("visibility") == "private":
            print(f"[webhook] Activity {activity_id} is strictly private. Ignoring update to preserve transparency.")
            _process_activity_delete(strava_athlete_id, activity_id)
            return

        # Save activity using the same format as sync.py
        from routers.sync import _build_act_doc, get_period_start, _update_yearly_leaderboard, CROSS_TRAINING_LABELS, _get_gear_details

        # Determine period
        goal_snap = user_ref.collection("goals").document("current").get()
        period = "monthly"
        if goal_snap.exists:
            period = goal_snap.to_dict().get("period", "monthly")
        period_start = get_period_start(period)

        gear_info = _get_gear_details(act.get("gear_id", ""), access_token, {})
        act_doc = _build_act_doc(act, period, period_start, gear_info)
        act_ref = user_ref.collection("activities").document(str(activity_id))
        act_ref.set(act_doc, merge=True)

        ct_label = CROSS_TRAINING_LABELS.get(act_type, act_type)
        if is_run:
            print(f"[webhook] Synced run {activity_id} for uid={uid} "
                  f"({act_doc['distance_km']}km, {act_doc['avg_pace']}/km)")
        else:
            print(f"[webhook] Synced cross-training {activity_id} for uid={uid} "
                  f"(type={ct_label}, {act_doc['duration_str']})")

        # Only recalculate run leaderboards for run activities
        if is_run:
            _recalculate_leaderboards(uid, user_ref)

        # ── Fetch & cache stream stats (runs only — cross-training has no pace/cadence data) ──
        stream_stats = {}
        if is_run:
            try:
                from utils.strava_rate_limiter import strava_request
                from utils.stream_analyzer import analyze_streams

                stream_resp = strava_request(
                    "GET",
                    f"{STRAVA_API_BASE}/activities/{activity_id}/streams",
                    params={
                        "keys": "distance,velocity_smooth,heartrate,cadence,altitude",
                        "key_by_type": "true",
                    },
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=15,
                )
                if stream_resp.ok:
                    raw = stream_resp.json()
                    max_hr = user_data.get("max_heart_rate", 190)
                    rest_hr = user_data.get("resting_heart_rate", 60)
                    stream_stats = analyze_streams(
                        distances=raw.get("distance", {}).get("data", []),
                        velocities=raw.get("velocity_smooth", {}).get("data", []),
                        heartrates=raw.get("heartrate", {}).get("data", []),
                        cadences=raw.get("cadence", {}).get("data", []),
                        altitudes=raw.get("altitude", {}).get("data", []),
                        max_hr=max_hr,
                        rest_hr=rest_hr,
                        official_splits=act.get("splits_metric"),
                    )
                    # Cache stream stats to the activity doc (avoid re-fetching from Strava)
                    if stream_stats:
                        act_ref.set({"stream_stats": stream_stats}, merge=True)
                        print(f"[webhook] Stream stats cached for {activity_id} "
                              f"({len(stream_stats.get('pace_splits', []))} km splits)")
                else:
                    print(f"[webhook] Streams fetch returned {stream_resp.status_code} — skipping")
            except Exception as _stream_err:
                print(f"[webhook] Stream analysis failed (non-critical): {_stream_err}")

        # ── For 'update' events (user edited title/photo on Strava): only sync data, skip notifications ──
        if aspect_type == "update":
            print(f"[webhook] Activity {activity_id} updated (metadata change) — data synced, skipping notifications")
            return

        # ── Generate journal entry (produces AI coach comment) ──
        # Works for both runs and cross-training — coach.py detects the type
        coach_tip = ""
        journal_entry = {}
        journal_cached = False
        try:
            from routers.coach import log_journal_entry, JournalLogRequest
            import asyncio

            journal_req = JournalLogRequest(uid=uid, activity_id=str(activity_id))
            # Run the async journal function synchronously in this background task
            loop = asyncio.new_event_loop()
            try:
                journal_result = loop.run_until_complete(log_journal_entry(journal_req))
            finally:
                loop.close()

            journal_cached = journal_result.get("cached", False)
            journal_entry = journal_result.get("entry", {})
            coach_tip = journal_entry.get("ai_comment", "")
            if coach_tip:
                print(f"[webhook] Journal entry {'cached' if journal_cached else 'created'}, AI comment will be reused for notifications")
        except Exception as _journal_err:
            print(f"[webhook] Journal entry generation failed (notifications will generate their own): {_journal_err}")

        # ── Notifications (non-blocking, never crashes the webhook) ──
        # Skip notifications if journal was cached (duplicate webhook event — notifications already sent)
        if journal_cached:
            print(f"[webhook] Skipping notifications for activity {activity_id} — already processed (duplicate event)")
        else:
            # Pass coach_tip + journal_entry so Discord/WeChat reuse the same AI content
            try:
                from utils.discord import send_activity_discord_notification, send_activity_wecom_notification
                send_activity_discord_notification(act_doc, user_data, uid=uid, coach_tip=coach_tip)
                send_activity_wecom_notification(act_doc, user_data, uid=uid, coach_tip=coach_tip, journal_entry=journal_entry)
            except Exception as _notify_err:
                print(f"[webhook] Notification delivery failed: {_notify_err}")

    except Exception as e:
        print(f"[webhook] Processing failed: {e}")
