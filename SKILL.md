# OpenAI Voice Skill

Real-time voice conversations using OpenAI's native SIP integration. Way more fluid than multi-hop STT→LLM→TTS solutions.

## How It Works

```
Phone call → Twilio SIP → OpenAI Realtime API
                              ↓
                         Your webhook accepts call
                         with custom instructions
                              ↓
                         Native voice conversation
```

OpenAI handles STT, LLM, and TTS in a single low-latency pipeline.

## Prerequisites

1. **Twilio account** with a phone number
2. **OpenAI API key** with Realtime API access
3. **Public webhook URL** (ngrok, cloudflared, or deployed server)

## Setup

### 1. Install Dependencies

```bash
cd scripts
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials:
# - OPENAI_API_KEY
# - OPENAI_PROJECT_ID (from platform.openai.com/settings)
# - WEBHOOK_SECRET (generate with: openssl rand -hex 32)
```

### 3. Start Webhook Server

```bash
python webhook-server.py
```

### 4. Expose Webhook (Development)

```bash
# Using cloudflared (recommended, no auth needed)
cloudflared tunnel --url http://localhost:8080

# Or ngrok
ngrok http 8080
```

### 5. Configure OpenAI Webhook

1. Go to platform.openai.com/settings → Project → Webhooks
2. Add webhook URL: `https://your-tunnel.trycloudflare.com/webhook`
3. Subscribe to: `realtime.call.incoming`

### 6. Configure Twilio SIP Trunk

1. In Twilio Console → Elastic SIP Trunking → Create trunk
2. Set Termination SIP URI: `sip:$PROJECT_ID@sip.api.openai.com;transport=tls`
3. Assign your phone number to the trunk

## Customization

Edit `config/agent.json` to customize:

```json
{
  "name": "Your Agent Name",
  "instructions": "You are a helpful assistant...",
  "voice": "alloy",
  "model": "gpt-realtime"
}
```

Available voices: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`

## Making Outbound Calls

```bash
# Via API
curl -X POST http://localhost:8080/call \
  -H "Content-Type: application/json" \
  -d '{"to": "+1234567890"}'
```

## Monitoring

```bash
# View active calls
curl http://localhost:8080/calls

# View call logs
tail -f logs/calls.log
```

## Troubleshooting

**Call doesn't connect:**
- Verify Twilio SIP trunk points to correct OpenAI SIP URI
- Check OpenAI webhook is receiving events
- Ensure PROJECT_ID matches your OpenAI project

**Poor audio quality:**
- OpenAI Realtime uses Opus codec by default
- Ensure network has low latency to OpenAI servers

**Webhook not firing:**
- Verify webhook URL is publicly accessible
- Check webhook signature validation
