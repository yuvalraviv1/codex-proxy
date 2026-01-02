"""Codex-specific data models."""

from typing import Optional, Any, Dict
from pydantic import BaseModel


class CodexFunctionCall(BaseModel):
    """Parsed function call from codex --json output."""

    id: Optional[str] = None
    name: str
    arguments: str  # Raw JSON string
    call_id: str


class CodexJsonEvent(BaseModel):
    """A single event from codex --json output."""

    type: str
    thread_id: Optional[str] = None
    item: Optional[Dict[str, Any]] = None
    usage: Optional[Dict[str, Any]] = None

    def extract_function_call(self) -> Optional[CodexFunctionCall]:
        """Extract function call if this event contains one."""
        if not self.item or self.item.get('type') != 'function_call':
            return None

        try:
            return CodexFunctionCall(
                id=self.item.get('id'),
                name=self.item['name'],
                arguments=self.item['arguments'],
                call_id=self.item['call_id']
            )
        except (KeyError, TypeError):
            return None


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
