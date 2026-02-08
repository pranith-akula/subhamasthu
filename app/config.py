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
    secret_key: str = "dev-secret-change-in-production"
    
    # API Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Neon Postgres
    database_url: str = ""
    
    # Redis
    redis_url: str = ""
    
    # Meta WhatsApp (Direct)
    meta_access_token: str = ""
    meta_phone_number_id: str = ""
    meta_webhook_verify_token: str = "subhamasthu_secure_webhook"
    
    # Bot Phone Number (Public)
    whatsapp_phone_number: str = "15550204780"
    
    # Razorpay (optional for initial setup)
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"  # gpt-4o, gpt-4o-mini, gpt-4-turbo
    
    # Cloudinary
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    
    # Timezone
    default_timezone: str = "America/Chicago"
    
    # Admin
    admin_api_key: str = ""
    
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
