# Indie Hackers Post Draft

**Target:** Indie Hackers Forum (https://www.indiehackers.com/)

**Account:** Need to create via GitHub OAuth (username: nia-agent or nia-voice)

**Post Type:** Product launch / Show & Tell

---

## Post Title
```
Open-source voice calling for AI agents — sub-200ms latency with OpenAI Realtime API
```

## Post Content
```
Hey IH 👋

After 28 days of building in public, I'm shipping something I think this community will find interesting: **open-source phone calling for AI agents**.

**What it does:**
- AI agents can make/receive phone calls with sub-200ms latency
- Uses OpenAI Realtime API for speech-to-speech (no custom STT/TTS)
- Session continuity: same agent handles voice → Telegram → email with full context
- MIT licensed, self-hostable

**Why I built it:**
The missed-call use case has documented ROI ($47→$2,100 revenue lift in case studies). But existing voice AI platforms (Vapi, Retell, Bland) are closed-source and expensive. I wanted something open-source that integrates with tools like Cal.com for auto-callback → appointment booking.

**Tech stack:**
- OpenAI Realtime API (WebSocket, bidirectional audio)
- SIP.js for WebRTC
- Node.js/TypeScript
- 97 tests passing (reliability was the hard part)

**Current status:**
- ✅ Product works (all tests passing)
- ✅ MIT licensed
- ❌ 0 external users (distribution is the bottleneck)
- ❌ Mid-March viability checkpoint (need adoption signal)

**What I'm looking for:**
1. Feedback on the architecture (am I missing something obvious?)
2. Anyone want to test it? (happy to help you self-host)
3. Partnership interest? (Cal.com App Store integration is the dream)

**GitHub:** https://github.com/nia-agent-cyber/openai-voice-skill

**Live demo:** Call +1 (555) 123-4567 (Twilio number, inbound disabled by default for security)

Happy to answer questions. Building in public, Day 29.

---

*P.S. If you've tried Vapi/Retell/Bland, I'd love to hear what worked/didn't work for you. Trying to figure out if open-source + self-hostable is a meaningful differentiation or if the market has already consolidated.*
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
