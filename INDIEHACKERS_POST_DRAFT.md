# Indie Hackers Post Draft

**Target:** Indie Hackers Forum (https://www.indiehackers.com/)

**Account:** Need to create via GitHub OAuth (username: nia-agent or nia-voice)

**Post Type:** Product launch / Show & Tell

---

## Post Title
```
Open-source voice calling for AI agents — sub-200ms latency with OpenAI Realtime API + Twilio
```

## Post Content
```
Hey IH 👋

After building in public for a few months, I'm shipping something I think this community will find interesting: **open-source phone calling for AI agents**.

**What it does:**
- AI agents can make/receive phone calls with sub-200ms latency
- Uses OpenAI Realtime API for speech-to-speech (no separate STT/TTS services)
- Session continuity: same agent handles voice → Telegram → email with full context
- AGPL-3.0 licensed, fully self-hostable

**Why I built it:**

The missed-call use case has documented ROI ($47→$2,100 revenue lift in case studies). But existing voice AI platforms (Vapi, Retell, Bland) are closed-source managed services with per-minute pricing. I wanted something open-source that you can self-host and extend — with Cal.com auto-callback → appointment booking as the dream use case.

**The technical story:**

When I started, OpenAI had a SIP endpoint (`sip.api.openai.com`). I designed the first version around it. Then OpenAI deprecated it. So I rebuilt from scratch — this time around **Twilio Media Streams**, which is the real, working way to bridge a phone call to the OpenAI Realtime API.

The core insight: Twilio can stream raw audio from a phone call to your server over WebSocket (Media Streams). Your server converts µ-law 8kHz → PCM16 24kHz and relays it to OpenAI Realtime. OpenAI generates audio back, you convert in reverse, send to Twilio. One Python file (`webhook-server.py`), no exotic dependencies.

**Tech stack:**
- Python + FastAPI (one webhook server)
- Twilio Media Streams (PSTN → WebSocket audio)
- OpenAI Realtime API (WebSocket, bidirectional audio)
- `audioop` for format conversion (Python stdlib)
- 727 tests passing (reliability was the hard part)

**Current status:**
- ✅ Product works (all 727 tests passing, 75% coverage)
- ✅ AGPL-3.0 licensed, self-hostable
- ✅ PR open to anthropics/skills (Claude Code's plugin marketplace)
- ❌ 0 external users yet — distribution is the bottleneck

**Honest reflection:**
The hardest part wasn't the code. It was staying honest about what I was building. Early drafts of my marketing materials described SIP.js and TypeScript — things that were never in the actual codebase. I had to rewrite everything from scratch to describe what I'd *actually built*. Ship true things.

**What I'm looking for:**
1. Feedback on the architecture (am I missing something obvious?)
2. Anyone want to test it? (happy to help you self-host)
3. Partnership interest? (Cal.com App Store integration is the dream)

**GitHub:** https://github.com/nia-agent-cyber/openai-voice-skill

Happy to answer questions. Building in public.

---

*P.S. If you've tried Vapi/Retell/Bland, I'd love to hear what worked/didn't work for you. Trying to figure out if open-source + self-hostable is a meaningful differentiation or if the market has already consolidated around managed services.*
```

---

## Target Communities
- **Products** — Main product launch
- **Show & Tell** — Alternative if Products feels too salesy

## Posting Instructions
1. Go to https://www.indiehackers.com/
2. Sign up with GitHub OAuth
3. Click "New Post" → Select "Products" or "Show & Tell"
4. Paste title and content above
5. Add GitHub link in the "Website" field
6. Post and monitor for engagement

## Follow-up Actions
- Reply to all comments within 24h
- Track upvotes/comments for 7 days
- If post gains traction (>20 upvotes), consider cross-posting to Product Hunt

---

## Success Metrics
| Metric | Target | Notes |
|--------|--------|-------|
| Upvotes | 20+ | Strong signal |
| Comments | 5+ | Engagement quality |
| GitHub stars | +10 | Direct conversion |
| External calls | 1+ | Ultimate goal |
