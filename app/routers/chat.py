"""Chat completions endpoint."""

import logging
from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.models.openai import ChatCompletionRequest, ChatCompletionResponse, Message
from app.services.codex_executor import CodexExecutor
from app.services.response_mapper import ResponseMapper
from app.auth import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/chat", tags=["chat"])
executor = CodexExecutor()
mapper = ResponseMapper()


@router.post("/completions", response_model=None)
async def create_chat_completion(
    request: ChatCompletionRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Create a chat completion using codex CLI.

    Supports both streaming and non-streaming modes.

    Args:
        request: Chat completion request
        api_key: Validated API key from dependency

    Returns:
        ChatCompletionResponse (non-streaming) or StreamingResponse (streaming)
    """
    # Build prompt from messages
    prompt = _build_prompt_from_messages(request.messages)
    logger.info(f"Chat completion request: stream={request.stream}, model={request.model}")

    try:
        if request.stream:
            # Streaming mode
            logger.debug("Starting streaming response")
            events = executor.execute_streaming(prompt, request.model)
            stream = mapper.create_streaming_response(events)

            return StreamingResponse(
                stream,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        else:
            # Non-streaming mode
            logger.debug("Starting non-streaming response")
            codex_response = await executor.execute_non_streaming(
                prompt,
                request.model
            )
            return mapper.create_non_streaming_response(codex_response)

    except RuntimeError as e:
        logger.error(f"Codex execution error: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


def _build_prompt_from_messages(messages: List[Message]) -> str:
    """
    Convert OpenAI messages format to a single prompt string.

    Strategy: Concatenate all messages with role prefixes.

    Args:
        messages: List of messages

    Returns:
        Combined prompt string
    """
    parts = []
    for msg in messages:
        if msg.role == "system":
            parts.append(f"System: {msg.content}")
        elif msg.role == "user":
            parts.append(f"User: {msg.content}")
        elif msg.role == "assistant":
            parts.append(f"Assistant: {msg.content}")

    return "\n\n".join(parts)
