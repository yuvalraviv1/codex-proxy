"""Execute OpenCode CLI commands and parse output."""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional, List

from app.models.codex import CodexJsonEvent, CodexResponse, CodexUsage
from app.services.base_executor import BaseExecutor
from app.config import settings

logger = logging.getLogger(__name__)


class OpenCodeExecutor(BaseExecutor):
    """Executes OpenCode CLI commands and parses output."""

    async def execute_streaming(
        self,
        prompt: str,
        model: Optional[str] = None
    ) -> AsyncGenerator[CodexJsonEvent, None]:
        """
        Execute opencode with --format json and yield JSON events.

        Args:
            prompt: The prompt to send to opencode
            model: Optional model override

        Yields:
            CodexJsonEvent objects parsed from JSON output
        """
        cmd = self._build_command(prompt, model, streaming=True)
        logger.info(f"Executing opencode (streaming): {' '.join(cmd[:3])}...")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Read stdout line by line for JSON events
        while True:
            line = await process.stdout.readline()
            if not line:
                break

            line_str = line.decode().strip()
            if not line_str:
                continue

            try:
                event_data = json.loads(line_str)
                # Map OpenCode event format to our internal format
                event = self._map_opencode_event(event_data)
                if event:
                    yield event
            except json.JSONDecodeError:
                # Skip non-JSON lines (like startup messages)
                logger.debug(f"Skipping non-JSON line: {line_str}")
                continue
            except Exception as e:
                logger.warning(f"Failed to parse event: {e}")
                continue

        await process.wait()

        if process.returncode != 0:
            stderr = await process.stderr.read()
            error_msg = stderr.decode()
            logger.error(f"OpenCode execution failed: {error_msg}")
            raise RuntimeError(f"OpenCode execution failed: {error_msg}")

    async def execute_non_streaming(
        self,
        prompt: str,
        model: Optional[str] = None
    ) -> CodexResponse:
        """
        Execute opencode with --format json and parse complete output.

        Args:
            prompt: The prompt to send to opencode
            model: Optional model override

        Returns:
            CodexResponse with content and usage
        """
        # Always use JSON format for reliable parsing
        cmd = self._build_command(prompt, model, streaming=True)
        logger.info(f"Executing opencode (non-streaming): {' '.join(cmd[:3])}...")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode()
            logger.error(f"OpenCode execution failed: {error_msg}")
            raise RuntimeError(f"OpenCode execution failed: {error_msg}")

        # Parse JSONL output
        output = stdout.decode()
        logger.debug(f"Raw opencode output (first 500 chars): {output[:500]}")
        return self._parse_jsonl_output(output)

    def _build_command(
        self,
        prompt: str,
        model: Optional[str],
        streaming: bool
    ) -> List[str]:
        """Build opencode command with appropriate flags."""
        # Map our proxy model name to the actual opencode model
        actual_model = settings.opencode_model
        if model and model != "opencode-local":
            # If a specific model other than our proxy name is requested, use it
            actual_model = model

        cmd = [
            settings.resolved_opencode_path,
            "run",
            prompt,
            "--model", actual_model,
            "--format", "json",  # Always use JSON for reliable parsing
        ]

        return cmd

    def _map_opencode_event(self, event_data: dict) -> Optional[CodexJsonEvent]:
        """
        Map OpenCode JSON event to our internal CodexJsonEvent format.

        OpenCode event format:
        - type: "step_start" -> start of processing
        - type: "text" -> part.text contains the content
        - type: "step_finish" -> end with part.tokens for usage
        - type: "error" -> error.data.message contains error
        """
        event_type = event_data.get("type", "")
        part = event_data.get("part", {})

        # Handle text events - this is where the actual content is
        if event_type == "text":
            text_content = part.get("text", "")
            if text_content:
                return CodexJsonEvent(
                    type="message",
                    content=text_content
                )

        # Handle step_finish as done event
        elif event_type == "step_finish":
            return CodexJsonEvent(type="done")

        # Handle errors
        elif event_type == "error":
            error_info = event_data.get("error", {})
            error_data = error_info.get("data", {})
            error_msg = error_data.get("message", error_info.get("name", "Unknown error"))
            return CodexJsonEvent(
                type="error",
                error=error_msg
            )

        # Skip step_start and other event types
        elif event_type in ("step_start",):
            logger.debug(f"Skipping OpenCode event type: {event_type}")
            return None

        # Unknown event type - log and skip
        logger.debug(f"Unknown OpenCode event type: {event_type}")
        return None

    def _parse_jsonl_output(self, output: str) -> CodexResponse:
        """
        Parse OpenCode JSONL output format.

        Args:
            output: Raw JSONL output from opencode

        Returns:
            CodexResponse with content and usage
        """
        content_parts = []
        input_tokens = 0
        output_tokens = 0

        for line in output.strip().split('\n'):
            if not line:
                continue

            try:
                event = json.loads(line)
                event_type = event.get("type", "")
                part = event.get("part", {})

                # Extract text content
                if event_type == "text":
                    text = part.get("text", "")
                    if text:
                        content_parts.append(text)

                # Extract token usage from step_finish
                elif event_type == "step_finish":
                    tokens = part.get("tokens", {})
                    input_tokens = tokens.get("input", 0)
                    output_tokens = tokens.get("output", 0)

                # Handle errors
                elif event_type == "error":
                    error_info = event.get("error", {})
                    error_data = error_info.get("data", {})
                    error_msg = error_data.get("message", error_info.get("name", "Unknown error"))
                    raise RuntimeError(f"OpenCode error: {error_msg}")

            except json.JSONDecodeError:
                logger.debug(f"Skipping non-JSON line: {line}")
                continue

        content = "".join(content_parts)

        usage = CodexUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )

        logger.info(f"Parsed response: {len(content)} chars, {input_tokens + output_tokens} tokens")

        return CodexResponse(
            content=content,
            usage=usage
        )
