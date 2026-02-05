# Voice Skill Status

**Last Updated:** 2026-02-05 16:56 GMT by Voice QA
**Repo:** github.com/nia-agent-cyber/openai-voice-skill

---

## Current State: 🧪 PR #32 MERGED — VALIDATION IN PROGRESS

### Critical Issue
**Josh Pigford (@Shpigford) couldn't get the voice skill working reliably and switched to Vapi.**

**PR #32** passed both QA and PM review. Ready for Remi to merge.

### What's Live
- ✅ `ask_openclaw` tool — pipeline working but unreliable
- ✅ Outbound calls via HTTP POST to `https://api.niavoice.org/call`
- ✅ Session bridge (T3) — transcripts sync to OpenClaw sessions
- ✅ Streaming responses (PR #30 merged)
- ✅ Security: inbound disabled by default (PR #29)

### In Progress
- [x] **#31** → **PR #32** — P0 reliability fixes ✅ **QA + PM APPROVED**
- [ ] **#27** — Integration testing for streaming responses
- [ ] **T4** — Inbound Handler (phone → session creation)

### QA Results (2026-02-05)
| Check | Status |
|-------|--------|
| Syntax check (`py_compile`) | ✅ Pass |
| Test suite (29 tests) | ✅ Pass |
| Exponential backoff impl | ✅ Verified |
| Timeout reduction (30s→5s) | ✅ Verified |
| Call ID logging | ✅ Verified |
| Code quality | ✅ Clean |

**QA Review:** [PR #32 comment](https://github.com/nia-agent-cyber/openai-voice-skill/pull/32#issuecomment-3852366818)

### PM Review (2026-02-05)
| Requirement | Status |
|-------------|--------|
| Exponential backoff (500ms → 30s, 10 attempts) | ✅ Correct |
| 10% jitter (thundering herd prevention) | ✅ Present |
| Timeout reduction (30s → 5s) | ✅ Via `OPENCLAW_VOICE_TIMEOUT` |
| Call ID tracking in all logs | ✅ Comprehensive |
| Metrics endpoint | ⏭️ Deferred to P1 |

**PM Review:** [PR #32 comment](https://github.com/nia-agent-cyber/openai-voice-skill/pull/32#issuecomment-3853328412)
**Mergeable:** ✅ MERGEABLE (no conflicts)

### Blocked
*Nothing currently blocked*

---

## Next Steps (Priority Order)

*PM Analysis: 2026-02-05 16:44 GMT*

### 🔴 P0 - This Week (Validation)
1. **Merge PR #32** — Approved, waiting for Remi
   - [x] Exponential backoff (500ms → 30s cap, 10 attempts)
   - [x] 5s timeout (was 30s)
   - [x] call_id tracking in all logs

2. **Validation Testing** — Exit criteria from DECISIONS.md
   - [ ] 10 successful test calls with tool use
   - [ ] Multiple tool invocations in one call
   - [ ] Timeout/failure scenario testing
   - [ ] No connection drops or timeouts
   - **Goal:** Prove we fixed the Josh Pigford problem

---

## 🧪 Validation Test Plan (QA)

**Prepared:** 2026-02-05 16:46 GMT by Voice QA
**Status:** 🧪 EXECUTING — PR #32 merged, validation in progress

### Exit Criteria (from DECISIONS.md)
- ✅ 10 successful test calls with tool use
- ✅ No timeouts or connection drops in testing

### Test Call Checklist

| # | Scenario | Tool Use | Description | Result | Notes |
|---|----------|----------|-------------|--------|-------|
| 1 | Simple tool call | Single | "What time is it?" or "What's the weather?" | ⏳ | call_id: CA92ea3d1410327ab19947a9429ceb8ed0, 16:54 GMT, awaiting Remi confirmation |
| 2 | Simple tool call | Single | "Check my calendar for today" | ⬜ | Different tool type |
| 3 | Multi-tool sequential | 2+ | "What's on my calendar and what's the weather?" | ⬜ | Tests sequential tool handling |
| 4 | Multi-tool sequential | 2+ | "Search for X then summarize it" | ⬜ | Chain of operations |
| 5 | Conversational with tool | Single | Small talk → tool request → follow-up | ⬜ | Natural conversation flow |
| 6 | Long response handling | Single | "Tell me about [complex topic]" via search | ⬜ | Tests streaming/timeout with larger responses |
| 7 | Rapid follow-up | 2+ | Tool call → immediate second question | ⬜ | Tests session stability under rapid input |
| 8 | Interrupted tool call | Single | Start tool request, pause mid-sentence, continue | ⬜ | Speech interruption handling |
| 9 | Error recovery | Single | Request something likely to timeout/fail, then valid request | ⬜ | Tests exponential backoff + recovery |
| 10 | Extended conversation | 3+ | 2+ minute call with multiple tool invocations | ⬜ | Sustained reliability test |

### Success Criteria Per Call
- [ ] Call connects within 5s
- [ ] Tool invocation completes (no timeout)
- [ ] Response delivered audibly
- [ ] No WebSocket drops during call
- [ ] Call ends cleanly
- [ ] Transcript syncs to session (T3 validation)

### Test Execution Notes
- **Phone:** Use Twilio number +1 440 291 5517
- **Logs:** Check call_id in logs for each call
- **Recording:** Note any latency issues or audio quality problems
- **Pass threshold:** 10/10 successful (0 failures allowed for exit criteria)

### Edge Cases to Watch
- First response latency (target: <3s)
- WebSocket reconnection behavior (if network hiccup)
- Timeout behavior with 5s limit
- Backoff progression if failures occur

### Test Execution Log

#### Test 1 — 2026-02-05 16:54 GMT
- **Call ID:** CA92ea3d1410327ab19947a9429ceb8ed0
- **Target:** +250794002033 (Remi)
- **API Response:** 200 OK in 0.43s
- **Message:** "Hi Remi, this is validation Test 1. Please ask me: What time is it? This tests the ask_openclaw tool."
- **Service Health at initiation:** 3 active calls → 6 active calls (call connected)
- **Observations:**
  - API endpoint responsive
  - Call initiated successfully
  - Service health endpoint shows tools_enabled: true
- **Awaiting:** Remi confirmation on tool invocation success, audio quality, any drops

---

### 🟡 P1 - Next 2 Weeks (Observability)
3. **Metrics & Observability** — "Can't improve what you can't measure"
   - [ ] `/metrics` endpoint (deferred from PR #32)
   - [ ] Call success rate tracking (target: >95%)
   - [ ] Time to first response (target: <3s)
   - [ ] WebSocket reconnection success rate
   - **Why:** BA insight — voice agents fail from weak observability, not bad AI

4. **#27** — Integration testing for streaming

### 🟢 P1 - Weeks 3-4 (Inbound)
5. **T4** — Inbound call handler
   - Enables "24/7 call answering" (top requested feature)
   - Agent-native differentiation vs Vapi
   - Blocked until: validation testing passes

### P2 - Later
6. Replace subprocess with HTTP API for lower latency
7. **T6** — Security allowlist enforcement
8. **T7** — Full E2E deployment testing
9. Structured logging (JSON with call_id, latency)

---

## PM Recommended Timeline

| Week | Focus | Deliverable |
|------|-------|-------------|
| Feb 5-12 | Validation | PR #32 merged, 10 successful test calls |
| Feb 12-19 | Observability | `/metrics` endpoint, success rate tracking |
| Feb 19-26 | Observability | TTFR metrics, structured logging |
| Feb 26 - Mar 5 | Inbound | T4 complete, inbound calls working |

## Concerns & Blockers

1. **PR #32 merge** — Depends on Remi's availability
2. **No telemetry** — We're flying blind on actual usage/failures
3. **Validation before features** — T4 blocked until we prove reliability

---

## Task Breakdown

| Task | Priority | Status | Description |
|------|----------|--------|-------------|
| **T8: Reliability** | **P0** | **✅ QA PASSED** | **Fix reliability issues (#31) — PR #32 ready for merge** |
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
| **#32** | **✅ QA + PM APPROVED — Ready for Remi** | **P0 reliability: exponential backoff, 5s timeout, call_id logging** |
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
