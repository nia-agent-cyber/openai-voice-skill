# Contributing to OpenAI Voice Skill

Thanks for your interest! This project adds real-time voice calling to OpenClaw agents via OpenAI's Realtime API and Twilio SIP.

## Quick Start

```bash
git clone https://github.com/nia-agent-cyber/openai-voice-skill.git
cd openai-voice-skill
pip install -r scripts/requirements.txt
pip install -r scripts/requirements-dev.txt
```

## Running Tests

```bash
pytest
```

All 97 tests should pass. PRs with failing tests won't be merged.

## Pull Request Process

1. Fork the repo and create a feature branch from `main`
2. Write tests for new functionality
3. Ensure all tests pass: `pytest`
4. Rebase on `main` before submitting: `git fetch origin && git rebase origin/main`
5. Open a PR with a clear description of what and why

## What's Welcome

- **Bug fixes** — especially around call reliability and edge cases
- **New examples** in `examples/` — show practical use cases
- **Documentation** — tutorials, guides, better docstrings
- **Integration examples** — Cal.com, CRMs, scheduling tools

## What to Avoid

- ⛔ Do not modify `webhook-server.py` — it's production infrastructure
- ⛔ Do not modify Twilio/SIP/OpenAI Realtime core code without discussion
- Open an issue first for large changes

## Architecture Overview

```
Twilio SIP ──→ webhook-server.py ──→ OpenAI Realtime API
                     │
                     ├── ask_openclaw tool ──→ OpenClaw agent
                     ├── call_recording.py ──→ session bridge
                     └── metrics/dashboard API
```

The channel plugin calls existing services via HTTP — it doesn't touch the voice pipeline directly.

## Code Style

- Python: Follow existing patterns in the codebase
- Tests: Use pytest, mock external services
- Commits: Clear, descriptive messages

## Questions?

Open an issue or check [examples/](examples/) for working code.
