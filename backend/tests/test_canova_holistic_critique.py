import os
import time
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient

import routers.miniapp as miniapp_mod
import utils.local_store as ls_mod
from config import settings
from main import app
from utils.local_store import LocalStore, init_db


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


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_canova_holistic.db"
    monkeypatch.setattr(ls_mod, "DB_PATH", str(db_file))
    monkeypatch.setattr(miniapp_mod, "DB_PATH", str(db_file))
    init_db()
    yield db_file


def _seed_activity(
    uid: str,
    act_id: str,
    start_time: str,
    dist_m: float,
    moving_s: int,
    pace_str: str,
    avg_hr: float,
    name: str = "常规有氧跑",
    sport_type: str = "Run",
    elev_gain: float = 15.0,
    trimp: float = 65.0,
    gps_track_data=None,
) -> dict:
    act = {
        "id": act_id,
        "user_id": uid,
        "name": name,
        "sport_type": sport_type,
        "start_time": start_time,
        "distance_meters": dist_m,
        "moving_time_seconds": moving_s,
        "elapsed_time_seconds": moving_s,
        "avg_pace_str": pace_str,
        "average_heartrate": avg_hr,
        "max_heartrate": avg_hr + 14,
        "elevation_gain_meters": elev_gain,
        "trimp": trimp,
    }
    if gps_track_data is not None:
        act["gps_track_data"] = gps_track_data
    LocalStore.upsert_activity(act, notify=False)
    return act


def test_point1_diverse_lenses_zero_boilerplate_and_terrain_baseline_isolation(isolated_db):
    uid = "u_holistic_p1"
    profile = {
        "id": uid,
        "display_name": "多镜头测试跑者",
        "max_heart_rate": 190,
        "resting_heart_rate": 54,
        "years_running": 3,
    }
    LocalStore.upsert_profile(uid, profile)

    # Seed 5 prior road runs so road comparable baseline exists
    for idx, day_num in enumerate((2, 4, 6, 8, 9), start=1):
        _seed_activity(
            uid=uid,
            act_id=f"p1_road_hist_{idx}",
            start_time=f"2026-11-0{day_num}T07:00:00+08:00",
            dist_m=10000.0,
            moving_s=3150,
            pace_str="5:15",
            avg_hr=146.0,
            name="路跑有氧积累",
            elev_gain=12.0,
            trimp=72.0,
        )

    # 5 diverse workout types
    workouts = [
        ("easy", "2026-11-11T07:00:00+08:00", 7000.0, 2485, "5:55", 131.0, "轻松有氧恢复", 10.0),
        ("threshold", "2026-11-12T07:00:00+08:00", 12000.0, 3180, "4:25", 173.0, "乳酸门槛巡航", 18.0),
        ("lsd", "2026-11-13T06:30:00+08:00", 30000.0, 10050, "5:35", 145.0, "周末30公里LSD", 80.0),
        ("intervals", "2026-11-14T07:00:00+08:00", 8000.0, 2000, "4:10", 171.0, "田径场间歇 5x1000m", 4.0),
        ("trail", "2026-11-15T07:00:00+08:00", 16000.0, 8400, "8:45", 138.0, "莫干山越野跑", 620.0),
    ]

    critiques = {}
    for key, st, dm, ms, ps, hr, nm, el in workouts:
        act = {
            "id": f"p1_eval_{key}",
            "user_id": uid,
            "name": nm,
            "sport_type": "TrailRun" if key == "trail" else "Run",
            "start_time": st,
            "distance_meters": dm,
            "moving_time_seconds": ms,
            "avg_pace_str": ps,
            "average_heartrate": hr,
            "elevation_gain_meters": el,
        }
        c = LocalStore.generate_canova_critique(act, profile)
        critiques[key] = c
        assert len(c) <= 230
        assert len(c) <= 226
        assert "💡" in c
        assert "⚡" in c[2:]
        assert c.index("💡") < c.index("⚡")
        assert "，进步扎实！" not in c
        assert "休整日" not in c

    assert "【间歇专项刺激】" in critiques["intervals"]
    assert "【长距离有氧耐力】" in critiques["lsd"]
    assert "爬升" in critiques["trail"]
    assert "徒步" in critiques["trail"]
    assert "离心" in critiques["trail"]
    # Trail critique must NOT compare pace against road baseline
    assert "较近期提速" not in critiques["trail"]

    # 2 steady aerobic runs on different microcycle days (Day 1 after 3 rest days vs Day 3 consecutive streak)
    _seed_activity(uid, "p1_mc_prev1", "2026-11-18T07:00:00+08:00", 10000.0, 3100, "5:10", 142.0, "稳态有氧1")
    _seed_activity(uid, "p1_mc_prev2", "2026-11-19T07:00:00+08:00", 10000.0, 3100, "5:10", 142.0, "稳态有氧2")
    steady_after_rest = {
        "id": "p1_steady_rest",
        "user_id": uid,
        "name": "稳态有氧跑",
        "sport_type": "Run",
        "start_time": "2026-11-23T07:00:00+08:00",
        "distance_meters": 10000.0,
        "moving_time_seconds": 3100,
        "avg_pace_str": "5:10",
        "average_heartrate": 142.0,
    }
    steady_streak = {
        "id": "p1_steady_streak",
        "user_id": uid,
        "name": "稳态有氧跑",
        "sport_type": "Run",
        "start_time": "2026-11-20T07:00:00+08:00",
        "distance_meters": 10000.0,
        "moving_time_seconds": 3100,
        "avg_pace_str": "5:10",
        "average_heartrate": 142.0,
    }
    c_steady_1 = LocalStore.generate_canova_critique(steady_after_rest, profile)
    c_steady_2 = LocalStore.generate_canova_critique(steady_streak, profile)
    assert c_steady_1 != c_steady_2
    assert len(c_steady_1) <= 226 and len(c_steady_2) <= 226


