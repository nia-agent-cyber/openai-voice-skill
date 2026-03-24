# Sprint 2 Test Scenarios: Live Tool Framework (Tier 1)

## What's New
Nia now has 4 live tools she can use during a call:
1. `memory_search` — search her memory files
2. `read_file` — read any workspace file
3. `get_project_status` — read a project's STATUS.md live
4. `memory_get` — get memory notes for a specific date

Nia will briefly announce when she's using a tool ("let me check on that...").

---

## Test Call Script

### Setup
- Call: +1 440 291 5517 (or Nia calls Remi at +250794002033)
- Each scenario tests one tool

---

### Scenario A: `get_project_status` — "What's the status of Bakkt?"

**What to say:**
> "What's the status of the Bakkt project?"

**Expected behavior:**
1. Nia says something like "Let me check that for you..." (brief filler or direct)
2. Nia reads `~/repos/bakkt-agent-app/STATUS.md` live
3. Nia gives a 1-3 sentence summary of the current Bakkt status

**Pass:** Nia gives live, accurate status info ✅  
**Fail:** Nia says she doesn't know or gives stale/generic info ❌

---

### Scenario B: `get_project_status` — "How is the voice project going?"

**What to say:**
> "How's the voice project going right now?"

**Expected behavior:**
Nia reads `~/repos/openai-voice-skill/STATUS.md` and gives a brief summary.
She should mention "OC integration" or "Sprint" work since that's what STATUS.md now reflects.

**Pass:** Live STATUS.md data returned, mentions recent work ✅  
**Fail:** Generic or stale answer ❌

---

### Scenario C: `memory_search` — "Do you remember what we discussed?"

**What to say:**
> "Do you remember anything about the trust project?"

**Expected behavior:**
Nia searches her memory files for "trust" and reports back what she finds.
If there's nothing, she says "I don't have anything in memory about that."

**Pass:** Either returns a relevant memory result, or gracefully says none found ✅  
**Fail:** Nia crashes, errors, or gives confusing response ❌

---

### Scenario D: `read_file` — "Can you read your memory file?"

**What to say:**
> "Can you read your MEMORY.md file for me?"

**Expected behavior:**
Nia reads `/Users/nia/.openclaw/workspace/MEMORY.md` and summarizes it briefly.

**Pass:** Nia reads and summarizes MEMORY.md content ✅  
**Fail:** Access denied error or file not found ❌

---

## How to Check Logs
```bash
tail -f /usr/local/var/log/niavoice.log
```

Look for lines like:
- `🔧 Tool call: get_project_status(['project'])`
- `🔧 Tool result (get_project_status): ...`
- `Tool call complete: memory_search call_id=...`

---

## Pass Criteria for Sprint 2
- [ ] Nia uses `get_project_status` when asked about a project status
- [ ] Nia returns live, accurate data (not hallucinated)
- [ ] Nia uses `memory_search` when asked "do you remember..."
- [ ] No tool call adds more than 1-2s of perceived latency (file reads are instant)
- [ ] Server logs show `🔧 Tool call:` entries
- [ ] No regressions to Sprint 1 post-call behavior
- [ ] Call still works normally (audio, mic, hang-up)
