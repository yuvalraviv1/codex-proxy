# Codex OpenAI Proxy

A FastAPI server that provides an OpenAI-compatible API interface to the local `codex` CLI tool. This allows you to use codex with tools like OpenWebUI and other applications that expect the OpenAI API format.

This project also includes research and tooling for direct interaction with the ChatGPT backend Codex API.

## Features

- OpenAI-compatible API endpoints (`/v1/chat/completions`, `/v1/models`)
- Support for both streaming and non-streaming responses
- API key authentication
- Exposes codex as `codex-local` model
- Automatic JSON event parsing for streaming
- Comprehensive error handling and logging
- Direct ChatGPT Codex API testing utilities

## Prerequisites

- Python 3.13+
- [Codex CLI](https://github.com/openai/codex) installed and accessible
- Virtual environment (recommended)

## Installation

1. Clone or download this repository

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file from the example:
```bash
cp .env.example .env
```

5. Edit `.env` and configure your settings:
```env
API_KEYS=sk-local-key1,sk-local-key2
HOST=0.0.0.0
PORT=8000
CODEX_PATH=/opt/homebrew/bin/codex
CODEX_MODEL=gpt-5.2-codex
LOG_LEVEL=info
```

## Configuration

The following environment variables can be configured in your `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `API_KEYS` | Comma-separated list of valid API keys | Empty (no auth) |
| `HOST` | Server bind address | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `CODEX_PATH` | Path to codex binary | `/opt/homebrew/bin/codex` |
| `CODEX_MODEL` | Codex model to use | `gpt-5.2-codex` |
| `LOG_LEVEL` | Logging level (debug/info/warning/error) | `info` |

## Running the Server

### Development Mode

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or simply:

```bash
python app/main.py
```

### Production Mode

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The server will be available at `http://localhost:8000`.

## API Documentation

Once the server is running, visit:

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Usage Examples

### Health Check

```bash
curl http://localhost:8000/health
```

### List Models

```bash
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer sk-local-key1"
```

### Chat Completion (Non-Streaming)

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-local-key1" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "codex-local",
    "messages": [
      {"role": "user", "content": "What is 2+2?"}
    ]
  }'
```

### Chat Completion (Streaming)

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-local-key1" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "codex-local",
    "messages": [
      {"role": "user", "content": "Explain quantum computing"}
    ],
    "stream": true
  }'
```

### Using OpenAI Python Client

```python
from openai import OpenAI

# Configure client to use local proxy
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-local-key1"
)

# List models
models = client.models.list()
print(f"Available models: {[m.id for m in models.data]}")

# Non-streaming chat completion
response = client.chat.completions.create(
    model="codex-local",
    messages=[
        {"role": "user", "content": "What is the capital of France?"}
    ]
)
print(response.choices[0].message.content)

# Streaming chat completion
stream = client.chat.completions.create(
    model="codex-local",
    messages=[
        {"role": "user", "content": "Tell me a joke"}
    ],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()
```

## Tool Calling / Function Calling

The proxy supports OpenAI-style tool calling (function calling), allowing models to use functions you define. Tools are described to the model via the prompt, and the model can request to call them by returning structured JSON.

### Basic Example

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-local-key1"
)

# Define available tools
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
                        "enum": ["celsius", "fahrenheit"]
                    }
                },
                "required": ["location"]
            }
        }
    }
]

# Make request with tools
response = client.chat.completions.create(
    model="codex-local",
    messages=[{"role": "user", "content": "What's the weather in Paris?"}],
    tools=tools
)

# Check if model wants to call a tool
message = response.choices[0].message
if message.tool_calls:
    for tool_call in message.tool_calls:
        print(f"Tool: {tool_call.function.name}")
        print(f"Arguments: {tool_call.function.arguments}")
        # Execute the function with these arguments
```

### Multi-Turn Tool Execution

```python
# 1. Initial request
response = client.chat.completions.create(
    model="codex-local",
    messages=[{"role": "user", "content": "What's the weather in Paris?"}],
    tools=tools
)

# 2. Check if tool was called
if response.choices[0].message.tool_calls:
    tool_call = response.choices[0].message.tool_calls[0]

    # Execute your tool (example)
    weather_data = {"temperature": 18, "condition": "partly cloudy"}

    # 3. Send result back to model
    messages = [
        {"role": "user", "content": "What's the weather in Paris?"},
        response.choices[0].message,  # Assistant's message with tool_calls
        {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": "get_weather",
            "content": json.dumps(weather_data)
        }
    ]

    # 4. Get final response
    final = client.chat.completions.create(
        model="codex-local",
        messages=messages,
        tools=tools
    )

    print(final.choices[0].message.content)
```

### Streaming with Tools

```python
stream = client.chat.completions.create(
    model="codex-local",
    messages=[{"role": "user", "content": "Calculate 123 * 456"}],
    tools=[...],
    stream=True
)

