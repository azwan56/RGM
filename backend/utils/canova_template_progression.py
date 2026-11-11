"""
Canova Funnel Periodization engine for coach group templates.

Coaches reported that 6/8-week plans built from preset group templates repeated the
exact same Tuesday / Wednesday / Thursday / Sunday sessions every week (only the
distance was multiplied). Following Renato Canova's "funnel" methodology
(Fundamental -> Special -> Specific, with 3:1 load waves), this module turns a single
7-day template week into a sequence of weeks whose stimulus, interval structure,
titles and descriptions evolve week by week, while keeping each template's pace
zones, training days and group-level volume.

Design:
- Each week of a plan is mapped to a Canova stage (0..7) via `canova_stage_sequence`.
- Stage 2 / round 0 is the "模版基准周" and reuses the template day verbatim, so the
  coach's original template (or edited custom days) is always preserved in the plan.
- All other weeks are generated from each day's `workout_type`, distance, weekday
  role (post-long recovery / pre-long shakeout / back-to-back day) and template category
  (road marathon, beginner, recovery/taper, gobi back-to-back, ultra trail).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# ── Stage metadata: (phase, theme, key focus, volume multiplier) ──
STAGE_META: Dict[int, Tuple[str, str, str, float]] = {
    0: ("基础适应期", "基础适应周", "有氧底座扩容 + 短间歇神经激活，强度课控制在舒适可完成范围，为专项负荷打底", 0.92),
    1: ("基础转化期", "有氧延伸周", "长距离加入后程渐进，周中引入乳酸门槛巡航短间歇，漏斗两端开始向专项配速靠拢", 0.96),
    2: ("专项准备期", "模版基准周", "按组别标准模版执行：长间歇 + 乳酸阈节奏 + 周末混氧长距离", 1.00),
    3: ("减量吸收周", "波浪减量周", "Canova 3:1 波浪负荷：跑量下调约 20%，以节奏感知替代高强课，促进超量恢复", 0.80),
    4: ("专项突破期", "专项交替周", "引入 Canova 快慢配速交替跑与后程马配切入长距离，提升比赛配速下的乳酸复用能力", 1.04),
    5: ("专项高峰期", "专项高峰周", "周期最高专项负荷：长段落马配巡航 + 专项模拟大课，锤炼后半程抗掉速能力", 1.08),
    6: ("巩固减量期", "减量锐化周", "削减约 25% 跑量，保留少量目标配速短间歇维持神经张力与步频经济性", 0.75),
    7: ("转化检验周", "周期检验周", "低负荷 + 计时测验 / 配速彩排，检验周期成果并校准下一周期配速分组", 0.70),
}
STAGE2_ALT_THEME = "门槛强化周"

# Recovery / taper template (E组) uses its own 4-week rebuild cycle
TAPER_META: Dict[int, Tuple[str, str, str, float]] = {
    0: ("减量排酸恢复期", "深度恢复周", "深度消除累积疲劳，优先睡眠与 HRV 回升，轻度短冲维持肌肉张力", 1.00),
    1: ("有氧重建期", "有氧重建周", "HRV 回升后逐步恢复低心率有氧容量，加入跨步跑唤醒神经", 1.08),
    2: ("神经再激活期", "神经再激活周", "加入目标配速短段落与渐进跑，重新建立配速感知", 1.14),
    3: ("回归过渡期", "回归过渡周", "目标配速段落延长，长距离后程渐进，准备回归原组别正常课表", 1.20),
}


def canova_stage_sequence(weeks_cnt: int) -> List[Tuple[int, int]]:
    """Returns [(stage_idx, round_idx), ...] for each week of the plan."""
    n = max(1, int(weeks_cnt or 1))
    base_map = {
        1: [2],
        2: [0, 2],
        3: [0, 2, 3],
        4: [0, 1, 2, 3],
        5: [0, 1, 2, 3, 4],
        6: [0, 1, 2, 3, 4, 5],
        7: [0, 1, 2, 3, 4, 5, 6],
        8: [0, 1, 2, 3, 4, 5, 6, 7],
    }
    if n in base_map:
        seq = base_map[n]
    else:
        middle_pool = [1, 2, 4, 3, 1, 2, 4, 3]
        seq = [0, 1, 2, 3] + middle_pool[: n - 8] + [4, 5, 6, 7]
    out: List[Tuple[int, int]] = []
    seen: Dict[int, int] = {}
    for st in seq:
        rnd = seen.get(st, 0)
        seen[st] = rnd + 1
        out.append((st, rnd))
    return out


def stage_outline(weeks_cnt: int, is_taper: bool = False) -> List[str]:
    if is_taper:
        return [f"W{i + 1} {TAPER_META[i % 4][1]}" for i in range(max(1, weeks_cnt))]
    res = []
    for i, (st, rnd) in enumerate(canova_stage_sequence(weeks_cnt)):
        theme = STAGE2_ALT_THEME if (st == 2 and rnd > 0) else STAGE_META[st][1]
        res.append(f"W{i + 1} {theme}")
    return res


def stage_week_meta(stage_idx: int, rnd: int, is_taper: bool = False) -> Dict[str, Any]:
    if is_taper:
        phase, theme, focus, mult = TAPER_META[stage_idx % 4]
        return {"phase": phase, "theme": theme, "focus": focus, "mult": mult}
    phase, theme, focus, mult = STAGE_META[stage_idx]
    if stage_idx == 2 and rnd > 0:
        theme = STAGE2_ALT_THEME
        focus = "第二轮门槛强化：拉长单组乳酸阈停留时间，长距离嵌入目标配速段落"
    if rnd > 0 and stage_idx not in (3, 6, 7):
        mult = round(mult + 0.04 * rnd, 3)
        theme = f"{theme}·进阶"
    return {"phase": phase, "theme": theme, "focus": focus, "mult": mult}


# ── Pace helpers ──
_PACE_RE = re.compile(r"(\d{1,2}):(\d{2})")


def _first_pace_sec(text: Any) -> Optional[int]:
    m = _PACE_RE.search(str(text or ""))
    if not m:
        return None
    sec = int(m.group(1)) * 60 + int(m.group(2))
    return sec if 150 <= sec <= 600 else None


def _fmt(sec: Optional[int]) -> str:
    if not sec:
        return ""
    sec = max(150, min(600, int(sec)))
    return f"{sec // 60}:{sec % 60:02d}"


def _paces(pace_zones: Dict[str, Any]) -> Dict[str, str]:
    pz = pace_zones or {}
    mp = _first_pace_sec(pz.get("marathon") or pz.get("marathon_pace"))
    easy = _first_pace_sec(pz.get("easy") or pz.get("easy_pace"))
    tempo = _first_pace_sec(pz.get("tempo") or pz.get("threshold_pace"))
    interval = _first_pace_sec(pz.get("interval") or pz.get("interval_pace"))
    if mp:
        easy = easy or mp + 50
        tempo = tempo or mp - 12
        interval = interval or mp - 35
    has_numeric = bool(mp)
    return {
        "has_numeric": "1" if has_numeric else "",
        "easy": _fmt(easy) or "轻松有氧配速",
        "mp": _fmt(mp) or "目标马配",
        "tempo": _fmt(tempo) or "乳酸阈配速",
        "interval": _fmt(interval) or "间歇配速",
        "rep": _fmt(interval - 8) if interval else "轻快冲刺配速",
        "hmp": _fmt(mp - 10) if mp else "半马配速",
        "fast_mp": _fmt(mp - 6) if mp else "略快于马配",
        "float": _fmt(mp + 12) if mp else "浮游巡航配速",
        "support": _fmt(mp + 20) if mp else "有氧支撑配速",
        "sub_mp": _fmt(mp + 10) if mp else "95%马配",
    }


def _clamp(v: float, lo: int, hi: int) -> int:
    return int(max(lo, min(hi, round(v))))


def _km(v: float) -> str:
    v = round(float(v), 1)
    return f"{int(v)}" if abs(v - int(v)) < 1e-6 else f"{v}"


STRENGTH_ROTATION = [
    "骨盆与臀中肌稳定（蚌式开合 + 侧桥 + 弹力带侧走）",
    "单腿离心抗阻（单腿罗马尼亚硬拉 + 慢速离心提踵）",
    "踝足刚性与足弓（弹力带四向踝 + 足底抓毛巾 + 单腿跳绳）",
    "深度筋膜松解（泡沫轴放松股四头肌、髂胫束与比目鱼肌）",
    "下肢抗疲劳力量（保加利亚分腿蹲 + 臀桥）",
    "核心抗塌腰（死虫式 + 鸟狗式 + 平板支撑）",
    "动态关节灵活性（髋关节绕环 + 动态拉伸，暂停大重量）",
    "轻柔拉伸与早睡蓄能",
]

POST_LONG_ROTATION = [
    "跑后 20 分钟泡沫轴放松小腿与股四头肌",
    "跑后完成 15 分钟髋屈肌与腘绳肌静态拉伸",
    "跑后用筋膜球滚压足底筋膜与跟腱周围",
    "减量周全程极慢速，跑后温水泡脚",
    "跑后补充 20g 优质蛋白，促进专项课后肌纤维修复",
    "高峰周务必监测晨起 HRV，偏低则改为跑休",
    "减量期轻松活动，跑后轻柔拉伸",
    "轻松活动关节，保持跑感",
]

PRE_LONG_ROTATION = [
    ("唤醒慢跑 + 关节活动度", "轻松舒适慢跑 {km}km，活动髋膝踝关节与心肺，不堆积疲劳。"),
    ("唤醒慢跑 + 行进间技术体操", "低心率慢跑 {km}km，跑后完成高抬腿、小步跑、后踢腿各 2×30m，优化次日长跑触地效率。"),
    ("预疲劳有氧慢跑 (Pre-Fatigue)", "稳态有氧慢跑 {km}km（末段含 4×80m 跨步跑），适度预耗浅层糖原，强化次日长距离脂肪动员能力。"),
    ("减量周轻柔恢复慢跑", "极轻松慢跑 {km}km，全程体感舒适，跑后早睡补碳水。"),
    ("专项大课前唤醒 + 4×100m 跨步跑", "轻松慢跑 {km}km + 4 组 100m 轻快跨步冲刺，唤醒神经募集迎接次日专项长距离。"),
    ("高峰大课前蓄能慢跑", "心率控制在 135 bpm 以下完成 {km}km 唤醒跑，备好次日大课能量胶与电解质。"),
    ("减量期短程唤醒跑 + 4×100m", "轻快慢跑 {km}km + 4×100m 轻快加速，保持良好跑感。"),
    ("检验周前唤醒跑", "轻松慢跑 {km}km + 2×80m 轻快加速，为次日检验课做好准备。"),
]


def _day(title: str, pace: str, hr: str, desc: str) -> Dict[str, str]:
    return {"title": title, "target_pace": pace, "target_hr_zone": hr, "description": desc}


# ── Road marathon variants ──
def _road_interval(st: int, rnd: int, km: float, p: Dict[str, str], beginner: bool) -> Dict[str, str]:
    main = max(1.6, km - (5.0 if km >= 10 else 4.0))
    if beginner:
        n200 = _clamp(main * 1000 / 200 * 0.5, 6, 12)
        n300 = _clamp(main * 1000 / 300 * 0.5, 5, 10)
        n400 = _clamp(main * 1000 / 400 * 0.6, 5, 10)
        n500 = _clamp(main * 1000 / 500 * 0.6, 4, 8)
        opts = {
            0: _day(f"有氧慢跑 + 200m 轻快跑×{n200}", f"{p['easy']}/km + 200m轻快", "Zone 2-3",
                    f"慢跑热身 2km + 身训 2 组 + ({n200}×200m 轻快跑 + 200m 慢走恢复) + 冷身慢跑，改善步频与心肺弹性。"),
            1: _day(f"有氧慢跑 + 300m 变速跑×{n300}", f"{p['easy']}/km + 300m @ {p['interval']}", "Zone 2-3",
                    f"慢跑热身 2km + {n300}×300m @ {p['interval']}/km（间歇 200m 慢走/慢跑）+ 冷身慢跑，循序增加快跑段长度。"),
            2: _day(f"有氧慢跑 + 400m 速度感知×{n400}", f"400m @ {p['interval']}/km", "Zone 3-4",
                    f"慢跑热身 2km + 身训 2 组 + {n400}×400m @ {p['interval']}/km（间休 90 秒）+ 冷身，建立稳定速度感。"),
            3: _day("减量周轻松法特莱克", f"{p['easy']}/km 穿插轻快", "Zone 2-3",
                    f"有氧慢跑中穿插 6×(30 秒轻快 + 90 秒慢跑)，总量 {_km(km)}km，体感轻松即可。"),
            4: _day("有氧慢跑 + 坡道冲刺 8×60m", f"{p['easy']}/km", "Zone 2-4",
                    f"有氧慢跑 {_km(max(3.0, km - 1.5))}km + 8 组 60m 缓坡上坡冲刺（慢走下坡恢复），强化臀腿推进力量与跑姿。"),
            5: _day(f"有氧慢跑 + 500m 节奏跑×{n500}", f"500m @ {p['tempo']}/km", "Zone 3-4",
                    f"慢跑热身 2km + {n500}×500m @ {p['tempo']}/km（间休 2 分钟）+ 冷身，提升乳酸门槛耐受。"),
            6: _day("减量期轻快跑 + 200m×6", f"{p['easy']}/km + 200m轻快", "Zone 2-3",
                    f"轻松慢跑 {_km(max(3.0, km - 1.5))}km + 6×200m 轻快跑（间休 200m 慢走），保持腿部弹性不累积疲劳。"),
            7: _day("周期检验 · 3km 自测跑", "3km 尽力匀速", "Zone 3-4",
                    "慢跑热身 2km + 3km 匀速尽力自测（记录用时与平均心率）+ 冷身慢跑，用于对比周期前后有氧能力进步。"),
        }
        return opts[st]

    n400 = _clamp(main * 1000 / 400, 6, 12) + rnd
    n800 = _clamp(main * 1000 / 800, 4, 10) + rnd
    n1200 = _clamp(main * 1000 / 1200, 3, 8)
    n_fart = _clamp(main * 1000 / 400, 6, 14)
    n2000 = _clamp(main / 2.0, 3, 6)
    n600 = _clamp(main * 1000 / 600 * 0.6, 4, 8)
    test_km = 5 if main >= 4 else 3
    pyramid = "2000-1600-1200-800-400m" if main >= 6 else "1600-1200-800-400m"
    opts = {
        0: _day(f"短间歇神经激活 ({n400}×400m) + 技术体操", f"{p['rep']}/km", "Zone 4 (节奏轻快不憋气)",
                f"慢跑热身 2km + 行进间技术体操 + {n400}×400m @ {p['rep']}/km（间休 200m 慢跑）+ 冷身 2km。Canova 基础期以短距离快速度维持神经募集，不追求乳酸堆积。"),
        1: _day(f"VO2Max 经典间歇 ({n800}×800m)", f"{p['interval']}/km", "Zone 4-5",
                f"慢跑热身 2-3km + 动态身训 + {n800}×800m @ {p['interval']}/km（间休 400m 慢跑约 2 分钟）+ 冷身 2km，拉升心肺每搏输出量。"),
        2: _day(f"有氧力量长间歇 ({n1200}×1200m)", f"{p['interval']}-{p['tempo']}/km", "Zone 4",
                f"慢跑热身 3km + {n1200}×1200m @ {p['interval']}~{p['tempo']}/km（间休 90 秒慢跑）+ 冷身 2km，延长 VO2Max 平台停留时间。"),
        3: _day(f"减量周法特莱克 ({n_fart}×1分钟快/1分钟慢)", f"{p['interval']} / {p['easy']}/km 交替", "Zone 2-4",
                f"慢跑热身 2km + {n_fart} 组 ×（1 分钟 @ {p['interval']}/km + 1 分钟慢跑）+ 冷身，减量周保留速度感但不深挖乳酸。"),
        4: _day(f"Canova 混氧递减间歇 ({pyramid})", f"{p['tempo']} → {p['rep']}/km", "Zone 4-5",
                f"慢跑热身 3km + 递减间歇 {pyramid}：长段 @ {p['tempo']}/km，每缩短一段配速提快约 5 秒，最后 400m @ {p['rep']}/km（段间 400m 慢跑）+ 冷身 2km。"),
        5: _day(f"Canova 专项速度耐力 ({n2000}×2000m @ 半马配速)", f"{p['hmp']}/km", "Zone 4 (LT2)",
                f"慢跑热身 3km + {n2000}×2000m @ {p['hmp']}/km（段间 400m 按 {p['float']}/km 浮游慢跑不停表）+ 冷身 2km，把速度储备转化为专项耐力。"),
        6: _day(f"赛前锐化间歇 ({n600}×600m)", f"{p['interval']}/km", "Zone 4",
                f"慢跑热身 2km + {n600}×600m @ {p['interval']}/km（间休 2 分钟充分恢复）+ 冷身，削减容量但保持步频张力。"),
        7: _day(f"周期检验 · {test_km}km 计时测验", f"{test_km}km 尽力匀速", "Zone 4-5",
                f"慢跑热身 3km + 技术体操 + {test_km}km 计时测验（前 1km 克制，后程逐步加速）+ 冷身 2km。用测验成绩校准下一周期配速分组。"),
    }
    return opts[st]


def _road_tempo(st: int, rnd: int, km: float, p: Dict[str, str], beginner: bool) -> Dict[str, str]:
    main = max(3.0, km - 4.0)
    n1600 = _clamp(main / 1.6, 3, 6) + rnd
    alt_sets = _clamp(main / 2.0, 3, 7)
    n3000 = _clamp(main / 3.0, 2, 4)
    taper_n = _clamp(main / 1.6 * 0.6, 2, 4)
    if beginner:
        alt_sets = min(alt_sets, 4)
    opts = {
        0: _day(f"有氧耐力渐速跑 ({_km(main)}km Progressive)", f"{p['easy']} 渐进至 {p['mp']}/km", "Zone 2 → Zone 3",
                f"热身 2km + {_km(main)}km 连续渐速跑（从 {p['easy']}/km 起步，每 2km 提速约 8 秒，末段达到 {p['mp']}/km）+ 冷身 2km，温和唤醒有氧代谢酶。"),
        1: _day(f"乳酸门槛巡航间歇 ({n1600}×1600m @ LT2)", f"{p['tempo']}/km", "Zone 3-4 (LT2)",
                f"热身 2km + {n1600}×1600m @ {p['tempo']}/km（组间 90 秒慢跑）+ 冷身 2km，以短间休分段累积乳酸阈停留时间。"),
        2: _day(f"连续乳酸阈节奏跑 ({_km(main)}km @ LT2)", f"{p['tempo']}/km", "Zone 3-4 (LT2)",
                f"热身 2km + {_km(main)}km 连续乳酸阈节奏跑 @ {p['tempo']}/km（均匀控速，练习高速巡航下的呼吸节奏）+ 冷身 2km。"),
        3: _day(f"减量周马配稳态感知跑 ({_km(main)}km @ MP)", f"{p['mp']}/km", "Zone 3",
                f"热身 2km + {_km(main)}km 按目标马配 {p['mp']}/km 轻松稳态巡航 + 冷身 2km。减量周不追极限强度，专注跑姿经济性。"),
        4: _day(f"Canova 专项交替跑 ({alt_sets}×(1km快+1km浮游))", f"{p['fast_mp']} / {p['float']}/km 交替", "Zone 3-4 交替",
                f"热身 2km + 连续 {alt_sets} 组 ×（1km @ {p['fast_mp']}/km 略快于马配 + 1km @ {p['float']}/km 浮游巡航，不停表）+ 冷身。Canova 核心课：训练肌肉在比赛配速下把乳酸当燃料复用。"),
        5: _day(f"Canova 专项长段落巡航 ({n3000}×3000m @ MP-LT2)", f"{p['mp']}-{p['tempo']}/km", "Zone 3-4",
                f"热身 2km + {n3000}×3000m @ {p['mp']}~{p['tempo']}/km（段间 1km 按 {p['support']}/km 浮游衔接）+ 冷身，直击比赛 30km 后抗掉速专项耐力。"),
        6: _day(f"赛前锐化 ({taper_n}×1600m @ MP)", f"{p['mp']}/km", "Zone 3",
                f"热身 2km + {taper_n}×1600m @ {p['mp']}/km（间休 2 分钟慢跑）+ 冷身，削减负荷但锁定目标配速肌肉记忆。"),
        7: _day("马配彩排跑 (MP Dress Rehearsal)", f"{p['mp']}/km", "Zone 3",
                f"热身 2km + {_km(min(main, 6.0))}km @ {p['mp']}/km 配速彩排（穿比赛鞋袜、演练补给）+ 冷身，检验心率与配速匹配度。"),
    }
    return opts[st]


def _road_long(st: int, rnd: int, km: float, p: Dict[str, str], beginner: bool) -> Dict[str, str]:
    L = km
    first65, last35 = round(L * 0.65, 1), round(L - round(L * 0.65, 1), 1)
    ff_frac = 0.25 if beginner else 0.40
    ff_last = round(L * ff_frac, 1)
    ff_first = round(L - ff_last, 1)
    seg = max(2, min(6, int(round(L * (0.12 if beginner else 0.18)))))
    half = round(L * 0.5, 1)
    mp_word = "马配" if p["has_numeric"] else "目标配速"
    opts = {
        0: _day(f"有氧稳态长距离 LSD {_km(L)}km", f"{p['easy']}/km", "Zone 2",
                f"全程 {_km(L)}km 按 {p['easy']}/km 低心率稳态巡航，严禁前半程起跑过快；每 5km 补水，专注毛细血管扩容与脂肪供能。"),
        1: _day(f"渐进加速长距离 {_km(L)}km (后段 95%{mp_word})", f"{p['easy']} 渐进至 {p['sub_mp']}/km", "Zone 2 → Zone 3",
                f"前 {_km(first65)}km 稳守 {p['easy']}/km，后 {_km(last35)}km 渐进提速至 {p['sub_mp']}/km（约 95% 目标配速），演练每 45 分钟补胶。"),
        2: _day(f"分段{mp_word}长距离 {_km(L)}km (含 2×{seg}km @ MP)", f"{p['easy']} 穿插 {p['mp']}/km", "Zone 2-3",
                f"总长 {_km(L)}km：前段有氧巡航，中后段嵌入 2×{seg}km @ {p['mp']}/km（段间 2km 按 {p['easy']}/km 过渡），建立长距离下的配速定力。"),
        3: _day(f"减量周有氧恢复长跑 {_km(L)}km", f"{p['easy']}/km", "Zone 2",
                f"减量吸收周轻松完成 {_km(L)}km 纯有氧耐力跑，不设配速硬指标，让前几周累积的肌纤维微损伤与肝糖原超量恢复。"),
        4: _day(f"后程切入长距离 {_km(L)}km (后{int(ff_frac * 100)}% @ MP)", f"{p['support']} 切入 {p['mp']}/km", "Zone 2 → Zone 3",
                f"前 {_km(ff_first)}km 按 {p['support']}/km 有氧支撑配速推进，后 {_km(ff_last)}km 连续切入目标配速 {p['mp']}/km，模拟比赛后程体能临界点。"),
        5: _day(f"Canova 专项模拟大课 {_km(L)}km", f"{p['support']} 渐进至 {p['mp']}/km", "Zone 2-4 专项区间",
                f"前 {_km(half)}km 稳态有氧，后 {_km(half)}km 执行专项推进（每 4km @ {p['mp']}/km + 1km @ {p['sub_mp']}/km 连续巡航）；全真演练比赛装备与每 40 分钟补给。"),
        6: _day(f"减量期中长跑 {_km(L)}km (末 3km @ MP)", f"{p['easy']} 末段 {p['mp']}/km", "Zone 2-3",
                f"前 {_km(max(4.0, L - 3.0))}km 轻松有氧，最后 3km 轻快提至 {p['mp']}/km 点到为止，保持心肺张力零疲劳累积。"),
        7: _day(f"周期检验长距离 {_km(L)}km (后 1/3 @ MP)", f"{p['easy']} 渐进至 {p['mp']}/km", "Zone 2-3",
                f"前 {_km(round(L * 0.67, 1))}km 轻松有氧，后 {_km(round(L - round(L * 0.67, 1), 1))}km 稳定在 {p['mp']}/km，记录配速与心率漂移，检验本周期专项耐力成果。"),
    }
    return opts[st]


def _medium_long_easy(st: int, km: float, p: Dict[str, str], strength: str) -> Dict[str, str]:
    opts = {
        0: ("中长距离有氧稳态跑", f"{p['easy']}/km", f"{_km(km)}km 有氧稳态巡航，全程压住心率不漂移，巩固毛细血管密度"),
        1: ("中长距离后程渐进跑", f"{p['easy']} 渐进至 {p['mp']}/km", f"前 {_km(km - 3)}km 有氧巡航，末 3km 自然提速至 {p['mp']}/km"),
        2: ("中长距离有氧耐力跑 (中段含 3km 马配)", f"{p['easy']} 穿插 {p['mp']}/km", f"{_km(km)}km 有氧跑，中段嵌入 3km @ {p['mp']}/km 后回到有氧配速"),
        3: ("减量周轻松有氧跑", f"{p['easy']}/km", f"减量周轻松完成 {_km(km)}km，体感舒适可交谈"),
        4: ("中长距离有氧支撑跑", f"{p['support']}/km", f"{_km(km)}km 按 Canova 有氧支撑配速 {p['support']}/km 稳态推进，介于轻松与马配之间"),
        5: ("中长距离 + 2×2km 马配嵌入", f"{p['easy']} 穿插 {p['mp']}/km", f"{_km(km)}km 有氧跑中嵌入 2×2km @ {p['mp']}/km（间隔 2km 有氧）"),
        6: ("减量期轻松有氧跑", f"{p['easy']}/km", f"轻松有氧 {_km(km)}km，维持有氧容量不累积疲劳"),
        7: ("检验周轻松有氧跑", f"{p['easy']}/km", f"轻松有氧 {_km(km)}km，为周末检验课蓄能"),
    }
    title, pace, body = opts[st]
    return _day(title, pace, "Zone 2" if st in (0, 3, 6, 7) else "Zone 2-3", f"{body}；跑后加练{strength}。")


# ── Recovery / taper (E组) variants ──
def _taper_day(st: int, role: str, km: float, p: Dict[str, str]) -> Dict[str, str]:
    if role == "long":
        opts = {
            1: _day(f"有氧重建耐力跑 {_km(km)}km", "轻松有氧配速", "Zone 2 (<140 bpm)", f"{_km(km)}km 轻松有氧跑，心率稳定即可，跑后补充碳水与蛋白。"),
            2: _day(f"渐进有氧跑 {_km(km)}km (末 3km 目标配速)", "轻松 → 目标马配", "Zone 2-3", f"前 {_km(max(4.0, km - 3))}km 轻松有氧，最后 3km 提至目标马拉松配速，重建配速感知。"),
            3: _day(f"回归长距离 {_km(km)}km (后 1/3 渐进)", "轻松 → 目标马配", "Zone 2-3", f"前 2/3 有氧稳态，后 1/3 渐进至目标配速，检验是否可回归原组别课表。"),
        }
    elif role == "tue":
        opts = {
            1: _day("有氧慢跑 + 6×100m 跨步跑", "轻松配速", "Zone 2", f"轻松慢跑 {_km(max(3.0, km - 1))}km + 6×100m 轻快跨步跑（走回恢复），唤醒神经不累积疲劳。"),
            2: _day("有氧慢跑 + 4×800m @ 目标马配", "800m @ 目标马配", "Zone 2-3", "慢跑热身 2km + 4×800m 按目标马拉松配速（间休 2 分钟）+ 冷身，重建配速感。"),
            3: _day("有氧跑 + 2×2km @ 目标马配", "2km @ 目标马配", "Zone 3", "慢跑热身 2km + 2×2km 目标马拉松配速（间休 3 分钟）+ 冷身，延长配速段落准备回归。"),
        }
    elif role == "sat":
        opts = {
            1: _day("唤醒慢跑 + 技术体操", "轻松配速", "Zone 2", f"轻松慢跑 {_km(km)}km + 高抬腿/小步跑技术体操各 2×30m。"),
            2: _day("唤醒慢跑 + 4×100m 加速", "轻松配速", "Zone 2", f"轻松慢跑 {_km(km)}km + 4×100m 轻快加速，保持肌肉张力。"),
            3: _day("预疲劳有氧慢跑", "轻松配速", "Zone 2", f"稳态有氧慢跑 {_km(km)}km，为次日回归长距离做准备。"),
        }
    else:
        opts = {
            1: _day(f"低心率有氧稳态跑 {_km(km)}km", "轻松配速", "Zone 2 (<140 bpm)", f"{_km(km)}km 低心率稳态慢跑，跑后完成 15 分钟核心与臀中肌激活。"),
            2: _day(f"有氧渐进跑 {_km(km)}km (末 2km 目标配速)", "轻松 → 目标马配", "Zone 2-3", f"前 {_km(max(3.0, km - 2))}km 轻松有氧，末 2km 提至目标马配，体感仍应轻松。"),
            3: _day(f"有氧跑 {_km(km)}km (中段 3km 目标配速)", "轻松 + 目标马配", "Zone 2-3", f"{_km(km)}km 有氧跑中段嵌入 3km 目标马配，跑后单腿离心力量 2 组。"),
        }
    return opts[st]


# ── Gobi back-to-back long run variants ──
def _gobi_long(st: int, km: float, p: Dict[str, str], day2: bool) -> Dict[str, str]:
    L = km
    if not day2:
        opts = {
            0: (f"戈壁背靠背 Day1：有氧负重长距离 {_km(L)}km", f"{p['easy']}/km", f"背水袋包（负重约 1kg）完成 {_km(L)}km 有氧稳态长距离，每 30 分钟补水与盐丸。"),
            1: (f"戈壁背靠背 Day1：负重渐进长距离 {_km(L)}km", f"{p['easy']} 渐进至 {p['sub_mp']}/km", f"负重完成 {_km(L)}km，后 1/3 渐进至 {p['sub_mp']}/km，演练边跑边补给。"),
            2: (f"戈壁背靠背 Day1：负重 + 后程戈壁巡航 {_km(L)}km", f"渐进至 {p['mp']}/km", f"负重 1.5kg 完成 {_km(L)}km，后 8km 顶至戈壁竞赛巡航配速 {p['mp']}/km，每 30 分钟强制补水与电解质盐丸。"),
            3: (f"减量周 Day1：轻负重有氧跑 {_km(L)}km", f"{p['easy']}/km", f"减量周轻负重有氧跑 {_km(L)}km，检查装备磨脚与水袋晃动问题。"),
            4: (f"戈壁背靠背 Day1：分段交替巡航 {_km(L)}km", f"{p['fast_mp']} / {p['float']}/km 交替", f"前半程有氧，后半程执行 3km @ {p['fast_mp']}/km + 2km @ {p['float']}/km 连续交替，模拟雅丹/盐碱地配速切换。"),
            5: (f"戈壁背靠背 Day1：全装备高温补给模拟 {_km(L)}km", f"{p['support']} 渐进至 {p['mp']}/km", f"全套比赛装备 + 中午高温时段完成 {_km(L)}km，后 40% 稳定在 {p['mp']}/km，实测盐丸与能量胶补给方案。"),
            6: (f"减量期 Day1：轻松中长跑 {_km(L)}km", f"{p['easy']}/km", f"轻松有氧 {_km(L)}km，末 2km 提至戈壁巡航配速点到为止。"),
            7: (f"戈壁配速检验 Day1：{_km(L)}km", f"{p['mp']}/km", f"前段有氧，后 1/3 按戈壁巡航配速 {p['mp']}/km 检验，记录心率漂移。"),
        }
    else:
        opts = {
            0: (f"戈壁背靠背 Day2：疲劳态有氧稳态 {_km(L)}km", f"{p['easy']}/km", f"Day1 次日在肌肉未完全恢复状态下完成 {_km(L)}km 有氧稳态，专练疲劳态脂肪供能。"),
            1: (f"戈壁背靠背 Day2：疲劳态渐进跑 {_km(L)}km", f"{p['easy']} 渐进至 {p['sub_mp']}/km", f"疲劳态 {_km(L)}km，末 1/4 渐进提速，培养后程不掉速意识。"),
            2: (f"戈壁背靠背 Day2：疲劳态稳态长距离 {_km(L)}km", f"{p['support']}/km", f"连续第二天出发 {_km(L)}km，专练戈壁第 3、4 竞赛日的抗掉速意志与脂肪供能效率。"),
            3: (f"减量周 Day2：轻松恢复跑 {_km(L)}km", f"{p['easy']}/km", f"减量周轻松跑 {_km(L)}km，跑后充分拉伸。"),
            4: (f"戈壁背靠背 Day2：疲劳态后程切入巡航 {_km(L)}km", f"切入 {p['mp']}/km", f"前 60% 有氧，后 40% 切入戈壁巡航配速 {p['mp']}/km，检验疲劳态配速保持能力。"),
            5: (f"戈壁背靠背 Day2：模拟第 3/4 日抗掉速 {_km(L)}km", f"{p['support']}-{p['mp']}/km", f"连续第二天全装备出发，中段 3×3km @ {p['mp']}/km，模拟赛程后两日团队控速。"),
            6: (f"减量期 Day2：短程轻松跑 {_km(L)}km", f"{p['easy']}/km", f"轻松跑 {_km(L)}km，保持连续跑动节奏不累积疲劳。"),
            7: (f"检验周 Day2：恢复跑 {_km(L)}km", f"{p['easy']}/km", f"轻松恢复跑 {_km(L)}km，总结本周期补给与配速数据。"),
        }
    title, pace, desc = opts[st]
    return _day(title, pace, "Zone 2-3", desc)


# ── Ultra trail variants ──
TRAIL_ECC = ["慢速离心单腿下台阶 3 组", "靠墙静蹲 + 单腿平衡", "脚踝四向弹力带 + 跳箱落地缓冲", "泡沫轴松解髂胫束",
             "负重台阶下踩离心 3 组", "背阔肌与上肢推杖力量", "动态拉伸与关节活动", "轻柔拉伸"]


def _trail_interval(st: int, km: float) -> Dict[str, str]:
    main = max(2.0, km - 4.0)
    n60 = _clamp(main * 1.6, 8, 14)
    n3 = _clamp(main * 1.0, 5, 10)
    n5 = _clamp(main * 0.6, 3, 6)
    n2 = _clamp(main * 0.8, 4, 8)
    opts = {
        0: ("短坡神经冲刺 ({n}×60秒陡坡)".format(n=n60), "坡度 6%-10% 强力推坡", "Zone 4",
            f"热身 2km + {n60}×60 秒陡坡全力上冲（慢跑下坡恢复）+ 冷身，强化臀大肌与小腿推进募集"),
        1: (f"陡坡 VO2Max 间歇 ({n3}×3分钟)", "坡度 8%-12% 强力推坡", "Zone 4 (165-175 bpm)",
            f"热身 2km + 陡坡（或跑步机 10% 坡度）3 分钟强力上坡×{n3}（慢跑下坡恢复）+ 冷身"),
        2: (f"长坡耐力间歇 ({n5}×5分钟)", "坡度 6%-8% 稳定推进", "Zone 3-4 (LT2)",
            f"热身 2km + {n5}×5 分钟长坡稳态推进（下坡慢跑恢复，练习高频小步下坡）+ 冷身"),
        3: ("减量周起伏法特莱克", "按体感 RPE 5-7", "Zone 2-3",
            f"起伏路线有氧跑 {_km(km)}km，遇坡轻快上冲、平路放松，减量周不追强度"),
        4: ("坡道乳酸穿梭 (上坡强推 + 平路衔接)", "上坡 RPE 8 + 平路等强配速", "Zone 3-4",
            f"热身 2km + {n2} 组 ×（400m 坡道强攻 + 800m 平路不间休衔接）+ 冷身，专克上完坡双腿灌铅"),
        5: ("长坡持续爬升 (2×15分钟 LT2)", "坡度 6%-10% 持续推进", "Zone 3-4 (LT2)",
            "热身 2km + 2×15 分钟连续爬坡 @ LT2（组间慢跑下坡练技术）+ 冷身，模拟长距离越野持续爬升段"),
        6: (f"减量期短坡锐化 ({n2}×2分钟)", "坡度 6%-8% 轻快推进", "Zone 3-4",
            f"热身 2km + {n2}×2 分钟轻快上坡（充分恢复）+ 冷身，维持爬坡神经张力"),
        7: ("固定坡道计时爬升测验", "全力匀速爬升", "Zone 4",
            "热身 2km + 固定坡道/楼梯 15-20 分钟计时爬升（记录爬升米数与平均心率）+ 冷身，对比周期前后爬坡能力"),
    }
    title, pace, hr, body = opts[st]
    return _day(title, pace, hr, f"{body}；跑后完成{TRAIL_ECC[st]}。")


def _trail_tempo(st: int, km: float, p: Dict[str, str]) -> Dict[str, str]:
    opts = {
        0: ("起伏路线有氧渐速跑", f"等强配速 {p['easy']} 渐进", "Zone 2-3", f"选择起伏路线完成 {_km(km)}km 渐速跑，上坡控心率、平路逐步提速"),
        1: ("台阶/天桥爬升巡航跑", "等强配速", "Zone 3", f"{_km(km)}km 中穿插台阶/天桥连续爬升，练习上坡碎步与平路快速衔接"),
        2: ("起伏坡道混氧节奏跑", f"等强配速 {p['mp']}", "Zone 3-4", f"连续起伏坡道 {_km(km)}km 混氧跑，上坡切换碎步、坡顶不降速直接衔接平路"),
        3: ("减量周起伏有氧感知跑", "按体感舒适", "Zone 2", f"微起伏路线舒适跑 {_km(km)}km，专注下坡落脚点预判与呼吸节奏"),
        4: ("上下坡转换交替跑", f"上坡强推 + 平路 {p['fast_mp']}", "Zone 3-4 交替", f"{_km(km)}km 中连续执行上坡强推 + 下坡高频小步 + 平路快速巡航转换，模拟越野赛地形切换"),
        5: ("连续起伏 LT2 巡航 + 技术下坡", "等强配速 LT2", "Zone 3-4 (LT2)", f"{_km(km)}km 起伏路线 LT2 持续巡航，后段加入 2km 技术下坡练股四头肌离心抗震"),
        6: ("减量期缓坡轻快巡航", "轻快等强配速", "Zone 2-3", f"缓坡路线轻快巡航 {_km(km)}km，保持山野肌肉记忆"),
        7: ("山野节奏检验跑", "等强配速", "Zone 3", f"固定起伏路线 {_km(km)}km 节奏跑，记录用时与心率对比周期初"),
    }
    title, pace, hr, body = opts[st]
    return _day(f"{title} {_km(km)}km", pace, hr, f"{body}；晚间加练{TRAIL_ECC[(st + 5) % 8]}。")


def _trail_long(st: int, km: float) -> Dict[str, str]:
    k = [45, 55, 62, 40, 60, 70, 38, 55][st]
    elev = int(round(km * k, -1))
    titles = [
        "山野有氧耐力拉练", "山野长坡推进拉练", "山野全装备补给拉练", "减量周山野轻快跑",
        "山野分段变速长距离", "山野巅峰模拟拉练 (头灯夜跑 + 全补给)", "减量期山野唤醒跑", "山野周期检验拉练",
    ]
    extra = [
        "全程控心率在 Zone 2，熟悉双杖推进节奏",
        "长坡持续推进不停歇，下坡练高频小步",
        "严格执行每小时 50-60g 碳水肠胃训练",
        "减量周控制爬升与时长，检查装备磨脚问题",
        "平缓路段按等强配速提速，陡坡切换快走",
        "傍晚出发含 1-2 小时头灯夜跑，全真模拟百公里后半程",
        "轻松进山保持山野肌肉记忆，严禁冲坡",
        "固定路线记录用时、爬升与补给数据，对比周期初",
    ]
    return _day(
        f"{titles[st]} {_km(km)}km (累计爬升 {elev}m+)",
        "按地形心率控制",
        "Zone 2-3",
        f"进山完成 {_km(km)}km（爬升约 {elev}m）：上坡双杖省力推进，技术下坡高频小步轻落地；{extra[st]}。",
    )


def _trail_b2b_easy(st: int, km: float, p: Dict[str, str]) -> Dict[str, str]:
    titles = [
        "背靠背疲劳态排酸有氧跑", "背靠背疲劳态平路稳态跑", "背靠背疲劳态 + 末段渐进", "减量周轻松恢复跑",
        "背靠背疲劳态起伏路跑", "背靠背疲劳态跑走结合长时间", "减量期轻松慢跑", "轻松恢复跑",
    ]
    bodies = [
        "进山次日平路恢复跑，强化双腿沉重状态下的动作控制",
        "疲劳态平路稳态巡航，保持高步频小步幅",
        "疲劳态有氧跑，末 2km 自然提速，模拟百公里后半程",
        "减量周轻松跑，跑后充分拉伸",
        "疲劳态选择微起伏路线，练习疲惫下坡控制",
        "疲劳态跑走结合（跑 8 分钟 + 走 2 分钟），延长时间上脚",
        "轻松活动关节，保持跑感",
        "轻松恢复跑，总结本周期数据",
    ]
    return _day(f"{titles[st]} {_km(km)}km", f"{p['easy']}/km", "Zone 2", f"{bodies[st]}，共 {_km(km)}km。")


def build_template_week_day(
    tpl: Dict[str, Any],
    src_d: Dict[str, Any],
    d_i: int,
    base_days: List[Dict[str, Any]],
    stage_idx: int,
    rnd: int,
    dist_km: float,
) -> Optional[Dict[str, str]]:
    """
    Returns {title, target_pace, target_hr_zone, description} for a template day at the given
    Canova stage, or None to keep the source day verbatim (anchor week / rest days).
    For repeated stages in long (9-12 week) plans, titles carry a "进阶" marker.
    """
    res = _build_template_week_day(tpl, src_d, d_i, base_days, stage_idx, rnd, dist_km)
    if res and rnd > 0 and not (stage_idx == 2):
        res["title"] = f"{res['title']} · 第{rnd + 1}轮进阶"
    return res


def _build_template_week_day(
    tpl: Dict[str, Any],
    src_d: Dict[str, Any],
    d_i: int,
    base_days: List[Dict[str, Any]],
    stage_idx: int,
    rnd: int,
    dist_km: float,
) -> Optional[Dict[str, str]]:
    """
    Returns {title, target_pace, target_hr_zone, description} for a template day at the given
    Canova stage, or None to keep the source day verbatim (anchor week / rest days).
    """
    w_type = str(src_d.get("workout_type") or "easy_run")
    if w_type in ("rest", "travel", "cross_training", "race") or dist_km <= 0:
        return None

    tpl_id = str(tpl.get("id") or "")
    category = str(tpl.get("category") or "")
    is_taper = tpl_id == "group_e_taper" or "taper" in category
    is_trail = tpl_id == "group_trail_ultra" or "trail" in category
    is_gobi = tpl_id == "group_gobi_a" or "gobi" in category
    beginner = tpl_id == "group_d_base" or float(tpl.get("weekly_km") or 50.0) < 36.0

    # Anchor week keeps the template (or coach-edited) day verbatim
    if is_taper and stage_idx % 4 == 0:
        return None
    if not is_taper and stage_idx == 2 and rnd == 0:
        return None

    p = _paces(tpl.get("pace_zones") or {})
    prev_type = str((base_days[d_i - 1] if d_i > 0 and d_i - 1 < len(base_days) else {}).get("workout_type") or "")
    next_type = str((base_days[d_i + 1] if d_i + 1 < len(base_days) else {}).get("workout_type") or "")
    is_tempo = w_type in ("tempo", "tempo_run", "threshold")

    if is_taper:
        st = stage_idx % 4
        if w_type == "long_run":
            role = "long"
        elif next_type == "long_run":
            role = "sat"
        elif d_i == 1 or w_type == "interval":
            role = "tue"
        else:
            role = "other"
        return _taper_day(st, role, dist_km, p)

    if is_trail:
        if w_type == "interval":
            return _trail_interval(stage_idx, dist_km)
        if is_tempo or w_type == "trail_climb":
            return _trail_tempo(stage_idx, dist_km, p)
        if w_type == "long_run":
            return _trail_long(stage_idx, dist_km)
        if prev_type == "long_run":
            return _trail_b2b_easy(stage_idx, dist_km, p)

    if w_type == "long_run":
        if is_gobi and (prev_type == "long_run" or next_type == "long_run"):
            return _gobi_long(stage_idx, dist_km, p, day2=(prev_type == "long_run"))
        return _road_long(stage_idx, rnd, dist_km, p, beginner)

    if w_type == "interval":
        res = _road_interval(stage_idx, rnd, dist_km, p, beginner)
        if is_gobi:
            res["description"] += "（戈壁专项：优先选择顶风路段或软土跑道，跑后加练软垫单腿平衡与臀中肌抗风阻身训）"
        return res

    if is_tempo:
        res = _road_tempo(stage_idx, rnd, dist_km, p, beginner)
        if is_gobi:
            res["description"] += "（戈壁专项：可选择碎石/土路完成，模拟雅丹与盐碱地地形切换）"
        return res

    # easy_run family
    strength = STRENGTH_ROTATION[stage_idx]
    if d_i == 0 or prev_type == "long_run":
        title = "主动排酸恢复慢跑" if stage_idx not in (3, 6) else "减量周极慢排酸跑"
        return _day(
            title,
            f"{p['easy']}/km 或更慢",
            "Zone 1-2 (<138 bpm)",
            f"长距离后主动恢复慢跑 {_km(dist_km)}km，全程放松步频；{POST_LONG_ROTATION[stage_idx]}。",
        )
    if next_type == "long_run" or (is_gobi and d_i == 5):
        t, desc = PRE_LONG_ROTATION[stage_idx]
        return _day(t, f"{p['easy']}/km", "Zone 2", desc.format(km=_km(dist_km)))
    if dist_km >= 12.0:
        return _medium_long_easy(stage_idx, dist_km, p, strength)
    return _day(
        f"有氧慢跑 + {strength.split('（')[0]}",
        f"{p['easy']}/km",
        "Zone 2",
        f"有氧轻松跑 {_km(dist_km)}km，保持呼吸平稳可交谈；跑后完成{strength}。",
    )
