"""
Cron Trigger Router — HTTP Endpoints for GCP Cloud Scheduler / External Cron Jobs.

Security: Protected via CRON_SECRET environment variable passed in header 'X-Cron-Secret' or query param 'secret'.
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Header, Query
from scheduler import run_daily_sync

logger = logging.getLogger("cron_router")
router = APIRouter()

CRON_SECRET = os.getenv("CRON_SECRET", "")


def verify_cron_secret(x_cron_secret: str = Header(None), secret: str = Query(None)):
    """Verifies that incoming request matches CRON_SECRET if specified."""
    if not CRON_SECRET:
        # If no secret configured, allow call but warn in logs
        logger.warning("[cron] CRON_SECRET is not configured in env, request processed without secret verification")
        return
    
    provided = x_cron_secret or secret
    if provided != CRON_SECRET:
        raise HTTPException(status_code=401, detail="Invalid Cron Secret")


@router.post("/daily-sync")
def trigger_daily_sync(x_cron_secret: str = Header(None), secret: str = Query(None)):
    """Triggers daily sync for Strava & Garmin connected users."""
    verify_cron_secret(x_cron_secret, secret)
    logger.info("[cron] Manual/Cloud Scheduler trigger for daily sync received")
    res = run_daily_sync()
    return {"status": "completed", "result": res}
