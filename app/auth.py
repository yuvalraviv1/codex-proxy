"""API key authentication."""

import logging
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
    """
    Verify API key from Authorization header.

    Args:
        credentials: HTTP authorization credentials

    Returns:
        The validated API key

    Raises:
        HTTPException: If API key is invalid or missing
    """
    # If no credentials provided
    if credentials is None:
        if not settings.api_keys_set:
            # No API keys configured - allow all requests (dev mode)
            logger.warning("No API key provided, but none configured (dev mode)")
            return "dev-mode"
        else:
            raise HTTPException(
                status_code=401,
                detail="Missing API key",
                headers={"WWW-Authenticate": "Bearer"}
            )

    # If no API keys configured, allow all requests
    if not settings.api_keys_set:
        logger.info("API key validation skipped (no keys configured)")
        return credentials.credentials

    # Validate against configured API keys
    if credentials.credentials not in settings.api_keys_set:
        logger.warning(f"Invalid API key attempted: {credentials.credentials[:10]}...")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"}
        )

    logger.debug("API key validated successfully")
    return credentials.credentials
