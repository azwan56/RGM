from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from firebase_config import db
import os
import json
import asyncio

router = APIRouter()

_api_key = os.getenv("GEMINI_API_KEY")
_gemini_base_url = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com")

# Model preference order — try these in sequence
_MODEL_CANDIDATES = [
    "gemini-2.5-flash",          # Latest, confirmed working
    "gemini-2.5-flash-lite",     # Lightweight variant
    "gemini-flash-latest",       # Alias for latest flash
]
_resolved_model = None  # Will be set on first successful call

import requests as http_requests

def _gemini_generate(prompt: str, temperature: float = 0.6, max_tokens: int = 6000, response_json: bool = True) -> dict:
    """Call Gemini REST API directly, bypassing SDK version issues."""
    global _resolved_model

    models_to_try = [_resolved_model] if _resolved_model else _MODEL_CANDIDATES

    last_error = None
    for model_name in models_to_try:
        # v1 does NOT support responseMimeType, so only use v1beta for JSON mode
        api_versions = ["v1beta"] if response_json else ["v1beta", "v1"]
        for api_ver in api_versions:
            url = f"{_gemini_base_url}/{api_ver}/models/{model_name}:generateContent?key={_api_key}"
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                },
            }
            if response_json:
                body["generationConfig"]["responseMimeType"] = "application/json"

            try:
                resp = http_requests.post(url, json=body, timeout=60)
                if resp.status_code == 200:
                    _resolved_model = model_name  # Cache working model
                    data = resp.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return {"text": text, "model": model_name, "api_version": api_ver}
                else:
                    last_error = f"{model_name}@{api_ver}: {resp.status_code} {resp.text[:200]}"
                    print(f"[gemini] {last_error}")
                    # If cached model is gone (404), clear cache and retry all candidates
                    if resp.status_code == 404 and _resolved_model:
                        print(f"[gemini] Cached model {_resolved_model} is gone, clearing cache")
                        _resolved_model = None
                        return _gemini_generate(prompt, temperature, max_tokens, response_json)
            except Exception as e:
                last_error = f"{model_name}@{api_ver}: {e}"
                print(f"[gemini] {last_error}")

    raise Exception(f"All Gemini models failed. Last error: {last_error}")


@router.get("/debug-models")
async def debug_models():
    """List available Gemini models for diagnostics."""
    results = {}
    for api_ver in ["v1beta", "v1"]:
        url = f"{_gemini_base_url}/{api_ver}/models?key={_api_key}"
        try:
            resp = http_requests.get(url, timeout=10)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                results[api_ver] = [m.get("name", "") for m in models if "generateContent" in str(m.get("supportedGenerationMethods", []))]
            else:
                results[api_ver] = f"Error {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            results[api_ver] = str(e)
    return results

class CoachRequest(BaseModel):
    uid: str

# ── Firestore helpers (run in thread pool) ────────────────────────────────────

def _fetch_leaderboard(uid: str):
    doc = db.collection("leaderboard").document(uid).get()
    return doc.to_dict() if doc.exists else None

def _fetch_goal(uid: str):
    doc = db.collection("users").document(uid).collection("goals").document("current").get()
    return doc.to_dict() if doc.exists else None

def _fetch_recent_activities(uid: str, n: int = 5):
    docs = (
        db.collection("users").document(uid)
        .collection("activities")
        .order_by("start_date_local", direction="DESCENDING")
        .limit(n)
        .stream()
    )
    return [d.to_dict() for d in docs]

def _build_runs_str(acts: list) -> str:
    if not acts:
        return "No recent activities."
    lines = [
        f"{a.get('start_date_local','')[:10]} "
        f"{a.get('distance_km',0)}km "
        f"@{a.get('avg_pace','?')}/km "
        f"HR:{a.get('avg_heart_rate',0)}bpm "
        f"Elev:{a.get('total_elevation_gain',0)}m"
        for a in acts
    ]
    return " | ".join(lines)

_FALLBACK = {
    "status": "继续加油 💪",
    "summary": "你的训练保持了很好的一致性！继续专注跑姿，循序渐进地提升吧。",
    "encouragement": "每一步都是进步，坚持就是胜利！",
    "actionable_tips": [
        "80% 的跑步保持轻松配速，能聊天的节奏最好",
        "注意补水和睡眠，恢复和训练同样重要",
        "每周跑量增幅不超过 10%，循序渐进",
        "每周安排 1 次速度训练（间歇跑或节奏跑）提升心肺能力",
    ],
    "training_principles": [
        {"title": "有氧优先（80/20法则）", "detail": "80% 的训练量以 Zone 2 轻松有氧为主，保持能聊天的节奏，避免长期高强度累积疲劳。"},
        {"title": "渐进超负荷", "detail": "每周跑量增幅不超过 10%，每 3-4 周安排一次减量周（跑量降至前一周的 60-70%），让身体充分适应。"},
        {"title": "质量训练", "detail": "每周保留 1-2 次高强度课（节奏跑或间歇跑），同步提升速度和乳酸阈值。"},
        {"title": "力量与柔韧", "detail": "每周 2 次核心力量训练（15-20 分钟），加强臀部、核心、小腿力量，预防跑步常见伤病。"},
    ],
    "weekly_cycle": [
        {"week": 1, "phase": "积累", "focus": "建立有氧基础，以轻松配速积累跑量", "key_session": "长距离慢跑 (LSD)", "volume_note": "维持当前跑量"},
        {"week": 2, "phase": "积累", "focus": "加入节奏跑，提升有氧阈值", "key_session": "节奏跑 Tempo Run", "volume_note": "跑量+5-8%"},
        {"week": 3, "phase": "强化", "focus": "间歇训练提升速度，长距离跑进一步延长", "key_session": "间歇跑 Interval", "volume_note": "跑量+5%"},
        {"week": 4, "phase": "恢复", "focus": "减量恢复，消化前三周训练刺激", "key_session": "轻松跑 + 拉伸放松", "volume_note": "跑量降至60-70%"},
    ],
    "key_metrics": {
        "target_long_run_pct": "周跑量的 30-35%",
        "easy_run_pct": "全部跑量的 75-80%",
        "max_weekly_increase": "10%"
    }
}

# ── Race Knowledge Base ───────────────────────────────────────────────────────

_RACE_KNOWLEDGE = {
    "10k": {
        "race_type": "10K 路跑", "difficulty_level": "初级",
        "total_distance": "10 公里", "elevation_gain": "通常 <100m",
        "key_demands": ["速度耐力（VO2max）", "乳酸阈值能力", "起跑配速控制"],
        "min_weekly_km": 30, "recommended_weekly_km": "30-50km",
        "climate_notes": "注意比赛日温湿度对配速影响",
    },
    "half_marathon": {
        "race_type": "半程马拉松", "difficulty_level": "中级",
        "total_distance": "21.1 公里", "elevation_gain": "通常 <200m",
        "key_demands": ["有氧耐力", "乳酸阈值跑能力", "配速分配策略", "赛中补给"],
        "min_weekly_km": 40, "recommended_weekly_km": "40-65km",
        "climate_notes": "赛中每5km补水，携带1-2个能量胶",
    },
    "full_marathon": {
        "race_type": "全程马拉松", "difficulty_level": "高级",
        "total_distance": "42.195 公里", "elevation_gain": "200-500m",
        "key_demands": ["长距离有氧耐力", "糖原储备与补给策略", "撞墙期心理应对", "负分配配速策略", "赛前需2-3次30km+拉练"],
        "min_weekly_km": 50, "recommended_weekly_km": "50-80km",
        "climate_notes": "赛前3天碳水加载，每5km补水，每45分钟补能量胶",
    },
    "gobi": {
        "race_type": "戈壁挑战赛（连续3天120K竞技赛事）", "difficulty_level": "极限",
        "total_distance": "120km（连续3天，每天约40K）", "elevation_gain": "累计1000-2000m+（戈壁沙地）",
        "key_demands": [
            "连续3天背靠背超长距离作战", "沙地/砾石地形适应",
            "极端高温（40°C+）与风沙耐受", "每日快速恢复能力",
            "装备负重管理", "水分与电解质管理", "3天持续心理韧性",
        ],
        "min_weekly_km": 60, "recommended_weekly_km": "60-100km",
        "climate_notes": "高温40°C+需热适应训练；昼夜温差>20°C；需防沙面罩和护目镜；每日恢复流程关键",
    },
    "trail_50k": {
        "race_type": "越野跑 50K", "difficulty_level": "高级",
        "total_distance": "50 公里", "elevation_gain": "通常 2000-3000m+",
        "key_demands": ["山地爬升/下坡技术", "越野地形适应", "长距离耐力", "补给策略", "越野装备使用"],
        "min_weekly_km": 50, "recommended_weekly_km": "50-80km",
        "climate_notes": "山区天气多变，需备雨衣、保暖层、头灯",
    },
    "trail_100k": {
        "race_type": "越野跑 100K", "difficulty_level": "极限",
        "total_distance": "100 公里", "elevation_gain": "通常 4000-6000m+",
        "key_demands": [
            "超长距离耐力（15-24小时）", "大量爬升与Power Hiking",
            "夜跑能力", "全天候装备管理", "分段补给计划", "低谷期心理应对",
        ],
        "min_weekly_km": 60, "recommended_weekly_km": "60-100km",
        "climate_notes": "需夜间越野经验，山区气候多变，携带完整强制装备",
    },
    "trail_100m": {
        "race_type": "越野跑 100英里（UTMB级别）", "difficulty_level": "极限",
        "total_distance": "约170公里", "elevation_gain": "8000-10000m+（UTMB约10000m+）",
        "key_demands": [
            "超极限耐力（30-46小时持续运动）", "巨量累计爬升（10000m+）与Power Hiking",
            "多次夜跑与睡眠管理", "极端天气应对（暴风雨、低温、大风）",
            "全程分段补给（含固体食物，每站换装）", "强制装备负重（3-5kg）",
            "30+小时心理极限挑战", "高海拔适应（2000-2600m+）",
        ],
        "min_weekly_km": 80, "recommended_weekly_km": "80-120km",
        "climate_notes": "穿越高山，海拔500-2600m；暴风雨/低温/大风；经历2+夜晚需睡眠策略；高海拔需调整配速",
    },
}


