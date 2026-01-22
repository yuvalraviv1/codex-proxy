"""CLI entry point for codex-proxy."""

import sys
import logging


def main():
    """Main entry point for the CLI Proxy."""
    import uvicorn
    from app.config import settings

    # Configure logging
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger = logging.getLogger(__name__)

    # Parse simple command-line arguments
    host = settings.host
    port = settings.port

    # Check for --help
    if "--help" in sys.argv or "-h" in sys.argv:
        print("""
CLI Proxy
=========

OpenAI-compatible API proxy for Codex and OpenCode CLIs.

Usage:
  codex-proxy [options]

Options:
  -h, --help          Show this help message
  --host HOST         Bind to this host (default: from .env or 0.0.0.0)
  --port PORT         Bind to this port (default: from .env or 8000)
  --reload            Enable auto-reload on code changes

Supported Backends:
  - Codex CLI (https://github.com/openai/codex) -> model: codex-local
  - OpenCode CLI (https://opencode.ai) -> model: opencode-local

Configuration:
  Set environment variables in .env file:

  Server:
    - API_KEYS: Comma-separated list of valid API keys
    - HOST: Server bind address (default: 0.0.0.0)
    - PORT: Server port (default: 8000)
    - LOG_LEVEL: Logging level (debug/info/warning/error)

  Codex:
    - CODEX_PATH: Path to codex binary (empty = auto-detect)
    - CODEX_MODEL: Codex model to use (default: o3)
    - CODEX_SANDBOX: Sandbox mode (default: read-only)

  OpenCode:
    - OPENCODE_PATH: Path to opencode binary (empty = auto-detect)
    - OPENCODE_MODEL: OpenCode model (default: anthropic/claude-sonnet-4)

Examples:
  codex-proxy
  codex-proxy --host 127.0.0.1 --port 8080
  codex-proxy --reload

For more information, visit: https://github.com/yuvalraviv1/codex-proxy
""")
        sys.exit(0)

    # Parse arguments
    reload_enabled = "--reload" in sys.argv

    try:
        host_idx = sys.argv.index("--host")
        if host_idx + 1 < len(sys.argv):
            host = sys.argv[host_idx + 1]
    except (ValueError, IndexError):
        pass

    try:
        port_idx = sys.argv.index("--port")
        if port_idx + 1 < len(sys.argv):
            port = int(sys.argv[port_idx + 1])
    except (ValueError, IndexError):
        pass

    logger.info(f"Starting CLI Proxy on {host}:{port}")
    logger.info(f"Reload enabled: {reload_enabled}")

    # Run the server
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        log_level=settings.log_level
    )


if __name__ == "__main__":
    main()
