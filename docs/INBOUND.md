# T4 Inbound Call Support

Documentation for inbound call handling in the Voice Skill.

## Overview

The voice skill supports both outbound and inbound calls:

- **Outbound**: Agent initiates call to user (existing)
- **Inbound**: User calls the agent's phone number (T4)

Inbound calls go through authorization checks before being connected to ensure security.

## Architecture

```
┌─────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Twilio    │───▶│ Inbound Handler  │───▶│  Webhook Server  │
│  Incoming   │    │   (port 8084)    │    │   (port 8080)    │
│    Call     │    │                  │    │                  │
└─────────────┘    │ • Authorization  │    │ • OpenAI Realtime│
                   │ • Session Context│    │ • SIP Integration│
                   │ • Caller History │    │ • Transcripts    │
                   └──────────────────┘    └──────────────────┘
                            │                       │
                            ▼                       ▼
                   ┌──────────────────┐    ┌──────────────────┐
                   │  Session Bridge  │◀──▶│ OpenClaw Session │
                   │   (port 8082)    │    │                  │
                   └──────────────────┘    └──────────────────┘
```

### Component Roles

| Component | Port | Role |
|-----------|------|------|
| **Inbound Handler** | 8084 | Authorization, session context, caller history |
| **Webhook Server** | 8080 | OpenAI Realtime connection, voice processing |
| **Session Bridge** | 8082 | Transcript sync to OpenClaw sessions |
| **Metrics Server** | 8083 | Call observability and monitoring |

## Configuration

### Environment Variables

```bash
# Inbound Handler
PORT=8084                        # Inbound handler port
VOICE_POLICY=allowlist           # Policy: open, allowlist, pairing
VOICE_ALLOWLIST=+14402915517     # Comma-separated allowlist

# Webhook Server
ALLOW_INBOUND_CALLS=true         # Enable inbound calls
OPENAI_PROJECT_ID=proj_xxx       # OpenAI project ID
```

### Config File (`config/inbound.json`)

```json
{
  "policy": "allowlist",
  "allowFrom": [
    "+14402915517",
    "+1440*"
  ],
  "voicemailEnabled": true,
  "afterHoursMessage": "I'm not available right now. Please leave a message.",
  "afterHoursStart": "22:00",
  "afterHoursEnd": "08:00",
  "afterHoursTimezone": "America/New_York"
}
```

## Authorization Policies

### `open` Policy

Accepts all incoming calls. **Not recommended for production.**

```json
{ "policy": "open" }
```

### `allowlist` Policy (Default)

Only accepts calls from numbers in the allowlist.

```json
{
  "policy": "allowlist",
  "allowFrom": [
    "+14402915517",      // Exact match
    "+1440*",            // Prefix match (all +1440 numbers)
    "*"                  // Wildcard (allow all)
  ]
}
```

### `pairing` Policy

Only accepts calls from paired devices (future implementation).

```json
{ "policy": "pairing" }
```

## API Endpoints

### Inbound Handler (port 8084)

#### `POST /authorize`

Check if a caller is authorized.

**Request:**
```json
{
  "caller_phone": "+14402915517",
  "caller_name": "John Doe",
  "caller_city": "Cleveland",
  "caller_state": "OH",
  "caller_country": "US"
}
```

**Response:**
```json
{
  "authorized": true,
  "reason": "allowlist_match",
  "message": "Caller matches allowlist entry: +1440*",
  "matched_entry": "+1440*",
  "policy": "allowlist"
}
```

#### `POST /context`

Get session context for an authorized caller.

**Request:**
```json
{
  "caller_phone": "+14402915517",
  "caller_name": "John Doe",
  "caller_city": "Cleveland"
}
```

**Response:**
```json
{
  "session_key": "voice:14402915517",
  "is_known_caller": true,
  "caller_name": "John Doe",
  "previous_call_count": 3,
  "last_call_at": "2026-02-05T15:30:00Z",
  "context_instructions": "--- INBOUND CALL CONTEXT ---\nCall Direction: Inbound...\n--- END CONTEXT ---"
}
```

#### `POST /call-started`

Record that a call has started (updates caller history).

#### `POST /missed-call`

Record a missed call for later follow-up.

```json
{
  "from_number": "+14402915517",
  "reason": "unauthorized",
  "voicemail_transcript": "Hi, this is John..."
}
```

#### `GET /missed-calls`

List recent missed calls.

```json
{
  "missed_calls": [
    {
      "timestamp": "2026-02-06T10:00:00Z",
      "from_number": "+1440****5517",
      "reason": "unauthorized",
      "has_voicemail": true,
      "callback_scheduled": false
    }
  ],
  "pending_callbacks": 1
}
```

#### `POST /missed-calls/callback`

Mark a missed call as scheduled for callback.

