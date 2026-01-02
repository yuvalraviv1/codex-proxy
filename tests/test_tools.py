"""Tests for tool calling functionality."""

import pytest
from app.models.openai import (
    FunctionDefinition,
    ToolDefinition,
    Message,
    ToolCall,
    FunctionCallDetails
)
from app.models.codex import CodexResponse, CodexUsage
from app.routers.chat import _build_prompt_from_messages, _format_tools_as_prompt
from app.services.response_mapper import _extract_tool_calls_from_text, ResponseMapper


class TestToolFormatting:
    """Test tool formatting for prompts."""

    def test_format_single_tool(self):
        """Test formatting a single tool definition."""
        tools = [
            ToolDefinition(
                type="function",
                function=FunctionDefinition(
                    name="get_weather",
                    description="Get current weather for a location",
                    parameters={
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "City name"}
                        },
                        "required": ["location"]
                    }
                )
            )
        ]

        prompt = _format_tools_as_prompt(tools)

        assert "get_weather" in prompt
        assert "Get current weather for a location" in prompt
        assert "location" in prompt
        assert '{"name": "tool_name", "arguments": {...}}' in prompt

    def test_format_multiple_tools(self):
        """Test formatting multiple tool definitions."""
        tools = [
            ToolDefinition(
                type="function",
                function=FunctionDefinition(
                    name="get_weather",
                    description="Get weather",
                    parameters={"type": "object"}
                )
            ),
            ToolDefinition(
                type="function",
                function=FunctionDefinition(
                    name="calculate",
                    description="Perform calculation",
                    parameters={"type": "object"}
                )
            )
        ]

        prompt = _format_tools_as_prompt(tools)

        assert "get_weather" in prompt
        assert "calculate" in prompt
        assert prompt.count("- ") >= 2  # At least 2 tool bullet points

    def test_format_tool_without_description(self):
        """Test tool without description uses default."""
        tools = [
            ToolDefinition(
                type="function",
                function=FunctionDefinition(
                    name="my_tool",
                    description=None
                )
            )
        ]

        prompt = _format_tools_as_prompt(tools)

        assert "my_tool" in prompt
        assert "No description provided" in prompt


class TestMessageBuilding:
    """Test message building with tools."""

    def test_basic_messages_without_tools(self):
        """Test building prompt from basic messages."""
        messages = [
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="Hello!"),
            Message(role="assistant", content="Hi there!")
        ]

        prompt = _build_prompt_from_messages(messages)

        assert "System: You are a helpful assistant." in prompt
        assert "User: Hello!" in prompt
        assert "Assistant: Hi there!" in prompt

    def test_messages_with_tools(self):
        """Test building prompt with tools included."""
        messages = [
            Message(role="user", content="What's the weather?")
        ]

        tools = [
            ToolDefinition(
                type="function",
                function=FunctionDefinition(
                    name="get_weather",
                    description="Get weather"
                )
            )
        ]

        prompt = _build_prompt_from_messages(messages, tools)

        assert "get_weather" in prompt
        assert "User: What's the weather?" in prompt
        # Tools should appear before messages
        assert prompt.index("get_weather") < prompt.index("User:")

    def test_assistant_message_with_tool_calls(self):
        """Test building prompt with assistant tool calls."""
        messages = [
            Message(role="user", content="Check weather"),
            Message(
                role="assistant",
                tool_calls=[
                    ToolCall(
                        id="call_123",
                        type="function",
                        function=FunctionCallDetails(
                            name="get_weather",
                            arguments='{"location": "SF"}'
                        )
                    )
                ]
            )
        ]

        prompt = _build_prompt_from_messages(messages)

        assert "Assistant called tool: get_weather" in prompt
        assert "call_123" not in prompt  # ID not shown, just the call
        assert '{"location": "SF"}' in prompt

    def test_tool_result_message(self):
        """Test building prompt with tool result messages."""
        messages = [
            Message(role="user", content="Check weather"),
            Message(
                role="assistant",
                tool_calls=[
                    ToolCall(
                        id="call_123",
                        type="function",
                        function=FunctionCallDetails(
                            name="get_weather",
                            arguments='{"location": "SF"}'
                        )
                    )
                ]
            ),
            Message(
                role="tool",
                tool_call_id="call_123",
                name="get_weather",
                content='{"temp": 72, "condition": "sunny"}'
            )
        ]

        prompt = _build_prompt_from_messages(messages)

        assert "Tool get_weather (call_id: call_123) returned:" in prompt
        assert "sunny" in prompt


