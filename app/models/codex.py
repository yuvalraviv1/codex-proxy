"""Codex-specific data models."""

from typing import Optional, Any, Dict
from pydantic import BaseModel


class CodexJsonEvent(BaseModel):
    """A single event from codex --json output."""

    type: str
    thread_id: Optional[str] = None
    item: Optional[Dict[str, Any]] = None
    usage: Optional[Dict[str, Any]] = None


class CodexUsage(BaseModel):
    """Token usage from codex."""

    input_tokens: int
    cached_input_tokens: int = 0
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens used."""
        return self.input_tokens + self.output_tokens


class CodexResponse(BaseModel):
    """Parsed response from codex CLI."""

    content: str
    usage: CodexUsage
    thread_id: Optional[str] = None
