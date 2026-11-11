"""
Race Intelligence Knowledge Base & Official Event Search Utility
Provides official multi-group race specifications for trail races, marathons,
half marathons, 10K, and 5K events, and uses DashScope live web search (enable_search=True)
to retrieve official race regulations for any unlisted event.
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List
from utils.llm import llm_client

logger = logging.getLogger("race_intel")


# ─────────────────────────────────────────────────────────────────────────────
# 1. OFFICIAL MULTI-GROUP TRAIL RACE CATALOG (官方多组别越野赛事库)
# ─────────────────────────────────────────────────────────────────────────────
OFFICIAL_TRAIL_CATALOG: List[Dict[str, Any]] = [
    {
        "event_name": "武功山越野赛",
        "keywords": ["武功山"],
        "default_km": 56.0,
        "base": {
            "max_altitude_m": 1918,
            "terrain_type": "高原草甸",
            "climate_zone": "亚热带季风",
            "avg_temp_c": 22,
            "weather_notes": "9月中旬举办，山下湿热（22~28℃），海拔1600米以上高山草甸日照紫外线强、山脊阵风大，午后易遇云雾或雷阵雨",
            "typical_participants": 3500,
            "mandatory_gear": "头灯（含备用电池）、急救毯、防风防水冲锋衣、至少1.5L水具、救生哨、手机与充电宝、号码布",
        },
        "groups": {
            100: {
                "race_distance_km": 97.0,
                "elevation_gain_m": 6190,
                "elevation_loss_m": 5920,
                "max_altitude_m": 1918,
                "difficulty_level": "极限级",
                "cutoff_notes": "100K组官方赛程97km，总关门时间 28小时，设 9个补给站，完赛获 ITRA 5分",
                "custom_notes": "武功山百公里旗舰组，完整穿越发云界、千丈岩、好汉坡、绝望坡与白鹤峰金顶（1918.3m），技术性碎石与高山草甸连续陡升陡降",
            },
            56: {
                "race_distance_km": 56.0,
                "elevation_gain_m": 3705,
                "elevation_loss_m": 3505,
                "max_altitude_m": 1918,
                "difficulty_level": "精英级",
                "cutoff_notes": "56K个人组（实际轨迹约57~59km）总关门时间 18小时（07:00出发），设 6个补给站，完赛获 ITRA 3分",
                "custom_notes": "官方主力中长距离组别，从武功山游客中心出发，途经好汉坡、绝望坡直登金顶十万亩高山草甸，累计爬升3705m，长距离石阶与草甸下坡极耗股四头肌",
            },
            33: {
                "race_distance_km": 33.0,
                "elevation_gain_m": 2235,
                "elevation_loss_m": 1965,
                "max_altitude_m": 1918,
                "difficulty_level": "进阶级",
                "cutoff_notes": "33K组总关门时间 9小时，设 3个补给站，完赛获 ITRA 2分",
                "custom_notes": "浓缩武功山高山草甸与金顶核心爬升路段，单峰直拔爬升集中",
            },
        },
    },
    {
        "event_name": "衢州·柯城·灵鹫山古道越野赛",
        "keywords": ["灵鹫山", "柯城越野", "衢州越野"],
        "default_km": 60.0,
        "base": {
            "terrain_type": "山地跑道",
            "climate_zone": "亚热带季风",
            "avg_temp_c": 17,
            "weather_notes": "10月下旬深秋举办，浙西山区气温约 12~21℃，早晚微凉，古道竹林间湿度较大",
            "typical_participants": 3000,
            "mandatory_gear": "头灯（含备用电源）、急救毯、防风外套、至少1.0~1.5L水具、救生哨、手机与移动电源",
        },
        "groups": {
            100: {
                "race_distance_km": 99.5,
                "elevation_gain_m": 5650,
                "elevation_loss_m": 5650,
                "max_altitude_m": 1442,
                "difficulty_level": "极限级",
                "cutoff_notes": "百公里「北冥」组（99.5km）总关门时间 28小时，完赛获 ITRA 5分",
                "custom_notes": "串联九华山脉、大荫山与灵鹫山千年古道，水亭门历史文化街区冲线",
            },
            70: {
                "race_distance_km": 69.5,
                "elevation_gain_m": 3850,
                "elevation_loss_m": 3850,
                "max_altitude_m": 1350,
                "difficulty_level": "精英级",
                "cutoff_notes": "70K「凌波」组总关门时间 19小时，完赛获 ITRA 3分",
                "custom_notes": "穿越灵鹫山森林古道、石阶山脊与竹海，终点设于衢州水亭门",
            },
            60: {
                "race_distance_km": 59.4,
                "elevation_gain_m": 3238,
                "elevation_loss_m": 3238,
                "max_altitude_m": 1004,
                "difficulty_level": "进阶级",
                "cutoff_notes": "60K「凌波」组（官方赛程59.36km）总关门时间 16小时，设 6个补给站，完赛获 ITRA 3分",
                "custom_notes": "从柯城区九华乡零号驿站出发，穿越灵鹫山千年古道、茶园竹海与森林山脊，终点抵达衢州水亭门历史文化街区，官方累计爬升3238m",
            },
            40: {
                "race_distance_km": 41.5,
                "elevation_gain_m": 2150,
                "elevation_loss_m": 2150,
                "max_altitude_m": 1004,
                "difficulty_level": "进阶级",
                "cutoff_notes": "40K「折梅」组（41.5km）总关门时间 11小时，完赛获 ITRA 2分",
                "custom_notes": "灵鹫山古道经典中距离组别，森林古道与山脊土路结合，可跑性佳",
            },
            25: {
                "race_distance_km": 25.6,
                "elevation_gain_m": 1180,
                "elevation_loss_m": 1180,
                "max_altitude_m": 780,
                "difficulty_level": "入门级",
                "cutoff_notes": "25K「六阳」组总关门时间 7小时，完赛获 ITRA 1分",
                "custom_notes": "适合进阶体验的轻越野古道赛段",
            },
        },
    },
    {
        "event_name": "宁海越野挑战赛 by UTMB",
        "keywords": ["宁海", "ninghai", "utnh", "cnh", "ynh"],
        "default_km": 60.0,
        "base": {
            "terrain_type": "丛林密林",
            "climate_zone": "亚热带季风",
            "avg_temp_c": 17,
            "weather_notes": "秋季举办，浙东森林竹海气候凉爽宜人（12~20℃），山脊偶有海风与微雨",
            "typical_participants": 4500,
            "mandatory_gear": "头灯（含备用电源）、急救毯、防风防水透气外套、至少1L水具、救生哨、手机与能量补给",
        },
        "groups": {
            105: {
                "race_distance_km": 105.0,
                "elevation_gain_m": 5100,
                "elevation_loss_m": 5100,
                "max_altitude_m": 956,
                "difficulty_level": "精英级",
                "cutoff_notes": "UTNH-105组（105km）总关门时间 27小时，设 9个补给站，完赛获 3颗 UTMB 跑石 (Running Stones) 及 ITRA 5分",
                "custom_notes": "UTMB世界系列赛中国旗舰百公里组，西门城楼起跑，完整串联徐霞客古道、法云寺、东海云顶与磨注峰，可跑性高",
            },
            60: {
                "race_distance_km": 59.0,
                "elevation_gain_m": 2550,
                "elevation_loss_m": 2550,
                "max_altitude_m": 956,
                "difficulty_level": "进阶级",
                "cutoff_notes": "CNH-60组（官方60K组，实际赛程58.8~59km）总关门时间 14小时（07:00起跑），设 5个补给站，完赛获 2颗 UTMB 跑石及 ITRA 3分",
                "custom_notes": "UTMB世界系列赛50K级别黄金组别（CNH-60），沿徐霞客古道穿越竹海、茶园、防火道并登顶东海云顶（海拔956m），累计爬升约2550m，赛道流畅",
            },
            25: {
                "race_distance_km": 24.5,
                "elevation_gain_m": 1150,
                "elevation_loss_m": 1150,
                "max_altitude_m": 750,
                "difficulty_level": "入门级",
                "cutoff_notes": "YNH-25组（24.5km）总关门时间 6小时，完赛获 1颗 UTMB 跑石及 ITRA 1分",
                "custom_notes": "古道竹林轻快赛道，非常适合路跑转越野跑者提速体验",
            },
        },
    },
    {
        "event_name": "Chiang Mai Thailand by UTMB (Chiang Dao 160)",
        "keywords": ["chiangdao", "chiangmai", "清道", "清迈utmb", "chiang dao"],
        "default_km": 160.0,
        "base": {
            "terrain_type": "丛林密林",
            "climate_zone": "热带季风",
            "avg_temp_c": 20,
            "weather_notes": "12月初泰北凉季（旱季）举办，谷底白天温暖（24~29℃），夜间高山丛林气温降至 8~12℃，昼夜温差极大",
            "typical_participants": 2500,
            "mandatory_gear": "双头灯及备用电池、连帽防水冲锋衣、保暖中层、急救毯、弹性绷带、至少1.5L水具、救生哨、400kcal应急能量、手机",
        },
        "groups": {
            160: {
                "race_distance_km": 173.0,
                "elevation_gain_m": 9800,
                "elevation_loss_m": 9800,
                "max_altitude_m": 1850,
                "difficulty_level": "极限级",
                "cutoff_notes": "Chiang Dao 160（100M百英里组，官方实际赛程 173km）总关门时间 48小时，设 14个CP站，完赛获 4颗 UTMB 跑石及 ITRA 6分",
                "custom_notes": "UTMB亚洲大满贯旗舰百英里组，周五上午从清道洞寺 (Wat Tham Chiang Dao) 起跑，穿越清道山与素贴山国家公园原始雨林、山地部落及陡峭红土坡，终点清迈 PAO 公园",
            },
            100: {
                "race_distance_km": 96.0,
                "elevation_gain_m": 4950,
                "elevation_loss_m": 4950,
                "max_altitude_m": 1685,
                "difficulty_level": "精英级",
                "cutoff_notes": "Elephant 100（官方赛程 96km）总关门时间 28小时，完赛获 3颗 UTMB 跑石及 ITRA 4分",
                "custom_notes": "穿越泰北素贴山与湄林高山雨林及象营步道，爬升紧凑",
            },
            50: {
                "race_distance_km": 51.0,
                "elevation_gain_m": 2450,
                "elevation_loss_m": 2450,
                "max_altitude_m": 1685,
                "difficulty_level": "进阶级",
                "cutoff_notes": "Suthep / Inthanon 50（官方赛程 51km）总关门时间 14小时，完赛获 2颗 UTMB 跑石及 ITRA 2分",
                "custom_notes": "泰北经典50K雨林越野赛道，穿越素贴山国家公园",
            },
        },
    },
    {
        "event_name": "柴古唐斯括苍越野赛",
        "keywords": ["柴古唐斯", "柴古", "括苍"],
        "default_km": 55.0,
        "base": {
            "terrain_type": "混合地形",
            "climate_zone": "亚热带季风",
            "avg_temp_c": 16,
            "weather_notes": "10月底或11月初举办，临海括苍山多云雾湿滑，山顶风车阵风强劲，夜间气温低至 5~8℃",
            "typical_participants": 4500,
            "mandatory_gear": "双头灯（百公里）、急救毯、保暖内层、防风防水冲锋衣、至少1.5L水具、救生哨、手机与移动电源",
        },
        "groups": {
            115: {
                "race_distance_km": 115.0,
                "elevation_gain_m": 6850,
                "elevation_loss_m": 6850,
                "max_altitude_m": 1382,
                "difficulty_level": "极限级",
                "cutoff_notes": "115K组（原100K旗舰组）总关门时间 31小时30分，设 10个补给站，完赛获 ITRA 5分",
                "custom_notes": "国内专业竞技水平最高的百公里赛道之一，临海兴善门起终点，登顶浙东南第一高峰米筛浪（1382m），连续十余座山峰高强度拉锯",
            },
            85: {
                "race_distance_km": 85.0,
                "elevation_gain_m": 4860,
                "elevation_loss_m": 4860,
                "max_altitude_m": 1382,
                "difficulty_level": "精英级",
                "cutoff_notes": "85K组总关门时间 22小时30分，设 8个补给站，完赛获 ITRA 4分",
                "custom_notes": "涵盖跑马坪风车防火道与兰辽林场核心技术爬升段",
            },
            55: {
                "race_distance_km": 55.0,
                "elevation_gain_m": 2962,
                "elevation_loss_m": 2962,
                "max_altitude_m": 1150,
                "difficulty_level": "进阶级",
                "cutoff_notes": "55K组总关门时间 11小时30分，设 5个补给站，完赛获 ITRA 3分",
                "custom_notes": "兴善门起跑，串联江南古长城、紫阳古街与括苍国家森林公园，官方赛程55km、累计爬升2962m，关门时间紧凑，对配速要求较高",
            },
            26: {
                "race_distance_km": 26.0,
                "elevation_gain_m": 1050,
                "elevation_loss_m": 1050,
                "max_altitude_m": 680,
                "difficulty_level": "入门级",
                "cutoff_notes": "26K九峰组总关门时间 5小时30分，完赛获 ITRA 1分",
                "custom_notes": "江南长城与九峰山经典短距离越野体验",
            },
        },
    },
    {
        "event_name": "崇礼168超级越野赛",
        "keywords": ["崇礼168", "崇礼越野", "utc168", "gtc100", "mtc50", "ctc70"],
        "default_km": 100.0,
        "base": {
            "terrain_type": "高原草甸",
            "climate_zone": "温带大陆性",
            "avg_temp_c": 18,
            "weather_notes": "7月盛夏举办，亚高原昼夜温差达 15℃，山脊入夜气温低至 8~10℃，午后易发强对流雷阵雨",
            "typical_participants": 8000,
            "mandatory_gear": "头灯及备用电池、急救毯、至少1.5L水具、防风防水冲锋衣、保暖中层、弹力绷带、手机",
        },
        "groups": {
            168: {
                "race_distance_km": 168.5,
                "elevation_gain_m": 7590,
                "elevation_loss_m": 7590,
                "max_altitude_m": 2160,
                "difficulty_level": "极限级",
                "cutoff_notes": "UTC-168组（168.5km）总关门时间 48小时，设 15个补给站，完赛获 ITRA 6分",
                "custom_notes": "大满贯百英里环线，完整串联雪如意、云顶、太舞、万龙、富龙等七大冬奥滑雪场与翠云山长城岭",
            },
            100: {
                "race_distance_km": 102.5,
                "elevation_gain_m": 4850,
                "elevation_loss_m": 4850,
                "max_altitude_m": 2160,
                "difficulty_level": "精英级",
                "cutoff_notes": "GTC-100组（102.5km）总关门时间 28小时，设 9个补给站，完赛获 ITRA 5分",
                "custom_notes": "冬奥小镇起终点，贯穿太舞、云顶及桦皮岭高山草甸与风车山脊，可跑性与爬升兼备",
            },
            70: {
                "race_distance_km": 70.2,
                "elevation_gain_m": 3380,
                "elevation_loss_m": 3380,
                "max_altitude_m": 2120,
                "difficulty_level": "进阶级",
                "cutoff_notes": "CTC-70组（70.2km）总关门时间 20小时，完赛获 ITRA 3分",
                "custom_notes": "崇礼高山草甸与滑雪道经典70公里组别",
            },
            50: {
                "race_distance_km": 51.8,
                "elevation_gain_m": 2420,
                "elevation_loss_m": 2420,
                "max_altitude_m": 2100,
                "difficulty_level": "进阶级",
                "cutoff_notes": "MTC-50组（51.8km）总关门时间 14小时，完赛获 ITRA 2分",
                "custom_notes": "雪场草甸与白桦林交织，累计爬升2420m",
            },
            30: {
                "race_distance_km": 31.2,
                "elevation_gain_m": 1560,
                "elevation_loss_m": 1560,
                "max_altitude_m": 2050,
                "difficulty_level": "入门级",
                "cutoff_notes": "TTC-30组（31.2km）总关门时间 8小时，完赛获 ITRA 1分",
                "custom_notes": "崇礼冬奥核心区30公里山地越野赛段",
            },
        },
    },
    {
        "event_name": "环勃朗峰超级越野赛 (UTMB Mont-Blanc)",
        "keywords": ["utmb", "环勃朗峰", "ccc", "occ", "tds"],
        "default_km": 171.0,
        "base": {
            "terrain_type": "山地跑道",
            "climate_zone": "高寒高原",
            "avg_temp_c": 10,
            "weather_notes": "8月末至9月初，阿尔卑斯山脉高海拔气候多变，2500米垭口夜间极寒可达 0℃ 以下并伴雨雪",
            "typical_participants": 2500,
            "mandatory_gear": "双头灯、连帽压胶防水冲锋衣、防水长裤、保暖中层、手套、防水帽、急救毯、1.5L水具、手机",
        },
        "groups": {
            171: {
                "race_distance_km": 171.0,
                "elevation_gain_m": 9963,
                "elevation_loss_m": 9963,
                "max_altitude_m": 2565,
                "difficulty_level": "极限级",
                "cutoff_notes": "UTMB决赛（171km）总关门时间 46小时30分，跨越法意瑞三国",
                "custom_notes": "世界越野跑最高殿堂，霞慕尼起终点，逆时针环绕勃朗峰连续翻越10余座海拔2000米以上高寒垭口",
            },
            148: {
                "race_distance_km": 148.0,
                "elevation_gain_m": 9300,
                "elevation_loss_m": 9300,
                "max_altitude_m": 2567,
                "difficulty_level": "极限级",
                "cutoff_notes": "TDS组（148km）总关门时间 44小时，库马约尔起跑至霞慕尼",
                "custom_notes": "技术难度极高的阿尔卑斯荒原路线，爬升陡峭险峻",
            },
            100: {
                "race_distance_km": 101.0,
                "elevation_gain_m": 6050,
                "elevation_loss_m": 6150,
                "max_altitude_m": 2565,
                "difficulty_level": "精英级",
                "cutoff_notes": "CCC决赛（101km）总关门时间 26小时30分，意大利库马约尔起跑，法国霞慕尼冲线",
                "custom_notes": "UTMB世界系列赛100K组全球总决赛，起跑即迎接大爬升，后程翻越Tête aux Vents",
            },
            55: {
                "race_distance_km": 57.0,
                "elevation_gain_m": 3500,
                "elevation_loss_m": 3400,
                "max_altitude_m": 2200,
                "difficulty_level": "精英级",
                "cutoff_notes": "OCC决赛（57km）总关门时间 14小时30分，瑞士奥西耶尔起跑，法国霞慕尼冲线",
                "custom_notes": "UTMB世界系列赛50K组全球总决赛，节奏极快的高手对决舞台",
            },
        },
    },
    {
        "event_name": "香港100超级越野赛 (HK100)",
        "keywords": ["香港100", "hk100", "港百"],
        "default_km": 103.0,
        "base": {
            "terrain_type": "混合地形",
            "climate_zone": "亚热带季风",
            "avg_temp_c": 16,
            "weather_notes": "1月中下旬举办，冬季海风清凉（12~20℃），大帽山顶偶有寒潮大雾",
            "typical_participants": 2800,
            "mandatory_gear": "头灯及备用电池、防风外套、急救毯、至少1.0L水具、哨子、手机、应急食物",
        },
        "groups": {
            100: {
                "race_distance_km": 103.0,
                "elevation_gain_m": 5300,
                "elevation_loss_m": 5300,
                "max_altitude_m": 957,
                "difficulty_level": "精英级",
                "cutoff_notes": "HK100百公里组（103km）总关门时间 30小时（16h内完赛获小金人，20h内小银人，24h内小铜人）",
                "custom_notes": "西贡北潭涌起跑，沿麦理浩径穿越西湾沙滩、鸡公山、马鞍山、针山、草山并登顶大帽山（957m），前缓后虐，水泥台阶占比高",
            },
            56: {
                "race_distance_km": 56.0,
                "elevation_gain_m": 2010,
                "elevation_loss_m": 2010,
                "max_altitude_m": 580,
                "difficulty_level": "进阶级",
                "cutoff_notes": "The Half 半程组（56km）总关门时间 14小时",
                "custom_notes": "涵盖西贡绝美海岸线、鹹田湾沙滩与麦理浩径前段精华山径",
            },
            33: {
                "race_distance_km": 33.0,
                "elevation_gain_m": 1460,
                "elevation_loss_m": 1460,
                "max_altitude_m": 450,
                "difficulty_level": "入门级",
                "cutoff_notes": "The Third 三分一组（33km）总关门时间 10小时",
                "custom_notes": "西贡半岛山海风光精华体验组",
            },
        },
    },
    {
        "event_name": "玄奘之路商学院戈壁挑战赛",
        "keywords": ["玄奘之路", "戈壁挑战赛", "戈赛", "戈19", "戈20", "戈21", "戈22"],
        "default_km": 121.0,
        "base": {
            "terrain_type": "沙漠戈壁",
            "climate_zone": "温带大陆性",
            "avg_temp_c": 24,
            "weather_notes": "5月初或10月初敦煌瓜州举办，戈壁极度干燥、紫外线极强，白天可达28~32℃，夜间降至5~10℃，常遇大风扬沙",
            "typical_participants": 5000,
            "mandatory_gear": "GPS定位仪、防风沙镜、防晒面巾、至少2L水袋包、电解质盐丸、急救包、防沙鞋套",
        },
        "groups": {
            121: {
                "race_distance_km": 121.0,
                "elevation_gain_m": 980,
                "elevation_loss_m": 1120,
                "max_altitude_m": 1650,
                "difficulty_level": "精英级",
                "cutoff_notes": "四天三夜总赛程约 121km（体验日+3个竞赛日，单日约28~35km，单日关门 9~10小时）",
                "custom_notes": "阿育王寺起跑，穿越锁阳城、疏勒河、盐碱地、黑戈壁、风车阵至戈壁清泉，黑戈壁砾石与软戈壁极其考验团队配速与有氧耐力",
            },
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# 2. OFFICIAL ROAD RACE CATALOG (官方马拉松 / 半马 / 10K / 5K 赛事库)
# ─────────────────────────────────────────────────────────────────────────────
OFFICIAL_ROAD_CATALOG: List[Dict[str, Any]] = [
    {
        "event_name": "上海马拉松",
        "keywords": ["上海马拉松", "上马"],
        "exclude_keywords": ["上海半程", "上半马", "苏州河半程", "静安半程", "浦东半程", "长宁半程"],
        "race_level": "世界白金标",
        "course_profile": "极速平坦 (破 PB 首选)",
        "course_surface": "柏油路",
        "fm_elevation_gain_m": 45,
        "fm_elevation_loss_m": 42,
        "max_altitude_m": 18,
        "avg_temp_c": 13,
        "humidity_pct": 65,
        "weather_notes": "11月下旬或12月初举办，气温通常在 10~16℃，体感清凉干燥，非常利于马拉松创造PB",
        "typical_participants": 38000,
        "fm_cutoff": "全马总关门时间 6小时15分（07:00起跑，13:15关门）",
        "10k_cutoff": "健身跑/10K组关门时间约 1小时30分~2小时",
        "custom_notes": "外滩金牛广场起跑，途经南京东路、静安寺、新天地、龙华、徐汇滨江，终点徐家汇体育公园，全线平坦顺滑",
    },
    {
        "event_name": "上海半程马拉松",
        "keywords": ["上海半程", "上半马"],
        "race_level": "国际金标",
        "course_profile": "极速平坦 (破 PB 首选)",
        "course_surface": "柏油路",
        "default_type": "hm",
        "hm_elevation_gain_m": 25,
        "hm_elevation_loss_m": 25,
        "max_altitude_m": 15,
        "avg_temp_c": 17,
        "humidity_pct": 68,
        "weather_notes": "4月中旬春季清晨举办，气温约 14~20℃，江风微拂",
        "typical_participants": 15000,
        "hm_cutoff": "半马总关门时间 3小时10分（07:00东方明珠起跑，10:10东方体育中心关门）",
        "custom_notes": "浦东东方明珠丰和路起跑，途经陆家嘴、世博大道、前滩滨江，终点东方体育中心，赛道宽阔平坦",
    },
    {
        "event_name": "上海10公里精英赛",
        "keywords": ["上海10公里", "上马10公里", "上马10k", "10公里精英赛"],
        "race_level": "国际金标",
        "course_profile": "极速平坦 (破 PB 首选)",
        "course_surface": "柏油路",
        "default_type": "10k",
        "10k_elevation_gain_m": 15,
        "10k_elevation_loss_m": 15,
        "max_altitude_m": 12,
        "avg_temp_c": 18,
        "humidity_pct": 65,
        "weather_notes": "10月中旬金秋举办，气温 15~21℃，体感干爽舒适",
        "typical_participants": 7000,
        "10k_cutoff": "10公里总关门时间 1小时30分（光复西路起跑，华东师大终点）",
        "custom_notes": "世界田联金标10公里路跑赛，普陀苏州河半马苏河畔极速赛道，冲刺直道顺畅",
    },
    {
        "event_name": "北京马拉松",
        "keywords": ["北京马拉松", "北马"],
        "exclude_keywords": ["北京半程", "北半马"],
        "race_level": "国际金标",
        "course_profile": "极速平坦 (破 PB 首选)",
        "course_surface": "柏油路",
        "fm_elevation_gain_m": 50,
        "fm_elevation_loss_m": 38,
        "max_altitude_m": 56,
        "avg_temp_c": 10,
        "humidity_pct": 50,
        "weather_notes": "10月下旬或11月初举办，秋高气爽，气温约 7~14℃，湿度低，起跑需注意防寒保暖",
        "typical_participants": 30000,
        "fm_cutoff": "全马总关门时间 6小时15分（07:30天安门广场起跑，13:45奥林匹克公园关门）",
        "custom_notes": "天安门广场起跑，沿长安街、学院路、科荟路最终直抵奥林匹克公园景观大道，全马净赛道宽阔平直",
    },
    {
        "event_name": "无锡马拉松",
        "keywords": ["无锡马拉松", "锡马"],
        "race_level": "国际金标",
        "course_profile": "极速平坦 (破 PB 首选)",
        "course_surface": "柏油路",
        "fm_elevation_gain_m": 38,
        "fm_elevation_loss_m": 38,
        "max_altitude_m": 22,
        "avg_temp_c": 13,
        "humidity_pct": 68,
        "weather_notes": "3月下旬樱花季举办，气温 9~17℃，空气温润，极利于破三与刷新PB",
        "typical_participants": 33000,
        "fm_cutoff": "全马总关门时间 6小时15分，半马总关门时间 3小时15分",
        "custom_notes": "国内公认破PB圣地（全国马拉松锦标赛赛道），太湖大道起跑，途经十里芳堤、鼋头渚樱花林、江南大学与尚贤河湿地",
    },
    {
        "event_name": "厦门马拉松",
        "keywords": ["厦门马拉松", "厦马"],
        "race_level": "世界白金标",
        "course_profile": "轻微起伏",
        "course_surface": "柏油路",
        "fm_elevation_gain_m": 125,
        "fm_elevation_loss_m": 125,
        "max_altitude_m": 30,
        "avg_temp_c": 15,
        "humidity_pct": 70,
        "weather_notes": "1月初举办，冬季海滨温和湿润，气温 12~19℃，环岛路海风需注意跟随集团破风",
        "typical_participants": 35000,
        "fm_cutoff": "全马总关门时间 6小时15分（分枪起跑）",
        "custom_notes": "厦门国际会展中心起终点，沿最美环岛路与演武大桥折返，缓坡起伏较多，注意前半程压制配速",
    },
    {
        "event_name": "武汉马拉松",
        "keywords": ["武汉马拉松", "汉马"],
        "race_level": "国际金标",
        "course_profile": "中等坡度",
        "course_surface": "柏油路",
        "fm_elevation_gain_m": 155,
        "fm_elevation_loss_m": 150,
        "max_altitude_m": 58,
        "avg_temp_c": 15,
        "humidity_pct": 75,
        "weather_notes": "3月下旬举办，春季气温约 11~20℃，东湖绿道空气湿润",
        "typical_participants": 30000,
        "fm_cutoff": "全马关门时间 6小时15分，半马关门时间 3小时15分，13公里跑关门 2小时",
        "custom_notes": "一城两江三镇四桥五湖，连续跨越晴川桥、武汉长江大桥、沙湖大桥进入东湖绿道，桥梁长坡需合理分配体能",
    },
    {
        "event_name": "广州马拉松",
        "keywords": ["广州马拉松", "广马"],
        "race_level": "国际金标",
        "course_profile": "极速平坦 (破 PB 首选)",
        "course_surface": "柏油路",
        "fm_elevation_gain_m": 60,
        "fm_elevation_loss_m": 60,
        "max_altitude_m": 28,
        "avg_temp_c": 18,
        "humidity_pct": 70,
        "weather_notes": "12月上中旬举办，华南初冬早晚凉爽（14~22℃），10点后日照升温需加强补水",
        "typical_participants": 30000,
        "fm_cutoff": "全马总关门时间 6小时15分（天河体育中心/花城广场）",
        "custom_notes": "珠江一江两岸平坦赛道，途经临江大道、猎德大桥、阅江路、滨江路，视野开阔",
    },
    {
        "event_name": "杭州马拉松",
        "keywords": ["杭州马拉松", "杭马"],
        "race_level": "国际金标",
        "course_profile": "中等坡度",
        "course_surface": "柏油路",
        "fm_elevation_gain_m": 165,
        "fm_elevation_loss_m": 165,
        "max_altitude_m": 45,
        "avg_temp_c": 14,
        "humidity_pct": 70,
        "weather_notes": "11月初深秋桂花季举办，气温 10~18℃，体感舒适",
        "typical_participants": 36000,
        "fm_cutoff": "全马关门时间 6小时15分，半马关门时间 3小时10分",
        "custom_notes": "黄龙体育中心起跑，沿西湖北山街、苏堤/白堤、钱塘江闻涛路至奥体中心大莲花，跨越复兴大桥与杨公堤缓坡",
    },
    {
        "event_name": "成都马拉松",
        "keywords": ["成都马拉松", "成马"],
        "race_level": "国际金标",
        "course_profile": "轻微起伏",
        "course_surface": "柏油路",
        "fm_elevation_gain_m": 95,
        "fm_elevation_loss_m": 120,
        "max_altitude_m": 515,
        "avg_temp_c": 15,
        "humidity_pct": 76,
        "weather_notes": "10月下旬举办，盆地秋季多阴天微凉（13~18℃），几乎无日晒，利于长距离发挥",
        "typical_participants": 35000,
        "fm_cutoff": "全马关门时间 6小时15分，半马关门时间 3小时10分",
        "custom_notes": "世界马拉松大满贯候选赛事，金沙遗址起跑，途经天府广场、春熙路、天府大道直达世纪城新会展中心",
    },
    {
        "event_name": "重庆马拉松",
        "keywords": ["重庆马拉松", "重马"],
        "race_level": "国际金标",
        "course_profile": "极速平坦 (破 PB 首选)",
        "course_surface": "柏油路",
        "fm_elevation_gain_m": 42,
        "fm_elevation_loss_m": 42,
        "max_altitude_m": 195,
        "avg_temp_c": 15,
        "humidity_pct": 75,
        "weather_notes": "3月中下旬举办，气温 12~19℃，江畔多阴天，风力较小",
        "typical_participants": 30000,
        "fm_cutoff": "全马总关门时间 6小时15分（南滨路海棠烟雨公园起终点）",
        "custom_notes": "全程沿长江南滨路、巴滨路平直折返，几乎零大坡，西南地区公认最佳破PB高速赛道",
    },
    {
        "event_name": "波士顿马拉松",
        "keywords": ["波士顿马拉松", "波马", "boston"],
        "race_level": "世界白金标",
        "course_profile": "丘陵赛道",
        "course_surface": "柏油路",
        "fm_elevation_gain_m": 248,
        "fm_elevation_loss_m": 388,
        "max_altitude_m": 150,
        "avg_temp_c": 12,
        "humidity_pct": 60,
        "weather_notes": "4月第三个周一爱国者日举办，新英格兰春季气温多变（6~18℃）",
        "typical_participants": 30000,
        "fm_cutoff": "全马总关门时间 6小时（Hopkinton 至 Boylston Street 点对点赛道）",
        "custom_notes": "世界大满贯殿堂，净下降140米但前半程连续下坡极易震伤股四头肌，26~34km牛顿四连坡及32km心碎坡 (Heartbreak Hill) 是核心决胜段",
    },
    {
        "event_name": "柏林马拉松",
        "keywords": ["柏林马拉松", "berlin"],
        "race_level": "世界白金标",
        "course_profile": "极速平坦 (破 PB 首选)",
        "course_surface": "柏油路",
        "fm_elevation_gain_m": 28,
        "fm_elevation_loss_m": 28,
        "max_altitude_m": 52,
        "avg_temp_c": 14,
        "humidity_pct": 60,
        "weather_notes": "9月最后一个周日举办，初秋凉爽稳定，气温 11~17℃，极少大风",
        "typical_participants": 48000,
        "fm_cutoff": "全马总关门时间 6小时15分",
        "custom_notes": "全球最快世界纪录诞生地，六月十七日大街起跑，穿过勃兰登堡门冲刺，赛道极度平坦宽阔",
    },
    {
        "event_name": "东京马拉松",
        "keywords": ["东京马拉松", "东马", "tokyo"],
        "race_level": "世界白金标",
        "course_profile": "极速平坦 (破 PB 首选)",
        "course_surface": "柏油路",
        "fm_elevation_gain_m": 38,
        "fm_elevation_loss_m": 72,
        "max_altitude_m": 42,
        "avg_temp_c": 10,
        "humidity_pct": 52,
        "weather_notes": "3月第一个周日举办，干爽低温（7~13℃），非常适宜高速巡航",
        "typical_participants": 38000,
        "fm_cutoff": "全马总关门时间 7小时（东京都厅起跑，东京站行幸大道终点）",
        "custom_notes": "前5公里微下坡约30米，中后程全平折返，途经浅草雷门、银座与皇居外苑",
    },
    {
        "event_name": "兰州马拉松",
        "keywords": ["兰州马拉松", "兰马"],
        "race_level": "国际金标",
        "course_profile": "轻微起伏",
        "course_surface": "柏油路",
        "fm_elevation_gain_m": 85,
        "fm_elevation_loss_m": 85,
        "max_altitude_m": 1530,
        "avg_temp_c": 20,
        "humidity_pct": 42,
        "weather_notes": "5月下旬举办，海拔约1520m亚高原，日照紫外线较强、后半程升温明显",
        "typical_participants": 40000,
        "fm_cutoff": "全马总关门时间 6小时15分，半马总关门时间 3小时15分",
        "custom_notes": "奥体中心起跑，沿百里黄河风情线两岸折返，亚高原稀薄空气对心率与配速冗余要求更高",
    },
    {
        "event_name": "南京马拉松",
        "keywords": ["南京马拉松", "南马"],
        "race_level": "国际金标",
        "course_profile": "轻微起伏",
        "course_surface": "柏油路",
        "fm_elevation_gain_m": 92,
        "fm_elevation_loss_m": 92,
        "max_altitude_m": 42,
        "avg_temp_c": 13,
        "humidity_pct": 66,
        "weather_notes": "11月中旬深秋举办，气温约 9~17℃，梧桐大道体感凉爽",
        "typical_participants": 30000,
        "fm_cutoff": "全马总关门时间 6小时15分",
        "custom_notes": "奥体中心起跑，途经夫子庙、玄武湖、中山陵风景区与幕燕滨江风光带",
    },
    {
        "event_name": "深圳马拉松",
        "keywords": ["深圳马拉松", "深马"],
        "race_level": "国际金标",
        "course_profile": "轻微起伏",
        "course_surface": "柏油路",
        "fm_elevation_gain_m": 88,
        "fm_elevation_loss_m": 88,
        "max_altitude_m": 35,
        "avg_temp_c": 19,
        "humidity_pct": 72,
        "weather_notes": "12月举办，气温约 15~23℃，海滨日照较暖湿，后程需防热漂移",
        "typical_participants": 20000,
        "fm_cutoff": "全马总关门时间 6小时15分",
        "custom_notes": "市民中心起跑，沿深南大道、深圳湾公园至宝安海滨广场",
    },
    {
        "event_name": "苏州马拉松",
        "keywords": ["苏州马拉松", "苏马"],
        "race_level": "国内 A 类认证",
        "course_profile": "轻微起伏",
        "course_surface": "柏油路",
        "fm_elevation_gain_m": 68,
        "fm_elevation_loss_m": 68,
        "max_altitude_m": 25,
        "avg_temp_c": 12,
        "humidity_pct": 68,
        "weather_notes": "3月上旬早春举办，气温约 8~15℃，温润适宜创造好成绩",
        "typical_participants": 25000,
        "fm_cutoff": "全马总关门时间 6小时15分，半马总关门时间 3小时15分",
        "custom_notes": "串联苏州高新区、姑苏古城护城河与金鸡湖环湖步道，过桥路段略有微坡",
    },
]


def _parse_time_to_hours(target_time: Optional[str]) -> Optional[float]:
    if not target_time:
        return None
    parts = str(target_time).strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) + int(parts[1]) / 60.0 + int(parts[2]) / 3600.0
        if len(parts) == 2:
            return int(parts[0]) / 60.0 + int(parts[1]) / 3600.0
    except Exception:
        pass
    return None


def _extract_distance_hint_km(
    race_name: str,
    race_type: Optional[str] = None,
    target_time: Optional[str] = None,
    matched_act_km: Optional[float] = None,
) -> Optional[float]:
    """
    Infers the exact distance group (km) from:
    1. Matched watch activity distance (if the race was already run!)
    2. Explicit number in race_name (e.g. '宁海60' -> 60, 'Chiang Dao 160' -> 160, '柴古55K' -> 55, '10K' -> 10)
    3. Explicit category in race_type (e.g. '全马', '半马', '10公里', '5公里', '越野跑 100K')
    4. Target time heuristic
    """
    # 1. If runner already completed this race and has a watch track, that's ground-truth distance
    if matched_act_km and matched_act_km >= 3.5:
        return float(matched_act_km)

    name_clean = (race_name or "").strip()
    rtype_clean = (race_type or "").strip()
    combined = f"{name_clean} {rtype_clean}".lower()

    # Special named UTMB sub-races
    if "occ" in name_clean.lower():
        return 55.0
    if "ccc" in name_clean.lower():
        return 100.0
    if "tds" in name_clean.lower():
        return 148.0

    # Check explicit numbers in race_name first (excluding edition numbers like 戈20 / 戈21 / 2025 / 2026)
    name_no_year = re.sub(r"202[0-9]", "", name_clean)
    name_no_gobi_ed = re.sub(r"戈\s*[0-9]{1,2}", "", name_no_year)

    # Match patterns like 168K, 160, 115, 105, 100, 85, 70, 60, 56, 55, 50, 42, 33, 30, 25, 21, 10, 5
    m_km = re.search(r"(\d{1,3}(?:\.\d+)?)\s*(?:km|k|公里|英里|mile|m)?", name_no_gobi_ed, re.IGNORECASE)
    if m_km:
        val = float(m_km.group(1))
        unit_part = m_km.group(0).lower()
        if "英里" in unit_part or "mile" in unit_part:
            return round(val * 1.60934, 1)
        # Note: '崇礼168' has 168 in event brand name; check if another group number is also present
        all_nums = [float(x) for x in re.findall(r"\d{1,3}(?:\.\d+)?", name_no_gobi_ed)]
        if len(all_nums) >= 2 and all_nums[0] == 168:
            return all_nums[-1]
        if 3.0 <= val <= 350.0:
            return val

    # Check road race keywords in name or race_type
    if "半马" in combined or "半程" in combined or "half" in combined or "21.0975" in combined:
        return 21.0975
    if "10公里" in combined or "10k" in combined:
        return 10.0
    if "5公里" in combined or "5k" in combined:
        return 5.0
    if "全马" in combined or "全程马拉松" in combined or "42.195" in combined:
        return 42.195

    # Check trail distance in race_type
    if "100英里" in rtype_clean or "168" in rtype_clean or "160" in rtype_clean:
        return 168.0
    if "100k" in rtype_clean.lower() or "100公里" in rtype_clean:
        return 100.0
    if "50k" in rtype_clean.lower() or "50公里" in rtype_clean:
        return 50.0

    # Heuristic from target_time if provided
    hours = _parse_time_to_hours(target_time)
    if hours is not None:
        is_trail = any(w in combined for w in ["trail", "越野", "山", "utmb", "柴古", "宁海", "崇礼", "武功", "灵鹫"])
        if is_trail:
            if hours >= 26:
                return 160.0
            if hours >= 13.5:
                return 100.0
            if hours >= 5.5:
                return 60.0
            if hours >= 3.5:
                return 35.0
            return 25.0
        else:
            if hours >= 2.3:
                return 42.195
            if hours >= 1.1:
                return 21.0975
            if hours >= 0.5:
                return 10.0
            return 5.0

    return None


def _match_official_trail_catalog(
    race_name: str,
    dist_hint_km: Optional[float],
) -> Optional[Dict[str, Any]]:
    clean_q = race_name.strip().lower().replace(" ", "")
    for entry in OFFICIAL_TRAIL_CATALOG:
        if any(kw.lower().replace(" ", "") in clean_q for kw in entry["keywords"]):
            groups: Dict[int, Dict[str, Any]] = entry["groups"]
            target_km = dist_hint_km if dist_hint_km is not None else entry.get("default_km", 50.0)
            # Pick group with closest nominal distance
            best_group_key = min(groups.keys(), key=lambda k: abs(float(k) - float(target_km)))
            group_data = dict(entry["base"])
            group_data.update(groups[best_group_key])
            # Ensure net_elevation_gain_m is also populated for unified consumption
            group_data["net_elevation_gain_m"] = group_data.get("elevation_gain_m")
            return {
                "event_name": entry["event_name"],
                "race_info": group_data,
            }
    return None


def _match_official_road_catalog(
    race_name: str,
    race_type: Optional[str],
    dist_hint_km: Optional[float],
) -> Optional[Dict[str, Any]]:
    clean_q = race_name.strip().lower().replace(" ", "")
    for entry in OFFICIAL_ROAD_CATALOG:
        if any(ex.lower().replace(" ", "") in clean_q for ex in entry.get("exclude_keywords", [])):
            continue
        if any(kw.lower().replace(" ", "") in clean_q for kw in entry["keywords"]):
            # Determine distance category: fm (42.195), hm (21.0975), 10k (10.0), 5k (5.0)
            default_cat = entry.get("default_type", "fm")
            cat = default_cat
            if dist_hint_km is not None:
                if abs(dist_hint_km - 5.0) <= 2.0:
                    cat = "5k"
                elif abs(dist_hint_km - 10.0) <= 3.5:
                    cat = "10k"
                elif abs(dist_hint_km - 21.0975) <= 5.0:
                    cat = "hm"
                else:
                    cat = "fm"

            fm_gain = entry.get("fm_elevation_gain_m", 50)
            fm_loss = entry.get("fm_elevation_loss_m", fm_gain)

            if cat == "5k":
                dist_km = 5.0
                gain_m = entry.get("5k_elevation_gain_m", max(5, round(fm_gain * 0.15)))
                loss_m = entry.get("5k_elevation_loss_m", max(5, round(fm_loss * 0.15)))
                cutoff = entry.get("5k_cutoff", "5公里项目官方关门时间约 45分钟~1小时")
            elif cat == "10k":
                dist_km = 10.0
                gain_m = entry.get("10k_elevation_gain_m", max(10, round(fm_gain * 0.28)))
                loss_m = entry.get("10k_elevation_loss_m", max(10, round(fm_loss * 0.28)))
                cutoff = entry.get("10k_cutoff", "10公里项目官方关门时间约 1小时30分")
            elif cat == "hm":
                dist_km = 21.0975
                gain_m = entry.get("hm_elevation_gain_m", max(15, round(fm_gain * 0.52)))
                loss_m = entry.get("hm_elevation_loss_m", max(15, round(fm_loss * 0.52)))
                cutoff = entry.get("hm_cutoff", "半程马拉松官方关门时间 3小时10分~3小时15分")
            else:
                dist_km = 42.195
                gain_m = fm_gain
                loss_m = fm_loss
                cutoff = entry.get("fm_cutoff", "全程马拉松官方关门时间 6小时15分")

            info = {
                "race_distance_km": dist_km,
                "elevation_gain_m": gain_m,
                "elevation_loss_m": loss_m,
                "net_elevation_gain_m": gain_m,
                "max_altitude_m": entry.get("max_altitude_m", 25),
                "race_level": entry["race_level"],
                "course_profile": entry["course_profile"],
                "course_surface": entry["course_surface"],
                "avg_temp_c": entry["avg_temp_c"],
                "humidity_pct": entry["humidity_pct"],
                "weather_notes": entry["weather_notes"],
                "typical_participants": entry["typical_participants"],
                "cutoff_notes": cutoff,
                "custom_notes": entry["custom_notes"],
            }
            return {
                "event_name": entry["event_name"],
                "race_info": info,
            }
    return None


def fetch_race_intelligence(
    race_name: str,
    race_type: Optional[str] = None,
    target_time: Optional[str] = None,
    race_date: Optional[str] = None,
    uid: Optional[str] = None,
    use_cache: bool = True,
    allow_web_search: bool = True,
) -> Dict[str, Any]:
    """
    Looks up structured official race intelligence for trail races, marathons, half marathons, 10K, and 5K.
    1. Checks if the runner has a synced GPS watch activity on race_date to identify the exact distance group run.
    2. Matches against the multi-group Official Race Catalog (trail & road).
    3. For unlisted races, invokes DashScope with live web search (enable_search=True, forced_search=True)
       to fetch official race regulations (distance, D+, D-, max altitude, cutoff, mandatory gear).
    """
    if not race_name or not race_name.strip():
        return {"success": False, "message": "赛事名称不能为空"}

    name = race_name.strip()
    matched_act_km: Optional[float] = None
    matched_act_gain: Optional[float] = None

    # Check if user has a synced watch activity on race_date
    if uid and race_date:
        try:
            from utils.local_store import LocalStore
            act = LocalStore.find_matched_activity_for_race(uid, race_date, min_distance_km=3.5)
            if act and act.get("distance_km"):
                matched_act_km = float(act["distance_km"])
                if act.get("elevation_gain_meters"):
                    matched_act_gain = round(float(act["elevation_gain_meters"]))
        except Exception as e:
            logger.warning(f"[race_intel] Optional watch activity check failed: {e}")

    dist_hint_km = _extract_distance_hint_km(
        race_name=name,
        race_type=race_type,
        target_time=target_time,
        matched_act_km=matched_act_km,
    )

    is_trail_hint = False
    combined_lower = f"{name} {race_type or ''}".lower()
    if any(
        k in combined_lower
        for k in [
            "trail", "越野", "山地", "168", "160", "utmb", "柴古", "宁海", "武功山",
            "灵鹫山", "莫干山", "四姑娘山", "港百", "hk100", "戈壁", "玄奘", "50k", "60k", "100k",
        ]
    ):
        is_trail_hint = True

    # 1. Check Official Trail Catalog
    trail_match = _match_official_trail_catalog(name, dist_hint_km)
    if trail_match:
        return {
            "success": True,
            "source": "official_catalog",
            "race_name": name,
            "official_event_name": trail_match["event_name"],
            "race_category": "trail",
            "race_info": trail_match["race_info"],
            "message": f"已匹配【{trail_match['event_name']}】官方竞赛规程数据",
        }

    # 2. Check Official Road Catalog
    road_match = _match_official_road_catalog(name, race_type, dist_hint_km)
    if road_match:
        return {
            "success": True,
            "source": "official_catalog",
            "race_name": name,
            "official_event_name": road_match["event_name"],
            "race_category": "road",
            "race_info": road_match["race_info"],
            "message": f"已匹配【{road_match['event_name']}】官方竞赛规程数据",
        }

    # 2.5 Check persistent SQLite cache (prevents repeated LLM web searches during batch club evaluations)
    dist_bucket = round(float(dist_hint_km), 1) if dist_hint_km else 0.0
    norm_race_key = re.sub(r"\s+", "", name.lower())
    cache_key = f"{norm_race_key}::{dist_bucket}"
    if use_cache:
        try:
            from utils.local_store import LocalStore
            cached_hit = LocalStore.get_cached_race_intel(cache_key)
            if cached_hit and cached_hit.get("race_info"):
                return {
                    "success": True,
                    "source": "cache",
                    "race_name": name,
                    "official_event_name": cached_hit.get("event_name") or name,
                    "race_category": cached_hit.get("race_category") or ("trail" if is_trail_hint else "road"),
                    "race_info": cached_hit["race_info"],
                    "message": f"已加载【{cached_hit.get('event_name') or name}】缓存竞赛规程数据",
                }
        except Exception as e:
            logger.warning(f"[race_intel] Cache read skipped: {e}")

    if not allow_web_search:
        fallback_dist = dist_hint_km or (50.0 if is_trail_hint else 42.195)
        fallback_gain = round(fallback_dist * (50 if is_trail_hint else 1.5))
        fallback_info = {
            "race_distance_km": fallback_dist,
            "elevation_gain_m": fallback_gain,
            "elevation_loss_m": fallback_gain,
            "net_elevation_gain_m": fallback_gain,
            "race_level": "国内 A 类认证",
            "course_profile": "轻微起伏",
            "course_surface": "柏油路",
            "avg_temp_c": 15,
            "humidity_pct": 65,
            "typical_participants": 15000,
            "cutoff_notes": "全马关门6小时15分" if fallback_dist > 30 else ("半马关门3小时10分" if fallback_dist > 15 else "10K关门1小时30分"),
            "custom_notes": f"针对 {name} 路跑赛事的参考配置",
        }
        return {
            "success": True,
            "source": "fallback",
            "race_name": name,
            "official_event_name": name,
            "race_category": "trail" if is_trail_hint else "road",
            "race_info": fallback_info,
            "message": "已填入标准路跑赛事参考配置",
        }

    # 3. Live Web Search Grounded LLM Lookup (DashScope enable_search=True)
    logger.info(
        f"Searching official race regulations via live web search for '{name}' "
        f"(type={race_type}, dist_hint={dist_hint_km}km, trail={is_trail_hint})..."
    )

    dist_context = f"跑者报名组别/参考距离: 约 {dist_hint_km} km" if dist_hint_km else "跑者未显式填写距离数字，请根据赛事名称与类型匹配最对应的主力官方组别"
    if matched_act_km:
        dist_context += f"（跑者实测完赛手表记录距离 {matched_act_km} km"
        if matched_act_gain:
            dist_context += f"，实测累计爬升 {matched_act_gain} m"
        dist_context += "）"

    system_prompt = """你是一位精通中国田协认证路跑赛事、World Athletics标牌赛事、UTMB世界系列赛及ITRA认证越野赛的官方竞赛规程数据专家。
