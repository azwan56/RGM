"""
Smart Weekly Training Schedule Importer (OCR / Vision + Structured Rule Parser)
Designed for Chinese Running Clubs & EMBA Gobi Challenge / Marathon Prep Teams:
- Parses weekly schedule screenshots (Excel tables) or pasted text
- Automatically splits multi-group schedules (A/B/C/D/E pace groups or Male/Female groups)
- Automatically merges strength training footnotes (体能训练 a/b/c) into the corresponding days
- Extracts group run locations (e.g. 周二卢湾体育场、周六文化公园合练) and precautions
"""

import re
import json
import hashlib
import base64
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from utils.llm import llm_client

logger = logging.getLogger("schedule_importer")


# Built-in verbatim presets matching real Fudan EMBA Gobi 22 Pre-A & Shangma schedules
PRESET_SCHEDULES: Dict[str, Dict[str, Any]] = {
    "gobi22_pre_a_w2": {
        "id": "gobi22_pre_a_w2",
        "label": "🏜️ 复旦EMBA戈22预备A队 · 第2周 (A/B/C/D/E五组)",
        "category": "gobi_pre_a",
        "raw_text": """复旦大学管理学院EMBA戈22预备A队周训练计划(第2周)
10月19日
星期一
休息
10月20日
星期二
节奏跑18km A:420-415 B:440-435
C:520-515 D:545-540
E:600-550(乐跑14km)
10月21日
星期三
轻松跑12km(配速自控)
体能训练(a)
10月22日
星期四
轻松跑16km(配速自控)
体能训练(b)
10月23日
星期五
休息（按摩、游泳、泡澡）
10月24日
星期六
耐力跑22km A:425-420 B:445-440
C:525-520 D:550-545
E:620-610(乐跑16km)
10月25日
星期日
LSD(长距离轻松跑)18km
体能训练(c)
1.体能练习:
a.垫步单腿提拉20次+原地高抬腿30次+原地踢臀跑30次×4组
b.徒手深蹲30次+徒手反向弓步20次+直膝跳30次x4组
c.开合蹲跳25次+斜撑高抬腿(单侧)20次×3组
(每个练习间歇30秒，再做下一个练习，每组间歇1分钟)
注意事项:
1.根据训练计划选择适合自己的分组与配速,不可激进。
2.要养成训练前热身，训练后拉伸韧带的好习惯。
3.体能的各项练习在跑后马上做，效果最佳。
4.每周坚持按摩一次，促进疲劳的恢复。
5.要保证充足的睡眠时间，做好身体健康的细节管理。
6.周二晚在卢湾体育场合练，周六早在文化公园合练。""",
    },
    "shangma_w2": {
        "id": "shangma_w2",
        "label": "🏃 复旦EMBA上马赛中赛 · 第2周 (男女分组+壶铃体能)",
        "category": "marathon_race",
        "raw_text": """复旦管理学院EMBA上马赛中赛周训练计划（第2周）
10月19日
休息
星期一
10月20日
节奏跑20k男:410-405~
女:440-435~
星期二
10月21日
轻松跑12km (配速自控)
星期三
体能训练(a)
10月22日
耐力跑20km 男:450-445 女:540-535
星期四
体能训练(b)
10月23日
休息(按摩、泡澡、泡脚)
星期五
10月24日
耐力跑28k男:410-405~
星期六
女:445-440~
10月25日
LSD(长距离轻松跑)130分钟
星期日
体能训练(c)
1.体能训练：
a.壶铃托杯式深蹲20次+壶铃单手反向弓步20次×4组
b.壶铃硬拉20次+半蹲跳20次×4组
c.开合蹲跳30次+直膝跳30次×4组
(每个练习之间间歇30秒，组间歇1分钟)
2.注意事项:
1.根据训练计划内容，选择适合自己的强度，坚持体能训练！
2.养成训练前充分热身，训练后拉伸韧带的习惯。
3.每周坚持至少按摩一次，促进身体疲劳的恢复。
4.保持良好的睡眠习惯，不熬夜、不喝大酒。
5.周二晚在卢湾体育场，周六在闵行文化公园合练。""",
    },
    "shangma_w3": {
        "id": "shangma_w3",
        "label": "🔥 复旦EMBA上马赛中赛 · 第3周 (16k节奏+1200m间歇+32k大课)",
        "category": "marathon_race",
        "raw_text": """复旦管理学院EMBA上马赛中赛周训练计划(第3周)
10月26日
休息
星期一
10月27日
节奏跑16km 男:400-355-350 女:435-430-425
星期二
间歇跑1200米×5 男335/km 女415/km
10月28日
轻松跑10km (配速自控)
星期三
体能训练(a)
10月29日
耐力跑18km 男:450-445 女:540-535
星期四
体能训练(b)
10月30日
休息(按摩、泡澡、泡脚)
星期五
10月31日
耐力跑32km 男:405-400-355
星期六
女:440-435-430
11月1日
LSD(长距离轻松跑)120分钟
星期日
体能训练(c)
1.体能训练:
a.壶铃托杯式深蹲20次+壶铃单手反向弓步20次×4组
b.壶铃硬拉20次+开合蹲跳30次×4组
c.半蹲跳25次+直膝跳30次×4组
(每个练习之间间歇30秒，组间歇1分钟)
2.注意事项:
1.根据训练计划内容，选择适合自己的强度，坚持体能训练!
2.养成训练前充分热身，训练后拉伸韧带的习惯。
3.每周坚持至少按摩一次，促进身体疲劳的恢复。
4.保持良好的睡眠习惯，不熬夜、不喝大酒。
5.周二晚在卢湾体育场，周六在闵行文化公园合练。""",
    },
}


WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
WEEKDAY_MAP = {
    "星期一": 0, "周一": 0,
    "星期二": 1, "周二": 1,
    "星期三": 2, "周三": 2,
    "星期四": 3, "周四": 3,
    "星期五": 4, "周五": 4,
    "星期六": 5, "周六": 5,
    "星期日": 6, "星期天": 6, "周日": 6,
}


def format_shorthand_pace(raw_pace: str) -> str:
    """
    Converts Chinese coach shorthand pace like '420-415', '410-405~', '400-355-350', '335/km'
    into readable '4:20-4:15/km', '4:10-4:05/km', '4:00-3:55-3:50/km', '3:35/km'.
    """
    if not raw_pace:
        return "配速自控"
    s = raw_pace.strip().rstrip("~～")
    has_km_suffix = "/km" in s.lower()
    s_clean = re.sub(r"/km", "", s, flags=re.IGNORECASE).strip()

    # Replace any 3-digit token like 420 -> 4:20, 355 -> 3:55, 600 -> 6:00
    def _conv_3digit(m: re.Match) -> str:
        val = m.group(0)
        mins = int(val[0])
        secs = int(val[1:])
        if 2 <= mins <= 9 and 0 <= secs <= 59:
            return f"{mins}:{secs:02d}"
        return val

    converted = re.sub(r"\b[2-9]\d{2}\b", _conv_3digit, s_clean)
    if ":" in converted and not converted.endswith("/km"):
        converted = f"{converted}/km"
    elif has_km_suffix and not converted.endswith("/km"):
        converted = f"{converted}/km"
    return converted


def extract_text_from_schedule_image(image_base64: str) -> str:
    """
    Uses DashScope multimodal model (qwen3.8-omni-flash / qwen-vl-max) to extract text verbatim from a schedule screenshot.
    """
    if not image_base64:
        return ""
    b64_clean = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64

    client = llm_client._get_client()
    if not client:
        raise ValueError("AI 视觉服务未配置 API Key，请使用文本粘贴或示例课表导入")

    vision_models = ["qwen3.8-omni-flash", "cmaas-qwen3.8-flash", "qwen3.8-max-0902", "qwen-vl-max"]
    last_err = None
    for model_name in vision_models:
        try:
            res = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_clean}"}},
                            {
                                "type": "text",
                                "text": (
                                    "请把这张跑步训练计划表图片中的所有文字完整、原样提取出来，"
                                    "包含标题、每日日期、星期、训练内容、各组配速（A/B/C/D/E或男/女）、"
                                    "底部的体能练习(a/b/c)及注意事项，不要遗漏任何一行。"
                                ),
                            },
                        ],
                    }
                ],
                temperature=0.1,
                max_tokens=1800,
            )
            content = (res.choices[0].message.content or "").strip()
            if content and len(content) > 20:
                logger.info(f"[schedule_importer] Vision OCR succeeded with model {model_name}")
                return content
        except Exception as e:
            last_err = e
            logger.warning(f"[schedule_importer] Vision model {model_name} failed: {e}")

    raise ValueError(f"图片文字识别失败: {last_err}")


