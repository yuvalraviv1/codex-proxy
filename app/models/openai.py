"""OpenAI API compatible data models."""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


# Tool calling models
class FunctionDefinition(BaseModel):
    """Function definition for tool calling."""

    name: str = Field(..., description="Function name")
    description: Optional[str] = Field(None, description="Function description")
    parameters: Optional[Dict[str, Any]] = Field(None, description="JSON Schema for parameters")
    strict: Optional[bool] = Field(None, description="Whether to enforce strict schema validation")


class ToolDefinition(BaseModel):
    """Tool definition for function calling."""

    type: Literal["function"] = Field(default="function", description="Tool type")
    function: FunctionDefinition


class FunctionCallDetails(BaseModel):
    """Details of a function call made by the assistant."""

    name: str = Field(..., description="Function name")
    arguments: str = Field(..., description="Function arguments as JSON string")


class ToolCall(BaseModel):
    """A tool call made by the assistant."""

    id: str = Field(..., description="Unique ID for this tool call")
    type: Literal["function"] = Field(default="function", description="Tool call type")
    function: FunctionCallDetails


# Message models
class Message(BaseModel):
    """Chat message with role and content."""

    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = Field(None, description="Tool calls made by assistant")
    tool_call_id: Optional[str] = Field(None, description="ID of tool call this message responds to")
    name: Optional[str] = Field(None, description="Name of the tool for tool messages")


class ChatCompletionRequest(BaseModel):
    """Request to create a chat completion."""

    model: str = Field(default="codex-local", description="Model to use")
    messages: List[Message] = Field(..., description="List of messages in the conversation")
    stream: bool = Field(default=False, description="Whether to stream the response")
    temperature: Optional[float] = Field(default=None, ge=0, le=2, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=None, gt=0, description="Maximum tokens to generate")
    top_p: Optional[float] = Field(default=None, ge=0, le=1, description="Nucleus sampling parameter")
    n: Optional[int] = Field(default=1, description="Number of completions to generate")
    stop: Optional[List[str]] = Field(default=None, description="Stop sequences")
    presence_penalty: Optional[float] = Field(default=None, ge=-2, le=2)
    frequency_penalty: Optional[float] = Field(default=None, ge=-2, le=2)
    tools: Optional[List[ToolDefinition]] = Field(None, description="Available tools for function calling")
    tool_choice: Optional[Union[Literal["none", "auto"], Dict[str, Any]]] = Field(
        None, description="Controls which tool is called"
    )


class Usage(BaseModel):
    """Token usage information."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Choice(BaseModel):
    """A chat completion choice."""

    index: int
    message: Message
    finish_reason: Literal["stop", "length", "error", "tool_calls"]


class ChatCompletionResponse(BaseModel):
    """Response from chat completion."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str = "codex-local"
    choices: List[Choice]
    usage: Usage


# Streaming models
class ChoiceDelta(BaseModel):
    """Delta update for streaming."""

    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


class StreamChoice(BaseModel):
    """A streaming choice with delta."""

    index: int
    delta: ChoiceDelta
    finish_reason: Optional[Literal["stop", "length", "error", "tool_calls"]] = None


class ChatCompletionStreamResponse(BaseModel):
    """Streaming response chunk."""

    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str = "codex-local"
    choices: List[StreamChoice]


# Models endpoint
class Model(BaseModel):
    """Model information."""

    id: str
    object: str = "model"
    created: int = 1700000000
    owned_by: str = "codex-proxy"


class ModelList(BaseModel):
    """List of available models."""

    object: str = "list"
    data: List[Model]


# Error responses
class ErrorDetail(BaseModel):
    """Error detail information."""

    message: str
    type: str
    param: Optional[str] = None
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response."""

    error: ErrorDetail
