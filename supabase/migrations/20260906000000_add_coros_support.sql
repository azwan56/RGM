-- ==============================================================================
-- RGM (Running Community Manager) - China Edition
-- Migration: Add COROS (高驰) Watch Integration Support
-- Target: PostgreSQL 15+ (Supabase)
-- ==============================================================================

-- 1. 为 profiles 表增加 COROS 账号绑定与凭据字段
ALTER TABLE public.profiles
ADD COLUMN IF NOT EXISTS coros_connected BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS coros_account TEXT,
ADD COLUMN IF NOT EXISTS coros_encrypted_password TEXT,
ADD COLUMN IF NOT EXISTS coros_domain VARCHAR(50) DEFAULT 'teamcnapi.coros.com',
ADD COLUMN IF NOT EXISTS coros_last_sync_at TIMESTAMPTZ;

-- 创建索引以优化高频同步查询
CREATE INDEX IF NOT EXISTS idx_profiles_coros_connected ON public.profiles(coros_connected) WHERE coros_connected = TRUE;

-- 2. 注释说明
COMMENT ON COLUMN public.profiles.coros_connected IS '是否已绑定 COROS (高驰) 账号';
COMMENT ON COLUMN public.profiles.coros_account IS 'COROS 账号（手机号或邮箱）';
COMMENT ON COLUMN public.profiles.coros_encrypted_password IS 'AES 加密的 COROS 登录密码';
COMMENT ON COLUMN public.profiles.coros_domain IS 'COROS API 域名 (中国区: teamcnapi.coros.com, 国际区: teamapi.coros.com)';
COMMENT ON COLUMN public.profiles.coros_last_sync_at IS '最近一次成功从 COROS 同步数据的时间戳';
