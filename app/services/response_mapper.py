"""Map codex responses to OpenAI API format."""

import time
import uuid
import logging
from typing import AsyncGenerator, Optional

from app.models.openai import (
    ChatCompletionResponse,
    ChatCompletionStreamResponse,
    Choice,
    StreamChoice,
    ChoiceDelta,
    Message,
    Usage
)
from app.models.codex import CodexJsonEvent, CodexResponse

logger = logging.getLogger(__name__)


class ResponseMapper:
    """Maps codex responses to OpenAI API format."""

    @staticmethod
    def create_non_streaming_response(
        codex_response: CodexResponse,
        request_id: Optional[str] = None
    ) -> ChatCompletionResponse:
        """
        Convert CodexResponse to OpenAI ChatCompletionResponse.

        Args:
            codex_response: The parsed codex response
            request_id: Optional request ID (generated if not provided)

        Returns:
            ChatCompletionResponse in OpenAI format
        """
        chat_id = request_id or f"chatcmpl-{uuid.uuid4().hex[:24]}"

        return ChatCompletionResponse(
            id=chat_id,
            created=int(time.time()),
            model="codex-local",
            choices=[
                Choice(
                    index=0,
                    message=Message(
                        role="assistant",
                        content=codex_response.content
                    ),
                    finish_reason="stop"
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
        request_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Convert codex JSONL events to OpenAI SSE stream.

        Args:
            events: Async generator of codex JSON events
            request_id: Optional request ID (generated if not provided)

        Yields:
            SSE-formatted strings: "data: {json}\n\n"
        """
        chat_id = request_id or f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())

        # Track state
        first_chunk = True
        usage_data = None

        async for event in events:
            if event.type == "item.completed" and event.item:
                item_type = event.item.get("type")

                # Only stream agent_message items (skip reasoning)
                if item_type == "agent_message":
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

        # Send final chunk with finish_reason
        final_chunk = ChatCompletionStreamResponse(
            id=chat_id,
            created=created,
            model="codex-local",
            choices=[
                StreamChoice(
                    index=0,
                    delta=ChoiceDelta(),
                    finish_reason="stop"
                )
            ]
        )
        yield f"data: {final_chunk.model_dump_json()}\n\n"

        # Send [DONE] marker
        yield "data: [DONE]\n\n"
