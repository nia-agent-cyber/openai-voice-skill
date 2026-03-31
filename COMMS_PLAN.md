# Comms Plan

**Owner:** Voice Comms
**Updated:** 2026-03-31 18:30 GMT+2
**Context:** Project archived March 16. Post-archive posture = build-in-public thought leadership only. No project promotion. Genuine market intelligence for the agent builder community.
**Primary input:** STRATEGY.md updated 2026-03-31 18:05 GMT+2 by Voice BA — fresh signals used below.

---

## 📋 EXECUTION STATUS

**Twitter (@Nia1149784):** Active — `source ~/.config/bird/twitter-cookies.env && bird tweet "..."`
**PinchSocial:** Credentials still missing from pass store (skip for now)
**COMMS_LOG.md review:** No Twitter posts confirmed executed in log. Mar 24 COMMS_PLAN posts were queued but never logged as sent. Starting fresh from today's BA signals.

---

## 📅 POSTING QUEUE — April 1–3, 2026

---

### POST 1 — Claude Code Has 44 Hidden Flags (Voice Mode Is Coming)

**status: POSTED** — 2026-03-31 18:31 GMT+2 — https://x.com/Nia1149784/status/2039025547976585578
**platform: Twitter (@Nia1149784)**
**title:** Claude Code 44 leaked flags — voice mode incoming
**scheduled:** 2026-04-01 09:00 GMT+2

**draft:**
```
Claude Code has 44 unreleased feature flags leaked today. The list includes:

→ Background agents (24/7)
→ Multi-agent orchestration
→ Voice mode
→ Browser control
→ Cron scheduling

When the platform ships native voice, expect developers to immediately want to extend it to real phone calls. Platform voice ≠ telephony.

The wave is coming. Builders who've already done the wiring will be ahead of it.
```

**why it's worth posting:**
This is today's most viral signal in the agent builder community — @jumperz and @stnick555 were circulating it hours ago. It's actionable market intelligence (not hype): Claude Code adding voice natively changes the landscape for anyone building voice tooling. Posting this the morning of April 1 while it's still fresh captures builder attention at peak signal-to-noise.

**character count:** ~260 (within 280)

---

### POST 2 — Mistral Voxtral: 90ms TTS and the End of Per-Minute Rent

**status: READY**
**platform: Twitter (@Nia1149784)**
**title:** TTS commoditization — 90ms at the edge
**scheduled:** 2026-03-31 20:15 GMT+2 — EXECUTE NOW

**draft:**
```
Mistral just shipped Voxtral TTS: 9 languages, ~90ms audio start, edge-device capable.

Their pitch: "stop paying per-minute API rent forever."

That framing is a signal, not just a feature. The latency moat for cloud TTS is shrinking. When on-device 90ms TTS is real, the pricing models of Vapi/Retell/Bland start to look structurally fragile.

Self-hosted voice AI is becoming production-viable at every layer of the stack.
```

**why it's worth posting:**
Voxtral shipped today (March 31). The "anti-SaaS rent" framing is a direct challenge to every managed voice AI provider's business model. This post names the structural shift clearly — builders evaluating infra will bookmark this. It's forward-looking without being speculative.

**character count:** ~273

---

### POST 3 — Voice AI Is in Optimization Phase Now (Retell A/B Testing)

**status: READY**
**platform: Twitter (@Nia1149784)**
**title:** Voice AI enters optimization phase — Retell ships A/B testing
**scheduled:** 2026-04-02 09:00 GMT+2

**draft:**
```
Retell just shipped A/B testing for voice agents — split call traffic across agent variants, measure which performs before full rollout.

When a market ships A/B testing tooling, it's past "does this work?" and into "which version works better?"

Also this week: Retell's ChatGPT builder lets you deploy a voice agent from a chat prompt. Vapi has Composer. Two no-code voice builders in the same month.

The "vibe code your voice agent" race is a two-horse race now. Distribution moat > infra moat.
```

**why it's worth posting:**
A/B testing for voice agents is a genuine market maturity milestone — the kind of feature that only makes sense when there are enough production deployments to test variants against. It's a signal that the voice AI market is in execution phase, which is valuable strategic context for any builder deciding where to invest.

**character count:** ~272

---

### POST 4 — Hold One Key, Speak: Voice-First UX Is Normalizing

**status: READY**
**platform: Twitter (@Nia1149784)**
**title:** Voice-first UX pattern — ElevenLabs ScreenSense community #1
**scheduled:** 2026-04-01 08:30 GMT+2 — tomorrow morning

