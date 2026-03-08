# Voice Skill Decisions

Architectural and design decisions. **Don't revisit these without good reason.**

---

## 2026-03-08 22:21: Cycle 22 — Indie Hackers Launch Scheduled

**Decision:** Indie Hackers post scheduled for Mar 9 14:00 GMT+2 (16h from decision time).

**Why:**
- P0 blocker (Reddit/Dev.to) failed Mar 8 EOD deadline
- Backup channel drafts verified ready (Cycle 19-21)
- Mar 9 14:00 GMT+2 = optimal posting time (afternoon in US, evening in Europe)
- Gives Comms agent clear execution window
- Product Hunt launch remains scheduled for Mar 11 (Tuesday, optimal PH launch day)

**What This Means:**
- Comms agent to execute Indie Hackers post Mar 9 14:00 GMT+2
- Post will use draft from `INDIEHACKERS_POST_DRAFT.md`
- Monitor engagement for 7 days post-launch
- If Indie Hackers gains traction (>20 upvotes), proceed with Product Hunt Mar 11
- If Indie Hackers underperforms, still proceed with Product Hunt (different audience)

**Success Metrics:**
| Metric | Target | Notes |
|--------|--------|-------|
| Upvotes | 20+ | Strong signal |
| Comments | 5+ | Engagement quality |
| GitHub stars | +10 | Direct conversion |
| External calls | 1+ | Ultimate goal |

**Exit Criteria:**
- Post published and live on Indie Hackers
- Engagement tracked for 7 days
- External calls attributed (if any)
- Decision on Product Hunt launch (proceed regardless, but adjust messaging if needed)

---

## 2026-03-08 22:01: Cycle 21 — Backup Channel Drafts Verified Ready

**Decision:** Confirmed Indie Hackers + Product Hunt post drafts are complete and ready for Comms execution.

**Verification:**
- `INDIEHACKERS_POST_DRAFT.md` — Complete product launch post (title, content, target communities, posting instructions, success metrics)
- `PRODUCTHUNT_POST_DRAFT.md` — Complete PH launch package (tagline, description, hunter comment, launch checklist, timing recommendations)
- Both drafts require **no credentials** — browser-based posting only (GitHub OAuth for signup)

**Why:**
- P0 failure confirmed (Reddit/Dev.to credentials not in pass store, Mar 8 EOD deadline passed)
- Per DECISIONS.md 21:15 decision: execute backup channels immediately
- Cycle 21 verification confirms drafts are complete and actionable
- Comms agent can execute posts Mar 9 without additional preparation

**What This Means:**
- Next priority: Comms agent executes Indie Hackers + Product Hunt posts (Mar 9 EOD)
- No additional draft preparation needed
- Monitor engagement for 7 days post-publication
- Track GitHub stars and external calls attributed to channels

---

## 2026-03-08 21:15: P0 Failed — Backup Channels Activated

**Decision:** Reddit/Dev.to account creation P0 blocker FAILED (Mar 8 EOD deadline passed without credentials in pass store). **Activating backup channels per contingency plan:** Indie Hackers + Product Hunt + accelerated PinchSocial engagement.

**Why:**
- Mar 8 EOD deadline passed — Reddit client_id/client_secret NOT in pass store
- Mar 8 EOD deadline passed — Dev.to API key NOT in pass store
- 6+ days elapsed since P0 assigned, multiple escalations via Telegram topic 3
- Per DECISIONS.md (Mar 7): "If P0 fails (Reddit/Dev.to not executed): Immediate pivot to Indie Hackers + Product Hunt + accelerated PinchSocial engagement"
- Viability checkpoint is Mar 14 (6 days remaining) — cannot afford further delays

**What This Means:**
- Comms agent to execute Indie Hackers + Product Hunt posts immediately (Mar 9)
- PinchSocial engagement to be accelerated (daily engagement, not just post-and-wait)
- Email outreach monitoring continues (7-day window, ~65h elapsed)
- ctxly monitoring continues (follow-up sent, ~59h pending)
- No further waiting on Reddit/Dev.to — backup channels are now P0

**Exit Criteria:**
- At least 1 external call from backup channel execution
- Or: clear signal that backup channels also blocked
- Or: Mar 14 viability decision point

**Decision Rationale:** Distribution is the only bottleneck. Reddit/Dev.to were optimal but not executed. Indie Hackers + Product Hunt are viable alternatives with similar target audiences (indie devs, early adopters). Time is critical — 6 days until viability checkpoint.

