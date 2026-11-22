export type WorkflowCategory = "onboarding" | "runner" | "club" | "leader" | "admin";
export type WorkflowRoleRequired = "public" | "runner" | "leader" | "org_admin" | "super_admin";
export type WorkflowPerspective = "runner" | "leader" | "admin";
export type WorkflowActionType = "navigate" | "open-coach-chat" | "toggle-theme" | "open-auth";

export interface UserRoleFlags {
  loggedIn?: boolean;
  isCoachOrOwner?: boolean;
  hasManagedOrg?: boolean;
  isSuperAdmin?: boolean;
}

export interface WorkflowEntry {
  id: string;
  title: string;
  breadcrumb: string;
  desc: string;
  steps: string[];
  category: WorkflowCategory;
  roleRequired: WorkflowRoleRequired;
  perspective?: WorkflowPerspective;
  href?: string;
  actionType?: WorkflowActionType;
  keywords: string[];
}

export const WORKFLOW_CATALOG: WorkflowEntry[] = [
  // ── Onboarding / Public ──
  {
    id: "auth-login",
    title: "登录 / 注册 / 微信扫码登录",
    breadcrumb: "顶栏 ▸ 登录 / 注册入口",
    desc: "支持微信扫码一键登入与账号密码登录，自动同步小程序跑团与手表数据。",
    steps: [
      "选择「微信扫码」或「账号密码 / 注册」标签页",
      "登录后系统自动同步您的跑团、课表与手表连接状态",
    ],
    category: "onboarding",
    roleRequired: "public",
    href: "/login",
    actionType: "open-auth",
    keywords: ["登录", "注册", "扫码", "微信登录", "账号", "login", "auth"],
  },
  {
    id: "manual-guide",
    title: "新用户操作手册与 FAQ 排障",
    breadcrumb: "跑者视角 ▸ 帮助手册 ▸ 新手上手指南",
    desc: "3 分钟了解绑表双区切换、14 天大群实名规则与常见同步问题排查。",
    steps: [
      "按顶部锚点直接跳至「绑定手表」「复旦戈准入」或「FAQ」",
      "可随时通过右上角或快捷键 ⌘/ 呼出 AI 操作助手带路",
    ],
    category: "onboarding",
    roleRequired: "public",
    perspective: "runner",
    href: "/dashboard/manual",
    actionType: "navigate",
    keywords: ["手册", "教程", "新手", "指南", "帮助", "faq", "怎么用", "入门", "说明"],
  },
  {
    id: "toggle-theme",
    title: "切换暗黑 / 明亮界面主题",
    breadcrumb: "侧边栏底部 / 顶栏 ▸ 主题切换",
    desc: "在 Obsidian Dark 曜石暗黑与 Volt Light 竞技亮色之间即时切换并持久化记忆。",
    steps: [
      "已为您直接切换全局配色主题",
      "也可随时在左侧边栏底部或顶栏一键切换",
    ],
    category: "onboarding",
    roleRequired: "public",
    actionType: "toggle-theme",
    keywords: ["主题", "暗黑", "明亮", "亮色", "深色", "浅色", "夜间", "白天", "theme", "light", "dark"],
  },
  {
    id: "runner-home",
    title: "跑者全息工作台首页",
    breadcrumb: "跑者视角 ▸ 首页工作台",
    desc: "集中查看今日 Canova 处方、三维跑量圆环、30 天 PMC 负荷曲线与跑团榜单。",
    steps: [
      "顶部可点击「同步手表数据」或查看「个人周报/月报」",
      "今日处方卡片支持直接记录体感 RPE 并唤起 AI 教练",
    ],
    category: "onboarding",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard",
    actionType: "navigate",
    keywords: ["首页", "工作台", "总览", "看板", "dashboard", "主页", "今日训练"],
  },

  // ── Runner: Devices & Profile & Privacy ──
  {
    id: "bind-garmin",
    title: "绑定 Garmin 佳明运动手表",
    breadcrumb: "跑者视角 ▸ 档案与隐私 ▸ 手表连接 ▸ 绑定佳明",
    desc: "支持中国区 (garmin.cn) 与国际区 (garmin.com) 双分区直连与后台静默同步。",
    steps: [
      "确认账号所属分区（国内行货选中国区 garmin.cn，海外账号选国际区）",
      "输入 Garmin Connect 邮箱与密码完成认证，1–3 分钟内同步历史记录",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/profile?tab=device&open=bind-garmin",
    actionType: "navigate",
    keywords: ["佳明", "garmin", "手表", "绑表", "绑定佳明", "中国区", "国际区", "garmin.cn", "garmin.com"],
  },
  {
    id: "bind-coros",
    title: "绑定 COROS 高驰运动手表",
    breadcrumb: "跑者视角 ▸ 档案与隐私 ▸ 手表连接 ▸ 绑定高驰",
    desc: "支持高驰 App 账号密码直连，自动同步跑步轨迹、心率与体能负荷。",
    steps: [
      "在弹窗中核对高驰账号区服（中国区 / 国际区）",
      "输入 COROS App 手机号或邮箱及密码完成绑定",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/profile?tab=device&open=bind-coros",
    actionType: "navigate",
    keywords: ["高驰", "coros", "手表", "绑表", "绑定高驰", "高驰直连"],
  },
  {
    id: "sync-watch",
    title: "手动同步最新手表跑步记录",
    breadcrumb: "跑者视角 ▸ 首页工作台 ▸ 同步手表数据",
    desc: "立即触发佳明 / 高驰后台数据拉取，更新今日打卡里程、配速与 HRV 指标。",
    steps: [
      "已为您自动触发手表同步请求，请稍候数秒查看最新跑步卡片",
      "若提示账号失效，可前往「档案与隐私 ▸ 手表连接」重新授权",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard?open=sync-watch",
    actionType: "navigate",
    keywords: ["同步", "刷新", "没同步", "拉取", "更新数据", "最新跑步", "sync"],
  },
  {
    id: "import-pb",
    title: "导入 / 编辑个人最好成绩 (PB)",
    breadcrumb: "跑者视角 ▸ 档案与隐私 ▸ 训练档案 ▸ 最佳成绩 PB",
    desc: "支持从 Garmin 一键抓取全马、半马、10K、5K 最快成绩或手动校准。",
    steps: [
      "点击卡片右上角「从 Garmin 导入」自动拉取历史 PB",
      "也可手动微调成绩并点击底部「保存档案」以校准 VDOT 跑力",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/profile?tab=training&scroll_to=pb",
    actionType: "navigate",
    keywords: ["pb", "最好成绩", "全马成绩", "半马成绩", "10公里", "5公里", "导入pb", "pr"],
  },
  {
    id: "org-required-fields",
    title: "补齐大群 14 天实名准入必填资料",
    breadcrumb: "跑者视角 ▸ 档案与隐私 ▸ 大群准入必填资料",
    desc: "填写大群要求的真实姓名、班级届别、身份证与紧急联系人，避免满 14 天访问受限。",
    steps: [
      "页面已自动滚动至黄色高亮的「大群必填资料」表单区",
      "补齐标有「必填」的字段后点击「保存档案」，即可自动解除或延续正式权限",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/profile?tab=profile&scroll_to_required=1",
    actionType: "navigate",
    keywords: ["实名", "补齐", "14天", "复旦戈", "身份证", "紧急联系人", "班级", "届别", "服装尺码", "转正", "解冻"],
  },
  {
    id: "privacy-settings",
    title: "配置 4 级隐私保护与隐藏轨迹开关",
    breadcrumb: "跑者视角 ▸ 档案与隐私 ▸ 隐私保护控制",
    desc: "独立设置姓名脱敏、GPS 路线隐藏、心率生理保密及同城寻搭子可见范围。",
    steps: [
      "根据需要开启「隐藏 GPS 轨迹」或「隐藏生理指标」开关",
      "可同步配置「Canova 教练精评」对哪几个跑团展示，设置即时生效",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/profile?tab=profile&scroll_to=privacy",
    actionType: "navigate",
    keywords: ["隐私", "隐藏", "轨迹", "脱敏", "gps", "生理指标", "保密", "可见范围", "不让看"],
  },
  {
    id: "physio-profile",
    title: "设置最大心率 / 静息心率与身体档案",
    breadcrumb: "跑者视角 ▸ 档案与隐私 ▸ 训练档案 ▸ 体能生理指标",
    desc: "维护最大心率、静息心率、身高体重与出生日期，提升 Karvonen 区间准确度。",
    steps: [
      "核对或修改最大心率、静息心率与出生日期",
      "点击下方「保存档案」即可自动重新划分 Z1–Z5 训练心率区间",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/profile?tab=training&scroll_to=physio",
    actionType: "navigate",
    keywords: ["最大心率", "静息心率", "心率", "身高", "体重", "出生日期", "年龄", "vo2max", "生理档案"],
  },
  {
    id: "mileage-goals",
    title: "设置周跑量与年度月度跑量目标",
    breadcrumb: "跑者视角 ▸ 档案与隐私 ▸ 训练档案 ▸ 跑量目标",
    desc: "设定常规周跑量目标及全年 12 个月统一或独立月跑量预算。",
    steps: [
      "在「周跑量」区域点击快捷里程或拖动滑块后点「保存周量」",
      "可在月跑量区域切换「统一设定」或「12 个月独立设定」",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/profile?tab=training&scroll_to=goals",
    actionType: "navigate",
    keywords: ["跑量目标", "周跑量", "月跑量", "年度跑量", "设定目标", "目标公里"],
  },
  {
    id: "race-plans",
    title: "添加备赛比赛计划、AI 赛事情报与完赛照片",
    breadcrumb: "跑者视角 ▸ 档案与隐私 ▸ 训练档案 ▸ 比赛计划",
    desc: "登记 A/B/C 优先级目标赛事、一键联网检索赛事情报，或补录完赛成绩与照片。",
    steps: [
      "点击「添加比赛」填写赛事名称、日期与目标完赛时间",
      "可点击「AI 联网查赛事情报」自动获取赛道爬升与气候参考",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/profile?tab=training&scroll_to=races",
    actionType: "navigate",
    keywords: ["比赛计划", "备赛", "报名比赛", "赛事", "赛事情报", "完赛成绩", "完赛照片", "a类赛事"],
  },
  {
    id: "data-purge",
    title: "清除个人隐私数据与账号数据重置",
    breadcrumb: "跑者视角 ▸ 档案与隐私 ▸ 数据生命周期与清除",
    desc: "支持一键清空实名身份证、手机号、紧急联系人等敏感加密底账。",
    steps: [
      "仔细核对需清除的个人隐私字段范围",
      "点击清除按钮并在二次确认弹窗中完成授权",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/profile?tab=profile&scroll_to=data-lifecycle",
    actionType: "navigate",
    keywords: ["清除数据", "删除资料", "注销", "清空记录", "清除隐私"],
  },

  // ── Runner: Training & Science ──
  {
    id: "generate-plan",
    title: "AI 生成或重新定制 Canova 周期训练课表",
    breadcrumb: "跑者视角 ▸ Canova 训练 ▸ 定制训练计划",
    desc: "根据目标赛事（或无赛维持期）、目标时间与每周训练天数生成 4–12 周科学课表。",
    steps: [
      "选择「赛事备赛」或「保持体能」，填入目标赛事与每周可训练天数",
      "点击「生成训练计划」，先预览对比后再决定是否正式替换激活",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/coach?tab=plan&open=plan-config",
    actionType: "navigate",
    keywords: ["生成课表", "制定课表", "训练计划", "定制计划", "排课", "canova", "周期课表", "重新制定"],
  },
  {
    id: "view-plan",
    title: "查看本周训练课表、打卡与填写 RPE 体感",
    breadcrumb: "跑者视角 ▸ Canova 训练 ▸ 本周课表矩阵",
    desc: "浏览本周每日训练类型、目标配速与心率区间，支持打卡、调换训练日和传图。",
    steps: [
      "点击任意一天的训练卡片可打开详情、标记完成或填写 RPE 体感",
      "需要动态调整今日或明日课表时，可直接在右侧向 Canova AI 教练提问",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/coach?tab=plan",
    actionType: "navigate",
    keywords: ["本周课表", "今日课表", "看课表", "打卡", "rpe", "体感", "训练内容"],
  },
  {
    id: "plan-versions",
    title: "查看课表历史版本与一键回滚",
    breadcrumb: "跑者视角 ▸ Canova 训练 ▸ 版本切换与回滚",
    desc: "查看系统自动备份的历次训练课表快照，支持随时对比并回滚恢复。",
    steps: [
      "在展开的「历史版本与快照」面板中选择需要恢复的课表版本",
      "点击「恢复此版本」即可安全切回原有周期安排",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/coach?tab=plan&open=plan-versions",
    actionType: "navigate",
    keywords: ["版本", "回滚", "撤销", "历史课表", "恢复课表", "以前版本"],
  },
  {
    id: "ai-coach-chat",
    title: "呼出 Canova AI 教练实时对话与身体反应调课",
    breadcrumb: "全局右上角 / 浮标 ▸ Canova AI 教练对话舱",
    desc: "结合您近 7 天实际跑量、本周课表与身体反应标签给出专业调课反馈。",
    steps: [
      "直接点选底部身体反应标签（如「肌肉酸痛」「心率偏高」）可秒发诊断",
      "也可输入具体伤痛或疲惫情况，勾选「同步至课表」自动写入今日体感",
    ],
    category: "runner",
    roleRequired: "runner",
    actionType: "open-coach-chat",
    keywords: ["ai教练", "问教练", "调课", "身体反应", "疼", "累", "疲惫", "受伤", "酸痛", "睡眠不好", "对话"],
  },
  {
    id: "coach-report",
    title: "Canova 多赛事战略诊断报告与冲突排查",
    breadcrumb: "跑者视角 ▸ Canova 训练 ▸ 战略诊断报告",
    desc: "诊断多场赛事的 A/B/C 优先级冲突、周期过渡建议与 6 级专项配速处方。",
    steps: [
      "若有多场备赛，可在多赛事卡片中调整 A/B/C 优先级重新评估冲突",
      "点击「生成深度训练诊断」即可刷新最新体能状态与专项处方",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/coach?tab=report",
    actionType: "navigate",
    keywords: ["诊断报告", "战略诊断", "多赛事", "冲突", "宏观周期", "a/b/c", "优先级"],
  },
  {
    id: "vdot-analysis",
    title: "查看 VDOT 跑力、体能负荷与生理曲线",
    breadcrumb: "跑者视角 ▸ 生理与轨迹 ▸ VDOT 与负荷总览",
    desc: "查看有效 VDOT 跑力、耐力保持系数、全半马预测与 30 天 HRV/睡眠恢复趋势。",
    steps: [
      "顶部 4 张 KPI 卡直接展示最新 VDOT、耐力系数与全半马完赛预测",
      "向下滚动可查看 30 天静息心率、HRV、睡眠及身体电量变化曲线",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/analysis",
    actionType: "navigate",
    keywords: ["vdot", "跑力", "ctl", "atl", "tsb", "生理", "hrv", "耐力系数", "完赛预测", "睡眠"],
  },
  {
    id: "taper-simulation",
    title: "赛前 7 天减量 (Taper) 状态推演模拟器",
    breadcrumb: "跑者视角 ▸ 生理与轨迹 ▸ Taper 减量推演",
    desc: "基于当前 CTL/ATL/TSB 对比三套赛前 7 天减量方案，找到最佳比赛日状态窗口。",
    steps: [
      "点击对比三套不同降量比例的推演卡片（含系统推荐方案）",
      "结合推演出的比赛日 TSB 数值决定赛前最后一周跑量安排",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/analysis?scroll_to=taper",
    actionType: "navigate",
    keywords: ["减量", "taper", "赛前", "推演", "状态模拟", "赛前一周", "降量"],
  },
  {
    id: "pacer-eval",
    title: "马拉松官方兔子（官兔）六维胜任度评估",
    breadcrumb: "跑者视角 ▸ 生理与轨迹 ▸ 官兔潜能评估卡",
    desc: "量化评估配速稳健度、有氧冗余度与官兔档位匹配度，支持生成官兔电子履历。",
    steps: [
      "查看您在各目标完赛档位下的 6 维配速稳健度评分",
      "可点击卡片内的「生成官兔履历」用于赛事官方配速员报名",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/analysis?scroll_to=pacer",
    actionType: "navigate",
    keywords: ["官兔", "兔子", "配速员", "pacer", "稳健度", "履历", "评估"],
  },
  {
    id: "pace-zones",
    title: "查看 Renato Canova 6 级专项配速区间",
    breadcrumb: "跑者视角 ▸ 生理与轨迹 ▸ Canova 配速矩阵",
    desc: "展示再生跑、基础耐力、有氧耐力、专项耐力等 6 档科学配速区间。",
    steps: [
      "已为您自动展开 Canova 专项配速表，对照日常训练课表卡控配速",
      "配速区间会根据您更新的 PB 或近期手表跑步效率自动校准",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/analysis?open=pace-zones",
    actionType: "navigate",
    keywords: ["配速表", "配速区间", "pace zone", "轻松跑配速", "节奏跑配速", "马拉松配速"],
  },
  {
    id: "share-card",
    title: "生成 4K 炫跑战报分享海报",
    breadcrumb: "跑者视角 ▸ 首页 / 生理分析 ▸ 4K 战报海报工坊",
    desc: "一键生成包含路线轨迹、心率配速与 Canova 数据的高清战报海报。",
    steps: [
      "在海报工坊中选择心仪的视觉模版与背景样式",
      "点击下载高清 PNG 长图，即可直接分享至微信朋友圈或跑团群",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard?open=share-card",
    actionType: "navigate",
    keywords: ["战报", "海报", "分享图", "4k", "炫跑", "发朋友圈", "战绩图"],
  },
  {
    id: "personal-report",
    title: "生成个人周报 / 月报数据总结",
    breadcrumb: "跑者视角 ▸ 首页工作台 ▸ 个人周报/月报",
    desc: "自动汇总本周或本月的跑量完成率、训练分布与负荷总结。",
    steps: [
      "在弹窗顶部切换「周报」或「月报」周期与越野跑统计口径",
      "支持一键复制总结文本或导出战报分享图片",
    ],
    category: "runner",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard?open=personal-report",
    actionType: "navigate",
    keywords: ["个人周报", "个人月报", "周总结", "月总结", "本周跑了多少"],
  },

  // ── Club & Community ──
  {
    id: "join-club-code",
    title: "输入 6 位邀请码加入跑团",
    breadcrumb: "跑者视角 ▸ 跑团与大群 ▸ 输入邀请码入团",
    desc: "输入团长分享的 6 位专属字母数字邀请码，秒速加入指定跑团。",
    steps: [
      "在弹出的输入框中填入 6 位跑团邀请码（不区分大小写）",
      "点击「立即加入」即可同步进入跑团排行榜与课表体系",
    ],
    category: "club",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/team?open=join-club",
    actionType: "navigate",
    keywords: ["邀请码", "加团", "入团", "进团", "6位码", "加入跑团"],
  },
  {
    id: "browse-clubs",
    title: "浏览平台全部公开跑团并选择加入",
    breadcrumb: "跑者视角 ▸ 跑团与大群 ▸ 浏览全部跑团",
    desc: "查看平台已创建的所有跑团及所在城市，直接申请加入心仪跑团。",
    steps: [
      "浏览跑团卡片中的城市、人数与合练介绍",
      "点击「申请加入」即可入团（若设邀请码则需填入对应口令）",
    ],
    category: "club",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/team?open=browse-clubs",
    actionType: "navigate",
    keywords: ["找跑团", "有哪些跑团", "所有跑团", "跑团列表", "选跑团"],
  },
  {
    id: "create-club",
    title: "自建专属跑团并成为团长",
    breadcrumb: "跑者视角 ▸ 跑团与大群 ▸ 自建跑团",
    desc: "输入跑团名称、城市与入团方式即可创立自己的跑团，自动解锁团长与教练工作台。",
    steps: [
      "填写跑团名称、常驻城市并选择「公开自由入团」或「邀请码入团」",
      "创建完成后可在团长驾驶舱生成 6 位邀请码海报邀请队友",
    ],
    category: "club",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/team?open=create-club",
    actionType: "navigate",
    keywords: ["自建跑团", "创建跑团", "建团", "当团长", "新建跑团"],
  },
  {
    id: "join-org",
    title: "加入大群体与戈友实名认证",
    breadcrumb: "跑者视角 ▸ 跑团与大群 ▸ 加入大群体 / 戈友认证",
    desc: "加入复旦戈等高校或大型跑步组织，支持大群邀请码与实名认证绑定。",
    steps: [
      "输入大群邀请码（如公开免码大群可直接选择）并核对个人实名字段",
      "提交后即可享有 14 天正式准入缓冲期并归属对应大群排行榜",
    ],
    category: "club",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/team?open=join-org",
    actionType: "navigate",
    keywords: ["大群", "大群体", "复旦戈", "校友", "戈友", "戈壁", "加入大群", "emba"],
  },
  {
    id: "weekend-events",
    title: "周末约跑配速列车报名上车",
    breadcrumb: "跑者视角 ▸ 跑团与大群 ▸ 约跑活动与配速列车",
    desc: "查看跑团线下约跑门岗锚点、各档位配速列车及兔子名单，一键报名上车。",
    steps: [
      "选择即将开始的约跑或月度挑战活动卡片",
      "挑选适合自己目标配速的列车（如 430 / 500 / 530）点击上车即可",
    ],
    category: "club",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/team?tab=events",
    actionType: "navigate",
    keywords: ["约跑", "合练", "周末", "活动", "配速列车", "上车", "报名", "门岗"],
  },
  {
    id: "mentorship-bind",
    title: "跑团师徒结对绑定",
    breadcrumb: "跑者视角 ▸ 跑团与大群 ▸ 排行榜 ▸ 师徒结对",
    desc: "在跑团内选择师傅或徒弟建立结对关系，互相查看周月训练激励与批注。",
    steps: [
      "在师徒结对弹窗中选择您想拜师的资深跑友或可带教的徒弟",
      "绑定后即可在跑团看板中追踪师徒合练完成率",
    ],
    category: "club",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/team?tab=leaderboard&open=mentorship",
    actionType: "navigate",
    keywords: ["师徒", "拜师", "收徒", "导师", "徒弟", "师傅", "结对"],
  },
  {
    id: "discover-buddies",
    title: "六维同频寻搭子（同城约跑友）",
    breadcrumb: "跑者视角 ▸ 同频寻搭子",
    desc: "按年龄组别、VDOT 同频配速、30 日跑量、常跑公园地标匹配合拍跑友并支持互关周 PK。",
    steps: [
      "在顶部筛选栏设置城市、常跑公园地标或检索范围",
      "点击跑友卡片即可发起关注或查看周跑量同频 PK 对比",
    ],
    category: "club",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/discover",
    actionType: "navigate",
    keywords: ["搭子", "跑友", "找人跑", "同频", "公园", "地标", "周pk", "附近跑者", "约搭子"],
  },
  {
    id: "showcase-plaza",
    title: "选团与名帅风采展厅",
    breadcrumb: "跑者视角 ▸ 选团与名帅",
    desc: "浏览各地跑团宣传主页、手表防伪核验战绩及认证教练带教履历与合练相册。",
    steps: [
      "顶部可切换「跑团展厅」或「名帅教练」两个浏览视图",
      "点击任意跑团或教练卡片可展开完整战绩认证与申请直达按钮",
    ],
    category: "club",
    roleRequired: "public",
    perspective: "runner",
    href: "/dashboard/plaza",
    actionType: "navigate",
    keywords: ["展厅", "名帅", "名团", "宣传页", "教练履历", "合练照片", "选团", "风采"],
  },
  {
    id: "leave-club",
    title: "退出当前跑团",
    breadcrumb: "跑者视角 ▸ 跑团与大群 ▸ 退出跑团",
    desc: "安全退出当前所在的跑团（含倒计时防误触确认，个人历史运动记录完全保留）。",
    steps: [
      "阅读退出说明并勾选确认框",
      "等待防误触倒计时结束后点击「确认退出跑团」即可",
    ],
    category: "club",
    roleRequired: "runner",
    perspective: "runner",
    href: "/dashboard/team?open=leave-club",
    actionType: "navigate",
    keywords: ["退团", "退出跑团", "离开跑团"],
  },

  // ── Leader (Captain & Coach) ──
  {
    id: "captain-cockpit",
    title: "团长运营驾驶舱与成员花名册",
    breadcrumb: "团/教视角 ▸ 团长驾驶舱",
    desc: "查看全团月度跑量达成环、未绑表激活漏斗、成员角色权限管理与常用工具入口。",
    steps: [
      "顶部驾驶舱直观展示全团达标率、激活人数与快捷操作按钮",
      "下方成员花名册可调整教练/分组权限或导出管理数据",
    ],
    category: "leader",
    roleRequired: "leader",
    perspective: "leader",
    href: "/dashboard/team?tab=president",
    actionType: "navigate",
    keywords: ["团长", "驾驶舱", "花名册", "激活率", "达标率", "成员管理", "未绑表"],
  },
  {
    id: "club-invite-poster",
    title: "生成跑团入团邀请码与分享海报",
    breadcrumb: "团/教视角 ▸ 团长驾驶舱 ▸ 邀请码与拉新海报",
    desc: "一键复制 6 位邀请码、微信邀请链接或生成带小程序码的高清入团招募海报。",
    steps: [
      "可直接复制 6 位邀请码或专属入团邀请链接发至微信群",
      "点击「下载入团海报」可导出带跑团徽章与扫码直达卡片的图片",
    ],
    category: "leader",
    roleRequired: "leader",
    perspective: "leader",
    href: "/dashboard/team?tab=president&open=club-invite",
    actionType: "navigate",
    keywords: ["邀请海报", "二维码", "小程序码", "拉新", "邀人进团", "分享跑团", "团邀请码"],
  },
  {
    id: "club-report",
    title: "生成跑团周报 / 月报与微信接龙文案",
    breadcrumb: "团/教视角 ▸ 战报播报室 ▸ 跑团周报/月报",
    desc: "支持导出高清战报长图、全员达标 CSV 明细及一键复制微信群接龙汇总文本。",
    steps: [
      "选择「周报」或「月报」以及越野跑统计口径",
      "可在三个视图间切换：一键下载长图海报、导出 CSV 或复制微信接龙文案",
    ],
    category: "leader",
    roleRequired: "leader",
    perspective: "leader",
    href: "/dashboard/team?tab=president&open=club-report",
    actionType: "navigate",
    keywords: ["跑团周报", "跑团月报", "接龙", "播报", "战报长图", "csv", "团队报表"],
  },
  {
    id: "targeted-recruit",
    title: "团长 / 教练多维靶向纳新",
    breadcrumb: "团/教视角 ▸ 团长驾驶舱 ▸ 靶向纳新漏斗",
    desc: "精准筛选周边活跃且允许招募检索的未入团跑友，一键发送带邀请码的入团邀约。",
    steps: [
      "在下方「多维靶向纳新」面板按城市、配速区间或跑量筛选潜在跑友",
      "点击跑友右侧「发送入团邀约」并跟踪邀约转化漏斗",
    ],
    category: "leader",
    roleRequired: "leader",
    perspective: "leader",
    href: "/dashboard/team?tab=president&open=targeted-recruit",
    actionType: "navigate",
    keywords: ["靶向纳新", "纳新", "招人", "招募", "邀请未入团", "未入团跑友"],
  },
  {
    id: "create-club-event",
    title: "发起跑团周末约跑或月度挑战活动",
    breadcrumb: "团/教视角 ▸ 选兔与约跑 ▸ 发起跑团活动",
    desc: "发布线下约跑配速列车（设门岗地标与各档位兔子）或团内月度里程挑战赛。",
    steps: [
      "选择活动类型（线下约跑或跑量挑战），填写集合时间、地点与目标要求",
      "提交后全团成员将收到活动通知并可直接在客户端报名上车",
    ],
    category: "leader",
    roleRequired: "leader",
    perspective: "leader",
    href: "/dashboard/team?tab=events&open=create-event",
    actionType: "navigate",
    keywords: ["发起活动", "发布约跑", "组织合练", "创建活动", "新建挑战赛", "编组列车"],
  },
  {
    id: "club-broadcast",
    title: "发送全团通知公告与站内广播",
    breadcrumb: "团/教视角 ▸ 团长驾驶舱 ▸ 全团消息广播",
    desc: "向跑团全体或特定组别成员推送重要训练提醒、合练变更或赛事动员通知。",
    steps: [
      "填写通知标题与正文内容（支持附带跳转页面链接）",
      "点击发送后，所有团员顶栏消息铃铛及小程序将同步收到提醒",
    ],
    category: "leader",
    roleRequired: "leader",
    perspective: "leader",
    href: "/dashboard/team?tab=president&open=broadcast",
    actionType: "navigate",
    keywords: ["广播", "群发", "全团通知", "发公告", "提醒全团"],
  },
  {
    id: "club-showcase-studio",
    title: "装修跑团对外宣传主页与合练照片墙",
    breadcrumb: "团/教视角 ▸ 团长驾驶舱 ▸ 宣传主页工坊",
    desc: "维护跑团在「选团展厅」的品牌故事、训练体系亮点与高清合练照片墙。",
    steps: [
      "编辑跑团对外展示标语、常驻训练场及亮点标签",
      "上传多张高质量合练照片并保存，即刻同步至公共选团展厅",
    ],
    category: "leader",
    roleRequired: "leader",
    perspective: "leader",
    href: "/dashboard/team?tab=president&open=club-showcase",
    actionType: "navigate",
    keywords: ["装修跑团", "跑团宣传页", "上传合练照片", "编辑品牌主页", "跑团相册"],
  },
  {
    id: "coach-showcase-studio",
    title: "装修教练认证履历与个人风采页",
    breadcrumb: "团/教视角 ▸ 教练工作台 ▸ 教练风采工坊",
    desc: "完善个人带教经历、认证资质证书与擅长训练体系，向全站跑者展示名帅风采。",
    steps: [
      "填写教练个人简介、带教理念与代表性学员成绩",
      "上传资质证明或赛场带队照片并开启对外展厅展示",
    ],
    category: "leader",
    roleRequired: "leader",
    perspective: "leader",
    href: "/dashboard/team?tab=coach&open=coach-showcase",
    actionType: "navigate",
    keywords: ["教练主页", "教练履历", "教练证书", "装修教练", "带教风采"],
  },
  {
    id: "coach-compass",
    title: "教练全队体能信号灯罗盘 & 选兔雷达",
    breadcrumb: "团/教视角 ▸ 教练信号灯罗盘",
    desc: "以红黄绿灰体能信号灯一览全队负荷风险，内置选兔稳健度雷达与队员跨视角调阅。",
    steps: [
      "顶部信号灯筛选栏可一键筛出过载预警（红/黄灯）队员",
      "点击任意队员的「审课/调阅」按钮可直接查看其完整曲线或调整课表",
    ],
    category: "leader",
    roleRequired: "leader",
    perspective: "leader",
    href: "/dashboard/team?tab=coach",
    actionType: "navigate",
    keywords: ["信号灯", "罗盘", "选兔雷达", "红黄绿", "队员风险", "过载", "教练工作台"],
  },
  {
    id: "import-schedule",
    title: "智能导入周训练课表 (Excel 文本 / 截图识别)",
    breadcrumb: "团/教视角 ▸ 教练工作台 ▸ 智能课表导入",
    desc: "粘贴微信群/Excel 周计划文本或上传课表截图，AI 自动拆解 A/B/C 分组与体能附注。",
    steps: [
      "在弹窗中直接粘贴周课表文字或上传表格截图（也可选内置模板体验）",
      "核对 AI 自动拆分好的每日距离、分组配速与体能提示后一键下发",
    ],
    category: "leader",
    roleRequired: "leader",
    perspective: "leader",
    href: "/dashboard/team?tab=coach&open=import-schedule",
    actionType: "navigate",
    keywords: ["导入课表", "excel", "表格", "截图识别", "ocr", "解析课表", "a/b/c组", "粘贴课表"],
  },
  {
    id: "assign-template",
    title: "使用课表模板批量派发给队员",
    breadcrumb: "团/教视角 ▸ 教练工作台 ▸ 批量派课",
    desc: "选择已有周课表模板，支持按组别或全员一键下发并按目标跑力动态缩放强度。",
    steps: [
      "选择需要下发的周期课表模板并勾选目标队员或配速分组",
      "预览各组强度与周跑量后点击「确认派发」完成批量排课",
    ],
    category: "leader",
    roleRequired: "leader",
    perspective: "leader",
    href: "/dashboard/team?tab=coach&open=assign-template",
    actionType: "navigate",
    keywords: ["批量派课", "派发课表", "下发计划", "课表模板", "给全队排课", "分配训练"],
  },
  {
    id: "batch-critique",
    title: "教练 5 秒连续批阅三栏舱",
    breadcrumb: "团/教视角 ▸ 5秒批阅排课",
    desc: "异常打卡置顶队列 + 心率配速生理对照 + 快捷词条连发，回车即自动切至下一位队员。",
    steps: [
      "左侧队列已按风险与未批阅状态排序，中间展示该队员本次心率/配速对照",
      "右侧点选常用点评词条或输入建议，按 Enter 发送并秒切下一位",
    ],
    category: "leader",
    roleRequired: "leader",
    perspective: "leader",
    href: "/dashboard/team?tab=coach&mode=batch-critique",
    actionType: "navigate",
    keywords: ["批阅", "点评", "5秒", "三栏", "批量点评", "审课"],
  },

  // ── Org Admin & Super Admin ──
  {
    id: "org-roster-audit",
    title: "大群 14 天实名花名册核验与转正",
    breadcrumb: "管理视角 ▸ 大群实名核验 ▸ 花名册审计",
    desc: "查看脱敏保护的实名成员花名册，支持核验转正、超期解冻及导出赛事保险名单。",
    steps: [
      "使用状态筛选器快速定位「待审核 / 临近 14 天到期」成员",
      "核验无误后点击「确认转正」，或点击右上角导出加密保险名册",
    ],
    category: "admin",
    roleRequired: "org_admin",
    perspective: "admin",
    href: "/dashboard/team?org_action=roster",
    actionType: "navigate",
    keywords: ["花名册", "实名核验", "审核转正", "超期解冻", "保险名单", "大群成员", "待审"],
  },
  {
    id: "org-pk-report",
    title: "大群全域报表与下属分跑团 PK 榜",
    breadcrumb: "管理视角 ▸ 大群工作台 ▸ 全域报表与分团 PK",
    desc: "横跨多个下属分跑团统计总跑量、人均里程与出勤率排行，支持未分团成员一键划转。",
    steps: [
      "在顶部切换「周报 / 月报」与指标排序维度查看分团 PK 榜",
      "可切换至「未分配分团成员」直接将散客划归指定分团",
    ],
    category: "admin",
    roleRequired: "org_admin",
    perspective: "admin",
    href: "/dashboard/team?org_action=report",
    actionType: "navigate",
    keywords: ["分团pk", "大群报表", "全域报表", "分跑团对比", "跨团统计"],
  },
  {
    id: "org-cross-events",
    title: "发起跨跑团联合大合练或分团对抗赛",
    breadcrumb: "管理视角 ▸ 大群工作台 ▸ 跨跑团联合活动",
    desc: "组织覆盖整个大群下辖分团的联合拉练或跑量团队对抗赛。",
    steps: [
      "选择「联合大合练」或「分跑团对抗赛」并指定参与分团范围",
      "发布后各分团成员均可在跑团首页直接报名并实时计分",
    ],
    category: "admin",
    roleRequired: "org_admin",
    perspective: "admin",
    href: "/dashboard/team?org_action=events",
    actionType: "navigate",
    keywords: ["跨团活动", "大合练", "分团对抗赛", "联合活动", "大群活动"],
  },
  {
    id: "org-field-rules",
    title: "配置大群入队必填字段规则",
    breadcrumb: "管理视角 ▸ 大群工作台 ▸ 入队必填规则",
    desc: "灵活设定大群成员在 14 天内必须填报的实名信息（如身份证、紧急联系人、届别）。",
    steps: [
      "逐项将字段切换为「必填」「选填」或「隐藏」",
      "保存规则后，所有未达标成员工作台将自动弹出补齐提醒",
    ],
    category: "admin",
    roleRequired: "org_admin",
    perspective: "admin",
    href: "/dashboard/team?org_action=fields",
    actionType: "navigate",
    keywords: ["必填字段", "入队字段", "字段规则", "设置必填", "表单规则"],
  },
  {
    id: "org-settings",
    title: "大群基础设置与免码/邀请码模式",
    breadcrumb: "管理视角 ▸ 大群工作台 ▸ 大群设置",
    desc: "更新大群名称、所在城市、公告简介以及自由免码入会或邀请码准入模式。",
    steps: [
      "在设置面板选择「自由免码入会」或「仅凭邀请码入会」",
      "调整并保存大群基础资料与专属邀请码",
    ],
    category: "admin",
    roleRequired: "org_admin",
    perspective: "admin",
    href: "/dashboard/team?org_action=settings",
    actionType: "navigate",
    keywords: ["大群设置", "免码入会", "大群邀请码", "修改大群信息"],
  },
  {
    id: "admin-orgs",
    title: "平台超管：大群与分团治理拓扑树",
    breadcrumb: "管理视角 ▸ 超管控制台 ▸ 大群与分团树",
    desc: "管理全站大群体与分跑团树状挂载关系、指派主理人或创建新大群。",
    steps: [
      "可查看并管理各城市大群与其下辖分团的拓扑挂载关系",
      "点击「新建大群」或编辑按钮可指派团长并管理生命周期",
    ],
    category: "admin",
    roleRequired: "super_admin",
    perspective: "admin",
    href: "/dashboard/admin?tab=orgs",
    actionType: "navigate",
    keywords: ["超管", "拓扑树", "新建大群", "指派团长", "挂载分团", "超级管理员"],
  },
  {
    id: "admin-unaffiliated",
    title: "平台超管：自由跑者待引导池",
    breadcrumb: "管理视角 ▸ 超管控制台 ▸ 自由跑者池",
    desc: "识别已绑定手表但尚未加入跑团的活跃自由跑友并一键推送入团引导。",
    steps: [
      "按状态筛选已绑表但未入团的活跃跑者",
      "点击行末推送按钮向其发送周边优质跑团邀请通知",
    ],
    category: "admin",
    roleRequired: "super_admin",
    perspective: "admin",
    href: "/dashboard/admin?tab=unaffiliated",
    actionType: "navigate",
    keywords: ["自由跑者", "未入团池", "散客", "待引导跑者"],
  },
  {
    id: "admin-analytics",
    title: "平台超管：全站增长漏斗与遥测大盘",
    breadcrumb: "管理视角 ▸ 超管控制台 ▸ 全站增长遥测",
    desc: "监测小程序与 Web 双端 DAU、核心功能漏斗转化及单跑者全生命周期轨迹钻取。",
    steps: [
      "调整统计天数与平台筛选（小程序 / Web / 全平台）",
      "点击任意会话或用户行可下钻查看完整页面访问与 API 耗时轨迹",
    ],
    category: "admin",
    roleRequired: "super_admin",
    perspective: "admin",
    href: "/dashboard/admin?tab=analytics",
    actionType: "navigate",
    keywords: ["遥测", "dau", "增长漏斗", "留存", "行为分析", "埋点", "转化率"],
  },
  {
    id: "admin-support",
    title: "平台超管：设备同步与 AI 运维排障工单",
    breadcrumb: "管理视角 ▸ 超管控制台 ▸ 设备与AI运维",
    desc: "统一监控 Garmin/COROS 同步队列状态、AI 服务健康度并回复用户反馈工单。",
    steps: [
      "查看最新用户反馈工单详情与关联账号设备状态",
      "输入官方处理答复后点击「发送回复」同步回传至用户端",
    ],
    category: "admin",
    roleRequired: "super_admin",
    perspective: "admin",
    href: "/dashboard/admin?tab=support",
    actionType: "navigate",
    keywords: ["工单", "反馈", "运维", "排障", "客服"],
  },
];

export const WORKFLOW_BY_ID: Record<string, WorkflowEntry> = Object.fromEntries(
  WORKFLOW_CATALOG.map((item) => [item.id, item])
);

export interface QuickIntentGroup {
  groupLabel: string;
  items: { label: string; query: string }[];
}

export const QUICK_INTENT_CHIPS: QuickIntentGroup[] = [
  {
    groupLabel: "🏃 新手与日常跑者",
    items: [
      { label: "⌚ 绑定佳明手表", query: "我想绑定佳明运动手表" },
      { label: "📅 AI 生成训练课表", query: "帮我制定一套马拉松训练课表" },
      { label: "🪪 补齐复旦戈实名资料", query: "我要补齐大群14天实名资料" },
      { label: "🤝 找同城跑友搭子", query: "想找附近配速差不多的跑步搭子" },
      { label: "🩺 腿酸问 AI 教练调课", query: "最近跑完腿有点酸，问AI教练怎么调课" },
      { label: "🖼️ 生成 4K 战报海报", query: "我要做一张4K跑步战报海报发朋友圈" },
    ],
  },
  {
    groupLabel: "👑 团长与教练",
    items: [
      { label: "📥 导入 Excel 周课表", query: "我是教练，想导入Excel周训练课表分AB组" },
      { label: "⚡ 5 秒连续批阅打卡", query: "打开教练5秒批阅连续点评队员" },
      { label: "📊 跑团周报与接龙", query: "导出本周跑团周报和微信群接龙" },
      { label: "📣 生成入团邀请海报", query: "生成跑团6位邀请码和拉新海报" },
    ],
  },
  {
    groupLabel: "🏛️ 大群管理与超管",
    items: [
      { label: "🛡️ 审核大群 14 天实名", query: "管理员审核大群实名花名册和导出保险名单" },
      { label: "🏆 查看分跑团 PK 榜", query: "查看大群下面各个分跑团的PK报表" },
      { label: "🚩 发起跨团大合练", query: "发起大群跨跑团联合大合练活动" },
    ],
  },
];

export function hasWorkflowPermission(
  entry: WorkflowEntry,
  roles?: UserRoleFlags
): boolean {
  if (entry.roleRequired === "public" || entry.roleRequired === "runner") {
    return true;
  }
  const isSuper = Boolean(roles?.isSuperAdmin);
  if (entry.roleRequired === "super_admin") return isSuper;
  if (entry.roleRequired === "org_admin") {
    return Boolean(roles?.hasManagedOrg) || isSuper;
  }
  if (entry.roleRequired === "leader") {
    return Boolean(roles?.isCoachOrOwner) || isSuper;
  }
  return true;
}

function getBigrams(text: string): Set<string> {
  const cleaned = text
    .toLowerCase()
    .replace(/[\s，。！？、,.!?/\\\-_:：()（）【】]+/g, "");
  if (!cleaned) return new Set();
  if (cleaned.length < 2) return new Set([cleaned]);
  const set = new Set<string>();
  for (let i = 0; i < cleaned.length - 1; i++) {
    set.add(cleaned.slice(i, i + 2));
  }
  return set;
}

export function matchWorkflowsLocally(
  query: string,
  roles?: UserRoleFlags,
  limit = 4
): WorkflowEntry[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const qBigrams = getBigrams(q);

  const scored = WORKFLOW_CATALOG.map((wf) => {
    let score = 0;
    const titleLow = wf.title.toLowerCase();
    if (titleLow.includes(q)) score += 6;
    for (const kw of wf.keywords) {
      const kLow = kw.toLowerCase();
      if (q.includes(kLow)) {
        score += 4.2 + Math.min(2, kLow.length * 0.35);
      } else if (kLow.includes(q) && q.length >= 2) {
        score += 2.5;
      }
    }
    const targetBigrams = getBigrams(`${wf.title} ${wf.keywords.join(" ")}`);
    let overlap = 0;
    qBigrams.forEach((bg) => {
      if (targetBigrams.has(bg)) overlap += 1;
    });
    score += overlap * 0.85;
    if (hasWorkflowPermission(wf, roles)) score += 0.25;
    return { wf, score };
  })
    .filter((item) => item.score > 0.6)
    .sort((a, b) => b.score - a.score);

  return scored.slice(0, limit).map((s) => s.wf);
}
