#!/usr/bin/env python3
"""
Recalculate running mileage and reclassify activity sport types.
Ensures that RGM strictly calculates only standard running and trail running distance.
Cross-training, swimming, cycling, hiking, walking, etc. are NOT counted towards running mileage.

Usage:
    python3 backend/scripts/recalc_running_mileage.py [--db /path/to/rgm.db]
"""

import os
import sys
import sqlite3
import argparse
import logging
from typing import Optional

# Setup import path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from utils.local_store import LocalStore, DB_PATH, RUNNING_SPORT_TYPES, RUNNING_SQL_FILTER

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("recalc_mileage")


def reclassify_activities(conn: sqlite3.Connection):
    cursor = conn.cursor()
    logger.info("Scanning activities for classification correction...")

    # 1. Swimming
    cursor.execute("""
        UPDATE activities 
        SET sport_type = 'Swim'
        WHERE (name LIKE '%泳%' OR name LIKE '%Swim%' OR name LIKE '%swimming%')
          AND sport_type != 'Swim'
    """)
    swim_count = cursor.rowcount
    logger.info(f"Updated {swim_count} activities to 'Swim'")

    # 2. Paddleboarding / Water sports
    cursor.execute("""
        UPDATE activities 
        SET sport_type = 'Paddleboard'
        WHERE (name LIKE '%桨板%' OR name LIKE '%paddle%')
          AND sport_type != 'Paddleboard'
    """)
    paddle_count = cursor.rowcount
    logger.info(f"Updated {paddle_count} activities to 'Paddleboard'")

    # 3. Cycling / Ride (excluding running metaphorical names like '翻车')
    cursor.execute("""
        UPDATE activities 
        SET sport_type = 'Ride'
        WHERE (name LIKE '%骑%' OR name LIKE '%车%' OR name LIKE '%Bike%' OR name LIKE '%Cycling%')
          AND name NOT LIKE '%翻车%'
          AND sport_type NOT IN ('Run', 'running', 'trail_running', 'TrailRun', 'Ride')
    """)
    ride_count = cursor.rowcount
    logger.info(f"Updated {ride_count} activities to 'Ride'")

    # 4. Hiking
    cursor.execute("""
        UPDATE activities 
        SET sport_type = 'Hike'
        WHERE (name LIKE '%徒步%' OR name LIKE '%Hike%')
          AND sport_type != 'Hike'
          AND sport_type NOT IN ('Run', 'running', 'trail_running', 'TrailRun')
    """)
    hike_count = cursor.rowcount
    logger.info(f"Updated {hike_count} activities to 'Hike'")

    # 5. Walking
    cursor.execute("""
        UPDATE activities 
        SET sport_type = 'Walk'
        WHERE (name LIKE '%健走%' OR name LIKE '%散步%' OR name LIKE '%Walk%')
          AND sport_type != 'Walk'
          AND sport_type NOT IN ('Run', 'running', 'trail_running', 'TrailRun')
    """)
    walk_count = cursor.rowcount
    logger.info(f"Updated {walk_count} activities to 'Walk'")

    # 6. Strength / Cross-training
    cursor.execute("""
        UPDATE activities 
        SET sport_type = 'Workout'
        WHERE (name LIKE '%力量%' OR name LIKE '%身训%' OR name LIKE '%爬楼%' OR name LIKE '%有氧运动%')
          AND sport_type NOT IN ('Run', 'running', 'trail_running', 'TrailRun', 'Workout')
    """)
    workout_count = cursor.rowcount
    logger.info(f"Updated {workout_count} activities to 'Workout'")

    conn.commit()
    logger.info(f"Reclassification complete: {swim_count + paddle_count + ride_count + hike_count + walk_count + workout_count} rows adjusted.")


