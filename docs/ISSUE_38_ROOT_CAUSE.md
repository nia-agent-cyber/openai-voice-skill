# Issue #38: Zombie Calls Root Cause Analysis

**Issue:** 46 zombie calls with 60,000+ second durations, missing transcripts, `ended_at: null`

**Date:** 2026-02-06

## Root Cause

The zombie calls are caused by **missing call termination in `webhook-server.py`'s Twilio webhook handler**.

### The Problem

When a call ends, two things can happen:

1. **OpenAI fires `realtime.call.ended`** (line ~410-426 in webhook-server.py)
   - ✅ This correctly calls `recording_manager.end_call_recording()`
   - ✅ Call is properly marked as completed with `ended_at` timestamp

2. **Twilio fires `CallStatus=completed/failed/etc`** (line ~470 in webhook-server.py)
   - ❌ This only removes call from `active_calls` dict
   - ❌ Does NOT call `recording_manager.end_call_recording()`
   - ❌ Database record stays with `status='active'`, `ended_at=null`

### Code Evidence

**Correct handling (OpenAI webhook):**
```python
elif event_type == "realtime.call.ended":
    # End call recording  <-- CORRECT
    background_tasks.add_task(
        recording_manager.end_call_recording,
        call_id, "completed"
    )
```

**Missing handling (Twilio webhook):**
```python
elif call_status in ["completed", "busy", "no-answer", "canceled", "failed"]:
    logger.info(f"Outbound call ended: {call_sid} ({call_status})")
    if call_sid in active_calls:
        duration = time.time() - active_calls[call_sid].get("started_at", time.time())
        logger.info(f"Call {call_sid} duration: {duration:.1f}s")
        del active_calls[call_sid]
        # ❌ MISSING: recording_manager.end_call_recording(call_sid, call_status)!
```

### Why This Happens

For outbound calls:
1. Agent calls `/call` endpoint → Twilio places call → OpenAI SIP
2. User hangs up → Twilio fires `CallStatus=completed`
3. OpenAI may not fire `realtime.call.ended` (or it gets lost/delayed)
4. Result: Call stays as "active" forever in the database

## Workaround (This PR)

Since we cannot modify `webhook-server.py` (production constraint), this PR adds:

1. **Stale call cleanup in `call_recording.py`**
   - `cleanup_stale_calls()` method finds calls older than 1 hour with status='active'
   - Marks them as `status='timeout'` with proper `ended_at`
   - Notifies session bridge for transcript sync

2. **Cleanup endpoints in `session-bridge.ts`**
   - `GET /zombie-calls` - List zombie calls for diagnostics
   - `POST /cleanup-stale-calls` - Trigger cleanup

3. **Migration script `cleanup_zombie_calls.py`**
   - One-time script to clean existing zombies
   - Can be run periodically as a cron job

## Permanent Fix Required

**In `webhook-server.py` `handle_twilio_webhook()`, add:**

```python
elif call_status in ["completed", "busy", "no-answer", "canceled", "failed"]:
    logger.info(f"Outbound call ended: {call_sid} ({call_status})")
    
    # ✅ ADD THIS: End call recording
    background_tasks.add_task(
        recording_manager.end_call_recording,
        call_sid, call_status
    )
    
    # ✅ ADD THIS: Clear call context store
    if CALL_CONTEXT_STORE_AVAILABLE:
        clear_call_context(call_sid)
    
    if call_sid in active_calls:
        duration = time.time() - active_calls[call_sid].get("started_at", time.time())
        logger.info(f"Call {call_sid} duration: {duration:.1f}s")
        del active_calls[call_sid]
```

This fix should be applied by someone authorized to modify `webhook-server.py`.

## Testing

After cleanup:
```bash
# Check for remaining zombies
curl -s https://api.niavoice.org/storage/stats | jq '.active_calls'
# Should be 0 or only truly active calls

# Verify cleanup worked
curl -s https://api.niavoice.org/history?limit=10 | jq '.[].status'
# Should see 'timeout' for cleaned zombies, 'completed' for proper terminations
```

## Related Files

- `scripts/call_recording.py` - Added cleanup methods
- `scripts/cleanup_zombie_calls.py` - Migration script
- `channel-plugin/src/adapters/session-bridge.ts` - Added cleanup endpoints
- `scripts/webhook-server.py` - ROOT CAUSE (needs fix by authorized person)
