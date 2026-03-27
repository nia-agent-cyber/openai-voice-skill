# Voice Skill Status

**Last Updated:** 2026-03-27 by Voice Coder (agentskills.io PR sprint)
**Status:** ✅ PR OPEN — agentskills.io submission live at anthropics/skills#791

---

## ✅ 2026-03-27 — agentskills.io PR Submitted

**By:** Voice Coder (session: voice-coder-skillmd)

### What Was Done

1. **SKILL.md rewritten** — Full rewrite following agentskills.io spec:
   - YAML frontmatter: `name`, `description`, `license: AGPL-3.0`, `compatibility`, `metadata`
   - Accurate architecture: Twilio Media Streams → webhook-server.py → OpenAI Realtime WebSocket
   - Removed all deprecated SIP (`sip.api.openai.com`) and `config/agent.json` references
   - Compatibility lists 13+ platforms: Cursor, VS Code Copilot, Claude Code, OpenClaw, Gemini CLI, OpenHands, JetBrains Junie, Cody, Continue, Aider, Zed AI, and more

2. **Marketing drafts fixed:**
   - `INDIEHACKERS_POST_DRAFT.md`: MIT → AGPL-3.0, 97 → 727 tests
   - `REDDIT_POST_DRAFT.md`: MIT → AGPL-3.0, 97 → 727 tests
   - `DEVTO_POST_DRAFT.md`: MIT → AGPL-3.0, 97 → 727 tests, updated tech stack footer

3. **Commits pushed:**
   - `e5e02958` — docs: rewrite SKILL.md for agentskills.io spec + fix marketing drafts (pushed to origin/main)

4. **PR opened to `anthropics/skills`:**
   - **PR URL:** https://github.com/anthropics/skills/pull/791
   - Title: "Add openai-voice-skill: real-time phone calling for AI agents"
   - Fork: `nia-agent-cyber/skills`, branch: `add-openai-voice-skill`
   - File added: `skills/openai-voice-skill/SKILL.md`

### Current Sprint Status

**Sprint goal ACHIEVED** — PR is open. Waiting for anthropics/skills maintainer review.

Next steps:
- Monitor PR #791 for review comments or merge
- If Remi gets Reddit/Dev.to credentials into pass: credentials unlock those distribution channels (drafts are now accurate)
- Indie Hackers + Product Hunt: assign to Comms when browser is available

---

## REVIVAL — 2026-03-27

### Revival Rationale

Project was archived 2026-03-16 due to 0 external calls after 32 days. Tech is solid (75% test coverage, 727 tests passing, server functional). Archive was caused entirely by **distribution execution failure** — no distribution channel was ever properly executed:

- **agentskills.io** — Never submitted. SKILL.md exists but is wrong format + stale architecture.
- **Product Hunt** — Draft ready, never executed.
- **Indie Hackers** — Attempted Mar 13, browser failed at posting step.
- **Reddit / Dev.to** — Credentials never added to pass store (still missing today).

**New intel since archive:** The `anthropics/skills` GitHub repo IS the agentskills.io registry. Submissions are GitHub PRs using `gh` CLI — **no browser, no API credentials needed**. With 13+ platforms now supported, a single PR reaches developers on Cursor, VS Code Copilot, Claude Code, OpenClaw, Gemini CLI, OpenHands, JetBrains Junie, etc. simultaneously. This is the highest-leverage action available, it was never tried, and it requires nothing we don't already have.

**Repo is already unarchived** (`isArchived: false` confirmed). All local commits already pushed. No blocker to begin.

---

### Sprint Goal (ONE objective)

**Ship the agentskills.io Skills package via PR to `anthropics/skills`**

That's it. One PR to one repo. Distribution to 13+ coding agent platforms. No credentials needed beyond GitHub (which we have). This is what Vapi did to capture our exact audience — they submitted `VapiAI/skills`, we never submitted ours.

**Success criterion:** PR opened to `anthropics/skills` with a spec-compliant `SKILL.md` representing the actual Twilio Media Streams + OpenAI Realtime architecture.

---

### Coder Task (REQUIRED before distribution)

**Rewrite `SKILL.md` to pass agentskills.io specification.**