def _fetch_training_summary(uid: str, weeks: int = 8) -> dict:
    """Comprehensive training analysis over the past N weeks."""
    from datetime import date, timedelta
    from collections import defaultdict

    cutoff = (date.today() - timedelta(weeks=weeks)).isoformat()
    docs = (
        db.collection("users").document(uid)
        .collection("activities")
        .where("start_date_local", ">=", cutoff)
        .order_by("start_date_local", direction="DESCENDING")
        .limit(300)
        .stream()
    )
    acts = [d.to_dict() for d in docs]

    if not acts:
        return {"avg_weekly_km": 0, "total_runs": 0, "weeks": weeks}

    # ── Core aggregation ──
    total_km = 0; total_elev = 0; total_time = 0
    hr_vals = []; pace_vals = []; distances = []
    trail_km = 0; trail_elev = 0; trail_runs = 0
    road_km = 0; road_runs = 0
    max_hr_seen = 0; longest_run = 0
    weekly_bins = defaultdict(lambda: {"km": 0, "runs": 0, "elev": 0, "hr_sum": 0, "hr_n": 0})

    for a in acts:
        km = a.get("distance_km", 0) or 0
        elev = a.get("total_elevation_gain", 0) or 0
        mt = a.get("moving_time", 0) or 0
        hr = a.get("avg_heart_rate", 0) or 0
        mhr = a.get("max_heart_rate", 0) or 0
        name = (a.get("name", "") or "").lower()

        total_km += km; total_elev += elev; total_time += mt
        distances.append(km)
        if km > longest_run:
            longest_run = km
        if hr > 0:
            hr_vals.append(hr)
        if mhr > max_hr_seen:
            max_hr_seen = mhr
        if km > 0 and mt > 0:
            pace_vals.append(mt / km / 60)  # min/km

        # Trail vs road detection
        is_trail = any(kw in name for kw in ["trail", "越野", "山", "hill", "mountain"])
        if elev > 30 and km > 0 and (elev / km) > 20:  # >20m/km elevation = trail-like
            is_trail = True
        if is_trail:
            trail_km += km; trail_elev += elev; trail_runs += 1
        else:
            road_km += km; road_runs += 1

        # Weekly bin (ISO week)
        ds = a.get("start_date_local", "")[:10]
        if ds:
            try:
                d = date.fromisoformat(ds)
                wk = d.isocalendar()[1]
                yk = f"{d.year}-W{wk:02d}"
                weekly_bins[yk]["km"] += km
                weekly_bins[yk]["runs"] += 1
                weekly_bins[yk]["elev"] += elev
                if hr > 0:
                    weekly_bins[yk]["hr_sum"] += hr
                    weekly_bins[yk]["hr_n"] += 1
            except ValueError:
                pass

    total_runs = len(acts)
    avg_weekly_km = round(total_km / weeks, 1)

    # ── Weekly trend (is volume increasing/stable/decreasing?) ──
    sorted_weeks = sorted(weekly_bins.keys())
    weekly_kms = [weekly_bins[w]["km"] for w in sorted_weeks]
    trend = "stable"
    if len(weekly_kms) >= 4:
        first_half = sum(weekly_kms[:len(weekly_kms)//2]) / max(1, len(weekly_kms)//2)
        second_half = sum(weekly_kms[len(weekly_kms)//2:]) / max(1, len(weekly_kms) - len(weekly_kms)//2)
        if second_half > first_half * 1.15:
            trend = "increasing"
        elif second_half < first_half * 0.85:
            trend = "decreasing"

    # ── Consistency: how many weeks had ≥3 runs ──
    active_weeks = sum(1 for w in weekly_bins.values() if w["runs"] >= 3)
    consistency = round(active_weeks / max(1, len(weekly_bins)) * 10)

    # ── Avg rest days per week ──
    avg_runs_per_week = total_runs / weeks
    avg_rest_days = round(7 - avg_runs_per_week, 1)

    # ── Pace formatting ──
    def _fmt_pace(min_per_km):
        m = int(min_per_km)
        s = int((min_per_km - m) * 60)
        return f"{m}:{s:02d}"

    avg_pace = _fmt_pace(sum(pace_vals) / len(pace_vals)) if pace_vals else "—"
    avg_hr = round(sum(hr_vals) / len(hr_vals)) if hr_vals else 0

    # ── Weekly breakdown (last 4 weeks for display) ──
    recent_weeks = []
    for wk in sorted_weeks[-4:]:
        wd = weekly_bins[wk]
        whr = round(wd["hr_sum"] / wd["hr_n"]) if wd["hr_n"] > 0 else 0
        recent_weeks.append({
            "week": wk, "km": round(wd["km"], 1),
            "runs": wd["runs"], "elevation": round(wd["elev"]),
            "avg_hr": whr,
        })

    return {
        "weeks": weeks,
        "total_runs": total_runs,
        "total_km": round(total_km, 1),
        "avg_weekly_km": avg_weekly_km,
        "avg_run_distance": round(total_km / total_runs, 1) if total_runs else 0,
        "longest_run": round(longest_run, 1),
        "total_elevation": round(total_elev),
        "avg_elevation_per_run": round(total_elev / total_runs) if total_runs else 0,
        "avg_pace": avg_pace,
        "avg_heart_rate": avg_hr,
        "max_heart_rate_seen": max_hr_seen,
        "trail_runs": trail_runs,
        "road_runs": road_runs,
        "trail_km": round(trail_km, 1),
        "road_km": round(road_km, 1),
        "trail_elevation": round(trail_elev),
        "volume_trend": trend,
        "consistency_score": consistency,
        "avg_rest_days_per_week": avg_rest_days,
        "avg_runs_per_week": round(avg_runs_per_week, 1),
        "recent_weeks": recent_weeks,
    }


def _build_race_analysis(rtype, rname, avg_weekly_km):
    """Build race analysis section from knowledge base + actual weekly km."""
    race_info = _RACE_KNOWLEDGE.get(rtype, {})
    if not race_info:
        return None

    est_weekly = round(avg_weekly_km)
    min_weekly = race_info.get("min_weekly_km", 40)

    if est_weekly >= min_weekly:
        fitness_gap = f"当前预估周跑量约{est_weekly}km，已达赛事建议最低{min_weekly}km+。基础跑量充足，重点转向专项能力提升。"
        readiness = min(10, round(est_weekly / min_weekly * 6.5))
    elif est_weekly >= min_weekly * 0.6:
        fitness_gap = f"当前预估周跑量约{est_weekly}km，距赛事建议{min_weekly}km还差约{min_weekly - est_weekly}km/周。基础尚可但需循序渐进提升跑量。"
        readiness = max(3, round(est_weekly / min_weekly * 7))
    else:
        fitness_gap = f"当前预估周跑量约{est_weekly}km，距赛事建议{min_weekly}km差距较大。需从有氧基础开始系统训练，切勿急于加量。"
        readiness = max(1, round(est_weekly / min_weekly * 5))

    return {
        "race_name": rname,
        "race_type": race_info["race_type"],
        "difficulty_level": race_info["difficulty_level"],
        "total_distance": race_info["total_distance"],
        "elevation_gain": race_info["elevation_gain"],
        "key_demands": race_info["key_demands"],
        "climate_notes": race_info["climate_notes"],
        "recommended_weekly_km": race_info["recommended_weekly_km"],
        "fitness_gap": fitness_gap,
        "readiness_score": readiness,
    }


# ── Endpoint ──────────────────────────────────────────────────────────────────

def _build_race_fallback(nearest_race, nearest_days, runner_name, stats, avg_weekly_km=0):
    """Generate race-specific fallback advice when Gemini API is unavailable."""
    if not nearest_race or nearest_days > 120:
        return {
            **_FALLBACK,
            "summary": f"{runner_name}，你已完成 {stats.get('total_distance_km', 0)} 公里，保持节奏！"
                       if stats else _FALLBACK["summary"],
        }

    rtype = nearest_race.get("type", "")
    rname = nearest_race.get("name", "比赛")
    rtarget = nearest_race.get("target_time", "")

    race_label = {
        "10k": "10K", "half_marathon": "半马", "full_marathon": "全马",
        "gobi": "戈壁挑战赛", "trail_50k": "越野50K",
        "trail_100k": "越野100K", "trail_100m": "越野100英里",
    }.get(rtype, rtype)

    # Phase-specific tips
    if nearest_days <= 7:
        status = "赛前倒计时 ⏳"
        summary = (
            f"{runner_name}，距{rname}（{race_label}）仅剩 {nearest_days} 天！"
            f"现在是赛前减量期，保持轻松跑维持状态即可，千万不要追求强度。"
        )
        encouragement = "信任你的训练，你已经准备好了！"
        tips = [
            f"跑量降至平时的 30-40%，每次跑步不超过 30-40 分钟",
            "赛前 2 天完全休息或仅做 15 分钟慢跑 + 动态拉伸",
            "调整作息，确保赛前连续 3 晚睡够 7-8 小时",
            "准备比赛装备清单：号码布、能量胶、凡士林、备用袜子",
        ]
        if rtype in ("gobi", "trail_100k", "trail_100m", "trail_50k"):
            tips.append("检查越野装备：头灯电池、水袋、应急毯、急救包")
        if rtarget:
            tips.append(f"回顾目标配速 {rtarget}，比赛前半段保守，后半段发力")

    elif nearest_days <= 14:
        status = "赛前调整期 📋"
        summary = (
            f"{runner_name}，距{rname}还有 {nearest_days} 天，"
            f"进入赛前调整期。减量但不停跑，1-2 次短距离配速跑验证状态。"
        )
        encouragement = "减量期的不安是正常的，相信过程！"
        tips = [
            "本周跑量减至高峰期的 50-60%，以轻松跑为主",
            f"安排 1 次 5-8km 的{race_label}目标配速跑，验证体感",
            "增加碳水摄入比例，赛前 3 天进行糖原补充",
            "提前研究赛道路线、补给站位置和海拔变化",
        ]
        if rtype in ("gobi", "trail_100k", "trail_100m"):
            tips.append("最后一次装备全套测试跑，确保无磨脚、背包晃动等问题")

    elif nearest_days <= 30:
        status = "备赛冲刺 🔥"
        summary = (
            f"{runner_name}，距{rname}还有 {nearest_days} 天，"
            f"这是最后的高质量训练窗口！保持强度但注意恢复，避免受伤。"
        )
        encouragement = "冲刺阶段，每一次训练都在为赛道蓄力！"
        tips = [
            f"每周安排 1 次{race_label}比赛配速的中长距离跑（15-25km）",
            "每周 1 次间歇跑或节奏跑，维持速度感",
            "注意身体信号，任何不适立即减量，保护性训练",
            "模拟比赛日流程：起床时间、赛前餐、热身节奏",
        ]
        if rtype == "full_marathon":
            tips.insert(0, "完成最后一次 30-32km 长距离拉练，之后开始逐步减量")
        elif rtype in ("gobi", "trail_100k", "trail_100m"):
            tips.insert(0, "完成最后一次 40-50km 的超长距离训练或连续 2 天背靠背长距离")

    elif nearest_days <= 60:
        status = "专项训练期 📈"
        summary = (
            f"{runner_name}，距{rname}还有 {nearest_days} 天，"
            f"正是提升比赛专项能力的关键阶段，跑量接近峰值。"
        )
        encouragement = "此刻的汗水，都会成为赛道上的底气！"
        tips = [
            f"周跑量稳定在备赛峰值，长距离拉练每周递增 2-3km",
            "每周 1-2 次比赛配速训练，找到比赛节奏",
            "加入一些高于比赛配速的间歇训练，提升乳酸阈值",
            "关注营养恢复，训练后 30 分钟内补充蛋白质和碳水",
        ]
    else:
        status = "基础储备期 💪"
        summary = (
            f"{runner_name}，距{rname}还有 {nearest_days} 天，"
            f"目前以打基础为主，稳步提升周跑量和有氧耐力。"
        )
        encouragement = "基础打得越扎实，赛道上越从容！"
        tips = [
            "80% 的跑步保持轻松配速（MAF 心率或能聊天的节奏）",
            "每周跑量增幅不超过 10%，循序渐进积累",
            "每周 1 次长距离慢跑，逐步延长到赛事距离的 60-70%",
            "加入核心力量训练和柔韧性训练，预防跑步伤病",
        ]

    # ── Build race_analysis from knowledge base ──
    race_analysis = _build_race_analysis(rtype, rname, avg_weekly_km)

    # ── Phase-specific training principles ──
    if nearest_days <= 14:
        principles = [
            {"title": "减量保状态", "detail": "跑量大幅减少但不完全停跑，保持肌肉记忆和跑感，每次跑步控制在30-40分钟内。"},
            {"title": "赛前营养加载", "detail": "赛前3天增加碳水比例至总热量60-70%，确保糖原储备充足，避免尝试新食物。"},
            {"title": "装备与赛道准备", "detail": "完成所有装备检查清单，研究赛道路线、补给站位置和海拔变化，制定配速策略。"},
        ]
    elif nearest_days <= 60:
        principles = [
            {"title": "比赛专项训练", "detail": f"针对{race_label}的特殊要求进行专项训练，模拟赛事地形和强度。"},
            {"title": "长距离递增", "detail": "每周长距离跑逐步延长，目标达到赛事距离的60-70%，建立信心和耐力储备。"},
            {"title": "配速校准", "detail": "通过节奏跑和比赛配速跑，找到适合自己的比赛节奏，避免起跑过快。"},
            {"title": "恢复与防伤", "detail": "高质量训练后安排充分恢复，加强核心力量和柔韧性训练，预防过度训练。"},
        ]
    else:
        principles = [
            {"title": "有氧基础优先（80/20法则）", "detail": "80%训练量保持Zone 2轻松有氧，建立强大的有氧引擎，为后期高强度训练打基础。"},
            {"title": "渐进超负荷", "detail": "每周跑量增幅≤10%，每3-4周安排一次减量周（降至60-70%），让身体充分适应和恢复。"},
            {"title": "长距离慢跑", "detail": "每周1次长距离慢跑（LSD），逐步延长到赛事距离的50-60%，培养脂肪供能效率。"},
            {"title": "核心力量与越野适应", "detail": "每周2次核心力量训练，加入山地/台阶训练提升爬升能力和下坡技术。"},
        ]

    # ── Phase-specific weekly cycle ──
    if nearest_days <= 14:
        weekly_cycle = [
            {"week": 1, "phase": "减量", "focus": "跑量降至峰值40-50%，以轻松跑维持状态", "key_session": "1次5-8km配速验证跑", "volume_note": "大幅减量"},
            {"week": 2, "phase": "赛前", "focus": "最后调整，赛前2天完全休息", "key_session": "赛前3天15分钟慢跑+动态拉伸", "volume_note": "最低量"},
        ]
    elif nearest_days <= 60:
        weekly_cycle = [
            {"week": 1, "phase": "强化", "focus": "保持高质量训练，长距离+专项课", "key_session": f"长距离跑 + 1次{race_label}配速训练", "volume_note": "接近峰值跑量"},
            {"week": 2, "phase": "强化", "focus": "间歇训练提升速度耐力", "key_session": "间歇跑或节奏跑", "volume_note": "维持峰值"},
            {"week": 3, "phase": "冲刺", "focus": "最后一次高强度长距离拉练", "key_session": "比赛模拟跑（赛事距离60-70%）", "volume_note": "峰值跑量"},
            {"week": 4, "phase": "减量", "focus": "开始逐步减量，保持跑感", "key_session": "轻松跑 + 短距离配速验证", "volume_note": "降至80%"},
        ]
    else:
        weekly_cycle = [
            {"week": 1, "phase": "积累", "focus": "建立有氧基础，轻松配速积累跑量", "key_session": "长距离慢跑（LSD）", "volume_note": "维持当前跑量"},
            {"week": 2, "phase": "积累", "focus": "加入节奏跑，提升有氧阈值", "key_session": "节奏跑 Tempo Run", "volume_note": "跑量+5-8%"},
            {"week": 3, "phase": "强化", "focus": "间歇训练提升速度，长距离进一步延长", "key_session": "间歇跑 Interval", "volume_note": "跑量+5%"},
            {"week": 4, "phase": "恢复", "focus": "减量恢复，消化前三周训练刺激", "key_session": "轻松跑 + 拉伸放松", "volume_note": "跑量降至60-70%"},
        ]

    # ── Key metrics ──
    rec_km = race_analysis.get("recommended_weekly_km", "40-60km") if race_analysis else "40-60km"
    key_metrics = {
        "recommended_weekly_km": rec_km,
        "easy_run_pace": "基于当前配速+30-60秒/km",
        "long_run_distance": f"赛事距离的50-70%",
        "maf_heart_rate": "180-年龄 (±5调整)",
    }

    result = {
        "status": status,
        "summary": summary,
        "encouragement": encouragement,
        "actionable_tips": tips[:5],
        "training_principles": principles,
        "weekly_cycle": weekly_cycle,
        "key_metrics": key_metrics,
    }
    if race_analysis:
        result["race_analysis"] = race_analysis
    return result

@router.post("/analyze")
async def generate_coach_feedback(req: CoachRequest):
    """
    Returns structured AI coaching feedback in Chinese.
    Parallel Firestore reads + personalized, encouraging tone.
    """
    loop = asyncio.get_event_loop()
    stats, goal_data, activities, profile, training_summary = await asyncio.gather(
        loop.run_in_executor(None, _fetch_leaderboard, req.uid),
        loop.run_in_executor(None, _fetch_goal, req.uid),
        loop.run_in_executor(None, _fetch_recent_activities, req.uid),
        loop.run_in_executor(None, _fetch_profile, req.uid),
        loop.run_in_executor(None, _fetch_training_summary, req.uid),
    )
    avg_weekly_km = training_summary.get("avg_weekly_km", 0)

    if not stats:
        return {"feedback": {
            "status": "等待数据 📊",
            "summary": "同步你的 Strava 数据，即可获得 AI 教练的专属建议！",
            "encouragement": "跑步之旅从第一步开始 🏃",
            "actionable_tips": []
        }}

    # Build rich context for personalized coaching
    goal_str = "暂未设定具体目标"
    if goal_data:
        period_cn = {"weekly": "每周", "monthly": "每月"}.get(goal_data.get("period", "monthly"), "每月")
        goal_str = (
            f"目标 {goal_data.get('target_distance', 0)} 公里/{period_cn}，"
            f"配速目标：{goal_data.get('target_pace', '未设')}"
        )

    # Profile context
    runner_name = (
        profile.get("display_name") or profile.get("strava_name")
        or profile.get("email", "").split("@")[0] or "跑者"
    ) if profile else "跑者"
    training_goal = profile.get("training_goal", "fitness") if profile else "fitness"
    years_running = profile.get("years_running", 0) if profile else 0
    # Compute age from date_of_birth, fallback to legacy 'age' field
    _dob = profile.get("date_of_birth", "") if profile else ""
    if _dob:
        try:
            from datetime import date as _d
            _born = _d.fromisoformat(_dob)
            _today = _d.today()
            age = _today.year - _born.year - ((_today.month, _today.day) < (_born.month, _born.day))
        except (ValueError, TypeError):
            age = profile.get("age", "") if profile else ""
    else:
        age = profile.get("age", "") if profile else ""

    goal_cn = {
        "fitness": "健康健身", "5k": "5K 突破", "10k": "10K 提升",
        "half": "半马训练", "full": "全马备赛", "ultra": "超马挑战",
    }.get(training_goal, training_goal)

    # Race context — multiple upcoming races
    race_type_cn = {
        "10k": "10K 路跑赛",
        "half_marathon": "半程马拉松",
        "full_marathon": "全程马拉松",
        "gobi": "戈壁挑战赛（连续3天共120K竞技赛事）",
        "trail_50k": "越野跑 50K",
        "trail_100k": "越野跑 100K",
        "trail_100m": "越野跑 100英里",
    }
    upcoming_races = profile.get("upcoming_races", []) if profile else []
    race_lines = []
    has_gobi = False
    if upcoming_races:
        from datetime import date
        for r in upcoming_races:
            rtype = race_type_cn.get(r.get("type", ""), r.get("type", ""))
            rname = r.get("name", rtype)
            rdate = r.get("date", "")
            rtarget = r.get("target_time", "")
            countdown = ""
            if rdate:
                try:
                    days = (date.fromisoformat(rdate) - date.today()).days
                    if days > 0:
                        countdown = f"（还有{days}天）"
                    elif days == 0:
                        countdown = "（今天！）"
                    else:
                        continue  # skip past races
                except ValueError:
                    pass
            line = f"  · {rname}（{rtype}）{rdate}{countdown}"
            if rtarget:
                line += f" 目标成绩：{rtarget}"
            race_lines.append(line)
            if r.get("type") == "gobi":
                has_gobi = True

    race_section = ""
    nearest_race = None
    nearest_days = 999
    if race_lines:
        race_section = "【备赛计划】\n" + "\n".join(race_lines) + "\n"
        if has_gobi:
            race_section += "⚠️ 戈壁挑战赛为连续3天共120K的高强度竞技赛事，训练要求激进，需要大量耐力储备和越野适应训练\n"
        race_section += "\n"

    # Find the nearest upcoming race for focused coaching
    if upcoming_races:
        from datetime import date
        for r in upcoming_races:
            rdate = r.get("date", "")
            if rdate:
                try:
                    days = (date.fromisoformat(rdate) - date.today()).days
                    if 0 <= days < nearest_days:
                        nearest_days = days
                        nearest_race = r
                except ValueError:
                    pass

    # Build race-specific coaching instructions
    race_coaching_instructions = ""
    if nearest_race:
        rtype = nearest_race.get("type", "")
        rname = nearest_race.get("name", "")
        rtarget = nearest_race.get("target_time", "")
        race_label = race_type_cn.get(rtype, rtype)

        # Determine training phase
        if nearest_days <= 7:
            phase = "赛前减量期"
            phase_detail = "距比赛仅剩1周以内，应大幅减量，保持状态但不追求强度。重点是休息、营养、心理准备。"
        elif nearest_days <= 14:
            phase = "赛前调整期"
            phase_detail = "距比赛2周，开始逐步减量（减至高峰期的50-60%），可安排1-2次短距离配速跑验证状态，但不追求新的训练刺激。"
        elif nearest_days <= 30:
            phase = "冲刺期"
            phase_detail = "距比赛1个月，这是最后的高质量训练窗口。保持强度但注意恢复，避免受伤。每周安排1次比赛配速跑。"
        elif nearest_days <= 60:
            phase = "专项期"
            phase_detail = "距比赛2个月，重点提升比赛专项能力。增加比赛配速训练和长距离拉练，跑量接近峰值。"
        elif nearest_days <= 120:
            phase = "基础期"
            phase_detail = "距比赛3-4个月，重点打基础。稳步提升周跑量，80%有氧 + 20%速度，建立耐力储备。"
        else:
            phase = "准备期"
            phase_detail = "距比赛尚远，可以轻松积累跑量，逐步建立训练习惯和基础体能。"

        # Race difficulty context
        race_difficulty = ""
        if rtype in ("gobi", "trail_100k", "trail_100m"):
            race_difficulty = (
                "这是一场极高难度的超长距离赛事，需要特别关注：\n"
                "  - 超长距离耐力储备（周跑量建议60-100km+）\n"
                "  - 越野地形适应训练（爬升、下坡技术）\n"
                "  - 补给策略（能量胶、电解质、固体食物搭配）\n"
                "  - 装备测试（越野鞋、背包、头灯、急救包）\n"
                "  - 心理韧性训练（长时间独处运动的心理准备）\n"
            )
            if rtype == "gobi":
                race_difficulty += (
                    "  - 戈壁特殊要素：防晒防沙、极端气候适应、连续3天恢复策略\n"
                    "  - 需要提前进行连续2-3天背靠背长距离训练\n"
                )
        elif rtype == "full_marathon":
            race_difficulty = "全程马拉松需要扎实的有氧基础，建议赛前至少完成2-3次30km+的长距离拉练。\n"
        elif rtype == "trail_50k":
            race_difficulty = "50K越野需要良好的爬升能力和下坡技术，建议增加山地训练和负重跑。\n"

        # PB target analysis
        pb_analysis = ""
        if rtarget:
            pb_analysis = f"目标成绩 {rtarget}，请根据跑者当前配速和心率数据，分析目标是否合理，给出达成目标的具体训练配速建议。\n"

        race_coaching_instructions = (
            f"\n【⚡ 重点备赛指导 — {rname or race_label}】\n"
            f"最近的比赛：{rname}（{race_label}），距今 {nearest_days} 天\n"
            f"当前阶段：{phase}\n"
            f"{phase_detail}\n"
            f"{race_difficulty}"
            f"{pb_analysis}"
            f"请围绕这场比赛的备赛需求给出有针对性的训练建议，"
            f"包括本周具体训练重点和需要注意的事项。\n\n"
        )

    # ── Build context variables used in prompt ───────────────────────────────
    runs_str = _build_runs_str(activities)
    completion_pct = stats.get("goal_completion_percentage", 0)

    # ── Training phase for plan (reuse nearest_race computed above) ──────────
    from datetime import date as _dclz
    plan_phase_block = ""
    if nearest_race:
        _rtype  = nearest_race.get("type", "")
        _rname  = nearest_race.get("name", _rtype)
        _rtarget= nearest_race.get("target_time", "")
        _rcn    = {"10k":"10K","half_marathon":"半程马拉松","full_marathon":"全程马拉松",
                   "gobi":"戈壁挑战赛（连续3天120K）","trail_50k":"越野50K",
                   "trail_100k":"越野100K","trail_100m":"越野100英里"}.get(_rtype, _rtype)
        if nearest_days <= 7:
            _phase = "赛前减量期"
            _prules = "跑量减至40%，至少3个休息日，最多1次短配速验证跑（≤5km），禁高强度。"
        elif nearest_days <= 21:
            _phase = "赛前调整期"
            _prules = f"赛前{nearest_days}天，跑量减至峰值60%，1次配速验证跑（≤8km），须有2个休息日。"
        elif nearest_days <= 42:
            _phase = "赛前冲刺期"
            _prules = f"距赛{nearest_days}天，1次目标配速中长距离（15-25km），1次间歇/节奏跑，1-2个休息日。"
        elif nearest_days <= 84:
            _phase = "专项训练期"
            _prules = "长距离+节奏跑+间歇三合一，配速向目标靠近，跑量接近峰值。"
        else:
            _phase = "基础储备期"
            _prules = "稳步堆跑量，80%轻松有氧，每周1次长距离慢跑。"
        plan_phase_block = (
            f"比赛：{_rname}（{_rcn}），还有{nearest_days}天，阶段：【{_phase}】\n"
            f"本周计划约束：{_prules}\n"
        )

    profile_vdot = profile.get("vdot") if profile else None
    profile_max_hr = profile.get("max_heart_rate", 190) if profile else 190
    profile_rest_hr = profile.get("resting_heart_rate", 60) if profile else 60
    profile_years = years_running
    profile_gender = profile.get("gender", "other") if profile else "other"
    profile_age = age

    _trend_cn = {"increasing": "上升", "stable": "平稳", "decreasing": "下降"}.get(
        training_summary.get("volume_trend", "stable"), "平稳")

    prompt = (
        "你是一位热情、专业、善于鼓励的中文跑步教练。\n"
        "请根据以下跑者信息，给出温暖、正面、具有激励性的个性化训练建议。\n"
        "回复必须是纯 JSON，不含 markdown 标记。\n\n"
        f"【跑者档案】\n"
        f"- 称呼：{runner_name}，年龄：{profile_age or '未知'}，性别：{profile_gender}，跑龄：{profile_years}年\n"
        f"- 训练目标：{goal_cn}，VDOT：{profile_vdot or '未知'}\n"
        f"- 最大心率：{profile_max_hr}，静息心率：{profile_rest_hr}\n"
        f"- 当前里程目标：{goal_str}\n\n"
        f"{race_section}"
        f"{race_coaching_instructions}"
        f"【过去8周训练统计分析】\n"
        f"- 周均跑量：{training_summary.get('avg_weekly_km', 0)} km/周\n"
        f"- 总跑次：{training_summary.get('total_runs', 0)} 次，总跑量：{training_summary.get('total_km', 0)} km\n"
        f"- 平均每跑距离：{training_summary.get('avg_run_distance', 0)} km，最长单次：{training_summary.get('longest_run', 0)} km\n"
        f"- 路跑：{training_summary.get('road_runs', 0)} 次/{training_summary.get('road_km', 0)}km，"
        f"越野跑：{training_summary.get('trail_runs', 0)} 次/{training_summary.get('trail_km', 0)}km\n"
        f"- 总海拔累积：{training_summary.get('total_elevation', 0)}m，平均每次：{training_summary.get('avg_elevation_per_run', 0)}m\n"
        f"- 8周平均配速：{training_summary.get('avg_pace', '?')}/km，平均心率：{training_summary.get('avg_heart_rate', 0)}bpm\n"
        f"- 跑量趋势：{_trend_cn}\n"
        f"- 每周平均跑步：{training_summary.get('avg_runs_per_week', 0)} 次，休息日：{training_summary.get('avg_rest_days_per_week', 0)} 天\n"
        f"- 训练一致性评分：{training_summary.get('consistency_score', 0)}/10\n\n"
        f"【本期目标完成度】\n"
        f"- 总里程：{stats.get('total_distance_km', 0)} km，目标完成：{completion_pct}%\n\n"
        f"【近期跑步记录】\n{runs_str}\n\n"
    )

    if nearest_race and nearest_days <= 120:
        prompt += (
            "⚠️ 核心要求：跑者有临近比赛！你必须：\n"
            "  1. 先在 race_analysis 中深入分析赛事的难度、强度和训练关键点\n"
            "  2. 在 summary 中评估跑者目前的体能/跑力与赛事要求的差距\n"
            "  3. 然后针对差距给出 training_principles 和 weekly_cycle\n"
            "  - 如果距比赛≤14天，重点提醒减量和赛前准备\n"
            "  - 如果有目标成绩，量化分析当前状态与目标的差距\n\n"
        )
    prompt += (
        "返回 JSON 格式如下（必须包含全部字段）：\n"
        '{\n'
    )
    # Only require race_analysis if there's an upcoming race
    if nearest_race:
        prompt += (
            '  "race_analysis": {\n'
            '    "race_name": "<赛事名称>",\n'
            '    "race_type": "<赛事类型，如：越野跑100英里/全程马拉松>",\n'
            '    "difficulty_level": "<初级|中级|高级|极限>",\n'
            '    "total_distance": "<总距离>",\n'
            '    "elevation_gain": "<累计爬升>",\n'
            '    "key_demands": ["<核心能力要求1>", "<核心能力要求2>", ...],\n'
            '    "climate_notes": "<气候/环境注意事项>",\n'
            '    "recommended_weekly_km": "<建议备赛周跑量>",\n'
            '    "fitness_gap": "<跑者当前体能与赛事要求的差距分析，2-3句话，要具体>",\n'
            '    "readiness_score": <1-10的备赛就绪评分>\n'
            '  },\n'
        )
    prompt += (
        '  "status": "<状态标签，如：备赛冲刺 🔥|稳步提升 📈|状态出色 💪|注意恢复 😴|继续加油 🏃>",\n'
        '  "summary": "<3-4句话，先评估当前体能与赛事/目标的差距，再给出本阶段训练方向>",\n'
        '  "encouragement": "<一句短小有力的鼓励金句>",\n'
        '  "actionable_tips": ["本周具体建议1（含数字）", "本周具体建议2", "建议3", "建议4"],\n'
        '  "training_principles": [\n'
        '    {"title": "<原则名称>", "detail": "<针对该跑者+赛事的具体执行说明，含配速/心率/距离参考值>"},\n'
        '    ... (共3-5条，必须针对赛事的key_demands展开)\n'
        '  ],\n'
        '  "weekly_cycle": [\n'
        '    {"week": 1, "phase": "<积累|强化|冲刺|减量>", "focus": "<目标>",\n'
        '     "key_session": "<关键课次含配速>", "volume_note": "<周跑量含数字>",\n'
        '     "tips": ["注意事项1", "注意事项2"]}\n'
        '    ... (共4周循环)\n'
        '  ],\n'
        '  "key_metrics": {\n'
        '    "recommended_weekly_km": "<如50-60km>",\n'
        '    "easy_run_pace": "<如6:00-6:30/km>",\n'
        '    "tempo_pace": "<如5:00-5:30/km>",\n'
        '    "long_run_distance": "<如25-30km>",\n'
        '    "maf_heart_rate": "<如145bpm>"\n'
        '  }\n'
        '}\n\n'
        "核心规则：\n"
        "1. 如有比赛，race_analysis 必须深入分析赛事难度、对跑者能力的具体要求\n"
        "2. fitness_gap 必须对比跑者当前数据和赛事要求，给出量化差距\n"
        "3. training_principles 必须针对赛事 key_demands 展开，不能泛泛而谈\n"
        "4. weekly_cycle 共4周，从当前周开始规划，距比赛近则体现减量\n"
        "5. key_metrics 所有数值必须基于跑者实际数据计算"
    )

    if not _api_key:
        fb = _build_race_fallback(nearest_race, nearest_days, runner_name, stats, avg_weekly_km)
        return {"feedback": fb}


    try:
        print(f"Coach prompt length: {len(prompt)} chars")
        response = await loop.run_in_executor(
            None,
            lambda: _gemini_generate(prompt, temperature=0.6, max_tokens=4000)
        )
        print(f"[coach] Used model: {response['model']}@{response['api_version']}")
        text = response["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        feedback = json.loads(text)



        if "encouragement" not in feedback:
            feedback["encouragement"] = "每一步都是进步，坚持就是胜利！"

        # ─ Save both to Firestore ─
        try:
            db.collection("users").document(req.uid).collection("coach").document("latest_analysis").set({
                **feedback,
                "saved_at": __import__("datetime").datetime.now().isoformat(),
                "nearest_race_days": nearest_days if nearest_days < 9999 else None,
                "nearest_race_name": nearest_race.get("name", "") if nearest_race else "",
            }, merge=False)
        except Exception as _save_err:
            print(f"[coach] Failed to save: {_save_err}")

        return {"feedback": feedback}

    except json.JSONDecodeError as e:
        print(f"Coach JSON parse error: {e}")
        fb = _build_race_fallback(nearest_race, nearest_days, runner_name, stats, avg_weekly_km)
        try:
            db.collection("users").document(req.uid).collection("coach").document("latest_analysis").set(
                {**fb, "saved_at": __import__("datetime").datetime.now().isoformat()}, merge=False)
        except Exception:
            pass
        return {"feedback": fb}
    except Exception as e:
        print(f"Coach generation failed: {e}")
        fb = _build_race_fallback(nearest_race, nearest_days, runner_name, stats, avg_weekly_km)
        fb["_error"] = str(e)
        try:
            db.collection("users").document(req.uid).collection("coach").document("latest_analysis").set(
                {**{k: v for k, v in fb.items() if not k.startswith("_")},
                 "saved_at": __import__("datetime").datetime.now().isoformat()}, merge=False)
        except Exception:
            pass
        return {"feedback": fb}


# ── Training Journal System ──────────────────────────────────────────────────

class JournalLogRequest(BaseModel):
    uid: str
    activity_id: str = ""
    force: bool = False

class WeeklyReviewRequest(BaseModel):
    uid: str


def _get_nearest_race_info(uid: str) -> dict:
    """Get nearest future race from goals."""
    import re
    from datetime import date as _dt
    user_ref = db.collection("users").document(uid)
    races_doc = user_ref.collection("goals").document("races").get()
    if not races_doc.exists:
        return {}
    races = races_doc.to_dict().get("upcoming", [])
    future = sorted([r for r in races if r.get("date", "") >= _dt.today().isoformat()],
                    key=lambda r: r.get("date", "9999"))
    if not future:
        return {}
    race = future[0]
    days_to = (_dt.fromisoformat(race["date"]) - _dt.today()).days if race.get("date") else 999
    return {"name": race.get("name", ""), "type": race.get("type", ""),
            "date": race.get("date", ""), "target_time": race.get("target_time", ""),
            "days_to": days_to}


def _get_or_create_journal(uid: str) -> dict:
    """Get active journal or create one based on nearest race."""
    import re
    user_ref = db.collection("users").document(uid)
    race = _get_nearest_race_info(uid)

    # Check existing active journal
    for doc in user_ref.collection("training_logs").where("status", "==", "active").limit(1).stream():
        j = doc.to_dict(); j["journal_id"] = doc.id
        # If race exists but journal is generic or for a different race → archive & recreate
        if race and race.get("name"):
            if race["name"] not in j.get("title", ""):
                user_ref.collection("training_logs").document(doc.id).update({"status": "archived"})
                break  # fall through to create new
        j["_race"] = race  # attach race info for prompt use
        return j

    # Create new journal
    title = "通用训练日志"
    race_type, race_date = "", ""
    journal_id = f"general-{__import__('datetime').date.today().year}"
    if race and race.get("name"):
        title = f"{race['name']} 备赛日志"
        race_type = race.get("type", "")
        race_date = race.get("date", "")
        slug = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]+', '-', race['name']).strip('-').lower()
        journal_id = f"{slug}-{race_date[:4]}" if race_date else slug

    data = {"title": title, "race_type": race_type, "race_date": race_date,
            "created_at": __import__("datetime").datetime.now().isoformat(), "status": "active"}
    user_ref.collection("training_logs").document(journal_id).set(data, merge=True)
    data["journal_id"] = journal_id
    data["_race"] = race
    return data


@router.post("/journal/log")
async def log_journal_entry(req: JournalLogRequest):
    """Generate AI commentary for a training session and save to journal."""
    loop = asyncio.get_event_loop()
    uid = req.uid
    user_ref = db.collection("users").document(uid)

    # 1. Get activity
    if req.activity_id:
        doc = user_ref.collection("activities").document(req.activity_id).get()
        activity = doc.to_dict() if doc.exists else None
    else:
        activity = None
        for doc in user_ref.collection("activities").order_by("start_date_local", direction="DESCENDING").limit(1).stream():
            activity = doc.to_dict()
    if not activity:
        return {"error": "No activity found"}

    # 2. Get/create journal
    journal = _get_or_create_journal(uid)
    journal_id = journal["journal_id"]
    entries_ref = user_ref.collection("training_logs").document(journal_id).collection("entries")

    # Check if entry already exists for this activity
    act_id = str(activity.get("activity_id", ""))
    entry_date = activity.get("start_date_local", "")[:10]
    existing = entries_ref.document(f"{entry_date}_{act_id}").get()
    if existing.exists and not req.force:
        return {"entry": existing.to_dict(), "journal_id": journal_id, "cached": True}

    # 3. This week's context
    from datetime import date as _dt, timedelta
    today = _dt.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    week_entries = [d.to_dict() for d in entries_ref.where("date", ">=", week_start).order_by("date").stream()]

    # 4. Training summary + user goal (parallel)
    training_summary, goal_data = await asyncio.gather(
        loop.run_in_executor(None, _fetch_training_summary, uid),
        loop.run_in_executor(None, _fetch_goal, uid),
    )

    # 5. Build prompt with rich comparison data
    km = activity.get("distance_km", 0)
    act_pace = activity.get("avg_pace", "—")
    act_hr = activity.get("avg_heart_rate", 0)
    act_elev = activity.get("total_elevation_gain", 0)
    act_max_hr = activity.get("max_heart_rate", 0)
    act_cadence = activity.get("avg_cadence", 0)
    week_km = sum(e.get("activity_snapshot", {}).get("distance_km", 0) for e in week_entries) + km
    week_runs = len(week_entries) + 1

    # Use user's actual goal for weekly target
    if goal_data and goal_data.get("target_distance"):
        goal_dist = goal_data["target_distance"]
        goal_period = goal_data.get("period", "monthly")
        if goal_period == "weekly":
            target_wk = goal_dist
        else:
            # Monthly goal → approximate weekly (÷ 4.33)
            target_wk = round(goal_dist / 4.33, 1)
    else:
        # Fallback: 105% of 8-week average
        target_wk = max(training_summary.get("avg_weekly_km", 30) * 1.05, 20)
    avg_pace_8w = training_summary.get("avg_pace", "—")
    avg_hr_8w = training_summary.get("avg_heart_rate", 0)
    avg_dist = training_summary.get("avg_run_distance", 0)
    longest = training_summary.get("longest_run", 0)
    is_trail = act_elev > 30 and km > 0 and (act_elev / km) > 15

    # Race context
    race = journal.get("_race", {})
    race_ctx = ""
    if race and race.get("name"):
        race_ctx = (
            f"【备赛目标】{race['name']}（{race.get('type','')}），"
            f"距比赛{race.get('days_to', '?')}天"
            f"{', 目标成绩：' + race['target_time'] if race.get('target_time') else ''}\n"
        )

    prev_context = ""
    for e in week_entries[-3:]:
        s = e.get("activity_snapshot", {})
        prev_context += f"- {e['date']}: {s.get('name','')} {s.get('distance_km',0)}km @{s.get('avg_pace','')}/km HR:{s.get('avg_heart_rate',0)}\n"

    prompt = (
        "你是一位专业跑步教练，正在为跑者撰写今日训练评语。\n"
        "你需要根据训练数据进行深入分析，不能只说'训练完成'。\n"
        "回复必须是纯 JSON，不含 markdown 标记。\n\n"
        f"【训练日志】{journal.get('title','训练日志')}\n"
        f"{race_ctx}"
        f"【今日训练详情】\n"
        f"- 活动名称：{activity.get('name','Run')}\n"
        f"- 距离：{km} km（8周平均每跑：{avg_dist}km，历史最长：{longest}km）\n"
        f"- 配速：{act_pace}/km（8周平均：{avg_pace_8w}/km，{'今日偏慢' if act_pace > avg_pace_8w else '今日偏快或持平'}）\n"
        f"- 平均心率：{act_hr}bpm（8周平均：{avg_hr_8w}bpm），最大心率：{act_max_hr}bpm\n"
        f"- 海拔爬升：{act_elev}m{'（越野/山地训练）' if is_trail else ''}\n"
        f"- 时长：{activity.get('duration_str','—')}\n"
        f"- 日期：{entry_date}\n\n"
        f"【本周训练进度】\n"
        f"- 本周已跑：{week_km:.1f}km / {week_runs}次，周目标约{target_wk:.0f}km（{min(100,round(week_km/target_wk*100))}%）\n\n"
        f"【跑者8周训练概况】\n"
        f"- 周均{training_summary.get('avg_weekly_km',0)}km | 路跑{training_summary.get('road_runs',0)}次 越野{training_summary.get('trail_runs',0)}次\n"
        f"- 平均配速{avg_pace_8w}/km | 平均HR:{avg_hr_8w} | 趋势：{training_summary.get('volume_trend','stable')}\n"
        f"- 一致性：{training_summary.get('consistency_score',0)}/10\n"
        f"{'【本周已有训练】' + chr(10) + prev_context if prev_context else ''}\n"
        "请分析以下维度并给出详细评语：\n"
        "1. 今日训练类型判断（轻松跑/节奏跑/间歇/长距离/恢复跑/越野）\n"
        "2. 配速与心率的匹配度（是否在合理区间）\n"
        "3. 与8周平均数据的对比（进步还是退步）\n"
        "4. 本周训练负荷是否合理\n"
        "5. 对备赛目标的贡献度\n\n"
        '返回JSON格式：\n'
        '{\n'
        '  "ai_comment": "<5-8句详细评语，必须引用具体数据（配速、心率、距离），分析训练质量和效果>",\n'
        '  "fatigue_level": "<low|moderate|high，基于心率/配速/本周累积综合判断>",\n'
        '  "performance_note": "<今日训练的核心亮点或需要注意的问题，2句话>",\n'
        '  "tomorrow_suggestion": "<明天的具体训练建议，含距离和强度>",\n'
        '  "training_type": "<轻松跑|节奏跑|间歇训练|长距离|恢复跑|越野训练|山地训练>"\n'
        '}\n'
    )

    ai = {"ai_comment": "训练完成，继续保持！", "fatigue_level": "moderate",
          "performance_note": "", "tomorrow_suggestion": "", "training_type": ""}
    if _api_key:
        try:
            resp = await loop.run_in_executor(None, lambda: _gemini_generate(prompt, temperature=0.5, max_tokens=4000))
            text = resp["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            ai = json.loads(text)
        except Exception as e:
            print(f"[journal] AI error: {e}")

    entry = {
        "date": entry_date, "entry_type": "daily",
        "activity_id": act_id,
        "activity_snapshot": {
            "name": activity.get("name", "Run"), "distance_km": km,
            "avg_pace": activity.get("avg_pace", "—"),
            "avg_heart_rate": activity.get("avg_heart_rate", 0),
            "total_elevation_gain": activity.get("total_elevation_gain", 0),
            "duration_str": activity.get("duration_str", "—"),
            "max_heart_rate": activity.get("max_heart_rate", 0),
        },
        "ai_comment": ai.get("ai_comment", ""),
        "fatigue_level": ai.get("fatigue_level", "moderate"),
        "performance_note": ai.get("performance_note", ""),
        "tomorrow_suggestion": ai.get("tomorrow_suggestion", ""),
        "training_type": ai.get("training_type", ""),
        "weekly_progress": {
            "week_km": round(week_km, 1), "week_runs": week_runs,
            "target_km": round(target_wk), "completion_pct": min(100, round(week_km / target_wk * 100)),
        },
        "created_at": __import__("datetime").datetime.now().isoformat(),
    }
    entries_ref.document(f"{entry_date}_{act_id}").set(entry)
    return {"entry": entry, "journal_id": journal_id}


class BackfillRequest(BaseModel):
    uid: str
    since_date: str = "2026-03-01"
    journal_title: str = ""


def _run_backfill_task(uid: str, since_date: str, journal_title: str):
    """Sync background task: generates AI journal entries for historical activities."""
    import re, time
    from datetime import datetime as _dt

    print(f"[backfill] Starting for uid={uid}, since={since_date}")
    user_ref = db.collection("users").document(uid)
    status_ref = user_ref.collection("meta").document("journal_backfill_status")

    try:
        # Fetch all activities since date
        acts_docs = list(
            user_ref.collection("activities")
            .where("start_date_local", ">=", since_date)
            .order_by("start_date_local")
            .limit(500)
            .stream()
        )
        activities = [d.to_dict() for d in acts_docs]
        if not activities:
            status_ref.set({"state": "done", "total": 0, "done": 0, "errors": 0,
                            "finished_at": _dt.now().isoformat()})
            print("[backfill] No activities found")
            return

        print(f"[backfill] Found {len(activities)} activities")

        # Create journal with custom title
        journal_title = journal_title or "UTMB 备赛日志"
        race = _get_nearest_race_info(uid)

        # Archive any existing active journals
        for doc in user_ref.collection("training_logs").where("status", "==", "active").limit(5).stream():
            user_ref.collection("training_logs").document(doc.id).update({"status": "archived"})

        slug = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]+', '-', journal_title).strip('-').lower()
        journal_id = slug
        user_ref.collection("training_logs").document(journal_id).set({
            "title": journal_title,
            "race_type": race.get("type", "") if race else "",
            "race_date": race.get("date", "") if race else "",
            "created_at": _dt.now().isoformat(),
            "status": "active",
        }, merge=True)
        entries_ref = user_ref.collection("training_logs").document(journal_id).collection("entries")

        status_ref.set({"state": "running", "total": len(activities), "done": 0,
                        "started_at": _dt.now().isoformat()})

        # Get training summary once (sync call)
        training_summary = _fetch_training_summary(uid)
        avg_pace_8w = training_summary.get("avg_pace", "—")
        avg_hr_8w = training_summary.get("avg_heart_rate", 0)
        avg_dist = training_summary.get("avg_run_distance", 0)
        longest = training_summary.get("longest_run", 0)

        race_ctx = ""
        if race and race.get("name"):
            race_ctx = f"【备赛目标】{race['name']}（{race.get('type','')}）\n"

        processed = 0
        errors = 0

        for activity in activities:
            act_id = str(activity.get("activity_id", ""))
            entry_date = activity.get("start_date_local", "")[:10]
            km = activity.get("distance_km", 0)
            act_elev = activity.get("total_elevation_gain", 0)
            is_trail = act_elev > 30 and km > 0 and (act_elev / km) > 15

            prompt = (
                "你是专业跑步教练，为跑者写简短训练评语。引用数据，简洁有力。\n"
                "必须返回纯JSON。\n\n"
                f"日志：{journal_title}\n{race_ctx}"
                f"日期：{entry_date} | {activity.get('name','Run')}\n"
                f"距离：{km}km（均{avg_dist}km） | 配速：{activity.get('avg_pace','—')}/km（均{avg_pace_8w}/km）\n"
                f"心率：{activity.get('avg_heart_rate',0)}bpm（均{avg_hr_8w}） | 爬升：{act_elev}m | 时长：{activity.get('duration_str','—')}\n\n"
                '返回：{"ai_comment":"<3-4句评语>","fatigue_level":"<low|moderate|high>",'
                '"performance_note":"<1句亮点>","tomorrow_suggestion":"<1句建议>",'
                '"training_type":"<轻松跑|节奏跑|间歇训练|长距离|恢复跑|越野训练|山地训练>"}\n'
            )

            ai = {"ai_comment": f"{entry_date}: {activity.get('name','Run')} {km}km 训练完成。",
                  "fatigue_level": "moderate", "performance_note": "", "tomorrow_suggestion": "",
                  "training_type": "越野训练" if is_trail else "轻松跑"}

            if _api_key:
                for attempt in range(3):  # Retry up to 3 times
                    try:
                        resp = _gemini_generate(prompt, temperature=0.5, max_tokens=2500)
                        text = resp["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                        ai = json.loads(text)
                        print(f"[backfill] {entry_date} AI OK (attempt {attempt+1})")
                        break
                    except Exception as e:
                        err_str = str(e)
                        print(f"[backfill] AI error for {entry_date} (attempt {attempt+1}): {err_str[:200]}")
                        if "429" in err_str or "Resource" in err_str or "quota" in err_str.lower():
                            wait = 10 * (attempt + 1)
                            print(f"[backfill] Rate limited, waiting {wait}s...")
                            time.sleep(wait)
                        else:
                            errors += 1
                            # Store last error for debugging
                            status_ref.set({"last_error": err_str[:300]}, merge=True)
                            break

            entry = {
                "date": entry_date, "entry_type": "daily", "activity_id": act_id,
                "activity_snapshot": {
                    "name": activity.get("name", "Run"), "distance_km": km,
                    "avg_pace": activity.get("avg_pace", "—"),
                    "avg_heart_rate": activity.get("avg_heart_rate", 0),
                    "total_elevation_gain": act_elev,
                    "duration_str": activity.get("duration_str", "—"),
                    "max_heart_rate": activity.get("max_heart_rate", 0),
                },
                "ai_comment": ai.get("ai_comment", ""),
                "fatigue_level": ai.get("fatigue_level", "moderate"),
                "performance_note": ai.get("performance_note", ""),
                "tomorrow_suggestion": ai.get("tomorrow_suggestion", ""),
                "training_type": ai.get("training_type", ""),
                "weekly_progress": {"week_km": 0, "week_runs": 0, "target_km": 0, "completion_pct": 0},
                "created_at": _dt.now().isoformat(),
            }
            entries_ref.document(f"{entry_date}_{act_id}").set(entry)
            processed += 1

            # Update progress every 3 entries
            if processed % 3 == 0:
                status_ref.set({"state": "running", "total": len(activities), "done": processed,
                                "errors": errors}, merge=True)

            # 4s delay = ~15 RPM to stay within Gemini free tier limit
            time.sleep(4)

        status_ref.set({"state": "done", "total": len(activities), "done": processed,
                        "errors": errors, "finished_at": _dt.now().isoformat()})
        print(f"[backfill] Complete: {processed}/{len(activities)}, errors={errors}")

    except Exception as e:
        print(f"[backfill] FATAL error: {e}")
        import traceback
        traceback.print_exc()
        status_ref.set({"state": "error", "error_msg": str(e),
                        "finished_at": _dt.now().isoformat()})



@router.post("/journal/backfill")
async def backfill_journal(req: BackfillRequest, background_tasks: BackgroundTasks):
    """Generate journal entries for ALL activities since a date. Runs in background."""
    from datetime import datetime as _dt
    user_ref = db.collection("users").document(req.uid)

    # Initial check
    acts_docs = list(
        user_ref.collection("activities")
        .where("start_date_local", ">=", req.since_date)
        .order_by("start_date_local")
        .limit(500)
        .stream()
    )
    if not acts_docs:
        return {"error": "No activities found", "since": req.since_date}
        
    status_ref = user_ref.collection("meta").document("journal_backfill_status")
    status_ref.set({"state": "starting", "total": len(acts_docs), "done": 0,
                    "started_at": _dt.now().isoformat()})

    background_tasks.add_task(_run_backfill_task, req.uid, req.since_date, req.journal_title)

    return {"message": f"Backfill task started for {len(acts_docs)} entries"}


@router.get("/journal/backfill-status")
def get_backfill_status(uid: str):
    """Poll backfill progress."""
    doc = db.collection("users").document(uid).collection("meta").document("journal_backfill_status").get()
    return doc.to_dict() if doc.exists else {"state": "idle"}

@router.get("/journal")
def get_journal(uid: str):
    """Get active journal with recent entries."""
    user_ref = db.collection("users").document(uid)
    journal = None; journal_id = None
    for doc in user_ref.collection("training_logs").where("status", "==", "active").limit(1).stream():
        journal = doc.to_dict(); journal_id = doc.id
    if not journal:
        return {"journal": None, "entries": []}

    cutoff = (__import__("datetime").date.today() - __import__("datetime").timedelta(days=90)).isoformat()
    entries = [d.to_dict() for d in
               user_ref.collection("training_logs").document(journal_id)
               .collection("entries").where("date", ">=", cutoff)
               .order_by("date", direction="DESCENDING").limit(60).stream()]
    journal["journal_id"] = journal_id
    return {"journal": journal, "entries": entries}


@router.post("/journal/weekly-review")
async def generate_weekly_review(req: WeeklyReviewRequest):
    """Generate weekly summary with plan adjustments."""
    loop = asyncio.get_event_loop()
    uid = req.uid
    user_ref = db.collection("users").document(uid)
    journal = _get_or_create_journal(uid)
    journal_id = journal["journal_id"]

    from datetime import date as _dt, timedelta
    today = _dt.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    entries_ref = user_ref.collection("training_logs").document(journal_id).collection("entries")
    daily = [d.to_dict() for d in entries_ref.where("date", ">=", week_start).order_by("date").stream()
             if d.to_dict().get("entry_type") == "daily"]
    if not daily:
        return {"error": "本周暂无训练记录"}

    training_summary = await loop.run_in_executor(None, _fetch_training_summary, uid)

    # Race context
    race_ctx = ""
    races_doc = user_ref.collection("goals").document("races").get()
    if races_doc.exists:
        future = sorted([r for r in races_doc.to_dict().get("upcoming", [])
                         if r.get("date", "") >= today.isoformat()], key=lambda r: r.get("date", "9999"))
        if future:
            days_to = (_dt.fromisoformat(future[0]["date"]) - today).days
            race_ctx = f"目标赛事：{future[0].get('name','')}，距比赛{days_to}天\n"

    total_km = sum(e.get("activity_snapshot", {}).get("distance_km", 0) for e in daily)
    total_elev = sum(e.get("activity_snapshot", {}).get("total_elevation_gain", 0) for e in daily)
    entries_str = "\n".join(
        f"- {e['date']}: {e.get('activity_snapshot',{}).get('name','')} "
        f"{e.get('activity_snapshot',{}).get('distance_km',0)}km "
        f"@{e.get('activity_snapshot',{}).get('avg_pace','—')}/km "
        f"HR:{e.get('activity_snapshot',{}).get('avg_heart_rate',0)} "
        f"疲劳:{e.get('fatigue_level','—')}"
        for e in daily
    )

    prompt = (
        "你是专业跑步教练，撰写本周训练总结。回复纯JSON。\n\n"
        f"【日志】{journal.get('title','')}\n{race_ctx}"
        f"【本周训练】\n{entries_str}\n"
        f"合计：{total_km:.1f}km / {len(daily)}次 / 爬升{total_elev}m\n"
        f"【8周概况】周均{training_summary.get('avg_weekly_km',0)}km | 趋势:{training_summary.get('volume_trend','stable')}\n\n"
        '返回JSON：{"summary":"<3-4句周总结>","achievements":["<亮点>"],'
        '"concerns":["<问题>"],"next_week_plan":{"focus":"<重点>",'
        '"target_km":"<建议跑量>","key_sessions":["<课次1>","<课次2>"],'
        '"adjustments":"<基于本周的调整>"},"weekly_score":<1-10>}\n'
    )

    ai = {"summary": "本周训练完成。", "achievements": [], "concerns": [],
          "next_week_plan": {"focus": "保持节奏", "target_km": str(round(training_summary.get("avg_weekly_km", 40))),
                            "key_sessions": [], "adjustments": ""}, "weekly_score": 7}
    if _api_key:
        try:
            resp = await loop.run_in_executor(None, lambda: _gemini_generate(prompt, temperature=0.5, max_tokens=1200))
            text = resp["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            ai = json.loads(text)
        except Exception as e:
            print(f"[journal] Weekly review error: {e}")

    review = {
        "date": today.isoformat(), "entry_type": "weekly_summary",
        "week_number": today.isocalendar()[1],
        "summary": ai.get("summary", ""), "achievements": ai.get("achievements", []),
        "concerns": ai.get("concerns", []), "next_week_plan": ai.get("next_week_plan", {}),
        "weekly_score": ai.get("weekly_score", 7),
        "week_stats": {"total_km": round(total_km, 1), "total_runs": len(daily), "total_elevation": round(total_elev)},
        "created_at": __import__("datetime").datetime.now().isoformat(),
    }
    entries_ref.document(f"week-{today.isocalendar()[1]:02d}-summary").set(review, merge=True)
    return {"review": review, "journal_id": journal_id}


# ── Training Plan Generator ──────────────────────────────────────────────────

class TrainingPlanRequest(BaseModel):
    uid: str


def _fetch_profile(uid: str):
    doc = db.collection("users").document(uid).get()
    return doc.to_dict() if doc.exists else {}


def _fetch_recent_14d(uid: str):
    from datetime import date, timedelta
    cutoff = (date.today() - timedelta(days=14)).isoformat()
    docs = (db.collection("users").document(uid)
              .collection("activities")
              .where("start_date_local", ">=", cutoff)
              .order_by("start_date_local", direction="DESCENDING")
              .limit(30)
              .stream())
    return [d.to_dict() for d in docs]


def _build_training_plan_fallback(total_km_14d: float, training_goal: str, upcoming_races: list) -> dict:
    """Returns a sensible template 7-day training plan when AI is unavailable."""
    from datetime import date, timedelta
    # Estimate weekly volume from last 14 days (half of 14d total)
    weekly_base = max(20, round(total_km_14d / 2))
    long_run = round(weekly_base * 0.35)
    tempo = round(weekly_base * 0.20)
    easy1 = round(weekly_base * 0.18)
    easy2 = round(weekly_base * 0.17)
    total = long_run + tempo + easy1 + easy2

    days = [
        {"day": 1, "type": "Easy", "title": "轻松恢复跑", "distance_km": easy1,
         "pace_target": "6:00-6:30", "hr_zone": "Zone 2", "duration_min": easy1 * 6,
         "description": f"热身跑2km，以轻松舒适的配速跑{easy1}km，心率保持在最大心率65-75%，冷身慢跑1km+静态拉伸10分钟。",
         "intensity": 2},
        {"day": 2, "type": "Tempo", "title": "节奏跑", "distance_km": tempo,
         "pace_target": "5:00-5:30", "hr_zone": "Zone 3-4", "duration_min": tempo * 5,
         "description": f"热身跑2km+动态拉伸，主课：{max(tempo-4, 4)}km节奏跑（比马拉松配速快30-45秒），冷身慢跑2km+拉伸。",
         "intensity": 4},
        {"day": 3, "type": "Rest", "title": "完全休息", "distance_km": 0,
         "pace_target": None, "hr_zone": None, "duration_min": 0,
         "description": "完全休息日。可做10-15分钟轻柔瑜伽或泡沫轴放松，保证睡眠质量。",
         "intensity": 0},
        {"day": 4, "type": "Easy", "title": "有氧慢跑", "distance_km": easy2,
         "pace_target": "6:00-6:30", "hr_zone": "Zone 2", "duration_min": easy2 * 6,
         "description": f"热身跑2km，以能聊天的轻松配速跑{easy2}km，专注跑姿和呼吸节奏，冷身拉伸。",
         "intensity": 2},
        {"day": 5, "type": "Interval", "title": "间歇速度训练", "distance_km": round(easy1 * 0.8),
         "pace_target": "4:30-5:00", "hr_zone": "Zone 4-5", "duration_min": round(easy1 * 0.8) * 6,
         "description": "热身跑2km，主课：6×800m间歇跑，每组间歇400m慢跑恢复，目标心率85-90%最大心率，冷身跑2km+拉伸。",
         "intensity": 5},
        {"day": 6, "type": "Long Run", "title": "长距离跑", "distance_km": long_run,
         "pace_target": "6:00-7:00", "hr_zone": "Zone 2", "duration_min": long_run * 6,
         "description": f"热身跑2km，全程保持轻松配速跑完{long_run}km，每5km补水一次，后段若体力允许可稍微提速，冷身拉伸15分钟。",
         "intensity": 3},
        {"day": 7, "type": "Recovery", "title": "恢复慢跑", "distance_km": round(easy1 * 0.7),
         "pace_target": "6:30-7:00", "hr_zone": "Zone 1-2", "duration_min": round(easy1 * 0.7) * 7,
         "description": "极轻松配速的恢复跑，心率不超过最大值的70%，以放松为主。完成后做全身拉伸和泡沫轴放松。",
         "intensity": 1},
    ]
    return {
        "plan_summary": f"基于你过去两周的训练量（{total_km_14d:.0f}km）制定的7天均衡训练计划，遵循80/20原则。",
        "weekly_km": total,
        "days": days,
    }


@router.post("/training-plan")
async def generate_training_plan(req: TrainingPlanRequest):
    """
    Generates a personalized 7-day training plan using Gemini AI.
    Uses VDOT, profile, goals, recent activities, and fitness state.
    Saves to Firestore for history.
    """
    loop = asyncio.get_event_loop()

    # ─ Fetch latest coach analysis to align plan with existing recommendations ─
    def _fetch_latest_coach_analysis(uid: str):
        doc = db.collection("users").document(uid).collection("coach").document("latest_analysis").get()
        return doc.to_dict() if doc.exists else None

    profile, goal_data, activities, stats, coach_analysis = await asyncio.gather(
        loop.run_in_executor(None, _fetch_profile, req.uid),
        loop.run_in_executor(None, _fetch_goal, req.uid),
        loop.run_in_executor(None, _fetch_recent_14d, req.uid),
        loop.run_in_executor(None, _fetch_leaderboard, req.uid),
        loop.run_in_executor(None, _fetch_latest_coach_analysis, req.uid),
    )

    if not profile:
        return {"error": "User profile not found. Please fill in your profile first."}

    # Build context
    vdot = profile.get("vdot") or None
    # Compute age from date_of_birth, fallback to legacy 'age' field
    _dob2 = profile.get("date_of_birth", "")
    if _dob2:
        try:
            from datetime import date as _d2
            _born2 = _d2.fromisoformat(_dob2)
            _today2 = _d2.today()
            age = _today2.year - _born2.year - ((_today2.month, _today2.day) < (_born2.month, _born2.day))
        except (ValueError, TypeError):
            age = profile.get("age", 30)
    else:
        age = profile.get("age", 30)
    gender = profile.get("gender", "other")
    years_running = profile.get("years_running", 0) or 0
    training_goal = profile.get("training_goal", "fitness")
    fm_pb_sec = profile.get("marathon_pb_sec", 0) or 0
    half_pb_sec = profile.get("half_pb_sec", 0) or 0
    max_hr = profile.get("max_heart_rate", 190)
    rest_hr = profile.get("resting_heart_rate", 60)

    # Activity summary
    total_km_14d = sum(a.get("distance_km", 0) for a in activities)
    run_count_14d = len(activities)
    recent_summary = []
    for a in activities[:7]:
        recent_summary.append(
            f"{a.get('start_date_local','')[:10]} "
            f"{a.get('distance_km',0):.1f}km "
            f"@{a.get('avg_pace','?')}/km "
            f"HR:{a.get('avg_heart_rate',0)}"
        )

    goal_str = "No specific target."
    if goal_data:
        goal_str = (
            f"Target {goal_data.get('target_distance',0)} km/"
            f"{goal_data.get('period','monthly')}, "
            f"pace goal: {goal_data.get('target_pace','N/A')}."
        )

    def _fmt_pb(sec):
        if not sec: return "N/A"
        h, r = divmod(sec, 3600)
        m = r // 60
        return f"{h}:{m:02d}"

    # ── Race & goal analysis — PRIMARY plan drivers ───────────────────────────
    from datetime import date as _date_cls
    upcoming_races = profile.get("upcoming_races", [])

    # Find nearest upcoming race
    nearest_race = None
    nearest_days = 9999
    for r in upcoming_races:
        rdate = r.get("date", "")
        if rdate:
            try:
                days = (_date_cls.fromisoformat(rdate) - _date_cls.today()).days
                if 0 < days < nearest_days:
                    nearest_days = days
                    nearest_race = r
            except ValueError:
                pass

    # Determine training phase from nearest race
    race_phase_block = ""
    if nearest_race:
        rtype = nearest_race.get("type", "")
        rname = nearest_race.get("name", rtype)
        rtarget = nearest_race.get("target_time", "")

        race_cn = {
            "10k": "10K", "half_marathon": "半程马拉松", "full_marathon": "全程马拉松",
            "gobi": "戈壁挑战赛（连续3天120K）", "trail_50k": "越野50K",
            "trail_100k": "越野100K", "trail_100m": "越野100英里",
        }.get(rtype, rtype)

        if nearest_days <= 7:
            phase = "赛前减量期"
            phase_rules = (
                "⚠️ 赛前最后1周！跑量减至平时40%，完全避免高强度训练。"
                "重点：轻松跑维持感觉、充分休息、赛前2天完全休息或超短慢跑。"
                "7天内【必须】安排至少3个休息日，最多1次配速验证跑（≤5km）。"
            )
        elif nearest_days <= 21:
            phase = "赛前调整期"
            phase_rules = (
                f"赛前{nearest_days}天，进入减量调整期。跑量减至峰值60%。"
                "保留1次短距离目标配速验证跑（≤8km），其余以轻松跑和休息为主。"
                "7天内【必须】安排2个休息日，禁止大量间歇或长距离拉练。"
            )
        elif nearest_days <= 42:
            phase = "赛前冲刺期"
            phase_rules = (
                f"距{rname}还有{nearest_days}天，最后高质量训练窗口！"
                "需要1次比赛配速的中长距离（15-25km），1次间歇/节奏跑。"
                f"如目标成绩{rtarget}，配速训练需贴近目标配速。"
                "7天内安排1-2个休息日，确保高质量恢复。"
            )
        elif nearest_days <= 84:
            phase = "专项训练期"
            phase_rules = (
                f"距{rname}还有{nearest_days}天，专项能力提升阶段。"
                "每周需要：1次长距离（按比赛距离60-80%），1次节奏跑，1次间歇。"
                f"若全马/超马，长距离跑优先，配速逐步向目标{rtarget or '成绩'}靠近。"
            )
        else:
            phase = "基础储备期"
            phase_rules = (
                f"距{rname}还有{nearest_days}天，以打基础为主。"
                "稳步提升周跑量，80%轻松有氧打底，每周1次长距离慢跑。"
                "不需要高强度专项训练，重点是积累有氧能力。"
            )

        race_phase_block = (
            f"\n\n{'='*50}\n"
            f"⚡ 核心训练依据 — 比赛备赛\n"
            f"{'='*50}\n"
            f"最近比赛：{rname}（{race_cn}）\n"
            f"比赛日期：{nearest_race.get('date', '')}（还有 {nearest_days} 天）\n"
            f"目标成绩：{rtarget or '未设定'}\n"
            f"当前阶段：【{phase}】\n"
            f"本周训练要求：{phase_rules}\n"
            f"{'='*50}\n"
            f"⚠️ 此计划必须完全围绕上述比赛阶段来制定，这是最高优先级！\n"
        )

    # Training goal context
    goal_cn_map = {
        "fitness": "健康健身（有氧为主，养成习惯）",
        "5k": "5K突破（速度训练为核心，800m/1km间歇）",
        "10k": "10K提速（节奏跑+间歇，提升乳酸阈）",
        "half": "半马训练（长距离拉练+配速跑）",
        "full": "全马备赛（高周跑量+多次30km+长距离）",
        "ultra": "超马挑战（极高跑量+背靠背长距离+越野适应）",
    }
    goal_cn = goal_cn_map.get(training_goal, training_goal)

    # All upcoming races list
    all_races_str = ""
    for r in upcoming_races:
        rdate = r.get("date", "")
        if rdate:
            try:
                days = (_date_cls.fromisoformat(rdate) - _date_cls.today()).days
                if days > 0:
                    all_races_str += (
                        f"\n  · {r.get('name', r.get('type',''))}（{rdate}，还有{days}天）"
                        f" 目标：{r.get('target_time','未设')}"
                    )
            except ValueError:
                pass

    # Build coach analysis context to align the plan
    coach_context = ""
    if coach_analysis:
        tips = coach_analysis.get("actionable_tips", [])
        tips_str = "\n".join(f"  · {t}" for t in tips) if tips else "  （暂无）"
        coach_context = (
            f"\n【⚠️ 必须对齐：AI教练最新分析建议（第三优先级，计划必须与此一致）】\n"
            f"  教练总结：{coach_analysis.get('summary', '')}\n"
            f"  当前状态：{coach_analysis.get('status', '')}\n"
            f"  行动建议（必须在7天计划中体现这些）：\n{tips_str}\n"
            f"  ⚠️ 7天计划的每天训练安排必须与上述建议保持一致，不能矛盾！\n"
        )

    prompt = (
        "你是一位专业的中文跑步教练，请为跑者制定一份个性化的7天训练计划。\n"
        "⚠️ 训练计划的制定优先级：① 比赛备赛阶段要求 > ② 训练目标 > ③ AI教练分析建议\n"
        "回复必须是纯 JSON，不含 markdown 标记。\n"
        f"{race_phase_block}\n"
        f"【训练目标（第二优先级）】\n"
        f"  {goal_cn}\n"
        f"  里程目标：{goal_str}\n\n"
        f"【全部赛事计划】{all_races_str or ' 无'}\n"
        f"{coach_context}\n"
        f"【跑者档案（用于校准强度）】\n"
        f"- 年龄：{age}，性别：{gender}，跑龄：{years_running}年\n"
        f"- VDOT：{vdot or '未知'}，最大心率：{max_hr}，静息心率：{rest_hr}\n"
        f"- 全马PB：{_fmt_pb(fm_pb_sec)}，半马PB：{_fmt_pb(half_pb_sec)}\n\n"
        f"【近14天体能数据（用于确认当前状态）】\n"
        f"{run_count_14d} 次跑步，共 {total_km_14d:.1f}km\n"
        f"近期跑步：{' | '.join(recent_summary) or '无近期数据'}\n"
        f"本月：{stats.get('total_distance_km',0)}km，"
        f"配速 {stats.get('avg_pace','?')}/km，"
        f"均心率 {stats.get('avg_heart_rate',0)}bpm\n\n"
        "请从明天开始生成7天训练计划，所有文本使用中文。\n"
        "返回 JSON 格式如下：\n"
        '{\n'
        '  "plan_summary": "<1-2句话，先说明当前备赛阶段/训练目标，再说本周训练重点>",\n'
        '  "weekly_km": <总公里数>,\n'
        '  "days": [\n'
        '    {\n'
        '      "day": 1,\n'
        '      "type": "<Easy|Tempo|Interval|Long Run|Recovery|Rest|Cross Training>",\n'
        '      "title": "<中文训练标题，要体现训练目的，如：赛前配速验证跑>",\n'
        '      "distance_km": <公里数，休息日为0>,\n'
        '      "pace_target": "<如 5:30-6:00，休息日为null>",\n'
        '      "hr_zone": "<如 Zone 2，休息日为null>",\n'
        '      "duration_min": <预估分钟数>,\n'
        '      "description": "<详细中文描述，必须包含：热身方式+主课内容（含具体配速/心率）+冷身方式，以及为什么安排这个训练（联系比赛或目标）>",\n'
        '      "intensity": <1-5强度>\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        "核心规则（按优先级）：\n"
        "1. 【最高优先级】若有备赛阶段要求，该阶段的训练规则必须严格执行，不可违背\n"
        "2. 每天描述中必须说明此训练如何服务于比赛目标或训练目标\n"
        "3. 安排 1-2 个休息日，遵循 80/20 原则\n"
        "4. 长距离跑安排在周末\n"
        "5. description 字段必须有详细执行步骤，不能简短！\n"
        "6. VDOT 未知时，根据近期配速数据推算心率区间和配速目标\n"
    )

    if not _api_key:
        plan = _build_training_plan_fallback(total_km_14d, training_goal, upcoming_races)
        return {"plan": plan, "generated_at": __import__("datetime").date.today().isoformat(), "source": "fallback"}

    try:
        response = await loop.run_in_executor(
            None,
            lambda: _gemini_generate(prompt, temperature=0.5, max_tokens=4000)
        )
        print(f"[training-plan] Used model: {response['model']}@{response['api_version']}")
        text = response["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        plan = json.loads(text)

        # Save to Firestore
        from datetime import date
        today = date.today().isoformat()
        try:
            plan_ref = (db.collection("users").document(req.uid)
                          .collection("training_plans").document(today))
            plan_ref.set({
                **plan,
                "generated_at": today,
                "vdot_used": vdot,
                "training_goal": training_goal,
            }, merge=True)
        except Exception as e:
            print(f"[training-plan] Failed to save: {e}")

        return {"plan": plan, "generated_at": today}

    except json.JSONDecodeError as e:
        print(f"Training plan JSON parse error: {e}")
        plan = _build_training_plan_fallback(total_km_14d, training_goal, upcoming_races)
        return {"plan": plan, "generated_at": __import__("datetime").date.today().isoformat(), "source": "fallback"}
    except Exception as e:
        print(f"Training plan generation failed: {e}")
        plan = _build_training_plan_fallback(total_km_14d, training_goal, upcoming_races)
        return {"plan": plan, "generated_at": __import__("datetime").date.today().isoformat(), "source": "fallback", "_error": str(e)}

