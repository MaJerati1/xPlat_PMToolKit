"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable loading."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # Application
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_SECRET_KEY: str = "change-me"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://toolkit:toolkit_dev@localhost:5432/meeting_toolkit"
    DATABASE_POOL_SIZE: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM Configuration
    LLM_DEFAULT_TIER: int = 1
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Model Selection
    LLM_PRIMARY_MODEL: str = "claude-sonnet-4-6"
    LLM_BUDGET_MODEL: str = "gpt-4o-mini"
    LLM_SELFHOSTED_MODEL: str = "llama3.3:70b"
    LLM_PREFERRED_PROVIDER: str = "anthropic"  # "anthropic", "openai", or "ollama"

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"

    # Auth0
    AUTH0_DOMAIN: str = ""
    AUTH0_CLIENT_ID: str = ""
    AUTH0_CLIENT_SECRET: str = ""
    AUTH0_AUDIENCE: str = ""

    # Email
    SENDGRID_API_KEY: str = ""
    EMAIL_FROM: str = "noreply@meeting-toolkit.com"

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # Sentry
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"

    # Setup Token (for settings API access)
    SETUP_TOKEN: str = ""



settings = Settings()
