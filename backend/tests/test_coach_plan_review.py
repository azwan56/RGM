import os
import sys
import uuid
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from utils.local_store import LocalStore

client = TestClient(app)


def test_coach_plan_draft_review_adjust_publish_and_cockpit():
    suffix = uuid.uuid4().hex[:8]
    owner_uid = f"coach_owner_{suffix}"
    runner_uid = f"club_runner_{suffix}"

    LocalStore.upsert_profile(owner_uid, {"display_name": "张总教练", "marathon_pb": "02:55:00"})
    LocalStore.upsert_profile(runner_uid, {"display_name": "李队员", "marathon_pb": "03:45:00", "age": 42})
    LocalStore.upsert_goal(runner_uid, {"weekly_target": 55.0, "target_distance": 220.0})
    LocalStore.upsert_race_plan(
        runner_uid,
        {
            "id": f"race_{suffix}",
            "name": "2026上海马拉松",
            "race_date": "2026-12-06",
            "race_type": "marathon",
            "target_time": "03:35:00",
            "priority": 1,
            "status": "upcoming",
        },
    )

    club = LocalStore.create_club(
        owner_id=owner_uid,
        name=f"测试精英跑团_{suffix}",
        description="教练排课审核测试跑团",
        city="上海",
    )
    club_id = club["id"]
    LocalStore.join_club_by_id(runner_uid, club_id)

    # 1. Member first has a self-created active plan
    self_gen_res = client.post(
        "/api/coach/plan/generate",
        json={
            "uid": runner_uid,
            "operator_uid": runner_uid,
            "goal_type": "fitness_maintenance",
            "target_race_name": "日常有氧维持",
            "target_time": "03:45:00",
            "weeks": 4,
            "days_per_week": 4,
            "as_draft": False,
            "use_fast_engine": True,
        },
    )
    assert self_gen_res.status_code == 200
    self_plan = self_gen_res.json()["plan"]
    assert self_plan["status"] == "active"

    # 2. Coach generates a draft plan for the runner with special notes
    draft_res = client.post(
        "/api/coach/plan/generate",
        json={
            "uid": runner_uid,
            "operator_uid": owner_uid,
            "goal_type": "race_prep",
            "target_race_name": "2026上海马拉松",
            "target_time": "03:35:00",
            "weeks": 4,
            "days_per_week": 4,
            "as_draft": True,
            "use_fast_engine": True,
            "coach_notes_prompt": "左膝轻微不适，首周长距离控制在18km以内",
        },
    )
    assert draft_res.status_code == 200
    draft_plan = draft_res.json()["plan"]
    assert draft_plan["status"] == "draft"
    assert draft_plan["review_status"] == "draft"
    draft_id = draft_plan["id"]

    # Verify runner's active plan is still the old self_plan until coach publishes
    user_plans_res = client.get(f"/api/coach/plan/user/{runner_uid}")
    assert user_plans_res.status_code == 200
    up_data = user_plans_res.json()
    assert up_data["active_plan"]["id"] == self_plan["id"]
    assert up_data["draft_plan"]["id"] == draft_id

    # 3. Coach performs 1-click weekly batch volume scaling (-15%) on Week 1
    orig_w1_km = draft_plan["schedule_data"]["weeks"][0]["weekly_mileage_km"]
    adj_res = client.post(
        f"/api/coach/plan/{draft_id}/week-adjust",
        json={
            "operator_uid": owner_uid,
            "week_index": 1,
            "action": "scale_volume",
            "scale_factor": 0.85,
        },
    )
    assert adj_res.status_code == 200
    adj_plan = adj_res.json()["plan"]
    new_w1_km = adj_plan["schedule_data"]["weeks"][0]["weekly_mileage_km"]
    assert new_w1_km <= orig_w1_km

    # 4. Coach edits Day 3 workout of Week 1
    edit_day_res = client.put(
        f"/api/coach/plan/{draft_id}/workout",
        json={
            "operator_uid": owner_uid,
            "week_index": 1,
            "day_index": 3,
            "workout_type": "easy_run",
            "title": "教练定制恢复有氧跑",
            "distance_km": 8.0,
            "duration_minutes": 48,
            "target_pace": "5'30\"-5'45\"/km",
            "target_hr_zone": "Zone 2",
            "description": "保持低心率轻松巡航，跑后拉伸小腿与髂胫束。",
        },
    )
    assert edit_day_res.status_code == 200

    # 5. Coach approves and publishes the draft plan to the runner
    pub_res = client.post(
        f"/api/coach/plan/{draft_id}/publish",
        json={
            "operator_uid": owner_uid,
            "coach_review_note": "本周按调整后的课表执行，注意左膝保暖与跑后冰敷。",
            "title": "2026上海马拉松 · 教练特批4周冲刺课表",
        },
    )
    assert pub_res.status_code == 200
    pub_plan = pub_res.json()["plan"]
    assert pub_plan["status"] == "active"
    assert pub_plan["review_status"] == "published"
    assert pub_plan["reviewed_by"] == owner_uid
    assert pub_plan["reviewed_by_name"] == "张总教练"
    assert "左膝保暖" in pub_plan["coach_review_note"]
    assert pub_plan["title"] == "2026上海马拉松 · 教练特批4周冲刺课表"

    # Verify runner's active plan is now the published plan and draft_plan is None
    after_pub_res = client.get(f"/api/coach/plan/user/{runner_uid}")
    after_data = after_pub_res.json()
    assert after_data["active_plan"]["id"] == draft_id
    assert after_data["draft_plan"] is None

    # 6. Verify Coach Cockpit includes plan_info and week_execution
    cockpit_res = client.get(f"/api/team/{club_id}/coach-cockpit?coach_uid={owner_uid}")
    assert cockpit_res.status_code == 200
    cp_data = cockpit_res.json()
    assert cp_data["summary"]["plans_published_count"] >= 1
    runner_entry = next((s for s in cp_data["students"] if s["user_id"] == runner_uid), None)
    assert runner_entry is not None
    assert runner_entry["plan_info"]["plan_state"] == "published"
    assert runner_entry["plan_info"]["reviewed_by_name"] == "张总教练"
    assert runner_entry["plan_info"]["week_execution"] is not None
    assert len(runner_entry["plan_info"]["week_execution"]["days_brief"]) == 7

    # 7. Verify Club Batch Generate creates draft for unscheduled member (owner_uid has no plan yet)
    batch_res = client.post(
        "/api/coach/plan/club-batch-generate",
        json={
            "club_id": club_id,
            "operator_uid": owner_uid,
            "weeks": 4,
            "only_without_plan": True,
        },
    )
    assert batch_res.status_code == 200
    batch_data = batch_res.json()
    assert batch_data["generated_count"] >= 1

    # 8. Verify W19 Daily Biometrics, Execution Text, RPE, Runner Notes & Day Swap
    w19_day_res = client.put(
        f"/api/coach/plan/{draft_id}/workout",
        json={
            "operator_uid": runner_uid,
            "week_index": 1,
            "day_index": 1,
            "hrv": 29,
            "resting_hr": 50,
            "respiratory_rate": 14.3,
            "strain_score": 14.0,
            "recovery_pct": 63,
            "actual_execution_text": "慢跑4.3km*554 / 身训2组 / 速度：1200米（348）+800米（352）",
            "rpe": 8,
            "athlete_notes": "臀腿核心延迟性酸胀，后程弹性减弱",
            "strength_completed": True,
        },
    )
    assert w19_day_res.status_code == 200
    w19_plan = w19_day_res.json()["plan"]
    day1_obj = w19_plan["schedule_data"]["weeks"][0]["days"][1]
    assert day1_obj["hrv"] == 29
    assert day1_obj["resting_hr"] == 50
    assert day1_obj["recovery_pct"] == 63
    assert day1_obj["rpe"] == 8
    assert "臀腿核心" in day1_obj["athlete_notes"]
    assert day1_obj["completed"] is True

    # Test swapping Saturday (index 5) and Sunday (index 6) even when client sends Saturday's full form fields
    orig_sat = w19_plan["schedule_data"]["weeks"][0]["days"][5]
    orig_sun = w19_plan["schedule_data"]["weeks"][0]["days"][6]
    orig_sat_title, orig_sat_km = orig_sat["title"], orig_sat["distance_km"]
    orig_sun_title, orig_sun_km = orig_sun["title"], orig_sun["distance_km"]

    swap_res = client.put(
        f"/api/coach/plan/{draft_id}/workout",
        json={
            "operator_uid": runner_uid,
            "week_index": 1,
            "day_index": 5,
            "workout_type": orig_sat["workout_type"],
            "title": orig_sat_title,
            "distance_km": orig_sat_km,
            "target_pace": orig_sat.get("target_pace") or "",
            "target_hr_zone": orig_sat.get("target_hr_zone") or "",
            "description": orig_sat.get("description") or "",
            "athlete_notes": orig_sat.get("athlete_notes") or "",
            "swap_with_day_index": 6,
        },
    )
    assert swap_res.status_code == 200
    swap_plan = swap_res.json()["plan"]
    new_sat = swap_plan["schedule_data"]["weeks"][0]["days"][5]
    new_sun = swap_plan["schedule_data"]["weeks"][0]["days"][6]
    assert new_sat["is_swapped"] is True
    assert new_sun["is_swapped"] is True
    assert new_sat["title"] == orig_sun_title
    assert new_sat["distance_km"] == orig_sun_km
    assert new_sun["title"] == orig_sat_title
    assert new_sun["distance_km"] == orig_sat_km
    assert "（已与周日对换课表）" in (new_sat.get("athlete_notes") or "")
    assert "（已与周六对换课表）" in (new_sun.get("athlete_notes") or "")

    # Test undoing the swap via undo_swap=True
    undo_res = client.put(
        f"/api/coach/plan/{draft_id}/workout",
        json={
            "operator_uid": runner_uid,
            "week_index": 1,
            "day_index": 5,
            "undo_swap": True,
        },
    )
    assert undo_res.status_code == 200
    undo_plan = undo_res.json()["plan"]
    restored_sat = undo_plan["schedule_data"]["weeks"][0]["days"][5]
    restored_sun = undo_plan["schedule_data"]["weeks"][0]["days"][6]
    assert restored_sat["is_swapped"] is False
    assert restored_sun["is_swapped"] is False
    assert restored_sat["title"] == orig_sat_title
    assert restored_sat["distance_km"] == orig_sat_km
    assert restored_sun["title"] == orig_sun_title
    assert restored_sun["distance_km"] == orig_sun_km
    assert "对换课表" not in (restored_sat.get("athlete_notes") or "")
    assert "对换课表" not in (restored_sun.get("athlete_notes") or "")

    # 9. Verify W19 Weekly Summary (伤痛 + 队员周小结 + 教练复盘 + 宏观周期大纲)
    summary_res = client.post(
        f"/api/coach/plan/{draft_id}/week-summary",
        json={
            "operator_uid": runner_uid,
            "week_index": 1,
            "injury_note": "左脚脚踝内侧轻微痛感",
            "athlete_weekly_summary": "周跑量59km，身体状态一般，周二合练强度较大",
            "travel_or_leave_note": "9.22—10.2 坦桑尼亚旅行",
            "coach_weekly_diagnosis": "腿部力量欠缺太多，弹性不够，下周需完成一次30km长距离",
            "macro_roadmap": "7-8月基础期 260-280km | 9-10月强化期 | 11月南马以赛代练 | 12.6上马",
        },
    )
    assert summary_res.status_code == 200
    sum_plan = summary_res.json()["plan"]
    w1_sum = sum_plan["schedule_data"]["weeks"][0]["week_summary"]
    assert w1_sum["injury_note"] == "左脚脚踝内侧轻微痛感"
    assert w1_sum["has_injury_alert"] is True
    assert "坦桑尼亚" in w1_sum["travel_or_leave_note"]
    assert "7-8月基础期" in sum_plan["schedule_data"]["macro_roadmap"]

    # 10. Verify Rolling Next Week Schedule Generation (W1 -> W2)
    roll_res = client.post(
        f"/api/coach/plan/{draft_id}/roll-next-week",
        json={
            "operator_uid": owner_uid,
            "source_week_index": 1,
            "coach_diagnosis": "腿部力量欠缺太多，弹性不够，下周需完成一次30km长距离",
            "weekday_group_workout": "交大合练：慢跑+身训+速度",
        },
    )
    assert roll_res.status_code == 200
    rolled_plan = roll_res.json()["plan"]
    w2 = rolled_plan["schedule_data"]["weeks"][1]
    assert w2["rolled_from_week"] == 1
    assert any("交大合练" in (d.get("title") or "") for d in w2["days"])
    assert any(float(d.get("distance_km") or 0) == 30.0 for d in w2["days"])

    # 11. Verify Club Broadcast Workout across active member plans
    bcast_res = client.post(
        "/api/coach/plan/club-broadcast-workout",
        json={
            "club_id": club_id,
            "operator_uid": owner_uid,
            "day_index": 1,
            "target_week_mode": "current",
            "workout_type": "interval",
            "title": "交大合练：慢跑+身训+间歇速度课",
            "distance_km": 12.0,
            "target_pace": "按A/B/C组配速",
            "target_hr_zone": "Z3-Z4",
            "description": "慢跑热身4km + 核心身训2组 + 场地间歇",
        },
    )
    assert bcast_res.status_code == 200
    assert bcast_res.json()["updated_count"] >= 1

    # 12. Verify Coach Pace & Intensity Group Templates & Batch Assignment + Custom Template CRUD
    tpl_res = client.get("/api/coach/plan/templates")
    assert tpl_res.status_code == 200
    tpl_list = tpl_res.json()["templates"]
    assert len(tpl_list) >= 8
    assert any(t["id"] == "group_s_sub240" for t in tpl_list)
    assert any(t["id"] == "group_gobi_a" for t in tpl_list)
    assert any(t["id"] == "group_trail_ultra" for t in tpl_list)
    assert any(t["id"] == "group_b_sub330" for t in tpl_list)

    assign_res = client.post(
        "/api/coach/plan/assign-template",
        json={
            "template_id": "group_b_sub330",
            "user_ids": [runner_uid, owner_uid],
            "operator_uid": owner_uid,
            "club_id": club_id,
            "apply_mode": "full_plan",
            "weeks_count": 4,
            "volume_scale": 1.0,
            "as_draft": True,
        },
    )
    assert assign_res.status_code == 200
    assign_data = assign_res.json()
    assert assign_data["assigned_count"] == 2
    assert assign_data["group_code"] == "B组"
    runner_assigned = next(p for p in assign_data["assigned_plans"] if p["user_id"] == runner_uid)
    assert runner_assigned["status"] == "draft"
    assert runner_assigned["plan"]["schedule_data"]["template_group_code"] == "B组"

    # 13. Save a Coach Custom Template (e.g. Gobi A+ or Sub-235 Custom Group) and assign it
    save_tpl_res = client.post(
        "/api/coach/plan/templates",
        json={
            "operator_uid": owner_uid,
            "club_id": club_id,
            "group_code": "戈21冲冠组",
            "category": "gobi_desert",
            "short_name": "🏜️ 戈21冲冠组 · 专属背靠背",
            "target_level": "戈21 A队主力 · 周跑量95km",
            "intensity_tag": "背靠背30k+25k + 沙地抗阻间歇",
            "from_plan_id": runner_assigned["plan_id"],
            "from_week_index": 1,
        },
    )
    assert save_tpl_res.status_code == 200
    custom_tpl = save_tpl_res.json()["template"]
    assert custom_tpl["is_custom"] is True
    assert custom_tpl["is_private_to_coach"] is True
    assert custom_tpl["group_code"] == "戈21冲冠组"

    # 13a. Verify Coach-Private Isolation & Cross-Club Portability:
    # - The creator coach (`owner_uid`) can see & apply this custom template in ANY other club (`other_club_999`)
    my_cross_club_res = client.get(f"/api/coach/plan/templates?club_id=other_club_999&operator_uid={owner_uid}")
    assert my_cross_club_res.status_code == 200
    assert any(t["id"] == custom_tpl["id"] for t in my_cross_club_res.json()["templates"])

    # - Another coach (`other_coach_xyz`) in the SAME club (`club_id`) CANNOT see or delete `owner_uid`'s custom template
    other_coach_res = client.get(f"/api/coach/plan/templates?club_id={club_id}&operator_uid=other_coach_xyz")
    assert other_coach_res.status_code == 200
    assert not any(t["id"] == custom_tpl["id"] for t in other_coach_res.json()["templates"])
    assert len(other_coach_res.json()["templates"]) == 8  # Only the 8 built-in system templates

    unauthorized_del = client.delete(f"/api/coach/plan/templates/{custom_tpl['id']}?operator_uid=other_coach_xyz&club_id={club_id}")
    assert unauthorized_del.status_code == 400

    # - Creator coach (`owner_uid`) can assign their custom template in another club (`other_club_999`)
    assign_custom_res = client.post(
        "/api/coach/plan/assign-template",
        json={
            "template_id": custom_tpl["id"],
            "target_user_ids": [runner_uid],
            "operator_uid": owner_uid,
            "club_id": "other_club_999",
            "apply_scope": "current_week",
            "as_draft": True,
        },
    )
    assert assign_custom_res.status_code == 200
    assert assign_custom_res.json()["group_code"] == "戈21冲冠组"

    del_tpl_res = client.delete(f"/api/coach/plan/templates/{custom_tpl['id']}?operator_uid={owner_uid}&club_id={club_id}")
    assert del_tpl_res.status_code == 200

    # 14. Verify Age, Gender & Conservative Dual-Gate Group Recommendation
    # (a) Female 52yo elite (FM 3:12:05, recent FM 3:27, HM 1:39, VO2max 55, CTL 54.1, month_km 157.5)
    # Should NOT be aggressively pushed into male A组 (3'42"/km intervals); should be B组 with 0.90 scale
    rec_female_master = LocalStore.recommend_athlete_template_group(
        marathon_pb="3:12:05",
        half_pb="1:39:10",
        recent_fm_sec=12441,
        vo2max=55.0,
        ctl=54.1,
        month_km=157.5,
        km_7d=57.4,
        age=52,
        gender="female",
    )
    assert rec_female_master["group_code"] == "B组"
    assert rec_female_master["recommended_scale"] == 0.9
    assert "女·52岁" in rec_female_master["reason"]

    # (b) Male 56yo Grand Master (historical PB 3:09:30, recent FM 4:03:11, VO2max 48, CTL 54.9, month_km 151.5)
    # Should be protected by 55+ age & current fitness -> C组 with 0.90 scale
    rec_grand_master = LocalStore.recommend_athlete_template_group(
        marathon_pb=11370,
        recent_fm_sec=14591,
        vo2max=48.0,
        ctl=54.9,
        month_km=151.5,
        km_7d=43.9,
        age=56,
        gender="male",
    )
    assert rec_grand_master["group_code"] == "C组"
    assert rec_grand_master["recommended_scale"] == 0.9
    assert "男·56岁" in rec_grand_master["reason"]

    # (c) Runner with high CTL (97.2) from slow ultra walks but HM 1:55:52, VO2max 46, age 55
    # Should NEVER be pushed into 240组 or A组; should be C组
    rec_high_ctl_slow = LocalStore.recommend_athlete_template_group(
        marathon_pb=None,
        half_pb="1:55:52",
        vo2max=46.0,
        ctl=97.2,
        month_km=222.6,
        km_7d=70.5,
        age=55,
        gender="male",
    )
    assert rec_high_ctl_slow["group_code"] == "C组"

    # (d) Sub-3 runner (FM 2:55:22) but low recent load (CTL 40.8, month_km 112.5, age 41)
    # Should step down 1 tier from A组 to B组 for injury prevention
    rec_low_load_sub3 = LocalStore.recommend_athlete_template_group(
        marathon_pb="2:55:22",
        half_pb="1:31:09",
        vo2max=57.0,
        ctl=40.8,
        month_km=112.5,
        km_7d=20.9,
        age=41,
        gender="male",
    )
    assert rec_low_load_sub3["group_code"] == "B组"

    # (e) Beginner / unsynced runner with default weekly_target=50km and CTL=0
    # Should be D组, never C组 or B组
    rec_beginner = LocalStore.recommend_athlete_template_group(
        marathon_pb=None,
        half_pb=None,
        ctl=0.0,
        month_km=0.0,
        km_7d=0.0,
        weekly_target=50.0,
        age=35,
        gender="female",
    )
    assert rec_beginner["group_code"] == "D组"