def parse_weekly_schedule_text(
    raw_text: str,
    reference_year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Deterministically parses a Chinese weekly running schedule text (from OCR or Excel copy-paste)
    into structured multi-group 7-day templates, footnotes, and group-run hints.
    """
    year = reference_year or date.today().year
    lines = [ln.strip() for ln in (raw_text or "").splitlines() if ln.strip()]
    if not lines:
        raise ValueError("课表内容为空，请上传清晰的课表截图或粘贴课表文字")

    # 1. Extract Plan Title & Week Number
    plan_title = "周训练计划"
    source_week_index = 1
    body_start_idx = 0

    for idx, ln in enumerate(lines[:5]):
        if any(k in ln for k in ("训练计划", "课表", "预备", "戈", "马拉松", "赛中赛")) or re.search(r"第\s*\d+\s*周", ln):
            plan_title = ln
            m_wk = re.search(r"第\s*(\d+)\s*周", ln)
            if m_wk:
                source_week_index = int(m_wk.group(1))
            body_start_idx = idx + 1
            break

    # 2. Split into Daily Area, Strength Footnotes Area, and Precautions Area
    daily_lines: List[str] = []
    strength_lines: List[str] = []
    precaution_lines: List[str] = []

    current_section = "daily"
    for ln in lines[body_start_idx:]:
        if re.match(r"^(?:[1一][\.\、\s]*)?体能(?:练习|训练)\s*[:：]?$", ln) or re.match(r"^(?:[1一][\.\、\s]*)?体能(?:练习|训练)\s*[:：]", ln):
            current_section = "strength"
            # If there is inline content after the header colon, keep it
            after = re.sub(r"^(?:[1一][\.\、\s]*)?体能(?:练习|训练)\s*[:：]?", "", ln).strip()
            if after:
                strength_lines.append(after)
            continue
        if re.match(r"^(?:[2二][\.\、\s]*)?注意事项\s*[:：]?", ln):
            current_section = "precautions"
            after = re.sub(r"^(?:[2二][\.\、\s]*)?注意事项\s*[:：]?", "", ln).strip()
            if after:
                precaution_lines.append(after)
            continue

        if current_section == "daily":
            # Also switch to strength if we hit a line starting with "a." or "a、" after Sunday
            if re.match(r"^[a-cA-C][\.\、]", ln) and len(daily_lines) >= 7:
                current_section = "strength"
                strength_lines.append(ln)
            else:
                daily_lines.append(ln)
        elif current_section == "strength":
            strength_lines.append(ln)
        elif current_section == "precautions":
            precaution_lines.append(ln)

    # 3. Parse Strength Footnotes (a, b, c) & Interval rest rule
    strength_dict: Dict[str, str] = {}
    strength_rest_note = ""
    for sln in strength_lines:
        m_item = re.match(r"^([a-dA-D])[\.\、\s]+(.+)$", sln)
        if m_item:
            key = m_item.group(1).lower()
            strength_dict[key] = m_item.group(2).strip()
        elif sln.startswith("(") or sln.startswith("（") or "间歇" in sln:
            strength_rest_note = sln.strip("()（） ")
        elif strength_dict:
            # Continuation of previous item
            last_k = list(strength_dict.keys())[-1]
            strength_dict[last_k] += " " + sln

    # 4. Parse Precautions & Group Run Hints (合练地点)
    precautions: List[str] = []
    weekday_group_run_notes: Dict[int, str] = {}
    for pln in precaution_lines:
        clean_p = re.sub(r"^\d+[\.\、\s]+", "", pln).strip()
        if clean_p:
            precautions.append(clean_p)
            # Detect group run venue notes like "周二晚在卢湾体育场合练，周六早在文化公园合练"
            if "合练" in clean_p or "体育场" in clean_p or "公园" in clean_p:
                clauses = re.split(r"[，,；;。]", clean_p)
                for cl in clauses:
                    for wd_str, wd_idx in WEEKDAY_MAP.items():
                        if wd_str in cl:
                            weekday_group_run_notes[wd_idx] = cl.strip()

    # 5. Segment Daily Lines into 7 Day Blocks (Mon..Sun)
    has_explicit_dates = any(re.search(r"\d{1,2}\s*月\s*\d{1,2}\s*日", ln) for ln in daily_lines)
    day_blocks: List[Dict[str, Any]] = []

    if has_explicit_dates:
        cur_block: Optional[Dict[str, Any]] = None
        for ln in daily_lines:
            m_date = re.match(r"^(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*(.*)$", ln)
            if m_date:
                if cur_block is not None:
                    day_blocks.append(cur_block)
                m_num = int(m_date.group(1))
                d_num = int(m_date.group(2))
                rem = m_date.group(3).strip()
                try:
                    dt_iso = date(year, m_num, d_num).isoformat()
                except Exception:
                    dt_iso = None
                cur_block = {
                    "month": m_num,
                    "day": d_num,
                    "date_iso": dt_iso,
                    "weekday_idx": len(day_blocks),
                    "raw_lines": [rem] if rem else [],
                }
            else:
                if cur_block is None:
                    cur_block = {
                        "month": None,
                        "day": None,
                        "date_iso": None,
                        "weekday_idx": 0,
                        "raw_lines": [],
                    }
                # Check if line is just a weekday token like "星期一" or starts with "星期一 "
                m_wd = re.match(r"^(星期[一二三四五六日天]|周[一二三四五六日])\s*(.*)$", ln)
                if m_wd:
                    wd_token = m_wd.group(1)
                    if wd_token in WEEKDAY_MAP:
                        cur_block["weekday_idx"] = WEEKDAY_MAP[wd_token]
                    rem_wd = m_wd.group(2).strip()
                    if rem_wd:
                        cur_block["raw_lines"].append(rem_wd)
                else:
                    cur_block["raw_lines"].append(ln)
        if cur_block is not None:
            day_blocks.append(cur_block)
    else:
        cur_block = None
        for ln in daily_lines:
            m_wd = re.match(r"^(星期[一二三四五六日天]|周[一二三四五六日])\s*[:：]?\s*(.*)$", ln)
            if m_wd:
                if cur_block is not None:
                    day_blocks.append(cur_block)
                wd_token = m_wd.group(1)
                rem_wd = m_wd.group(2).strip()
                cur_block = {
                    "month": None,
                    "day": None,
                    "date_iso": None,
                    "weekday_idx": WEEKDAY_MAP.get(wd_token, len(day_blocks)),
                    "raw_lines": [rem_wd] if rem_wd else [],
                }
            elif cur_block is not None:
                cur_block["raw_lines"].append(ln)
        if cur_block is not None:
            day_blocks.append(cur_block)

    # Ensure 7 day blocks ordered 0..6
    by_wd: Dict[int, Dict[str, Any]] = {}
    for idx, blk in enumerate(day_blocks):
        w_i = blk.get("weekday_idx")
        if w_i is None or w_i in by_wd or not (0 <= w_i <= 6):
            w_i = idx
        if 0 <= w_i <= 6:
            by_wd[w_i] = blk

    # Infer Monday date if any date_iso was parsed
    parsed_monday: Optional[date] = None
    for w_i, blk in by_wd.items():
        if blk.get("date_iso"):
            try:
                dt_obj = datetime.strptime(blk["date_iso"], "%Y-%m-%d").date()
                parsed_monday = dt_obj - timedelta(days=w_i)
                break
            except Exception:
                pass

    today = date.today()
    current_monday = today - timedelta(days=today.weekday())
    next_monday = current_monday + timedelta(days=7)
    default_monday = parsed_monday or next_monday

    # 6. Detect Grouping Mode across the 7 days:
    #    - 'pace_groups' (A/B/C/D/E)
    #    - 'gender' (男/女)
    #    - 'single' (通用)
    full_daily_text = "\n".join(" ".join(blk.get("raw_lines") or []) for blk in by_wd.values())
    pace_group_letters = sorted(
        list(set(re.findall(r"(?<![A-Za-z])([A-F])\s*[:：]\s*\d{3}", full_daily_text)))
    )
    has_gender_split = bool(
        re.search(r"男\s*[:：]?\s*\d{3}", full_daily_text)
        and re.search(r"女\s*[:：]?\s*\d{3}", full_daily_text)
    )

    if len(pace_group_letters) >= 2:
        grouping_mode = "pace_groups"
        group_defs = [
            {
                "group_code": f"{letter}组",
                "short_key": letter,
                "group_name": f"预备队 {letter}组" if "预备" in plan_title or "戈" in plan_title else f"{letter}组",
                "badge_color": {"A": "rose", "B": "amber", "C": "emerald", "D": "sky", "E": "purple"}.get(letter, "amber"),
            }
            for letter in pace_group_letters
        ]
    elif has_gender_split:
        grouping_mode = "gender"
        group_defs = [
            {"group_code": "男组", "short_key": "男", "group_name": "男子组 (男)", "badge_color": "sky"},
            {"group_code": "女组", "short_key": "女", "group_name": "女子组 (女)", "badge_color": "rose"},
        ]
    else:
        grouping_mode = "single"
        group_defs = [
            {"group_code": "全员组", "short_key": "ALL", "group_name": "全员标准组", "badge_color": "amber"},
        ]

    # 7. Helper to build a single day workout for a specific group
    def _build_day_for_group(w_i: int, raw_lines: List[str], grp: Dict[str, Any], day_date_iso: str) -> Dict[str, Any]:
        s_key = grp["short_key"]
        g_code = grp["group_code"]
        combined_text = " ".join(raw_lines).strip()

        # Check for strength training reference (a/b/c)
        strength_tag = None
        strength_detail = ""
        m_str = re.search(r"体能(?:训练|练习)\s*[\(（]?([a-dA-D])[\)）]?", combined_text)
        if m_str:
            strength_tag = m_str.group(1).lower()
            raw_ex = strength_dict.get(strength_tag, "")
            if raw_ex:
                rest_suffix = f"（{strength_rest_note}）" if strength_rest_note else ""
                strength_detail = f"💪 跑后体能训练({strength_tag})：{raw_ex}{rest_suffix}"
            else:
                strength_detail = f"💪 跑后完成体能训练({strength_tag})"

        # Remove strength text from running lines for cleaner parsing
        run_lines = []
        for rl in raw_lines:
            cleaned = re.sub(r"体能(?:训练|练习)\s*[\(（]?[a-dA-D][\)）]?", "", rl).strip()
            if cleaned:
                run_lines.append(cleaned)
        run_text = " ".join(run_lines).strip()

        # Rest day check
        if not run_text or run_text.startswith("休息") or run_text == "跑休":
            rec_match = re.search(r"[\(（]([^\)）]+)[\)）]", run_text)
            rec_hint = rec_match.group(1).strip() if rec_match else ""
            title = f"休息恢复 ({rec_hint})" if rec_hint else "休息日"
            desc = f"完全跑休，主动恢复（{rec_hint}），保证充足睡眠与肌肉排酸。" if rec_hint else "完全跑休，保证充足睡眠，促进超量恢复。"
            return {
                "day_index": w_i + 1,
                "day_of_week": WEEKDAY_NAMES[w_i],
                "date": day_date_iso,
                "workout_type": "rest",
                "title": title,
                "distance_km": 0.0,
                "duration_minutes": 0,
                "target_pace": "—",
                "target_hr_zone": "Zone 1",
                "description": desc,
                "has_strength": False,
                "strength_tag": None,
                "completed": False,
                "coach_notes": weekday_group_run_notes.get(w_i, ""),
            }

        # Check for compound workout (e.g., 节奏跑16km + 间歇跑1200米×5 on same day)
        has_tempo = "节奏跑" in run_text
        has_interval = "间歇跑" in run_text or re.search(r"\d{3,4}\s*(?:米|m)\s*[×xX*]\s*\d+", run_text)

        if has_tempo and has_interval:
            # Parse tempo part & interval part separately
            tempo_dist = 16.0
            m_td = re.search(r"节奏跑\s*(\d+(?:\.\d+)?)\s*(?:km|k|公里)?", run_text, flags=re.IGNORECASE)
            if m_td:
                tempo_dist = float(m_td.group(1))

            iv_spec = "间歇跑"
            m_iv = re.search(r"(间歇跑\s*\d+\s*(?:米|m)\s*[×xX*]\s*\d+(?:组)?)", run_text, flags=re.IGNORECASE)
            if m_iv:
                iv_spec = m_iv.group(1).replace(" ", "")

            if grouping_mode == "gender":
                # Extract 1st and 2nd pace for 男 or 女
                p_matches = re.findall(rf"{s_key}\s*[:：]?\s*([0-9\-~～]+(?:/km)?)", run_text, flags=re.IGNORECASE)
                p1 = format_shorthand_pace(p_matches[0]) if len(p_matches) >= 1 else "按目标配速"
                p2 = format_shorthand_pace(p_matches[1]) if len(p_matches) >= 2 else ""
                pace_str = f"节奏 {p1}" + (f" · 间歇 {p2}" if p2 else "")
            else:
                pace_str = "按分组配速执行"

            title = f"节奏跑{int(tempo_dist) if tempo_dist.is_integer() else tempo_dist}km + {iv_spec}"
            if strength_tag:
                title += f" + 体能({strength_tag})"

            desc_parts = [f"【复合专项课】{title}（{g_code}配速：{pace_str}）。"]
            if strength_detail:
                desc_parts.append(strength_detail)
            if w_i in weekday_group_run_notes:
                desc_parts.append(f"📍 合练提示：{weekday_group_run_notes[w_i]}")

            return {
                "day_index": w_i + 1,
                "day_of_week": WEEKDAY_NAMES[w_i],
                "date": day_date_iso,
                "workout_type": "interval",
                "title": title,
                "distance_km": tempo_dist,
                "duration_minutes": int(round(tempo_dist * 4.5)),
                "target_pace": pace_str,
                "target_hr_zone": "Zone 3-5",
                "description": "\n".join(desc_parts),
                "has_strength": bool(strength_tag),
                "strength_tag": strength_tag,
                "completed": False,
                "coach_notes": weekday_group_run_notes.get(w_i, ""),
            }

        # Standard single run session (节奏跑 / 耐力跑 / 轻松跑 / LSD / 间歇跑)
        # 1. Determine workout_type & base label
        if "间歇" in run_text:
            w_type = "interval"
            base_type_label = "间歇跑"
            hr_zone = "Zone 4-5"
        elif "节奏" in run_text:
            w_type = "tempo_run"
            base_type_label = "节奏跑"
            hr_zone = "Zone 3-4"
        elif "LSD" in run_text.upper() or "长距离" in run_text:
            w_type = "long_run"
            base_type_label = "LSD(长距离轻松跑)" if "LSD" in run_text.upper() else "长距离跑"
            hr_zone = "Zone 2"
        elif "耐力" in run_text:
            w_type = "long_run"
            base_type_label = "耐力跑"
            hr_zone = "Zone 2-3"
        else:
            w_type = "easy_run"
            base_type_label = "轻松跑"
            hr_zone = "Zone 2"

        # 2. Extract base distance (km) or duration (minutes)
        base_dist_km = 0.0
        duration_min = 0

        m_km = re.search(r"(\d+(?:\.\d+)?)\s*(?:km|k|公里)", run_text, flags=re.IGNORECASE)
        m_min = re.search(r"(\d+)\s*分钟", run_text)

        if m_km:
            base_dist_km = float(m_km.group(1))
            if base_dist_km < 18.0 and w_type == "long_run" and "耐力" in run_text:
                # 18km endurance run on Thursday
                pass
        elif m_min:
            duration_min = int(m_min.group(1))
            # Estimate distance_km from duration based on group so weekly mileage is accurate
            pace_min_per_km = {
                "A": 5.0, "B": 5.3, "C": 5.7, "D": 6.0, "E": 6.4,
                "男": 5.4, "女": 6.0, "ALL": 5.6
            }.get(s_key, 5.6)
            base_dist_km = round((duration_min / pace_min_per_km) * 2.0) / 2.0

        # 3. Extract group-specific pace and any group-specific distance override (like E:600-550(乐跑14km))
        eff_dist_km = base_dist_km
        group_custom_label = ""
        target_pace = "配速自控"

        if grouping_mode == "pace_groups":
            # Match e.g. E:600-550(乐跑14km) or A:420-415
            m_grp = re.search(
                rf"(?<![A-Za-z]){s_key}\s*[:：]\s*([0-9\-~～/]+)\s*(?:[\(（]([^\)）]+)[\)）])?",
                run_text,
            )
            if m_grp:
                raw_p = m_grp.group(1).strip()
                target_pace = format_shorthand_pace(raw_p)
                paren_note = (m_grp.group(2) or "").strip()
                if paren_note:
                    group_custom_label = paren_note
                    m_override_km = re.search(r"(\d+(?:\.\d+)?)\s*(?:km|k|公里)", paren_note, flags=re.IGNORECASE)
                    if m_override_km:
                        eff_dist_km = float(m_override_km.group(1))
        elif grouping_mode == "gender":
            m_gen = re.search(
                rf"{s_key}\s*[:：]?\s*([0-9\-~～/]+(?:/km)?)",
                run_text,
                flags=re.IGNORECASE,
            )
            if m_gen:
                target_pace = format_shorthand_pace(m_gen.group(1).strip())

        if target_pace == "配速自控" and duration_min > 0:
            target_pace = f"配速自控 ({duration_min}分钟)"

        if duration_min <= 0 and eff_dist_km > 0:
            duration_min = int(round(eff_dist_km * 5.5))

        # 4. Construct clean Title & Description
        dist_str = f"{int(eff_dist_km) if eff_dist_km.is_integer() else eff_dist_km}km"
        if m_min and not m_km:
            core_title = f"{base_type_label} {duration_min}分钟 (约{dist_str})"
        elif group_custom_label:
            core_title = f"{base_type_label} · {group_custom_label}"
        else:
            core_title = f"{base_type_label} {dist_str}"

        if strength_tag:
            core_title += f" + 体能({strength_tag})"

        desc_lines = []
        if target_pace and target_pace != "配速自控":
            desc_lines.append(f"【{g_code}课表】{core_title}，目标配速 {target_pace}。")
        else:
            desc_lines.append(f"【{g_code}课表】{core_title}（配速自控，保持有氧舒适节奏）。")

        if strength_detail:
            desc_lines.append(strength_detail)
        if w_i in weekday_group_run_notes:
            desc_lines.append(f"📍 合练安排：{weekday_group_run_notes[w_i]}")

        return {
            "day_index": w_i + 1,
            "day_of_week": WEEKDAY_NAMES[w_i],
            "date": day_date_iso,
            "workout_type": w_type,
            "title": core_title,
            "distance_km": eff_dist_km,
            "duration_minutes": duration_min,
            "target_pace": target_pace,
            "target_hr_zone": hr_zone,
            "description": "\n".join(desc_lines),
            "has_strength": bool(strength_tag),
            "strength_tag": strength_tag,
            "completed": False,
            "coach_notes": weekday_group_run_notes.get(w_i, ""),
        }

    # 8. Build the complete 7-day schedule for every detected group
    parsed_groups: List[Dict[str, Any]] = []
    for grp in group_defs:
        g_days = []
        for w_i in range(7):
            blk = by_wd.get(w_i, {"raw_lines": ["休息"]})
            d_iso = (default_monday + timedelta(days=w_i)).isoformat()
            day_obj = _build_day_for_group(w_i, blk.get("raw_lines") or ["休息"], grp, d_iso)
            g_days.append(day_obj)

        weekly_km = round(sum(float(d["distance_km"] or 0.0) for d in g_days if d["workout_type"] != "rest"), 1)
        run_days_cnt = sum(1 for d in g_days if d["workout_type"] != "rest" and float(d["distance_km"] or 0.0) > 0)
        strength_days_cnt = sum(1 for d in g_days if d.get("has_strength"))

        # Collect representative paces for summary card
        sample_paces = [
            f"{d['day_of_week']} {d['target_pace']}"
            for d in g_days
            if d["workout_type"] in ("tempo_run", "interval", "long_run")
            and d["target_pace"] not in ("—", "配速自控")
            and not d["target_pace"].startswith("配速自控")
        ]

        parsed_groups.append({
            "group_code": grp["group_code"],
            "short_key": grp["short_key"],
            "group_name": grp["group_name"],
            "badge_color": grp["badge_color"],
            "weekly_km": weekly_km,
            "days_per_week": run_days_cnt,
            "strength_days_count": strength_days_cnt,
            "pace_summary": " · ".join(sample_paces[:2]) if sample_paces else "按组别有氧配速控制",
            "days": g_days,
        })

    coach_review_note = "；".join(precautions) if precautions else "请严格按所属分组配速执行，跑后及时完成体能训练与拉伸。"

    return {
        "plan_title": plan_title,
        "source_week_index": source_week_index,
        "grouping_mode": grouping_mode,
        "parsed_monday": parsed_monday.isoformat() if parsed_monday else None,
        "default_monday": default_monday.isoformat(),
        "current_monday": current_monday.isoformat(),
        "next_monday": next_monday.isoformat(),
        "strength_footnotes": strength_dict,
        "strength_rest_note": strength_rest_note,
        "precautions": precautions,
        "weekday_group_run_notes": {WEEKDAY_NAMES[k]: v for k, v in weekday_group_run_notes.items()},
        "coach_review_note": coach_review_note,
        "groups": parsed_groups,
        "raw_text": raw_text,
    }
