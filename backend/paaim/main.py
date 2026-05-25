from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from paaim.config import settings
from paaim.models import create_tables
from paaim.agents.registry import initialize_registry
from paaim.logging_config import setup_logging, get_logger
from paaim.connectors.manager import get_connector_manager, ConnectorConfig

# Setup logging (JSON in production, plain text in development)
json_output = settings.ENVIRONMENT != "development"
setup_logging(level="INFO", json_output=json_output)
logger = get_logger(__name__)

# Initialize application
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize app on startup."""
    try:
        # Create database tables
        create_tables()
        logger.info("Database tables created/verified")

        # Initialize agent registry
        initialize_registry()
        logger.info("Agent registry initialized")

        # Initialize connectors
        manager = get_connector_manager()

        # Register MES connector if configured
        if settings.MES_HOST:
            mes_config = ConnectorConfig(
                name="mes",
                host=settings.MES_HOST,
                port=settings.MES_PORT,
                timeout_seconds=settings.MES_TIMEOUT,
                extra_config={
                    "username": settings.MES_USER,
                    "password": settings.MES_PASSWORD,
                },
            )
            manager.register_connector("mes_prod", "mes", mes_config)
            logger.info("MES connector registered")

        # Register CMMS connector if configured
        if settings.CMMS_HOST:
            cmms_config = ConnectorConfig(
                name="cmms",
                host=settings.CMMS_HOST,
                port=settings.CMMS_PORT,
                timeout_seconds=settings.CMMS_TIMEOUT,
            )
            manager.register_connector("cmms_prod", "cmms", cmms_config)
            logger.info("CMMS connector registered")

        # Connect all connectors
        await manager.connect_all()
        logger.info("All connectors connected")

        # Start health monitoring
        await manager.start_health_monitoring()
        logger.info("Connector health monitoring started")

        logger.info(
            f"PAAIM started successfully in {settings.ENVIRONMENT} mode",
            extra={
                "database_url": settings.DATABASE_URL,
                "redis_url": settings.REDIS_URL,
            },
        )

    except Exception as e:
        logger.error(
            f"Startup error: {e}",
            extra={"error_type": type(e).__name__},
            exc_info=True,
        )
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    try:
        manager = get_connector_manager()
        await manager.disconnect_all()
        logger.info("PAAIM shutdown completed successfully")
    except Exception as e:
        logger.error(f"Shutdown error: {e}", exc_info=True)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "running",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health")
async def health():
    """Health status endpoint."""
    return {"status": "healthy"}


@app.get("/health/connectors")
async def connector_health():
    """Get connector health status."""
    manager = get_connector_manager()
    health_summary = manager.get_health_summary()
    return {"connectors": health_summary}


# Import and include routers
from paaim.api import events, agents, auth

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])

