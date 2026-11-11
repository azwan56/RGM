import logging
try:
    from supabase import create_client, Client
except ImportError:
    create_client = None
    Client = None
from config import settings

logger = logging.getLogger("rgm_db")

def get_supabase_admin():
    """Returns a Supabase client initialized with the Service Role Key for backend administration."""
    if not create_client:
        logger.warning("[supabase] supabase-py library not installed. Client in fallback mode.")
        return None
    url = (settings.SUPABASE_URL or "").strip().rstrip("/")
    key = (settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY or "").strip()
    if (
        not url
        or not key
        or url in (f"http://localhost:{settings.PORT}", f"http://127.0.0.1:{settings.PORT}", "http://localhost:8000", "http://127.0.0.1:8000")
        or "fake" in key.lower()
        or "your_production" in key.lower()
    ):
        logger.info("[supabase] External Supabase disabled or placeholder configured; using LocalStore primary mode.")
        return None
    return create_client(url, key)

# Shared admin client
supabase_admin = get_supabase_admin()
