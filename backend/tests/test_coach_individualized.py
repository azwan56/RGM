import pytest
from datetime import date
from utils.running_metrics import (
    get_age_from_dob,
    format_duration,
    get_race_specific_zones,
    get_canova_zones,
    calculate_trimp,
    compute_ctl_atl_tsb
)
from routers.coach import resolve_race_category, parse_time_str
from utils.local_store import LocalStore

def test_get_age_from_dob():
    today = date.today()
    # Person born exactly 30 years ago
    birth_year = today.year - 30
    dob = f"{birth_year}-{today.month:02d}-{today.day:02d}"
    age = get_age_from_dob(dob)
    assert age == 30

    # Person born 55 years ago
    dob_55 = f"{today.year - 55}-01-01"
    age_55 = get_age_from_dob(dob_55)
    assert age_55 in [55, 56]

    # None and empty
    assert get_age_from_dob(None) is None
    assert get_age_from_dob("") is None

def test_format_duration():
    assert format_duration(11370) == "3:09:30"
    assert format_duration(5457) == "1:30:57"
    assert format_duration(2426) == "40:26"
    assert format_duration(1164) == "19:24"
    assert format_duration(0) == "—"
    assert format_duration(None) == "—"

def test_parse_time_str():
    assert parse_time_str("3:09:30") == 11370
    assert parse_time_str("01:30:00") == 5400
    assert parse_time_str("42:00") == 2520
    assert parse_time_str("8:00:00") == 28800
    assert parse_time_str(None) is None

def test_resolve_race_category():
    cat1, name1 = resolve_race_category("武功山 50K 越野赛")
    assert cat1 == "trail"
    assert "越野" in name1

    cat2, name2 = resolve_race_category("柴古唐斯 Plus")
    assert cat2 == "trail"

    cat3, name3 = resolve_race_category("无锡马拉松")
    assert cat3 == "marathon"

    cat4, name4 = resolve_race_category("上海半程马拉松")
    assert cat4 == "half"

    cat5, name5 = resolve_race_category("10公里场地突破")
    assert cat5 == "10k"

    # Crucial test: "上海马拉松" even if race_type is mistakenly passed as "half"
    cat6, name6 = resolve_race_category("上海马拉松", race_type="half", target_time_seconds=11370)
    assert cat6 == "marathon", "上海马拉松 without 半 must resolve to marathon even if race_type is half"

def test_get_race_specific_zones():
    # Trail zones use HRR and climbing/downhill descriptions
    trail_zones = get_race_specific_zones("trail", max_hr=190, rest_hr=56)
    assert "recovery" in trail_zones
    assert "fundamental" in trail_zones
    assert "Power Hiking" in trail_zones["fundamental"]["desc"]
    assert "离心" in trail_zones["specific"]["desc"]
    assert "心率" in trail_zones["recovery"]["range"]

    # Half Marathon zones use pace
    half_zones = get_race_specific_zones("half", target_time_seconds=5400) # 1:30:00
    assert "specific" in half_zones
    assert "/km" in half_zones["specific"]["range"]
    assert "LT2" in half_zones["specific"]["name"]

    # Marathon zones use MP
    marathon_zones = get_race_specific_zones("marathon", target_time_seconds=11370)
    assert "specific" in marathon_zones
    # 3:09:30 marathon pace is 4:29/km, range should be ~4:29 - 4:17
    assert "4:29" in marathon_zones["specific"]["range"] or "4:17" in marathon_zones["specific"]["range"]

    # Crucial test: Mismatched time (3:09:30 passed with half marathon)
    # Must auto-correct to marathon distance so pace is ~4:29/km, NOT 8:59/km!
    mismatch_zones = get_race_specific_zones("half", target_time_seconds=11370)
    assert "4:29" in mismatch_zones["specific"]["range"] or "4:17" in mismatch_zones["specific"]["range"]
    assert "11:31" not in mismatch_zones["recovery"]["range"], "Pace must not be 11:31 /km for a 3:09 runner"
    assert "/km" in marathon_zones["specific"]["range"]

def test_training_load_tsb_decay():
    """Verify that rest days properly decay ATL and CTL."""
    daily_series = [
        ("2026-01-01", 100.0), # Big workout
        ("2026-01-02", 0.0),   # Rest day
        ("2026-01-03", 0.0),   # Rest day
        ("2026-01-04", 0.0),   # Rest day
    ]
    res = compute_ctl_atl_tsb(daily_series)
    assert len(res) == 4
    # On Jan 1: ATL jumped
    atl_day1 = res[0]["atl"]
    # On Jan 4: ATL decayed significantly
    atl_day4 = res[3]["atl"]
    assert atl_day4 < atl_day1
    # TSB on Jan 4 should be higher (fresher) than on Jan 1
    assert res[3]["tsb"] > res[0]["tsb"]

