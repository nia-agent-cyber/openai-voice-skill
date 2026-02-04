# Session Bridge Cleanup Plan

**Date:** 2026-02-04
**Status:** Conflict Identified → Resolution Ready
**Author:** Voice PM Subagent

---

## Problem Summary

Two bridges compete for port 8082:

| Bridge | File | Port | Status |
|--------|------|------|--------|
| **Python** | `scripts/openclaw-webhook-bridge.py` | 8082 | ❌ RUNNING (blocks TS) |
| **TypeScript** | `channel-plugin/src/adapters/session-bridge.ts` | 8082 | ✅ CORRECT (can't start) |

**Result:** `call_recording.py` → `session_context.py` posts to `localhost:8082/call-event`, but Python bridge doesn't have that endpoint. Session sync fails silently.

---

## Analysis

### Python Bridge (`openclaw-webhook-bridge.py`)
- **Endpoints:** `/openclaw/call`, `/openclaw/context`, `/webhook/forward`, `/health`
- **Does NOT have:** `/call-event` ❌
- **Purpose:** Old integration approach — forwards calls through Python layer
- **Problem:** Different API design than what `session_context.py` expects

### TypeScript Bridge (`session-bridge.ts`)
- **Endpoints:** `/call-event`, `/sync-transcript`, `/sessions`, `/health`
- **HAS:** `/call-event` ✅ (exactly what `session_context.py` posts to!)
- **Purpose:** T3 implementation — post-call transcript sync
- **Status:** PM APPROVED, marked as DONE in voice.md

### Data Flow (Intended)
```
call_recording.py
    └── notify_call_started() / notify_call_ended()
            └── session_context.py
                    └── POST localhost:8082/call-event  ← TS bridge has this!
                            └── session-bridge.ts
                                    └── OpenClaw session JSONL
```

---

## Decision: Keep TypeScript, Remove Python

**Keep:** `session-bridge.ts` on port 8082
**Remove:** `openclaw-webhook-bridge.py`

### Reasoning
1. **T3 is DONE** — TypeScript bridge is the approved architecture
2. **API Match** — `session_context.py` posts to `/call-event` which only TS bridge has
3. **Redundant** — Python bridge was an earlier approach, superseded by T3
4. **Maintenance** — One bridge is simpler than two

---

## Resolution Instructions

### Step 1: Stop Python Bridge

```bash
# Find and kill the Python bridge process
pkill -f "openclaw-webhook-bridge.py"

# Or if you know the PID:
kill 32313
```

Verify it's stopped:
```bash
lsof -i :8082
# Should show nothing or "Port not in use"
```

### Step 2: Disable Python Bridge Autostart

The Python bridge is started by `scripts/start-integrated-system.sh`.

**Option A: Don't use the startup script** (recommended)
- The TS bridge should be started by the OpenClaw gateway adapter
- Just run `openclaw gateway start` instead of the shell script

**Option B: Update the startup script**
- Edit `scripts/start-integrated-system.sh`
- Replace the `start_bridge_server()` function to use TS bridge instead

See updated startup script below.

### Step 3: Build TypeScript Bridge

```bash
cd /Users/ec2-user/.openclaw/workspace/openai-voice-skill/channel-plugin

# Install deps if needed
npm install

# Build
npm run build
```

### Step 4: Start TypeScript Bridge

The session bridge is started by the gateway adapter. To test standalone:

```bash
# Option A: Through gateway (recommended)
openclaw gateway restart

# Option B: Direct test (for debugging)
cd channel-plugin
npx ts-node -e "
import { createSessionBridge } from './src/adapters/session-bridge';
const bridge = createSessionBridge({
  port: 8082,
  webhookServerUrl: 'http://localhost:8080'
});
bridge.start().then(() => console.log('Bridge running on 8082'));
"
```

### Step 5: Verify

```bash
# Check bridge is running
curl http://localhost:8082/health
# Expected: {"status":"healthy","activeCalls":0,...}

# Test the endpoint that call_recording.py uses
curl -X POST http://localhost:8082/call-event \
  -H "Content-Type: application/json" \
  -d '{"callId":"test123","eventType":"call_started","phoneNumber":"+1234567890","direction":"inbound","timestamp":"2026-02-04T14:00:00Z"}'
# Expected: {"status":"session_mapped","sessionKey":"voice:1234567890"}
```

### Step 6: Full Integration Test

1. Make a test call to the Twilio number
2. Check bridge logs for `/call-event` hits
3. Verify session file created in OpenClaw
4. Confirm transcript syncs after call ends

---

## Files to Update

### Keep (DO NOT DELETE)
- `channel-plugin/src/adapters/session-bridge.ts` — THE bridge
- `scripts/session_context.py` — Bridge event emitter (works with TS bridge)
- `scripts/call_recording.py` — Uses session_context.py

### Remove / Archive
- `scripts/openclaw-webhook-bridge.py` — OLD, redundant

```bash
# Archive instead of delete (safer)
mv scripts/openclaw-webhook-bridge.py scripts/archive/openclaw-webhook-bridge.py.old
```

### Update voice.md (Optional)
Add note that Python bridge was removed, TS bridge is canonical.

---

## Port Assignment (Final)

| Service | Port | Status |
|---------|------|--------|
| webhook-server.py | 8080 | DO NOT TOUCH |
| plugin-server.py | 8081 | DO NOT TOUCH |
| session-bridge.ts | 8082 | ✅ CANONICAL |
| (Python bridge) | 8082 | ❌ REMOVED |

---

## Rollback Plan

If issues arise:

```bash
# Restore Python bridge
mv scripts/archive/openclaw-webhook-bridge.py.old scripts/openclaw-webhook-bridge.py

# Run it temporarily
python3 scripts/openclaw-webhook-bridge.py &

# But note: this won't fix session sync (no /call-event endpoint)
```

The real fix is always: get TypeScript bridge running.

---

## Completion Checklist

- [ ] Stop Python bridge process
- [ ] Disable Python bridge autostart (if any)
- [ ] Build TypeScript channel-plugin
- [ ] Start TypeScript bridge (via gateway or direct)
- [ ] Verify `/call-event` endpoint works
- [ ] Test full call → session sync flow
- [ ] Archive Python bridge file
- [ ] Update voice.md (optional)
