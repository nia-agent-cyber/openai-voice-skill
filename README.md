# OpenAI Voice Skill

**Real-time voice conversations for OpenClaw agents using OpenAI's Realtime API.**

Built by [Nia](https://github.com/nia-agent-cyber) for [OpenClaw](https://openclaw.ai) agents.

## What This Does

Voice as a first-class channel for your OpenClaw agent:
- **Call your agent** - Dial the Twilio number, talk to your agent
- **Agent calls you** - Outbound calls initiated by the agent
- **Session continuity** - Same phone number = same conversation, across voice and text channels
- **Full agent access** - Voice sessions can invoke OpenClaw's tools via `ask_openclaw`

## ✅ What's Working

| Feature | Status | Notes |
|---------|--------|-------|
| Voice channel in OpenClaw | ✅ | Shows in `openclaw status` |
| Outbound calls | ✅ | HTTP POST to `/call` endpoint |
| Inbound calls | ✅ | OpenAI Realtime handles conversation |
| Session sync | ✅ | Transcripts sync to OpenClaw sessions |
| Cross-channel context | ✅ | Voice ↔ Telegram share conversation history |
| `ask_openclaw` tool | ✅ | Voice can invoke full agent capabilities |
| Sub-200ms latency | ✅ | Native speech-to-speech |

## Why Native SIP?

Most voice solutions chain services with cumulative latency:

```
Phone → Twilio → Server → Deepgram STT → LLM → ElevenLabs TTS → Server → Phone
                   ~300ms      ~500ms        ~500ms              ~300ms
```

**This skill uses OpenAI's Realtime API with native SIP:**

```
Phone → Twilio SIP → OpenAI Realtime API → Phone
                         ~200ms total
```

Single hop. Native speech-to-speech. Conversations feel natural.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         OpenClaw Agent                               │
│                                                                      │
│  ┌──────────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │ Session Store    │◄───│ Session Bridge   │◄───│ Call Events   │  │
│  │ (voice:+1234...) │    │ (port 8082)      │    │               │  │
│  └──────────────────┘    └──────────────────┘    └───────┬───────┘  │
│           │                                              │          │
│           ▼                                              │          │
│  ┌──────────────────────────────────────────────────────┴───────┐  │
│  │                    webhook-server.py (port 8080)              │  │
│  │  - Receives Twilio webhooks                                   │  │
│  │  - Connects to OpenAI Realtime API                           │  │
│  │  - Handles ask_openclaw function calls                       │  │
│  │  - Stores transcripts                                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Twilio SIP     │  │ OpenAI Realtime │  │ OpenClaw CLI    │
│  (phone calls)  │  │ (voice AI)      │  │ (tool execution)│
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Key Components

| Component | Port | Description |
|-----------|------|-------------|
| webhook-server.py | 8080 | Core voice server - Twilio webhooks + OpenAI Realtime |
| session-bridge.ts | 8082 | Syncs transcripts to OpenClaw sessions |
| realtime_tool_handler.py | — | Handles `ask_openclaw` function calls |
| openclaw_executor.py | — | Bridges to OpenClaw CLI |

### Session Sync Flow

1. **Call starts** → Bridge creates session key (`voice:+15551234567`)
2. **During call** → Transcript events sent to bridge
3. **Call ends** → Full transcript synced to OpenClaw session JSONL
4. **Cross-channel** → Same phone = same session in Telegram/other channels

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+ (for channel plugin)
- OpenClaw installed and configured
- Twilio account with phone number
- OpenAI API access (with Realtime API enabled)

### 1. Clone & Install

```bash
git clone https://github.com/nia-agent-cyber/openai-voice-skill.git
cd openai-voice-skill/scripts
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp ../.env.example ../.env
```

Edit `.env`:

```bash
# Required
OPENAI_API_KEY=sk-...
OPENAI_PROJECT_ID=proj_...

# For outbound calls
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+14402915517

# Public URL (for Twilio webhooks)
PUBLIC_URL=https://api.niavoice.org

# Optional
PORT=8080
OPENCLAW_TIMEOUT=30
```

### 3. Configure Twilio

**SIP Trunk (for OpenAI Realtime):**
1. Go to Elastic SIP Trunking → Create trunk
2. Termination URI: `sip:YOUR_PROJECT_ID@sip.api.openai.com;transport=tls`
3. Assign your phone number to the trunk

**Webhook (for outbound calls):**
1. Phone Numbers → Your number → Voice Configuration
2. Webhook URL: `https://your-domain/voice/twiml`

### 4. Configure OpenAI

1. Go to platform.openai.com/settings
2. Project → Webhooks
3. Add your server URL + `/webhook`
4. Subscribe to `realtime.call.incoming`

### 5. Run the Server

```bash
# Start the voice server
python webhook-server.py

# In production, use the cloudflare tunnel
cloudflared tunnel --url http://localhost:8080
```

### 6. Install Channel Plugin (Optional)

For full OpenClaw integration:

```bash
cd channel-plugin
npm install
npm run build
cp -r dist/* ~/.openclaw/extensions/voice-channel/
```

Add to OpenClaw config:

```yaml
channels:
  voice:
    accounts:
      default:
        enabled: true
        webhookUrl: "https://api.niavoice.org"
```

Restart OpenClaw:

```bash
openclaw gateway restart
```

## Usage

### Inbound Calls

Just call your Twilio number! The OpenAI Realtime API handles the conversation with your configured agent personality.

### Outbound Calls

**HTTP API:**

```bash
curl -X POST https://api.niavoice.org/call \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+1234567890",
    "message": "Hello! This is your AI assistant calling."
  }'
```

**Response:**

```json
{
  "status": "initiated",
  "call_id": "CAxxxxxxxxxxxxxxxxxxxxx",
  "message": "Call initiated to +1234567890"
}
```

### ask_openclaw Tool

During voice calls, the agent can invoke `ask_openclaw` to access OpenClaw's full capabilities:

**Caller:** "What's on my calendar today?"

**Voice Agent:** *uses ask_openclaw* → OpenClaw checks calendar → speaks result

The tool definition:

```json
{
  "name": "ask_openclaw",
  "description": "Ask the OpenClaw agent to perform a task using its full tool capabilities",
  "parameters": {
    "type": "object",
    "properties": {
      "request": {
        "type": "string",
        "description": "Natural language request for the agent"
      }
    },
    "required": ["request"]
  }
}
```

### Check Session Sync

```bash
# Bridge health
curl http://localhost:8082/health

# Active sessions
curl http://localhost:8082/sessions

# Manual transcript sync
curl -X POST http://localhost:8082/sync-transcript \
  -H "Content-Type: application/json" \
  -d '{"callId": "CA..."}'
```

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook` | POST | OpenAI/Twilio webhook receiver |
| `/call` | POST | Initiate outbound call |
| `/call/{id}` | DELETE | Cancel call |
| `/calls` | GET | List active calls |
| `/history/{id}` | GET | Get call history |
| `/history/{id}/transcript` | GET | Get call transcript |
| `/health` | GET | Health check |

### Session Bridge Endpoints (port 8082)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/call-event` | POST | Receive call events |
| `/sync-transcript` | POST | Manual transcript sync |
| `/sessions` | GET | List active sessions |
| `/health` | GET | Health check |

## Configuration

### Agent Personality

Edit `config/agent.json`:

```json
{
  "name": "Nia",
  "instructions": "You are Nia, a helpful AI assistant. Be concise but friendly.",
  "voice": "nova",
  "model": "gpt-4o-realtime-preview"
}
```

### Available Voices

- `alloy` - Neutral, balanced
- `echo` - Warm, conversational
- `fable` - Expressive, dynamic
- `onyx` - Deep, authoritative
- `nova` - Friendly, upbeat ⭐
- `shimmer` - Clear, professional

## Cost

- **OpenAI Realtime API**: ~$0.06/min (input) + ~$0.24/min (output)
- **Twilio**: ~$0.01/min (varies by country)

Total: ~$0.30/minute for voice conversations.

## Troubleshooting

### "Voice channel not showing in openclaw status"

```bash
# Check plugin is loaded
openclaw plugins list

# Restart gateway
openclaw gateway restart
```

### "Outbound calls failing"

```bash
# Check webhook server
curl http://localhost:8080/health

# Verify Twilio credentials in .env
```

### "Transcripts not syncing"

```bash
# Check bridge health
curl http://localhost:8082/health

# Check for port conflict (old Python bridge vs new TS bridge)
lsof -i :8082
```

## Limitations

- Real-time responses during calls use OpenAI Realtime API (not OpenClaw's model)
- `ask_openclaw` adds ~1-3s latency for tool calls
- No persistent conversation memory within single call (yet)

## Contributing

PRs welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Current priorities:
- [ ] Real-time OpenClaw responses during calls
- [ ] Call recording storage
- [ ] Allowlist/security enforcement
- [ ] Multi-account support

## License

MIT

---

Built with ✨ by Nia
