"""
End-to-end tests for Assistant Coach Weekly Schedule Import & Multi-Group Batch Assignment:
1. Parsing Gobi 22 Pre-A Week 2 schedule (A/B/C/D/E 5 pace groups + E group custom distance + strength footnotes a/b/c + group run venues)
2. Parsing Shangma Week 2 & Week 3 schedules (Male/Female split + compound tempo/interval + duration-based LSD)
3. Batch assigning imported multi-group schedule to corresponding club members & persisting member training_group
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from utils.local_store import LocalStore

client = TestClient(app)


def test_import_presets_and_parse_gobi22_pre_a():
    # 1. Fetch presets
    r_pre = client.get("/api/coach/plan/import-presets")
    assert r_pre.status_code == 200
    presets = r_pre.json()["presets"]
    assert len(presets) >= 3

    # 2. Parse Gobi 22 Pre-A Week 2 schedule
    r_parse = client.post(
        "/api/coach/plan/import-weekly-schedule",
        json={"preset_id": "gobi22_pre_a_w2"},
    )
    assert r_parse.status_code == 200
    data = r_parse.json()
    assert data["success"] is True
    parsed = data["parsed_schedule"]
    assert "戈22预备A队" in parsed["plan_title"]
    assert parsed["source_week_index"] == 2
    assert parsed["grouping_mode"] == "pace_groups"

    groups = {g["group_code"]: g for g in parsed["groups"]}
    assert set(groups.keys()) == {"A组", "B组", "C组", "D组", "E组"}

    # Check A组 vs E组 distances & paces
    assert groups["A组"]["weekly_km"] == 86.0
    assert groups["E组"]["weekly_km"] == 76.0  # Tue 14km + Sat 16km

    tue_a = groups["A组"]["days"][1]
    tue_e = groups["E组"]["days"][1]
    assert tue_a["distance_km"] == 18.0
    assert tue_a["target_pace"] == "4:20-4:15/km"
    assert tue_e["distance_km"] == 14.0
    assert tue_e["target_pace"] == "6:00-5:50/km"

    # Check Wednesday strength footnote (a) merged into description
    wed_a = groups["A组"]["days"][2]
    assert wed_a["has_strength"] is True
    assert "垫步单腿提拉20次" in wed_a["description"]
    assert "每个练习间歇30秒" in wed_a["description"]


def test_parse_shangma_week3_compound_and_duration_lsd():
    r_parse = client.post(
        "/api/coach/plan/import-weekly-schedule",
        json={"preset_id": "shangma_w3"},
    )
    assert r_parse.status_code == 200
    parsed = r_parse.json()["parsed_schedule"]
    assert parsed["grouping_mode"] == "gender"
    groups = {g["group_code"]: g for g in parsed["groups"]}
    assert set(groups.keys()) == {"男组", "女组"}

    # Tuesday compound session: 节奏跑16km + 间歇跑1200米×5
    tue_m = groups["男组"]["days"][1]
    tue_f = groups["女组"]["days"][1]
    assert tue_m["workout_type"] == "interval"
    assert "4:00-3:55-3:50/km" in tue_m["target_pace"]
    assert "3:35/km" in tue_m["target_pace"]
    assert "4:35-4:30-4:25/km" in tue_f["target_pace"]
    assert "4:15/km" in tue_f["target_pace"]

    # Sunday 120min LSD + strength(c)
    sun_m = groups["男组"]["days"][6]
    assert sun_m["workout_type"] == "long_run"
    assert sun_m["distance_km"] > 15.0
    assert "半蹲跳25次+直膝跳30次" in sun_m["description"]


def test_batch_assign_imported_week_and_persist_member_groups():
    from utils.local_store import init_db, DB_PATH
    import sqlite3
    init_db()
    club_id = "test_gobi_pre_a_club"
    coach_uid = "test_asst_coach_01"
    runner_a = "test_runner_gobi_a"
    runner_e = "test_runner_gobi_e"

    # Ensure profiles & club exist
    LocalStore.upsert_profile(coach_uid, {"display_name": "预A助教", "gender": "男"})
    LocalStore.upsert_profile(runner_a, {"display_name": "队员甲(A组)", "gender": "男", "marathon_pb": "2:58:00"})
    LocalStore.upsert_profile(runner_e, {"display_name": "队员乙(E组)", "gender": "女", "marathon_pb": "4:20:00"})

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO clubs (id, name, owner_id, invite_code, status) VALUES (?, ?, ?, ?, 'active')",
            (club_id, "复旦戈22预备A队", coach_uid, "GOBI22"),
        )
        cur.execute(
            "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status) VALUES (?, ?, ?, 'coach', 'active')",
            (f"{club_id}_{coach_uid}", club_id, coach_uid),
        )
        cur.execute(
            "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status) VALUES (?, ?, ?, 'member', 'active')",
            (f"{club_id}_{runner_a}", club_id, runner_a),
        )
        cur.execute(
            "INSERT OR REPLACE INTO club_memberships (id, club_id, user_id, role, status) VALUES (?, ?, ?, 'member', 'active')",
            (f"{club_id}_{runner_e}", club_id, runner_e),
        )
        conn.commit()

    # 1. Parse schedule with club_id
    r_parse = client.post(
        "/api/coach/plan/import-weekly-schedule",
        json={
            "preset_id": "gobi22_pre_a_w2",
            "club_id": club_id,
            "operator_uid": coach_uid,
        },
    )
    assert r_parse.status_code == 200
    parsed = r_parse.json()["parsed_schedule"]
    groups_map = {g["group_code"]: g for g in parsed["groups"]}

    # 2. Batch assign A组 to runner_a and E组 to runner_e for target_monday="2026-11-02"
    r_assign = client.post(
        "/api/coach/plan/batch-assign-imported-week",
        json={
            "club_id": club_id,
            "operator_uid": coach_uid,
            "plan_title": parsed["plan_title"],
            "source_week_index": 2,
            "target_monday": "2026-11-02",
            "coach_review_note": parsed["coach_review_note"],
            "as_draft": False,
            "save_as_templates": True,
            "group_assignments": [
                {
                    "group_code": "A组",
                    "group_name": "预备队 A组",
                    "days": groups_map["A组"]["days"],
                    "user_ids": [runner_a],
                },
                {
                    "group_code": "E组",
                    "group_name": "预备队 E组",
                    "days": groups_map["E组"]["days"],
                    "user_ids": [runner_e],
                },
            ],
        },
    )
    assert r_assign.status_code == 200
    assign_res = r_assign.json()
    assert assign_res["success"] is True
    assert assign_res["total_assigned_count"] == 2

    # 3. Verify runner_a got 86km plan and runner_e got 76km plan with exact dates 2026-11-02 ~ 2026-11-08
    plan_a = LocalStore.get_user_active_training_plan(runner_a)
    plan_e = LocalStore.get_user_active_training_plan(runner_e)
    assert plan_a is not None
    assert plan_e is not None
    wk_a = [w for w in plan_a["schedule_data"]["weeks"] if w["days"][0]["date"] == "2026-11-02"][0]
    wk_e = [w for w in plan_e["schedule_data"]["weeks"] if w["days"][0]["date"] == "2026-11-02"][0]
    assert wk_a["weekly_mileage_km"] == 86.0
    assert wk_e["weekly_mileage_km"] == 76.0
    assert wk_e["days"][1]["distance_km"] == 14.0
    assert wk_e["days"][1]["target_pace"] == "6:00-5:50/km"

    # 4. Verify training_group is persisted in club_memberships for next week's auto-matching
    r_parse_next = client.post(
        "/api/coach/plan/import-weekly-schedule",
        json={
            "preset_id": "gobi22_pre_a_w2",
            "club_id": club_id,
            "operator_uid": coach_uid,
        },
    )
    rec_map = r_parse_next.json()["recommended_member_mapping"]
    assert rec_map[runner_a] == "A组"
    assert rec_map[runner_e] == "E组"


def test_draft_isolation_and_batch_rollback():
    """
    Verify that:
    1) Dispatching with as_draft=True NEVER modifies an athlete's existing active plan in-place.
    2) Rolling back a draft batch removes the draft while keeping the active plan untouched.
    3) Dispatching with as_draft=False creates an automatic snapshot that can be rolled back in 1 click.
    """
    club_id = "test_gobi_pre_a_club"
    coach_uid = "test_asst_coach_01"
    runner_a = "test_runner_gobi_a"

    # Give runner_a a clean AI active plan first
    ai_plan = LocalStore.upsert_training_plan(
        {
            "user_id": runner_a,
            "title": "队员甲 · 上海马拉松 8周科学训练计划",
            "goal_type": "race_prep",
            "target_race_name": "上海马拉松",
            "target_time": "2:58:00",
            "weeks_count": 8,
            "days_per_week": 5,
            "overview_summary": "Canova 8周周期计划",
            "schedule_data": {
                "weeks": [
                    {
                        "week_index": 1,
                        "week_number": 1,
                        "theme": "Canova 基础期",
                        "weekly_mileage_km": 70.0,
                        "days": [
                            {
                                "day_of_week": "周一",
                                "date": "2026-11-02",
                                "workout_type": "easy_run",
                                "title": "AI原计划轻松跑 10km",
                                "distance_km": 10.0,
                                "target_pace": "4:55/km",
                                "completed": True,
                                "actual_distance_km": 10.2,
                            }
                        ],
                    }
                ]
            },
            "status": "active",
            "review_status": "self_active",
        }
    )
    assert ai_plan["title"] == "队员甲 · 上海马拉松 8周科学训练计划"

    r_parse = client.post(
        "/api/coach/plan/import-weekly-schedule",
        json={"preset_id": "shangma_w2", "club_id": club_id, "operator_uid": coach_uid},
    )
    parsed = r_parse.json()["parsed_schedule"]
    male_days = [g for g in parsed["groups"] if g["group_code"] == "男组"][0]["days"]

    # 1. Dispatch as_draft=True -> Active AI plan must remain untouched!
    r_draft = client.post(
        "/api/coach/plan/batch-assign-imported-week",
        json={
            "club_id": club_id,
            "operator_uid": coach_uid,
            "plan_title": parsed["plan_title"],
            "source_week_index": 2,
            "target_monday": "2026-11-02",
            "coach_review_note": parsed["coach_review_note"],
            "as_draft": True,
            "save_as_templates": False,
            "group_assignments": [
                {
                    "group_code": "男组",
                    "group_name": "上马男组",
                    "days": male_days,
                    "user_ids": [runner_a],
                }
            ],
        },
    )
    assert r_draft.status_code == 200
    draft_batch_id = r_draft.json()["batch_id"]

    active_after_draft = LocalStore.get_user_active_training_plan(runner_a)
    draft_after_draft = LocalStore.get_user_draft_training_plan(runner_a)
    assert active_after_draft is not None
    assert active_after_draft["id"] == ai_plan["id"]
    assert active_after_draft["title"] == "队员甲 · 上海马拉松 8周科学训练计划"
    assert draft_after_draft is not None
    assert draft_after_draft["id"] != ai_plan["id"]
    assert "上马赛中赛周训练计划" in draft_after_draft["title"]

    # 2. Rollback the draft batch -> draft is removed, active AI plan still intact
    r_rb_draft = client.post(
        f"/api/coach/plan/club-batches/{draft_batch_id}/rollback",
        json={"operator_uid": coach_uid},
    )
    assert r_rb_draft.status_code == 200
    assert LocalStore.get_user_draft_training_plan(runner_a) is None
    assert LocalStore.get_user_active_training_plan(runner_a)["title"] == "队员甲 · 上海马拉松 8周科学训练计划"

    # 3. Dispatch as_draft=False (direct publish) -> updates active plan, then rollback restores AI plan!
    r_pub = client.post(
        "/api/coach/plan/batch-assign-imported-week",
        json={
            "club_id": club_id,
            "operator_uid": coach_uid,
            "plan_title": parsed["plan_title"],
            "source_week_index": 2,
            "target_monday": "2026-11-02",
            "coach_review_note": parsed["coach_review_note"],
            "as_draft": False,
            "save_as_templates": False,
            "group_assignments": [
                {
                    "group_code": "男组",
                    "group_name": "上马男组",
                    "days": male_days,
                    "user_ids": [runner_a],
                }
            ],
        },
    )
    assert r_pub.status_code == 200
    pub_batch_id = r_pub.json()["batch_id"]
    assert "上马赛中赛周训练计划" in LocalStore.get_user_active_training_plan(runner_a)["title"]

    # Rollback the published batch -> restores "队员甲 · 上海马拉松 8周科学训练计划"!
    r_rb_pub = client.post(
        f"/api/coach/plan/club-batches/{pub_batch_id}/rollback",
        json={"operator_uid": coach_uid},
    )
    assert r_rb_pub.status_code == 200
    restored_active = LocalStore.get_user_active_training_plan(runner_a)
    assert restored_active["title"] == "队员甲 · 上海马拉松 8周科学训练计划"
    assert restored_active["schedule_data"]["weeks"][0]["days"][0]["title"] == "AI原计划轻松跑 10km"
    assert restored_active["schedule_data"]["weeks"][0]["days"][0]["completed"] is True

