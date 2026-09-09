"""
Race Intelligence Knowledge Base & AI Auto-Search Utility
Provides instant curated race profiles for major marathons and trail events,
and falls back to LLM-powered deep search/inference for any other race.
"""

import json
import logging
from typing import Dict, Any, Optional
from utils.llm import llm_client

logger = logging.getLogger("race_intel")

# Pre-curated knowledge base for popular Chinese and global races
CURATED_RACES: Dict[str, Dict[str, Any]] = {
    "上海马拉松": {
        "race_level": "世界白金标",
        "course_profile": "极速平坦 (破 PB 首选)",
        "course_surface": "柏油路",
        "net_elevation_gain_m": 45,
        "avg_temp_c": 13,
        "humidity_pct": 65,
        "weather_notes": "11月下旬或12月初举办，气温通常在 10~16℃，体感清凉干燥，非常利于马拉松出成绩",
        "typical_participants": 38000,
        "custom_notes": "外滩金牛广场起跑，途经陆家嘴、世博滨江，折返后终点徐家汇体育公园，弯道稍多但极平坦"
    },
    "北京马拉松": {
        "race_level": "国际金标",
        "course_profile": "极速平坦 (破 PB 首选)",
        "course_surface": "柏油路",
        "net_elevation_gain_m": 50,
        "avg_temp_c": 10,
        "humidity_pct": 50,
        "weather_notes": "10月下旬或11月初，秋高气爽，气温约 8~14℃，风力轻微，注意前半程保暖",
        "typical_participants": 30000,
        "custom_notes": "天安门广场起跑，一路向北直抵奥林匹克公园景观大道，国马赛道宽阔平直"
    },
    "厦门马拉松": {
        "race_level": "世界白金标",
        "course_profile": "轻微起伏",
        "course_surface": "柏油路",
        "net_elevation_gain_m": 120,
        "avg_temp_c": 15,
        "humidity_pct": 70,
        "weather_notes": "1月初举办，沿海气候温和湿润，气温约 12~18℃，海风对体能消耗有一定影响",
        "typical_participants": 35000,
        "custom_notes": "最美环岛路赛道，途经演武大桥，有缓坡起伏，海风与湿度需注意补液防抽筋"
    },
    "无锡马拉松": {
        "race_level": "国际金标",
        "course_profile": "极速平坦 (破 PB 首选)",
        "course_surface": "柏油路",
        "net_elevation_gain_m": 35,
        "avg_temp_c": 14,
        "humidity_pct": 68,
        "weather_notes": "3月下旬春季举办，樱花季，气候湿润舒适，气温在 10~18℃ 之间，降水概率适中",
        "typical_participants": 33000,
        "custom_notes": "国内著名破 PB 圣地，赛道极为平坦顺畅，途径太湖、鼋头渚樱花大道"
    },
    "武汉马拉松": {
        "race_level": "国际金标",
        "course_profile": "中等坡度",
        "course_surface": "柏油路",
        "net_elevation_gain_m": 150,
        "avg_temp_c": 16,
        "humidity_pct": 75,
        "weather_notes": "3月或4月春季，气温逐渐回升约 13~22℃，湿度稍高",
        "typical_participants": 30000,
        "custom_notes": "一城两江三镇四桥五湖，连续经过晴川桥、武汉长江大桥与沙湖大桥，桥梁长坡需注意分配体能"
    },
    "广州马拉松": {
        "race_level": "国际金标",
        "course_profile": "极速平坦 (破 PB 首选)",
        "course_surface": "柏油路",
        "net_elevation_gain_m": 60,
        "avg_temp_c": 18,
        "humidity_pct": 72,
        "weather_notes": "12月中旬举办，华南冬季，气温通常在 14~21℃，早晚凉爽但中午微热",
        "typical_participants": 30000,
        "custom_notes": "珠江两岸一江两岸赛道，途径海心沙、猎德大桥、琶洲，视野开阔，后程气温上升需注意补水"
    },
    "杭州马拉松": {
        "race_level": "国际金标",
        "course_profile": "中等坡度",
        "course_surface": "柏油路",
        "net_elevation_gain_m": 180,
        "avg_temp_c": 14,
        "humidity_pct": 70,
        "weather_notes": "11月初深秋，气温在 10~18℃，风景优美但秋雨概率需关注",
        "typical_participants": 36000,
        "custom_notes": "黄龙体育中心起跑，沿西湖白堤、杨公堤、钱塘江，起伏小坡较多，后程钱塘江畔风大"
    },
    "重庆马拉松": {
        "race_level": "国际金标",
        "course_profile": "极速平坦 (破 PB 首选)",
        "course_surface": "柏油路",
        "net_elevation_gain_m": 40,
        "avg_temp_c": 15,
        "humidity_pct": 75,
        "weather_notes": "3月中下旬春季，气温 12~19℃，多阴天，无大风",
        "typical_participants": 30000,
        "custom_notes": "重马完全沿着南滨路、巴滨路长江沿线折返，赛道近乎零坡度，是西南地区最佳破PB赛道"
    },
    "波士顿马拉松": {
        "race_level": "世界白金标",
        "course_profile": "丘陵赛道",
        "course_surface": "柏油路",
        "net_elevation_gain_m": 240,
        "avg_temp_c": 12,
        "humidity_pct": 60,
        "weather_notes": "4月第三个星期一爱国者日，天气变化多端，可能遭遇逆风、低温甚至降雨",
        "typical_participants": 30000,
        "custom_notes": "点对点下坡赛道，前半程连续下坡极易导致股四头肌疲劳，32公里处著名的心碎坡 (Heartbreak Hill) 是最大挑战"
    },
    "柏林马拉松": {
        "race_level": "世界白金标",
        "course_profile": "极速平坦 (破 PB 首选)",
        "course_surface": "柏油路",
        "net_elevation_gain_m": 25,
        "avg_temp_c": 14,
        "humidity_pct": 60,
        "weather_notes": "9月最后一个周末，初秋天气晴朗稳定，气温 12~18℃，湿度适宜",
        "typical_participants": 45000,
        "custom_notes": "世界大满贯纪录诞生地，全柏油超宽路面，拐弯极少，穿过勃兰登堡门冲刺"
    },
    "东京马拉松": {
        "race_level": "世界白金标",
        "course_profile": "极速平坦 (破 PB 首选)",
        "course_surface": "柏油路",
        "net_elevation_gain_m": 35,
        "avg_temp_c": 11,
        "humidity_pct": 52,
        "weather_notes": "3月初春季，天气干燥微凉，气温 7~13℃，非常适合创造个人好成绩",
        "typical_participants": 38000,
        "custom_notes": "从东京都厅起跑，途径浅草寺、银座、东京塔，折返顺滑平坦"
    },
    "武功山": {
        "race_distance_km": 50.0,
        "elevation_gain_m": 3200,
        "elevation_loss_m": 3000,
        "max_altitude_m": 1918,
        "difficulty_level": "精英级",
        "terrain_type": "高原草甸",
        "climate_zone": "亚热带季风",
        "mandatory_gear": "头灯、备用电池、1.5L储水袋、急救毯、冲锋衣、口哨",
        "cutoff_notes": "50K 组总关门时间 15小时，共设 5个 CP 点",
        "avg_temp_c": 22,
        "weather_notes": "9月中旬举办，高山草甸阳光直射紫外线强烈，午后易有雷阵雨且山脊风大",
        "typical_participants": 3000,
        "custom_notes": "以金顶十万亩高山草甸和绝望坡著称，爬升陡峭，石阶与草甸泥土混合，下坡极耗腿力"
    },
    "崇礼168": {
        "race_distance_km": 102.5,
        "elevation_gain_m": 4850,
        "elevation_loss_m": 4850,
        "max_altitude_m": 2160,
        "difficulty_level": "精英级",
        "terrain_type": "高原草甸",
        "climate_zone": "温带大陆性",
        "mandatory_gear": "双头灯、急救毯、1.5L水具、保暖防风外套、弹力绷带",
        "cutoff_notes": "100K 组关门时间 28小时，设 8个补给站",
        "avg_temp_c": 18,
        "weather_notes": "7月盛夏举办，昼夜温差达 15℃，山顶入夜低温接近 8℃，高海拔常有强对流阵雨",
        "typical_participants": 5000,
        "custom_notes": "冬奥小镇起跑，贯穿密苑云顶、太舞滑雪场及桦皮岭，草甸山脊路段风大景美"
    },
    "柴古唐斯": {
        "race_distance_km": 105.0,
        "elevation_gain_m": 6200,
        "elevation_loss_m": 6200,
        "max_altitude_m": 1382,
        "difficulty_level": "极限级",
        "terrain_type": "混合地形",
        "climate_zone": "亚热带季风",
        "mandatory_gear": "双头灯、急救毯、保暖内衣、防水冲锋衣、水具1.5L、手机充电宝",
        "cutoff_notes": "100K 组关门时间 31小时，设 10个补给站",
        "avg_temp_c": 16,
        "weather_notes": "10月下旬或11月初，临海括苍山多雾湿滑，夜间高山寒冷湿冷",
        "typical_participants": 4000,
        "custom_notes": "国内越野狂欢殿堂，赛道包含碎石路、竹林、泥泞土路与防火道，爬升密集，后程米筛浪风力强劲"
    },
    "宁海越野": {
        "race_distance_km": 105.0,
        "elevation_gain_m": 5100,
        "elevation_loss_m": 5100,
        "max_altitude_m": 950,
        "difficulty_level": "进阶级",
        "terrain_type": "丛林密林",
        "climate_zone": "亚热带季风",
        "mandatory_gear": "头灯、救生毯、防水外套、水具1L、哨子",
        "cutoff_notes": "100K 组关门 27小时，60K 组关门 15小时",
        "avg_temp_c": 18,
        "weather_notes": "10月中旬金秋，浙东丘陵林区，气温适中舒适，偶有小雨湿滑",
        "typical_participants": 4500,
        "custom_notes": "UTMB 资格赛体系，古道石阶与茶园相间，可跑性高，竹林赛道景致宜人"
    },
    "UTMB": {
        "race_distance_km": 171.0,
        "elevation_gain_m": 10000,
        "elevation_loss_m": 10000,
        "max_altitude_m": 2565,
        "difficulty_level": "极限级",
        "terrain_type": "山地跑道",
        "climate_zone": "高寒高原",
        "mandatory_gear": "双头灯、防水冲锋衣(带风帽10000mm)、保暖长裤/长袖、冰爪、急救毯、水具1.5L",
        "cutoff_notes": "总关门时间 46小时30分钟，跨越法意瑞三国",
        "avg_temp_c": 10,
        "weather_notes": "8月末至9月初，阿尔卑斯山脉高海拔气候瞬息万变，夜间极寒达 0℃ 以下，可能有降雪",
        "typical_participants": 2800,
        "custom_notes": "世界越野跑殿堂最高荣誉，环勃朗峰逆时针穿越，技术路段多，高海拔垭口连续翻越"
    }
}