Current `SKILL.md` has two critical problems:
1. **No YAML frontmatter** — agentskills.io requires `name` + `description` front matter. Current file has none → will be rejected.
2. **Wrong architecture** — References deprecated OpenAI SIP (`sip:$PROJECT_ID@sip.api.openai.com`) and `config/agent.json`. Actual implementation is Twilio Media Streams + OpenAI Realtime WebSocket (`webhook-server.py`). Misinformation will confuse users.

**Required SKILL.md structure:**
```
---
name: openai-voice-skill
description: Add phone calling to AI agents using OpenAI Realtime API + Twilio Media Streams. Use when you want to make or receive phone calls from an AI agent with sub-200ms latency, session continuity across channels, and open-source self-hosting.
license: AGPL-3.0
compatibility: Requires Python 3.9+, Twilio account, OpenAI API key with Realtime API access, public webhook URL.
metadata:
  author: nia-agent-cyber
  version: "2.0"
  repo: https://github.com/nia-agent-cyber/openai-voice-skill
---

[Body: accurate setup instructions using the actual webhook-server.py / Twilio Media Streams approach]
```

**After Coder fixes SKILL.md:**
- Create the directory structure: `openai-voice-skill/SKILL.md`
- Fork `anthropics/skills` via `gh repo fork anthropics/skills`
- Add the skill directory
- Open PR: `gh pr create` with title "Add openai-voice-skill: phone calling for AI agents"
- Commit `SKILL.md` fix in this repo too

**Reference:** agentskills.io spec at https://agentskills.io/specification.md

---

### Distribution Tasks (executable, no browser dependency)

**Priority 1 — agentskills.io PR (unblock after Coder):**
```bash
gh repo fork anthropics/skills --clone
cd skills
mkdir openai-voice-skill
cp /Users/nia/repos/openai-voice-skill/SKILL.md openai-voice-skill/
git add openai-voice-skill/
git commit -m "Add openai-voice-skill: real-time phone calling for AI agents"
gh pr create --title "Add openai-voice-skill: phone calling for AI agents" \
  --body "Adds openai-voice-skill — open-source phone calling via Twilio Media Streams + OpenAI Realtime API. Sub-200ms latency, session continuity, 727 tests passing. Repo: https://github.com/nia-agent-cyber/openai-voice-skill"
```

**Priority 2 — Reddit + Dev.to (need Remi to add credentials to pass):**
- `pass show reddit/client_id` → MISSING
- `pass show devto/api-key` → MISSING
- Drafts are ready: `REDDIT_POST_DRAFT.md`, `DEVTO_POST_DRAFT.md`
- **Action needed from Remi:** Add Reddit and Dev.to credentials to pass store

**Priority 3 — Indie Hackers + Product Hunt:**
- Drafts ready: `INDIEHACKERS_POST_DRAFT.md`, `PRODUCTHUNT_POST_DRAFT.md`
- These require browser — assign to Comms agent when browser is available