class TestToolCallExtraction:
    """Test extracting tool calls from text."""

    def test_extract_single_tool_call(self):
        """Test extracting a single tool call from response."""
        text = '''I'll check the weather for you.
{"name": "get_weather", "arguments": {"location": "San Francisco"}}
'''

        tool_calls, remaining = _extract_tool_calls_from_text(text)

        assert tool_calls is not None
        assert len(tool_calls) == 1
        assert tool_calls[0].function.name == "get_weather"
        assert tool_calls[0].function.arguments == '{"location": "San Francisco"}'
        assert tool_calls[0].id.startswith("call_")
        assert "I'll check the weather for you." in remaining

    def test_extract_multiple_tool_calls(self):
        """Test extracting multiple tool calls."""
        text = '''{"name": "get_weather", "arguments": {"location": "SF"}}
{"name": "calculate", "arguments": {"expr": "2+2"}}'''

        tool_calls, remaining = _extract_tool_calls_from_text(text)

        assert tool_calls is not None
        assert len(tool_calls) == 2
        assert tool_calls[0].function.name == "get_weather"
        assert tool_calls[1].function.name == "calculate"

    def test_extract_no_tool_calls(self):
        """Test text without tool calls returns None."""
        text = "Here is a regular response without any tool calls."

        tool_calls, remaining = _extract_tool_calls_from_text(text)

        assert tool_calls is None
        assert remaining == text

    def test_extract_with_whitespace(self):
        """Test extraction handles various whitespace."""
        text = '''{ "name" : "get_weather" , "arguments" : {"location":"NYC"} }'''

        tool_calls, remaining = _extract_tool_calls_from_text(text)

        assert tool_calls is not None
        assert len(tool_calls) == 1
        assert tool_calls[0].function.name == "get_weather"


class TestNonStreamingResponse:
    """Test non-streaming response with tools."""

    def test_response_without_tools(self):
        """Test creating response when tools not enabled."""
        codex_response = CodexResponse(
            content="Hello, how can I help you?",
            usage=CodexUsage(
                input_tokens=10,
                output_tokens=8,
                cached_input_tokens=0
            )
        )

        mapper = ResponseMapper()
        response = mapper.create_non_streaming_response(
            codex_response,
            tools_enabled=False
        )

        assert response.choices[0].message.content == "Hello, how can I help you?"
        assert response.choices[0].message.tool_calls is None
        assert response.choices[0].finish_reason == "stop"

    def test_response_with_tool_calls(self):
        """Test creating response with extracted tool calls."""
        codex_response = CodexResponse(
            content='Let me check that. {"name": "calculate", "arguments": {"expr": "2+2"}}',
            usage=CodexUsage(
                input_tokens=15,
                output_tokens=20,
                cached_input_tokens=0
            )
        )

        mapper = ResponseMapper()
        response = mapper.create_non_streaming_response(
            codex_response,
            tools_enabled=True
        )

        assert response.choices[0].message.tool_calls is not None
        assert len(response.choices[0].message.tool_calls) == 1
        assert response.choices[0].message.tool_calls[0].function.name == "calculate"
        assert response.choices[0].finish_reason == "tool_calls"
        # Text should be cleaned of the tool call JSON
        assert '"name"' not in response.choices[0].message.content

    def test_response_tools_enabled_but_no_calls(self):
        """Test tools enabled but no tool calls in response."""
        codex_response = CodexResponse(
            content="I don't need to use any tools for this.",
            usage=CodexUsage(
                input_tokens=20,
                output_tokens=10,
                cached_input_tokens=0
            )
        )

        mapper = ResponseMapper()
        response = mapper.create_non_streaming_response(
            codex_response,
            tools_enabled=True
        )

        assert response.choices[0].message.tool_calls is None
        assert response.choices[0].finish_reason == "stop"
        assert response.choices[0].message.content == "I don't need to use any tools for this."


class TestCodexFunctionCallExtraction:
    """Test CodexFunctionCall extraction from events."""

    def test_extract_valid_function_call(self):
        """Test extracting function call from event item."""
        from app.models.codex import CodexJsonEvent

        event = CodexJsonEvent(
            type="item.completed",
            item={
                "type": "function_call",
                "id": "item_123",
                "name": "get_weather",
                "arguments": '{"location": "NYC"}',
                "call_id": "call_abc123"
            }
        )

        func_call = event.extract_function_call()

        assert func_call is not None
        assert func_call.name == "get_weather"
        assert func_call.arguments == '{"location": "NYC"}'
        assert func_call.call_id == "call_abc123"
        assert func_call.id == "item_123"

    def test_extract_non_function_call_item(self):
        """Test that non-function-call items return None."""
        from app.models.codex import CodexJsonEvent

        event = CodexJsonEvent(
            type="item.completed",
            item={
                "type": "agent_message",
                "text": "Hello!"
            }
        )

        func_call = event.extract_function_call()

        assert func_call is None

    def test_extract_no_item(self):
        """Test event without item returns None."""
        from app.models.codex import CodexJsonEvent

        event = CodexJsonEvent(
            type="turn.completed",
            usage={"input_tokens": 10}
        )

        func_call = event.extract_function_call()

        assert func_call is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
