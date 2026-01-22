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
    logger.info("Starting CLI Proxy (Codex/OpenCode)")
    validate_cli_backends()
    logger.info(f"Server configured: host={settings.host}, port={settings.port}")
    logger.info(f"API keys configured: {len(settings.api_keys_set)}")

    yield

    # Shutdown
    logger.info("Shutting down CLI Proxy")


def validate_cli_backends():
    """Verify CLI backends are accessible."""
    codex_path = settings.resolved_codex_path
    opencode_path = settings.resolved_opencode_path

    codex_available = shutil.which(codex_path) is not None
    opencode_available = shutil.which(opencode_path) is not None

    if codex_available:
        logger.info(f"Codex CLI found at {codex_path} (model: {settings.codex_model})")
    else:
        logger.warning(f"Codex CLI not found at {codex_path} - codex-local model will not work")

    if opencode_available:
        logger.info(f"OpenCode CLI found at {opencode_path} (model: {settings.opencode_model})")
    else:
        logger.warning(f"OpenCode CLI not found at {opencode_path} - opencode-local model will not work")

    if not codex_available and not opencode_available:
        error_msg = (
            "No CLI backends found! Please install at least one of:\n"
            "  - Codex CLI: https://github.com/openai/codex\n"
            "  - OpenCode CLI: https://opencode.ai\n"
            "Or set CODEX_PATH / OPENCODE_PATH environment variables."
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)


# Create FastAPI application
app = FastAPI(
    title="CLI Proxy",
    description="OpenAI-compatible API proxy for Codex and OpenCode CLIs",
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
    codex_path = settings.resolved_codex_path
    opencode_path = settings.resolved_opencode_path

    return {
        "status": "healthy",
        "version": "1.0.0",
        "backends": {
            "codex": {
                "path": codex_path,
                "available": shutil.which(codex_path) is not None,
                "model": settings.codex_model
            },
            "opencode": {
                "path": opencode_path,
                "available": shutil.which(opencode_path) is not None,
                "model": settings.opencode_model
            }
        }
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "CLI Proxy",
        "version": "1.0.0",
        "description": "OpenAI-compatible API proxy for Codex and OpenCode CLIs",
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
