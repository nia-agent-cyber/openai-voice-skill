# PRD: OpenClaw Integration for Voice Calls
**Status:** Draft  
**Author:** Nia  
**Date:** 2026-03-24  
**For:** Voice PM → Coder → QA

---

## Background

Voice calling works (v1.0.0-working, tagged 2026-03-24). Remi can call `+1 440 291 5517` or receive calls from Nia. The current implementation is functional but "dumb" — Nia loads static files (SOUL.md, MEMORY.md) at call start and has no live capabilities during the call.

**The gap:** During a call, Nia cannot look anything up, check project status, search her memory, or do anything beyond what was pre-loaded. She's essentially operating from a snapshot taken when the server started.

**The goal:** Nia on a voice call should feel like Nia in Telegram — same context, same capabilities, same intelligence. The call should be a first-class interaction mode, not a stripped-down one.

---

## Core Problems to Solve

### 1. Pre-Call: Context is Stale
Currently context is loaded once at server startup. If something changed since the server started (new memory, project update, recent Telegram conversation), Nia doesn't know about it.

**What we want:** Immediately before the call connects, run a fresh context fetch — pull latest memory, project statuses, recent activity. Remi picks up and Nia is already fully briefed.

### 2. During-Call: Zero Live Capabilities
Nia cannot look anything up mid-call. She can only discuss what's in her pre-loaded prompt.

**What we want:** Nia can use tools mid-call. Remi says "what's the status of Bakkt?" — Nia reads STATUS.md. Remi says "remind me about that at 3pm" — Nia creates a cron job.

### 3. Post-Call: Calls are Forgotten
Call transcripts are saved as JSON files in `memory/call-transcripts/` but never processed. The main session is never notified. Nia wakes up the next session with no knowledge a call happened.

**What we want:** After every call, Nia summarizes it, writes it to daily memory, and wakes the main session so she knows about it.

---

## Proposed Architecture

### Phase 1: Pre-Call + Post-Call (no latency risk)

**Pre-call briefing** (runs when call is initiated, before Remi picks up):
- Rebuild context fresh from disk (already mostly done — `build_call_prompt()` reads live files)
- Add: read `memory/heartbeat-state.json` for latest check timestamps
- Add: read last 3 call transcripts as brief summaries ("recent calls context")
- Add: query OpenClaw gateway for any pending cron jobs or active subagents

**Post-call handler** (runs when WebSocket closes):
- Summarize transcript using OpenAI chat completions (cheap, async, non-blocking)
- Write summary to `memory/YYYY-MM-DD.md` with call metadata (duration, turns, caller)
- Send wake event to OpenClaw gateway with the summary text
- Gateway wakes main session → Nia reads it on next heartbeat