请优先通过联网搜索检索该赛事对应组别的【官方竞赛规程 / 官方网站 / UTMB官网 / 最酷Zuicool / 爱燃烧】公布的真实官方数据（严禁随意编造距离和爬升）。

请根据赛事性质，严格返回如下纯 JSON 格式（严禁包含 ```json 代码块或任何额外解释文字）：

【如果是越野赛 / 山地赛 / 戈壁赛 (Trail Running)】：
{
  "race_category": "trail",
  "race_info": {
    "race_distance_km": 59.0,              // 必填数字：该组别官方公布的实际赛道距离 (km)
    "elevation_gain_m": 2550,              // 必填数字：官方公布累计爬升 D+ (米)
    "elevation_loss_m": 2550,              // 必填数字：官方公布累计下降 D- (米；若起终点海拔相同且官方仅公布D+，则填与D+相同的数值)
    "net_elevation_gain_m": 2550,          // 数字：与 elevation_gain_m 保持一致
    "max_altitude_m": 956,                 // 必填数字：赛道最高点海拔 (米)
    "difficulty_level": "进阶级",          // 枚举：入门级 / 进阶级 / 精英级 / 极限级
    "terrain_type": "山地跑道",            // 枚举：山地跑道 / 高原草甸 / 丛林密林 / 岩石峭壁 / 沙漠戈壁 / 混合地形
    "climate_zone": "亚热带季风",          // 枚举：温带大陆性 / 亚热带季风 / 高寒高原 / 热带季风 / 温带海洋性
    "avg_temp_c": 17,                      // 数字：办赛当月平均气温 (℃)
    "weather_notes": "举办月份、昼夜温差与降水/风力特征",
    "typical_participants": 3000,          // 数字：赛事总规模人数
    "mandatory_gear": "官方强制装备清单（如头灯、急救毯、冲锋衣、1.5L水具、哨子等）",
    "cutoff_notes": "官方关门时间、补给站数量、ITRA积分或UTMB跑石说明",
    "custom_notes": "官方起终点、核心爬升山峰与赛道技术特征"
  }
}

【如果是公路赛（全马 42.195K、半马 21.0975K、10K、5K）】：
{
  "race_category": "road",
  "race_info": {
    "race_distance_km": 42.195,            // 必填数字：全马填 42.195，半马填 21.0975，10K填 10.0，5K填 5.0
    "elevation_gain_m": 50,                // 必填数字：赛道累计爬升 D+ (米)
    "elevation_loss_m": 50,                // 必填数字：赛道累计下降 D- (米)
    "net_elevation_gain_m": 50,            // 必填数字：赛道累计爬升 (米)
    "max_altitude_m": 30,                  // 数字：赛道最高海拔 (米)
    "race_level": "国际金标",               // 枚举：世界白金标 / 国际金标 / IAAF 银标 / IAAF 铜标 / 国内 A 类认证 / 普通大众认证 / 品牌邀请赛
    "course_profile": "极速平坦 (破 PB 首选)", // 枚举：极速平坦 (破 PB 首选) / 轻微起伏 / 中等坡度 / 丘陵赛道 / 多爬升挑战赛道
    "course_surface": "柏油路",             // 枚举：柏油路 / 石板路 / 混合路面 / 碎石路
    "avg_temp_c": 14,                      // 数字：办赛当月平均气温 (℃)
    "humidity_pct": 65,                    // 数字：历史平均湿度 (%)
    "weather_notes": "举办月份的天气体感与风力说明",
    "typical_participants": 25000,         // 数字：大致参赛规模
    "cutoff_notes": "对应组别官方关门时间（如全马6小时15分、半马3小时10分、10K 1小时30分）",
    "custom_notes": "官方起终点、途经地标与赛道坡度起伏详情"
  }
}"""

    user_prompt = (
        f"赛事名称: {name}\n"
        f"赛事类型: {race_type or ('越野赛' if is_trail_hint else '路跑赛事')}\n"
        f"{dist_context}\n"
        f"比赛日期参考: {race_date or '未提供'}\n"
        "请联网核实该赛事对应组别的官方竞赛规程数据，并仅输出 JSON。"
    )

    try:
        raw = llm_client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=1000,
            enable_search=True,
        )
        clean = raw.strip()
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0].strip()
        else:
            start_idx = clean.find("{")
            end_idx = clean.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                clean = clean[start_idx : end_idx + 1]

        parsed = json.loads(clean)
        race_info = parsed.get("race_info", {}) or {}
        category = parsed.get("race_category") or ("trail" if is_trail_hint else "road")

        # Post-processing & consistency guarantees
        if not race_info.get("race_distance_km"):
            if dist_hint_km:
                race_info["race_distance_km"] = dist_hint_km
            elif category == "road":
                race_info["race_distance_km"] = 42.195
            else:
                race_info["race_distance_km"] = 50.0

        # Ensure elevation_gain_m, elevation_loss_m, and net_elevation_gain_m are all populated
        gain = race_info.get("elevation_gain_m") or race_info.get("net_elevation_gain_m")
        if gain is None and matched_act_gain:
            gain = matched_act_gain
        if gain is not None:
            race_info["elevation_gain_m"] = round(float(gain))
            race_info["net_elevation_gain_m"] = round(float(gain))
            if race_info.get("elevation_loss_m") is None:
                race_info["elevation_loss_m"] = round(float(gain))

        if use_cache and race_info:
            try:
                from utils.local_store import LocalStore
                LocalStore.set_cached_race_intel(
                    cache_key=cache_key,
                    event_name=name,
                    race_category=category,
                    race_info=race_info,
                    source="official_web_search",
                )
            except Exception as e:
                logger.warning(f"[race_intel] Cache write skipped: {e}")

        return {
            "success": True,
            "source": "official_web_search",
            "race_name": name,
            "race_category": category,
            "race_info": race_info,
            "message": "已联网检索官方赛事规程并填充数据",
        }
    except Exception as e:
        logger.error(f"Live official race intelligence search failed for '{name}': {e}")
        fallback_dist = dist_hint_km or (50.0 if is_trail_hint else 42.195)
        if is_trail_hint:
            fallback_gain = matched_act_gain or round(fallback_dist * 50)
            fallback = {
                "race_distance_km": fallback_dist,
                "elevation_gain_m": fallback_gain,
                "elevation_loss_m": fallback_gain,
                "net_elevation_gain_m": fallback_gain,
                "max_altitude_m": 1200,
                "difficulty_level": "进阶级",
                "terrain_type": "山地跑道",
                "climate_zone": "亚热带季风",
                "avg_temp_c": 18,
                "typical_participants": 2000,
                "mandatory_gear": "头灯、急救毯、防风外套、1.5L水具、哨子",
                "cutoff_notes": f"{fallback_dist}km 组别请以赛事官方手册关门时间为准",
                "custom_notes": f"针对 {name} 的越野赛事参考配置",
            }
        else:
            fallback_gain = round(fallback_dist * 1.5)
            fallback = {
                "race_distance_km": fallback_dist,
                "elevation_gain_m": fallback_gain,
                "elevation_loss_m": fallback_gain,
                "net_elevation_gain_m": fallback_gain,
                "race_level": "国内 A 类认证",
                "course_profile": "轻微起伏",
                "course_surface": "柏油路",
                "avg_temp_c": 15,
                "humidity_pct": 65,
                "typical_participants": 15000,
                "cutoff_notes": (
                    "全马关门6小时15分"
                    if fallback_dist > 30
                    else ("半马关门3小时10分" if fallback_dist > 15 else "10K关门1小时30分")
                ),
                "custom_notes": f"针对 {name} 路跑赛事的参考配置",
            }
        return {
            "success": True,
            "source": "fallback",
            "race_name": name,
            "race_category": "trail" if is_trail_hint else "road",
            "race_info": fallback,
            "message": "已为您填入赛事参考数据",
        }
