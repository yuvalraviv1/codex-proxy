"""Models listing endpoint."""

from fastapi import APIRouter, Depends

from app.models.openai import Model, ModelList
from app.auth import verify_api_key

router = APIRouter(prefix="/v1", tags=["models"])


@router.get("/models", response_model=ModelList)
async def list_models(
    api_key: str = Depends(verify_api_key)
) -> ModelList:
    """
    List available models.

    Returns:
        List containing the codex-local model
    """
    return ModelList(
        data=[
            Model(
                id="codex-local",
                object="model",
                owned_by="codex-proxy"
            )
        ]
    )