Implementation notes:
- Summary call should be async and non-blocking (don't delay server cleanup)
- Use `gpt-4o-mini` for summarization (cheap, fast, doesn't need to be perfect)
- Wake event format: `POST /internal/wake` with `{"text": "Call with Remi ended. Summary: ..."}`

### Phase 2: Live Tools During Call (measured latency risk)

Use OpenAI Realtime's built-in tool/function calling. When Nia determines she needs to look something up, she calls a tool, the server executes it, and the result is injected back as a `conversation.item.create` before a new `response.create`.

**Tool execution flow:**
```
User speaks → Realtime STT → LLM decides to call tool
→ `response.function_call_arguments.done` event fires
→ server executes tool locally
→ `conversation.item.create` (type: function_call_output)
→ `response.create`
→ LLM responds with live data
```

---

## OpenClaw Tools — Ranked for Voice Integration

### Tier 1: Implement First (fast, high value, safe)

| # | Tool | Latency | Value | Notes |
|---|------|---------|-------|-------|
| 1 | `memory_search` | ~300ms | 🔥🔥🔥 | Semantic search of Nia's memory — most useful for "do you remember when..." |
| 2 | `read` (read_file) | <10ms | 🔥🔥🔥 | Read any workspace file. Covers MEMORY.md, STATUS.md, project files, etc. |
| 3 | `get_project_status` | <10ms | 🔥🔥🔥 | Thin wrapper: read `~/repos/{project}/STATUS.md`. Always relevant. |
| 4 | `memory_get` | <10ms | 🔥🔥 | Pull specific lines from memory files. Pairs with memory_search. |

### Tier 2: Implement Soon (acceptable latency, high value)

| # | Tool | Latency | Value | Notes |
|---|------|---------|-------|-------|
| 5 | `cron_create` | ~200ms | 🔥🔥🔥 | "Remind me at 3pm" during a call — huge UX win. Thin wrapper over cron tool. |
| 6 | `message_send` | ~200ms | 🔥🔥 | "Send me that link" — Nia sends a Telegram message while on call with Remi. |
| 7 | `sessions_send` | ~100ms | 🔥🔥 | Inject a note into the main session mid-call ("note for later: ..."). |
| 8 | `web_search` | ~800ms | 🔥🔥 | Factual lookups. Pair with filler phrase ("let me check that quickly..."). |

### Tier 3: Future / Optional

| # | Tool | Latency | Value | Notes |
|---|------|---------|-------|-------|
| 9 | `web_fetch` | ~1s | 🔥 | Fetch a specific URL if Remi mentions one. Slow but sometimes useful. |
| 10 | `exec` (scoped) | variable | 🔥 | `git status`, `ls`, safe read-only commands only. Never exec user input. |
| 11 | `sessions_spawn` | ~2s | 🔥 | Spawn a subagent for a complex background task during the call. Too slow for sync. |
| 12 | `image` (vision) | ~1s | 🔥 | Describe an image Remi might share. Async only. |

### Not Applicable for Voice

| Tool | Reason |
|------|--------|
| `write` / `edit` | Dangerous during live calls — no review loop |
| `gateway` | Dangerous |
| `browser` | Too slow (2-5s), not voice-appropriate |
| `canvas` | No display during voice calls |
| `nodes` | Not relevant |
| `tts` | Built into OpenAI Realtime already |
| `process` | Internal, not a call-facing tool |

---

## Implementation Plan

### Sprint 1: Post-Call Handler (3-4 hours)
1. Add `summarize_and_remember()` async function called from cleanup block
2. Use `gpt-4o-mini` chat completions to summarize transcript + call metadata
3. Append summary to `memory/YYYY-MM-DD.md`
4. POST wake event to OpenClaw gateway (`http://localhost:18789/internal/events/wake`)
5. Test: make a call, hang up, verify memory file updated and main session notified

### Sprint 2: Live Tool Framework (4-6 hours)
1. Implement tool dispatcher in `receive_from_openai()` for `response.function_call_arguments.done` events
2. Add tool registry dict (name → async handler function)
3. Implement Tier 1 tools: `memory_search`, `read_file`, `get_project_status`, `memory_get`
4. Add filler phrase mechanism: send `response.create` with "let me check..." before tool executes
5. Update `session.update` tools list with Tier 1 tools
6. Test: call and ask "what's the status of Bakkt?" — Nia should read STATUS.md live

### Sprint 3: Tier 2 Tools + Pre-Call Enrichment (2-3 hours)
1. Implement `cron_create`, `message_send`, `sessions_send` tool handlers
2. Pre-call: add last 3 call summaries to context (from `memory/call-transcripts/`)
3. Pre-call: add heartbeat state (last check timestamps)
4. Test: "remind me at 5pm", "send me that link" during a call

---

## Success Criteria

- [ ] After every call, a summary appears in `memory/YYYY-MM-DD.md` within 30s
- [ ] Main session receives wake event with call summary
- [ ] "What's the status of [project]?" during a call returns live STATUS.md data
- [ ] "Search your memory for [topic]" during a call returns relevant results
- [ ] "Remind me at 3pm" during a call creates a cron job that fires
- [ ] No tool call adds more than 1s of perceived silence (filler phrase covers it)
- [ ] No regressions to current working v1.0.0 behavior

---

## Constraints

- Do NOT add tools that execute arbitrary user-provided shell commands
- Do NOT use tools that could modify production config during a live call
- All tool handlers must have timeouts (max 3s — better to skip than to hang)
- Maintain backward compatibility with v1.0.0-working tag
- Test on actual calls with Remi before merging

---

## Open Questions for PM to Resolve

1. **Interruption model**: Should Remi be able to interrupt Nia mid-sentence? Currently disabled (mic muted while Nia speaks) to prevent echo. Re-enabling needs echo cancellation solution.
2. **Tool transparency**: Should Nia announce when she's using a tool ("let me check STATUS.md...") or just do it silently?
3. **Call history in context**: How many past call summaries to include in pre-call context? Suggest: last 3 calls, max 500 chars each.
4. **Gateway auth**: Need to confirm the gateway wake event endpoint and auth token format before Sprint 1.
