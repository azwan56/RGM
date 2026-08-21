import logging
from supabase import create_client, Client
from config import settings

logger = logging.getLogger("rgm_db")

def get_supabase_admin() -> Client:
    """Returns a Supabase client initialized with the Service Role Key for backend administration."""
    key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY
    if not settings.SUPABASE_URL or not key:
        logger.warning("[supabase] SUPABASE_URL or key not provided. Client initialized in mock/fallback mode.")
        return None
    return create_client(settings.SUPABASE_URL, key)

# Shared admin client
supabase_admin = get_supabase_admin()
