import json
import time
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient

from config import settings
from main import app
from utils.local_store import LocalStore, get_beijing_today
from utils.workout_segmentation import analyze_activity_segments, has_large_plan_discrepancy

client = TestClient(app)


def _make_jwt(uid: str) -> str:
    return jwt.encode(
        {
            "sub": uid,
            "uid": uid,
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        },
        settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )


def test_personal_share_card_with_active_scheduled_plan_and_json_journal():
    """
    Regression test for production 500 TypeError in GET /api/miniapp/personal-share-card/{uid}
    when the runner has an active scheduled training plan on the activity date.
    """
    ts = int(time.time() * 1000)
    uid = f"u_share_plan_{ts}"
    today_iso = get_beijing_today().isoformat()

    LocalStore.upsert_profile(
        uid,
        {
            "id": uid,
            "display_name": "分享卡计划跑者",
            "gender": "male",
            "max_heart_rate": 188,
            "resting_heart_rate": 52,
        },
    )

    LocalStore.save_training_plan(
        {
            "id": f"tp_share_{ts}",
            "user_id": uid,
            "title": "复旦戈专项周期课表",
            "goal_type": "marathon",
            "start_date": today_iso,
            "weeks_count": 1,
            "status": "active",
            "schedule_data": {
                "weeks": [
                    {
                        "week_index": 1,
                        "week_title": "专项有氧周",
                        "weekly_mileage_km": 60.0,
                        "days": [
                            {
                                "day_of_week": "周三",
                                "date": today_iso,
                                "workout_type": "easy_run",
                                "title": "有氧稳态跑 14km",
                                "distance_km": 14.0,
                                "target_pace": "5:05 - 5:25 /km",
                                "target_hr_zone": "140-152 bpm",
                                "description": "全程保持平稳呼吸与高步频。",
                                "completed": False,
                            }
                        ],
                    }
                ]
            },
        }
    )

    # 1. Matching workout (14.3km @ 5:12/km) + JSON ai_journal
    act_match_id = f"coros_match_{ts}"
    LocalStore.upsert_activity(
        {
            "id": act_match_id,
            "user_id": uid,
            "name": "晚间有氧稳态跑",
            "sport_type": "Run",
            "start_time": f"{today_iso}T18:08:00",
            "distance_meters": 14300.0,
            "moving_time_seconds": 4462,
            "avg_pace_str": "5:12",
            "average_heartrate": 146,
            "elevation_gain_meters": 28.0,
            "ai_journal": json.dumps(
                {"summary": "AI教练点评：本次 14.3km 有氧稳态跑配速与心率高度契合周期目标。"},
                ensure_ascii=False,
            ),
        },
        notify=False,
        reconcile_plan=False,
    )

    with patch("utils.wechat.wechat_client.get_wxacode_by_path", return_value=b""), patch(
        "utils.wechat.wechat_client.get_wxacode_unlimit", return_value=b""
    ):
        resp = client.get(
            f"/api/miniapp/personal-share-card/{uid}?env_version=release&activity_id={act_match_id}",
            headers={"Authorization": f"Bearer {_make_jwt(uid)}"},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["day_plan"]["has_scheduled_plan"] is True
    assert data["actual_data"]["distance_km"] == 14.3
    opts = {o["key"]: o for o in data["commentary_options"]}
    assert opts["exec"]["label"] == "📊 计划执行复盘"
    assert "有氧稳态跑 14km" in opts["exec"]["text"]
    # JSON ai_journal must be cleanly unwrapped and AI -> Canova sanitized
    assert not opts["journal"]["text"].startswith("{")
    assert "Canova 教练点评" in opts["journal"]["text"]

    # 2. Large discrepancy workout on same planned day (5.0km short shakeout vs 14.0km plan)
    act_disc_id = f"coros_disc_{ts}"
    LocalStore.upsert_activity(
        {
            "id": act_disc_id,
            "user_id": uid,
            "name": "晨间排酸慢跑",
            "sport_type": "Run",
            "start_time": f"{today_iso}T07:00:00",
            "distance_meters": 5000.0,
            "moving_time_seconds": 1800,
            "avg_pace_str": "6:00",
            "average_heartrate": 135,
        },
        notify=False,
        reconcile_plan=False,
    )

    with patch("utils.wechat.wechat_client.get_wxacode_by_path", return_value=b""), patch(
        "utils.wechat.wechat_client.get_wxacode_unlimit", return_value=b""
    ):
        resp2 = client.get(
            f"/api/miniapp/personal-share-card/{uid}?env_version=release&activity_id={act_disc_id}",
            headers={"Authorization": f"Bearer {_make_jwt(uid)}"},
        )

    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()
    assert data2["success"] is True
    opts2 = {o["key"]: o for o in data2["commentary_options"]}
    assert opts2["exec"]["label"] == "📊 训练效果复盘"

    # Also verify direct 2-arg call to has_large_plan_discrepancy never raises TypeError
    assert (
        has_large_plan_discrepancy(
            planned_day={"workout_type": "easy_run", "distance_km": 14.0, "target_pace": "5:10-5:30"},
            activity={"distance_meters": 5000.0, "avg_pace_str": "6:00"},
        )
        is True
    )


def test_personal_share_card_respects_gps_and_biometrics_privacy():
    """
    When a runner enables hide_gps_route & hide_biometrics:
    - Owner loading their own share card gets full GPS polyline + heart rate.
    - Regular club teammate loading that runner's share card gets 200 OK with hidden GPS & hidden HR.
    """
    ts = int(time.time() * 1000)
    owner_uid = f"u_share_priv_owner_{ts}"
    mate_uid = f"u_share_priv_mate_{ts}"
    today_iso = get_beijing_today().isoformat()

    LocalStore.upsert_profile(
        owner_uid,
        {
            "id": owner_uid,
            "display_name": "隐私保护跑者",
            "hide_gps_route": True,
            "hide_biometrics": True,
        },
    )
    LocalStore.upsert_profile(
        mate_uid,
        {
            "id": mate_uid,
            "display_name": "同团跑友",
        },
    )
    club = LocalStore.create_club(owner_uid, f"测试跑团_{ts}", "隐私测试")
    club_id = club["id"]
    LocalStore.join_club_by_code(mate_uid, club["invite_code"])

    act_id = f"coros_priv_{ts}"
    LocalStore.upsert_activity(
        {
            "id": act_id,
            "user_id": owner_uid,
            "name": "保密轨迹跑",
            "sport_type": "Run",
            "start_time": f"{today_iso}T19:00:00",
            "distance_meters": 10000.0,
            "moving_time_seconds": 3000,
            "avg_pace_str": "5:00",
            "average_heartrate": 152,
            "max_heartrate": 168,
        },
        notify=False,
        reconcile_plan=False,
    )
    LocalStore.save_activity_streams(
        act_id,
        user_id=owner_uid,
        gps_track_data={
            "activity_id": act_id,
            "points": [
                {"lat": 31.2981, "lng": 121.5012},
                {"lat": 31.2995, "lng": 121.5030},
                {"lat": 31.3010, "lng": 121.5051},
            ],
            "elevation_profile": [
                {"dist_km": 0.0, "elevation_m": 8.0},
                {"dist_km": 5.0, "elevation_m": 14.0},
                {"dist_km": 10.0, "elevation_m": 9.0},
            ],
        },
    )

    with patch("utils.wechat.wechat_client.get_wxacode_by_path", return_value=b""), patch(
        "utils.wechat.wechat_client.get_wxacode_unlimit", return_value=b""
    ):
        # Owner sees own GPS track + HR
        r_self = client.get(
            f"/api/miniapp/personal-share-card/{owner_uid}?activity_id={act_id}&club_id={club_id}",
            headers={"Authorization": f"Bearer {_make_jwt(owner_uid)}"},
        )
        assert r_self.status_code == 200
        d_self = r_self.json()
        assert d_self["track_overlay"]["has_gps_track"] is True
        assert d_self["actual_data"]["average_heartrate"] == 152

        # Regular teammate gets 200 OK without hidden GPS or HR
        r_mate = client.get(
            f"/api/miniapp/personal-share-card/{owner_uid}?activity_id={act_id}&club_id={club_id}",
            headers={"Authorization": f"Bearer {_make_jwt(mate_uid)}"},
        )
        assert r_mate.status_code == 200
        d_mate = r_mate.json()
        assert d_mate["success"] is True
        assert d_mate["track_overlay"]["has_gps_track"] is False
        assert d_mate["actual_data"]["average_heartrate"] is None


def test_workout_segmentation_handles_partial_tail_lap_with_none_pace():
    """
    Regression test for COROS tail lap where pace_sec is None (e.g. 8m / 0s button-press tail).
    Must not raise TypeError: int() argument must be ... not 'NoneType'.
    """
    activity = {
        "id": "coros_tail_none_test",
        "name": "阈值巡航跑",
        "sport_type": "Run",
        "distance_meters": 10008.0,
        "moving_time_seconds": 2850,
        "avg_pace_str": "4:45",
        "average_heartrate": 158,
    }
    laps = [
        {"lap_index": i + 1, "distance_m": 1000.0, "duration_s": 285, "pace_sec": 285, "avg_hr": 156 + (i % 4)}
        for i in range(10)
    ] + [
        {"lap_index": 11, "distance_m": 8.0, "duration_s": 0, "pace_sec": None, "avg_hr": 160},
    ]

    result = analyze_activity_segments(
        activity=activity,
        track_data={"laps": laps, "points": []},
        planned_day=None,
        preset_race=None,
        max_hr=188.0,
    )
    assert isinstance(result, dict)
    assert result.get("phases")
