"""
AI Operation Assistant Router:
- POST /api/assistant/navigate: Understands user text/voice intent (via DashScope LLM + deterministic Chinese scorer fallback)
  and routes users directly to the exact workflow entry and deep-link modal/section.
- POST /api/assistant/transcribe: Transcribes uploaded 16kHz WAV speech audio using DashScope ASR
  (paraformer-realtime-v2 -> qwen3-asr-flash -> qwen-audio-asr).
"""

import json
import logging
import os
import re
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel

from config import settings
from utils.llm import llm_client
from utils.security import enforce_rate_limit, get_client_ip

logger = logging.getLogger("router_assistant")
router = APIRouter()

MAX_AUDIO_BYTES = 5 * 1024 * 1024  # 5 MB safety limit


class NavigateRequest(BaseModel):
    query: str
    current_path: Optional[str] = ""
    user_roles: Optional[Dict[str, Any]] = None


# Canonical workflow catalog kept in sync with frontend/src/lib/workflowCatalog.ts
ASSISTANT_WORKFLOWS: List[Dict[str, Any]] = [
    # ── Onboarding / Public ──
    {
        "id": "auth-login",
        "title": "登录 / 注册 / 微信扫码登录",
        "breadcrumb": "顶栏 ▸ 登录 / 注册入口",
        "role": "public",
        "keywords": ["登录", "注册", "扫码", "微信登录", "手机号登录", "账号登录", "登出", "login", "auth"],
        "phrases": ["怎么登录", "微信扫码登录", "注册账号", "登录平台"],
        "default_reply": "点击即可唤起登录与注册弹窗，支持微信扫码或账号密码一键登入。",
    },
    {
        "id": "manual-guide",
        "title": "新用户操作手册与 FAQ 排障",
        "breadcrumb": "跑者视角 ▸ 帮助手册 ▸ 新手上手指南",
        "role": "public",
        "keywords": ["手册", "教程", "新手", "指南", "帮助", "faq", "怎么用", "入门", "说明", "排查"],
        "phrases": ["新手教程", "操作手册", "怎么上手", "使用指南", "常见问题"],
        "default_reply": "正在为您打开官方新用户操作手册，包含绑表、入群实名与常见排障指引。",
    },
    {
        "id": "toggle-theme",
        "title": "切换暗黑 / 明亮界面主题",
        "breadcrumb": "侧边栏底部 / 顶栏 ▸ 主题切换",
        "role": "public",
        "keywords": ["主题", "暗黑", "明亮", "亮色", "深色", "浅色", "夜间模式", "白天模式", "theme", "light", "dark"],
        "phrases": ["切换亮色", "切换暗黑", "换个主题", "白天模式", "夜间模式"],
        "default_reply": "已为您定位界面主题切换指令，可即时在曜石暗黑与竞技亮色之间切换。",
    },
    {
        "id": "runner-home",
        "title": "跑者全息工作台首页",
        "breadcrumb": "跑者视角 ▸ 首页工作台",
        "role": "runner",
        "keywords": ["首页", "工作台", "总览", "看板", "dashboard", "主页", "今日训练", "负荷曲线"],
        "phrases": ["回首页", "打开工作台", "看今日概览"],
        "default_reply": "正在带您回到跑者全息工作台，集中查看今日处方、跑量圆环与体能曲线。",
    },
    # ── Runner: Devices & Profile & Privacy ──
    {
        "id": "bind-garmin",
        "title": "绑定 Garmin 佳明运动手表",
        "breadcrumb": "跑者视角 ▸ 档案与隐私 ▸ 手表连接 ▸ 绑定佳明",
        "role": "runner",
        "keywords": ["佳明", "garmin", "手表", "绑表", "绑定佳明", "中国区", "国际区", "garmin.cn", "garmin.com", "connect"],
        "phrases": ["绑定佳明", "连佳明手表", "佳明中国区", "绑定garmin", "连运动手表"],
        "default_reply": "正在为您直达 Garmin 佳明手表连接弹窗，选择中国区或国际区并输入账号即可开启自动同步。",
    },
    {
        "id": "bind-coros",
        "title": "绑定 COROS 高驰运动手表",
        "breadcrumb": "跑者视角 ▸ 档案与隐私 ▸ 手表连接 ▸ 绑定高驰",
        "role": "runner",
        "keywords": ["高驰", "coros", "手表", "绑表", "绑定高驰", "高驰直连"],
        "phrases": ["绑定高驰", "连高驰手表", "绑定coros"],
        "default_reply": "正在为您打开 COROS 高驰手表直连弹窗，登录账号后即可自动同步跑步记录与体能负荷。",
    },
    {
        "id": "sync-watch",
        "title": "手动同步最新手表跑步记录",
        "breadcrumb": "跑者视角 ▸ 首页工作台 ▸ 同步手表数据",
        "role": "runner",
        "keywords": ["同步", "刷新", "没同步", "拉取", "更新数据", "最新跑步", "打卡记录", "sync"],
        "phrases": ["同步手表数据", "刚跑完没同步", "手动同步记录", "刷新跑步数据"],
        "default_reply": "正在前往工作台并触发手表最新运动数据同步。",
    },
    {
        "id": "import-pb",
        "title": "导入 / 编辑个人最好成绩 (PB)",
        "breadcrumb": "跑者视角 ▸ 档案与隐私 ▸ 训练档案 ▸ 最佳成绩 PB",
        "role": "runner",
        "keywords": ["pb", "最好成绩", "全马成绩", "半马成绩", "10公里", "5公里", "导入pb", "历史成绩", "pr"],
        "phrases": ["导入pb", "修改最好成绩", "从佳明导入pb", "填全马pb"],
        "default_reply": "已为您定位到「训练档案 · 最佳成绩 (PB)」区域，支持一键从 Garmin 导入或手动填写。",
    },
    {
        "id": "org-required-fields",
        "title": "补齐大群 14 天实名准入必填资料",
        "breadcrumb": "跑者视角 ▸ 档案与隐私 ▸ 大群准入必填资料",
        "role": "runner",
        "keywords": ["实名", "补齐", "14天", "复旦戈", "身份证", "紧急联系人", "班级", "届别", "服装尺码", "鞋码", "转正", "解冻"],
        "phrases": ["补齐实名资料", "填复旦戈资料", "14天实名认证", "填身份证和紧急联系人"],
        "default_reply": "正在直达「大群准入必填资料」表单并自动滚动高亮待填项目，提交即可完成实名核验。",
    },
    {
        "id": "privacy-settings",
        "title": "配置 4 级隐私保护与隐藏轨迹开关",
        "breadcrumb": "跑者视角 ▸ 档案与隐私 ▸ 隐私保护控制",
        "role": "runner",
        "keywords": ["隐私", "隐藏", "轨迹", "脱敏", "gps", "生理指标", "保密", "可见范围", "权限", "保护", "不让看"],
        "phrases": ["隐藏gps轨迹", "隐私设置", "不让别人看心率", "调整隐私开关"],
        "default_reply": "正在为您打开「4 级隐私保护设置」，可独立控制 GPS 轨迹脱敏、生理指标及寻搭子可见范围。",
    },
    {
        "id": "physio-profile",
        "title": "设置最大心率 / 静息心率与身体档案",
        "breadcrumb": "跑者视角 ▸ 档案与隐私 ▸ 训练档案 ▸ 体能生理指标",
        "role": "runner",
        "keywords": ["最大心率", "静息心率", "心率", "身高", "体重", "出生日期", "年龄", "vo2max", "最大摄氧量", "生理档案"],
        "phrases": ["修改最大心率", "设置静息心率", "填身高体重"],
        "default_reply": "正在跳转到体能生理指标配置区，修改后将实时校准您的 Karvonen 心率区间。",
    },
    {
        "id": "mileage-goals",
        "title": "设置周跑量与年度月度跑量目标",
        "breadcrumb": "跑者视角 ▸ 档案与隐私 ▸ 训练档案 ▸ 跑量目标",
        "role": "runner",
        "keywords": ["跑量目标", "周跑量", "月跑量", "年度跑量", "设定目标", "目标公里", "公里数"],
        "phrases": ["设置周跑量", "修改月跑量目标", "设定跑量计划"],
        "default_reply": "正在直达「跑量目标」设置区，您可以单独设定常规周跑量以及 12 个月的跑量计划。",
    },
    {
        "id": "race-plans",
        "title": "添加备赛比赛计划、AI 赛事情报与完赛照片",
        "breadcrumb": "跑者视角 ▸ 档案与隐私 ▸ 训练档案 ▸ 比赛计划",
        "role": "runner",
        "keywords": ["比赛计划", "备赛", "报名比赛", "赛事", "赛事情报", "完赛成绩", "完赛照片", "马拉松目标", "a类赛事", "b类赛事"],
        "phrases": ["添加备赛比赛", "查赛事情报", "上传完赛照片", "设置目标赛事"],
        "default_reply": "正在前往「比赛计划」面板，可添加备赛赛事、联网检索 AI 赛事情报并记录完赛荣誉。",
    },
    {
        "id": "data-purge",
        "title": "清除个人隐私数据与账号数据重置",
        "breadcrumb": "跑者视角 ▸ 档案与隐私 ▸ 数据生命周期与清除",
        "role": "runner",
        "keywords": ["清除数据", "删除资料", "注销", "清空记录", "清除隐私", "解绑注销"],
        "phrases": ["清除个人数据", "删除隐私资料", "清空我的记录"],
        "default_reply": "已为您定位至「数据生命周期管理」区，可安全执行隐私字段清除操作。",
    },
    # ── Runner: Training & Science ──
    {
        "id": "generate-plan",
        "title": "AI 生成或重新定制 Canova 周期训练课表",
        "breadcrumb": "跑者视角 ▸ Canova 训练 ▸ 定制训练计划",
        "role": "runner",
        "keywords": ["生成课表", "制定课表", "训练计划", "定制计划", "排课", "canova", "周期课表", "重新制定", "新课表"],
        "phrases": ["生成训练计划", "制定马拉松课表", "重新生成课表", "帮我排个训练计划"],
        "default_reply": "正在为您打开 Canova 周期训练计划定制面板，设置目标赛事与每周训练天数即可一键生成。",
    },
    {
        "id": "view-plan",
        "title": "查看本周训练课表、打卡与填写 RPE 体感",
        "breadcrumb": "跑者视角 ▸ Canova 训练 ▸ 本周课表矩阵",
        "role": "runner",
        "keywords": ["本周课表", "今日课表", "看课表", "打卡", "rpe", "体感", "训练内容", "怎么练"],
        "phrases": ["看今天的课表", "查看本周训练计划", "打卡今日训练", "填rpe体感"],
        "default_reply": "正在前往 Canova 科学训练中心，您可以查看本周每天课表、打卡完成并记录体感 RPE。",
    },
    {
        "id": "plan-versions",
        "title": "查看课表历史版本与一键回滚",
        "breadcrumb": "跑者视角 ▸ Canova 训练 ▸ 版本切换与回滚",
        "role": "runner",
        "keywords": ["版本", "回滚", "撤销", "历史课表", "恢复课表", "以前版本"],
        "phrases": ["回滚课表", "恢复之前的训练计划", "查看课表历史版本"],
        "default_reply": "正在打开课表历史版本切换器，可随时对比并一键回滚到过往任意版本。",
    },
    {
        "id": "ai-coach-chat",
        "title": "呼出 Canova AI 教练实时对话与身体反应调课",
        "breadcrumb": "全局右上角 / 浮标 ▸ Canova AI 教练对话舱",
        "role": "runner",
        "keywords": ["ai教练", "问教练", "调课", "身体反应", "疼", "累", "疲惫", "受伤", "酸痛", "睡眠不好", "对话", "聊", "感冒"],
        "phrases": ["问问ai教练", "腿疼怎么调整课表", "身体不舒服调课", "和canova教练对话"],
        "default_reply": "正在为您呼出 Canova AI 科学教练对话舱，点选身体反应标签即可结合负荷数据即时调课。",
    },
    {
        "id": "coach-report",
        "title": "Canova 多赛事战略诊断报告与冲突排查",
        "breadcrumb": "跑者视角 ▸ Canova 训练 ▸ 战略诊断报告",
        "role": "runner",
        "keywords": ["诊断报告", "战略诊断", "多赛事", "冲突", "宏观周期", "a/b/c", "优先级", "训练诊断"],
        "phrases": ["看战略诊断报告", "多赛事冲突诊断", "生成训练诊断"],
        "default_reply": "正在打开 Canova 战略诊断报告标签页，助您梳理多场赛事优先级与周期负荷分配。",
    },
    {
        "id": "vdot-analysis",
        "title": "查看 VDOT 跑力、体能负荷与生理曲线",
        "breadcrumb": "跑者视角 ▸ 生理与轨迹 ▸ VDOT 与负荷总览",
        "role": "runner",
        "keywords": ["vdot", "跑力", "ctl", "atl", "tsb", "生理", "hrv", "耐力系数", "完赛预测", "睡眠", "分析"],
        "phrases": ["看我的跑力", "查vdot", "看体能负荷曲线", "预测全马成绩"],
        "default_reply": "正在带您前往运动生理分析中心，查看最新有效 VDOT、五维耐力系数与 30 天生理恢复趋势。",
    },
    {
        "id": "taper-simulation",
        "title": "赛前 7 天减量 (Taper) 状态推演模拟器",
        "breadcrumb": "跑者视角 ▸ 生理与轨迹 ▸ Taper 减量推演",
        "role": "runner",
        "keywords": ["减量", "taper", "赛前", "推演", "状态模拟", "赛前一周", "降量"],
        "phrases": ["赛前减量推演", "taper模拟", "赛前一周怎么减量"],
        "default_reply": "正在定位至「赛前 7 天减量推演模拟器」，对比三套减量方案对比赛日 TSB 状态的影响。",
    },
    {
        "id": "pacer-eval",
        "title": "马拉松官方兔子（官兔）六维胜任度评估",
        "breadcrumb": "跑者视角 ▸ 生理与轨迹 ▸ 官兔潜能评估卡",
        "role": "runner",
        "keywords": ["官兔", "兔子", "配速员", "pacer", "稳健度", "履历", "评估"],
        "phrases": ["官兔评估", "能不能当兔子", "查看官兔胜任度", "配速员简历"],
        "default_reply": "正在跳转并滚动至「官兔六维胜任度评估卡」，可生成您的官方配速员量化履历。",
    },
    {
        "id": "pace-zones",
        "title": "查看 Renato Canova 6 级专项配速区间",
        "breadcrumb": "跑者视角 ▸ 生理与轨迹 ▸ Canova 配速矩阵",
        "role": "runner",
        "keywords": ["配速表", "配速区间", "pace zone", "轻松跑配速", "节奏跑配速", "马拉松配速", "区间"],
        "phrases": ["查看配速区间", "我的训练配速是多少", "打开canova配速表"],
        "default_reply": "正在前往生理分析页并为您自动展开「Canova 马拉松专项配速矩阵」。",
    },
    {
        "id": "share-card",
        "title": "生成 4K 炫跑战报分享海报",
        "breadcrumb": "跑者视角 ▸ 首页 / 生理分析 ▸ 4K 战报海报工坊",
        "role": "runner",
        "keywords": ["战报", "海报", "分享图", "4k", "炫跑", "发朋友圈", "长图", "战绩图"],
        "phrases": ["生成战报海报", "做一张跑步海报", "发朋友圈的4k战报"],
        "default_reply": "正在为您打开「4K 炫跑战报海报」工坊，可直接导出带轨迹与跑力水印的高清长图。",
    },
    {
        "id": "personal-report",
        "title": "生成个人周报 / 月报数据总结",
        "breadcrumb": "跑者视角 ▸ 首页工作台 ▸ 个人周报/月报",
        "role": "runner",
        "keywords": ["个人周报", "个人月报", "周总结", "月总结", "本周跑了多少", "本月跑量总结"],
        "phrases": ["看个人周报", "生成个人月报", "本周跑步总结"],
        "default_reply": "正在为您开启「个人周报 / 月报」面板，一键生成专属周期跑量与心率分布报告。",
    },
    # ── Club & Community ──
    {
        "id": "join-club-code",
        "title": "输入 6 位邀请码加入跑团",
        "breadcrumb": "跑者视角 ▸ 跑团与大群 ▸ 输入邀请码入团",
        "role": "runner",
        "keywords": ["邀请码", "加团", "入团", "进团", "6位码", "加入跑团"],
        "phrases": ["用邀请码加团", "输入跑团邀请码", "我有邀请码怎么进团"],
        "default_reply": "正在前往跑团中心并自动打开「输入 6 位邀请码入团」弹窗。",
    },
    {
        "id": "browse-clubs",
        "title": "浏览平台全部公开跑团并选择加入",
        "breadcrumb": "跑者视角 ▸ 跑团与大群 ▸ 浏览全部跑团",
        "role": "runner",
        "keywords": ["找跑团", "有哪些跑团", "所有跑团", "跑团列表", "加入跑团", "选跑团"],
        "phrases": ["有哪些跑团可以加", "找个跑团加入", "浏览所有跑团"],
        "default_reply": "正在为您打开平台全部跑团列表，可按城市与简介一键申请加入。",
    },
    {
        "id": "create-club",
        "title": "自建专属跑团并成为团长",
        "breadcrumb": "跑者视角 ▸ 跑团与大群 ▸ 自建跑团",
        "role": "runner",
        "keywords": ["自建跑团", "创建跑团", "建团", "当团长", "新建跑团", "开一个跑团"],
        "phrases": ["自己建一个跑团", "怎么创建跑团", "我要自建跑团"],
        "default_reply": "正在前往跑团中心并拉起「创建专属跑团」向导，填写团名与城市即可创建。",
    },
    {
        "id": "join-org",
        "title": "加入大群体与戈友实名认证",
        "breadcrumb": "跑者视角 ▸ 跑团与大群 ▸ 加入大群体 / 戈友认证",
        "role": "runner",
        "keywords": ["大群", "大群体", "复旦戈", "校友", "戈友", "戈壁", "加入大群", "emba"],
        "phrases": ["加入复旦戈大群", "加入大群体", "戈友实名认证"],
        "default_reply": "正在为您打开「加入大群体 · 戈友认证」弹窗，输入大群邀请码或填写实名信息即可入驻。",
    },
    {
        "id": "weekend-events",
        "title": "周末约跑配速列车报名上车",
        "breadcrumb": "跑者视角 ▸ 跑团与大群 ▸ 约跑活动与配速列车",
        "role": "runner",
        "keywords": ["约跑", "合练", "周末", "活动", "配速列车", "上车", "报名", "门岗", "世纪公园"],
        "phrases": ["参加周末约跑", "报名配速列车", "看跑团合练活动"],
        "default_reply": "正在直达「周末约跑与配速列车」活动列表，可查看集合门岗并选择目标配速列车上车。",
    },
    {
        "id": "mentorship-bind",
        "title": "跑团师徒结对绑定",
        "breadcrumb": "跑者视角 ▸ 跑团与大群 ▸ 排行榜 ▸ 师徒结对",
        "role": "runner",
        "keywords": ["师徒", "拜师", "收徒", "导师", "徒弟", "师傅", "结对"],
        "phrases": ["绑定师徒关系", "找个跑团师傅", "我要拜师"],
        "default_reply": "正在前往跑团中心并为您打开「师徒结对」绑定面板。",
    },
    {
        "id": "discover-buddies",
        "title": "六维同频寻搭子（同城约跑友）",
        "breadcrumb": "跑者视角 ▸ 同频寻搭子",
        "role": "runner",
        "keywords": ["搭子", "跑友", "找人跑", "同频", "公园", "地标", "周pk", "附近跑者", "约搭子", "关注"],
        "phrases": ["找跑步搭子", "同城找跑友", "六维寻搭子", "找附近同配速的人"],
        "default_reply": "正在进入「六维同频寻搭子」，系统将按年龄组别、VDOT 配速与常跑地标为您匹配跑友。",
    },
    {
        "id": "showcase-plaza",
        "title": "选团与名帅风采展厅",
        "breadcrumb": "跑者视角 ▸ 选团与名帅",
        "role": "public",
        "keywords": ["展厅", "名帅", "名团", "宣传页", "教练履历", "合练照片", "选团", "风采", "品牌主页"],
        "phrases": ["看名帅教练展厅", "浏览跑团宣传页", "选团风采展厅"],
        "default_reply": "正在进入「选团与名帅风采展厅」，可查看手表防伪核验战绩与认证教练履历。",
    },
    {
        "id": "leave-club",
        "title": "退出当前跑团",
        "breadcrumb": "跑者视角 ▸ 跑团与大群 ▸ 退出跑团",
        "role": "runner",
        "keywords": ["退团", "退出跑团", "离开跑团", "不想待在团里"],
        "phrases": ["退出当前跑团", "怎么退团"],
        "default_reply": "正在前往跑团中心并拉起退出跑团二次确认面板，请注意退团不会删除您的个人跑步记录。",
    },
    # ── Leader (Captain & Coach) ──
    {
        "id": "captain-cockpit",
        "title": "团长运营驾驶舱与成员花名册",
        "breadcrumb": "团/教视角 ▸ 团长驾驶舱",
        "role": "leader",
        "keywords": ["团长", "驾驶舱", "花名册", "激活率", "达标率", "成员管理", "管理跑团", "未绑表"],
        "phrases": ["打开团长驾驶舱", "看全团花名册", "管理跑团成员"],
        "default_reply": "正在为您切换至团/教视角并打开「团长运营驾驶舱」。",
    },
    {
        "id": "club-invite-poster",
        "title": "生成跑团入团邀请码与分享海报",
        "breadcrumb": "团/教视角 ▸ 团长驾驶舱 ▸ 邀请码与拉新海报",
        "role": "leader",
        "keywords": ["邀请海报", "二维码", "小程序码", "拉新", "邀人进团", "分享跑团", "团邀请码"],
        "phrases": ["生成入团邀请海报", "分享跑团邀请码", "导出入团二维码"],
        "default_reply": "正在打开跑团专属邀请码与高清拉新海报生成器。",
    },
    {
        "id": "club-report",
        "title": "生成跑团周报 / 月报与微信接龙文案",
        "breadcrumb": "团/教视角 ▸ 战报播报室 ▸ 跑团周报/月报",
        "role": "leader",
        "keywords": ["跑团周报", "跑团月报", "接龙", "播报", "战报长图", "csv", "团队报表", "导出明细"],
        "phrases": ["生成跑团周报", "导出微信群接龙", "做跑团月报海报"],
        "default_reply": "正在打开「跑团周报 / 月报三视图工坊」，支持长图海报、CSV 表格与微信接龙一键复制。",
    },
    {
        "id": "targeted-recruit",
        "title": "团长 / 教练多维靶向纳新",
        "breadcrumb": "团/教视角 ▸ 团长驾驶舱 ▸ 靶向纳新漏斗",
        "role": "leader",
        "keywords": ["靶向纳新", "纳新", "招人", "招募", "挖人", "邀请未入团", "未入团跑友"],
        "phrases": ["怎么靶向纳新", "招募周边活跃跑友", "打开纳新面板"],
        "default_reply": "正在进入团长管理页并定位至「多维靶向纳新与漏斗」工作区。",
    },
    {
        "id": "create-club-event",
        "title": "发起跑团周末约跑或月度挑战活动",
        "breadcrumb": "团/教视角 ▸ 选兔与约跑 ▸ 发起跑团活动",
        "role": "leader",
        "keywords": ["发起活动", "发布约跑", "组织合练", "创建活动", "新建挑战赛", "编组列车"],
        "phrases": ["发起周末约跑", "发布跑团活动", "组织一次合练"],
        "default_reply": "正在为您切换至活动页签并拉起「发起跑团活动 / 配速列车」弹窗。",
    },
    {
        "id": "club-broadcast",
        "title": "发送全团通知公告与站内广播",
        "breadcrumb": "团/教视角 ▸ 团长驾驶舱 ▸ 全团消息广播",
        "role": "leader",
        "keywords": ["广播", "群发", "全团通知", "发公告", "提醒全团"],
        "phrases": ["发全团通知", "给全团群发消息", "发布跑团公告"],
        "default_reply": "正在打开「全团广播通知」发送窗口，支持直达全团成员消息中心。",
    },
    {
        "id": "club-showcase-studio",
        "title": "装修跑团对外宣传主页与合练照片墙",
        "breadcrumb": "团/教视角 ▸ 团长驾驶舱 ▸ 宣传主页工坊",
        "role": "leader",
        "keywords": ["装修跑团", "跑团宣传页", "上传合练照片", "编辑品牌主页", "跑团相册"],
        "phrases": ["装修跑团宣传页", "上传跑团照片", "美化跑团主页"],
        "default_reply": "正在为您开启「跑团品牌宣传工坊」，可编辑宣传文案与上传高清合练相册。",
    },
    {
        "id": "coach-showcase-studio",
        "title": "装修教练认证履历与个人风采页",
        "breadcrumb": "团/教视角 ▸ 教练工作台 ▸ 教练风采工坊",
        "role": "leader",
        "keywords": ["教练主页", "教练履历", "教练证书", "装修教练", "带教风采"],
        "phrases": ["编辑教练履历", "装修我的教练风采页"],
        "default_reply": "正在打开「教练风采工坊」，可配置您的带教资质、成绩背书与学员案例。",
    },
    {
        "id": "coach-compass",
        "title": "教练全队体能信号灯罗盘 & 选兔雷达",
        "breadcrumb": "团/教视角 ▸ 教练信号灯罗盘",
        "role": "leader",
        "keywords": ["信号灯", "罗盘", "选兔雷达", "红黄绿", "队员风险", "过载", "教练工作台", "看学员状态"],
        "phrases": ["打开教练信号灯", "查看队员风险筛查", "看选兔雷达"],
        "default_reply": "正在切换至「教练全队体能信号灯罗盘」，自动将 TSB 过载与伤痛预警队员置顶。",
    },
    {
        "id": "import-schedule",
        "title": "智能导入周训练课表 (Excel 文本 / 截图识别)",
        "breadcrumb": "团/教视角 ▸ 教练工作台 ▸ 智能课表导入",
        "role": "leader",
        "keywords": ["导入课表", "excel", "表格", "截图识别", "ocr", "解析课表", "a/b/c组", "粘贴课表", "导入周计划"],
        "phrases": ["导入excel课表", "上传课表截图", "智能识别周训练表"],
        "default_reply": "正在进入教练工作台并自动拉起「智能周课表导入器」，支持粘贴表格或上传截图自动分组。",
    },
    {
        "id": "assign-template",
        "title": "使用课表模板批量派发给队员",
        "breadcrumb": "团/教视角 ▸ 教练工作台 ▸ 批量派课",
        "role": "leader",
        "keywords": ["批量派课", "派发课表", "下发计划", "课表模板", "给全队排课", "分配训练"],
        "phrases": ["批量派发课表", "给队员下发训练模板", "全团批量排课"],
        "default_reply": "正在进入教练工作台并自动弹出「模板批量派课」向导。",
    },
    {
        "id": "batch-critique",
        "title": "教练 5 秒连续批阅三栏舱",
        "breadcrumb": "团/教视角 ▸ 5秒批阅排课",
        "role": "leader",
        "keywords": ["批阅", "点评", "5秒", "三栏", "批量点评", "审课", "评价打卡"],
        "phrases": ["打开5秒批阅", "连续点评队员打卡", "教练批量批阅"],
        "default_reply": "正在直达「教练 5 秒连续批阅三栏舱」，支持快捷键与词条连发自动切换下一位队员。",
    },
    # ── Org Admin & Super Admin ──
    {
        "id": "org-roster-audit",
        "title": "大群 14 天实名花名册核验与转正",
        "breadcrumb": "管理视角 ▸ 大群实名核验 ▸ 花名册审计",
        "role": "org_admin",
        "keywords": ["花名册", "实名核验", "审核转正", "超期解冻", "保险名单", "大群成员", "导出名单", "待审"],
        "phrases": ["审核大群实名名单", "打开大群花名册", "导出大群保险名单", "14天实名核验"],
        "default_reply": "正在为您切换至管理视角并打开「大群 14 天实名花名册核验台」。",
    },
    {
        "id": "org-pk-report",
        "title": "大群全域报表与下属分跑团 PK 榜",
        "breadcrumb": "管理视角 ▸ 大群工作台 ▸ 全域报表与分团 PK",
        "role": "org_admin",
        "keywords": ["分团pk", "大群报表", "全域报表", "分跑团对比", "跨团统计", "未分配分团"],
        "phrases": ["看分跑团pk", "打开大群全域报表", "统计各分团跑量"],
        "default_reply": "正在打开「大群全域报表与分跑团 PK 驾驶舱」。",
    },
    {
        "id": "org-cross-events",
        "title": "发起跨跑团联合大合练或分团对抗赛",
        "breadcrumb": "管理视角 ▸ 大群工作台 ▸ 跨跑团联合活动",
        "role": "org_admin",
        "keywords": ["跨团活动", "大合练", "分团对抗赛", "联合活动", "大群活动"],
        "phrases": ["发起跨分团大合练", "创建分跑团对抗赛"],
        "default_reply": "正在拉起「跨跑团联合活动」发起窗口，可勾选参与分团并设置跑量挑战规则。",
    },
    {
        "id": "org-field-rules",
        "title": "配置大群入队必填字段规则",
        "breadcrumb": "管理视角 ▸ 大群工作台 ▸ 入队必填规则",
        "role": "org_admin",
        "keywords": ["必填字段", "入队字段", "字段规则", "设置必填", "表单规则"],
        "phrases": ["配置大群必填字段", "修改入队表单要求"],
        "default_reply": "正在打开「大群入队字段规则配置」，可自定义必填、选填与隐藏项。",
    },
    {
        "id": "org-settings",
        "title": "大群基础设置与免码/邀请码模式",
        "breadcrumb": "管理视角 ▸ 大群工作台 ▸ 大群设置",
        "role": "org_admin",
        "keywords": ["大群设置", "免码入会", "大群邀请码", "修改大群信息"],
        "phrases": ["修改大群邀请码", "设置大群免码加入"],
        "default_reply": "正在打开「大群基础信息与入会模式设置」。",
    },
    {
        "id": "admin-orgs",
        "title": "平台超管：大群与分团治理拓扑树",
        "breadcrumb": "管理视角 ▸ 超管控制台 ▸ 大群与分团树",
        "role": "super_admin",
        "keywords": ["超管", "拓扑树", "新建大群", "指派团长", "挂载分团", "超级管理员", "平台管理"],
        "phrases": ["打开超管控制台", "新建大群和分团", "超管拓扑树"],
        "default_reply": "正在进入「平台超管 · 大群与分团治理拓扑树」。",
    },
    {
        "id": "admin-unaffiliated",
        "title": "平台超管：自由跑者待引导池",
        "breadcrumb": "管理视角 ▸ 超管控制台 ▸ 自由跑者池",
        "role": "super_admin",
        "keywords": ["自由跑者", "未入团池", "散客", "待引导跑者"],
        "phrases": ["看未入团自由跑者池", "引导自由跑者入团"],
        "default_reply": "正在前往「超管 · 自由跑者待引导池」。",
    },
    {
        "id": "admin-analytics",
        "title": "平台超管：全站增长漏斗与遥测大盘",
        "breadcrumb": "管理视角 ▸ 超管控制台 ▸ 全站增长遥测",
        "role": "super_admin",
        "keywords": ["遥测", "dau", "增长漏斗", "留存", "行为分析", "埋点", "转化率"],
        "phrases": ["看全站dau和遥测", "查看激活转化漏斗"],
        "default_reply": "正在打开「超管 · 全站增长漏斗与遥测大盘」。",
    },
    {
        "id": "admin-support",
        "title": "平台超管：设备同步与 AI 运维排障工单",
        "breadcrumb": "管理视角 ▸ 超管控制台 ▸ 设备与AI运维",
        "role": "super_admin",
        "keywords": ["工单", "反馈", "运维", "排障", "客服", "报错监控"],
        "phrases": ["看用户反馈工单", "打开设备与ai运维"],
        "default_reply": "正在打开「超管 · 设备同步与 AI 运维排障」台账。",
    },
]

