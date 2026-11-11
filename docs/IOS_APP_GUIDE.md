# RGM iOS 原生 App (SwiftUI) 构建与三端数据一致性指南

本项目已在 `ios/` 目录下建立**纯原生 Xcode iOS 工程 (`RGM.xcodeproj`)**，采用 **SwiftUI + Swift Concurrency (`async/await`) + Sign in with Apple** 构建，无需任何第三方工具（如 HBuilderX），直接在 Mac 的 Xcode 中即可编译、真机调试与打包。

---

## 🏗️ 1. 三端一致性核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                    统一后端服务 (FastAPI)                      │
│                  https://rgm.vanpower.net                   │
│                                                             │
│  - /api/auth/*     (统一认证: 微信UnionID / 苹果ID / 佳明高驰)      │
│  - /api/sync/*     (Garmin / COROS 官方数据拉取与解析)         │
│  - /api/coach/*    (Canova AI 智能教练与周计划引擎)          │
│  - /api/profile/*  (跑者生理指标、跑量目标与大团准入状态)       │
│  - /api/team/*     (跑团、排行榜、成员战报与打卡动态)           │
└──────────────────────────────┬──────────────────────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
    ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
    │  微信小程序端   │  │ iOS 原生App端 │  │   Web 网站端   │
    │  (mp-weixin)  │  │(RGM.xcodeproj)│  │ (Next.js 15)  │
    └───────────────┘  └───────────────┘  └───────────────┘
```

### 数据一致性保障机制：
1. **统一数据中心**：三端共享阿里云 PostgreSQL (Supabase) 数据库。跑量目标、跑步数据、跑团排行榜实时同步。
2. **账号跨端打通 (微信 UnionID 体系 & 苹果登录)**：
   - 微信授权共享 `unionid`，老用户在 iOS 端一键识别并恢复档案。
   - 原生支持 **Sign in with Apple (通过 Apple 登录)**，完全符合 App Store 审核准则 4.8。
3. **运动手表跨端直连 (Garmin / COROS)**：
   - 内置官方账号验证 Sheet，手表数据拉取后自动与小程序和网站同步。

---

## 🚀 2. 如何在 Xcode 中打开与运行

### 第一步：在 Xcode 中打开工程
直接在终端运行：
```bash
open ios/RGM.xcodeproj
```
或者在 Xcode 菜单点击 `File` -> `Open...`，选择项目目录下的 **`ios/RGM.xcodeproj`**。

### 第二步：选择目标机型并运行
1. 观察 Xcode 顶部工具栏，左侧会看到一个标准的 **【▶️ Run 播放键】**。
2. 在目标设备列表中选择您的 **iPhone 真机**（数据线连接后会显示在列表）或任意 **iOS Simulator（如 iPhone 16 Pro）**。
3. 按下快捷键 `Cmd + R`（或点击 ▶️ 按钮），Xcode 会自动完成编译并把 App 安装启动到您的手机上！

---

## 📁 3. iOS 原生工程目录结构 (`ios/`)

```text
ios/
├── RGM.xcodeproj/                # Xcode 原生工程文件 (直接双击即可打开)
├── RGM/
│   ├── App/
│   │   ├── RGMApp.swift          # App 主入口与生命周期
│   │   └── AppState.swift        # 全局响应式状态管理 (自动拉取数据、手表同步)
│   ├── Models/
│   │   └── Models.swift          # 数据模型 (UserProfile / Activity / Leaderboard)
│   ├── Services/
│   │   ├── APIService.swift      # RESTful API 客户端 (连接 https://rgm.vanpower.net)
│   │   └── StorageManager.swift  # 本地安全存储与 Token 会话管理
│   ├── Theme/
│   │   └── Theme.swift           # 暗黑科技风主题 (Strava橙 #FC4C02 / 纯黑底色)
│   ├── Views/
│   │   ├── MainTabView.swift     # 5大原生底部导航栏
│   │   ├── Dashboard/            # 1. 看板：月度跑量环形仪表盘、最近运动卡片、一键同步
│   │   ├── Coach/                # 2. Canova教练：AI 耐力训练智能对话、专项计划
│   │   ├── Analysis/             # 3. 深度分析：CTL/ATL/TSB 负荷与 VDOT 配速区间
│   │   ├── Team/                 # 4. 跑团：跑团大本营与月度英雄榜
│   │   └── Profile/              # 5. 个人中心：Sign in with Apple、佳明/高驰直连绑定
│   ├── Assets.xcassets/          # App 图标与主题颜色资源
│   ├── Info.plist                # 权限声明 (定位、相册、相机等)
│   └── RGM.entitlements          # 原生能力配置 (Sign in with Apple)
└── project.yml                   # XcodeGen 规范化工程配置文件
```

---

## 🛠️ 4. 重新生成工程（如果添加了新文件）
如果您后续在 `ios/RGM/` 目录下添加或删除了 Swift 文件，只需在 `ios/` 目录下执行一次：
```bash
cd ios
xcodegen generate
```
即可自动将所有新文件归入 `RGM.xcodeproj`，无需手动在 Xcode 里拖拽配置文件。
