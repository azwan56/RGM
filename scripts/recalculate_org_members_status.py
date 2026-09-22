#!/usr/bin/env python3
"""
Recalculates and enforces member statuses across all organizations.
Members missing required fields are downgraded to 'temporary' (or 'expired').
"""

import sys
import os
import sqlite3
import json
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from utils.local_store import LocalStore, DB_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("recalc_status")


def recalculate_statuses(target_db: str = DB_PATH):
    logger.info(f"Connecting to database: {target_db}")
    with sqlite3.connect(target_db) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT m.org_id, m.user_id, m.status, m.real_name, m.class_name, m.role, o.name as org_name
            FROM organization_members m
            JOIN organizations o ON m.org_id = o.id
            ORDER BY m.org_id, m.user_id
        """)
        members = c.fetchall()

    logger.info(f"Total organization memberships to evaluate: {len(members)}")

    updated_count = 0
    for m in members:
        org_id = m["org_id"]
        uid = m["user_id"]
        old_status = m["status"]

        status_info = LocalStore.check_org_member_status(org_id, uid)
        new_status = status_info.get("status")
        missing = status_info.get("missing_fields", [])

        if old_status != new_status:
            updated_count += 1
            missing_labels = [f.get("label", f.get("field")) for f in missing]
            logger.info(
                f"[{m['org_name']}] User {uid}: status changed '{old_status}' -> '{new_status}' "
                f"(missing: {', '.join(missing_labels) if missing_labels else 'none'})"
            )
        else:
            logger.info(f"[{m['org_name']}] User {uid}: status unchanged '{old_status}'")

    logger.info(f"Recalculation complete. {updated_count} membership statuses updated.")


if __name__ == "__main__":
    db_file = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    recalculate_statuses(db_file)
