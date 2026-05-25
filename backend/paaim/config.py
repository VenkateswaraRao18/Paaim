import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Application settings from environment variables."""

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://paaim:paaim_dev@localhost:5432/paaim_db"
    )

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # API
    API_TITLE: str = "PAAIM API"
    API_VERSION: str = "0.1.0"
    API_DESCRIPTION: str = "Policy-Aware Agentic Intelligence Manager for Manufacturing"

    # Anthropic
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # App environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development"

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # MES Connector
    MES_HOST: str = os.getenv("MES_HOST", "")
    MES_PORT: int = int(os.getenv("MES_PORT", "8001"))
    MES_TIMEOUT: int = int(os.getenv("MES_TIMEOUT", "30"))
    MES_USER: str = os.getenv("MES_USER", "paaim")
    MES_PASSWORD: str = os.getenv("MES_PASSWORD", "password")

    # CMMS Connector
    CMMS_HOST: str = os.getenv("CMMS_HOST", "")
    CMMS_PORT: int = int(os.getenv("CMMS_PORT", "8002"))
    CMMS_TIMEOUT: int = int(os.getenv("CMMS_TIMEOUT", "30"))

settings = Settings()

