# OpenClaw Voice Channel Integration Guide

## Phase 2: Integration Bridge Complete

This guide covers the completed Phase 2 integration between the TypeScript Voice Channel Plugin and the existing Python webhook server infrastructure.

## 🏗️ Architecture Overview

The integration consists of three main components working together:

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  TypeScript Plugin  │    │  Integration Bridge │    │  Python Webhook     │
│  (OpenClaw Session  │◄──►│  (Event Routing &   │◄──►│  (Voice Call        │
│   Management)       │    │   State Sync)       │    │   Handling)         │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
         │                           │                           │
         ▼                           ▼                           ▼
   OpenClaw Context            Session Mapping              OpenAI Realtime API
   Memory Integration          Event Translation           Twilio Integration
   Cross-Channel Linking       Health Monitoring           Call Recording
```

### Component Responsibilities

1. **TypeScript Plugin** (`src/channel/voice/integrated-plugin.ts`)
   - Manages OpenClaw sessions and context
   - Handles memory integration and persistence
   - Provides channel plugin interface
   - Manages cross-channel session linking

2. **Integration Bridge** (`scripts/openclaw-webhook-bridge.py`)
   - Routes calls between TypeScript and Python
   - Maintains session ID mappings
   - Forwards webhook events
   - Provides health monitoring

3. **Python Webhook Server** (`scripts/webhook-server.py`)
   - Handles actual voice call operations
   - Interfaces with OpenAI Realtime API
   - Manages Twilio integration for outbound calls
   - Handles call recording and transcription

## 🚀 Quick Start

### 1. Prerequisites

**Environment Variables:**
```bash
# Required
export OPENAI_API_KEY="your-openai-api-key"
export OPENAI_PROJECT_ID="your-openai-project-id"

# Optional (for outbound calls)
export TWILIO_ACCOUNT_SID="your-twilio-account-sid"
export TWILIO_AUTH_TOKEN="your-twilio-auth-token"
export TWILIO_PHONE_NUMBER="your-twilio-phone-number"

# Optional (for webhook security)
export WEBHOOK_SECRET="your-webhook-secret"
```

**Dependencies:**
```bash
# Python dependencies
pip install fastapi uvicorn httpx twilio pydantic

# Node.js dependencies  
cd src && npm install
```

### 2. Start the Integrated System

Use the provided startup script:

```bash
chmod +x scripts/start-integrated-system.sh
./scripts/start-integrated-system.sh
```

This starts all three components:
- Python Webhook Server (port 8080)
- Integration Bridge (port 8082)
- TypeScript Plugin (port 8081)

### 3. Verify Integration

Check system health:
```bash
# Check all services
curl http://localhost:8080/health  # Python server
curl http://localhost:8082/health  # Bridge
curl http://localhost:8081/health  # TypeScript plugin

# Check integration status
curl http://localhost:8081/status
```

## 📞 Making Calls

### Outbound Call via OpenClaw

```javascript
const { IntegratedVoiceChannelPlugin } = require('./src/channel/voice/integrated-plugin');

const plugin = new IntegratedVoiceChannelPlugin(config);
await plugin.initialize();

// Initiate call with OpenClaw context
const sessionId = await plugin.initiateOutgoingCall(
  '+1234567890',           // Phone number
  '+1987654321',           // Caller ID (optional)
  'Hello, this is a test'  // Initial context (optional)
);

console.log('Call initiated, session:', sessionId);
```

### Outbound Call via REST API

```bash
curl -X POST http://localhost:8082/openclaw/call \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+1234567890",
    "caller_id": "+1987654321", 
    "openclaw_session_id": "session_123",
    "context": {
      "agent_identity": "I am your helpful assistant",
      "user_profile": "Frequent caller, prefers brief responses",
      "recent_memory": "Last discussed appointment scheduling"
    }
  }'
```

### Inbound Call Handling

Inbound calls are automatically handled by the Python server and forwarded to the TypeScript plugin with OpenClaw session creation.

## 🔄 Event Flow

### Outbound Call Flow

1. **TypeScript Plugin** receives call request
2. **Bridge** forwards to Python server with OpenClaw context
3. **Python Server** initiates call via Twilio → OpenAI
4. **Bridge** maps Python call ID to OpenClaw session ID
5. **Webhook events** flow back: Python → Bridge → TypeScript → OpenClaw

### Inbound Call Flow

1. **Python Server** receives OpenAI webhook (incoming call)
2. **Python Server** auto-accepts with default configuration  
3. **Bridge** detects new call, creates OpenClaw session mapping
4. **TypeScript Plugin** receives session creation event
5. **Context injection** happens automatically based on caller history

### Message Flow (During Call)

1. **User speaks** → OpenAI Realtime API processes
2. **Python Server** receives transcript via webhook
3. **Bridge** forwards transcript to TypeScript Plugin
4. **TypeScript Plugin** converts to OpenClaw message
5. **OpenClaw** processes message and generates response
6. **Response** flows back through same path to voice output

## 🎛️ Configuration

### Main Configuration File

Edit `config/integration-config.yaml`:

```yaml
# OpenAI settings
openai:
  model: "gpt-4o-realtime-preview"
  voice: "alloy"

# Call behavior
call:
  defaultInstructions: "You are a helpful AI assistant..."
  recordCalls: true
  maxCallDurationMinutes: 30

# OpenClaw integration  
openclaw:
  memoryEnabled: true
  contextMaxTokens: 8000
  crossChannelEnabled: true

