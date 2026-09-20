#!/usr/bin/env python3
"""
cleanup_test_clubs.py
Performs cleanup of auto-generated test clubs and organizations while safely
preserving:
1. All profiles (user accounts, avatars, metrics, personal info)
2. All activities (workouts, GPS tracks, cadence, heart rate, TRIMP)
3. 'RGM先锋跑团' (club_rgm_flagship)
4. '复旦戈闵文跑团' (club_fudan_gobi_main)
5. '复旦戈' (org_fudan_gobi)
6. Memberships for Alex, Vivian Chen (晓韵), SUN JIN (Jin SUN) in both clubs and 复旦戈.
"""

import sys
import sqlite3
from datetime import datetime

def run_cleanup(db_path: str):
    print(f"Connecting to database at {db_path}...")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Pre-checks
    c.execute("SELECT COUNT(*) FROM profiles")
    profiles_before = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM activities")
    activities_before = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM clubs")
    clubs_before = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM organizations")
    orgs_before = c.fetchone()[0]

    print(f"Before cleanup: {profiles_before} profiles, {activities_before} activities, {clubs_before} clubs, {orgs_before} orgs.")

    now_iso = datetime.utcnow().isoformat() + "Z"

    # Start transaction
    with conn:
        # 1. Update/Ensure 'RGM先锋跑团' (club_rgm_flagship)
        c.execute("SELECT COUNT(*) FROM clubs WHERE id = 'club_rgm_flagship'")
        if c.fetchone()[0] == 0:
            c.execute("""
                INSERT INTO clubs (id, name, logo_url, description, city, invite_code, owner_id, created_at, org_id, join_mode, status)
                VALUES ('club_rgm_flagship', 'RGM先锋跑团', 
                        'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80',
                        '基于科学耐力训练与 Renato Canova 哲学的精英跑者联盟，追求 PB 突破与健康长久奔跑。',
                        '上海', 'RGM888', 'u_df65d9a588c9', ?, NULL, 'free', 'active')
            """, (now_iso,))
        else:
            c.execute("""
                UPDATE clubs
                SET name = 'RGM先锋跑团',
                    description = '基于科学耐力训练与 Renato Canova 哲学的精英跑者联盟，追求 PB 突破与健康长久奔跑。',
                    org_id = NULL,
                    status = 'active',
                    join_mode = 'free'
                WHERE id = 'club_rgm_flagship'
            """)

        # 2. Update/Ensure 'org_fudan_gobi'
        c.execute("SELECT COUNT(*) FROM organizations WHERE id = 'org_fudan_gobi'")
        if c.fetchone()[0] == 0:
            c.execute("""
                INSERT INTO organizations (id, name, logo_url, description, city, invite_code, owner_id, created_at)
                VALUES ('org_fudan_gobi', '复旦戈',
                        'https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=300&auto=format&fit=crop&q=80',
                        '复旦大学戈壁挑战赛大群体 · 汇聚商学院EMBA/MBA及泛复旦戈友，下设各个戈友跑团与训练营。',
                        '上海', 'FDGOBI', 'u_df65d9a588c9', ?)
            """, (now_iso,))
        else:
            c.execute("""
                UPDATE organizations
                SET name = '复旦戈',
                    invite_code = 'FDGOBI'
                WHERE id = 'org_fudan_gobi'
            """)

        # 3. Update/Ensure '复旦戈闵文跑团' (club_fudan_gobi_main)
        c.execute("SELECT COUNT(*) FROM clubs WHERE id = 'club_fudan_gobi_main'")
        if c.fetchone()[0] == 0:
            c.execute("""
                INSERT INTO clubs (id, name, logo_url, description, city, invite_code, owner_id, org_id, join_mode, status, created_at)
                VALUES ('club_fudan_gobi_main', '复旦戈闵文跑团',
                        'https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=300&auto=format&fit=crop&q=80',
                        '复旦戈闵文跑团 · 汇聚复旦戈友与闵文精英跑者，定期开展长距离拉练与马拉松科学耐力备战。',
                        '上海', 'FD8888', 'u_df65d9a588c9', 'org_fudan_gobi', 'free', 'active', ?)
            """, (now_iso,))
        else:
            c.execute("""
                UPDATE clubs
                SET name = '复旦戈闵文跑团',
                    description = '复旦戈闵文跑团 · 汇聚复旦戈友与闵文精英跑者，定期开展长距离拉练与马拉松科学耐力备战。',
                    org_id = 'org_fudan_gobi',
                    status = 'active',
                    join_mode = 'free'
                WHERE id = 'club_fudan_gobi_main'
            """)

        # 4. Remove all test clubs except the two preserved clubs
        c.execute("DELETE FROM clubs WHERE id NOT IN ('club_rgm_flagship', 'club_fudan_gobi_main')")

        # 5. Remove all test organizations except 'org_fudan_gobi'
        c.execute("DELETE FROM organizations WHERE id != 'org_fudan_gobi'")

        # 6. Clean club_memberships for removed clubs
        c.execute("DELETE FROM club_memberships WHERE club_id NOT IN ('club_rgm_flagship', 'club_fudan_gobi_main')")

        # 7. Clean organization_members for removed orgs
        c.execute("DELETE FROM organization_members WHERE org_id != 'org_fudan_gobi'")

        # 8. Clean club_events and coach_assignments for removed clubs
        c.execute("DELETE FROM club_events WHERE club_id NOT IN ('club_rgm_flagship', 'club_fudan_gobi_main')")
        c.execute("DELETE FROM coach_assignments WHERE club_id NOT IN ('club_rgm_flagship', 'club_fudan_gobi_main')")

        # 9. Clean training_plans club_id foreign key
        c.execute("UPDATE training_plans SET club_id = NULL WHERE club_id IS NOT NULL AND club_id NOT IN ('club_rgm_flagship', 'club_fudan_gobi_main')")

        # 10. Ensure core runner memberships in 'club_rgm_flagship'
        core_users = [
            ("u_df65d9a588c9", "owner"),
            ("Vivian Chen", "member"),
            ("SUN JIN", "member")
        ]
        for uid, role in core_users:
            c.execute("SELECT id FROM profiles WHERE id = ?", (uid,))
            if c.fetchone():
                c.execute("""
                    INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                    VALUES (?, 'club_rgm_flagship', ?, ?, 'active', ?, 1)
                """, (f"club_rgm_flagship_{uid}", uid, role, now_iso))

        # 11. Ensure core runner memberships in 'club_fudan_gobi_main'
        for uid, role in core_users:
            c.execute("SELECT id FROM profiles WHERE id = ?", (uid,))
            if c.fetchone():
                c.execute("""
                    INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status, joined_at, privacy_consent)
                    VALUES (?, 'club_fudan_gobi_main', ?, ?, 'active', ?, 1)
                """, (f"club_fudan_gobi_main_{uid}", uid, role, now_iso))

        # 12. Ensure core runner memberships in 'org_fudan_gobi'
        for uid, role in core_users:
            c.execute("SELECT id, display_name, gender, date_of_birth, real_name, phone, class_name FROM profiles WHERE id = ?", (uid,))
            p_row = c.fetchone()
            if p_row:
                p_id, p_disp, p_gender, p_dob, p_rname, p_phone, p_cname = p_row
                # Check if member already in org_fudan_gobi
                c.execute("SELECT id FROM organization_members WHERE org_id = 'org_fudan_gobi' AND user_id = ?", (uid,))
                m_exists = c.fetchone()
                if not m_exists:
                    c.execute("""
                        INSERT INTO organization_members (id, org_id, user_id, real_name, gender, date_of_birth, class_name, phone, role, status, joined_at, confirmed_at, confirmed_by)
                        VALUES (?, 'org_fudan_gobi', ?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, ?, 'u_df65d9a588c9')
                    """, (f"org_fudan_gobi_{uid}", uid, p_rname or p_disp, p_gender or 'male', p_dob or '1985-01-01', p_cname or '复旦戈友', p_phone or '', role, now_iso, now_iso))

    # Post-checks
    c.execute("SELECT COUNT(*) FROM profiles")
    profiles_after = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM activities")
    activities_after = c.fetchone()[0]
    c.execute("SELECT id, name, org_id, (SELECT COUNT(*) FROM club_memberships WHERE club_id = clubs.id) FROM clubs")
    clubs_after = c.fetchall()
    c.execute("SELECT id, name, (SELECT COUNT(*) FROM organization_members WHERE org_id = organizations.id) FROM organizations")
    orgs_after = c.fetchall()

    print("\n--- Cleanup Verification Report ---")
    print(f"Profiles: Before={profiles_before}, After={profiles_after} (Difference: {profiles_after - profiles_before})")
    print(f"Activities: Before={activities_before}, After={activities_after} (Difference: {activities_after - activities_before})")
    print(f"Remaining Clubs ({len(clubs_after)}):")
    for cl in clubs_after:
        print(f"  - [{cl[0]}] {cl[1]} (org_id: {cl[2]}, members: {cl[3]})")
    print(f"Remaining Organizations ({len(orgs_after)}):")
    for og in orgs_after:
        print(f"  - [{og[0]}] {og[1]} (members: {og[2]})")

    assert profiles_before == profiles_after, "Error: Profiles count changed!"
    assert activities_before == activities_after, "Error: Activities count changed!"
    assert len(clubs_after) == 2, f"Expected exactly 2 clubs, got {len(clubs_after)}"
    assert len(orgs_after) == 1, f"Expected exactly 1 organization, got {len(orgs_after)}"
    print("\nSUCCESS: All data integrity checks passed!")

if __name__ == "__main__":
    db_file = sys.argv[1] if len(sys.argv) > 1 else "backend/data/rgm.db"
    run_cleanup(db_file)
