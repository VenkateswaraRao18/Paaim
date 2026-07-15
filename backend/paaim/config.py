from typing import List
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Core ───────────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-a-real-secret"

    # ── API metadata ───────────────────────────────────────────────────────
    API_TITLE: str = "PAAIM API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "Policy-Aware Agentic Intelligence Manager for Manufacturing"

    # ── Database ───────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./paaim_dev.db"
    DATABASE_URL_SYNC: str = "sqlite:///./paaim_dev.db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

    # ── Redis ──────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_DECISION_CACHE_TTL: int = 3600

    # ── AI — Google Gemini ─────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_MAX_TOKENS: int = 1024
    GEMINI_TIMEOUT: int = 30

    # ── Live watchers ──────────────────────────────────────────────────────
    # There is deliberately no stream URL here. A source's address belongs to
    # the source record the operator connected, not to config: a default made
    # PAAIM answer with a hardcoded plant's signals when nothing was connected
    # at all, and offered watchers on machines it had never been told about.
    #
    # Watchers are in-memory, so a restart drops them. Rebuild on boot from the
    # confirmed mappings — the operator's own configuration.
    STREAM_AUTO_CONNECT: bool = True
    STREAM_TRIGGER_LEVEL: str = "critical"
    # One physical fault = one incident, across every source that reports it.
    # Sized in minutes: long enough to cover a stream and a historian seeing the
    # same breach, short enough that a genuinely new fault is never swallowed.
    INCIDENT_DEDUPE_WINDOW_S: float = 120.0

    # ── Event Bus (reliable ingestion backbone) ────────────────────────────
    # EVENT_BUS = "memory" (durable JSONL log, runs anywhere) | "kafka"
    EVENT_BUS: str = "memory"
    BUS_DATA_DIR: str = "./data_bus"
    BUS_EVENTS_TOPIC: str = "factory.events"
    BUS_DECISIONS_TOPIC: str = "factory.decisions"
    BUS_DLQ_TOPIC: str = "factory.events.dlq"
    BUS_CONSUMER_GROUP: str = "paaim-orchestrator"
    BUS_AUTO_CONSUME: bool = True          # start the background consumer on app startup
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"

    # ── Logging ────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── CORS ───────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000"

    # ── Rate limiting ──────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 120

    # ── JWT ────────────────────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # ── MES Connector ──────────────────────────────────────────────────────
    MES_HOST: str = ""
    MES_PORT: int = 8001
    MES_TIMEOUT: int = 30
    MES_USER: str = "paaim"
    MES_PASSWORD: str = ""

    # ── CMMS Connector ─────────────────────────────────────────────────────
    CMMS_HOST: str = ""
    CMMS_PORT: int = 8002
    CMMS_TIMEOUT: int = 30

    # ── ERP Connector ──────────────────────────────────────────────────────
    ERP_HOST: str = ""
    ERP_PORT: int = 8003
    ERP_TIMEOUT: int = 30
    ERP_CLIENT_ID: str = ""
    ERP_CLIENT_SECRET: str = ""
    ERP_API_PREFIX: str = "/api/v1"

    # ── Derived helpers ────────────────────────────────────────────────────
    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}")
        return v

    @model_validator(mode="after")
    def enforce_production_secrets(self) -> "Settings":
        if self.is_production:
            if self.SECRET_KEY == "change-me-in-production-use-a-real-secret":
                raise ValueError("SECRET_KEY must be set in production")
            if not self.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY must be set in production")
        return self


settings = Settings()
