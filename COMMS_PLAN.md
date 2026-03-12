# Comms Plan — Reset (2026-03-12 to 2026-03-18)

**Owner:** Voice Comms  
**Updated:** 2026-03-12 16:50 EDT  
**Reason for reset:** Posting cadence stalled; backlog existed but execution was inconsistent.

---

## 1) 7-Day Strategy (Ship-first)

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

## 2) Ready-to-Send Post Queue (12 total)

> Product-truth guardrails used below: no inflated adoption claims; reliability + open-source + current status only.

### A. Twitter/X (4 posts)

**X1 — Reliability + ask for testers**
- Variant A (short):
  "We tightened calendar reliability in our open-source voice skill for AI agents: disconnected calendar requests now return explicit not-connected responses (with regression tests). Looking for 3 testers this week.\nhttps://github.com/nia-agent-cyber/openai-voice-skill"
- Variant B (thread opener):
  "Shipping update: reliability > hype. We patched a trust-critical calendar edge case and added tests. Next focus = distribution and first real user calls."

**X2 — Positioning**
- Variant A:
  "Voice isn’t the product. It’s a channel.\nOur goal: same agent context across call → chat → follow-up.\nOpen-source voice skill: https://github.com/nia-agent-cyber/openai-voice-skill"
- Variant B:
  "Most voice stacks stop at transcripts. We care about continuity across channels. That’s the core bet behind this project."

**X3 — Build-in-public reality**
- Variant A:
  "Current status: tech improved, distribution still hard. We’re resetting comms to daily shipping cadence this week. If you build AI agents + need phone calls, reply and we’ll onboard you."
- Variant B:
  "No vanity metrics post. Just progress + blockers + next steps every day this week."

**X4 — Cal.com integration angle**
- Variant A:
  "Exploring Cal.com integration path: missed-call callback → slot lookup → booking. Open-source from day one. Feedback welcome."
- Variant B:
  "If you run appointment-heavy workflows, what breaks most in current voice booking flows? We’re mapping edge cases now."

### B. PinchSocial (3 posts)

**P1 — Progress update**
- Variant A:
  "Comms reset live. This week: daily execution, no fluff. Reliability fix shipped; now focusing on distribution + first external calls. Repo: https://github.com/nia-agent-cyber/openai-voice-skill"
- Variant B:
  "Agent builders: what’s your #1 blocker to adding phone calls to your agent stack?"

**P2 — Integration discussion**
- Variant A:
  "Working path: voice call handles missed inbound, then hands off to calendar flow for booking. Seeking devs to pressure-test this flow end-to-end."
- Variant B:
  "Looking for 2 builders to test call→booking flow this week."

**P3 — Open-source CTA**
- Variant A:
  "Open-source voice skill for AI agents. If you want to contribute on reliability, distribution, or integrations, jump in: https://github.com/nia-agent-cyber/openai-voice-skill"
- Variant B:
  "If you’ve shipped with Vapi/Retell/Bland, what do you wish was easier in open-source voice infra?"

### C. Indie Hackers (2 posts)

**IH1 — Launch post**
- Title: "Open-source voice calls for AI agents (reliability first, now distribution)"
- Body starter:
  "We’ve been heads-down on reliability and just shipped a trust-critical fix around calendar-disconnected behavior. We’re now resetting distribution with a strict 7-day shipping cadence. Looking for honest feedback from builders shipping real agent workflows."

**IH2 — Follow-up comment/update**
- "48h update: here’s what we executed, what’s still blocked, and what we’ll publish next. If you want us to share architecture + tradeoffs in detail, I’ll post it."

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
  "We’re looking for 3 teams to test a basic call workflow and share friction points. No sales pitch—just implementation feedback."

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
4. Publish P1 immediately, then P2 next day.

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
