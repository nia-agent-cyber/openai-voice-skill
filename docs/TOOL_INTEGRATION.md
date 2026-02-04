# ask_openclaw Tool Integration

**Status:** Implemented ✅  
**Issue:** #21  
**Date:** 2026-02-04

## Overview

The `ask_openclaw` tool gives OpenAI Realtime voice sessions access to all OpenClaw agent capabilities. When a caller asks to do something that requires tools (email, calendar, files, etc.), the voice agent calls OpenClaw to execute the request.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Voice Call Flow                             │
└─────────────────────────────────────────────────────────────────────┘

Caller → Twilio SIP → OpenAI Realtime Session
                              │
                              │ (tools configured)
                              ▼
                    ┌──────────────────┐
                    │  Function Call   │
                    │  ask_openclaw    │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │ webhook-    │  │ realtime_   │  │ openclaw_   │
    │ server.py   │  │ tool_       │  │ executor.py │
    │ (accept     │  │ handler.py  │  │ (CLI call)  │
    │ call)       │  │ (WebSocket) │  │             │
    └─────────────┘  └──────┬──────┘  └──────┬──────┘
                            │                │
                            ▼                ▼
                    Listen for        openclaw chat
                    function_call     --message "..."
                    events            --no-interactive
                            │                │
                            ▼                ▼
                    Send result       Full agent
                    back to           capabilities
                    Realtime          (email, files, etc.)
```

## Components

### 1. config/agent.json

Tool definition and instructions:

```json
{
  "tools": [
    {
      "type": "function",
      "name": "ask_openclaw",
      "description": "Ask the OpenClaw agent to perform any task...",
      "parameters": {
        "type": "object",
        "properties": {
          "request": {
            "type": "string",
            "description": "Natural language description..."
          }
        },
        "required": ["request"]
      }
    }
  ]
}
```

### 2. scripts/openclaw_executor.py

Executes requests via OpenClaw CLI:

```python
from openclaw_executor import execute_openclaw_request

result = await execute_openclaw_request("Check my calendar for today")
# Returns voice-friendly text response
```

Features:
- Async subprocess execution
- Configurable timeout (default 30s)
- Voice-friendly output formatting (strips markdown)
- Graceful error handling

### 3. scripts/realtime_tool_handler.py

WebSocket handler for function calls:

```python
from realtime_tool_handler import start_tool_handler

await start_tool_handler(
    call_id="call_123",
    session_id="session_456",
    model="gpt-4o-realtime-preview"
)
```

Features:
- Connects to Realtime session via WebSocket
- Listens for `response.function_call_arguments.done` events
- Executes functions via OpenClaw executor
- Sends results back via `conversation.item.create`
- Auto-reconnect on connection loss

### 4. scripts/webhook-server.py (updated)

Integration points:
- Passes tools to session when accepting calls
- Starts tool handler after call acceptance
- Stops tool handler when call ends
- New endpoint: `GET /tools/status`

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCLAW_TIMEOUT` | 30 | Max seconds for OpenClaw execution |
| `OPENCLAW_MODEL` | (default) | Override model for OpenClaw requests |

### agent.json Instructions

The instructions include guidance for verbal acknowledgment:

```
IMPORTANT: When the user asks you to do something that requires:
- Checking or sending emails/messages
- Reading or writing files
- Calendar operations
- Code execution
- Web searches
- Memory/workspace access

You MUST use the ask_openclaw tool. Before calling it, ALWAYS say:
"Let me check that for you" or "One moment while I look that up"

This verbal acknowledgment is CRITICAL - the tool takes a few seconds
and the user needs to know something is happening.
```

## API Endpoints

### GET /tools/status

Returns status of tool handlers:

```json
{
  "tool_handler_available": true,
  "configured_tools": ["ask_openclaw"],
  "active_handlers": 1,
  "handlers": {
    "call_123": {
      "session_id": "session_456",
      "running": true,
      "stats": {
        "function_calls": 3,
        "successful_calls": 3,
        "failed_calls": 0
      }
    }
  }
}
```

### GET /health (updated)

Now includes tool info:

```json
{
  "status": "ok",
  "tools_enabled": true,
  "tool_count": 1
}
```

## Usage Examples

**Caller:** "Check my email"

**Voice Agent:** "Let me check that for you..." *(verbal ack)*

**[ask_openclaw called with request: "Check email inbox for unread messages"]**

**[OpenClaw executes, returns summary]**

**Voice Agent:** "You have 3 unread emails. The first is from John about the meeting tomorrow..."

## Testing

### Test Executor Directly

```bash
cd scripts
python openclaw_executor.py "What time is it?"
```

### Test Tool Handler Status

```bash
curl http://localhost:8080/tools/status
```

### End-to-End Test

1. Start webhook server: `python webhook-server.py`
2. Make a test call
3. Ask: "Check my calendar for today"
4. Verify verbal acknowledgment plays
5. Verify tool executes and response speaks

## Limitations

1. **Latency:** OpenClaw execution adds 2-5 seconds
2. **Concurrency:** One tool call at a time per session
3. **Output Length:** Responses truncated to ~2000 chars for voice
4. **Session:** Uses default OpenClaw session (not call-specific)

## Future Enhancements

- [ ] Session isolation per caller
- [ ] Parallel tool calls
- [ ] Audio feedback during execution
- [ ] Custom tool definitions via config
- [ ] Streaming results for long operations
