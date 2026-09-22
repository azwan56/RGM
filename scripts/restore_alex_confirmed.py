import sqlite3
import json
import os
import sys

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "backend/data/rgm.db"

def restore_confirmed():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM organization_members WHERE user_id = 'u_df65d9a588c9' AND org_id = 'org_fudan_gobi'")
        row = cursor.fetchone()
        if not row:
            print("Alex not found in organization_members")
            return

        cols = [desc[0] for desc in cursor.description]
        data = dict(zip(cols, row))

        extra = {}
        if data.get("extra_data"):
            try:
                extra = json.loads(data["extra_data"])
            except Exception:
                extra = {}

        extra["program"] = "复旦-BI（挪威）"
        extra["class_detail"] = "10班"
        extra["gobi_experience"] = "戈11 A组"
        extra["clothing_size"] = "XL"
        extra["shoe_size"] = "44"
        extra["health_declaration"] = True

        cursor.execute("""
            UPDATE organization_members
            SET class_name = '复旦-BI（挪威） 10班',
                status = 'confirmed',
                confirmed_at = '2026-09-20T01:41:27.499970Z',
                confirmed_by = 'u_df65d9a588c9',
                extra_data = ?
            WHERE user_id = 'u_df65d9a588c9' AND org_id = 'org_fudan_gobi'
        """, (json.dumps(extra, ensure_ascii=False),))
        conn.commit()
        print("Successfully RESTORED Alex as confirmed member!")

if __name__ == "__main__":
    restore_confirmed()
