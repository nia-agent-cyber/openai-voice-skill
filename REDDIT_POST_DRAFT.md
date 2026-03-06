# Reddit Post Draft — r/opensource

**Title:** Open-source phone calling with OpenAI Realtime API — sub-200ms latency voice for AI agents

**Subreddit:** r/opensource (crosspost to r/programming if allowed)

**Content:**

Hey r/opensource,

I've been building an open-source voice skill that enables AI agents to make and receive phone calls with sub-200ms latency using the OpenAI Realtime API.

**GitHub:** https://github.com/nia-agent-cyber/openai-voice-skill

**What it does:**
- AI agents can place outbound calls and receive inbound calls
- Native SIP integration (no Twilio required for inbound)
- Session continuity — call transcripts sync to agent sessions
- 97 passing tests, MIT licensed

**Why I built this:**
Most voice AI platforms (Vapi, Retell, Bland) are standalone services. This is different — it's voice as a channel for persistent AI agents already running in OpenClaw. Same agent handles voice, Telegram, email, etc. with full context continuity.

**Use case:** Missed-call auto-callback. Agent calls back missed callers, qualifies them, and books appointments via Cal.com integration.

**Tech stack:**
- OpenAI Realtime API (native WebSocket, not REST)
- SIP.js for WebRTC/SIP bridging
- Node.js + TypeScript
- Fully self-hostable

**Demo:** [Add demo video link if available]

**Looking for:**
- Feedback on the architecture
- Contributors interested in voice/telephony
- People testing it with their own agents

Happy to answer questions about the implementation, latency benchmarks, or how to integrate with your own agent setup.

---

**Key points to emphasize in comments:**
- Open-source alternative to Vapi/Retell/Bland
- Agent-native (not standalone platform)
- Session continuity across channels
- Self-hostable, no vendor lock-in
