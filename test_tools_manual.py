#!/usr/bin/env python3
"""Manual testing script for tools/functions support.

This script tests the tool calling functionality with the OpenAI Python client.

Usage:
    1. Start the proxy server: python app/main.py
    2. Run this script: python test_tools_manual.py

Requirements:
    pip install openai
"""

import json
from openai import OpenAI


def main():
    """Run manual tests for tool calling."""

    # Configure client to use local proxy
    client = OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="test-key"  # Replace with your configured API key
    )

    # Define tools
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name, e.g. 'San Francisco'"
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "description": "Temperature unit"
                        }
                    },
                    "required": ["location"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "Perform a mathematical calculation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Mathematical expression to evaluate, e.g. '2 + 2'"
                        }
                    },
                    "required": ["expression"]
                }
            }
        }
    ]

    print("=" * 70)
    print("Testing Tool Calling Support - Codex Proxy")
    print("=" * 70)

    # Test 1: Non-streaming with tools
    print("\n[Test 1] Non-streaming request with tools")
    print("-" * 70)

    try:
        response = client.chat.completions.create(
            model="codex-local",
            messages=[
                {"role": "user", "content": "What's the weather like in San Francisco?"}
            ],
            tools=tools
        )

        print(f"✓ Request successful")
        print(f"  Finish reason: {response.choices[0].finish_reason}")
        print(f"  Message content: {response.choices[0].message.content}")

        if response.choices[0].message.tool_calls:
            print(f"  Tool calls: {len(response.choices[0].message.tool_calls)}")
            for tc in response.choices[0].message.tool_calls:
                print(f"    - {tc.function.name}({tc.function.arguments})")
        else:
            print("  Tool calls: None")

    except Exception as e:
        print(f"✗ Test failed: {e}")

    # Test 2: Multi-turn conversation with tool result
    print("\n[Test 2] Multi-turn conversation with tool result")
    print("-" * 70)

    try:
        # First turn - request
        response1 = client.chat.completions.create(
            model="codex-local",
            messages=[
                {"role": "user", "content": "Calculate 123 * 456"}
            ],
            tools=tools
        )

        print(f"✓ First turn successful")
        print(f"  Finish reason: {response1.choices[0].finish_reason}")

        if response1.choices[0].message.tool_calls:
            print(f"  Tool call requested: {response1.choices[0].message.tool_calls[0].function.name}")

            # Simulate tool execution
            tool_call = response1.choices[0].message.tool_calls[0]

            # Second turn - with tool result
            messages = [
                {"role": "user", "content": "Calculate 123 * 456"},
                response1.choices[0].message,
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": "calculate",
                    "content": json.dumps({"result": 56088})
                }
            ]

            response2 = client.chat.completions.create(
                model="codex-local",
                messages=messages,
                tools=tools
            )

            print(f"✓ Second turn successful")
            print(f"  Final response: {response2.choices[0].message.content}")
        else:
            print("  No tool call was made")

    except Exception as e:
        print(f"✗ Test failed: {e}")

    # Test 3: Streaming with tools
    print("\n[Test 3] Streaming request with tools")
    print("-" * 70)

    try:
        stream = client.chat.completions.create(
            model="codex-local",
            messages=[
                {"role": "user", "content": "Get the weather in Tokyo"}
            ],
            tools=tools,
            stream=True
        )

        print("✓ Streaming started")
        print("  Stream content: ", end="", flush=True)

        has_tool_calls = False
        for chunk in stream:
            delta = chunk.choices[0].delta

            if delta.content:
                print(delta.content, end="", flush=True)

            if delta.tool_calls:
                has_tool_calls = True
                for tc in delta.tool_calls:
                    print(f"\n  Tool call: {tc.function.name}({tc.function.arguments})")

        print()
        print(f"  Had tool calls: {has_tool_calls}")

    except Exception as e:
        print(f"✗ Test failed: {e}")

    # Test 4: Request without tools (baseline)
    print("\n[Test 4] Request without tools (baseline)")
    print("-" * 70)

    try:
        response = client.chat.completions.create(
            model="codex-local",
            messages=[
                {"role": "user", "content": "Say hello!"}
            ]
            # No tools parameter
        )

        print(f"✓ Request successful")
        print(f"  Finish reason: {response.choices[0].finish_reason}")
        print(f"  Content: {response.choices[0].message.content}")

    except Exception as e:
        print(f"✗ Test failed: {e}")

    print("\n" + "=" * 70)
    print("Testing complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
