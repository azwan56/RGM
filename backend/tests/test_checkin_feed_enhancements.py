import uuid
from datetime import datetime
from fastapi.testclient import TestClient
from main import app
from utils.local_store import LocalStore, init_db

client = TestClient(app)


def test_checkin_feed_likers_and_threaded_comments():
    init_db()
    uid1 = "u_feed_enh_1"
    uid2 = "u_feed_enh_2"
    uid3 = "u_feed_enh_3"

    LocalStore.upsert_profile(uid1, {"display_name": "张三", "avatar_url": "https://example.com/a1.png"})
    LocalStore.upsert_profile(uid2, {"display_name": "李四", "avatar_url": "https://example.com/a2.png"})
    LocalStore.upsert_profile(uid3, {"display_name": "王五", "avatar_url": "https://example.com/a3.png"})

    act_id = f"act_feed_social_test_{uuid.uuid4().hex[:8]}"
    LocalStore.upsert_activity(
        {
            "id": act_id,
            "user_id": uid1,
            "name": "晨跑打卡",
            "sport_type": "Run",
            "start_time": "2026-11-02T06:30:00Z",
            "distance_meters": 10000.0,
            "moving_time_seconds": 3000,
            "avg_pace_str": "5:00 /km",
            "average_heartrate": 142,
        },
        notify=False,
    )

    # 1. Like with user 2 and user 3 -> verify likers list with avatars and names
    res_l1 = client.post(f"/api/team/activities/{act_id}/like", json={"user_id": uid2})
    assert res_l1.status_code == 200
    d1 = res_l1.json()
    assert d1["liked"] is True
    assert d1["likes_count"] >= 1
    assert any(l["user_id"] == uid2 and l["display_name"] == "李四" and l["avatar_url"] == "https://example.com/a2.png" for l in d1["likers"])

    res_l2 = client.post(f"/api/team/activities/{act_id}/like", json={"user_id": uid3})
    assert res_l2.status_code == 200
    d2 = res_l2.json()
    assert len(d2["likers"]) >= 2

    # 2. Root comment by user 2, reply by user 1, nested reply by user 3 -> verify thread fields
    c1_res = client.post(
        f"/api/team/activities/{act_id}/comments",
        json={"user_id": uid2, "content": "配速很稳，加油！"},
    )
    assert c1_res.status_code == 200
    c1 = c1_res.json()["comment"]
    assert c1["parent_id"] is None

    c2_res = client.post(
        f"/api/team/activities/{act_id}/comments",
        json={
            "user_id": uid1,
            "content": "谢谢李四哥，今天主课顶住了！",
            "parent_id": c1["id"],
        },
    )
    assert c2_res.status_code == 200
    c2 = c2_res.json()["comment"]
    assert c2["parent_id"] == c1["id"]
    assert c2["reply_to_user_id"] == uid2
    assert c2["reply_to_name"] == "李四"

    # Nested reply to c2 should normalize parent_id to root c1 while keeping reply_to_name == "张三"
    c3_res = client.post(
        f"/api/team/activities/{act_id}/comments",
        json={
            "user_id": uid3,
            "content": "周末一起拉练！",
            "parent_id": c2["id"],
        },
    )
    assert c3_res.status_code == 200
    c3 = c3_res.json()["comment"]
    assert c3["parent_id"] == c1["id"]
    assert c3["reply_to_user_id"] == uid1
    assert c3["reply_to_name"] == "张三"

    social_res = client.get(f"/api/team/activities/{act_id}/social?uid={uid2}")
    assert social_res.status_code == 200
    s_data = social_res.json()
    assert s_data["has_liked"] is True
    assert len(s_data["likers"]) >= 2
    assert any(c["id"] == c3["id"] and c["parent_id"] == c1["id"] and c["reply_to_name"] == "张三" for c in s_data["comments"])


