from functools import lru_cache

from app.ai.base import AIProvider
from app.ai.groq_provider import GroqAIProvider
from app.core.config import get_settings


@lru_cache
def get_ai_provider() -> AIProvider | None:
    """None means no provider is configured - callers must handle this
    explicitly (AIProviderNotConfiguredError) rather than silently degrading,
    since a missing key should be an obvious 503, not a mysterious failure.
    """
    settings = get_settings()
    if settings.ai_provider == "groq" and settings.ai_api_key:
        return GroqAIProvider(api_key=settings.ai_api_key, default_model=settings.ai_default_model)
    return None
