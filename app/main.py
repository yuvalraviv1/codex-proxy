"""FastAPI application entry point."""

import logging
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import chat, models
from app.config import settings
from app.models.openai import ErrorResponse, ErrorDetail

# Configure logging
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Codex OpenAI Proxy")
    validate_codex()
    logger.info(f"Server configured: host={settings.host}, port={settings.port}")
    logger.info(f"Codex: path={settings.codex_path}, model={settings.codex_model}")
    logger.info(f"API keys configured: {len(settings.api_keys_set)}")

    yield

    # Shutdown
    logger.info("Shutting down Codex OpenAI Proxy")


def validate_codex():
    """Verify codex CLI is accessible."""
    if not shutil.which(settings.codex_path):
        error_msg = (
            f"Codex CLI not found at {settings.codex_path}. "
            "Please install codex or update CODEX_PATH environment variable."
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    logger.info(f"Codex CLI found at {settings.codex_path}")


# Create FastAPI application
app = FastAPI(
    title="Codex OpenAI Proxy",
    description="OpenAI-compatible API proxy for local codex CLI",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom exception handler for OpenAI-compatible error responses
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle exceptions with OpenAI-compatible error format."""
    logger.exception(f"Unhandled exception: {exc}")

    error_response = ErrorResponse(
        error=ErrorDetail(
            message=str(exc),
            type="internal_error",
            code="500"
        )
    )

    return JSONResponse(
        status_code=500,
        content=error_response.model_dump()
    )


# Include routers
app.include_router(chat.router)
app.include_router(models.router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "codex_path": settings.codex_path,
        "model": settings.codex_model
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Codex OpenAI Proxy",
        "version": "1.0.0",
        "description": "OpenAI-compatible API proxy for local codex CLI",
        "endpoints": {
            "health": "/health",
            "models": "/v1/models",
            "chat_completions": "/v1/chat/completions"
        },
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level
    )