for chunk in stream:
    delta = chunk.choices[0].delta

    if delta.content:
        print(delta.content, end="", flush=True)

    if delta.tool_calls:
        for tc in delta.tool_calls:
            print(f"\nTool call: {tc.function.name}")
            print(f"Arguments: {tc.function.arguments}")

print()
```

### How It Works

1. **Tool Description**: Tools are included as natural language documentation in the system prompt
2. **Model Decision**: The model decides whether to call a tool based on the user's request
3. **Tool Call Format**: If calling a tool, the model returns JSON: `{"name": "tool_name", "arguments": {...}}`
4. **Extraction**: The proxy extracts tool calls from the response and structures them in OpenAI format
5. **Execution**: Your application executes the tool and sends results back
6. **Continuation**: The model uses tool results to generate the final response

### Implementation Notes

- **Prompt-Based**: Tools are described in the prompt, not formally registered with codex CLI
- **Best-Effort Parsing**: Tool calls are extracted via regex patterns from model output
- **Validation**: Parameter validation should be done in your application code
- **Streaming Support**: Tool calls are streamed as deltas when using `stream=True`

### Limitations

- Tool definitions are not validated by codex - they're documentation for the model
- The model may occasionally hallucinate tools not in your list
- Parallel tool calling is supported but depends on model behavior
- No automatic parameter validation (implement in your code)

### Testing

Run the manual test script to verify tool calling:

```bash
python test_tools_manual.py
```

Run unit tests:

```bash
pytest tests/test_tools.py -v
```

## Integration with OpenWebUI

1. Start the Codex OpenAI Proxy server
2. In OpenWebUI, go to Settings → Connections
3. Add a new OpenAI connection:
   - Base URL: `http://localhost:8000/v1`
   - API Key: One of your configured keys (e.g., `sk-local-key1`)
4. The `codex-local` model should now appear in OpenWebUI's model selector

## Project Structure

```
codex-proxy/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings management
│   ├── auth.py              # API key authentication
│   ├── models/
│   │   ├── openai.py       # OpenAI schemas
│   │   └── codex.py        # Codex models
│   ├── services/
│   │   ├── codex_executor.py   # CLI execution
│   │   └── response_mapper.py  # Format conversion
│   └── routers/
│       ├── chat.py          # Chat completions
│       └── models.py        # Models listing
├── .env                     # Configuration (not in git)
├── .env.example            # Example configuration
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## How It Works

1. **Request Flow**: Client sends OpenAI-compatible request → FastAPI validates → Converts to codex prompt
2. **Execution**: Executes `codex e <prompt> --skip-git-repo-check --json` (for streaming) or without `--json` (for non-streaming)
3. **Response Mapping**: Parses codex output and converts to OpenAI format
4. **Streaming**: Codex JSON events are converted to Server-Sent Events (SSE) format
5. **Non-Streaming**: Full codex output is parsed and returned as complete response

## Known Limitations

1. **Prompt Format**: Messages are concatenated with role prefixes (e.g., "User: ...\n\nAssistant: ..."). This is simple but may not preserve all conversational nuances.

2. **Token Estimation**: For non-streaming mode, the split between input and output tokens is estimated using an 80/20 heuristic since standard output doesn't separate them clearly.

3. **OpenAI Parameters**: Some OpenAI parameters (temperature, max_tokens, etc.) are accepted but may be ignored since the codex CLI doesn't expose all of them.

4. **Concurrency**: Each request spawns a subprocess. For high concurrency scenarios, consider adding request queuing or rate limiting.

5. **Security**: The default sandbox mode is `read-only` for safety. Adjust `CODEX_SANDBOX` in `.env` if needed, but be cautious with `workspace-write` or `danger-full-access`.

## Troubleshooting

### Codex not found

If you get an error about codex not being found:

1. Check that codex is installed: `which codex`
2. Update `CODEX_PATH` in `.env` to the correct path
3. Ensure codex is executable: `chmod +x /path/to/codex`

### Authentication errors

If API key validation fails:

1. Check that your `.env` file has `API_KEYS` configured
2. Ensure you're passing the correct key in the `Authorization: Bearer` header
3. For development without auth, leave `API_KEYS` empty in `.env`

### Streaming not working

If streaming responses aren't working:

1. Check that you're setting `"stream": true` in the request
2. Ensure your client supports Server-Sent Events (SSE)
3. Check server logs for any errors during streaming

### No output from codex

If codex executes but returns empty responses:

1. Check server logs for codex execution details
2. Try running the codex command manually to verify it works
3. Check that `CODEX_MODEL` is set correctly
4. Ensure codex has proper authentication configured

## Development

To contribute or modify the code:

1. Install dev dependencies (if any)
2. Make your changes
3. Test with `pytest` (tests to be added)
4. Run the server in development mode with `--reload`

## License

This project is provided as-is for use with the Codex CLI tool.

## Support

For issues and questions:

- Check the [Troubleshooting](#troubleshooting) section
- Review the server logs (set `LOG_LEVEL=debug` for verbose output)
- Consult the [Codex CLI documentation](https://github.com/openai/codex)
