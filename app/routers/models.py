"""Models listing endpoint."""

import shutil
from fastapi import APIRouter, Depends

from app.models.openai import Model, ModelList
from app.auth import verify_api_key
from app.config import settings

router = APIRouter(prefix="/v1", tags=["models"])


@router.get("/models", response_model=ModelList)
async def list_models(
    api_key: str = Depends(verify_api_key)
) -> ModelList:
    """
    List available models.

    Returns:
        List containing available CLI backend models
    """
    models = []

    # Check if Codex CLI is available
    codex_path = settings.resolved_codex_path
    if shutil.which(codex_path):
        models.append(
            Model(
                id="codex-local",
                object="model",
                owned_by="codex-proxy"
            )
        )

    # Check if OpenCode CLI is available
    opencode_path = settings.resolved_opencode_path
    if shutil.which(opencode_path):
        models.append(
            Model(
                id="opencode-local",
                object="model",
                owned_by="codex-proxy"
            )
        )

    return ModelList(data=models)
