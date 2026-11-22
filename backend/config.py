import os
import logging
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    load_dotenv(env_path, override=False)
else:
    load_dotenv(override=False)

_INSECURE_SECRET_KEYS = {
    "",
    "rgm-cn-secret-encryption-key-32ch!",
    "rgm-cn-secret-encryption-key-for-garmin-pwd-32!",
    "rgm-cn-secret-encryption-key-must-be-32-chars-long!!",
    "production-secret-encryption-key-for-garmin-pwd!",
    "replace-with-at-least-32-char-random-encryption-key",
    "dev-secret-key-change-in-prod",
}
_INSECURE_JWT_SECRETS = {
    "",
    "super-secret-jwt-token-with-minimum-32-chars",
    "super-secret-jwt-token-with-at-least-32-characters-long",
    "your_32_characters_minimum_jwt_secret_key!",
}


class Settings:
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    PORT: int = int(os.getenv("PORT", "8000"))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "rgm-cn-secret-encryption-key-32ch!")
    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS",
        "https://rgm.vanpower.net,https://vanpower.net,https://www.vanpower.net,https://servicewechat.com",
    )

    # Supabase (disabled by default while SQLite WAL LocalStore is canonical; set ENABLE_SUPABASE_DUAL_WRITE=true when migrating)
    ENABLE_SUPABASE_DUAL_WRITE: bool = os.getenv("ENABLE_SUPABASE_DUAL_WRITE", "false").lower() in ("true", "1")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip()
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "").strip()
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "super-secret-jwt-token-with-minimum-32-chars")

    # LLM (DashScope Qwen / DeepSeek — 4-tier routing)
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    DASHSCOPE_WORKSPACE_ID: str = os.getenv("DASHSCOPE_WORKSPACE_ID", "")
    DASHSCOPE_BASE_URL: str = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/api/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen-max")
    LLM_MODEL_REASONING: str = os.getenv("LLM_MODEL_REASONING", os.getenv("LLM_MODEL", "qwen-max"))
    LLM_MODEL_WORKHORSE: str = os.getenv("LLM_MODEL_WORKHORSE", "qwen-plus")
    LLM_MODEL_FAST: str = os.getenv("LLM_MODEL_FAST", "qwen-flash")
    LLM_MODEL_OCR: str = os.getenv("LLM_MODEL_OCR", "qwen3.5-ocr")
    OPENAI_API_BASE: str = os.getenv("OPENAI_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "") or os.getenv("DASHSCOPE_API_KEY", "")

    # WeChat Mini Program (secret must come from environment / .env, never hardcoded in git)
    WECHAT_APP_ID: str = os.getenv("WECHAT_APP_ID") or "wxdfff48d6d0506130"
    WECHAT_APP_SECRET: str = os.getenv("WECHAT_APP_SECRET", "").strip()
    WECHAT_SUBSCRIBE_TEMPLATE_ID: str = os.getenv("WECHAT_SUBSCRIBE_TEMPLATE_ID", "I8K67iHNWQB0on15Z01rxKinP18DAuIPgaz7LSXIqT0")
    WECHAT_MINIPROGRAM_STATE: str = os.getenv("WECHAT_MINIPROGRAM_STATE", "formal")

    # Aliyun SMS
    ALIYUN_ACCESS_KEY_ID: str = os.getenv("ALIYUN_ACCESS_KEY_ID", "")
    ALIYUN_ACCESS_KEY_SECRET: str = os.getenv("ALIYUN_ACCESS_KEY_SECRET", "")
    ALIYUN_SMS_SIGN_NAME: str = os.getenv("ALIYUN_SMS_SIGN_NAME", "")
    ALIYUN_SMS_TEMPLATE_CODE: str = os.getenv("ALIYUN_SMS_TEMPLATE_CODE", "")

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")

    # Scheduler
    ENABLE_SCHEDULER: bool = os.getenv("ENABLE_SCHEDULER", "true").lower() in ("true", "1")
    GARMIN_SYNC_INTERVAL_MINUTES: int = int(os.getenv("GARMIN_SYNC_INTERVAL_MINUTES", "30"))


settings = Settings()

if settings.ENVIRONMENT.lower() == "production":
    if settings.SECRET_KEY in _INSECURE_SECRET_KEYS or len(settings.SECRET_KEY) < 16:
        logging.getLogger("rgm_config").warning(
            "SECURITY WARNING: SECRET_KEY is weak/default in production; schedule key rotation with credential re-encryption"
        )
    if settings.SUPABASE_JWT_SECRET in _INSECURE_JWT_SECRETS or len(settings.SUPABASE_JWT_SECRET) < 24:
        raise RuntimeError("SECURITY ERROR: SUPABASE_JWT_SECRET must be set to a strong production secret when ENVIRONMENT=production")
