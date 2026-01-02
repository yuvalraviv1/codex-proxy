"""Map codex responses to OpenAI API format."""

import re
import time
import uuid
import logging
from typing import AsyncGenerator, List, Optional, Tuple

from app.models.openai import (
    ChatCompletionResponse,
    ChatCompletionStreamResponse,
    Choice,
    StreamChoice,
    ChoiceDelta,
    Message,
    Usage,
    ToolCall,
    FunctionCallDetails
)
from app.models.codex import CodexJsonEvent, CodexResponse

logger = logging.getLogger(__name__)


def _extract_tool_calls_from_text(text: str) -> Tuple[Optional[List[ToolCall]], Optional[str]]:
    """
    Parse function calls from codex text response.

    Looks for JSON patterns like: {"name": "tool_name", "arguments": {...}}

    Args:
        text: The response text from codex

    Returns:
        Tuple of (tool_calls list or None, remaining text or None)
    """
    # Pattern to match function call JSON
    # Matches: {"name": "...", "arguments": {...}}
    pattern = r'\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{[^}]*\})\s*\}'

    matches = list(re.finditer(pattern, text, re.DOTALL))

    if not matches:
        return None, text

    tool_calls = []
    for match in matches:
        name = match.group(1)
        arguments = match.group(2)

        tool_call = ToolCall(
            id=f"call_{uuid.uuid4().hex[:24]}",
            type="function",
            function=FunctionCallDetails(
                name=name,
                arguments=arguments
            )
        )
        tool_calls.append(tool_call)

    # Remove tool call JSON from text
    remaining_text = re.sub(pattern, "", text, flags=re.DOTALL).strip()

    # Clean up extra whitespace
    remaining_text = re.sub(r'\n{3,}', '\n\n', remaining_text)

    return tool_calls, remaining_text if remaining_text else None


class ResponseMapper:
    """Maps codex responses to OpenAI API format."""

    @staticmethod
    def create_non_streaming_response(
        codex_response: CodexResponse,
        tools_enabled: bool = False,
        request_id: Optional[str] = None
    ) -> ChatCompletionResponse:
        """
        Convert CodexResponse to OpenAI ChatCompletionResponse.

        Args:
            codex_response: The parsed codex response
            tools_enabled: Whether tools are enabled for this request
            request_id: Optional request ID (generated if not provided)

        Returns:
            ChatCompletionResponse in OpenAI format
        """
        chat_id = request_id or f"chatcmpl-{uuid.uuid4().hex[:24]}"

        tool_calls = None
        finish_reason = "stop"
        content = codex_response.content

        # Extract tool calls if tools are enabled
        if tools_enabled:
            tool_calls, remaining_content = _extract_tool_calls_from_text(content)
            if tool_calls:
                finish_reason = "tool_calls"
                content = remaining_content
                logger.info(f"Extracted {len(tool_calls)} tool call(s) from response")

        return ChatCompletionResponse(
            id=chat_id,
            created=int(time.time()),
            model="codex-local",
            choices=[
                Choice(
                    index=0,
                    message=Message(
                        role="assistant",
                        content=content,
                        tool_calls=tool_calls
                    ),
                    finish_reason=finish_reason
                )
            ],
            usage=Usage(
                prompt_tokens=codex_response.usage.input_tokens,
                completion_tokens=codex_response.usage.output_tokens,
                total_tokens=codex_response.usage.total_tokens
            )
        )

    @staticmethod
    async def create_streaming_response(
        events: AsyncGenerator[CodexJsonEvent, None],
        tools_enabled: bool = False,
        request_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Convert codex JSONL events to OpenAI SSE stream.

        Args:
            events: Async generator of codex JSON events
            tools_enabled: Whether tools are enabled for this request
            request_id: Optional request ID (generated if not provided)

        Yields:
            SSE-formatted strings: "data: {json}\n\n"
        """
        chat_id = request_id or f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())

        # Track state
        first_chunk = True
        usage_data = None
        has_tool_calls = False

        async for event in events:
            if event.type == "item.completed" and event.item:
                item_type = event.item.get("type")

                # Handle function_call items if tools are enabled
                if item_type == "function_call" and tools_enabled:
                    func_call = event.extract_function_call()
                    if func_call:
                        has_tool_calls = True

                        tool_call = ToolCall(
                            id=func_call.call_id,
                            type="function",
                            function=FunctionCallDetails(
                                name=func_call.name,
                                arguments=func_call.arguments
                            )
                        )

                        logger.info(f"Streaming tool call: {func_call.name}")

                        # Stream tool call as delta
                        chunk = ChatCompletionStreamResponse(
                            id=chat_id,
                            created=created,
                            model="codex-local",
                            choices=[
                                StreamChoice(
                                    index=0,
                                    delta=ChoiceDelta(
                                        role="assistant" if first_chunk else None,
                                        tool_calls=[tool_call]
                                    ),
                                    finish_reason=None
                                )
                            ]
                        )
                        first_chunk = False
                        yield f"data: {chunk.model_dump_json()}\n\n"

                # Stream agent_message items (skip reasoning)
                elif item_type == "agent_message":
                    text = event.item.get("text", "")

                    if first_chunk:
                        # First chunk includes role
                        chunk = ChatCompletionStreamResponse(
                            id=chat_id,
                            created=created,
                            model="codex-local",
                            choices=[
                                StreamChoice(
                                    index=0,
                                    delta=ChoiceDelta(
                                        role="assistant",
                                        content=text
                                    ),
                                    finish_reason=None
                                )
                            ]
                        )
                        first_chunk = False
                    else:
                        # Subsequent chunks only have content
                        chunk = ChatCompletionStreamResponse(
                            id=chat_id,
                            created=created,
                            model="codex-local",
                            choices=[
                                StreamChoice(
                                    index=0,
                                    delta=ChoiceDelta(content=text),
                                    finish_reason=None
                                )
                            ]
                        )

                    yield f"data: {chunk.model_dump_json()}\n\n"

            elif event.type == "turn.completed" and event.usage:
                usage_data = event.usage
                logger.info(f"Turn completed with usage: {usage_data}")

        # Determine finish reason
        finish_reason = "tool_calls" if has_tool_calls else "stop"

        # Send final chunk with finish_reason
        final_chunk = ChatCompletionStreamResponse(
            id=chat_id,
            created=created,
            model="codex-local",
            choices=[
                StreamChoice(
                    index=0,
                    delta=ChoiceDelta(),
                    finish_reason=finish_reason
                )
            ]
        )
        yield f"data: {final_chunk.model_dump_json()}\n\n"

        # Send [DONE] marker
        yield "data: [DONE]\n\n"
