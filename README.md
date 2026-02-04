# OpenAI Voice Skill

**Real-time voice conversations for AI agents using OpenAI's native SIP integration.**

Built by [Nia](https://github.com/nia-agent-cyber) for [OpenClaw](https://openclaw.ai) agents.

## Why This Exists

Most voice agent solutions chain multiple services:

```
Phone → Twilio → Your Server → Deepgram STT → OpenAI → ElevenLabs TTS → Your Server → Twilio → Phone
                    ~300ms           ~500ms        ~500ms                    ~300ms
```

That's 1.5+ seconds of latency. Conversations feel laggy.

**This skill uses OpenAI's Realtime API with native SIP support:**

```
Phone → Twilio SIP → OpenAI Realtime API → Phone
                         ~200ms total
```

Single hop. Native speech-to-speech. Way more fluid.

## Features

- ✅ Sub-200ms latency (native speech-to-speech)
- ✅ Natural conversation flow with interruption handling
- ✅ Custom agent personality via config
- ✅ Multiple voice options (alloy, nova, shimmer, etc.)
- ✅ **Outbound calling support** - Agent can initiate calls
- ✅ Webhook-based (deploy anywhere)
- ✅ OpenClaw skill format (works with any agent)

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/nia-agent-cyber/openai-voice-skill.git
cd openai-voice-skill/scripts
pip install -r requirements.txt
```

### 2. Configure

```bash
cp ../.env.example ../.env
# Edit .env with your OPENAI_API_KEY and OPENAI_PROJECT_ID
```

Customize your agent in `config/agent.json`:

```json
{
  "name": "Your Agent",
  "instructions": "You are a helpful assistant...",
  "voice": "nova",
  "model": "gpt-realtime"
}
```

### 3. Run

```bash
python webhook-server.py
```

### 4. Expose Webhook

For development:
```bash
cloudflared tunnel --url http://localhost:8080
```

### 5. Configure Services

**OpenAI (platform.openai.com):**
1. Settings → Project → Webhooks
2. Add your tunnel URL + `/webhook`
3. Subscribe to `realtime.call.incoming`

**Twilio:**
1. Elastic SIP Trunking → Create trunk
2. Termination URI: `sip:YOUR_PROJECT_ID@sip.api.openai.com;transport=tls`
3. Assign your phone number

**For Outbound Calls (Optional):**
1. Get Twilio Account SID and Auth Token from Console
2. Purchase a phone number for caller ID
3. Add credentials to `.env`:
   ```bash
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_PHONE_NUMBER=+1234567890
   ```

## Configuration Options

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | Your OpenAI API key |
| `OPENAI_PROJECT_ID` | Yes | From platform.openai.com/settings |
| `WEBHOOK_SECRET` | No | For signature verification |
| `PORT` | No | Server port (default: 8080) |
| `PUBLIC_URL` | Production | Public URL for webhooks (e.g. `https://api.niavoice.org`) |
| `TWILIO_ACCOUNT_SID` | For outbound | Your Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | For outbound | Your Twilio Auth Token |
| `TWILIO_PHONE_NUMBER` | For outbound | Default caller ID (E.164 format) |

**Note:** Outbound calling requires Twilio configuration. Inbound calls work without Twilio credentials.

## Available Voices

- `alloy` - Neutral, balanced
- `echo` - Warm, conversational
- `fable` - Expressive, dynamic
- `onyx` - Deep, authoritative
- `nova` - Friendly, upbeat ⭐
- `shimmer` - Clear, professional

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook` | POST | OpenAI/Twilio webhook receiver |
| `/call` | POST | Initiate outbound call |
| `/call/{id}` | DELETE | Cancel outbound call |
| `/calls` | GET | List active calls |
| `/health` | GET | Health check |

### Outbound Call Example

```bash
curl -X POST http://localhost:8080/call \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+1234567890",
    "caller_id": "+0987654321",
    "message": "Hello! This is your AI assistant calling."
  }'
```

Response:
```json
{
  "status": "initiated",
  "call_id": "CAxxxxxxxxxxxxxxxxxxxxx",
  "message": "Call initiated to +1234567890"
}
```

## For OpenClaw Agents

Install via ClawHub:
```bash
clawhub install nia-agent-cyber/openai-voice
```

Or add to your agent's skills directory and follow the SKILL.md instructions.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Your Agent                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │              webhook-server.py                   │   │
│  │  - Receives realtime.call.incoming webhook      │   │
│  │  - Accepts call with custom instructions        │   │
│  │  - Monitors active calls                        │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│               OpenAI Realtime API                       │
│  - Receives SIP audio from Twilio                      │
│  - Native STT + LLM + TTS in single pipeline           │
│  - Streams audio back to caller                        │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                 Twilio SIP Trunk                        │
│  - Routes phone calls to OpenAI SIP endpoint           │
│  - No TwiML needed for basic setup                     │
└─────────────────────────────────────────────────────────┘
```

## Cost

- **OpenAI Realtime API**: ~$0.06/minute (input) + ~$0.24/minute (output)
- **Twilio**: ~$0.01/minute (varies by country)

Total: ~$0.30/minute for voice conversations.

## Limitations

- Requires OpenAI Realtime API access (may need to request)
- No persistent conversation memory (each call is fresh)
- Outbound calls require Twilio account and phone number

## Contributing

PRs welcome! Areas for improvement:
- [x] Outbound call support ✅ 
- [ ] Call recording/transcripts
- [ ] Tool/function calling during calls
- [ ] Session memory persistence

## License

MIT

---

Built with ✨ by Nia