WORKFLOW_MAP: Dict[str, Dict[str, Any]] = {w["id"]: w for w in ASSISTANT_WORKFLOWS}


def _extract_bigrams(text: str) -> set:
    cleaned = re.sub(r"[\s，。！？、,.!?/\\\-_:：()（）【】]+", "", text.lower())
    if len(cleaned) < 2:
        return {cleaned} if cleaned else set()
    return {cleaned[i : i + 2] for i in range(len(cleaned) - 1)}


def _has_role_permission(role_required: str, user_roles: Dict[str, Any]) -> bool:
    if role_required in ("public", "runner"):
        return True
    is_super = bool(user_roles.get("is_super_admin"))
    if role_required == "super_admin":
        return is_super
    if role_required == "org_admin":
        return bool(user_roles.get("has_managed_org")) or is_super
    if role_required == "leader":
        return bool(user_roles.get("is_coach_or_owner")) or is_super
    return True


def _role_denial_hint(wf: Dict[str, Any]) -> str:
    role = wf.get("role")
    if role == "leader":
        return (
            f"「{wf['title']}」需要跑团团长或认证教练权限。您当前为普通跑者账号，"
            f"可以先点击下方「自建跑团」成为团长，或前往「选团与名帅展厅」申请成为认证教练。"
        )
    if role == "org_admin":
        return (
            f"「{wf['title']}」需要大群主理人或大群管理员权限。普通跑者可通过「加入大群体」参与大群实名认证。"
        )
    if role == "super_admin":
        return f"「{wf['title']}」仅限平台超级管理员访问。您可以先使用跑者工作台或团长/教练相关功能。"
    return f"当前账号暂无访问「{wf['title']}」的权限。"


