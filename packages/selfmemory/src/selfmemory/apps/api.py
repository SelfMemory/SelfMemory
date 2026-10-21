import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from selfmemory.config import config
from selfmemory.features import BUILTIN
from selfmemory.features.runs.store import ensure_indexes
from selfmemory.features.runs.worker import Worker
from selfmemory.features.wiki.service import WikiService
from selfmemory.kernel.datetime import utc_now
from selfmemory.kernel.feature import discover
from selfmemory.platform.dependencies import mongo_db
from selfmemory.platform.health import is_alive, is_ready, perform_health_checks
from selfmemory.platform.ory.hydra_proxy import router as hydra_proxy_router
from selfmemory.platform.ory.mcp_metadata import get_protected_resource_metadata
from selfmemory.platform.rate_limiter import limiter
from selfmemory.platform.telemetry.setup import initialize_telemetry
from selfmemory.wiki_settings import load_settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

load_dotenv()

# Validate configuration on startup
config_errors = config.validate()
if config_errors:
    logging.error("=" * 50)
    logging.error("CONFIGURATION VALIDATION FAILED")
    logging.error("=" * 50)
    for error in config_errors:
        logging.error(f"  ❌ {error}")
    logging.error("=" * 50)
    logging.error("Please fix the configuration errors before starting the server.")
    raise RuntimeError("Configuration validation failed. See logs for details.")

# Log configuration (excluding sensitive values)
config.log_config()

# Log security status for API documentation
if config.app.ENVIRONMENT == "production":
    logging.info("🔒 SECURITY: API documentation endpoints disabled in production")
else:
    logging.info(
        "📚 DEV MODE: API documentation available at /docs, /redoc, /openapi.json"
    )

WIKI_SETTINGS = load_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the wiki service and, unless disabled, the in-process run worker.

    Any number of API processes may each run a worker: claiming a job is one
    atomic update, so they share the queue without coordination. Set
    SELFMEMORY_WORKER=off to run workers separately
    (``python -m selfmemory.features.runs.worker``).
    """
    try:
        ensure_indexes(mongo_db)
    except Exception:
        logging.exception("could not create wiki indexes; continuing")
    service = WikiService(mongo_db, WIKI_SETTINGS)
    app.state.wiki = service
    worker = None
    if WIKI_SETTINGS.worker_enabled:
        worker = Worker(service)
        worker.start()
        logging.info("wiki worker started (%s)", worker.worker_id)
    try:
        yield
    finally:
        if worker is not None:
            worker.stop()


# FastAPI app with conditional documentation based on environment
app = FastAPI(
    title="SelfMemory APIs",
    lifespan=lifespan,
    # Security: Disable API documentation in production to prevent information disclosure
    docs_url="/docs" if config.app.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if config.app.ENVIRONMENT != "production" else None,
    openapi_url="/openapi.json" if config.app.ENVIRONMENT != "production" else None,
)

# Initialize OpenTelemetry (production only)
initialize_telemetry(app)

# Add rate limiting to app state
app.state.limiter = limiter


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
    ]
    + [config.app.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


API_PREFIX = "/api/v1"
# Unversioned alias kept for the current dashboard until the new UI reaches
# parity; hidden from the OpenAPI contract.
LEGACY_API_PREFIX = "/api"


class _ApiContext:
    """The AppContext features register against (see kernel/feature.py)."""

    def __init__(self, app: FastAPI) -> None:
        self.app = app

    def add_router(self, router) -> None:
        self.app.include_router(router, prefix=API_PREFIX)
        self.app.include_router(
            router, prefix=LEGACY_API_PREFIX, include_in_schema=False
        )


_ctx = _ApiContext(app)
for feature in discover(BUILTIN):
    feature.register(_ctx)
app.include_router(hydra_proxy_router)


@app.get("/", summary="Service index")
def service_index():
    """Point a browser at the useful entry points.

    Intentionally unauthenticated: it exposes no data, only the shape of the
    API, and it has to answer before any credential exists.
    """
    return {
        "service": "SelfMemory",
        "status": "running",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/health",
        "wiki": {
            "model": "raw sources -> agent-maintained OKF wiki (git per scope)",
            "auth": "Authorization: Session <cookie> | Bearer <token or api key>",
            "endpoints": [
                "GET    /api/v1/wiki/scopes",
                "GET    /api/v1/wiki/tree",
                "GET    /api/v1/wiki/file?path=",
                "PUT    /api/v1/wiki/file",
                "DELETE /api/v1/wiki/file?path=",
                "GET    /api/v1/wiki/sources?scope=",
                "POST   /api/v1/wiki/upload",
                "POST   /api/v1/wiki/runs",
                "GET    /api/v1/wiki/runs/{id}/events",
                "GET    /api/v1/wiki/chats",
                "GET    /api/v1/wiki/graph",
                "GET    /api/v1/wiki/timeline",
                "GET    /api/v1/wiki/search?q=",
                "GET    /api/v1/wiki/promotions",
                "GET    /api/v1/wiki/status",
            ],
        },
    }


@app.get(
    "/.well-known/oauth-protected-resource",
    summary="Protected Resource Metadata for MCP",
)
def mcp_protected_resource_metadata():
    """
    RFC 9728 Protected Resource Metadata endpoint for MCP clients.

    This endpoint tells MCP clients:
    - What authorization servers to use (Ory Hydra)
    - What scopes are supported
    - Where to find documentation
    """
    if not config.mcp.ENABLED:
        raise HTTPException(status_code=404, detail="MCP is not enabled")

    logging.info("[MCP] Serving Protected Resource Metadata")
    return get_protected_resource_metadata()


@app.get("/health", summary="Comprehensive health check")
def health_check():
    """
    Comprehensive health check endpoint.

    Checks all system dependencies:
    - Database connectivity
    - Memory usage
    - Disk usage
    - SMTP connectivity (if configured)

    Returns:
        - 200: All systems healthy or degraded
        - 503: One or more critical systems unhealthy
    """
    try:
        health_status = perform_health_checks()

        # Return 503 if unhealthy
        if health_status["status"] == "unhealthy":
            return JSONResponse(status_code=503, content=health_status)

        return health_status

    except Exception:
        logging.exception("Health check error:")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": utc_now().isoformat(),
                "error": "Health check failed",
            },
        )


@app.get("/health/live", summary="Liveness probe")
def liveness_probe():
    """Kubernetes-style liveness probe. Returns 200 if the application is running."""
    if is_alive():
        return {"status": "alive", "timestamp": utc_now().isoformat()}

    return JSONResponse(
        status_code=503, content={"status": "dead", "timestamp": utc_now().isoformat()}
    )


@app.get("/health/ready", summary="Readiness probe")
def readiness_probe():
    """Kubernetes-style readiness probe. Returns 200 if the application is ready to serve traffic."""
    try:
        if is_ready():
            return {"status": "ready", "timestamp": utc_now().isoformat()}

        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "timestamp": utc_now().isoformat()},
        )

    except Exception:
        logging.exception("Readiness check error:")
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "timestamp": utc_now().isoformat(),
                "error": "Readiness check failed",
            },
        )


def main() -> None:  # pragma: no cover - process entry point
    import uvicorn

    logging.info("Starting SelfMemory Backend Server")
    logging.info(f"API available at: http://{config.server.HOST}:{config.server.PORT}/")

    uvicorn.run(
        app,
        host=config.server.HOST,
        port=config.server.PORT,
        log_level=config.logging.LEVEL.lower(),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
