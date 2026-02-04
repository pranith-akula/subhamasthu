"""
Application configuration using pydantic-settings.
Loads from environment variables / .env file.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    app_name: str = "subhamasthu"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: str
    
    # API Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Neon Postgres
    database_url: str
    
    # Redis
    redis_url: str
    
    # Gupshup WhatsApp
    gupshup_api_key: str
    gupshup_app_name: str
    gupshup_source_number: str
    gupshup_webhook_secret: str = ""
    
    # Razorpay
    razorpay_key_id: str
    razorpay_key_secret: str
    razorpay_webhook_secret: str
    
    # OpenAI
    openai_api_key: str
    
    # Timezone
    default_timezone: str = "America/Chicago"
    
    # Admin
    admin_api_key: str
    
    @property
    def is_development(self) -> bool:
        return self.app_env == "development"
    
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
