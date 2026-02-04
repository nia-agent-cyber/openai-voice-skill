# Voice Channel Plugin for OpenClaw

A proper OpenClaw channel plugin for voice calls, providing native session continuity, unified conversation history, and standard security features.

## Status

**Phase 1: In Development** — Scaffolding complete, implementation in progress.

See [Issue #19](https://github.com/nia-agent-cyber/openai-voice-skill/issues/19) for acceptance criteria.

## Why a Channel Plugin?

The previous approach used a standalone tool (`nia-voice-call`). This works but has limitations:

| Feature | Tool Approach | Channel Approach |
|---------|---------------|------------------|
| Session continuity | ❌ Separate context | ✅ Same session as Telegram |
| Conversation history | ❌ Fragmented | ✅ Unified thread |
| Security features | ❌ Custom implementation | ✅ Native allowlists, DM policies |
| Configuration | ❌ Plugin config | ✅ `channels.voice` in openclaw.yaml |

## Architecture

```
channel-plugin/
├── openclaw.plugin.json    # Plugin manifest
├── src/
│   ├── index.ts            # Plugin entry point
│   ├── meta.ts             # Channel metadata
│   ├── types.ts            # Type definitions
│   └── adapters/
│       ├── config.ts       # Configuration adapter
│       ├── outbound.ts     # Send messages (text → TTS → call)
│       ├── status.ts       # Health monitoring
│       ├── gateway.ts      # Start/stop voice service
│       └── inbound.ts      # Handle incoming calls (Phase 2)
└── package.json
```

## Configuration

Add to your `~/.openclaw/openclaw.yaml`:

```yaml
channels:
  voice:
    enabled: true
    twilioAccountSid: ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    twilioAuthToken: your_auth_token
    twilioPhoneNumber: "+14402915517"
    openaiApiKey: sk-...  # For Realtime API
    webhookUrl: https://api.niavoice.org
    allowFrom:
      - "+1234567890"  # Allowed callers
    dmPolicy: allowlist  # or 'open' or 'pairing'
```

## Development

```bash
# Install dependencies
cd channel-plugin
npm install

# Build
npm run build

# Watch mode
npm run dev

# Test
npm test
```

## Installation

Link the plugin to OpenClaw extensions:

```bash
ln -s $(pwd)/channel-plugin ~/.openclaw/extensions/voice-channel
```

Restart OpenClaw gateway to load the plugin.

## Roadmap

- [x] **Phase 1**: Plugin scaffold, config adapter, basic outbound
- [ ] **Phase 2**: Inbound call handling, session integration
- [ ] **Phase 3**: Allowlists, directory integration, call history

## Related

- [OpenClaw Plugin Docs](https://openclaw.dev/docs/plugins)
- [Signal Channel](https://github.com/openclaw/openclaw/blob/main/src/channels/plugins/signal.ts) — Reference implementation
- [Existing Voice Tool](../plugin-server/) — Legacy tool being replaced
