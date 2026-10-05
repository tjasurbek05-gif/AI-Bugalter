"""Application settings, loaded from environment variables / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""

    # OpenAI
    openai_api_key: str = ""
    whisper_model: str = "whisper-1"
    gpt_parse_model: str = "gpt-4o-mini"
    gpt_insights_model: str = "gpt-4o"

    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_1_week: str = ""
    stripe_price_1_month: str = ""
    stripe_price_3_months: str = ""
    stripe_price_6_months: str = ""
    stripe_price_1_year: str = ""

    # Click (click.uz)
    click_service_id: str = ""
    click_merchant_id: str = ""
    click_secret_key: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://bugalter_user:secure_password@localhost:5432/ai_bugalter"
    redis_url: str = "redis://localhost:6379/0"

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    webhook_url: str = ""
    webhook_secret: str = "change_me_to_a_random_string"

    # Business rules
    free_tier_monthly_limit: int = 5
    loan_reminder_days_before: int = 3

    # Monitoring
    sentry_dsn: str = ""
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def telegram_webhook_path(self) -> str:
        return f"/webhook/telegram/{self.webhook_secret}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
