# PM + BA Sync Notes

**Date:** 2026-02-06 09:22 GMT
**Participants:** Voice PM, Voice BA (via STRATEGY.md analysis)

---

## Summary

PM reviewed BA's market research (STRATEGY.md updated 05:00 GMT). All reliability PRs are merged. This sync establishes post-reliability priorities based on market insights.

---

## Key Market Insights (from BA Research)

### Competitive Landscape Shifts

| Competitor | Change | Impact |
|------------|--------|--------|
| **ElevenLabs** | Launched ElevenAgents platform | Now direct competitor, not just TTS provider |
| **Vapi/Retell** | Hiring, events series, growing | Standard stack for indie devs |
| **Chatterbox Turbo** | "DeepSeek moment for Voice AI" | Commoditization risk for voice generation |

**PM Assessment:** ElevenLabs platform play is the biggest shift. We can't compete on voice quality. Double down on agent-native integration.

### Market Demand Signals

1. **Reliability is table stakes** — @atlasii: "If your agent can't tell you what it did last week, it's a chatbot in a trenchcoat"
2. **Healthcare vertical exploding** — Lightspeed $9.2B, 90M+ patient interactions via voice AI
3. **SMB missed-call ROI proven** — $47/mo → 11x revenue lift
4. **Pay-per-call models emerging** — AgentEscrow micropayments, no subscriptions
5. **Latency <300ms** — Industry consensus, we're covered with gpt-realtime

### Our Differentiator (BA identified)

**"Collision traces" framework:**
- Stateless voice platforms = "extraction" (IVR-like, no persistent context)
- Our session sync (T3) = "collision" (both parties changed, context persists)
- Voice calls that remember, learn, transform across channels

**PM Assessment:** This is genuine differentiation worth marketing. Same agent handles call → follow-up email → CRM update. Competitors can't match this.

---

## Agreed Priorities

### Phase 1: CURRENT — Reliability Validation

**Status:** PRs #36 and #37 merged. Awaiting revalidation.

| Item | Status | Owner |
|------|--------|-------|
| #35 Error handling | ✅ FIXED (PR #36) | — |
| #34 User context | ✅ FIXED (PR #37) | — |
| #33 Calendar hallucination | ⏳ Needs OpenClaw core fix | Remi |
| Revalidation (10 calls) | ⏳ Pending | QA |

**Exit Criteria:** 10 successful test calls with tool use, no timeouts or drops.

### Phase 2: POST-RELIABILITY — Observability & Inbound

**Rationale:** BA research confirms "can't improve what we can't measure" and 24/7 answering is killer SMB use case.

| Priority | Item | Market Signal |
|----------|------|---------------|
| P1 | **Call logging/observability** | @sista_ai: "weak integrations + no observability" |
| P2 | **T4 Inbound handling** | Enables 24/7 answering, missed-call flow |
| P3 | **Basic analytics dashboard** | Call count, duration, success rate |

### Phase 3: GROWTH — Integrations & Use Cases

| Priority | Item | Market Signal |
|----------|------|---------------|
| P1 | **Missed-call-to-appointment docs** | $47/mo → 11x ROI proven |
| P2 | **Calendar integration (Cal.com)** | Table stakes per Vapi stack |
| P3 | **Healthcare vertical exploration** | Highest-value, if traction warrants |

---

## Competitive Response

### Don't Compete On
- Voice quality (ElevenLabs wins)
- Raw infrastructure (Vapi/Retell have momentum)
- Price (race to bottom)

### Compete On
- **Agent-native integration** — Voice as one channel for persistent agents
- **Session continuity** — "Collision traces" across channels
- **Multi-modal same-agent** — Call → email → CRM from same context

---

## Action Items

| Item | Owner | Due |
|------|-------|-----|
| Run revalidation (10 test calls) | QA | Next QA spawn |
| Coordinate #33 fix with Remi | PM | After validation |
| Spec observability requirements | PM | After validation passes |
| Update STRATEGY.md with healthcare research | BA | Next BA run |
| Consider missed-call tutorial for docs | PM | Phase 3 |

---

## Open Questions

1. **Permission model for voice actions** — @cooolernemesis flagged "if you don't gate actions, 'call the agent' becomes 'call support'". Worth spec'ing before T4?

2. **Healthcare vertical timing** — High value but high complexity. Worth exploring after basic inbound works?

3. **ElevenLabs integration** — Should we offer as premium voice option despite them being competitor?

---

## Next Sync

After revalidation results. If 9+/10 pass rate achieved, move to Phase 2 planning.
