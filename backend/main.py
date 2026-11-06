"""
backend/main.py
FastAPI application entry point for OneContext.
Initializes lifespan services, mounts API routers, and configures error handling and CORS.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.memory import router as memory_router
from backend.api.projects import router as projects_router
from backend.config import get_settings
from backend.core.hindsight_client import HindsightWrapper
from backend.core.llm_client import LLMClient
from backend.core.memory_service import MemoryService
from backend.models.schemas import ErrorResponse, HealthResponse
from backend.storage import local_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("onecontext")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: initializes clients on startup and closes them on shutdown."""
    settings = get_settings()

    # 1. Initialize local SQLite metadata tables
    local_db.init_db()

    # 2. Initialize Core clients
    hindsight = HindsightWrapper(settings)
    llm = LLMClient(settings)

    # 3. Attach services to application state
    app.state.hindsight = hindsight
    app.state.llm = llm
    app.state.memory_service = MemoryService(
        hindsight=hindsight,
        llm=llm,
        db_module=local_db,
    )

    logger.info("OneContext backend initialized.")
    yield

    # 4. Graceful cleanup on shutdown
    logger.info("Shutting down OneContext backend...")
    hindsight.close()


app = FastAPI(
    title="OneContext API",
    description="Shared long-term project memory for AI agents, powered by Hindsight and Groq.",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(projects_router)
app.include_router(memory_router)


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check() -> HealthResponse:
    """Check system status."""
    return HealthResponse(
        status="ok",
        hindsight="connected",
        groq="connected",
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all error handler returning structured JSON without exposing internal tracebacks."""
    logger.error(f"Unhandled error processing {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="InternalServerError",
            detail=str(exc) or "An unexpected server error occurred.",
        ).model_dump(),
    )