def test_canova_critique_plan_main_set_and_concrete_beginner_encouragement():
    init_db()
    uid = "u_feed_canova_plan_runner"
    LocalStore.upsert_profile(
        uid,
        {
            "display_name": "进阶跑者小陈",
            "years_running": 1,
            "max_heart_rate": 190,
            "resting_heart_rate": 55,
            "marathon_pb": "4:20:00",
        },
    )

    # Seed historical runs so concrete improvements in distance, pace, and HR can be computed
    LocalStore.upsert_activity(
        {
            "id": "act_hist_1",
            "user_id": uid,
            "name": "历史有氧跑1",
            "sport_type": "Run",
            "start_time": "2026-10-25T07:00:00Z",
            "distance_meters": 10000.0,
            "moving_time_seconds": 3480,
            "avg_pace_str": "5:48 /km",
            "average_heartrate": 152,
        },
        notify=False,
    )
    LocalStore.upsert_activity(
        {
            "id": "act_hist_2",
            "user_id": uid,
            "name": "历史有氧跑2",
            "sport_type": "Run",
            "start_time": "2026-10-28T07:00:00Z",
            "distance_meters": 11000.0,
            "moving_time_seconds": 3795,
            "avg_pace_str": "5:45 /km",
            "average_heartrate": 150,
        },
        notify=False,
    )

    # Create an active training plan with a Warm-up + Main Set + Cool-down workout on 2026-11-02
    LocalStore.upsert_training_plan(
        {
            "id": "plan_feed_critique_test",
            "user_id": uid,
            "title": "小陈上马备赛计划",
            "status": "active",
            "start_date": "2026-11-02",
            "end_date": "2026-11-08",
            "schedule_data": {
                "weeks": [
                    {
                        "week_index": 1,
                        "phase": "专项准备期",
                        "days": [
                            {
                                "date": "2026-11-02",
                                "day_of_week": "周一",
                                "workout_type": "tempo",
                                "title": "乳酸门槛巡航跑 (LT2 稳态延伸)",
                                "distance_km": 14.0,
                                "target_pace": "5:15 /km",
                                "target_hr_zone": "心率 142-152 bpm (LT2)",
                                "description": "热身 2km + 10km @ 5:15/km 门槛稳态巡航 + 2km 冷身。",
                            }
                        ],
                    }
                ]
            },
        },
        skip_backup=True,
    )

    # Today's activity on 2026-11-02 showing improved distance (14km vs 10.5km), faster pace (5:20 vs 5:46), lower HR (145 vs 151)
    today_act = {
        "id": "act_today_mainset_1",
        "user_id": uid,
        "name": "门槛巡航打卡",
        "sport_type": "Run",
        "start_time": "2026-11-02T07:00:00Z",
        "distance_meters": 14000.0,
        "moving_time_seconds": 4480,
        "avg_pace_str": "5:20 /km",
        "average_heartrate": 145,
        "max_heartrate": 154,
    }
    critique = LocalStore.generate_canova_critique(today_act)

    # Verify Requirement 3: Workout execution & Main Set focus
    assert "课表主课执行评估" in critique
    assert "乳酸门槛巡航跑" in critique
    assert "热身+主课+冷身" in critique
    assert "主课" in critique
    assert "达成率 100%" in critique

    # Verify Requirement 4: Concrete progress encouragement on Distance, Pace, and Heart Rate (no hollow slogan) + Concise length
    assert "每一步都在重塑更好的自己" not in critique
    assert "入门进阶亮点" not in critique
    assert "【亮点】" in critique
    assert "14.0km" in critique
    assert "提速" in critique
    assert "下降" in critique
    assert len(critique) <= 230

    # Verify Requirement 5 & Home Status VDOT: MiniApp dashboard includes club_feed_summary + vdot
    dash_res = client.get(f"/api/miniapp/dashboard/{uid}")
    assert dash_res.status_code == 200
    dash = dash_res.json()
    assert "club_feed_summary" in dash
    assert "today_checkin_count" in dash["club_feed_summary"]
    assert "coach_critique_count" in dash["club_feed_summary"]
    assert dash.get("vdot") is not None and dash["vdot"] > 0
    assert dash.get("fitness_form", {}).get("vdot") == dash["vdot"]


