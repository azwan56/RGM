# RGM 国内版 (Running Community Manager - China Edition)

专为国内跑者打造的跑团管理与 AI 智能训练平台。
全面基于 **阿里云 (Alibaba Cloud) + Supabase (PostgreSQL) + Garmin (佳明双区直连) + 微信小程序 + 通义千问/DeepSeek AI** 构建。

---

## 🌟 核心特性

- **纯净 Garmin 直连**：无缝对接佳明中国区 (`garmin.cn`) 与国际区 (`garmin.com`)，自动同步跑步数据与日常健康指标（静息心率、VO2 Max、睡眠、身体电量、HRV）。
- **国内极速架构**：全栈部署于阿里云，无任何海外网络依赖与延迟。
- **Supabase BaaS 驱动**：使用 PostgreSQL 15+ 关系型数据库代替 Firebase，支持行级安全策略 (RLS)、强事务与复杂数据统计。
- **微信小程序互联**：微信一键登录、手机号快捷绑定，随时随地滑块调节跑量目标、一键触发佳明同步、查看每日进度与团队排行榜。
- **Renato Canova AI 跑步教练**：接入阿里云百炼（通义千问 Qwen-Max / DeepSeek-V3），结合 CTL/ATL/TSB、VDOT 跑力模型提供世界级马拉松专项化训练指导与单次跑步点评。
- **跑团社交竞跑**：6位专属邀请码快速建团/入团，支持按“目标完成率”或“绝对跑量”实时排名，一键生成朋友圈分享战报。

---

## 📁 目录结构

```text
rgm-cn/
├── backend/          # FastAPI 核心服务 (Garmin 适配器 / AI 教练引擎 / 微信认证)
├── frontend/         # Next.js 15 Web 前端 (暗黑科技风格 UI / 数据看板)
├── miniapp/          # 微信小程序端 (Uni-app + Vue 3 + TypeScript)
├── supabase/         # 数据库脚本 (PostgreSQL DDL / RLS 权限 / 本地 Docker)
└── deploy/           # 阿里云线上部署配置 (Docker Compose / Nginx / 环境变量模板)
```

---

## 🚀 快速开始

### 1. 数据库准备 (Supabase)
在阿里云自建 Supabase 或连接已有 PostgreSQL 实例，导入建表脚本：
```bash
psql -h <DB_HOST> -U <DB_USER> -d <DB_NAME> -f supabase/migrations/20260816000000_init_schema.sql
```

### 2. 后端服务 (Backend)
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env # 填写 Supabase、DashScope Key 与微信小程序 AppID
uvicorn main:app --reload --port 8000
```

### 3. Web 前端 (Frontend)
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev # 访问 http://localhost:3000
```

### 4. 微信小程序 (MiniApp)
```bash
cd miniapp
npm install
npm run dev:mp-weixin # 使用微信开发者工具导入 dist/dev/mp-weixin 目录
```

---

## 📄 授权协议
MIT License
