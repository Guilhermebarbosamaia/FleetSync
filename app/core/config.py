from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações globais da aplicação carregadas a partir de variáveis de ambiente ou .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "FleetPulse"
    DEBUG: bool = False
    FRONTEND_URL: str = "http://localhost:5173"

    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fleetpulse"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PUBSUB_CHANNEL: str = "fleet:telemetry"
    REDIS_STATE_TTL_SECONDS: Optional[int] = 86400  # 24 horas por padrão; None para infinito


settings = Settings()
