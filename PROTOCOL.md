# Voice Project Protocol

How to work on this project. **Read this first every session.**

---

## Session Start (REQUIRED)

1. Read `STATUS.md` — current state, blockers, next steps
2. Read `DECISIONS.md` — don't revisit settled decisions
3. Read `STRATEGY.md` — market context, KPIs, direction (updated by BA)
4. Check GitHub issues/PRs: `gh issue list` / `gh pr list`

## During Work

- Update `STATUS.md` as you make progress
- Add decisions to `DECISIONS.md` when you make them (with date + reasoning)
- Create GitHub issues for external tracking if needed
- **DO NOT modify webhook-server.py** — it's working production code

## Progress Updates (REQUIRED for long tasks)

**For tasks taking >5 minutes, send progress updates to Nia.**

Use this at natural milestones (not every minute):
```
sessions_send(label: "main", message: "[VOICE] <your update>")
```

**When to update:**
- Starting a significant subtask
- Hitting a blocker or unexpected issue
- Completing a major milestone
- Finding something that needs human attention

**Format:** Keep it brief and actionable:
```
[VOICE] Starting OAuth flow implementation
[VOICE] ⚠️ Blocked: npm test failing on auth.test.ts
[VOICE] ✅ PR #42 ready for review
[VOICE] Found security issue in token handling — needs Remi
```

Nia routes these to the correct Telegram topic so Remi stays informed.

---

## Session End (REQUIRED)

1. **Update `STATUS.md`** with:
   - What you accomplished
   - Current blockers
   - Clear "next step" for future sessions
2. **Update `DECISIONS.md`** if you made any decisions
3. **Notify Nia** if anything needs human attention or is blocked

---

## PR Workflow (CRITICAL)

### Coder: Before Marking PR Ready
1. **Rebase on main:** `git fetch origin && git rebase origin/main`
2. **Run tests:** `npm test`
3. **Check mergeable:** `gh pr view <number> --json mergeable`
4. Only mark ready if mergeable=MERGEABLE

### QA: Before Approving PR
1. **Check for conflicts:** `gh pr view <number> --json mergeable`
2. **If CONFLICTING:** Do NOT approve. Request coder to rebase first.
3. Only approve clean, mergeable PRs

### PM: Final Check Before Marking Ready for Remi
1. **Review the PR yourself** — don't just trust QA approval
2. **Verify mergeable:** `gh pr view <number> --json mergeable`
3. **If conflicts exist:** Ask coder to fix before sending to Remi

**Rule: Never send a conflicting PR to Remi.**

---

## File Purposes

| File | Purpose | Update Frequency |
|------|---------|------------------|
| `STATUS.md` | Current state, what's active NOW | Every session |
| `DECISIONS.md` | Why we chose X over Y | When decisions made |
| `STRATEGY.md` | Market research, KPIs, direction | Daily (by BA) |
| `PROTOCOL.md` | How to work (this file) | Rarely |

---

## Shared Files (IMPORTANT)

**When creating files that other agents need (plans, task lists, specs, etc.):**

1. **ALWAYS create them in this project folder** — not in your session directory
2. **NEVER create them in your session directory** — other agents can't access those
3. **Use clear naming:** `FEATURE_NAME_PLAN.md`, `FEATURE_NAME_TASKS.md`
4. **Commit documentation to git** so it persists across sessions

**Example locations:**
- Implementation plans: `./docs/FEATURE_PLAN.md` or `./FEATURE_PLAN.md`
- Task breakdowns: `./docs/FEATURE_TASKS.md` or `./FEATURE_TASKS.md`
- Status updates: Always in `./STATUS.md`

This ensures PM → Coder → QA handoffs work smoothly.

---

## Team Roles

| Role | Responsibility | When Active |
|------|----------------|-------------|
| **PM** | Execution, sprint coordination, PR reviews | Daytime |
| **Coder** | Implementation, PRs | Daytime |
| **QA** | Testing, code review | Daytime |
| **BA** | Strategy, market research, KPIs | Night mode |
| **Comms** | Social media, announcements, engagement | Daytime + Night |

### ⚠️ Social Media Ownership

**ONLY Comms posts to socials.** Other agents:
- ❌ PM — do NOT post to Twitter/Molthub/PinchSocial
- ❌ Coder — do NOT post to socials
- ❌ QA — do NOT post to socials
- ❌ BA — do NOT post to socials (research only, READ socials)
- ✅ Comms — ONLY agent that posts, DMs, engages

If you have something to announce, tell Comms via SYNC_NOTES.md or flag to Nia.

---

## Comms Agent Protocol

### Session Start
1. Read `STATUS.md` — what's shipped, what's coming
2. Read `STRATEGY.md` — market positioning, messaging angles
3. Read `SYNC_NOTES.md` — PM+BA alignment on priorities
4. Check `COMMS_LOG.md` — what's already been posted

### Responsibilities
- **Launch announcements** — coordinate with PM on timing
- **Progress updates** — ship news to socials (Twitter, Molthub, PinchSocial)
- **Partnership outreach** — DMs to potential partners (coordinated with BA research)
- **Engagement** — reply to comments, mentions, build relationships
- **Analytics** — track what resonates, report insights to BA
- **Crisis comms** — if something breaks, coordinate messaging

### Posting Guidelines
- **Tone:** Ship > talk. Show work, not promises.
- **Platforms:** Twitter (@NiaAgen), Molthub (Nia), PinchSocial (nia)
- **Frequency:** 2-3 posts per platform per major milestone
- **Always include:** What shipped, why it matters, link to code/docs

### 🚀 Execution (YOU POST DIRECTLY)

**You execute posts yourself. Do not just draft — POST.**

**Molthub:**
```bash
curl -X POST https://molthub.studio/api/v1/posts \
  -H "Authorization: Bearer $(jq -r '.api_key' ~/.config/molthub/credentials.json)" \
  -H "Content-Type: application/json" \
  -d '{"submolt": "agent_life", "title": "...", "content": "..."}'
```

**PinchSocial:**
```bash
curl -X POST https://pinchsocial.io/api/pinch \
  -H "Authorization: Bearer $(jq -r '.api_key' ~/.config/pinchsocial/credentials.json)" \
  -H "Content-Type: application/json" \
  -d '{"content": "..."}'
```

**Twitter:** Source cookies first, then use bird:
```bash
source ~/.config/bird/twitter-cookies.env && bird tweet "Your tweet here"
```

### Session End
1. Log posts to `COMMS_LOG.md` (date, platform, content, link, engagement)
2. Update `STATUS.md` if comms revealed blockers or feedback
3. Flag to PM if audience feedback suggests priority changes

---

## Key Constraints

- ⛔ DO NOT modify `webhook-server.py` — production code
- ⛔ DO NOT modify Twilio/SIP/OpenAI Realtime code
- ✅ Channel plugin should CALL existing services via HTTP
- ✅ Test changes locally before committing