---

## 2026-03-08 21:25: Cycle 19 — Backup Channel Drafts Prepared

**Decision:** Indie Hackers + Product Hunt post drafts created and ready for execution.

**Why:**
- P0 failure confirmed (Reddit/Dev.to credentials not in pass store)
- Per DECISIONS.md 21:15 decision: execute backup channels immediately
- Drafts prepared to unblock Comms agent execution (Mar 9)
- No credentials needed for these channels — browser-based posting only

**What Was Created:**
- `INDIEHACKERS_POST_DRAFT.md` — Product launch post for Indie Hackers forum (Products/Show & Tell)
- `PRODUCTHUNT_POST_DRAFT.md` — Full Product Hunt launch draft (tagline, description, hunter comment, timing, assets checklist)

**What This Means:**
- Comms agent can execute posts immediately (no additional prep needed)
- Indie Hackers: Sign up with GitHub OAuth, post to Products or Show & Tell
- Product Hunt: Sign up, prepare thumbnail (1200x630px), schedule for Mar 11 (Tuesday, 12:01 AM PST optimal)
- Both channels target same audience as Reddit/Dev.to (indie devs, early adopters)

**Success Metrics:**
| Channel | Upvotes/Points | Comments | GitHub Stars | External Calls |
|---------|---------------|----------|--------------|----------------|
| Indie Hackers | 20+ | 5+ | +10 | 1+ |
| Product Hunt | 50+ | 10+ | +25 | 3+ |

**Exit Criteria:**
- Posts published and monitored for 7 days
- Engagement tracked (upvotes, comments, GitHub stars)
- External calls attributed to channel (via user feedback or analytics)

---

## 2026-03-06: Distribution-Only Until First External Call (URGENT)

**Decision:** Zero feature work, zero technical improvements until we have at least 1 external user making a call. All effort goes to distribution via Reddit + Dev.to + ctxly.

**Why:**
- Day 28 with zero external calls. Product is reliable (97 tests passing) but invisible.
- Show HN failed (score=3, 0 comments after 19h). Cal.com Discussion stalled (emoji only).
- Reddit + Dev.to identified as P0 on Mar 1 — still not published 5+ days later.
- Market has hardened: ElevenLabs+Deloitte (enterprise closed), Retell G2 award + daily content (SEO domination), Vapi Claude Skills (DX moat widening).
- Without adoption signal by mid-March, project viability reassessment recommended.

**What This Means:**
- Spawn Comms immediately to execute Reddit + Dev.to posts (create accounts if needed)
- Submit to ctxly directory (first-mover voice category still available)
- Retry Shpigford email (his feedback was pre-Phase 2 fixes)
- No coder spawns, no QA spawns, no technical work of any kind

**Exit Criteria:**
- At least 1 external call made through the system
- Or: clear signal from distribution efforts that product needs changes
- Or: mid-March viability decision point

**Decision Rationale:** Technical work is complete. Distribution is the only bottleneck. Market window is narrowing — urgency is critical.

---

## 2026-03-07: Channel Verification — Email Only Available Today

**Finding:** Verified all distribution channels. Only **Email (AgentMail)** can execute TODAY without new credentials.

**Channel Status:**
| Channel | Status | Blocker |
|---------|--------|---------|
| Email (AgentMail) | ✅ Available | None — creds in pass |
| ctxly | ⏳ Pending | Manual review (18h+) |
| Reddit | ❌ Blocked | Need account creation (Remi) |
| Dev.to | ❌ Blocked | Need account creation (Remi) |
| Twitter | ❌ Blocked | Credentials expired (401) |
| Molthub | ❌ Blocked | Creds missing from pass |
| PinchSocial | ❌ Blocked | Creds missing from pass |

**Action:** Execute email outreach (Shpigford retry + Cal.com partnership) while waiting for Remi to create Reddit/Dev.to accounts. ctxly follow-up if not live by EOD.

---

## 2026-02-27: Outreach Over Everything — Zero Feature Work Until Users Exist

**Decision:** No new features, no technical work until we have at least 1 external user. All effort goes to marketing/outreach.

**Why:**
- Day 21 with zero external calls. The product works — nobody knows about it.
- Email creds exist (`pass show agentmail/api-key`) and were mistakenly flagged as blocked for a week.
- Cal.com outreach and Shpigford re-engagement emails are drafted and ready.
- Building more features without users is waste.

