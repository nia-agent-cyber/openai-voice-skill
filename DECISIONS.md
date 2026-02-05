# Voice Skill Decisions

Architectural and design decisions. **Don't revisit these without good reason.**

---

## 2026-02-04: ask_openclaw WebSocket Fix

**Decision:** Tool handler connects to sideband WebSocket, not new session

**Bug Found:** Tool handler was connecting to wrong endpoint:
- ❌ WRONG: `wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview` (new empty session)
- ✅ FIXED: `wss://api.openai.com/v1/realtime?call_id={call_id}` (existing call's sideband)

**Commit:** 983dc4bc

---

## 2026-02-04: Session Bridge Architecture (T3)

**Decision:** Post-call transcript sync instead of real-time interception

**Why:** 
- webhook-server.py uses OpenAI Realtime for end-to-end voice (STT → LLM → TTS)
- Intercepting mid-conversation would require modifying webhook-server.py
- Constraint: DO NOT modify webhook-server.py

**Architecture:**
```
webhook-server.py → call_recording.py → Session Bridge (8082) → OpenClaw Session
```

**Result:** Voice transcripts appear in OpenClaw session history. Cross-channel continuity works.

---

## 2026-02-04: Disable Inbound Calls by Default

**Decision:** Security fix — inbound calls disabled unless explicitly enabled

**Why:** Anyone could call the Twilio number and interact with the agent. Need allowlist enforcement first.

**Result:** PR #29 merged. Inbound requires explicit config to enable.

---

## 2026-02-04: Code Sync Discipline

**Decision:** Commit working code IMMEDIATELY after testing

**Why:** PR #16 had untested `voice` parameter that broke production.

**Rules:**
1. Commit working code immediately after testing
2. PM: Never add untested changes
3. QA: Verify PR matches tested code exactly
4. Deployer: Test after deploy before marking complete

---

## 2026-02-03: Use OpenAI Realtime (not custom STT/TTS)

**Decision:** Let OpenAI Realtime handle speech-to-speech, use `ask_openclaw` tool for agent capabilities

**Why:**
- OpenAI Realtime provides low-latency voice experience
- Custom STT → Agent → TTS would add latency
- Tool calling allows accessing OpenClaw agent when needed

**Result:** Best of both worlds — fast voice UX + full agent capabilities via tool

---

## Constraints (DO NOT VIOLATE)

- ⛔ **DO NOT modify webhook-server.py** — production code
- ⛔ **DO NOT modify Twilio/SIP/OpenAI Realtime code**
- ✅ Channel plugin should CALL existing services via HTTP
- ✅ Keep both old plugin AND new channel working in parallel until migration complete