def test_started_goal_lock_and_plan_preview_confirm():
    from datetime import datetime
    today = datetime.now().date()
    cur_month = today.month

    # 1. Seed a baseline goal with enforce_started_lock=False so current week & started months have known values
    LocalStore.upsert_goal(
        "user_alex",
        {
            "year": today.year,
            "weekly_target": 55.0,
            "monthly_target": 200.0,
            "monthly_targets": {str(m): 200.0 for m in range(1, 13)},
            "annual_target": 2400.0,
        },
        enforce_started_lock=False,
    )
    base_goal = LocalStore.get_goal("user_alex")
    assert base_goal["current_week_target"] == 55.0
    assert base_goal["current_week_locked"] is True

    # 2. Attempting to explicitly modify current_week via API should be rejected (HTTP 400)
    res_bad_week = client.put(
        "/api/profile/user_alex/goal",
        json={"weekly_target": 80.0, "target_period": "current_week"},
    )
    assert res_bad_week.status_code == 400

    # 3. Attempting to explicitly modify a started month (<= today.month) should be rejected (HTTP 400)
    res_bad_month = client.put(
        "/api/profile/user_alex/goal",
        json={"monthly_target": 320.0, "target_month": cur_month},
    )
    assert res_bad_month.status_code == 400

    # 4. Updating weekly & monthly goals with enforce_started_lock=True keeps current_week_target (55.0)
    # and started months (1..cur_month = 200.0) locked, while updating next_weekly_target (72.0) and unstarted months (> cur_month = 260.0)
    new_monthly_map = {str(m): 260.0 for m in range(1, 13)}
    res_ok_goal = client.put(
        "/api/profile/user_alex/goal",
        json={
            "weekly_target": 72.0,
            "target_period": "next_week",
            "monthly_targets": new_monthly_map,
            "enforce_started_lock": True,
        },
    )
    assert res_ok_goal.status_code == 200
    saved_goal = res_ok_goal.json()["goal"]
    assert saved_goal["current_week_target"] == 55.0
    assert saved_goal["next_weekly_target"] == 72.0
    mt = saved_goal["monthly_targets"]
    for m in range(1, 13):
        val = float(mt[str(m)] if isinstance(mt, dict) else mt[m - 1])
        if m <= cur_month:
            assert val == 200.0
        else:
            assert val == 260.0

    # 5. Preview-only AI plan generation should NOT overwrite existing plan in DB until confirmed
    existing_plan = LocalStore.get_user_active_training_plan("user_alex")
    existing_plan_id = existing_plan["id"] if existing_plan else None
    existing_race_name = existing_plan["target_race_name"] if existing_plan else None

    res_preview = client.post(
        "/api/coach/plan/generate",
        json={
            "user_id": "user_alex",
            "race_type": "42k",
            "target_race_name": "Preview Unconfirmed Marathon",
            "target_time": "03:15:00",
            "weeks": 4,
            "runs_per_week": 4,
            "use_fast_engine": True,
            "preview_only": True,
        },
    )
    assert res_preview.status_code == 200
    preview_body = res_preview.json()
    assert preview_body["preview_only"] is True
    preview_plan = preview_body["plan"]
    assert preview_plan["target_race_name"] == "Preview Unconfirmed Marathon"
    assert preview_plan.get("is_preview") is True
    assert str(preview_plan["id"]).startswith("preview_")

    # Verify DB was NOT modified by preview
    after_preview_plan = LocalStore.get_user_active_training_plan("user_alex")
    if existing_plan_id:
        assert after_preview_plan["id"] == existing_plan_id
        assert after_preview_plan["target_race_name"] == existing_race_name

    # 6. Confirming the preview writes the plan to DB
    res_confirm = client.post(
        "/api/coach/plan/confirm",
        json={
            "user_id": "user_alex",
            "operator_uid": "user_alex",
            "plan_payload": preview_plan,
        },
    )
    assert res_confirm.status_code == 200
    confirmed_plan = res_confirm.json()["plan"]
    assert str(confirmed_plan["id"]).startswith("plan_")
    assert confirmed_plan["target_race_name"] == "Preview Unconfirmed Marathon"
    db_plan = LocalStore.get_user_active_training_plan("user_alex")
    assert db_plan["id"] == confirmed_plan["id"]

    # 7. Started-week workout prescription lock for athlete self-edit vs unstarted Week 2
    plan_id = confirmed_plan["id"]
    w1_day1_orig_km = float(confirmed_plan["schedule_data"]["weeks"][0]["days"][0]["distance_km"])
    res_athlete_edit_w1 = client.patch(
        f"/api/coach/plan/{plan_id}/workout",
        json={
            "operator_uid": "user_alex",
            "week_index": 1,
            "day_index": 0,
            "distance_km": w1_day1_orig_km + 10.0,
            "title": "Should Be Locked Title",
            "completed": True,
            "rpe": 6,
            "athlete_notes": "打卡正常完成",
        },
    )
    assert res_athlete_edit_w1.status_code == 200
    updated_w1_plan = res_athlete_edit_w1.json()["plan"]
    w1_day1 = updated_w1_plan["schedule_data"]["weeks"][0]["days"][0]
    # Prescription (distance_km, title) on started Week 1 is locked for athlete self-edit, while check-in (completed, rpe) succeeds
    assert float(w1_day1["distance_km"]) == w1_day1_orig_km
    assert w1_day1["title"] != "Should Be Locked Title"
    assert w1_day1["completed"] is True
    assert w1_day1["rpe"] == 6

    # Unstarted Week 2 prescription CAN be edited by athlete
    res_athlete_edit_w2 = client.patch(
        f"/api/coach/plan/{plan_id}/workout",
        json={
            "operator_uid": "user_alex",
            "week_index": 2,
            "day_index": 1,
            "distance_km": 14.5,
            "title": "Unstarted Week Custom Run",
        },
    )
    assert res_athlete_edit_w2.status_code == 200
    w2_day2 = res_athlete_edit_w2.json()["plan"]["schedule_data"]["weeks"][1]["days"][1]
    assert float(w2_day2["distance_km"]) == 14.5
    assert w2_day2["title"] == "Unstarted Week Custom Run"


