# Examples

## missed_call_handler.py

Minimal missed-call → appointment flow. Answers every call with an AI receptionist that qualifies leads and books appointments.

**Quick start:**
```bash
export TWILIO_ACCOUNT_SID=AC...
export TWILIO_AUTH_TOKEN=...
export BUSINESS_NAME="My Business"
export PUBLIC_HOST=your-tunnel.trycloudflare.com

python examples/missed_call_handler.py
```

See [docs/MISSED_CALL_TUTORIAL.md](../docs/MISSED_CALL_TUTORIAL.md) for the full walkthrough with ROI analysis.