def update_canova_critiques(conn: sqlite3.Connection):
    cursor = conn.cursor()
    logger.info("Updating Canova AI critiques for non-running activities...")

    cursor.execute("""
        SELECT id, name, sport_type, distance_meters, moving_time_seconds, elevation_gain_meters, 
               avg_pace_str, average_heartrate, trimp, user_id, ai_journal
        FROM activities
        WHERE sport_type NOT IN ('Run', 'running', 'trail_running', 'TrailRun', 'treadmill_running', 'track_running', 'street_running', 'obstacle_run')
    """)
    rows = cursor.fetchall()
    updated = 0
    for r in rows:
        act = {
            "id": r[0],
            "name": r[1],
            "sport_type": r[2],
            "distance_meters": r[3],
            "moving_time_seconds": r[4],
            "elevation_gain_meters": r[5],
            "avg_pace_str": r[6],
            "average_heartrate": r[7],
            "trimp": r[8],
            "user_id": r[9],
            "ai_journal": r[10],
        }
        old_critique = str(r[10] or "")
        # If old critique was treating it as a run or empty, regenerate
        if "奔跑" in old_critique or "跑程" in old_critique or "配速" in old_critique or not old_critique.strip():
            new_critique = LocalStore.generate_canova_critique(act)
            cursor.execute("UPDATE activities SET ai_journal = ? WHERE id = ?", (new_critique, r[0]))
            updated += 1

    conn.commit()
    logger.info(f"Updated Canova critiques for {updated} non-running activities.")


def reconcile_active_training_plans(conn: sqlite3.Connection):
    cursor = conn.cursor()
    logger.info("Reconciling active training plans to remove non-running matching...")
    cursor.execute("SELECT id, user_id FROM training_plans WHERE status = 'active'")
    plans = cursor.fetchall()
    for pid, uid in plans:
        plan = LocalStore.get_user_active_training_plan(uid, reconcile=False)
        if plan:
            reconciled = LocalStore.reconcile_training_plan_activities(plan, uid)
            if reconciled and reconciled.get("schedule_data"):
                cursor.execute("UPDATE training_plans SET schedule_data = ? WHERE id = ?", (
                    reconciled["schedule_data"] if isinstance(reconciled["schedule_data"], str) else sqlite3.Binary(sqlite3.dumps(reconciled["schedule_data"])) if False else __import__("json").dumps(reconciled["schedule_data"]),
                    pid
                ))
    conn.commit()
    logger.info(f"Reconciled {len(plans)} active training plans.")


def report_user_mileage_changes(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT user_id 
        FROM activities 
        WHERE sport_type NOT IN ('Run', 'running', 'trail_running', 'TrailRun', 'treadmill_running', 'track_running', 'street_running', 'obstacle_run')
          AND distance_meters > 0
    """)
    uids = [r[0] for r in cursor.fetchall()]
    logger.info(f"Users with non-running distance activities: {len(uids)}")

    for uid in uids:
        # All distance in Sept
        cursor.execute("SELECT SUM(distance_meters) FROM activities WHERE user_id = ? AND start_time >= '2026-09-01'", (uid,))
        all_dist = cursor.fetchone()[0] or 0.0
        # Running distance in Sept
        cursor.execute(f"SELECT SUM(distance_meters) FROM activities WHERE user_id = ? AND start_time >= '2026-09-01' AND {RUNNING_SQL_FILTER}", (uid,))
        run_dist = cursor.fetchone()[0] or 0.0

        # All distance all time
        cursor.execute("SELECT SUM(distance_meters) FROM activities WHERE user_id = ?", (uid,))
        all_time_all = cursor.fetchone()[0] or 0.0
        cursor.execute(f"SELECT SUM(distance_meters) FROM activities WHERE user_id = ? AND {RUNNING_SQL_FILTER}", (uid,))
        all_time_run = cursor.fetchone()[0] or 0.0

        logger.info(
            f"User '{uid}': Sept All={all_dist/1000:.2f}km -> RunOnly={run_dist/1000:.2f}km (Diff: -{(all_dist-run_dist)/1000:.2f}km) | "
            f"AllTime All={all_time_all/1000:.2f}km -> RunOnly={all_time_run/1000:.2f}km (Diff: -{(all_time_all-all_time_run)/1000:.2f}km)"
        )


def main():
    parser = argparse.ArgumentParser(description="Recalculate running mileage and reclassify activities")
    parser.add_argument("--db", type=str, default=DB_PATH, help="Path to rgm.db SQLite file")
    args = parser.parse_args()

    db_path = args.db
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}")
        sys.exit(1)

    logger.info(f"Connecting to database at {db_path}...")
    conn = sqlite3.connect(db_path)
    try:
        reclassify_activities(conn)
        update_canova_critiques(conn)
        reconcile_active_training_plans(conn)
        report_user_mileage_changes(conn)
        logger.info("Recalculation and reclassification successfully completed!")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
