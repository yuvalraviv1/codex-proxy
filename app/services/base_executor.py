"""Base executor interface for CLI backends."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional

from app.models.codex import CodexJsonEvent, CodexResponse


class BaseExecutor(ABC):
    """Abstract base class for CLI executors (Codex, OpenCode, etc.)."""

    @abstractmethod
    async def execute_streaming(
        self,
        prompt: str,
        model: Optional[str] = None
    ) -> AsyncGenerator[CodexJsonEvent, None]:
        """
        Execute CLI with streaming output.

        Args:
            prompt: The prompt to send
            model: Optional model override

        Yields:
            CodexJsonEvent objects parsed from JSON output
        """
        pass

    @abstractmethod
    async def execute_non_streaming(
        self,
        prompt: str,
        model: Optional[str] = None
    ) -> CodexResponse:
        """
        Execute CLI without streaming.

        Args:
            prompt: The prompt to send
            model: Optional model override

        Returns:
            CodexResponse with content and usage
        """
        pass
