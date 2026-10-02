"""Application configuration using pydantic-settings."""

import warnings
from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Insecure default value that must be changed in production
_INSECURE_DEFAULT_SECRET = "your-secret-key-change-in-production"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "OnCall Copilot"
    environment: Literal["development", "testing", "production"] = "development"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/oncall_copilot"
    database_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT Authentication
    jwt_secret_key: str = _INSECURE_DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Encryption key for sensitive data (e.g., GitHub tokens)
    # If not provided, falls back to deriving from jwt_secret_key
    encryption_key: str | None = None

    # Ollama - AI Investigation (Phase 4+)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:latest"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        """Validate security settings based on environment."""
        if self.environment == "production":
            # Fail hard in production with insecure defaults
            if self.jwt_secret_key == _INSECURE_DEFAULT_SECRET:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a secure value in production. "
                    "Generate one with: openssl rand -hex 32"
                )
            if len(self.jwt_secret_key) < 32:
                raise ValueError(
                    "JWT_SECRET_KEY must be at least 32 characters in production."
                )
        elif self.jwt_secret_key == _INSECURE_DEFAULT_SECRET:
            # Warn in development
            warnings.warn(
                "Using insecure default JWT_SECRET_KEY. "
                "Set JWT_SECRET_KEY environment variable for security.",
                UserWarning,
                stacklevel=2,
            )
        return self

    @property
    def async_database_url(self) -> str:
        """Ensure database URL uses asyncpg driver."""
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://")
        return self.database_url

    @property
    def effective_encryption_key(self) -> str:
        """Get the encryption key, falling back to JWT secret if not set."""
        return self.encryption_key or self.jwt_secret_key


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
