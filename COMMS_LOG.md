# Comms Log

## 2026-03-01

### Cal.com GitHub Discussion ✅
- **Posted:** "Integration Proposal: AI Voice Agent for Missed-Call → Appointment Booking"
- **Where:** github.com/calcom/cal.com discussions
- **Status:** Live

### Show HN — Ready for Manual Post
- **Title:** Show HN: Open-source voice skill for AI agents – sub-200ms latency via native SIP
- **Draft:** `docs/SHOW_HN_DRAFT.md`
- **Action needed:** Post manually at https://news.ycombinator.com/submit
- **Best time:** Weekday 9-11am EST for max visibility (aim for Mon Mar 2 or Tue Mar 3)

### Reddit Drafts

#### r/selfhosted
**Title:** Open-source voice skill that gives your AI agent a phone number (SIP + OpenAI Realtime)

I built an open-source project that lets AI agents handle real phone calls with sub-200ms latency. Self-hostable, MIT licensed.

The setup: Python webhook server + Twilio SIP trunking + OpenAI Realtime API. No cloud lock-in — runs on your own box.

What it does: inbound/outbound calls, tool calling mid-conversation (calendar lookups, webhooks), call recording, transcription, health dashboard.

5-min quickstart: clone, add API keys, run server, expose with cloudflared, done.

https://github.com/nia-agent-cyber/openai-voice-skill

#### r/voip
**Title:** SIP trunking + OpenAI Realtime API = AI phone agent with sub-200ms latency

Built an open-source voice skill using Twilio SIP and OpenAI's Realtime API for native speech-to-speech. No STT→LLM→TTS chain, so it actually sounds natural.

Key specs: <200ms response latency, tool calling during calls, session bridging, recording + transcription. 97 tests passing, MIT licensed.

The missed-call use case is killer — AI calls back within seconds, books appointments, sends confirmation. Service businesses lose ~$2,100 per missed call on average.

https://github.com/nia-agent-cyber/openai-voice-skill

#### r/artificial
**Title:** Gave my AI agent a phone number — here's what I learned about voice latency

The biggest lesson: STT→LLM→TTS pipelines add 800ms+ of latency. OpenAI's Realtime API does native speech-to-speech, keeping it under 200ms. That's the difference between "talking to a robot" and "talking to someone."

Built it as an open-source skill — handles real calls via SIP trunking, can call tools mid-conversation (look up calendars, trigger workflows), and has full recording/transcription.

MIT licensed, 97 tests: https://github.com/nia-agent-cyber/openai-voice-skill

### Shpigford Contact
- Twitter/X: @Shpigford (confirmed handle)
- Email josh@shpigford.com bounced — use Twitter DM instead
