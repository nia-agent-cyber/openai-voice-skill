# Voice Skill Status

**Last Updated:** 2026-02-05 by Nia
**Repo:** github.com/nia-agent-cyber/openai-voice-skill

---

## Current State: ✅ CORE WORKING

### What's Live
- ✅ `ask_openclaw` tool — full pipeline working (Phone → Twilio → OpenAI Realtime → OpenClaw Agent → Voice)
- ✅ Outbound calls via HTTP POST to `https://api.niavoice.org/call`
- ✅ Session bridge (T3) — transcripts sync to OpenClaw sessions
- ✅ Streaming responses (PR #30 merged)
- ✅ Security: inbound disabled by default (PR #29)

### In Progress
- [ ] **#27** — Integration testing for streaming responses
- [ ] **T4** — Inbound Handler (phone → session creation)

### Blocked
*Nothing currently blocked*

---

## Next Steps (Priority Order)

1. **Test streaming in live call** — needs Remi
2. **#27** — Integration testing for streaming
3. **T4** — Inbound call handler
4. **T6** — Security allowlist enforcement (P2)
5. **T7** — Full E2E deployment testing

---

## Task Breakdown

| Task | Priority | Status | Description |
|------|----------|--------|-------------|
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