# Bridge settings
bridge:
  monitoring:
    healthCheckInterval: 30000
    alertOnFailure: true
```

### Environment-Specific Settings

Create `.env` file:
```bash
OPENAI_API_KEY=your-key
OPENAI_PROJECT_ID=your-project
TWILIO_ACCOUNT_SID=your-sid
TWILIO_AUTH_TOKEN=your-token
TWILIO_PHONE_NUMBER=+1234567890
WEBHOOK_SECRET=your-secret
```

## 🔍 Monitoring and Debugging

### Health Endpoints

```bash
# Overall system health
curl http://localhost:8081/status

# Individual service health
curl http://localhost:8080/health  # Python server
curl http://localhost:8082/health  # Bridge  
curl http://localhost:8081/health  # TypeScript plugin
```

### Session Management

```bash
# List active OpenClaw sessions
curl http://localhost:8082/openclaw/sessions

# Get specific session details
curl http://localhost:8082/openclaw/session/{session_id}

# List active calls (Python server view)
curl http://localhost:8080/calls
```

### Call History

```bash
# Get call history
curl http://localhost:8080/history?limit=10

# Get call transcript
curl http://localhost:8080/history/{call_id}/transcript

# Download call audio
curl http://localhost:8080/history/{call_id}/audio -o call_audio.wav
```

### Logs

- **Python Server**: Console output or configure logging in webhook-server.py
- **Bridge**: Console output or configure logging in openclaw-webhook-bridge.py  
- **TypeScript Plugin**: Console output or configure logging in integrated-plugin.ts

## 🔧 Development and Testing

### Manual Testing

1. **Test outbound call**:
   ```bash
   curl -X POST http://localhost:8082/openclaw/call \
     -H "Content-Type: application/json" \
     -d '{"to": "+1234567890", "openclaw_session_id": "test_123"}'
   ```

2. **Monitor events**:
   ```bash
   # Watch logs in separate terminals
   tail -f python_server.log
   tail -f bridge.log  
   tail -f typescript_plugin.log
   ```

3. **Test inbound call**:
   - Call your OpenAI project's SIP number
   - Check session creation in logs
   - Verify context injection

### Development Mode

Set environment variable:
```bash
export VOICE_DEV_MODE=true
```

This enables:
- More verbose logging
- Mock mode for testing without actual calls
- Additional debugging endpoints

## 🚨 Troubleshooting

### Common Issues

**1. Services Won't Start**
- Check port availability: `lsof -i :8080,:8081,:8082`
- Verify environment variables are set
- Check Python dependencies: `pip list`
- Check Node.js dependencies: `cd src && npm list`

**2. Calls Not Connecting**  
- Verify OpenAI project configuration
- Check Twilio credentials (for outbound)
- Ensure webhook URLs are reachable
- Check firewall settings

**3. Context Not Injecting**
- Verify session ID mapping in bridge
- Check TypeScript plugin initialization
- Review OpenClaw workspace permissions
- Verify memory files exist and are readable

**4. Webhook Events Missing**
- Check bridge health: `curl http://localhost:8082/health`
- Verify TypeScript plugin webhook endpoint
- Check network connectivity between services
- Review webhook signature verification

### Debug Commands

```bash
# Check service connectivity
curl -v http://localhost:8080/health
curl -v http://localhost:8082/health  
curl -v http://localhost:8081/health

# Check session mappings
curl http://localhost:8082/openclaw/sessions | jq

# Test webhook forwarding
curl -X POST http://localhost:8082/webhook/forward \
  -H "Content-Type: application/json" \
  -d '{"call_id": "test", "event_type": "test_event", "data": {}}'
```

## 🔄 Next Steps (Phase 3 Ideas)

1. **Advanced Context Injection**
   - Real-time instruction updates during calls
   - Dynamic voice/personality switching
   - Advanced caller identification

2. **Enhanced Integration**
   - Direct OpenClaw message routing
   - Multi-channel conversation threading
   - Advanced session linking

3. **Production Features**
   - Load balancing across multiple servers
   - Call queue management
   - Advanced monitoring and alerting
   - Auto-scaling capabilities

## 📁 File Structure

```
openai-voice-skill/
├── src/
│   ├── channel/voice/
│   │   ├── integrated-plugin.ts         # Main plugin (NEW)
│   │   ├── integrated-call-handler.ts   # Call handling with bridge (NEW)
│   │   ├── session-manager.ts          # Session management
│   │   ├── context-manager.ts          # Context injection
│   │   └── types.ts                    # Type definitions
│   └── bridge/
│       └── python-webhook-bridge.ts    # Bridge to Python (NEW)
├── scripts/
│   ├── webhook-server.py               # Original Python server
│   ├── openclaw-webhook-bridge.py      # Integration bridge (NEW)
│   └── start-integrated-system.sh      # Startup script (NEW)
├── config/
│   └── integration-config.yaml         # Main configuration (NEW)
└── INTEGRATION_GUIDE.md               # This file (NEW)
```

## 🎯 Success Criteria Met

✅ **TypeScript architecture foundation complete**  
✅ **Integration bridge with Python webhook server built**  
✅ **OpenClaw session management integrated**  
✅ **Event routing and state synchronization working**  
✅ **Context injection from OpenClaw to voice calls**  
✅ **Webhook event forwarding Python → TypeScript → OpenClaw**  
✅ **Health monitoring and error handling**  
✅ **Configuration management and environment setup**  
✅ **Documentation and startup scripts**

The Phase 2 integration is **complete and ready for review**! 🚀