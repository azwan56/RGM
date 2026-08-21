-- ==============================================================================
-- RGM (Running Community Manager) - China Edition Database Schema for Supabase
-- Target: PostgreSQL 15+ with pg_crypto & uuid-ossp
-- ==============================================================================

-- 0. 启用必要扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==============================================================================
-- 1. 用户档案表 (public.profiles)
-- 关联 Supabase auth.users 表
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE,
    phone TEXT UNIQUE,
    wechat_openid TEXT UNIQUE,
    wechat_unionid TEXT,
    display_name TEXT NOT NULL DEFAULT '跑者',
    avatar_url TEXT,
    gender VARCHAR(10) CHECK (gender IN ('male', 'female', 'other')),
    date_of_birth DATE,
    height_cm NUMERIC(5, 1),
    weight_kg NUMERIC(5, 1),
    years_running INT DEFAULT 0,
    bio TEXT,
    
    -- 生理核心指标
    max_heart_rate INT DEFAULT 190,
    resting_heart_rate INT DEFAULT 60,
    
    -- 个人最好成绩 PB (秒数存储，方便排序与换算)
    marathon_pb INT,     -- 全马 (例如 10800 = 3:00:00)
    half_pb INT,         -- 半马
    ten_k_pb INT,        -- 10公里
    five_k_pb INT,       -- 5公里
    
    -- 佳明绑定状态与加密凭据
    garmin_connected BOOLEAN DEFAULT FALSE,
    garmin_email TEXT,
    garmin_encrypted_password TEXT,
    garmin_domain VARCHAR(20) DEFAULT 'garmin.cn', -- 'garmin.cn' (中国版) 或 'garmin.com' (国际版)
    garmin_last_sync_at TIMESTAMPTZ,
    
    -- 通知渠道
    wecom_webhook_url TEXT,
    wechat_subscribe_enabled BOOLEAN DEFAULT FALSE,
    
    -- 用户偏好与系统字段
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================================================================
-- 2. 跑量目标表 (public.goals)
-- 支持全年 12 个月独立跑量目标设定
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    year INT NOT NULL DEFAULT EXTRACT(YEAR FROM CURRENT_DATE)::INT,
    period_type VARCHAR(20) DEFAULT 'monthly', -- 'monthly' 或 'weekly'
    target_distance NUMERIC(6, 1) NOT NULL DEFAULT 200.0, -- km (默认月目标)
    monthly_targets JSONB DEFAULT '[200,200,200,200,200,200,200,200,200,200,200,200]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_user_year UNIQUE(user_id, year)
);

-- ==============================================================================
-- 3. 跑步与运动记录表 (public.activities)
-- 由 Garmin 直连拉取入库
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.activities (
    id TEXT PRIMARY KEY, -- 格式为 'garmin_{activity_id}'
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    source VARCHAR(20) NOT NULL DEFAULT 'garmin_cn',
    name TEXT NOT NULL,
    activity_type VARCHAR(30) NOT NULL DEFAULT 'Run', -- 'Run', 'TrailRun', 'Treadmill', 'Workout' 等
    start_time TIMESTAMPTZ NOT NULL,
    timezone VARCHAR(50) DEFAULT 'Asia/Shanghai',
    
    -- 基础运动数据
    distance_meters NUMERIC(10, 2) NOT NULL DEFAULT 0,
    moving_time_seconds INT NOT NULL DEFAULT 0,
    elapsed_time_seconds INT NOT NULL DEFAULT 0,
    average_speed_mps NUMERIC(6, 3), -- 米/秒
    max_speed_mps NUMERIC(6, 3),
    avg_pace_str VARCHAR(20),        -- '4:35 /km'
    
    -- 心率与负荷指标
    average_heartrate INT,
    max_heartrate INT,
    average_cadence INT,
    total_elevation_gain NUMERIC(6, 1) DEFAULT 0,
    calories INT DEFAULT 0,
    trimp NUMERIC(6, 1) DEFAULT 0,
    aerobic_training_effect NUMERIC(3, 1),
    anaerobic_training_effect NUMERIC(3, 1),
    
    -- 详细分段、心率区间与原始数据 (JSONB)
    splits JSONB,
    laps JSONB,
    raw_garmin_data JSONB,
    
    -- AI 教练单次点评与日志 (Renato Canova 专项度评估)
    ai_journal JSONB,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建索引以优化高频查询
CREATE INDEX IF NOT EXISTS idx_activities_user_time ON public.activities(user_id, start_time DESC);
CREATE INDEX IF NOT EXISTS idx_activities_type ON public.activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_activities_start_time ON public.activities(start_time DESC);

-- ==============================================================================
-- 4. 每日健康与体能指标 (public.daily_health_metrics)
-- 来自 Garmin 每日健康摘要 (RHR, VO2 Max, 睡眠, 身体电量, HRV)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.daily_health_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    resting_heart_rate INT,
    vo2_max NUMERIC(4, 1),
    sleep_duration_seconds INT,
    sleep_score INT,
    body_battery_max INT,
    hrv_status VARCHAR(20),
    hrv_weekly_avg NUMERIC(5, 1),
    stress_level INT,
    source VARCHAR(20) DEFAULT 'garmin_cn',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_user_date UNIQUE(user_id, date)
);