#### `GET /callers`

List known callers.

#### `GET /health`

Health check.

## Call Flow

### Authorized Call

1. Caller dials Twilio number
2. Twilio webhooks to inbound handler
3. Handler checks authorization → **AUTHORIZED**
4. Handler builds session context with caller history
5. Handler returns TwiML to connect to OpenAI SIP
6. Webhook server accepts call with context-enhanced instructions
7. Real-time voice conversation via OpenAI Realtime
8. Call ends → transcript syncs to OpenClaw session

### Unauthorized Call

1. Caller dials Twilio number
2. Twilio webhooks to inbound handler
3. Handler checks authorization → **DENIED**
4. Handler returns TwiML to play rejection message
5. If voicemail enabled: record voicemail
6. Missed call recorded for later callback
7. Webhook → voicemail transcript stored

## Session Context Injection

Inbound calls get context injected into agent instructions:

```
--- INBOUND CALL CONTEXT ---
Call Direction: Inbound (caller reached you)
Caller Location: Cleveland, OH, US
Caller ID Name: John Doe

--- CALLER HISTORY ---
Known as: John
Previous calls: 3
Last call: 2026-02-05T15:30:00Z
Notes: Interested in API documentation

Since this is a returning caller, you may reference previous conversations if relevant.
--- END CONTEXT ---
```

For new callers:

```
--- INBOUND CALL CONTEXT ---
Call Direction: Inbound (caller reached you)
Caller Location: Unknown

--- NEW CALLER ---
This is the first call from this number. Be welcoming and ask how you can help.
--- END CONTEXT ---
```

## Missed Call to Appointment Flow

The T4 implementation supports a "missed call to appointment" workflow:

1. **Unauthorized caller** → Voicemail recorded
2. **Agent reviews** missed calls via `/missed-calls` endpoint
3. **Voicemail transcribed** (via Twilio's transcription)
4. **Agent schedules callback** → marks via `/missed-calls/callback`
5. **Outbound call** initiated with context from voicemail

This enables 24/7 lead capture even when calls can't be immediately answered.

## Running the Services

### Development

```bash
# Terminal 1: Inbound Handler
python scripts/inbound_handler.py

# Terminal 2: Webhook Server (existing)
python scripts/webhook-server.py

# Terminal 3: Session Bridge (existing)
npx ts-node channel-plugin/src/adapters/session-bridge.ts
```

### Production

Use systemd services or Docker Compose:

```yaml
services:
  inbound-handler:
    build: .
    command: python scripts/inbound_handler.py
    ports:
      - "8084:8084"
    environment:
      - VOICE_POLICY=allowlist

  webhook-server:
    build: .
    command: python scripts/webhook-server.py
    ports:
      - "8080:8080"
    environment:
      - ALLOW_INBOUND_CALLS=true
```

## Twilio Configuration

Configure Twilio to send inbound webhooks:

1. Go to Twilio Console → Phone Numbers
2. Select your number (+1 440 291 5517)
3. Under "Voice & Fax", set:
   - **A call comes in**: Webhook
   - **URL**: `https://api.niavoice.org/inbound/twiml`
   - **HTTP Method**: POST

The inbound handler generates TwiML that either:
- **Accepts**: Connects to OpenAI Realtime via SIP
- **Rejects**: Plays message and records voicemail

## Security Considerations

1. **Default secure**: Empty allowlist = all calls rejected
2. **No PII in logs**: Phone numbers are masked
3. **Signature verification**: Twilio webhooks verified
4. **Session isolation**: Each caller gets unique session key
5. **Rate limiting**: Consider adding for production

## Monitoring

Check inbound call health via metrics:

```bash
# Inbound handler health
curl http://localhost:8084/health

# Missed call stats
curl http://localhost:8084/missed-calls

# Known callers
curl http://localhost:8084/callers

# Combined with observability (port 8083)
curl http://localhost:8083/metrics/dashboard
```

## Troubleshooting

### Call rejected but caller is in allowlist

1. Check phone number format (must be E.164: `+14402915517`)
2. Check config is loaded: `curl http://localhost:8084/config`
3. Test authorization directly:
   ```bash
   curl -X POST http://localhost:8084/authorize \
     -H "Content-Type: application/json" \
     -d '{"caller_phone": "+14402915517"}'
   ```

### Voicemail not recording

1. Check `voicemailEnabled: true` in config
2. Verify Twilio recording settings
3. Check TwiML output for `<Record>` element

### No context appearing in calls

1. Verify session bridge is running (port 8082)
2. Check caller history: `curl http://localhost:8084/callers`
3. Verify context endpoint:
   ```bash
   curl -X POST http://localhost:8084/context \
     -H "Content-Type: application/json" \
     -d '{"caller_phone": "+14402915517"}'
   ```