def test_generate_canova_critique_individualized():
    # 1. Trail run with 800m elevation gain
    trail_act = {
        "user_id": "u_test_runner",
        "distance_meters": 18000,
        "avg_pace_str": "6:30",
        "average_heartrate": 150,
        "elevation_gain_meters": 850,
        "name": "武功山拉练"
    }
    trail_critique = LocalStore.generate_canova_critique(trail_act)
    assert "爬升" in trail_critique
    assert "离心" in trail_critique or "Power Hiking" in trail_critique

    # 2. Master runner aged 55
    master_profile = {
        "id": "u_master_runner",
        "max_heart_rate": 165,
        "resting_heart_rate": 52,
        "date_of_birth": "1970-01-01"
    }
    road_act = {
        "user_id": "u_master_runner",
        "distance_meters": 22000,
        "avg_pace_str": "5:15",
        "average_heartrate": 140,
        "elevation_gain_meters": 10,
        "name": "周末长距离"
    }
    master_critique = LocalStore.generate_canova_critique(road_act, profile=master_profile)
    assert "72 小时" in master_critique or "大师组" in master_critique or "超量恢复" in master_critique

def test_analyze_multi_race_calendar_and_strategy():
    from utils.running_metrics import analyze_multi_race_calendar
    from routers.coach import generate_fallback_multi_race_strategy

    # 1. Test multi-race calendar with conflicts, pairings, and trail cross-discipline
    races = [
        {"name": "上海半马", "race_type": "half", "race_date": "2026-10-18", "target_time": "1:32:00", "priority": "B"},
        {"name": "无锡马拉松", "race_type": "marathon", "race_date": "2026-11-15", "target_time": "3:15:00", "priority": "A"},
        {"name": "武功山 50K", "race_type": "trail", "race_date": "2026-11-29", "target_time": "8:00:00", "priority": "A"}
    ]
    res = analyze_multi_race_calendar(races)
    assert res["total_upcoming"] == 3
    # Shanghai Half is B
    assert res["races"][0]["tier"] == "B"
    # Wuxi Marathon is A
    assert res["races"][1]["tier"] == "A"
    # Golden pairing between Shanghai Half & Wuxi Marathon (28 days)
    assert len(res["pairings"]) == 1
    assert "黄金以赛代练配对" in res["pairings"][0]["strategy"]
    # Conflict between Wuxi Marathon & WuGongShan 50K (14 days < 21 days)
    assert len(res["conflicts"]) == 1
    assert "赛程冲突警报" in res["conflicts"][0]["warning"]
    # Cross discipline transition between Wuxi (road) and WuGongShan (trail)
    assert len(res["cross_discipline"]) == 1
    assert "跨赛道专项切换" in res["cross_discipline"][0]["transition_tip"]

    # 2. Test fallback strategy generator
    strat = generate_fallback_multi_race_strategy(res, "无锡马拉松", "marathon")
    assert "macro_cycle_overview" in strat
    assert len(strat["race_timeline_advice"]) == 3
    assert strat["race_timeline_advice"][0]["race_name"] == "上海半马"
    assert strat["race_timeline_advice"][0]["tier"] == "B"
    assert "conflict_resolution" in strat
    assert "赛程冲突警报" in strat["conflict_resolution"]

def test_update_race_priority_and_deduplication():
    from routers.coach import update_coach_race_priority, CoachRacePriorityRequest, CoachAnalysisRequest, generate_coach_analysis
    import uuid
    test_uid = f"u_test_pri_{uuid.uuid4().hex[:8]}"
    
    # 1. Setup profile and 2 races
    LocalStore.upsert_profile(test_uid, {"display_name": "多赛测试跑者"})
    r1_id = LocalStore.upsert_race_plan(test_uid, {
        "name": "武功山",
        "race_type": "trail",
        "race_date": "2026-11-01",
        "target_time": "8:00:00",
        "priority": "A"
    })
    r2_id = LocalStore.upsert_race_plan(test_uid, {
        "name": "灵鹫山",
        "race_type": "trail",
        "race_date": "2026-10-15",
        "target_time": "7:30:00",
        "priority": "A"
    })

    # 2. Adjust Lingjiushan priority to "B"
    res = update_coach_race_priority(CoachRacePriorityRequest(uid=test_uid, race_id=r2_id, priority="B"))
    assert res["success"] is True
    # Verify in DB
    updated_races = LocalStore.get_race_plans(test_uid)
    r2_updated = next(r for r in updated_races if r["id"] == r2_id)
    assert r2_updated["priority"] == 2

    # 3. Test Deduplication: calling analysis with target_race="武功山 50K" should match "武功山" without duplicating
    analysis = generate_coach_analysis(CoachAnalysisRequest(
        uid=test_uid,
        target_race="武功山 50K",
        target_time="8:00:00",
        race_type="trail"
    ))
    # Should only have 2 races, not 3!
    upcoming_races = analysis["multi_race_analysis"]["races"]
    assert len(upcoming_races) == 2
    race_names = [r["name"] for r in upcoming_races]
    assert race_names.count("武功山") == 1
    assert "武功山 50K" not in race_names or race_names.count("武功山 50K") == 1
    # Check that ID is preserved in timeline advice
    timeline = analysis["multi_race_strategy"]["race_timeline_advice"]
    assert len(timeline) == 2
    assert all("id" in t and t["id"] for t in timeline)