CREATE INDEX IF NOT EXISTS idx_health_user_date ON public.daily_health_metrics(user_id, date DESC);

-- ==============================================================================
-- 5. 跑团与战队表 (public.teams)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    invite_code VARCHAR(10) NOT NULL UNIQUE,
    owner_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    description TEXT,
    logo_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================================================================
-- 6. 跑团成员表 (public.team_members)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.team_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES public.teams(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    role VARCHAR(20) DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_team_user UNIQUE(team_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_team_members_user ON public.team_members(user_id);
CREATE INDEX IF NOT EXISTS idx_team_members_team ON public.team_members(team_id);

-- ==============================================================================
-- 7. AI 教练深度分析与报告表 (public.coach_reports)
-- 包含最新周期诊断、每周智能复盘、月度总结
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.coach_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    report_type VARCHAR(30) NOT NULL, -- 'latest_analysis', 'weekly_review', 'monthly_review', 'training_plan'
    period_key VARCHAR(30),           -- 例如 '2026-W33', '2026-08'
    content JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_coach_reports_lookup ON public.coach_reports(user_id, report_type, period_key);

-- ==============================================================================
-- 8. 触发器：自动更新 updated_at 字段
-- ==============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS trg_profiles_updated_at ON public.profiles;
CREATE TRIGGER trg_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_goals_updated_at ON public.goals;
CREATE TRIGGER trg_goals_updated_at
    BEFORE UPDATE ON public.goals
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_activities_updated_at ON public.activities;
CREATE TRIGGER trg_activities_updated_at
    BEFORE UPDATE ON public.activities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_teams_updated_at ON public.teams;
CREATE TRIGGER trg_teams_updated_at
    BEFORE UPDATE ON public.teams
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==============================================================================
-- 9. 触发器：Supabase 注册新用户时自动创建 public.profiles 记录与初始 Goals
-- ==============================================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, phone, display_name, avatar_url)
    VALUES (
        NEW.id,
        NEW.email,
        NEW.phone,
        COALESCE(NEW.raw_user_meta_data->>'display_name', NEW.raw_user_meta_data->>'name', '跑者_' || SUBSTRING(NEW.id::text, 1, 6)),
        COALESCE(NEW.raw_user_meta_data->>'avatar_url', NULL)
    )
    ON CONFLICT (id) DO NOTHING;

    INSERT INTO public.goals (user_id, year, target_distance)
    VALUES (NEW.id, EXTRACT(YEAR FROM CURRENT_DATE)::INT, 200.0)
    ON CONFLICT (user_id, year) DO NOTHING;

    RETURN NEW;
END;
$$ language 'plpgsql' SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ==============================================================================
-- 10. 行级安全策略 (Row-Level Security, RLS)
-- ==============================================================================
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.goals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_health_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.team_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coach_reports ENABLE ROW LEVEL SECURITY;

-- 允许用户读写属于自己的 profile 数据；所有认证用户可读取基本资料用于跑团榜
CREATE POLICY "Users can view all public profiles for leaderboard"
    ON public.profiles FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Users can update own profile"
    ON public.profiles FOR UPDATE
    TO authenticated
    USING (auth.uid() = id);

-- Goals 策略
CREATE POLICY "Users can manage own goals"
    ON public.goals FOR ALL
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Authenticated users can read goals for leaderboard"
    ON public.goals FOR SELECT
    TO authenticated
    USING (true);

-- Activities 策略
CREATE POLICY "Users can view own activities"
    ON public.activities FOR ALL
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Users can read teammates activities"
    ON public.activities FOR SELECT
    TO authenticated
    USING (true);

-- Daily Health 策略
CREATE POLICY "Users can manage own health metrics"
    ON public.daily_health_metrics FOR ALL
    TO authenticated
    USING (auth.uid() = user_id);

-- Teams & Team Members 策略
CREATE POLICY "Anyone authenticated can view teams"
    ON public.teams FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Team owners can update own team"
    ON public.teams FOR UPDATE
    TO authenticated
    USING (auth.uid() = owner_id);

CREATE POLICY "Authenticated users can create teams"
    ON public.teams FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = owner_id);

CREATE POLICY "Members can view team members"
    ON public.team_members FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Users can join team"
    ON public.team_members FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can leave team"
    ON public.team_members FOR DELETE
    TO authenticated
    USING (auth.uid() = user_id);

-- Coach Reports 策略
CREATE POLICY "Users can manage own coach reports"
    ON public.coach_reports FOR ALL
    TO authenticated
    USING (auth.uid() = user_id);