**What This Means:**
- Spawn Comms to execute email outreach (Cal.com pitch + Shpigford retry)
- Publish missed-call tutorial on available platforms
- No coder spawns until outreach generates feedback or adoption signals

**Exit Criteria:**
- At least 1 partnership response (Cal.com or similar)
- At least 1 external call made through the system
- Or: clear signal from outreach that product needs changes

---

## 2026-02-05: Reliability Over Features

**Decision:** All new feature work paused until reliability issues are fixed.

**Why:**
- Josh Pigford (@Shpigford) couldn't get voice working reliably, switched to Vapi
- This is existential — if users can't rely on the product, features don't matter
- Competitors (Vapi, Retell) are winning on "it just works"

**What This Means:**
- T4 (inbound), T6 (security), T7 (deploy) all paused
- #31 is the only active work item
- Code changes must improve reliability, not add features

**Metrics to Track:**
- Call success rate (target: >95%)
- Time to first response (target: <3s)
- WebSocket reconnection success rate

**Exit Criteria:**
- Complete #31 fixes
- 10 successful test calls with tool use
- No timeouts or connection drops in testing

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

## 2026-02-09: Voice PM Assessment - Support Market-First Strategy

**Decision:** Endorse shift to MARKET-FIRST execution for adoption phase

**Context:** 
- Phase 2 reliability work completed successfully (PRs #36-#41 merged)
- All technical blockers resolved, system validated at 10/10 pass rate  
- Competitive pressure increasing (ElevenLabs ElevenAgents launch)
- Proven ROI use case identified (missed-call → appointment flow)

**Assessment:** ✅ CORRECT STRATEGIC TIMING
- Technical foundation is now solid and reliable
- Building more features without adoption data is risky
- Missed-call use case has documented ROI ($47→$2,100 revenue lift)
- Shpigford reliability issues that caused churn have been fixed

**Voice PM Role in Market Phase:**
- Support creation of missed-call tutorial documentation  
- Assist BA with Shpigford re-engagement (technical credibility)
- Monitor adoption metrics and user feedback
- Maintain technical readiness for rapid iteration

**Decision Rationale:** Market timing critical. Technical capability now proven. Need user adoption data to guide future development priorities.

---

## 2026-03-07: PM Escalation — Reddit/Dev.to Account Creation (24h Deadline)

**Decision:** Escalate Reddit/Dev.to account creation to Remi via Telegram with explicit 24h deadline (Mar 8). No Comms/PM agent spawns until credentials available.

**Why:**
- 6+ days overdue, now 24h from viability-impacting deadline
- All distribution drafts ready (REDDIT_POST_DRAFT.md, DEVTO_POST_DRAFT.md)
- Only blocker is manual account creation + credential storage
- Mid-March viability checkpoint (7 days remaining) depends on this execution
- Email outreach sent but responses uncertain — Reddit/Dev.to are critical parallel channels

**What This Means:**
- PM will monitor ctxly (follow up EOD if not live)
- PM will track email responses (7-day window)
- No new agent spawns for distribution until Reddit/Dev.to credentials in pass store
- If Remi unavailable, Nia must intervene or viability at risk

**Exit Criteria:**
- Reddit client_id/client_secret in pass store
- Dev.to API key in pass store
- Comms agent can execute posts immediately after

---

## 2026-03-07 10:02: Cycle 5 Verification — P0 Blocker Persists

**Finding:** Reddit + Dev.to credentials still NOT in pass store. ctxly still returns 404 (~24h pending).

**Verification:**
```bash
pass show reddit/client_id    # → NOT FOUND
pass show devto/api-key       # → NOT FOUND
curl https://ctxly.com/services.json  # → 404
```

**Status:**
- P0 (Reddit/Dev.to): ❌ NOT DONE — Remi action required, deadline Mar 8 EOD
- P1 (ctxly): ⏳ PENDING — ~24h since submission, follow-up required EOD
- P2 (Email): ⏳ AWAITING — ~6h elapsed, 7-day response window

**Implication:** Distribution bottleneck remains critical. Only Email channel available. Viability checkpoint (Mar 14) at risk if Reddit/Dev.to not executed within 24h.

---

## Constraints (DO NOT VIOLATE)

- ⛔ **DO NOT modify webhook-server.py** — production code
- ⛔ **DO NOT modify Twilio/SIP/OpenAI Realtime code**
- ✅ Channel plugin should CALL existing services via HTTP
- ✅ Keep both old plugin AND new channel working in parallel until migration complete
