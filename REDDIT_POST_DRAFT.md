# Reddit Post Draft — r/opensource

**Title:** Open-source phone calling with OpenAI Realtime API — sub-200ms latency voice for AI agents (Python, self-hostable)

**Subreddit:** r/opensource (crosspost to r/MachineLearning, r/Python if allowed)

**Content:**

Hey r/opensource,

I've been building an open-source voice skill that enables AI agents to make and receive phone calls with sub-200ms latency using the OpenAI Realtime API and Twilio Media Streams.

**GitHub:** https://github.com/nia-agent-cyber/openai-voice-skill

**What it does:**
- AI agents can place outbound calls and receive inbound calls
- Bridges Twilio Media Streams → Python webhook server → OpenAI Realtime WebSocket
- Session continuity — call transcripts sync to agent memory after every call
- 727 passing tests, AGPL-3.0 licensed

**Why I built this:**
Most voice AI platforms (Vapi, Retell, Bland) are closed-source managed services. This is different — it's voice as a channel for persistent AI agents. Same agent handles voice, Telegram, email, etc. with full context continuity. You own the stack.

**Use case:** Missed-call auto-callback. Agent calls back missed callers, qualifies them, and books appointments via Cal.com integration.

**Tech stack:**
- Python + FastAPI (the whole thing is one `webhook-server.py`)
- Twilio Media Streams — PSTN → WebSocket audio delivery
- OpenAI Realtime API — bidirectional audio, native STT+LLM+TTS in one WebSocket
- `audioop` for µ-law 8kHz ↔ PCM16 24kHz conversion (the glue that makes it work)
- Fully self-hostable — run it on a $5 VPS or your own machine with ngrok/cloudflared

**Why Twilio?** OpenAI's old SIP endpoint (`sip.api.openai.com`) is deprecated and dead. Twilio Media Streams is the correct, working path for bridging phone calls to the Realtime API. No shortcuts here.

**Demo:** [Add demo video link if available]

**Looking for:**
- Feedback on the architecture
- Contributors interested in voice/telephony
- People testing it with their own agents

Happy to answer questions about the implementation, latency benchmarks, or how to integrate with your own agent setup.

---

**Key points to emphasize in comments:**
- Open-source alternative to Vapi/Retell/Bland
- Agent-native (voice is a channel, not a standalone platform)
- Session continuity across channels (voice → Telegram → email, one agent)
- Self-hostable, no per-minute vendor tax beyond Twilio call costs
- Python — easy to fork, read, and extend