def score_workflows_deterministic(
    query: str,
    user_roles: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Fast deterministic Chinese + English intent scorer over ASSISTANT_WORKFLOWS.
    Combines exact phrase hits, keyword hits, and Chinese character bigram overlap.
    """
    q = (query or "").strip().lower()
    roles = user_roles or {}
    q_bigrams = _extract_bigrams(q)

    scored: List[Dict[str, Any]] = []
    for wf in ASSISTANT_WORKFLOWS:
        score = 0.0
        title_low = wf["title"].lower()
        crumb_low = wf["breadcrumb"].lower()

        if q and q in title_low:
            score += 6.0
        for phrase in wf.get("phrases", []):
            p_low = phrase.lower()
            if p_low in q:
                score += 10.0
            elif q and q in p_low:
                score += 5.0

        for kw in wf.get("keywords", []):
            k_low = kw.lower()
            if k_low in q:
                score += 4.2 + min(2.0, len(k_low) * 0.35)

        # Specific compound disambiguation boosts
        if ("手表" in q or "绑" in q) and wf["id"] == "bind-garmin" and "高驰" not in q and "coros" not in q:
            score += 1.5
        if ("课表" in q or "计划" in q) and ("导入" in q or "excel" in q or "表格" in q or "截图" in q):
            if wf["id"] == "import-schedule":
                score += 6.0
        elif ("课表" in q or "计划" in q) and ("批量" in q or "派" in q or "下发" in q or "模板" in q):
            if wf["id"] == "assign-template":
                score += 6.0
        elif ("课表" in q or "计划" in q) and ("生成" in q or "制定" in q or "定制" in q or "新" in q or "重" in q):
            if wf["id"] == "generate-plan":
                score += 5.5
        if ("周报" in q or "月报" in q) and ("团" in q or "全队" in q or "接龙" in q):
            if wf["id"] == "club-report":
                score += 6.0
        elif ("周报" in q or "月报" in q) and "大群" in q:
            if wf["id"] == "org-pk-report":
                score += 6.0
        elif ("周报" in q or "月报" in q) and wf["id"] == "personal-report":
            score += 4.0
        if ("实名" in q or "复旦戈" in q or "14天" in q) and ("审核" in q or "核验" in q or "花名册" in q or "转正" in q or "管理员" in q):
            if wf["id"] == "org-roster-audit":
                score += 6.5
        elif ("实名" in q or "复旦戈" in q or "14天" in q or "紧急联系人" in q or "身份证" in q) and ("补" in q or "填" in q or "我" in q):
            if wf["id"] == "org-required-fields":
                score += 6.5
        if ("邀请码" in q or "海报" in q) and ("生成" in q or "分享" in q or "发给" in q or "拉新" in q) and "战报" not in q:
            if wf["id"] == "club-invite-poster":
                score += 5.5

        target_bigrams = _extract_bigrams(wf["title"] + " " + " ".join(wf.get("keywords", [])))
        if q_bigrams and target_bigrams:
            overlap = len(q_bigrams & target_bigrams)
            score += overlap * 0.9

        # Slight tie-breaker favoring permitted role when scores tie
        if _has_role_permission(wf["role"], roles):
            score += 0.25

        # Normalize rough confidence between 0 and 0.98
        confidence = min(0.98, round(score / 14.0, 2)) if score > 0 else 0.15
        scored.append({"workflow": wf, "score": score, "confidence": confidence})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def _parse_llm_json(raw: str) -> Optional[Dict[str, Any]]:
    text = (raw or "").strip()
    if not text:
        return None
    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        brace_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if brace_match:
            text = brace_match.group(0)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _build_llm_catalog_prompt() -> str:
    lines = []
    for wf in ASSISTANT_WORKFLOWS:
        lines.append(f"- {wf['id']} | 角色:{wf['role']} | {wf['title']} | 关键词:{','.join(wf['keywords'][:6])}")
    return "\n".join(lines)


@router.post("/navigate")
def navigate_by_intent(payload: NavigateRequest, request: Request = None) -> Dict[str, Any]:
    """
    Understands a runner/captain/coach/admin's natural-language goal and returns
    the primary target workflow ID, alternatives, friendly reply, and navigation permission status.
    """
    enforce_rate_limit(
        "assistant_nav",
        get_client_ip(request),
        max_calls=30,
        window_seconds=300,
        detail="AI 向导请求过于频繁，请稍后再试",
    )
    query = (payload.query or "").strip()[:200]
    if not query:
        raise HTTPException(status_code=400, detail="请输入或说出您的操作目的")

    user_roles = payload.user_roles or {}
    if "logged_in" not in user_roles:
        # Default to logged_in=True when caller didn't explicitly send false
        user_roles = {**user_roles, "logged_in": True}

    ranked = score_workflows_deterministic(query, user_roles)
    top_det = ranked[0]
    det_primary_id = top_det["workflow"]["id"]
    det_alt_ids = [r["workflow"]["id"] for r in ranked[1:3]]

    chosen_primary_id = det_primary_id
    chosen_alt_ids = det_alt_ids
    chosen_reply = top_det["workflow"]["default_reply"]
    chosen_conf = top_det["confidence"]
    used_llm = False

    top_score = float(top_det.get("score") or 0.0)
    second_score = float(ranked[1].get("score") or 0.0) if len(ranked) > 1 else 0.0
    strong_det_hit = (top_score >= 16.0) and ((top_score - second_score) >= 4.0)

    # Short-circuit unambiguous deterministic matches to save tokens; invoke fast LLM for ambiguous queries
    if not strong_det_hit and llm_client._get_client() is not None and len(query) >= 2:
        catalog_text = _build_llm_catalog_prompt()
        role_summary = (
            f"logged_in={bool(user_roles.get('logged_in'))}, "
            f"is_coach_or_owner={bool(user_roles.get('is_coach_or_owner'))}, "
            f"has_managed_org={bool(user_roles.get('has_managed_org'))}, "
            f"is_super_admin={bool(user_roles.get('is_super_admin'))}"
        )
        system_prompt = (
            "你是「万跑跑团助手」的 AI 操作向导。用户可能用口语或语音描述他们想完成的操作。\n"
            "请从下面唯一的流程清单中选择最匹配的 1 个主推流程 primary_id 和 0~2 个相关备选 alternative_ids。\n"
            "严格只输出合法 JSON 对象，格式为：\n"
            '{"primary_id":"...","alternative_ids":["..."],"reply":"不超过45字的中文友好引导","confidence":0.92}\n\n'
            f"流程清单：\n{catalog_text}"
        )
        user_prompt = (
            f"用户当前页面：{payload.current_path or '/dashboard'}\n"
            f"用户权限：{role_summary}\n"
            f"用户操作目的：{query}"
        )
        try:
            raw = llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=getattr(settings, "LLM_MODEL_FAST", "qwen-flash"),
                temperature=0.1,
                max_tokens=360,
                disable_thinking=True,
            )
            parsed = _parse_llm_json(raw)
            if parsed and parsed.get("primary_id") in WORKFLOW_MAP:
                chosen_primary_id = str(parsed["primary_id"])
                raw_alts = parsed.get("alternative_ids") or []
                valid_alts = [
                    str(aid)
                    for aid in raw_alts
                    if isinstance(aid, str) and aid in WORKFLOW_MAP and aid != chosen_primary_id
                ][:2]
                chosen_alt_ids = valid_alts if valid_alts else [
                    r["workflow"]["id"] for r in ranked if r["workflow"]["id"] != chosen_primary_id
                ][:2]
                if isinstance(parsed.get("reply"), str) and parsed["reply"].strip():
                    chosen_reply = parsed["reply"].strip()
                try:
                    conf_val = float(parsed.get("confidence", 0.9))
                    chosen_conf = max(0.2, min(0.99, round(conf_val, 2)))
                except Exception:
                    chosen_conf = 0.9
                used_llm = True
        except Exception as e:
            logger.warning(f"[assistant] LLM navigation fallback to deterministic: {e}")

    primary_wf = WORKFLOW_MAP[chosen_primary_id]
    permission_ok = _has_role_permission(primary_wf["role"], user_roles)
    requires_auth = primary_wf["role"] != "public" and not bool(user_roles.get("logged_in", True))

    if not permission_ok:
        auto_navigate = False
        chosen_reply = _role_denial_hint(primary_wf)
        # Ensure at least one accessible alternative (e.g., create-club or showcase-plaza) is suggested
        if primary_wf["role"] == "leader" and "create-club" not in chosen_alt_ids:
            chosen_alt_ids = ["create-club"] + [a for a in chosen_alt_ids if a != "create-club"][:1]
        elif primary_wf["role"] == "org_admin" and "join-org" not in chosen_alt_ids:
            chosen_alt_ids = ["join-org"] + [a for a in chosen_alt_ids if a != "join-org"][:1]
    else:
        auto_navigate = chosen_conf >= 0.35

    return {
        "success": True,
        "query": query,
        "primary_id": chosen_primary_id,
        "alternative_ids": chosen_alt_ids,
        "reply": chosen_reply,
        "confidence": chosen_conf,
        "auto_navigate": auto_navigate,
        "permission_ok": permission_ok,
        "requires_auth": requires_auth,
        "engine": "llm" if used_llm else "deterministic",
    }


def _extract_text_from_recognition_result(res: Any) -> str:
    if res is None:
        return ""
    try:
        sentence = res.get_sentence() if hasattr(res, "get_sentence") else None
    except Exception:
        sentence = None
    if not sentence and isinstance(getattr(res, "output", None), dict):
        sentence = res.output.get("sentence")
    if isinstance(sentence, list):
        parts = []
        for s in sentence:
            if isinstance(s, dict) and s.get("text"):
                parts.append(str(s["text"]).strip())
        return "".join(parts).strip()
    if isinstance(sentence, dict):
        return str(sentence.get("text") or "").strip()
    return ""


def _extract_text_from_multimodal_response(res: Any) -> str:
    try:
        output = getattr(res, "output", None)
        choices = output.get("choices") if isinstance(output, dict) else getattr(output, "choices", None)
        if not choices:
            return ""
        msg = choices[0].get("message") if isinstance(choices[0], dict) else getattr(choices[0], "message", None)
        content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("text"):
                    parts.append(str(item["text"]).strip())
            return "".join(parts).strip()
    except Exception:
        return ""
    return ""


def _transcribe_wav_via_dashscope(wav_path: str) -> tuple[str, str]:
    """
    Transcribes a local 16kHz WAV file via Alibaba DashScope.
    Tries Paraformer real-time Recognition first, then falls back to Qwen-ASR models.
    """
    api_key = (settings.DASHSCOPE_API_KEY or settings.OPENAI_API_KEY or "").strip()
    if not api_key or api_key.startswith("sk-your"):
        raise RuntimeError("未配置 DASHSCOPE_API_KEY，无法使用云端语音识别")

    import dashscope
    dashscope.api_key = api_key
    workspace = (settings.DASHSCOPE_WORKSPACE_ID or "").strip() or None

    # 1. Inspect RIFF WAV header before calling DashScope Paraformer Realtime v2
    is_riff_wav = False
    detected_sample_rate = 16000
    try:
        with open(wav_path, "rb") as wf:
            hdr = wf.read(44)
        if len(hdr) >= 28 and hdr[:4] == b"RIFF" and hdr[8:12] == b"WAVE":
            is_riff_wav = True
            sr = int.from_bytes(hdr[24:28], "little")
            if 8000 <= sr <= 48000:
                detected_sample_rate = sr
    except OSError:
        pass

    if is_riff_wav:
        try:
            from dashscope.audio.asr import Recognition

            rec_kwargs: Dict[str, Any] = {
                "model": "paraformer-realtime-v2",
                "callback": None,
                "format": "wav",
                "sample_rate": detected_sample_rate,
                "api_key": api_key,
            }
            if workspace:
                rec_kwargs["workspace"] = workspace
            rec = Recognition(**rec_kwargs)
            result = rec.call(wav_path)
            text = _extract_text_from_recognition_result(result)
            if text:
                return text, "paraformer-realtime-v2"
        except Exception as e:
            logger.warning(f"[assistant] Paraformer ASR failed, trying Qwen-ASR fallback: {e}")

    # 2. Fallback: Qwen3-ASR-Flash / Qwen-Audio-ASR via MultiModalConversation
    from dashscope import MultiModalConversation

    for model_name in ("qwen3-asr-flash", "qwen-audio-asr"):
        try:
            call_kwargs: Dict[str, Any] = {
                "model": model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": [{"audio": f"file://{wav_path}"}],
                    }
                ],
                "api_key": api_key,
            }
            if workspace:
                call_kwargs["workspace"] = workspace
            res = MultiModalConversation.call(**call_kwargs)
            status_code = getattr(res, "status_code", 200)
            if status_code in (None, 200):
                text = _extract_text_from_multimodal_response(res)
                if text:
                    return text, model_name
        except Exception as e:
            logger.warning(f"[assistant] Fallback ASR model {model_name} failed: {e}")

    return "", "none"


@router.post("/transcribe")
async def transcribe_voice_audio(
    request: Request = None,
    audio: UploadFile = File(...),
) -> Dict[str, Any]:
    """
    Accepts recorded audio from the browser microphone and returns recognized Chinese text.
    """
    enforce_rate_limit(
        "assistant_asr",
        get_client_ip(request),
        max_calls=20,
        window_seconds=300,
        detail="语音识别请求过于频繁，请稍后再试",
    )
    raw_bytes = await audio.read(MAX_AUDIO_BYTES + 1)
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="录音文件为空，请重新录制后再试")
    if len(raw_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="录音文件超过 5MB 上限，请控制在 30 秒以内")

    # Detect actual audio container by magic bytes before relying on client filename
    if len(raw_bytes) >= 12 and raw_bytes[:4] == b"RIFF" and raw_bytes[8:12] == b"WAVE":
        suffix = ".wav"
    elif raw_bytes[:4] == b"\x1a\x45\xdf\xa3":
        suffix = ".webm"
    elif raw_bytes[:4] == b"OggS":
        suffix = ".ogg"
    else:
        suffix = os.path.splitext(audio.filename or "voice.wav")[1].lower() or ".wav"
        if suffix not in (".wav", ".pcm", ".mp3", ".m4a", ".webm", ".ogg"):
            suffix = ".wav"

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_f:
            tmp_f.write(raw_bytes)
            tmp_path = tmp_f.name

        text, engine = await run_in_threadpool(_transcribe_wav_via_dashscope, tmp_path)
        if not text:
            return {
                "success": False,
                "text": "",
                "engine": engine,
                "detail": "未能识别到清晰语音，请靠近麦克风重试或直接输入文字",
            }
        return {
            "success": True,
            "text": text,
            "engine": engine,
        }
    except HTTPException:
        raise
    except RuntimeError as cfg_err:
        return {
            "success": False,
            "text": "",
            "engine": "unconfigured",
            "detail": str(cfg_err),
        }
    except Exception as e:
        logger.error(f"[assistant] Transcribe failed: {e}")
        raise HTTPException(status_code=500, detail=f"语音识别服务暂不可用：{str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