def test_slim_club_feed_and_batch_leaderboard_with_privacy():
    init_db()
    owner_uid = f"u_owner_slim_{uuid.uuid4().hex[:6]}"
    coach_uid = f"u_coach_slim_{uuid.uuid4().hex[:6]}"
    runner_uid = f"u_runner_slim_{uuid.uuid4().hex[:6]}"
    peer_uid = f"u_peer_slim_{uuid.uuid4().hex[:6]}"

    LocalStore.upsert_profile(owner_uid, {"display_name": "团长老张"})
    LocalStore.upsert_profile(coach_uid, {"display_name": "主教练老王"})
    LocalStore.upsert_profile(
        runner_uid,
        {
            "display_name": "隐私跑者小李",
            "hide_gps_route": 1,
            "hide_biometrics": 1,
        },
    )
    LocalStore.upsert_profile(peer_uid, {"display_name": "普通队友小周"})

    club = LocalStore.create_club(name=f"极速测试团_{uuid.uuid4().hex[:4]}", description="测试精简Feed与榜单", owner_id=owner_uid)
    club_id = club["id"]
    LocalStore.join_club_by_id(coach_uid, club_id, via_invite=True, inviter_uid=owner_uid)
    LocalStore.update_member_role(club_id, coach_uid, "coach")
    LocalStore.join_club_by_id(runner_uid, club_id, via_invite=True, inviter_uid=owner_uid)
    LocalStore.join_club_by_id(peer_uid, club_id, via_invite=True, inviter_uid=owner_uid)

    dense_points = [{"latitude": 31.20 + i * 0.0001, "longitude": 121.50 + i * 0.0001, "elevation": 12.3} for i in range(180)]
    heavy_track = {
        "points": dense_points,
        "telemetry_series": [{"dist_km": i * 0.05, "hr": 150} for i in range(240)],
        "elevation_profile": [{"d": i * 0.1, "e": 12.0} for i in range(120)],
        "laps": [{"lap": i, "dist": 1000} for i in range(15)],
    }

    today = LocalStore.get_beijing_today()
    run_ts = f"{today.year:04d}-{today.month:02d}-01T07:00:00Z"

    act_priv = f"garmin_priv_{uuid.uuid4().hex[:6]}"
    act_pub = f"garmin_pub_{uuid.uuid4().hex[:6]}"
    LocalStore.upsert_activity(
        {
            "id": act_priv,
            "user_id": runner_uid,
            "name": "保密晨跑",
            "sport_type": "Run",
            "start_time": run_ts,
            "distance_meters": 12000.0,
            "moving_time_seconds": 3600,
            "avg_pace_str": "5:00 /km",
            "average_heartrate": 155,
            "gps_track_data": heavy_track,
            "laps_data": [{"lapIndex": 1, "distance": 12000}],
            "splits_data": [{"splitIndex": 1, "distance": 12000}],
        },
        notify=False,
    )
    LocalStore.upsert_activity(
        {
            "id": act_pub,
            "user_id": peer_uid,
            "name": "公开晨跑",
            "sport_type": "Run",
            "start_time": run_ts,
            "distance_meters": 8000.0,
            "moving_time_seconds": 2400,
            "avg_pace_str": "5:00 /km",
            "average_heartrate": 148,
            "gps_track_data": heavy_track,
            "laps_data": [{"lapIndex": 1, "distance": 8000}],
            "splits_data": [{"splitIndex": 1, "distance": 8000}],
        },
        notify=False,
    )

    # 1. Peer viewer: public run keeps <=36-pt slim thumbnail & strips heavy blobs; private run hides GPS & HR
    feed_peer = client.get(f"/api/team/{club_id}/feed?uid={peer_uid}").json()["feed"]
    by_id_peer = {a["id"]: a for a in feed_peer}
    pub_item = by_id_peer[act_pub]
    assert pub_item["has_gps_track"] is True
    assert len(pub_item["gps_track_data"]["points"]) == 36
    assert "telemetry_series" not in pub_item["gps_track_data"]
    assert "laps_data" not in pub_item
    assert "splits_data" not in pub_item

    priv_for_peer = by_id_peer[act_priv]
    assert priv_for_peer["is_gps_hidden"] is True
    assert priv_for_peer["gps_track_data"] is None
    assert priv_for_peer["average_heartrate"] is None

    # 2. Coach viewer: can view private runner's slim route preview and HR
    feed_coach = client.get(f"/api/team/{club_id}/feed?uid={coach_uid}").json()["feed"]
    priv_for_coach = {a["id"]: a for a in feed_coach}[act_priv]
    assert priv_for_coach["is_gps_hidden"] is False
    assert len(priv_for_coach["gps_track_data"]["points"]) == 36
    assert priv_for_coach["average_heartrate"] == 155

    # 3. Batch leaderboard accuracy
    lb = client.get(f"/api/team/{club_id}/leaderboard?user_id={peer_uid}").json()["leaderboard"]
    assert len(lb) == 4
    assert lb[0]["user_id"] == runner_uid and lb[0]["distance_km"] == 12.0
    assert lb[1]["user_id"] == peer_uid and lb[1]["distance_km"] == 8.0

