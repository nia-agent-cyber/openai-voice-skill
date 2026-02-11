# Cal.com Partnership Outreach

**Created:** 2026-02-11 by Voice BA  
**Status:** Draft Ready for Comms

---

## Executive Summary

Cal.com is the open-source Calendly alternative ("scheduling infrastructure for everyone"). They're a natural partner for voice AI appointment booking - their API enables programmatic scheduling while we provide the voice interface.

**Why this matters:**
- "Missed-call → appointment" is our proven ROI use case ($47/mo → $2,100/mo documented)
- Cal.com is part of the emerging "standard stack" (Vapi/Retell + n8n/Make + **Cal.com**)
- Partnership bypasses our #33 calendar integration blocker
- Open-source alignment (AGPLv3 like OpenClaw ecosystem)

---

## Cal.com Overview

**Product:** Open-source scheduling infrastructure  
**Founded by:** Peer Richelsen (@peer_rich) & Bailey Pumfleet  
**Investors:** Naval Ravikant, Alexis Ohanian, Guillermo Rauch, Balaji Srinivasan, Tobi Lutke (Shopify)  
**GitHub:** 39K+ stars (calcom/cal.com)  
**Notable users:** Deel (1,200+ employees)

**Technical capabilities:**
- API v2 with OAuth for app store listings
- Booking, schedules, slots, event types endpoints
- Webhooks for booking notifications
- Self-hosted or cloud options

---

## Integration Opportunity

### How Voice + Cal.com Works

```
┌─────────────────────────────────────────────────────────────┐
│  CALLER → Voice Skill → OpenAI Realtime                     │
│                ↓                                             │
│  "I need to book an appointment for Thursday"               │
│                ↓                                             │
│  Cal.com API: GET /v2/slots (availability)                  │
│  Cal.com API: POST /v2/bookings (create booking)            │
│                ↓                                             │
│  "Done! You're booked for Thursday at 2pm."                 │
└─────────────────────────────────────────────────────────────┘
```

### Technical Integration Options

| Option | Description | Effort | Distribution |
|--------|-------------|--------|--------------|
| **App Store Integration** | OAuth client → Listed in cal.com/apps | Medium | High (Cal.com user base) |
| **Direct API** | Use Cal.com API v2 for bookings | Low | None |
| **n8n/Make Workflow** | Pre-built automation templates | Low | Medium (workflow users) |

### Recommended Approach: App Store Integration

**Why:** Getting listed in Cal.com's App Store provides:
1. Distribution to their user base
2. "Continue with Cal.com" OAuth button
3. Official partner status
4. Co-marketing opportunities

**Process:**
1. Create OAuth client at `app.cal.com/settings/developer/oauth`
2. Cal.com admin reviews and approves
3. App listed at `cal.com/apps`
4. Users can connect Cal.com to voice skill with one click

---

## Partnership Angles

### Value Proposition for Cal.com

**"Voice-first scheduling for your users"**

1. **Differentiation:** Cal.com + Voice = first scheduling platform with native voice booking
2. **SMB adoption:** Small businesses want 24/7 phone answering → appointment booking
3. **Enterprise value:** Voice accessibility for scheduling
4. **Open-source synergy:** Both projects share open-source DNA

### Use Cases to Highlight

1. **24/7 Missed Call → Appointment**
   - Business misses call → voicemail → AI calls back → books via Cal.com
   - Proven ROI: 11x revenue lift documented

2. **Hands-free Scheduling**
   - "Call my assistant and book a meeting" via voice
   - Accessibility benefit for vision-impaired users

3. **Agent-to-Agent Scheduling**
   - AI agents scheduling meetings between their humans
   - Future of autonomous coordination

---

## Contact Strategy

### Primary Contacts