def test_point2_recovery_banister_load_modulation_and_non_night_wear_sanitization(isolated_db):
    uid = "u_holistic_p2"
    profile = {
        "id": uid,
        "display_name": "体能恢复测试员",
        "max_heart_rate": 188,
        "resting_heart_rate": 52,
        "years_running": 4,
    }
    LocalStore.upsert_profile(uid, profile)
    LocalStore.upsert_goal(uid, {"weekly_target": 60, "monthly_target": 240})

    # Seed 21 days of running history to build CTL/ATL/TSB, ending with a 22km long run on 2026-11-12
    for offset in range(21, 1, -2):
        day_str = f"2026-11-{(13 - offset):02d}" if offset < 13 else f"2026-10-{(31 + 13 - offset):02d}"
        _seed_activity(
            uid=uid,
            act_id=f"p2_hist_{offset}",
            start_time=f"{day_str}T07:00:00+08:00",
            dist_m=11000.0,
            moving_s=3465,
            pace_str="5:15",
            avg_hr=144.0,
            name="有氧积累",
            trimp=82.0,
        )
    # 2026-11-12 yesterday demanding 22km long run
    _seed_activity(
        uid=uid,
        act_id="p2_long_yesterday",
        start_time="2026-11-12T06:30:00+08:00",
        dist_m=22000.0,
        moving_s=7480,
        pace_str="5:40",
        avg_hr=151.0,
        name="长距离耐力拉练",
        trimp=145.0,
    )

    # 6 valid consecutive overnight health records (2026-11-08 .. 2026-11-13)
    for d in range(8, 14):
        LocalStore.upsert_daily_health(
            uid,
            {
                "date": f"2026-11-{d:02d}",
                "source": "garmin",
                "sleep_duration_seconds": int(7.6 * 3600),
                "sleep_score": 85,
                "hrv_last_night_avg": 64,
                "hrv_weekly_avg": 61,
                "hrv_status": "BALANCED",
                "resting_heart_rate": 51,
            },
        )

    # Subcase A: Recovery run on 2026-11-13 after yesterday's 22km long run
    rec_run = _seed_activity(
        uid=uid,
        act_id="p2_recovery_today",
        start_time="2026-11-13T07:30:00+08:00",
        dist_m=8000.0,
        moving_s=2840,
        pace_str="5:55",
        avg_hr=129.0,
        name="排酸恢复慢跑",
        trimp=42.0,
    )
    c_rec = LocalStore.generate_canova_critique(rec_run, profile)
    assert len(c_rec) <= 230
    assert "本周" in c_rec
    assert "昨日" in c_rec or "22" in c_rec
    assert "睡眠" in c_rec or "HRV" in c_rec
    assert "CTL" in c_rec and "TSB" in c_rec

    # Segmented critique check on 2026-11-13 with km_splits
    splits = [
        {"km": i + 1, "distance_meters": 1000.0, "moving_time_seconds": 330 - i * 8, "pace_str": f"{(330 - i * 8)//60}:{(330 - i * 8)%60:02d}", "average_heartrate": 138 + i * 3}
        for i in range(6)
    ]
    seg_act = _seed_activity(
        uid=uid,
        act_id="p2_segmented_prog",
        start_time="2026-11-13T18:00:00+08:00",
        dist_m=6000.0,
        moving_s=sum(s["moving_time_seconds"] for s in splits),
        pace_str="5:10",
        avg_hr=146.0,
        name="渐进加速训练",
        trimp=58.0,
        gps_track_data={"km_splits": splits},
    )
    seg_res = LocalStore.compute_and_cache_segment_analysis(seg_act["id"], force=True)
    assert seg_res is not None
    assert seg_res["schema_version"] == 4
    assert "CTL" in seg_res["coach_advice"] or "本周" in seg_res["coach_advice"]
    seg_journal = seg_res.get("updated_ai_journal") or ""
    assert len(seg_journal) <= 230
    assert "💡" in seg_journal and "⚡" in seg_journal[2:]
    assert seg_journal.index("💡") < seg_journal.index("⚡")

    # Subcase B: Suppressed overnight sleep/HRV warning on 2026-11-14
    LocalStore.upsert_daily_health(
        uid,
        {
            "date": "2026-11-14",
            "source": "garmin",
            "sleep_duration_seconds": int(5.1 * 3600),
            "sleep_score": 54,
            "hrv_last_night_avg": 44,
            "hrv_weekly_avg": 62,
            "hrv_status": "LOW",
            "resting_heart_rate": 58,
        },
    )
    suppressed_run = {
        "id": "p2_suppressed",
        "user_id": uid,
        "name": "晨跑",
        "sport_type": "Run",
        "start_time": "2026-11-14T07:00:00+08:00",
        "distance_meters": 9000.0,
        "moving_time_seconds": 3000,
        "avg_pace_str": "5:33",
        "average_heartrate": 149.0,
    }
    c_supp = LocalStore.generate_canova_critique(suppressed_run, profile)
    assert "低于基线" in c_supp or "早睡补足8h" in c_supp

    # Subcase C: Daytime-only non-night-wearing watch (no overnight sleep/HRV -> must NEVER fabricate biometrics)
    uid_daytime = "u_holistic_daytime_only"
    LocalStore.upsert_profile(uid_daytime, {"id": uid_daytime, "display_name": "白天佩戴用户"})
    LocalStore.upsert_daily_health(
        uid_daytime,
        {
            "date": "2026-11-13",
            "source": "garmin",
            "sleep_duration_seconds": None,
            "sleep_score": None,
            "hrv_last_night_avg": None,
            "hrv_weekly_avg": None,
            "resting_heart_rate": 68,
        },
    )
    c_daytime = LocalStore.generate_canova_critique(
        {
            "id": "p2_daytime_run",
            "user_id": uid_daytime,
            "name": "午间跑",
            "sport_type": "Run",
            "start_time": "2026-11-13T12:15:00+08:00",
            "distance_meters": 8000.0,
            "moving_time_seconds": 2640,
            "avg_pace_str": "5:30",
            "average_heartrate": 144.0,
        },
        {"id": uid_daytime, "max_heart_rate": 188, "resting_heart_rate": 54},
    )
    assert "HRV" not in c_daytime
    assert "睡眠" not in c_daytime
    assert "静息" not in c_daytime