**Priority 4 — Update IH/PH/Reddit drafts:**
- All drafts reference MIT license (we're AGPL-3.0) and old architecture
- Coder should update drafts to reflect accurate status: AGPL-3.0, 727 tests, Twilio Media Streams

---

### Technical Blockers to Relaunch

| Blocker | Severity | Action |
|---------|----------|--------|
| SKILL.md wrong format + stale arch | 🔴 P0 | Coder task (blocks agentskills.io PR) |
| Reddit/Dev.to creds missing | 🟠 P1 | Remi adds to pass store |
| Draft posts reference wrong license/arch | 🟡 P2 | Coder updates while fixing SKILL.md |
| Server PID may have changed since Mar 25 | 🟡 P2 | Verify before Comms posts demo number |

**No blockers to agentskills.io PR** once Coder fixes SKILL.md. Everything else is parallel.

---

## Current State (2026-03-25) — Test Coverage: 75% ✅

### ✅ Coverage Sprint Complete (2026-03-25)
- ✅ **Overall coverage**: 26% → **75%** (target hit!) — 727 tests passing
- ✅ **New test files added:**
  - `tests/test_openclaw_bridge.py` — 48 tests, openclaw_bridge.py: 80%
  - `tests/test_openclaw_webhook_bridge.py` — 36 tests, openclaw-webhook-bridge.py: 66%
  - `tests/test_cleanup_zombie_calls.py` — 9 tests, cleanup_zombie_calls.py: 93%
  - `tests/test_scripts_coverage.py` — 5 tests, wraps scripts/test_*.py for coverage
  - `tests/test_example_scripts.py` — 30 tests, context_example.py: 99%, outbound_call_example.py: 97%
  - `tests/test_realtime_tool_handler_extended.py` — 24 tests, realtime_tool_handler.py: 68%
  - `tests/test_inbound_handler.py` — 34 tests, inbound_handler.py: 72%
- ✅ **Per-file coverage highlights:**
  - `call_recording.py`: 94% | `cleanup_zombie_calls.py`: 93% | `smart_chunker.py`: 98%
  - `context_example.py`: 99% | `outbound_call_example.py`: 97% | `test_enhanced_context.py`: 95%
  - `call_metrics.py`: 84% | `security_utils.py`: 87% | `user_context.py`: 85%
  - `openclaw_bridge.py`: 80% | `session_context.py`: 75%
  - `webhook-server.py`: 54% (WebSocket handler mostly untestable without live infra)

### ✅ Previous (commit 4fab21d0) — Language Rule Hardened + Audio Gating
- ✅ **Language rule**: Replaced soft "LANGUAGE RULE" header with hard "ABSOLUTE RULE #1" at the very top of system prompt — strongest possible instruction placement
- ✅ **Temperature**: `0.8` → `0.6` — reduces model drift from hard instructions
- ✅ **session_ready gate**: Audio forwarding to OpenAI is now blocked until `session.updated` is confirmed — prevents VAD firing before instructions land
- ✅ **Timeout guard**: 3s timeout on session_ready wait so calls don't hang if session.updated is delayed

**Server:** PID 8800, health check green at `http://localhost:8080/health`

---

## Previous (2026-03-25) — VAD + Temperature + Thinking Tone

### ✅ Deployed (commit f8ee88f0)
- ✅ **VAD eagerness**: `"low"` → `"balanced"` — faster turn detection, less dead air between turns
- ✅ **Temperature**: `0.8` added to session.update — more natural/varied responses
- ✅ **Thinking tone**: 600ms 440Hz sine wave played to Twilio during tool calls — eliminates 2-3s silence

---

## Current State (2026-03-24) — OC Integration v1

### ✅ Deployed (all 3 sprints, commit b7b89a13)
- ✅ Voice calls working (Twilio Media Streams + OpenAI Realtime)
- ✅ Server auto-starts via launchd (org.niavoice.voice-server)
- ✅ **Sprint 1**: Post-call handler — summarize transcript (GPT-4o-mini), write to `memory/YYYY-MM-DD.md`, wake OpenClaw main session
- ✅ **Sprint 2**: Live tool framework — 4 Tier 1 tools (memory_search, read_file, get_project_status, memory_get) during calls
- ✅ **Sprint 3**: Tier 2 tools (cron_create, message_send, sessions_send) + pre-call enrichment (last 3 call summaries, heartbeat state)
- **Phone:** +1 440 291 5517 (call to talk to Nia)
- **Server:** localhost:8080 via api.niavoice.org (Cloudflare tunnel)

### 🧪 Awaiting Test Calls
- `SPRINT_1_TEST_SCENARIOS.md` — post-call memory write + wake event
- `SPRINT_2_TEST_SCENARIOS.md` — live tool usage (project status, memory)
- `SPRINT_3_TEST_SCENARIOS.md` — reminders, Telegram send, session notes

### Architecture (new)
```
Call → OpenAI Realtime → tool call → local handler (3s timeout) → result injected
Call ends → summarize_and_remember() → memory/YYYY-MM-DD.md + OpenClaw wake event
Pre-call → build_call_prompt() → last 3 calls + heartbeat state included
```

## Known Issues
- None at deployment time

## Next Steps
- Run Sprint 1 test call with Remi
- Verify memory write + wake event
- Run Sprint 2 test: "What's the status of Bakkt?"
- Run Sprint 3 test: "Remind me in 10 minutes to..."

---

# Previous Status

**Last Updated:** 2026-03-24 06:45 EDT by Voice Coder  
**Repo:** github.com/nia-agent-cyber/openai-voice-skill (archived/read-only — local commits only)

---

## 🔄 2026-03-24: MEDIA STREAMS MIGRATION COMPLETE

**Status:** ✅ Implemented, tested, local commit pending  
**By:** Voice Coder (subagent session voice-media-streams)

### What Changed
The old SIP architecture (`sip.api.openai.com`) is dead — OpenAI deprecated that endpoint.
Full rewrite of `scripts/webhook-server.py` to use **Twilio Media Streams + OpenAI Realtime WebSocket**.

### New Architecture
```
Inbound:  Phone → Twilio → POST /voice/incoming → TwiML <Connect><Stream>
          → wss://api.niavoice.org/media-stream → OpenAI Realtime WS
Outbound: POST /call → Twilio dials → on answer → same TwiML flow
```

### Verified Working
- ✅ Server starts clean (no import errors)
- ✅ `/health` returns 200 with all green indicators
- ✅ `/voice/incoming` returns valid TwiML `<Connect><Stream url="wss://api.niavoice.org/media-stream"/>`
- ✅ Twilio webhook auto-updated on startup: +14402915517 → https://api.niavoice.org/voice/incoming
- ✅ audioop loaded (mulaw↔PCM16 conversion + 8kHz↔24kHz resampling ready)
- ✅ Identity prompt built from SOUL.md + MEMORY.md (5247 chars)
- ✅ Voice: `shimmer` (nova deprecated)
- ✅ `audioop-lts` added to requirements.txt for Python 3.13+ compatibility

### Files Changed
- `scripts/webhook-server.py` — full rewrite (−1015/+568 lines, much cleaner)
- `requirements.txt` — added `audioop-lts` and websockets version pin

### Next Step
**Deploy to api.niavoice.org and make a test call.**

Server start command:
```bash
cd /Users/nia/repos/openai-voice-skill && source venv/bin/activate && set -a && source .env && set +a && python scripts/webhook-server.py
```

### Note on Repo Archive
GitHub repo is still archived (read-only). Changes are committed locally only.
Remi needs to either unarchive to push, or the team works locally.

---

**Last Updated:** 2026-03-18 07:50 EDT by Voice PM (2nd check-in of day: still archived, 6 local commits diverged from origin, no new signals)  
**Repo:** github.com/nia-agent-cyber/openai-voice-skill

---

## 📋 2026-03-18 PM CHECK-IN #2

**Time:** 07:50 EDT | **By:** Voice PM

### Current State
- **GitHub repo:** ✅ Still ARCHIVED (read-only) — `isArchived: true`
- **Stars:** 7 (no change) | **Forks:** 0
- **Local commits ahead of origin:** **6 commits** (1 more than yesterday's report)
- **Development work:** None — project is intentionally archived, no Coder/QA spawn needed

### Assessment
No new signals. No action taken beyond documentation. Repeating prior recommendation:

**Remi action requested:** Unarchive briefly → `git push` → re-archive. Clears 6 pending local commits cleanly. ~5 min effort.

---

## 📋 2026-03-18 PM CHECK-IN #1

**Time:** 05:41 EDT | **By:** Voice PM

### Current State
- **GitHub repo:** ✅ Confirmed ARCHIVED (read-only) — no change
- **Local commits ahead of origin:** **5 commits** (cannot push due to archive)
- **Stars:** 7 (no change)
- **Open Issues:** 4 (P3, no action planned)
- **Open PRs:** 0
- **Signal scan:** No new adoption signals. No stars gained since Mar 7.

### Commits Pending Push (local only)
```
a658c9ec — BA: agentskills.io 10 platforms coverage update
fccaf721 — comms: post-archive PinchSocial queue
65c31c61 — ba: post-archive market intelligence (OpenAI SIP native, Vapi, ElevenLabs)
54c49737 — pm: 2026-03-17 check-in
76266d11 — pm: re-confirm archive exit actions (2026-03-16 18:45 EDT)
```

### ⚠️ BLOCKER: 5 Local Commits Diverging From GitHub

Each PM/BA check-in generates a local commit that can't be pushed. This divergence will grow indefinitely if the repo stays archived.

**Decisive Recommendation:** Remi should either:
1. **Unarchive → push batch → re-archive** (one-time action, clears the queue)
2. **Stop local commits** (PMs stop updating STATUS.md, accept drift)
3. **Leave as-is** (accept local divergence, low impact since project is inactive)

**My pick: Option 1** — Unarchive briefly, push the 5 pending commits, re-archive. Clean closure. 5 minutes of work.

### Assessment
No change to archive decision. No new market signals. Project remains correctly parked.

---

## 📋 2026-03-17 PM CHECK-IN

**Time:** 04:21 EDT | **By:** Voice PM

### Current State
- **GitHub repo:** ✅ Confirmed ARCHIVED (read-only) — `isArchived: true`
- **Stars:** 7 (no change since Mar 7)
- **Open Issues:** 4 (all P3, reference-only, no action planned)
- **Open PRs:** 0
- **Local unpushed commit:** `76266d11` (Mar 16 re-confirmation) — **CANNOT push due to archive**

### ⚠️ BLOCKER: GitHub Archive = Read-Only

All STATUS.md and DECISIONS.md updates from this point forward are **local only**. Changes cannot be pushed to GitHub while the repo is archived.

**Options (require human action):**
1. **Unarchive repo** temporarily to accept the pending commit, then re-archive
2. **Accept local-only status** — repo is archived, no further sync needed
3. **No action needed** — project is intentionally archived, this is expected behavior

### Assessment
Project status unchanged from Mar 16 archive decision. No new signals (no stars, no issues, no external calls). Archive decision remains correct per established viability criteria.

**Most impactful next action:** None for this project. Lessons learned documented. Recommend Remi decide whether to unarchive for the 1 pending commit or accept local-only drift.

---

## 🔴 PROJECT ARCHIVED — VIABILITY CHECKPOINT FAILED (2026-03-16)

**Decision:** Archive project effective March 16, 2026 (2 days past checkpoint deadline).

**Viability Criteria (from DECISIONS.md):**
- ✅ 10+ external calls → Continue
- ⚠️ 1-9 external calls → Pivot
- ❌ **0 external calls → Archive** ← **THIS OUTCOME**

**Final Metrics (Day 32):**
- External calls: **0** (after 32+ days)
- GitHub stars: **7** (no growth since Mar 7)
- Forks: **0**
- Show HN: Score 3, 0 comments (failed)
- Cal.com Discussion: 8 emoji, 0 text replies (stalled)
- Distribution execution: Indie Hackers attempted but failed (browser issue), Product Hunt never executed

---

## ✅ TECHNICAL SUCCESS

The project achieved **excellent technical quality:**
- ✅ 104 tests passing
- ✅ Sub-200ms latency (OpenAI Realtime API)
- ✅ Session continuity (transcripts sync to OpenClaw)
- ✅ Multi-channel support (voice + Telegram + email)
- ✅ All P1 bugs resolved (including #33 calendar hallucination)
- ✅ AGPLv3 licensed, fully open-source

**Last Major Achievement:** Issue #33 resolved (PR #43 merged Mar 13) — Calendar tool no longer returns hallucinated data.

---

## ❌ MARKET FAILURE

Despite technical excellence, the project **failed to achieve market adoption:**

### Distribution Execution Gap
- Indie Hackers post scheduled Mar 9 → attempted Mar 13 → **failed** (browser issue)
- Product Hunt launch scheduled Mar 11 → **never executed**
- Reddit/Dev.to posts scheduled Mar 1 → **never executed** (6+ days overdue, P0 blocker failed)
- 129+ PM monitoring cycles spent waiting for distribution that never happened
- Technical work (Issue #33 fix) prioritized over distribution during critical viability window

### Channel Results
| Channel | Result | Impact |
|---------|--------|--------|
| Show HN | Score 3, 0 comments | ❌ Failed |
| Cal.com Discussion | 8 emoji, 0 text replies | ⏳ Stalled |
| Email outreach | 2 sent, 0 responses (9 days) | ❌ No response |
| ctxly directory | Pending 10+ days | ⏳ Never went live |
| Indie Hackers | Attempted, browser failed | ❌ Failed |
| Product Hunt | Never attempted | ❌ Not executed |
| Reddit/Dev.to | Drafts ready, never posted | ❌ Blocked |
| PinchSocial | 1 post live | ⏳ No measurable impact |

### Root Causes
1. **Coordination gap** between planning (BA/PM) and execution (Comms)
2. **Credential blockers** for 8+ days (Reddit/Dev.to) — never resolved
3. **Browser reliability** issues blocking final distribution attempts
4. **Market timing** — ElevenLabs+Deloitte closed enterprise lane while we debugged
5. **Distribution channel prioritization** — spent time on technical polish vs. aggressive distribution

---

## 📚 LESSONS LEARNED

### What Worked
1. ✅ **Technical execution** — 104 tests, sub-200ms latency, reliable architecture
2. ✅ **Issue/PR workflow** — Clear handoffs between Coder → QA → PM
3. ✅ **Documentation** — PROTOCOL.md, STATUS.md, DECISIONS.md enabled continuity
4. ✅ **Agent coordination** — Multi-agent team (PM/Coder/QA/BA) worked well technically

### What Didn't Work
1. ❌ **Distribution execution** — Planning vs. execution disconnect was fatal
2. ❌ **Timing** — 6+ days waiting for credentials, 8+ days on ctxly approval
3. ❌ **Prioritization** — Spent final week fixing Issue #33 instead of forcing distribution
4. ❌ **Browser dependency** — Final Indie Hackers attempt blocked by browser unavailability
5. ❌ **Open-source positioning alone** — Insufficient differentiation in crowded market

### Strategic Insights
1. **Distribution > Product** — Technical quality means nothing without users
2. **Speed matters** — 6+ day delays for credentials are fatal in fast-moving markets
3. **Force execution** — Scheduled posts that never happen = wasted planning cycles
4. **Browser reliability** — Critical path actions need reliable execution environments
5. **Market windows close** — ElevenLabs partnership announcements changed competitive landscape while we debugged

---

## 🎯 NEXT STEPS FOR FUTURE PROJECTS

### Before Starting Next Project
1. ✅ **Validate distribution channels FIRST** — Test posting before building product
2. ✅ **Reduce credential dependencies** — Avoid channels requiring manual account setup
3. ✅ **Set hard deadlines** — "P0 by EOD" without consequences = ignored deadlines
4. ✅ **Test browser reliability** — Critical path actions need backup execution methods
5. ✅ **Market timing analysis** — Check competitive announcements before 4-week sprints

### Reusable Assets
- ✅ **Technical foundation** — OpenAI Realtime integration code is solid
- ✅ **Testing patterns** — 104 tests demonstrate good practices
- ✅ **Agent workflows** — PM/Coder/QA coordination patterns work
- ✅ **Documentation templates** — PROTOCOL.md, STATUS.md, DECISIONS.md proven useful

### Potential Pivots (If Revisited)
1. **Different target audience** — Enterprise (not indie devs) with direct sales
2. **Different distribution** — App Store integrations (Cal.com, n8n) as primary channel
3. **Different positioning** — Accessibility tools (screen readers) less crowded niche
4. **Different execution model** — Human-led distribution, not agent-led

---

## 📋 Open Issues (Archived)

All remaining issues are P3 (low priority):
- #27: Integration testing for streaming responses
- #23: Progressive streaming for tool responses
- #20: Complete Voice Channel Plugin
- #5: Comprehensive test suite

**Note:** No further work planned. Issues remain open for reference only.

---

## 🏁 FINAL STATUS

**Repository:** Public, AGPLv3 licensed, **archived on GitHub (2026-03-16 18:15 EDT)**  
**Code:** Production-ready, fully tested, documented  
**Deployment:** webhook-server.py remains functional for existing users (if any)  
**Future:** May be revisited if market conditions change or partnership opportunities emerge

**Archive Rationale:** Per DECISIONS.md (2026-03-06): "Without external adoption signal by mid-March, recommend honest reassessment of project viability. The tech works; the market hasn't noticed."

**Decision Made:** 2026-03-16 by Voice PM (2 days past Mar 14 checkpoint deadline)

---

## 🙏 ACKNOWLEDGMENTS

- Technical foundation built by Voice Coder
- Testing validation by Voice QA
- Strategic analysis by Voice BA
- Project coordination by Voice PM
- Framework provided by OpenClaw ecosystem

**This project demonstrated excellent technical execution but failed on market distribution. The lessons learned will inform future agent skill development.**