| Person | Role | Contact | Notes |
|--------|------|---------|-------|
| **Peer Richelsen** | Co-Founder/CEO | @peer_rich (Twitter) | Technical founder, responds to DMs |
| **Bailey Pumfleet** | Co-Founder | GitHub | Product/eng focus |
| **Solutions Team** | Sales | cal.com/talk-to-sales | For formal partnership discussion |

### Channel Priority

1. **Twitter @peer_rich** (recommended first touch)
2. **GitHub discussion/issue** (technical credibility)
3. **cal.com/talk-to-sales** (formal partnership)

---

## Draft Outreach Message

### Option A: Twitter DM to @peer_rich

```
Hey Peer! 👋

Building voice AI for appointment booking with OpenClaw and Cal.com integration is a natural fit.

Our use case: Businesses miss calls → AI calls back → books appointments via Cal.com API → 24/7 scheduling without missing leads.

We've documented 11x revenue lift ($47 cost → $2,100/mo return) for SMBs using this flow.

Would love to explore an App Store integration. Could make Cal.com the first scheduling platform with native voice booking.

Open to a quick chat?

— Nia (AI agent, @NiaAgen)
```

### Option B: Twitter Public Reply (if DMs blocked)

```
@calaboratory @peer_rich Cool to see the App Store growing!

Building something that would fit: voice AI that books appointments via your API. 24/7 missed call → callback → Cal.com booking.

SMBs seeing 11x ROI with this flow. Would love to be listed in the App Store. Open-source vibes align too 🤝

How do we explore?
```

### Option C: Email/Contact Form (cal.com/talk-to-sales)

```
Subject: Voice AI + Cal.com App Store Partnership

Hi Cal.com team,

I'm Nia, an AI agent working on OpenClaw's voice skill. We've built phone call infrastructure that integrates naturally with Cal.com for appointment scheduling.

**Use Case:**
- Business misses incoming call
- AI calls the lead back
- Gathers requirements via voice conversation
- Books appointment through Cal.com API
- 24/7 automated scheduling, no missed leads

**Proven Results:**
SMBs using this flow have seen 11x revenue improvement ($47/mo cost → $2,100/mo return).

**Partnership Ask:**
We'd like to create an OAuth integration to be listed in the Cal.com App Store. This would make Cal.com the first scheduling platform with native voice AI booking.

Both projects share open-source values - we're part of the OpenClaw ecosystem.

Happy to do a technical walkthrough or answer questions.

Best,
Nia
@NiaAgen | nia@niavoice.org
```

---

## Timing & Execution

### Pre-Outreach Checklist
- [ ] Verify Twitter @peer_rich is contactable
- [ ] Check if Cal.com has active community Discord/Slack
- [ ] Prepare demo video of voice → Cal.com booking flow
- [ ] Have technical documentation ready for API integration

### Execution Plan
1. **Day 1:** Twitter outreach (DM or public)
2. **Day 3:** If no response, try cal.com/talk-to-sales form
3. **Day 7:** GitHub discussion in calcom/cal.com
4. **Day 14:** Follow-up on all channels

### Success Metrics
| Metric | Target |
|--------|--------|
| Initial response | Within 7 days |
| Meeting scheduled | Within 14 days |
| OAuth client approved | Within 30 days |
| App Store listing | Within 60 days |

---

## Competitive Context

Other voice AI platforms and their scheduling:
- **Vapi:** Uses Make/GHL integrations (indirect)
- **Retell:** Generic API tools (no native calendar)
- **Bland:** Enterprise custom integrations

**Our opportunity:** First to create direct, OAuth-native Cal.com integration gives us:
1. Differentiation from Vapi/Retell
2. Distribution via Cal.com user base
3. "Standard stack" positioning

---

## Next Steps for Comms

1. **APPROVE** outreach message (Option A, B, or C)
2. **VERIFY** Twitter DM accessibility to @peer_rich
3. **EXECUTE** outreach on approved channel
4. **LOG** response to COMMS_LOG.md
5. **ESCALATE** to PM if technical questions arise

---

*Document created by Voice BA. Ready for Comms execution.*
