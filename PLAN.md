# CLI Proxy - Implementation Plan

## Completed Features

### 1. OpenCode CLI Support (Completed)

Added OpenCode CLI as a second backend alongside Codex CLI.

**Files Created:**
- `app/services/base_executor.py` - Abstract base class for CLI executors
- `app/services/opencode_executor.py` - OpenCode CLI executor implementation

**Files Modified:**
- `app/config.py` - Added OpenCode settings + cross-platform path detection
- `app/services/codex_executor.py` - Now inherits from BaseExecutor
- `app/routers/chat.py` - Routes to appropriate executor based on model
- `app/routers/models.py` - Lists available models based on installed CLIs
- `app/main.py` - Validates both backends, shows dual-backend info
- `app/cli.py` - Updated help text for dual-backend support
- `.env.example` - Added OpenCode configuration options
- `README.md` - Updated documentation for dual-backend support

**How Model Routing Works:**
- `codex-local` → Codex CLI (`codex e <prompt> --json`)
- `opencode-local` → OpenCode CLI (`opencode run <prompt> --format json`)
- Models starting with `anthropic/` or `openai/` → OpenCode CLI

### 2. Cross-Platform Path Detection (Completed)

CLIs are now auto-detected across platforms:
- **macOS**: `/opt/homebrew/bin/`, `/usr/local/bin/`
- **Linux**: `/usr/local/bin/`, `/usr/bin/`, `~/.local/bin/`
- **Windows**: Common installation paths, falls back to PATH

Set `CODEX_PATH=` or `OPENCODE_PATH=` to empty for auto-detection.

---

## Remaining Items from Original Plan

### Medium Priority (Optional Enhancements)

1. **Configuration Validation**
   - Add validation for port range, sandbox modes
   - Provide helpful error messages

2. **Dynamic Timestamp in Model Metadata**
   - Replace hardcoded timestamp in `app/models/openai.py`

3. **Enhanced Security Warning**
   - Add more visible warning when running without API keys

---

## Usage

### Running with uvx

```bash
# From GitHub
uvx --from git+https://github.com/yuvalraviv1/codex-proxy codex-proxy

# From a specific branch
uvx --from git+https://github.com/yuvalraviv1/codex-proxy@branch-name codex-proxy
```

### Available Models

| Model | Backend | Command |
|-------|---------|---------|
| `codex-local` | Codex CLI | `codex e <prompt>` |
| `opencode-local` | OpenCode CLI | `opencode run <prompt>` |

### Configuration

See `.env.example` for all available options.