def search_curated_database(query: str) -> Optional[Dict[str, Any]]:
    """Tries to find a match in the curated knowledge base by exact or substring match."""
    clean_q = query.strip().lower().replace(" ", "")
    for name, data in CURATED_RACES.items():
        clean_name = name.lower().replace(" ", "")
        if clean_name in clean_q or clean_q in clean_name:
            return dict(data)
    return None


def fetch_race_intelligence(race_name: str, race_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Looks up structured race intelligence.
    First checks curated knowledge base; if not found, invokes LLM to deduce race features.
    """
    if not race_name or not race_name.strip():
        return {"success": False, "message": "赛事名称不能为空"}

    name = race_name.strip()
    is_trail_hint = False
    if race_type:
        t = race_type.lower()
        if "trail" in t or "越野" in t or "山地" in t:
            is_trail_hint = True
    if "越野" in name or "trail" in name.lower() or "168" in name or "utmb" in name.lower() or "50k" in name.lower() or "100k" in name.lower():
        is_trail_hint = True

    # 1. Check curated database first
    matched = search_curated_database(name)
    if matched:
        detected_category = "trail" if "elevation_gain_m" in matched and matched.get("elevation_gain_m", 0) > 300 else "marathon"
        return {
            "success": True,
            "source": "knowledge_base",
            "race_name": name,
            "race_category": detected_category,
            "race_info": matched,
            "message": "已从权威赛事资料库精准匹配赛事情报"
        }

    # 2. Invoke LLM client
    logger.info(f"Querying LLM for race intelligence on '{name}' (trail_hint={is_trail_hint})...")
    system_prompt = """你是一位精通全球路跑马拉松与越野超级耐力赛的数据分析专家。
你的任务是根据跑者给出的【赛事名称】与【预估类型】，检索或严谨推理该赛事的客观赛道数据。

请根据赛事性质，严格返回如下 JSON 格式之一：

【如果是越野赛 (Trail Running)】：
{
  "race_category": "trail",
  "race_info": {
    "race_distance_km": 50.0,             // 数字，公里
    "elevation_gain_m": 2500,              // 数字，累计爬升 D+ (米)
    "elevation_loss_m": 2500,              // 数字，累计下降 D- (米)
    "max_altitude_m": 1800,                // 数字，最高点海拔 (米)
    "difficulty_level": "进阶级",          // 枚举：入门级 / 进阶级 / 精英级 / 极限级
    "terrain_type": "山地跑道",            // 枚举：山地跑道 / 高原草甸 / 丛林密林 / 岩石峭壁 / 沙漠戈壁 / 混合地形
    "climate_zone": "亚热带季风",          // 枚举：温带大陆性 / 亚热带季风 / 高寒高原 / 热带季风 / 温带海洋性
    "avg_temp_c": 18,                      // 数字，历史比赛天气平均气温 (℃)
    "weather_notes": "秋季举办，昼夜温差大...",
    "typical_participants": 2000,          // 数字，大致参赛人数
    "mandatory_gear": "头灯、急救毯、1.5L水具...",
    "cutoff_notes": "关门时间与补给点设置说明",
    "custom_notes": "赛道难点和特点概述"
  }
}

【如果是公路跑（全马、半马、10K、5K）】：
{
  "race_category": "road",
  "race_info": {
    "race_level": "国际金标",               // 枚举：世界白金标 / 国际金标 / IAAF 银标 / IAAF 铜标 / 国内 A 类认证 / 普通大众认证 / 品牌邀请赛
    "course_profile": "极速平坦 (破 PB 首选)", // 枚举：极速平坦 (破 PB 首选) / 轻微起伏 / 中等坡度 / 丘陵赛道 / 多爬升挑战赛道
    "course_surface": "柏油路",             // 枚举：柏油路 / 石板路 / 混合路面 / 碎石路
    "net_elevation_gain_m": 50,            // 数字，累计爬升 (米)
    "avg_temp_c": 15,                      // 数字，历史平均气温 (℃)
    "humidity_pct": 65,                    // 数字，历史平均湿度 (%)
    "weather_notes": "举办月份的天气体感与风力说明...",
    "typical_participants": 20000,         // 数字，大致参赛人数
    "custom_notes": "赛道地标与破PB建议"
  }
}

要求：
1. 数据尽可能真实准确，如果不确定请基于该地区地理地形给出合理专业估算。
2. 只能输出纯 JSON，严禁输出任何 Markdown 标识符（如 ```json）或非 JSON 解释文字！"""

    user_prompt = f"赛事名称: {name}\n赛事类型参考: {race_type or ('越野赛' if is_trail_hint else '马拉松')}"

    try:
        raw = llm_client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=800
        )
        clean = raw.strip()
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0].strip()

        parsed = json.loads(clean)
        race_info = parsed.get("race_info", {})
        category = parsed.get("race_category", "trail" if is_trail_hint else "road")

        return {
            "success": True,
            "source": "ai_inference",
            "race_name": name,
            "race_category": category,
            "race_info": race_info,
            "message": "已通过 AI 智能检索并估算赛事情报"
        }
    except Exception as e:
        logger.error(f"AI race intelligence deduction failed for '{name}': {e}")
        if is_trail_hint:
            fallback = {
                "race_distance_km": 50.0,
                "elevation_gain_m": 2000,
                "elevation_loss_m": 2000,
                "max_altitude_m": 1200,
                "difficulty_level": "进阶级",
                "terrain_type": "混合地形",
                "climate_zone": "亚热带季风",
                "avg_temp_c": 18,
                "typical_participants": 1500,
                "mandatory_gear": "头灯、急救毯、水具",
                "custom_notes": f"针对 {name} 越野赛的综合推荐设置"
            }
        else:
            fallback = {
                "race_level": "国内 A 类认证",
                "course_profile": "轻微起伏",
                "course_surface": "柏油路",
                "net_elevation_gain_m": 60,
                "avg_temp_c": 15,
                "humidity_pct": 65,
                "typical_participants": 15000,
                "custom_notes": f"针对 {name} 马拉松赛事的综合推荐设置"
            }
        return {
            "success": True,
            "source": "fallback",
            "race_name": name,
            "race_category": "trail" if is_trail_hint else "road",
            "race_info": fallback,
            "message": "已为您填入智能推荐的赛事情报参考"
        }
