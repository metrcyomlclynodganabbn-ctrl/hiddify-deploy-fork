"""
Configuration settings for Hiddify Bot.
Uses Pydantic Settings for type-safe configuration management.
"""

from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # ==================== TELEGRAM BOT ====================
    bot_token: str = Field(..., description="Telegram Bot Token from @BotFather")
    admin_ids: List[int] = Field(default_factory=list, description="Admin Telegram IDs")

    # ==================== DATABASE ====================
    db_host: str = Field(default="postgres", description="Database host")
    db_port: int = Field(default=5432, description="Database port")
    db_name: str = Field(default="hiddify_bot", description="Database name")
    db_user: str = Field(default="hiddify_user", description="Database user")
    db_password: str = Field(..., description="Database password")

    @property
    def database_url(self) -> str:
        """Construct async database URL."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # ==================== HIDDIFY API ====================
    panel_domain: str = Field(..., description="Hiddify Panel domain")
    hiddify_api_token: str = Field(..., description="Hiddify API token")

    @property
    def hiddify_api_url(self) -> str:
        """Construct Hiddify API URL."""
        domain = self.panel_domain.rstrip("/")
        if not domain.endswith("/api"):
            domain = f"{domain}/api" if domain.endswith("/") else f"{domain}/api"
        return domain

    # ==================== PAYMENTS ====================
    # CryptoBot
    cryptobot_api_token: Optional[str] = Field(default=None, description="CryptoBot API token")
    cryptobot_payment_url: Optional[str] = Field(default=None, description="CryptoBot payment URL")

    # Telegram Stars (built-in, no token needed)

    # YooMoney (ЮМани)
    yoomoney_api_token: Optional[str] = Field(default=None, description="YooMoney API token")
    yoomoney_shop_id: Optional[str] = Field(default=None, description="YooMoney shop ID")

    # Stripe (deprecated in v4, will be removed)
    stripe_secret_key: Optional[str] = Field(default=None, description="Stripe secret key (deprecated)")
    stripe_webhook_secret: Optional[str] = Field(default=None, description="Stripe webhook secret (deprecated)")

    # Pricing
    price_weekly: float = Field(default=3.00, description="Price for weekly plan")
    price_monthly: float = Field(default=10.00, description="Price for monthly plan")
    price_quarterly: float = Field(default=25.00, description="Price for quarterly plan")

    # ==================== REDIS ====================
    redis_host: str = Field(default="redis", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_password: str = Field(..., description="Redis password")

    @property
    def redis_url(self) -> str:
        """Construct Redis URL."""
        auth_part = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth_part}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ==================== TRIAL ====================
    trial_days: int = Field(default=7, description="Trial period in days")
    trial_data_limit_gb: int = Field(default=10, description="Trial data limit in GB")

    # ==================== REFERRAL ====================
    referral_bonus: float = Field(default=1.00, description="Referral bonus amount")
    referral_currency: str = Field(default="USD", description="Referral bonus currency")

    # ==================== SUPPORT ====================
    max_open_tickets: int = Field(default=3, description="Maximum open tickets per user")

    # ==================== LOGGING ====================
    log_level: str = Field(default="INFO", description="Log level")
    log_file: str = Field(default="logs/bot.log", description="Log file path")

    # ==================== SECURITY ====================
    secret_key: str = Field(..., description="Secret key for encryption")

    # ==================== FEATURES ====================
    enable_promo_codes: bool = Field(default=True, description="Enable promo codes")
    enable_referral_system: bool = Field(default=True, description="Enable referral system")
    enable_trial_period: bool = Field(default=True, description="Enable trial period")


# Global settings instance
settings = Settings()
