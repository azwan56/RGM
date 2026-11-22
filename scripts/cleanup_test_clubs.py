#!/usr/bin/env python3
"""
cleanup_test_clubs.py
Parameter-driven cleanup of auto-generated test clubs and organizations while preserving
all user profiles, activities, and explicitly supplied keep-lists.

Usage:
    python3 scripts/cleanup_test_clubs.py [--db-path backend/data/rgm.db] [--core-json /secure/core_users.json]
"""

import argparse
import json
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

from utils.encryption import encrypt_pii
from utils.local_store import DB_PATH, LocalStore, db_connect

PRESERVED_CLUBS = ("club_rgm_flagship", "club_fudan_gobi_main")
PRESERVED_ORG = "org_fudan_gobi"


def run_cleanup(db_path: str, core_users: list):
    print(f"Connecting to database at {db_path}...")
    now_iso = datetime.utcnow().isoformat() + "Z"

    with db_connect(db_path) as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM profiles")
        profiles_before = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM activities")
        activities_before = c.fetchone()[0]

        c.execute("DELETE FROM clubs WHERE id NOT IN ('club_rgm_flagship', 'club_fudan_gobi_main')")
        c.execute("DELETE FROM organizations WHERE id != ?", (PRESERVED_ORG,))
        c.execute("DELETE FROM club_memberships WHERE club_id NOT IN ('club_rgm_flagship', 'club_fudan_gobi_main')")
        c.execute("DELETE FROM organization_members WHERE org_id != ?", (PRESERVED_ORG,))
        c.execute("DELETE FROM club_events WHERE club_id NOT IN ('club_rgm_flagship', 'club_fudan_gobi_main')")
        c.execute("DELETE FROM coach_assignments WHERE club_id NOT IN ('club_rgm_flagship', 'club_fudan_gobi_main')")
        c.execute(
            "UPDATE training_plans SET club_id = NULL WHERE club_id IS NOT NULL AND club_id NOT IN ('club_rgm_flagship', 'club_fudan_gobi_main')"
        )

        if core_users:
            core_uids = tuple(u["uid"] for u in core_users)
            placeholders = ",".join("?" for _ in core_uids)
            c.execute(
                f"DELETE FROM organization_members WHERE org_id = ? AND user_id NOT IN ({placeholders})",
                (PRESERVED_ORG,) + core_uids,
            )
            for u in core_users:
                uid = u["uid"]
                c.execute("SELECT id, phone FROM profiles WHERE id = ?", (uid,))
                p_row = c.fetchone()
                if not p_row:
                    continue
                existing_phone = p_row[1] or ""
                enc_rname = encrypt_pii(u.get("real_name") or "")
                enc_dob = encrypt_pii(u.get("date_of_birth") or "")
                extra_str = json.dumps(u.get("extra") or {}, ensure_ascii=False)
                role = u.get("role") or "member"
                c.execute(
                    """
                    INSERT OR REPLACE INTO organization_members (
                        id, org_id, user_id, real_name, gender, date_of_birth, class_name,
                        phone, role, status, joined_at, confirmed_at, confirmed_by, extra_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, ?, 'system', ?)
                    """,
                    (
                        f"{PRESERVED_ORG}_{uid}",
                        PRESERVED_ORG,
                        uid,
                        enc_rname,
                        u.get("gender") or "male",
                        enc_dob,
                        u.get("class_name") or "",
                        existing_phone,
                        role,
                        now_iso,
                        now_iso,
                        extra_str,
                    ),
                )
                for cid in PRESERVED_CLUBS:
                    c.execute(
                        """
                        INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                        VALUES (?, ?, ?, ?, 'active', ?, 1)
                        """,
                        (f"{cid}_{uid}", cid, uid, role, now_iso),
                    )
        conn.commit()

        c.execute("SELECT COUNT(*) FROM profiles")
        profiles_after = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM activities")
        activities_after = c.fetchone()[0]
        assert profiles_before == profiles_after, "Profiles count mismatch"
        assert activities_before == activities_after, "Activities count mismatch"

    purge_res = LocalStore.remove_expired_org_members_from_sub_clubs(PRESERVED_ORG)
    print(f"Purge expired sub-club members result: {purge_res}")
    print("Cleanup complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up test clubs and orgs safely")
    parser.add_argument("--db-path", default=DB_PATH, help="Target SQLite DB path")
    parser.add_argument("--core-json", default="", help="Optional untracked JSON file of core users to confirm")
    args = parser.parse_args()
    users = []
    if args.core_json and os.path.exists(args.core_json):
        with open(args.core_json, "r", encoding="utf-8") as f:
            users = json.load(f)
    run_cleanup(args.db_path, users)
