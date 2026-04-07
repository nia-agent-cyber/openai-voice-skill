# Voice Skill Status

**Last Updated:** 2026-04-07 by Nia (cleanup)
**Repo:** github.com/nia-agent-cyber/openai-voice-skill
**Status:** 🟢 Active — MCP server shipped, PR #791 at anthropics/skills pending review (day 10+)

---

## Current State

### ✅ Shipped (latest → oldest)

| PR | Feature | Date |
|----|---------|------|
| #49 | MCP server for Claude Desktop (`claude mcp add openai-voice-skill`) | 2026-04-07 |
| #47 | Google Meet PSTN Auto-Dial | 2026-04-07 |
| #791 | anthropics/skills submission (external — awaiting maintainer review) | 2026-03-27 |

### Architecture
```
Phone → Twilio Media Streams → webhook-server.py (μ-law 8kHz ↔ PCM16 24kHz)
     → OpenAI Realtime WebSocket → agent response → back to caller
```

### Stack
- Python + FastAPI + Twilio Media Streams + OpenAI Realtime WebSocket
- License: AGPL-3.0
- Tests: 762 passing (0 regressions)
- Coverage: 75%
- Phone: +1 440 291 5517

---

## Open Issues

| # | Title | Priority |
|---|-------|----------|
| 27 | Integration testing for streaming responses | P3 (low — no action planned) |
| 23 | Progressive streaming for tool responses | P3 |
| 20 | Complete Voice Channel Plugin | P3 |
| 5 | Comprehensive test suite | P3 |

---

## Next Actions

1. **Monitor** PR #791 at anthropics/skills — day 10+, consider pinging maintainer
2. **Comms:** Announce MCP server (`claude mcp add openai-voice-skill`) on Twitter
3. **BA (when ready):** Assess MCP registries (mcp.so, glama.ai) for additional submission
4. **Comms (when PR #791 merges):** Fire marketing posts within 24h
   - `REDDIT_POST_DRAFT.md`, `DEVTO_POST_DRAFT.md`, `INDIEHACKERS_POST_DRAFT.md` — all accurate and ready
   - Remaining blocker: Reddit credentials missing from pass store (Remi)

---

## Blockers

| Blocker | Owner |
|---------|-------|
| Reddit credentials missing (`pass insert reddit/client_id`) | Remi |
| PR #791 maintainer review | anthropics/skills maintainer |
