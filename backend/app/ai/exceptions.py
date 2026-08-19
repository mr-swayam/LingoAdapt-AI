class AIProviderNotConfiguredError(Exception):
    """No AI provider is configured (app.ai.factory.get_ai_provider() -> None).
    Deliberately not a subclass of AIProviderError - "not configured" is a
    deployment/config issue the caller must handle explicitly, not a
    transient provider failure to retry."""


class AIProviderError(Exception):
    """Base class for anything that goes wrong talking to an AI provider."""


class AITimeoutError(AIProviderError):
    pass


class AIRequestError(AIProviderError):
    """Provider reachable but returned an error (bad status, auth failure, etc.)."""


class AIResponseValidationError(AIProviderError):
    """Provider responded, but the content didn't parse into the expected
    structured schema - rules.md: never trust AI output without validation.
    """