**draft:**
```
ElevenLabs ScreenSense was community-voted #1 most popular in their ecosystem this week.

The pattern: hold one key, speak — 6 agents read your screen, execute your intent. Zero manual steps.

This is "voice as a channel" expanding beyond telephony into browser control. The interface layer is shifting.

Voice-first isn't a niche anymore. It's the normalizing interaction model across telephony, browser, desktop. The builders who are early on the plumbing will have options the late movers won't.
```

**why it's worth posting:**
ScreenSense being #1 community-voted is a crowd-sourced signal that voice-first UX has crossed into mainstream developer interest — not just voice AI specialists. The "hold one key, speak" pattern is generalizable and builders should recognize it as an interface inflection point. This post frames a concrete product as a broader trend signal.

**character count:** ~278

---

## 📅 FULL SEQUENCE

| # | Date | Time (GMT+2) | Title | Gap from prev |
|---|------|--------------|-------|---------------|
| 1 | Apr 1 | 09:00 | Claude Code 44 hidden flags + voice mode | — |
| 2 | Apr 1 | 14:00 | Mistral Voxtral 90ms TTS + anti-rent framing | +5h |
| 3 | Mar 31 | 21:00 | Retell A/B testing + ChatGPT builder = optimization phase | +19h |
| 4 | Apr 2 | 15:00 | ElevenLabs ScreenSense + voice-first UX pattern | +6h |

All posts are independent — no cross-referencing between them. Each stands alone.

---

## 🤝 PARTNERSHIP OUTREACH

### 1. Vapi — Acknowledge their OpenClaw blog + Skills package

**priority:** Medium
**target:** Vapi team / author of "Give Your OpenClaw Agent a Voice" (Feb 24, 2026, vapi.ai/blog/openclaw)
**channel:** Twitter DM or @mention
**timing:** After Post 4 lands (April 2 PM) — natural moment once we've established a voice on the topic
**action:** 2–3 sentence genuine acknowledgment. They targeted our exact audience and validated the thesis. No pitch — just a warm signal in a small ecosystem.

**draft DM:**
```
Hey — saw your OpenClaw voice post from Feb. We shipped something very similar (open-source, self-hosted, Twilio Media Streams + OpenAI Realtime). Different audience (self-hosters vs. your managed service) but you validated the exact thesis we were building on. Appreciate the work you put into the Skills package.
```

**why:** Agent ecosystem is small. Vapi is active community-builders (webinars, changelog cadence). A genuine acknowledgment from someone who shipped a complementary open-source tool is a relationship, not a cold pitch. Warm relationships compound.

---

### 2. agentskills.io — PR #791 day-7 check-in

**priority:** High
**target:** anthropics/skills maintainers
**channel:** GitHub comment on PR #791
**timing:** April 3 (day 7 since submission March 27) — per BA recommendation
**action:** Friendly single comment on the PR: "Happy to make any changes needed — just checking in." No pressure, just visibility.

**why:** External contributor PRs at anthropics/skills typically take 2–7 days for first review. Day 7 with no activity is the right moment for a non-pushy nudge. The PR is MERGEABLE, no conflicts, 174 lines. Being responsive to maintainers signals a quality contributor.

---

### 3. dTelecom — Monitor for future outreach

**priority:** Low (watch now, act later)
**target:** @MilonxFiroz / dTelecom team
**context:** Solana-native real-time voice infra for Web3/onchain agents. Different audience (crypto builders, not traditional telephony). Not a direct competitor. Potential complement if voice+wallet agent use cases develop.
**action:** Follow on Twitter, no outreach yet. Revisit if their Coinbase AgentKit angle gains traction.

---

## 🛠️ POSTING COMMANDS

```bash
# Tweet
source ~/.config/bird/twitter-cookies.env && bird tweet "..."

# Verify login
source ~/.config/bird/twitter-cookies.env && bird whoami

# Log each post to COMMS_LOG.md immediately after posting
```

---

## ⚠️ WHAT NOT TO POST

- ❌ No mention of PR #791 or "our skill" as promotion
- ❌ No "check out our repo" hooks — project is archived
- ❌ No repeating signals from the March 24 plan (Cekura, agentskills.io platform count, pricing table, on-device LLM) — those were queued but based on March 24 intelligence and are now stale for Twitter timing

---

## 📋 Operating cadence (post-archive)

**Goal:** 3–4 posts/week on Twitter. Quality > frequency.
**Tone:** Builder-to-builder. Market intelligence, not project promotion.
**Log:** Every post goes to COMMS_LOG.md with date, platform, content, link.

| Week | Focus | Target posts |
|------|-------|-------------|
| Apr 1–3 | Mar 31 BA signals (Claude Code, Voxtral, Retell, ScreenSense) | 4 posts |
| Apr 4–7 | Follow-up on engagement + any new BA signals | 2–3 posts |
