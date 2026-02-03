# OpenClaw Voice Channel Plugin

This directory contains the implementation of Issue #10: transforming the openai-voice-skill into a proper OpenClaw channel plugin.

## Overview

The voice channel plugin integrates voice calls as a first-class OpenClaw channel with:

- **Session Management**: Voice calls create proper OpenClaw sessions with unique IDs
- **Memory Integration**: Access to MEMORY.md, daily memory files, and cross-channel context
- **Context Injection**: Dynamic context loading based on caller history and agent state  
- **Session Bridging**: Link voice sessions to existing OpenClaw sessions (telegram, discord, etc.)
- **Workflow Integration**: Voice calls can trigger OpenClaw actions and access tools
- **Channel Handoffs**: Seamless transfer between voice and text channels

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                Voice Channel Plugin                     │
│  ┌─────────────────┬─────────────────┬─────────────────┐│
│  │  Session Mgr    │  Context Mgr    │   Call Handler  ││
│  │                 │                 │                 ││
│  │ • Creates       │ • Loads memory  │ • OpenAI API    ││
│  │   sessions      │ • Injects       │ • Audio stream  ││
│  │ • Links across  │   context       │ • Transcription ││
│  │   channels      │ • Persists      │ • Call mgmt     ││
│  │ • Caller        │   conversations │                 ││
│  │   history       │                 │                 ││
│  └─────────────────┴─────────────────┴─────────────────┘│
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                OpenClaw Core                           │
│  • Session management                                  │
│  • Memory system (MEMORY.md, daily files)            │
│  • Cross-channel messaging                           │
│  • Tool/workflow integration                         │
└─────────────────────────────────────────────────────────┘
```

## Components

### VoiceChannelPlugin (`index.ts`)
Main plugin class implementing the OpenClaw channel interface:
- `createSession()` - Creates voice sessions with OpenClaw integration
- `sendMessage()` - Handles OpenClaw messages → voice output  
- `receiveAudio()` - Processes voice input → OpenClaw messages
- `linkToSession()` - Links voice calls to existing sessions

### VoiceSessionManager (`session-manager.ts`)
Manages voice call sessions:
- Session lifecycle management
- Caller identity tracking and history
- Cross-channel session linking
- Session persistence and recovery

### VoiceContextManager (`context-manager.ts`)  
Handles OpenClaw context integration:
- Memory file access (MEMORY.md, memory/YYYY-MM-DD.md)
- Context injection with token management
- Cross-channel context loading
- Conversation persistence

### VoiceCallHandler (`call-handler.ts`)
Manages actual voice call interactions:
- OpenAI Realtime API integration
- Audio streaming and processing
- Webhook event handling
- Call lifecycle management

## Session Flow

### Incoming Call
```
Phone Call → OpenAI Webhook → Create Session → Inject Context → Accept Call
     ↓                            ↓               ↓             ↓
Link to existing    →    Load memory files  →  Prepare    →   Start
OpenClaw session         & caller history      instructions   conversation
```

### Outgoing Call  
```
OpenClaw Request → Create Session → Inject Context → Initiate Call
       ↓               ↓              ↓               ↓
Load target info → Load memory → Prepare context → Start conversation
```

### Context Injection
The plugin injects relevant context from:
- `SOUL.md` - Agent identity and personality
- `USER.md` - User profile and preferences  
- `memory/YYYY-MM-DD.md` - Recent conversation history
- Caller history - Previous interactions with this phone number
- Cross-channel context - Related conversations from telegram/discord
- `HEARTBEAT.md` / `TODO.md` - Current tasks and projects

## Integration Points

### OpenClaw Session System
- Voice sessions use standard OpenClaw session IDs
- Sessions appear in OpenClaw's session management
- Voice messages flow through OpenClaw's message routing
- Sessions can be linked to telegram, discord, email sessions

### Memory System
- Voice calls append to daily memory files (`memory/YYYY-MM-DD.md`)
- Call summaries contribute to agent's long-term memory
- Caller-specific memory persists across calls
- Memory is searchable and accessible to other channels

### Tool/Workflow Integration
- Voice calls can trigger OpenClaw tools and workflows
- Agent can access files, send emails, manage calendar during calls
- Multi-step workflows can span voice and text channels
- Tool results can be communicated via voice

## Configuration

The plugin integrates with OpenClaw's configuration system:

```yaml
channels:
  voice:
    enabled: true
    plugin: "@openclaw/voice-channel-plugin"
    openai: { ... }
    integration:
      memory_enabled: true
      cross_channel_enabled: true
      context_max_tokens: 2000
```

See `config/openclaw-voice-config.yaml` for full configuration options.

## Message Flow

### Voice → OpenClaw
1. Audio received from call
2. OpenAI Realtime API transcribes  
3. Transcript → OpenClawMessage
4. Message routed through OpenClaw system
5. Agent processes with full context
6. Response → Voice output

### OpenClaw → Voice  
1. Agent generates response/action
2. OpenClawMessage → Voice instruction
3. Instruction sent to OpenAI Realtime API
4. Audio synthesized and streamed to caller

## Implementation Status

- ✅ **Channel Plugin Architecture** - Core plugin structure implemented
- ✅ **Session Management** - Voice session creation and lifecycle  
- ✅ **Context Integration** - Memory file access and context injection
- ✅ **Call Handling** - OpenAI Realtime API integration foundation
- 🔄 **Active Development** - Integration with existing webhook server
- ⏳ **Next Phase** - Testing and refinement

## Next Steps

1. **Integration Bridge** - Connect TypeScript plugin to existing Python webhook server
2. **Context Testing** - Validate memory file access and context injection  
3. **Session Linking** - Implement cross-channel session linking
4. **Tool Integration** - Enable tool/workflow access during calls
5. **Production Hardening** - Error handling, monitoring, security

## Usage Example

```typescript
// Initialize voice channel plugin
const voicePlugin = new VoiceChannelPlugin(config);
await voicePlugin.initialize();

// Handle incoming call
const sessionId = await voicePlugin.handleIncomingCall(
  callId, 
  phoneNumber,
  metadata
);

// Send message to voice session  
await voicePlugin.sendMessage(sessionId, {
  content: "Hello! How can I help you today?",
  // ... other OpenClawMessage properties
});

// Link to existing telegram session
await voicePlugin.linkToSession(sessionId, telegramSessionId);
```

This implementation provides the foundation for true voice-text-workflow continuity in OpenClaw agents.