# Voice Skill Status

**Last Updated:** 2026-02-06 08:11 GMT by Voice PM
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
| **#35** | **P0** | Reliability | Application error during web search | **PR #36 — NEEDS REBASE** |
| **#34** | **P1** | Context | Wrong timezone and location passed to tools | **PR #37 — NEEDS REBASE** |
| **#33** | **P1** | Data Integrity | Calendar returns hallucinated data | Destroys user trust |

---

## 🔧 Fix Plan

### Phase 1: P0 Reliability (#35) — PR #36 QA APPROVED ✅

**Problem:** Test 4 ("Search for X then summarize") caused an application error.

**Root Cause (confirmed):**
- Insufficient try/catch coverage in `_handle_function_call`
- Streaming execution errors could propagate without graceful fallback
- `_send_function_result` failures could crash the handler

**Fix Applied (PR #36):**
1. ✅ Wrapped entire `_handle_function_call` in comprehensive try/except
2. ✅ Added `_send_function_result_safe` (no-throw version) for error handlers
3. ✅ Improved `_execute_streaming_function` to handle mid-stream errors gracefully
4. ✅ Enhanced `_execute_function` with specific error handling for timeouts, execution errors
5. ✅ Added 8 unit tests for error handling scenarios (all 37 tests passing)

**QA Review:** APPROVED (2026-02-06 06:47 GMT)
- Code changes appropriately scoped
- Tests comprehensive and passing
- PR rebased and mergeable
- Ready for PM review and merge

---

### Phase 2: P1 Context (#34) — PR #37 QA APPROVED ✅

**Problem:** Tools receive no user context (timezone, location).
- Time tool returned 14:15 when user's local time was 18:59 (4+ hour diff)
- Weather returned wrong location data

**Root Cause (confirmed):**
- Voice session didn't pass user timezone/location to OpenClaw
- Tools defaulted to UTC or server location

**Fix Applied (PR #37):**
1. ✅ New `user_context.py` - Resolves timezone/location from phone number (50+ country codes)
2. ✅ New `call_context_store.py` - Shared storage for call context
3. ✅ Updated `openclaw_executor.py` - Injects `[CALLER CONTEXT: ...]` prefix
4. ✅ Updated `realtime_tool_handler.py` - Passes context to executor
5. ✅ Minimal changes to `webhook-server.py` - Stores/clears call context

**QA Review:** APPROVED (2026-02-06 06:59 GMT)
- Code changes appropriately scoped
- Phone numbers properly masked in logs
- All tests passing (29/29)
- PR rebased and mergeable
- Ready for PM review and merge

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

1. ✅ **PR #36** (P0 #35 error handling) — QA approved, ready for PM review and merge
2. ✅ **PR #37** (P1 #34 timezone/location) — QA approved, ready for PM review and merge
3. **#33 may require OpenClaw core fix** — coordinate with Remi
4. **Re-run validation** after PRs merged

---

---

## Open Issues

| Issue | Description | Priority | Status |
|-------|-------------|----------|--------|
| **#35** | **Application error during web search** | **P0** | **PR #36 — NEEDS REBASE** |
| **#34** | **Wrong timezone and location context** | **P1** | **PR #37 — NEEDS REBASE** |
| **#33** | **Calendar hallucination** | **P1** | **OPEN - NEEDS FIX** |
| #31 | Reliability fixes | P0 | ✅ Fixed (PR #32) |
| #27 | Integration testing | P1 | TODO |

## Recent PRs

| PR | Status | Description |
|----|--------|-------------|
| **#37** | **⚠️ CONFLICTS** | Fix #34: Pass user timezone/location context to tools |
| **#36** | **⚠️ CONFLICTS** | Fix #35: Comprehensive error handling for ask_openclaw |
| #32 | ✅ Merged | P0 reliability: exponential backoff, 5s timeout, call_id logging |
| #30 | ✅ Merged | Streaming tool responses |
| #29 | ✅ Merged | Security: disable inbound by default |

---

## PM Review (2026-02-06 08:11 GMT)

### PR #36 (Issue #35 - Error Handling) 
- ✅ Code meets issue requirements
- ✅ QA approved (2026-02-06 06:47)
- ❌ **MERGE CONFLICTS** — needs rebase before merge
- **Action:** Posted changes requested on PR

### PR #37 (Issue #34 - Timezone/Location)
- ✅ Code meets issue requirements  
- ✅ QA approved (2026-02-06 06:59)
- ❌ **MERGE CONFLICTS** — needs rebase before merge
- **Action:** Posted changes requested on PR

### Next Steps
1. **Spawn Voice Coder** to rebase both PRs on main
2. After rebase, verify mergeable and approve for merge
3. Coordinate with Remi on #33 (calendar hallucination)

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
