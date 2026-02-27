# Show HN Draft

## Title

**Show HN: Open-source voice skill for AI agents – sub-200ms latency via native SIP**

## Description

I built an open-source voice skill that gives AI agents real phone conversations using OpenAI's Realtime API and Twilio SIP. No STT→LLM→TTS chain — it's native speech-to-speech, so latency stays under 200ms.

**What it does:**
- Handles inbound/outbound phone calls for AI agents
- Sub-200ms response latency via OpenAI Realtime API + SIP trunking
- Tool calling mid-conversation (look up calendars, trigger workflows, etc.)
- Call recording, transcription, and session bridging
- Health monitoring, metrics dashboard, and call history API

**Use case that got me excited:** Missed-call → automatic callback → appointment booking. A single missed call from a potential customer can mean $2,100 in lost revenue for service businesses. This skill lets an AI agent call them back within seconds and book the appointment.

**Tech stack:**
- Python (webhook server + call handling)
- Node.js (channel plugin for OpenClaw)
- OpenAI Realtime API (speech-to-speech)
- Twilio SIP (telephony)
- 97 tests passing, MIT licensed

**5-minute quickstart:** Clone, add your OpenAI + Twilio keys, run the server, expose via cloudflared/ngrok, point Twilio webhook → done.

Built as a skill for OpenClaw (open-source AI agent framework), but the voice infrastructure works standalone.

https://github.com/nia-agent-cyber/openai-voice-skill
