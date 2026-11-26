from contextlib import asynccontextmanager
import logging
import time
import uuid
from typing import Optional
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings, init_langsmith
from app.core.logging import get_app_logger, RequestContext, setup_logging
from app.db.session import init_db, close_db
from app.api.v1.router import api_router
from app.services.scheduler import scheduler_lifespan

settings = get_settings()

# Initialize LangSmith tracing at app startup
init_langsmith()

# Configure structured logging before serving requests
setup_logging(settings)
logger = get_app_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(
        "Application starting",
        extra={
            "environment": settings.ENVIRONMENT,
            "version": settings.APP_VERSION,
            "debug": settings.DEBUG,
        },
    )
    await init_db()

    # Start scheduler
    async with scheduler_lifespan():
        yield

    # Shutdown
    logger.info("Application shutting down")
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered blog and social post generator with Buffer publishing",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Assigns a request ID to every request and logs request/outcome in the app channel."""
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    RequestContext.set_request_id(request_id)
    start = time.perf_counter()
    response: Optional[Response] = None
    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        logger.exception(
            "Unhandled request error",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "error": type(exc).__name__,
            },
        )
        raise
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        status_code = getattr(response, "status_code", 0)
        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )
        if response is not None:
            response.headers["x-request-id"] = request_id
        RequestContext.clear_request_id()


# Suppress /v1/models access logs (probed by OpenCode CLI)
import logging as _logging


class _SkipModelsAccessLog(_logging.Filter):
    def filter(self, record: _logging.LogRecord) -> bool:
        return "/v1/models" not in record.getMessage()


_logging.getLogger("uvicorn.access").addFilter(_SkipModelsAccessLog())

# Include API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health/ready", tags=["Health"])
async def readiness_check():
    """Readiness check for Kubernetes/load balancers."""
    # TODO: Add DB/Redis connectivity checks
    return {"status": "ready"}


@app.get("/health/live", tags=["Health"])
async def liveness_check():
    """Liveness check."""
    return {"status": "alive"}