# Bug Analysis: ask_openclaw Tool Not Working

**Date:** 2026-02-04  
**Severity:** Critical  
**Status:** Root cause identified, fix plan documented

## Executive Summary

The `ask_openclaw` tool isn't working because **the tool handler is connecting to the wrong WebSocket endpoint**. It's creating a NEW Realtime session instead of connecting to the EXISTING call's sideband channel.

## Root Cause

### The Bug (in `realtime_tool_handler.py` line ~79)

```python
# CURRENT (WRONG):
url = f"{OPENAI_REALTIME_URL}?model={self.model}"
# Evaluates to: wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview
```

### What It Should Be

```python
# CORRECT:
url = f"wss://api.openai.com/v1/realtime?call_id={self.call_id}"
```

## Why This Matters

The current code creates a **completely new, empty Realtime session** that has:
- No connection to the phone call
- No audio from the user
- No function call events (because function calls happen in the ORIGINAL session)

Meanwhile, the actual phone call session (with the user talking) generates function call events that go... nowhere that we're listening.

## How OpenAI Realtime + SIP Actually Works

```
                                    ┌─────────────────────────────────┐
                                    │       OpenAI SIP Endpoint       │
                                    │   sip:{project}@sip.api.openai  │
                                    └──────────────┬──────────────────┘
                                                   │
                    ┌──────────────────────────────┴─────────────────────────────┐
                    │                                                            │
            1. SIP Audio Channel                                    2. WebSocket Sideband
            (Phone <-> Model)                                       (Server Control)
                    │                                                            │
        ┌───────────┴───────────┐                              ┌─────────────────┴─────────────────┐
        │                       │                              │                                   │
   User speaks          Model speaks                    Function call events            Server sends:
   (audio in)           (audio out)                     Tool call events               - session.update
        │                       │                       - response.done                - conversation.item.create
        │                       │                       - etc.                         - response.create (for tool output)
        │                       │                              │                                   │
        └───────────────────────┘                              └───────────────────────────────────┘
                    │                                                            │
                    │              SAME CALL_ID                                  │
                    └──────────────────┬─────────────────────────────────────────┘
                                       │
                              ?call_id=rtc_xxxxx
```

### Key Architecture Points

1. **SIP audio is separate from WebSocket control**
   - Phone audio flows directly between the phone and OpenAI
   - Our server NEVER touches the raw audio

2. **Sideband WebSocket connection**
   - After accepting a call via REST API, we connect a WebSocket using `?call_id={call_id}`
   - This WebSocket receives ALL events from that session including function calls
   - This is the "sideband" or "control channel"

3. **Function calls flow through the sideband**
   - When the model decides to call a function, it emits `response.function_call_arguments.done`
   - This event is sent through the sideband WebSocket
   - We respond by sending `conversation.item.create` with the function output
   - Then `response.create` to trigger the model to speak the result

## Evidence From Logs

Looking at what the logs show:
- "Tool handler started" ✅ (Handler object created)
- "Connected to Realtime session" ✅ (WebSocket connected... to wrong endpoint!)
- NO function call events ❌ (Because we're listening to an empty session)

The connection succeeds because `wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview` is a valid endpoint for creating a new session. But it's NOT the session with the active phone call.

## Fix Plan

### Step 1: Fix the WebSocket URL (Critical)

In `realtime_tool_handler.py`, change the `connect()` method:

```python
# BEFORE:
url = f"{OPENAI_REALTIME_URL}?model={self.model}"
headers = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "OpenAI-Beta": "realtime=v1"  # Also outdated for GA API
}

# AFTER:
url = f"wss://api.openai.com/v1/realtime?call_id={self.call_id}"
headers = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    # Remove OpenAI-Beta header for GA API
}
```

### Step 2: Update the Handler Initialization

The handler is already receiving `call_id` but also has a `session_id` parameter that's confusing. Simplify:

```python
# BEFORE:
def __init__(
    self,
    session_id: str,
    call_id: str,
    model: str = "gpt-4o-realtime-preview",
    ...
)

# AFTER:
def __init__(
    self,
    call_id: str,  # This is the ONLY ID we need
    ...
)
```

### Step 3: Update the Caller in webhook-server.py

In `accept_call()`, the call to `start_tool_handler` should pass the call_id:

```python
# BEFORE (line ~608):
asyncio.create_task(start_tool_handler(
    call_id=call_id,
    session_id=session_id,  # Confusing
    model=AGENT_CONFIG["model"]
))

# AFTER:
asyncio.create_task(start_tool_handler(call_id=call_id))
```

### Step 4: Timing Fix - Connect AFTER accept completes

Currently the tool handler might connect before the call is fully accepted. The accept response confirms when the session is ready:

```python
# In accept_call(), start handler AFTER successful accept:
if response.status_code == 200:
    logger.info(f"Call {call_id} accepted successfully")
    # NOW it's safe to connect the sideband
    if TOOL_HANDLER_AVAILABLE and AGENT_CONFIG.get("tools"):
        asyncio.create_task(start_tool_handler(call_id=call_id))
```

### Step 5: GA API Event Names (Optional but recommended)

The GA API has updated some event names. Update the handler to listen for both old and new names:

```python
# Function call events - handle both beta and GA names
if event_type in ["response.function_call_arguments.done"]:
    await self._handle_function_call(event)
```

## Testing Plan

1. **Make a test call** to the voice number
2. **Ask something that triggers ask_openclaw**, e.g., "What's the weather today?"
3. **Check logs for:**
   - "Connected to Realtime session for call {call_id}" 
   - "Function call received: ask_openclaw"
   - "Executing OpenClaw request: ..."
   - "Function result sent"
4. **Verify the model speaks the result** back to the caller

## References

- [OpenAI Realtime SIP Guide](https://platform.openai.com/docs/guides/realtime-sip)
- [Webhooks and Server-side Controls](https://platform.openai.com/docs/guides/realtime-server-controls)
- [Realtime Conversations (Function Calling)](https://platform.openai.com/docs/guides/realtime-conversations#function-calling)

## Code Example from OpenAI Docs

This is the correct pattern from OpenAI's documentation:

```python
async def websocket_task(call_id):
    try:
        async with websockets.connect(
            "wss://api.openai.com/v1/realtime?call_id=" + call_id,  # ← KEY FIX
            additional_headers=AUTH_HEADER,
        ) as websocket:
            await websocket.send(json.dumps(response_create))

            while True:
                response = await websocket.recv()
                print(f"Received from WebSocket: {response}")
    except Exception as e:
        print(f"WebSocket error: {e}")
```

---

**Next Steps:** Implement fixes in `realtime_tool_handler.py` and `webhook-server.py`, then test with a live call.
