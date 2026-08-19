from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET_KEY = "change-me-in-production"


class Settings(BaseSettings):
    # str_strip_whitespace: a real deployment (Phase 14, Railway) hit a
    # trailing newline that ended up inside DATABASE_URL's value via its
    # host's environment-variable UI - psycopg then tried to connect to a
    # database literally named "railway\n", which doesn't exist. Stripping
    # whitespace on every string field defends against this class of paste/
    # editor artifact across every setting, not just the one that broke.
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", str_strip_whitespace=True
    )

    environment: str = "development"
    database_url: str = "postgresql+psycopg://lingoadapt:lingoadapt@localhost:5432/lingoadapt_dev"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = _DEFAULT_SECRET_KEY
    cors_origins: str = "http://localhost:3000"

    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""

    ai_provider: str = "none"
    ai_api_key: str = ""
    ai_default_model: str = ""

    # Phase 14: empty means error monitoring stays disabled (see
    # app/core/monitoring.py) - no Sentry account exists for this project to
    # hardcode a real DSN for.
    sentry_dsn: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _reject_unsafe_production_config(self) -> "Settings":
        # Phase 12/13 security review: fail at startup rather than silently
        # run with a misconfiguration that's obvious in hindsight but easy
        # to ship by accident (an unedited .env, a copy-pasted dev config).
        if self.environment != "production":
            return self

        if self.secret_key == _DEFAULT_SECRET_KEY:
            # The single most catastrophic case - app.core.security uses this
            # to sign/verify every access token, so the placeholder value
            # means anyone could forge a valid one.
            raise ValueError(
                "SECRET_KEY must be set to a real secret when ENVIRONMENT=production "
                "(refusing to start with the placeholder default)."
            )

        localhost_origins = [
            origin
            for origin in self.cors_origin_list
            if "localhost" in origin or "127.0.0.1" in origin
        ]
        if localhost_origins:
            raise ValueError(
                f"CORS_ORIGINS still includes localhost origin(s) {localhost_origins} with "
                "ENVIRONMENT=production (refusing to start - set CORS_ORIGINS to the real "
                "production frontend origin(s))."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
