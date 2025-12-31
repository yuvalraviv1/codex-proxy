"""Execute codex CLI commands and parse output."""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional, List

from app.models.codex import CodexJsonEvent, CodexResponse, CodexUsage
from app.config import settings

logger = logging.getLogger(__name__)


class CodexExecutor:
    """Executes codex CLI commands and parses output."""

    async def execute_streaming(
        self,
        prompt: str,
        model: Optional[str] = None
    ) -> AsyncGenerator[CodexJsonEvent, None]:
        """
        Execute codex with --json flag and yield JSONL events.

        Args:
            prompt: The prompt to send to codex
            model: Optional model override

        Yields:
            CodexJsonEvent objects parsed from JSONL output
        """
        cmd = self._build_command(prompt, model, streaming=True)
        logger.info(f"Executing codex (streaming): {' '.join(cmd[:3])}...")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Read stdout line by line
        while True:
            line = await process.stdout.readline()
            if not line:
                break

            line_str = line.decode().strip()
            if not line_str:
                continue

            try:
                event_data = json.loads(line_str)
                event = CodexJsonEvent(**event_data)
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
            logger.error(f"Codex execution failed: {error_msg}")
            raise RuntimeError(f"Codex execution failed: {error_msg}")

    async def execute_non_streaming(
        self,
        prompt: str,
        model: Optional[str] = None
    ) -> CodexResponse:
        """
        Execute codex without --json and parse complete output.

        Args:
            prompt: The prompt to send to codex
            model: Optional model override

        Returns:
            CodexResponse with content and usage
        """
        cmd = self._build_command(prompt, model, streaming=False)
        logger.info(f"Executing codex (non-streaming): {' '.join(cmd[:3])}...")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode()
            logger.error(f"Codex execution failed: {error_msg}")
            raise RuntimeError(f"Codex execution failed: {error_msg}")

        # Codex outputs to stderr, not stdout
        output = stderr.decode()
        logger.debug(f"Raw codex output (first 500 chars): {output[:500]}")
        return self._parse_standard_output(output)

    def _build_command(
        self,
        prompt: str,
        model: Optional[str],
        streaming: bool
    ) -> List[str]:
        """Build codex command with appropriate flags."""
        # Map our proxy model name to the actual codex model
        actual_model = settings.codex_model
        if model and model != "codex-local":
            # If a specific model other than our proxy name is requested, use it
            actual_model = model

        cmd = [
            settings.codex_path,
            "e",
            prompt,
            "--skip-git-repo-check",
            "-m", actual_model,
            "-s", settings.codex_sandbox
        ]

        if settings.codex_full_auto:
            cmd.append("--full-auto")

        if streaming:
            cmd.append("--json")

        return cmd

    def _parse_standard_output(self, output: str) -> CodexResponse:
        """
        Parse standard codex output format.

        Expected format:
        --------
        ...metadata...
        --------
        user
        <prompt>
        ...
        thinking
        <reasoning>
        codex
        <response>
        tokens used
        <number>
        """
        lines = output.strip().split('\n')

        # Find sections
        content_lines = []
        in_response = False
        tokens = 0

        for i, line in enumerate(lines):
            stripped = line.strip()

            if stripped == "codex":
                in_response = True
                continue
            elif stripped == "tokens used":
                # Next line contains token count
                if i + 1 < len(lines):
                    try:
                        # Remove commas from number
                        token_str = lines[i + 1].strip().replace(',', '')
                        tokens = int(token_str)
                    except ValueError:
                        logger.warning(f"Failed to parse token count: {lines[i + 1]}")
                break
            elif in_response:
                content_lines.append(line)

        content = '\n'.join(content_lines).strip()

        # Estimate token split (rough heuristic: 80% input, 20% output)
        # This is a simplification since standard output doesn't separate them
        input_tokens = int(tokens * 0.8)
        output_tokens = tokens - input_tokens

        usage = CodexUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )

        logger.info(f"Parsed response: {len(content)} chars, {tokens} tokens")

        return CodexResponse(
            content=content,
            usage=usage
        )
