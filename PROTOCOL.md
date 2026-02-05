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

## Key Constraints

- ⛔ DO NOT modify `webhook-server.py` — production code
- ⛔ DO NOT modify Twilio/SIP/OpenAI Realtime code
- ✅ Channel plugin should CALL existing services via HTTP
- ✅ Test changes locally before committing
