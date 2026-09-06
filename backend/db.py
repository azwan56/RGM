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
    key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY
    if not settings.SUPABASE_URL or not key:
        logger.warning("[supabase] SUPABASE_URL or key not provided. Client initialized in mock/fallback mode.")
        return None
    return create_client(settings.SUPABASE_URL, key)

# Shared admin client
supabase_admin = get_supabase_admin()
