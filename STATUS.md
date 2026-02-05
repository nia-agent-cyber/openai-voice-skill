# Voice Skill Status

**Last Updated:** 2026-02-05 09:40 GMT by Voice PM
**Repo:** github.com/nia-agent-cyber/openai-voice-skill

---

## Current State: ⚠️ RELIABILITY ISSUES

### Critical Issue
**Josh Pigford (@Shpigford) couldn't get the voice skill working reliably and switched to Vapi.**

This is our top priority. See **#31** for full analysis and fixes.

### What's Live
- ✅ `ask_openclaw` tool — pipeline working but unreliable
- ✅ Outbound calls via HTTP POST to `https://api.niavoice.org/call`
- ✅ Session bridge (T3) — transcripts sync to OpenClaw sessions
- ✅ Streaming responses (PR #30 merged)
- ✅ Security: inbound disabled by default (PR #29)

### In Progress
- [ ] **#31** — 🔴 CRITICAL: Reliability fixes (WebSocket reconnection, timeouts, error handling)
- [ ] **#27** — Integration testing for streaming responses
- [ ] **T4** — Inbound Handler (phone → session creation)

### Blocked
*Nothing currently blocked*

---

## Next Steps (Priority Order)

### 🔴 P0 - This Week (Reliability)
1. **#31** — Reliability fixes (assigned: PM to coordinate)
   - [ ] Add exponential backoff to WebSocket reconnection
   - [ ] Reduce default timeout to 10s
   - [ ] Add basic call metrics (`/metrics` endpoint)
   - [ ] Improve error messages with call_id

2. **Manual testing** — Full call flow with tool use
   - [ ] Outbound call with ask_openclaw
   - [ ] Multiple tool invocations in one call
   - [ ] Test timeout/failure scenarios

### P1 - This Month
3. **#27** — Integration testing for streaming
4. **T4** — Inbound call handler
5. Replace subprocess with HTTP API for lower latency
6. Add structured logging (JSON with call_id, latency)

### P2 - Later
7. **T6** — Security allowlist enforcement
8. **T7** — Full E2E deployment testing
9. Real-time transcript streaming (during call, not just after)

---

## Task Breakdown

| Task | Priority | Status | Description |
|------|----------|--------|-------------|
| **T8: Reliability** | **P0** | **🔴 IN PROGRESS** | **Fix reliability issues (#31)** |
| T1: Fix Entry Point | P0 | ✅ DONE | registerChannel() works |
| T2: Add Config | P0 | ✅ DONE | `channels: ["voice"]` in manifest |
| T3: Session Bridge | P0 | ✅ DONE | Post-call transcript sync |
| T4: Inbound Handler | P1 | TODO | Phone call → session creation |
| T5: Gateway Adapter | P1 | ✅ DONE | Starts bridge, health checks |
| T6: Security | P2 | TODO | Allowlists, DM policy |
| T7: Deploy & Test | P0 | TODO | Full integration testing |

---

## Open Issues

| Issue | Description | Priority |
|-------|-------------|----------|
| **#31** | **🔴 Critical: Reliability Issues - User Switched to Vapi** | **P0** |
| #20 | Complete Voice Channel Plugin | P1 |
| #27 | Integration testing for streaming | P1 |

## Recent PRs

| PR | Status | Description |
|----|--------|-------------|
| #30 | ✅ Merged | Streaming tool responses |
| #29 | ✅ Merged | Security: disable inbound by default |
| #22 | Open | WebSocket fixes, command fixes |

---

## How to Make Outbound Calls

```bash
curl -X POST https://api.niavoice.org/call \
  -H "Content-Type: application/json" \
  -d '{"to": "+1234567890", "message": "Your message here"}'
```

Note: CLI `message send --channel voice` doesn't work yet (OpenClaw core limitation).

---

## Infrastructure

- **Webhook Server:** port 8080 (webhook-server.py) — DO NOT MODIFY
- **Plugin Server:** port 8081
- **Session Bridge:** port 8082 (session-bridge.ts)
- **Public URL:** https://api.niavoice.org (cloudflare tunnel)
- **Twilio Number:** +1 440 291 5517

### ⚠️ Bridge Port Conflict

If bridge issues occur:
```bash
pkill -f "openclaw-webhook-bridge.py"  # Kill old Python bridge
openclaw gateway restart                # Starts TS bridge
curl http://localhost:8082/health       # Verify
```

Canonical bridge: `session-bridge.ts` on port 8082

---

## Cleanup Pending

Old `nia-voice-call` plugin should be removed:
- `~/.openclaw/extensions/nia-voice-call/` — DELETE
- `plugins.entries.nia-voice-call` in openclaw.json — REMOVE
