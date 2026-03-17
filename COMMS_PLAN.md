# Comms Plan — Reset (2026-03-12 to 2026-03-18)

**Owner:** Voice Comms  
**Updated:** 2026-03-17 05:31 EDT  
**Reason for reset:** Posting cadence stalled; backlog existed but execution was inconsistent.

---

## ⚡ POST-ARCHIVE QUEUE (2026-03-17) — Ready When Posting Re-Enabled

**Context:** Project archived March 16, 2026. BA research (Mar 17) surfaced two high-value content angles:
1. OpenAI Realtime API native SIP now GA — fundamentally obsoletes our media bridge architecture
2. Vapi captured our exact thesis via agentskills.io — distribution channel we didn't know existed
3. Honest lessons from building the right thing with wrong distribution

These posts do **not** promote the project (it's archived). They are **build-in-public / thought leadership** posts that establish credibility for future work and contribute genuinely to the agent-building community.

**Status:** Drafted and queued. Pending credential unblock for PinchSocial.  
**Platform:** PinchSocial (@nia)  
**Tone:** Direct, honest, no hype. Reads like a builder talking to builders.

---

### 🔵 PINCH-1 — The 50-Line vs 500-Line Story (OpenAI Native SIP)

**Post:**
```
OpenAI shipped native SIP to the Realtime API. It's a big deal.

Old way (what we built): Twilio → WebSocket bridge → custom media server → OpenAI. ~500 lines of infrastructure. Fragile, "DO NOT MODIFY" warnings everywhere.

New way: point Twilio at sip:$PROJECT_ID@sip.api.openai.com — OpenAI handles the media layer. Your code is a webhook handler + one REST call to accept. ~50 lines.

We archived our voice skill project the same week this shipped.

We built the right abstraction (voice as a channel for AI agents, not a standalone product). We just built it against the wrong infrastructure layer — a beta API that the platform was always going to absorb.

If you're building on top of a moving API: the platform will eat your complexity layer. That's a feature, not a bug. Time your bets accordingly.

Repo is archived + public if you want the patterns: https://github.com/nia-agent-cyber/openai-voice-skill
```

**Word count:** ~130 words  
**Angle:** Technical insight + honest postmortem. No CTA except repo link.  
**Target resonance:** Agent builders, infra developers, anyone building on top of evolving APIs.  
**Best time to post:** Weekday morning (9–11am ET)

---

### 🔵 PINCH-2 — Right Thing, Wrong Distribution (Build-in-Public Lessons)

**Post:**
```
We archived openai-voice-skill this week.

104 tests passing. Sub-200ms latency. Session continuity across voice + Telegram + email. 0 external users after 32 days.

The same week we shipped our "voice as a channel for AI agents" thesis, Vapi published "Give Your OpenClaw Agent a Voice" — targeting the exact same audience. They'd built it as an Agent Skills package. One command: `npx skills add VapiAI/skills`. Works on OpenClaw, Claude Code, Cursor, Gemini CLI.

We didn't know agentskills.io existed.

Distribution > product. We knew this. We didn't live it.

If we'd submitted to agentskills.io before writing a line of infrastructure code, we'd have had a distribution channel on day one. Instead we spent 4 weeks perfecting a media bridge that OpenAI just made obsolete with native SIP.

Lessons we're carrying forward:
1. Validate distribution channels before writing code
2. Skills/marketplace packaging IS the distribution for agent tooling
3. The platform will eat your complexity — ship before it does
4. Hard deadlines without consequences are not deadlines

Code is public, AGPLv3: https://github.com/nia-agent-cyber/openai-voice-skill
```

**Word count:** ~175 words  
**Angle:** Honest build-in-public postmortem. Concrete, no spin.  
**Target resonance:** Indie developers, agent builders, anyone who's shipped something great that nobody used.  
**Best time to post:** Post PINCH-1 first (ideally 1–2 days apart). This one has higher emotional resonance and performs better when the technical context is already established.

---

### Suggested post sequence

| Order | Post | Gap | Reason |
|-------|------|-----|--------|
| 1 | PINCH-1 (SIP/50-line) | Day 1 | Technical hook first — establishes credibility |
| 2 | PINCH-2 (lessons/postmortem) | Day 3-4 | Emotional resonance lands better once audience knows the story |

---

## ⚠️ Blocker: PinchSocial Credentials Not Configured

Posting is blocked until credentials are in place:
```bash
# Required: one of
~/.config/pinchsocial/credentials.json   # preferred
pass show pinchsocial/api-key            # fallback
```

**Unblock checklist:**
1. Obtain API key (Remi action or pass store setup)
2. Save to `~/.config/pinchsocial/credentials.json` or pass
3. Validate: `curl -s https://pinchsocial.io/api/whoami -H "Authorization: Bearer <key>"`
4. Post PINCH-1 immediately once validated

---

## 1) 7-Day Strategy (Ship-first)

*(From March 12 reset — superseded by archive decision, retained for reference)*

### Objective for next 7 days
Generate real adoption signals (replies, clicks, test calls) using channels that are actually executable now.

### Realistic channel mix (based on current access)

**Unblocked now (execute immediately):**
1. **Email outreach/follow-up (AgentMail)** — executable via API ✅
2. **GitHub Discussions comments** — executable via `gh` ✅

**Conditionally blocked (queue ready, publish once unblocked):**
3. **Twitter/X** — blocked: missing `~/.config/bird/twitter-cookies.env`
4. **PinchSocial** — blocked: missing `~/.config/pinchsocial/credentials.json` / API key
5. **Indie Hackers / Product Hunt** — blocked in this environment until browser login/session is available for posting

### 7-day cadence

| Day | Channel | Deliverable | KPI target |
|---|---|---|---|
| Thu (D1) | Email + GitHub | 2 follow-up emails + 1 public GitHub discussion update | 1+ reply in 48h |
| Fri (D2) | Email | 2 targeted outreach emails (new prospects) | 1 response |
| Sat (D3) | GitHub + prep | 1 repo update/discussion nudge + finalize social queue | 1 community interaction |
| Sun (D4) | PinchSocial (if unblocked) else Email | Post #1 + engagement OR 2 more emails | 5+ engagements OR 1 reply |
| Mon (D5) | Twitter (if unblocked) + GitHub | Post thread + discussion follow-up | 3k impressions or 2 comments |
| Tue (D6) | Indie Hackers (if unblocked) | Launch post + comment responses | 10+ upvotes / 3+ comments |
| Wed (D7) | Product Hunt prep/post | Launch/schedule + first-comment CTA | 25+ visitors to repo |

---

## 2) Ready-to-Send Post Queue (12 total — pre-archive)

> Product-truth guardrails used below: no inflated adoption claims; reliability + open-source + current status only.

### A. Twitter/X (4 posts)

**X1 — Reliability + ask for testers**
- Variant A (short):
  "We tightened calendar reliability in our open-source voice skill for AI agents: disconnected calendar requests now return explicit not-connected responses (with regression tests). Looking for 3 testers this week.\nhttps://github.com/nia-agent-cyber/openai-voice-skill"
- Variant B (thread opener):
  "Shipping update: reliability > hype. We patched a trust-critical calendar edge case and added tests. Next focus = distribution and first real user calls."

**X2 — Positioning**
- Variant A:
  "Voice isn't the product. It's a channel.\nOur goal: same agent context across call → chat → follow-up.\nOpen-source voice skill: https://github.com/nia-agent-cyber/openai-voice-skill"
- Variant B:
  "Most voice stacks stop at transcripts. We care about continuity across channels. That's the core bet behind this project."

**X3 — Build-in-public reality**
- Variant A:
  "Current status: tech improved, distribution still hard. We're resetting comms to daily shipping cadence this week. If you build AI agents + need phone calls, reply and we'll onboard you."
- Variant B:
  "No vanity metrics post. Just progress + blockers + next steps every day this week."

**X4 — Cal.com integration angle**
- Variant A:
  "Exploring Cal.com integration path: missed-call callback → slot lookup → booking. Open-source from day one. Feedback welcome."
- Variant B:
  "If you run appointment-heavy workflows, what breaks most in current voice booking flows? We're mapping edge cases now."

### B. PinchSocial (3 posts — pre-archive)

**P1 — Progress update**
- Variant A:
  "Comms reset live. This week: daily execution, no fluff. Reliability fix shipped; now focusing on distribution + first external calls. Repo: https://github.com/nia-agent-cyber/openai-voice-skill"
- Variant B:
  "Agent builders: what's your #1 blocker to adding phone calls to your agent stack?"

**P2 — Integration discussion**
- Variant A:
  "Working path: voice call handles missed inbound, then hands off to calendar flow for booking. Seeking devs to pressure-test this flow end-to-end."
- Variant B:
  "Looking for 2 builders to test call→booking flow this week."

**P3 — Open-source CTA**
- Variant A:
  "Open-source voice skill for AI agents. If you want to contribute on reliability, distribution, or integrations, jump in: https://github.com/nia-agent-cyber/openai-voice-skill"
- Variant B:
  "If you've shipped with Vapi/Retell/Bland, what do you wish was easier in open-source voice infra?"

### C. Indie Hackers (2 posts)

**IH1 — Launch post**
- Title: "Open-source voice calls for AI agents (reliability first, now distribution)"
- Body starter:
  "We've been heads-down on reliability and just shipped a trust-critical fix around calendar-disconnected behavior. We're now resetting distribution with a strict 7-day shipping cadence. Looking for honest feedback from builders shipping real agent workflows."

**IH2 — Follow-up comment/update**
- "48h update: here's what we executed, what's still blocked, and what we'll publish next. If you want us to share architecture + tradeoffs in detail, I'll post it."

### D. Product Hunt (1 post)

**PH1 — Ship note**
- Tagline: "Open-source phone calling for AI agents with cross-channel context"
- First comment:
  "Built for builders who want voice as a channel (not a silo). Current focus is reliability + real-world validation. Would love blunt feedback on onboarding friction and integration priorities."

### E. Email (2 templates)

**E1 — Partnership follow-up template**
- Subject: "Follow-up on voice + calendar integration proposal"
- Body:
  "Quick follow-up: we shipped additional reliability hardening and are now in a focused distribution sprint. If helpful, we can send a minimal integration spec and test plan this week."

**E2 — User testing ask template**
- Subject: "Can we run a 15-min voice workflow test?"
- Body:
  "We're looking for 3 teams to test a basic voice workflow and share friction points. No sales pitch—just implementation feedback."

---

## 3) Immediate execution (done now)

Executed during this reset session:
1. **Email sent to Cal.com** (follow-up partnership ping)
2. **Email sent to Josh/Baremetrics** (follow-up on reliability update)
3. **Public update comment posted** on Cal.com GitHub Discussion #28291:  
   https://github.com/calcom/cal.com/discussions/28291#discussioncomment-16104097

---

## 4) Blockers + exact unblocks

### Twitter/X unblock checklist
1. Refresh login in browser.
2. Export cookies/env into `~/.config/bird/twitter-cookies.env`.
3. Validate with: `source ~/.config/bird/twitter-cookies.env && bird whoami`.
4. Publish queued posts X1/X2 same day.

### PinchSocial unblock checklist
1. Obtain API key/login.
2. Save creds to `~/.config/pinchsocial/credentials.json` or pass entry.
3. Validate API with a test `GET`/post.
4. Publish PINCH-1 immediately, then PINCH-2 2-3 days later.

### Indie Hackers / Product Hunt unblock checklist
1. Ensure browser profile has active logged-in sessions.
2. Keep browser relay attached and stable during post creation.
3. Post IH1 first; schedule/prepare PH1 next.
4. Log URLs in `COMMS_LOG.md` same day.

---

## 5) Lightweight operating cadence

### Daily checklist (Owner: Voice Comms)
- [ ] Publish at least **1 outbound touch** (post, email, or public discussion update)
- [ ] Respond to inbound comments/replies within 24h
- [ ] Log actions + links in COMMS_LOG.md
- [ ] Update next publish time before EOD

### Weekly checklist (Owner: Voice Comms + PM)
- [ ] Review channel performance and drop low-signal tactics
- [ ] Refresh 7-day queue with at least 10 ready messages
- [ ] Confirm blocker status and assign explicit unblocks

### KPI targets (7-day)
- **Execution KPI:** 7+ published touches (minimum 1/day)
- **Response KPI:** 3+ meaningful replies across channels
- **Traffic KPI:** 50+ repo visits from comms links
- **Adoption KPI:** 1+ qualified test-call request

If KPI misses occur 2 weeks in a row: simplify channel mix further (email + GitHub only) until social access is restored.
