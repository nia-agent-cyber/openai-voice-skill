# Sprint 1 Test Scenarios: Post-Call Handler

## What's New
After a call ends, Nia now:
1. Summarizes the call transcript using GPT-4o-mini
2. Writes the summary to the daily memory file
3. Sends a wake event to OpenClaw so the main session knows a call happened

---

## Test Call Script

### Setup
- Call: +1 440 291 5517 (or Nia calls Remi at +250794002033)
- Duration: ~1 minute is enough

---

### Scenario A: Memory File Gets Updated

**What to do:**
1. Call and have a brief conversation (30–60 seconds)
2. Example things to say:
   - "Hey Nia, just testing the new memory system."
   - "Tell me something interesting about the voice project."
   - "What have you been working on lately?"
3. Hang up
4. Wait 15–30 seconds
5. Check the file: `/Users/nia/.openclaw/workspace/memory/YYYY-MM-DD.md`
   (replace YYYY-MM-DD with today's date, e.g. `2026-03-24.md`)

**Expected result:**
A new section appears at the bottom of the daily memory file like:
```
## 📞 Call with Remi at 14:35 (62s, 8 turns)
Remi called to test the new post-call memory system. Nia described the voice project's
recent progress. No action items were discussed.
```

**Pass:** Summary entry exists in the file ✅  
**Fail:** No new entry in the file ❌

---

### Scenario B: Main Session Is Notified

**What to do:**
After hanging up from Scenario A, check if Nia (main Telegram session) received a notification.

**Expected result:**
Within 30 seconds of hanging up, the main OpenClaw session should wake up and Nia should be aware the call happened. If you ask Nia in Telegram "did we just have a call?", she should know.

**Pass:** Main session receives wake notification ✅  
**Fail:** No wake event in server logs (`Post-call: OpenClaw wake event sent`) ❌

---

## How to Check Logs (for debugging)
```bash
tail -f /usr/local/var/log/niavoice.log
# or
log stream --predicate 'process == "Python"' --level debug 2>/dev/null | grep -i "post-call"
```

Look for lines like:
- `Post-call summary generated: ...`
- `Post-call: summary written to .../memory/2026-03-24.md`
- `Post-call: OpenClaw wake event sent ✅`

---

## Pass Criteria for Sprint 1
- [ ] Call summary appears in `memory/YYYY-MM-DD.md` within 30s of call end
- [ ] Summary is 2–4 sentences and accurately describes the conversation
- [ ] Server logs show `Post-call: OpenClaw wake event sent ✅`
- [ ] No regressions: call audio still works, no server errors during call
