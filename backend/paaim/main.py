from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from paaim.config import settings
from paaim.models import create_tables
from paaim.agents.registry import initialize_registry

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
    # Create database tables
    create_tables()

    # Initialize agent registry
    initialize_registry()

    print(f"PAAIM started in {settings.ENVIRONMENT} mode")
    print(f"Database: {settings.DATABASE_URL}")
    print(f"Redis: {settings.REDIS_URL}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("PAAIM shutting down")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "running",
        "environment": settings.ENVIRONMENT
    }


@app.get("/health")
async def health():
    """Health status endpoint."""
    return {"status": "healthy"}


# Import and include routers
from paaim.api import events, agents

app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
