import time
import uuid
import logging

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from paaim.config import settings
from paaim.models import create_tables
from paaim.agents.registry import initialize_registry
from paaim.logging_config import setup_logging, get_logger
from paaim.connectors.manager import get_connector_manager, ConnectorConfig

setup_logging(level=settings.LOG_LEVEL, json_output=settings.is_production)
logger = get_logger(__name__)

app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ── Security headers ──────────────────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)


# ── Request correlation ID + latency logging ──────────────────────────────────
class RequestTracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.perf_counter()
        request.state.request_id = request_id

        response: Response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"

        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 1),
            },
        )
        return response


app.add_middleware(RequestTracingMiddleware)


# ── Startup / shutdown ────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    try:
        await create_tables()
        logger.info("Database tables created/verified")

        initialize_registry()
        logger.info("Agent registry initialized")

        manager = get_connector_manager()

        if settings.MES_HOST:
            mes_config = ConnectorConfig(
                name="mes",
                host=settings.MES_HOST,
                port=settings.MES_PORT,
                timeout_seconds=settings.MES_TIMEOUT,
                extra_config={"username": settings.MES_USER, "password": settings.MES_PASSWORD},
            )
            manager.register_connector("mes_prod", "mes", mes_config)
            logger.info("MES connector registered")

        if settings.CMMS_HOST:
            cmms_config = ConnectorConfig(
                name="cmms",
                host=settings.CMMS_HOST,
                port=settings.CMMS_PORT,
                timeout_seconds=settings.CMMS_TIMEOUT,
            )
            manager.register_connector("cmms_prod", "cmms", cmms_config)
            logger.info("CMMS connector registered")

        if settings.ERP_HOST:
            erp_config = ConnectorConfig(
                name="erp",
                host=settings.ERP_HOST,
                port=settings.ERP_PORT,
                timeout_seconds=settings.ERP_TIMEOUT,
                extra_config={
                    "client_id": settings.ERP_CLIENT_ID,
                    "client_secret": settings.ERP_CLIENT_SECRET,
                    "api_prefix": settings.ERP_API_PREFIX,
                },
            )
            manager.register_connector("erp_prod", "erp", erp_config)
            logger.info("ERP connector registered")

        await manager.connect_all()
        await manager.start_health_monitoring()

        # Reliable ingestion backbone: start the durable bus consumer that
        # turns published events into governed decisions (at-least-once).
        if settings.BUS_AUTO_CONSUME:
            from paaim.bus.consumer import start_orchestration_consumer
            await start_orchestration_consumer()
            logger.info("Event bus consumer started", extra={"backend": settings.EVENT_BUS})

        logger.info(
            "PAAIM started successfully",
            extra={"environment": settings.ENVIRONMENT, "database_url": settings.DATABASE_URL},
        )
    except Exception as e:
        logger.error("Startup error", extra={"error": str(e)}, exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    try:
        manager = get_connector_manager()
        await manager.stop_health_monitoring()
        await manager.disconnect_all()
        if settings.BUS_AUTO_CONSUME:
            from paaim.bus.consumer import stop_orchestration_consumer
            await stop_orchestration_consumer()
        from paaim.stream_bridge.bridge import get_stream_bridge
        await get_stream_bridge().disconnect_all()
        logger.info("PAAIM shutdown completed")
    except Exception as e:
        logger.error("Shutdown error", extra={"error": str(e)}, exc_info=True)


# ── Health endpoints ──────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "running",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health")
async def health():
    from paaim.models import engine
    from sqlalchemy import text
    db_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    status_str = "healthy" if db_ok else "degraded"
    return {
        "status": status_str,
        "database": "connected" if db_ok else "error",
        "environment": settings.ENVIRONMENT,
        "version": settings.API_VERSION,
    }


@app.get("/health/connectors")
async def connector_health():
    manager = get_connector_manager()
    return {"connectors": manager.get_health_summary()}


@app.get("/metrics")
async def metrics():
    """Expose Prometheus metrics."""
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        from fastapi.responses import Response as _Response
        return _Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except ImportError:
        return {"error": "prometheus_client not installed"}


# ── Routers ───────────────────────────────────────────────────────────────────
from paaim.api import events, agents, auth, custom_agents, analytics, knowledge, stream_agents, semantic, chat, normalization, evaluation
from fastapi import APIRouter as _AR
from paaim.observability.tracing import get_tracing_status
from paaim.model_router.router import get_router as _get_router
from paaim.memory.short_term import get_memory_store as _get_mem

_obs_router = _AR()

@_obs_router.get("/status")
def observability_status():
    return {
        "tracing": get_tracing_status(),
        "model_router": _get_router().get_catalogue(),
        "memory": _get_mem().stats(),
    }

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(custom_agents.router, prefix="/api/custom-agents", tags=["custom-agents"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(stream_agents.router, prefix="/api/stream-agents", tags=["stream-agents"])
app.include_router(semantic.router, prefix="/api/semantic", tags=["semantic"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(normalization.router, prefix="/api/normalization", tags=["normalization"])
app.include_router(evaluation.router, prefix="/api/eval", tags=["eval"])
app.include_router(_obs_router, prefix="/api/observability", tags=["observability"])
