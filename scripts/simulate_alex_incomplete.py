import sqlite3
import json
import os
import sys

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "backend/data/rgm.db"

def simulate_incomplete():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM organization_members WHERE user_id = 'u_df65d9a588c9' AND org_id = 'org_fudan_gobi'")
        row = cursor.fetchone()
        if not row:
            print("Alex not found in organization_members")
            return

        cols = [desc[0] for desc in cursor.description]
        data = dict(zip(cols, row))
        print("Current Alex data:", data.get("status"), data.get("class_name"))

        extra = {}
        if data.get("extra_data"):
            try:
                extra = json.loads(data["extra_data"])
            except Exception:
                extra = {}

        # Remove gobi_experience and clear class_name
        extra.pop("gobi_experience", None)
        extra.pop("program", None)
        extra.pop("class_detail", None)

        cursor.execute("""
            UPDATE organization_members
            SET class_name = '',
                status = 'temporary',
                confirmed_at = NULL,
                confirmed_by = NULL,
                extra_data = ?
            WHERE user_id = 'u_df65d9a588c9' AND org_id = 'org_fudan_gobi'
        """, (json.dumps(extra, ensure_ascii=False),))
        conn.commit()
        print("Successfully simulated Alex as INCOMPLETE member!")

if __name__ == "__main__":
    simulate_incomplete()
