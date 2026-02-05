# Voice Skill Status

**Last Updated:** 2026-02-05 17:10 GMT by Voice PM
**Repo:** github.com/nia-agent-cyber/openai-voice-skill

---

## Current State: 🔴 NOT READY FOR USERS — 6/10 Validation Pass Rate

### Critical Finding

**Validation testing complete. Results are WORSE than initially reported:**

| Test | Result | Issue |
|------|--------|-------|
| 1 | ⚠️ | Wrong timezone (#34) |
| 2 | ❌ | Hallucinated calendar (#33) |
| 3 | ❌ | Wrong location + timezone (#34) |
| 4 | ❌ | Application error on web search (#35) |
| 5 | ✅ | Passed |
| 6 | ✅ | Passed |
| 7 | ✅ | Passed |
| 8 | ✅ | Passed |
| 9 | ✅ | Passed |
| 10 | ✅ | Passed |

**Pass Rate: 6/10** — Voice connects reliably, but **wrong answers = not usable**.

### Issues to Fix (Priority Order)

| Issue | Priority | Type | Description | Impact |
|-------|----------|------|-------------|--------|
| **#35** | **P0** | Reliability | Application error during web search | Crashes are unacceptable |
| **#34** | **P1** | Context | Wrong timezone and location passed to tools | Affects ALL location/time tools |
| **#33** | **P1** | Data Integrity | Calendar returns hallucinated data | Destroys user trust |

---

## 🔧 Fix Plan

### Phase 1: P0 Reliability (#35) — IMMEDIATE

**Problem:** Test 4 ("Search for X then summarize") caused an application error.

**Root Cause (suspected):**
- Web search tool may throw unhandled exception
- Timeout handling in ask_openclaw may not catch all error cases
- PR #32 fixed timeouts but may not handle all error paths

**Action Required:**
1. Review ask_openclaw error handling for web search
2. Add try/catch around tool execution
3. Ensure graceful fallback on any tool error

**Coder Task:** Investigate #35, add comprehensive error handling in tool bridge.

---

### Phase 2: P1 Context (#34) — This Week

**Problem:** Tools receive no user context (timezone, location).
- Time tool returned 14:15 when user's local time was 18:59 (4+ hour diff)
- Weather returned wrong location data

**Root Cause (suspected):**
- Voice session doesn't pass user timezone/location to OpenClaw
- Tools default to UTC or server location
- Context may be available in Twilio call metadata but not forwarded

**Action Required:**
1. Check if Twilio provides caller timezone/location
2. Pass user context from voice session to ask_openclaw
3. Ensure OpenClaw tools receive and use context

**Coder Task:** Add user context (timezone, location) to voice → OpenClaw bridge.

---

### Phase 3: P1 Data Integrity (#33) — This Week

**Problem:** Calendar tool returns fake meetings when no calendar connected.

**Root Cause (suspected):**
- OpenClaw calendar tool doesn't validate connection state
- Falls back to LLM generating plausible responses
- No "calendar not connected" error path

**Action Required:**
1. Calendar tool must validate connection before returning data
2. Return explicit error when no calendar connected
3. Voice agent should say "No calendar connected" not hallucinate

**Note:** This may be an OpenClaw core fix, not voice skill.

---

## Status Summary

| Category | Status | Notes |
|----------|--------|-------|
| **Voice Infrastructure** | ✅ WORKING | Calls connect, audio good, no drops |
| **Tool Reliability** | ❌ BROKEN | #35 - Application crashes |
| **Tool Accuracy** | ❌ BROKEN | #33, #34 - Wrong answers |
| **User Ready** | ❌ NO | 6/10 pass rate not acceptable |

---

## What's Live
- ✅ Outbound calls via HTTP POST to `https://api.niavoice.org/call`
- ✅ Session bridge (T3) — transcripts sync to OpenClaw sessions
- ✅ Streaming responses (PR #30 merged)
- ✅ Security: inbound disabled by default (PR #29)
- ⚠️ `ask_openclaw` tool — connects but gives wrong/broken answers

## What's Blocked
- **T4 (Inbound)** — Blocked until validation passes
- **Feature work** — All paused per DECISIONS.md

---

## Validation Test Log (Complete)

### Test 1 — 2026-02-05 16:54 GMT
- **Call ID:** CA92ea3d1410327ab19947a9429ceb8ed0
- **Scenario:** "What time is it?"
- **Voice:** ✅ Connected, no drops
- **Tool:** ⚠️ Wrong timezone (4+ hours off)
- **Issue:** #34

### Test 2 — 2026-02-05 ~16:55 GMT
- **Scenario:** "Check my calendar for today"
- **Voice:** ✅ Stable
- **Tool:** ❌ Hallucinated fake meetings
- **Issue:** #33

### Test 3 — 2026-02-05 ~16:58 GMT
- **Scenario:** "What's on my calendar and what's the weather?"
- **Voice:** ✅ Multi-tool stable
- **Tool:** ❌ Wrong location for weather
- **Issue:** #34

### Test 4 — 2026-02-05 (validation)
- **Scenario:** "Search for X then summarize"
- **Voice:** ✅ Connected
- **Tool:** ❌ Application error
- **Issue:** #35 (P0)

### Tests 5-10 — 2026-02-05 (validation)
- **Scenarios:** Conversational, long responses, rapid follow-up, interrupted, error recovery, extended
- **Voice:** ✅ All passed
- **Tool:** ✅ Worked (these didn't hit broken tools)

---

## Next Steps

1. **Spawn coder** for #35 (P0 application error) — IMMEDIATE
2. **Spawn coder** for #34 (timezone/location context) — after #35
3. **#33 may require OpenClaw core fix** — coordinate with Remi
4. **Re-run validation** after fixes

---

## Open Issues

| Issue | Description | Priority | Status |
|-------|-------------|----------|--------|
| **#35** | **Application error during web search** | **P0** | **OPEN - NEEDS FIX** |
| **#34** | **Wrong timezone and location context** | **P1** | **OPEN - NEEDS FIX** |
| **#33** | **Calendar hallucination** | **P1** | **OPEN - NEEDS FIX** |
| #31 | Reliability fixes | P0 | ✅ Fixed (PR #32) |
| #27 | Integration testing | P1 | TODO |

## Recent PRs

| PR | Status | Description |
|----|--------|-------------|
| #32 | ✅ Merged | P0 reliability: exponential backoff, 5s timeout, call_id logging |
| #30 | ✅ Merged | Streaming tool responses |
| #29 | ✅ Merged | Security: disable inbound by default |

---

## Infrastructure

- **Webhook Server:** port 8080 (webhook-server.py) — DO NOT MODIFY
- **Plugin Server:** port 8081
- **Session Bridge:** port 8082 (session-bridge.ts)
- **Public URL:** https://api.niavoice.org (cloudflare tunnel)
- **Twilio Number:** +1 440 291 5517

---

## Spawn Requests for Nia

### 1. Coder for #35 (P0 — Immediate)

```
You are Voice Coder.
FIRST: Read PROTOCOL.md, STATUS.md, DECISIONS.md in the repo.
TASK: Fix #35 - Application error during web search tool call.
- Add comprehensive try/catch around ask_openclaw tool execution
- Ensure graceful error handling for ALL tool failures
- Test with web search scenario
FINALLY: Update STATUS.md and create PR.
```

### 2. Coder for #34 (P1 — After #35)

```
You are Voice Coder.
FIRST: Read PROTOCOL.md, STATUS.md, DECISIONS.md in the repo.
TASK: Fix #34 - Tools receive wrong timezone/location.
- Check if Twilio provides caller context (timezone, location)
- Pass user context from voice session to ask_openclaw bridge
- Ensure tools receive and use context correctly
FINALLY: Update STATUS.md and create PR.
```

### 3. Note on #33

Calendar hallucination (#33) may require OpenClaw core changes, not voice skill fixes. Recommend Nia discuss with Remi whether calendar tool should validate connection state.
