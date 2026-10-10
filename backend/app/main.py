"""SelfHealOps FastAPI application entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.router import api_router
from app.config import get_settings
from app.database import init_db
from app.services.monitoring import start_scheduler_if_enabled, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("selfhealops")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    start_scheduler_if_enabled()
    logger.info("SelfHealOps backend started (v%s).", __version__)
    try:
        yield
    finally:
        stop_scheduler()
        logger.info("SelfHealOps backend shutting down.")


settings = get_settings()

app = FastAPI(
    title="SelfHealOps API",
    description=(
        "Agentic AI-based self-healing DevOps automation. Monitors GitHub Actions "
        "workflows, diagnoses failures, proposes allowlisted remediations, enforces "
        "human approval, executes and verifies results."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit():
        if int(content_length) > settings.max_request_body_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large.", "code": "payload_too_large"},
            )
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error.", "code": "validation_error", "errors": exc.errors()},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": f"http_{exc.status_code}"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error.", "code": "internal_error"},
    )


@app.get("/health", tags=["health"], summary="Root health check")
def root_health() -> dict:
    from app.database import get_db  # noqa: F401

    return {"status": "ok", "version": __version__}


app.include_router(api_router)