def test_point3_forward_training_plan_race_countdown_and_share_card_privacy(isolated_db, monkeypatch):
    monkeypatch.setattr("utils.wechat.wechat_client.get_wxacode_by_path", lambda **kwargs: b"x" * 600)

    uid = "u_holistic_p3"
    profile = {
        "id": uid,
        "display_name": "备赛前瞻跑者",
        "max_heart_rate": 188,
        "resting_heart_rate": 52,
        "years_running": 4,
    }
    LocalStore.upsert_profile(uid, profile)

    # Seed CTL history & valid sleep/HRV so share card commentary_phys gets rich context
    for day_d in range(5, 13):
        _seed_activity(
            uid=uid,
            act_id=f"p3_hist_{day_d}",
            start_time=f"2026-11-{day_d:02d}T07:00:00+08:00",
            dist_m=10000.0,
            moving_s=3120,
            pace_str="5:12",
            avg_hr=145.0,
            name="有氧跑",
            trimp=78.0,
        )
        LocalStore.upsert_daily_health(
            uid,
            {
                "date": f"2026-11-{day_d:02d}",
                "source": "garmin",
                "sleep_duration_seconds": int(7.5 * 3600),
                "sleep_score": 83,
                "hrv_last_night_avg": 62,
                "hrv_weekly_avg": 60,
                "hrv_status": "BALANCED",
                "resting_heart_rate": 52,
            },
        )
    LocalStore.upsert_daily_health(
        uid,
        {
            "date": "2026-11-13",
            "source": "garmin",
            "sleep_duration_seconds": int(7.5 * 3600),
            "sleep_score": 84,
            "hrv_last_night_avg": 63,
            "hrv_weekly_avg": 60,
            "hrv_status": "BALANCED",
            "resting_heart_rate": 52,
        },
    )

    LocalStore.upsert_race_plan(
        uid,
        {
            "id": "race_sh_p3",
            "name": "上海马拉松",
            "race_type": "全马",
            "race_date": "2026-12-01",
            "target_time": "3:15:00",
            "status": "upcoming",
        },
    )

    LocalStore.upsert_training_plan(
        {
            "id": "plan_sh_p3",
            "user_id": uid,
            "title": "上马冲刺四周",
            "status": "active",
            "start_date": "2026-11-09",
            "end_date": "2026-12-06",
            "target_race_name": "上海马拉松",
            "target_date": "2026-12-01",
            "schedule_data": {
                "weeks": [
                    {
                        "week_number": 1,
                        "weekly_mileage_km": 65,
                        "days": [
                            {
                                "date": "2026-11-13",
                                "type": "有氧慢跑",
                                "title": "轻松有氧",
                                "distance_km": 10,
                                "target_pace": "5:15/km",
                            },
                            {
                                "date": "2026-11-14",
                                "type": "阈值跑",
                                "title": "乳酸门槛跑",
                                "distance_km": 12,
                                "target_pace": "4:30/km",
                            },
                        ],
                    }
                ]
            },
        },
        skip_backup=True,
    )

    today_act = _seed_activity(
        uid=uid,
        act_id="p3_act_nov13",
        start_time="2026-11-13T07:00:00+08:00",
        dist_m=10000.0,
        moving_s=3100,
        pace_str="5:10",
        avg_hr=142.0,
        name="晨间有氧",
        trimp=72.0,
    )
    critique_p3 = today_act["ai_journal"]
    assert len(critique_p3) <= 230
    forward_part = critique_p3.split("⚡")[-1]
    assert ("明日" in forward_part and "门槛" in forward_part) or ("上海" in forward_part and "D-18" in forward_part)

    # Taper countdown D-9 check on 2026-11-22 (no tomorrow workout in schedule -> emits D-9 & 减量)
    taper_act = {
        "id": "p3_act_nov22",
        "user_id": uid,
        "name": "赛前减量节奏",
        "sport_type": "Run",
        "start_time": "2026-11-22T07:00:00+08:00",
        "distance_meters": 8000.0,
        "moving_time_seconds": 2520,
        "avg_pace_str": "5:15",
        "average_heartrate": 141.0,
    }
    critique_taper = LocalStore.generate_canova_critique(taper_act, profile)
    assert len(critique_taper) <= 230
    taper_forward = critique_taper.split("⚡")[-1]
    assert "D-9" in taper_forward and "减量" in taper_forward

    # Share card endpoint verification (owner visible vs public hide_biometrics)
    avatar_dir = os.path.join(os.path.dirname(os.path.dirname(miniapp_mod.__file__)), "data", "avatars")
    try:
        token = _make_jwt(uid)
        res_owner = client.get(
            f"/api/miniapp/personal-share-card/{uid}?activity_id=p3_act_nov13&target_date=2026-11-13",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_owner.status_code == 200
        opts_owner = {item["key"]: item["text"] for item in res_owner.json()["commentary_options"]}
        assert "本周" in opts_owner["phys"]
        assert "CTL" in opts_owner["phys"]
        assert "睡眠" in opts_owner["phys"] or "HRV" in opts_owner["phys"]

        # Enable hide_biometrics and query as public/unauthenticated viewer
        LocalStore.upsert_profile(uid, {**profile, "hide_biometrics": True})
        res_public = client.get(
            f"/api/miniapp/personal-share-card/{uid}?activity_id=p3_act_nov13&target_date=2026-11-13",
        )
        assert res_public.status_code == 200
        opts_public = {item["key"]: item["text"] for item in res_public.json()["commentary_options"]}
        assert "bpm" not in opts_public["phys"]
        assert "HRV" not in opts_public["phys"]
        assert "bpm" not in opts_public["journal"]
        assert "HRV" not in opts_public["journal"]
    finally:
        if os.path.isdir(avatar_dir):
            for fname in os.listdir(avatar_dir):
                if uid in fname and fname.startswith("wxacode_share_"):
                    try:
                        os.remove(os.path.join(avatar_dir, fname))
                    except OSError:
                        pass


def test_self_healing_needs_canova_critique_refresh():
    stale_samples = [
        "【基础有氧跑】8.0km @ 5:30/km 🌟【亮点】稳健完成 8.0km，进步扎实！ 💡 课后适度拉伸放松。",
        "【稳态有氧进阶】分段表现：稳定跑 10.0k(5:15)。 💡 分段节奏清晰，跑后做好小腿与臀中肌放松拉伸。",
        "【山地有氧跑】分段表现：有氧跑 12.0k(6:40)。 💡 越野跑中遇爬升路段主动切换徒步（Power Hiking）节能、下坡注意小步高频缓震。",
        "📋【课表核对】达成率 100%。 💡 主课分段配速与生理负荷控制理想，课后做好拉伸与碳水补充。",
        "【长距离有氧耐力】分段表现：稳态 22.0k(5:10)。 💡 核心段心率解耦率仅 2.1%，有氧耐力稳固。",
        "⚡【混氧门槛突破】分段表现：巡航 10.0k(4:25)。 💡 补充碳水。 ⚡【精英专项进阶】专项指标达成，紧扣配速收敛。",
    ]
    for s in stale_samples:
        assert LocalStore._needs_canova_critique_refresh(s, None, strict_format_upgrade=False) is True

    v4_critique = (
        "【稳态有氧进阶】10.0km @ 5:12/km（均心143bpm），后程稳控有氧经济性。"
        " 🌟【亮点】本周第3练推进至28/60km。"
        " 💡 睡眠7.5h(84分)·HRV 63ms(稳居基线)、CTL 42·TSB -8(状态平衡)，跑后拉伸腘绳肌。"
        " ⚡ 距上海马拉D-18（专项决战期），明日乳酸门槛跑12km(4:30/km)。"
    )
    assert LocalStore._needs_canova_critique_refresh(v4_critique, None, strict_format_upgrade=False) is False
    assert LocalStore._needs_canova_critique_refresh('{"summary": "跑者手记"}', None, strict_format_upgrade=False) is False
    assert LocalStore._needs_canova_critique_refresh(
        "【交叉训练 · 游泳 (Cross-Training / Swim)】完成1500米无冲击有氧刺激。",
        None,
        strict_format_upgrade=False,
    ) is False
    assert LocalStore._needs_canova_critique_refresh(
        "🏆【赛事复盘 · 上马】3:14:20强势完赛，成功达成目标。",
        None,
        strict_format_upgrade=False,
    ) is False
    assert LocalStore._needs_canova_critique_refresh(
        "今天世纪公园晨跑十公里，秋高气爽非常舒服！",
        None,
        strict_format_upgrade=False,
    ) is False
