# Sprint 3 Test Scenarios: Tier 2 Tools + Pre-Call Enrichment

## What's New
1. **Tier 2 tools**: `cron_create`, `message_send`, `sessions_send`
2. **Pre-call enrichment**: Last 3 call summaries in context, heartbeat state

---

## Test Call Script

### Setup
- Call: +1 440 291 5517 (or Nia calls Remi at +250794002033)
- Check Telegram and memory file after each test

---

### Scenario A: `cron_create` — "Remind me at [time]"

**What to say:**
> "Remind me in 10 minutes to check on the deployment."

**Expected behavior:**
1. Nia says "I'll set that reminder for you."
2. Nia calls `cron_create` with the message and time
3. After ~10 minutes, Remi receives a Telegram message: "Check on the deployment"

**Pass:** Reminder is set and fires at the right time ✅  
**Fail:** Nia says she can't set reminders, or reminder never arrives ❌

---

### Scenario B: `message_send` — "Send me that in Telegram"

**What to say:**
> "Send me the link to the OpenClaw docs in Telegram."

Then say:
> "Actually, send me a note that says: voice integration sprint 3 is done."

**Expected behavior:**
1. Nia sends a Telegram message to +250794002033 with the requested text
2. Remi receives it immediately

**Pass:** Telegram message arrives within 10 seconds ✅  
**Fail:** No message arrives, or Nia says she can't send ❌

---

### Scenario C: `sessions_send` — "Note that for later"

**What to say:**
> "Note this for later: Remi wants to add web search to the next sprint."

**Expected behavior:**
1. Nia says "I'll add that to my notes."
2. Nia calls `sessions_send` with the note
3. The main OpenClaw session receives a wake event with the note
4. (Optional) Nia in Telegram should know about the note if asked

**Pass:** Server logs show `sessions_send` tool called, wake event sent ✅  
**Fail:** Tool errors or no wake event sent ❌

---

### Scenario D: Pre-call context (call history)

**What to do:**
If this is not the first test call (Scenarios from Sprint 1/2 have been run), Nia should have some call history.

**What to say:**
> "Do you remember our call earlier today?"

**Expected behavior:**
Nia should have the last few call summaries in her context and be able to reference them.

**Pass:** Nia mentions something from a recent call ✅  
**Fail:** Nia has no memory of previous calls ❌

---

## How to Check Logs
```bash
tail -f /usr/local/var/log/niavoice.log
```

Look for:
- `🔧 Tool call: cron_create`
- `🔧 Tool call: message_send`
- `🔧 Tool call: sessions_send`
- `Post-call: OpenClaw wake event sent` (from sessions_send)
- `Built call prompt: ... chars` (should include recent call history)

---

## Pass Criteria for Sprint 3
- [ ] `cron_create` sets a reminder that fires at the right time
- [ ] `message_send` sends Telegram message within 10 seconds
- [ ] `sessions_send` sends wake note to main session
- [ ] Pre-call context includes last 3 call summaries (check build_call_prompt log)
- [ ] No regressions to Sprint 1/2 behavior
- [ ] Total tool count in session.update is 7 (4 Tier 1 + 3 Tier 2)