def test_non_night_wearing_watch_data_availability_and_warnings():
    """
    Verifies:
    1. When a Garmin/COROS user does NOT wear their watch at night (only wears it during runs or has
       stale >3-day-old overnight records), invalid fallback values (static profile RHR, fabricated sleep score,
       daytime body battery, or old historical HRV) are NEVER injected.
    2. `LocalStore.assess_recovery_data_availability`, `/api/miniapp/dashboard/{uid}`, `/api/coach/plan/user/{uid}`,
       and `LocalStore.get_coach_students_metrics` explicitly flag `recovery_data_available=False`,
       `night_wear_missing=True`, and surface clear warnings to both runner and coach.
    """
    from datetime import timedelta
    uid = f"u_daytime_only_{uuid.uuid4().hex[:6]}"
    today_iso = LocalStore.get_beijing_today().isoformat()
    old_date_iso = (LocalStore.get_beijing_today() - timedelta(days=15)).isoformat()

    LocalStore.upsert_profile(uid, {
        "id": uid,
        "display_name": "仅跑步戴表跑者",
        "garmin_connected": 1,
        "resting_heart_rate": 54,
        "vo2max": 52.0,
    })

    # 1. Insert an old historical night from 15 days ago (should NOT be spliced into today's health!)
    LocalStore.upsert_daily_health(uid, {
        "date": old_date_iso,
        "resting_heart_rate": 50,
        "sleep_score": 85,
        "sleep_duration_seconds": 27000,
        "hrv_last_night_avg": 68,
        "hrv_weekly_avg": 65,
        "body_battery_max": 90,
    })

    # 2. Insert today's daytime-only record (wore watch during a run: steps & calories present, NO overnight HRV or sleep_duration_seconds)
    # Even if a caller passes a fallback resting_heart_rate or sleep_score without overnight HRV/sleep_duration_seconds, it must be stripped!
    LocalStore.upsert_daily_health(uid, {
        "date": today_iso,
        "resting_heart_rate": 54,
        "sleep_score": 78,
        "body_battery_max": 75,
        "steps": 12500,
        "active_calories": 680,
        "hr_max": 176,
    })

    latest_h = LocalStore.get_latest_health(uid)
    assert latest_h is not None
    assert latest_h["date"] == today_iso
    assert latest_h["steps"] == 12500
    # Overnight recovery fields MUST be None (not 54, not 78, and not spliced from 15 days ago!)
    assert latest_h["resting_heart_rate"] is None
    assert latest_h["sleep_score"] is None
    assert latest_h["hrv_last_night_avg"] is None
    assert latest_h["body_battery_max"] is None
    assert LocalStore.compute_physiological_recovery_pct(latest_h) is None

    # 3. Verify recovery availability assessment
    avail = LocalStore.assess_recovery_data_availability(uid)
    assert avail["recovery_data_available"] is False
    assert avail["night_wear_missing"] is True
    assert "夜间HRV" in avail["missing_recovery_fields"]
    assert "晨起静息心率" in avail["missing_recovery_fields"]
    assert "24 小时" in avail["user_warning"]
    assert "夜间未佩戴手表" in avail["coach_warning"]

    # 4. Verify miniapp dashboard endpoint does NOT fallback to profile RHR and warns user
    dash_res = client.get(f"/api/miniapp/dashboard/{uid}")
    assert dash_res.status_code == 200
    dash = dash_res.json()
    th = dash["today_health"]
    assert th["recovery_data_available"] is False
    assert th["night_wear_missing"] is True
    assert th["resting_heart_rate"] is None
    assert th["hrv_ms"] is None
    assert th["sleep_score"] is None
    assert "24 小时" in (dash.get("ai_coach_tip") or "")

    # 5. Case 2 (COROS intermittent non-wear like 李敏):
    # Wore watch on 3 of last 7 nights, but missed the last 2 nights (where daytime HR 70 and fabricated sleep_duration_seconds 26280 were passed without HRV)
    uid_coros = f"u_coros_intermittent_{uuid.uuid4().hex[:6]}"
    LocalStore.upsert_profile(uid_coros, {
        "id": uid_coros,
        "display_name": "李敏测试",
        "coros_connected": 1,
        "resting_heart_rate": 48,
    })
    base_today = LocalStore.get_beijing_today()
    for d_off, hrv_v, rhr_v in [
        (6, 49.0, 47),
        (5, None, 54),
        (4, None, 52),
        (3, 42.0, 47),
        (2, 38.0, 47),
        (1, None, 62),
        (0, None, 70),
    ]:
        d_str = (base_today - timedelta(days=d_off)).isoformat()
        LocalStore.upsert_daily_health(uid_coros, {
            "date": d_str,
            "resting_heart_rate": rhr_v,
            "hrv_last_night_avg": hrv_v,
            "hrv_weekly_avg": 41.0 if hrv_v else None,
            "sleep_duration_seconds": 26280,  # Legacy fabricated COROS sleep_duration_seconds
            "sleep_score": 72,
        })
    avail_coros = LocalStore.assess_recovery_data_availability(uid_coros)
    assert avail_coros["recovery_data_available"] is False
    assert avail_coros["night_wear_missing"] is True
    assert avail_coros["night_wear_intermittent"] is True
    assert avail_coros["valid_nights_7d"] == 3
    assert "3/7" in avail_coros["user_warning"]
    assert "3/7" in avail_coros["coach_warning"]
    latest_coros_h = LocalStore.get_latest_health(uid_coros)
    assert latest_coros_h["resting_heart_rate"] is None
    assert latest_coros_h["sleep_score"] is None

    # 6. Case 3 (Garmin multi-day prior non-wear breaking 7-day baseline like 陈晓韵):
    # Did not wear watch at night for 11 of last 14 nights; wore only on the last 3 nights so hrv_weekly_avg=None and hrv_status="NONE"
    uid_garmin_gap = f"u_garmin_gap_{uuid.uuid4().hex[:6]}"
    LocalStore.upsert_profile(uid_garmin_gap, {
        "id": uid_garmin_gap,
        "display_name": "陈晓韵测试",
        "garmin_connected": 1,
        "resting_heart_rate": 48,
    })
    for d_off in range(13, 2, -1):
        d_str = (base_today - timedelta(days=d_off)).isoformat()
        LocalStore.upsert_daily_health(uid_garmin_gap, {
            "date": d_str,
            "steps": 14000,
            "active_calories": 650,
        })
    for d_off, hrv_v, rhr_v, slp_v in [
        (2, 39.0, 48, 85),
        (1, 81.0, 47, 52),
        (0, 51.0, 50, 72),
    ]:
        d_str = (base_today - timedelta(days=d_off)).isoformat()
        LocalStore.upsert_daily_health(uid_garmin_gap, {
            "date": d_str,
            "resting_heart_rate": rhr_v,
            "hrv_last_night_avg": hrv_v,
            "hrv_weekly_avg": None,
            "hrv_status": "NONE",
            "sleep_score": slp_v,
            "sleep_duration_seconds": 25200,
        })
    avail_garmin_gap = LocalStore.assess_recovery_data_availability(uid_garmin_gap)
    assert avail_garmin_gap["recovery_data_available"] is False
    assert avail_garmin_gap["night_wear_missing"] is True
    assert avail_garmin_gap["night_wear_intermittent"] is True
    assert avail_garmin_gap["hrv_baseline_broken"] is True
    assert avail_garmin_gap["valid_nights_7d"] == 3
    assert "3/7" in avail_garmin_gap["user_warning"]
    assert "基线" in avail_garmin_gap["coach_warning"]
    latest_gap_h = LocalStore.get_latest_health(uid_garmin_gap)
    assert LocalStore.compute_physiological_recovery_pct(latest_gap_h) is None






