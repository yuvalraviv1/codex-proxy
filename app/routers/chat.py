"""Chat completions endpoint."""

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.models.openai import (
    ChatCompletionRequest,
    Message,
    ToolDefinition
)
from app.services.base_executor import BaseExecutor
from app.services.codex_executor import CodexExecutor
from app.services.opencode_executor import OpenCodeExecutor
from app.services.response_mapper import ResponseMapper
from app.auth import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/chat", tags=["chat"])

# Initialize executors
codex_executor = CodexExecutor()
opencode_executor = OpenCodeExecutor()
mapper = ResponseMapper()


def get_executor(model: str) -> BaseExecutor:
    """
    Get the appropriate executor based on the model name.

    Args:
        model: The model name from the request

    Returns:
        The appropriate executor instance
    """
    # Route to OpenCode for opencode-local or provider/model format
    if (model == "opencode-local" or
        model.startswith("anthropic/") or
        model.startswith("openai/") or
        model.startswith("opencode/")):
        return opencode_executor
    # Default to codex for "codex-local" or any other model
    return codex_executor


@router.post("/completions", response_model=None)
async def create_chat_completion(
    request: ChatCompletionRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Create a chat completion using the appropriate CLI backend.

    Supports both streaming and non-streaming modes.
    Routes to Codex or OpenCode based on the model name.

    Args:
        request: Chat completion request
        api_key: Validated API key from dependency

    Returns:
        ChatCompletionResponse (non-streaming) or StreamingResponse (streaming)
    """
    # Get the appropriate executor for this model
    executor = get_executor(request.model)
    backend_name = "OpenCode" if isinstance(executor, OpenCodeExecutor) else "Codex"

    # Build prompt from messages with tools
    prompt = _build_prompt_from_messages(request.messages, request.tools)
    tools_enabled = bool(request.tools)

    logger.info(
        f"Chat completion request: backend={backend_name}, stream={request.stream}, "
        f"model={request.model}, tools={len(request.tools) if request.tools else 0}"
    )

    try:
        if request.stream:
            # Streaming mode
            logger.debug(f"Starting streaming response via {backend_name}")
            events = executor.execute_streaming(prompt, request.model)
            stream = mapper.create_streaming_response(events, tools_enabled=tools_enabled)

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
            logger.debug(f"Starting non-streaming response via {backend_name}")
            response = await executor.execute_non_streaming(
                prompt,
                request.model
            )
            return mapper.create_non_streaming_response(response, tools_enabled=tools_enabled)

    except RuntimeError as e:
        logger.error(f"{backend_name} execution error: {e}")
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


def _format_tools_as_prompt(tools: List[ToolDefinition]) -> str:
    """
    Convert tool definitions to natural language documentation for the prompt.

    Args:
        tools: List of tool definitions

    Returns:
        Formatted tools documentation
    """
    if not tools:
        return ""

    lines = ["You have access to the following tools:\n"]

    for tool in tools:
        func = tool.function
        lines.append(f"- {func.name}: {func.description or 'No description provided'}")

        if func.parameters:
            # Format parameters as JSON for clarity
            params_str = json.dumps(func.parameters, indent=2)
            lines.append(f"  Parameters: {params_str}")

    lines.append("\nTo use a tool, respond with a JSON object in this exact format:")
    lines.append('{"name": "tool_name", "arguments": {...}}')
    lines.append("\nYou can include explanation text along with or after the JSON.")

    return "\n".join(lines)


def _build_prompt_from_messages(
    messages: List[Message],
    tools: Optional[List[ToolDefinition]] = None
) -> str:
    """
    Convert OpenAI messages format to a single prompt string with tools context.

    Strategy:
    1. Add tool definitions as documentation (if provided)
    2. Process messages including tool calls and results
    3. Concatenate with role prefixes

    Args:
        messages: List of messages
        tools: Optional list of tool definitions

    Returns:
        Combined prompt string
    """
    parts = []

    # Add tools documentation at the beginning
    if tools:
        tools_prompt = _format_tools_as_prompt(tools)
        parts.append(tools_prompt)
        parts.append("")  # Blank line separator

    # Process messages
    for msg in messages:
        if msg.role == "system":
            parts.append(f"System: {msg.content}")
        elif msg.role == "user":
            parts.append(f"User: {msg.content}")
        elif msg.role == "assistant":
            # Handle assistant messages with tool calls
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    parts.append(
                        f"Assistant called tool: {tc.function.name}"
                        f"(arguments: {tc.function.arguments})"
                    )
            elif msg.content:
                parts.append(f"Assistant: {msg.content}")
        elif msg.role == "tool":
            # Tool result from previous turn
            parts.append(
                f"Tool {msg.name} (call_id: {msg.tool_call_id}) returned: "
                f"{msg.content}"
            )

    return "\n\n".join(parts)
