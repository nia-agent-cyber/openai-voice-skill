# Session Context Injection for Voice Calls

This feature transforms the voice channel from an isolated tool into a proper channel with full OpenClaw session context. Voice calls now start with actual conversation context instead of generic responses.

## 🎯 What This Enables

**Before:**
```
Voice Agent: "Hi, how can I help you today?"
```

**After:**
```
Voice Agent: "Hey Remi! Following up on our conversation about the voice integration project. How did the OpenAI API testing go?"
```

## 🏗️ Architecture

### Core Components

1. **Session Context Bridge** (`scripts/session_context.py`)
   - Extracts conversation history from OpenClaw memory files
   - Parses user preferences and ongoing projects
   - Formats context for OpenAI Realtime API

2. **OpenClaw Integration** (`scripts/openclaw_bridge.py`)
   - Maps phone numbers to OpenClaw user sessions
   - Manages context caching and security
   - Handles call memory recording

3. **Enhanced Webhook Handler** (modified `scripts/webhook-server.py`)
   - Injects session context when accepting calls
   - Supports both inbound and outbound call context
   - Fallback to basic mode if context extraction fails

### Data Flow

```
Incoming Call → Identify Caller → Extract Context → Format Instructions → OpenAI Realtime API
     ↓              ↓                   ↓                    ↓
Phone Number → User Mapping → Memory Files → Enhanced Instructions
```

## 🚀 Setup Guide

### 1. Configure Phone Mapping

Edit `config/phone_mapping.json` to map phone numbers to users:

```json
{
  "+1234567890": {
    "name": "Remi",
    "session_id": "main",
    "relationship": "primary_user",
    "preferred_name": "Remi",
    "context_level": "full"
  }
}
```

**Fields:**
- `name`: Display name for the user
- `session_id`: OpenClaw session identifier  
- `relationship`: `primary_user`, `team_member`, `client`, `unknown`
- `preferred_name`: How the AI should address them
- `context_level`: `full`, `work_only`, `limited`

### 2. Environment Variables

```bash
# Optional: Override workspace detection
export OPENCLAW_WORKSPACE=/path/to/your/workspace

# Optional: Fallback phone mapping as JSON
export PHONE_USER_MAPPING='{""+15551234567":{"name":"John","session_id":"main","relationship":"primary_user"}}'

# Optional: OpenClaw API integration (future)
export OPENCLAW_API_URL=http://localhost:3000
export OPENCLAW_API_KEY=your_api_key_here
```

### 3. Workspace Structure

Your OpenClaw workspace should have:

```
workspace/
├── SOUL.md           # Agent identity and personality
├── USER.md           # User profile information
├── MEMORY.md         # Long-term memory (main sessions only)
├── memory/
│   ├── 2024-02-04.md # Daily conversation logs
│   ├── 2024-02-03.md
│   └── ...
├── phone_mapping.json # Phone number mappings
└── call_contexts/     # Temporary call context (auto-created)
```

### 4. Start the Enhanced Server

```bash
cd scripts
python webhook-server.py
```

The server will now automatically inject session context for all voice calls.

## 🔧 Configuration Options

### Context Security Levels

The system respects different relationship levels:

- **Primary User** (`primary_user`): Full context including personal memory
- **Team Member** (`team_member`): Work-related context only, personal info filtered
- **Client** (`client`): Limited context, project-specific only
- **Unknown** (`unknown`): No historical context, helpful but cautious

### Context Extraction Settings

Modify in code or add to config:

```python
context = extractor.extract_recent_context(
    hours_back=24,        # How far back to look
    max_messages=20,      # Max conversation messages
)
```

## 📋 Testing the Feature

### 1. Run the Demo Script

```bash
python context_example.py
```

This will:
- Test context extraction from your workspace
- Show caller identification
- Demonstrate instruction formatting
- Simulate a complete call flow

### 2. Make a Test Call

1. Add your phone number to `config/phone_mapping.json`
2. Start the webhook server
3. Make a call to your OpenAI voice number
4. Listen for context-aware responses

### 3. Check the Logs

The server logs will show:
```
INFO - Identifying caller and extracting context for +15****1234
INFO - Generated enhanced instructions for Remi (1847 chars)
INFO - Call abc123 accepted successfully with context for Remi
```

## 🔍 How Context Extraction Works

### Memory File Parsing

The system reads:
- `SOUL.md` - Agent identity
- `USER.md` - User profile  
- `MEMORY.md` - Long-term memories
- `memory/YYYY-MM-DD.md` - Daily conversation logs

### Conversation Pattern Recognition

Extracts conversations using patterns like:
```
14:30 - User: Let's work on the API integration
14:31 - Nia: Great! I'll help you with that.
```

### Project Context Detection

Looks for:
- README.md, PROJECT.md files
- TODO.md, GOALS.md lists
- Recent decisions and conclusions

### Context Summarization

Generates voice-appropriate summaries:
```
User: Remi (primary_user) | Recent activity: 5 conversations | 
Key topics: API, voice integration | Active projects: OpenAI Voice Skill
```

## 🛡️ Security & Privacy

### Data Encryption

Sensitive call data is encrypted when `ENCRYPT_SESSION_DATA=true`:
- Phone numbers
- Personal context
- Call metadata

### Context Filtering

Different users see different context levels:
- **Unknown callers**: No personal history
- **Team members**: Work context only, personal details filtered
- **Primary users**: Full context access

### Memory Safety

- Temporary call contexts auto-deleted after calls
- Phone numbers masked in logs
- Session data cached with TTL limits

## 🚨 Troubleshooting

### Context Not Working

1. **Check workspace detection:**
   ```bash
   python -c "from session_context import create_context_extractor; print(create_context_extractor().workspace_path)"
   ```

2. **Verify memory files exist:**
   ```bash
   ls -la memory/
   ls -la SOUL.md USER.md MEMORY.md
   ```

3. **Test phone mapping:**
   ```bash
   python -c "from openclaw_bridge import create_openclaw_bridge; import asyncio; print(asyncio.run(create_openclaw_bridge().identify_caller('+1234567890')))"
   ```

### Common Issues

**"No workspace path available"**
- Set `OPENCLAW_WORKSPACE` environment variable
- Ensure SOUL.md exists in workspace root

**"Failed to identify caller"**
- Check phone number format (E.164: +1234567890)
- Verify `config/phone_mapping.json` exists and is valid JSON

**"Context extraction failed"**
- Check file permissions on memory files
- Ensure memory files contain readable content

### Fallback Mode

If context extraction fails, the system gracefully falls back to basic instructions with a note that context extraction failed. Calls will still work, just without enhanced context.

## 🔄 Memory Integration

### Call Memory Recording

Completed calls automatically append to daily memory files:

```markdown
## 2024-02-04T14:30:00 - Voice Call
**Caller:** Remi
**Duration:** 180.5s
**Summary:** Discussed voice integration project progress
**Key Points:**
- Session context working well
- Need to test with different users
- Deploy to production next week
```

### Context Updates

During calls, context can be updated:
```python
await openclaw_bridge.update_call_context(call_id, {
    "user_mentioned_project": "voice integration",
    "discussed_topics": ["OpenAI API", "session context"]
})
```

## 🎛️ Advanced Configuration

### Custom Context Extractors

Extend the `SessionContextExtractor` class:

```python
class CustomExtractor(SessionContextExtractor):
    def _extract_project_info(self, content, filename):
        # Custom project parsing logic
        return super()._extract_project_info(content, filename)
```

### API Integration

Future enhancement: Direct OpenClaw API integration:

```python
# When OPENCLAW_API_KEY is set, the bridge will:
# 1. Query OpenClaw API for user sessions
# 2. Retrieve live conversation state
# 3. Get real-time context updates
```

### Webhook Forwarding

The system can forward call events to other services:

```python
# Events fired: call_initiated, context_extracted, call_ended
# Customize in openclaw_bridge.py
```

## 📊 Metrics & Monitoring

The system logs key metrics:

- Context extraction time
- Instruction length generated
- Cache hit/miss rates  
- Caller identification success
- Fallback mode activation

Monitor these in your logs to optimize performance.

## 🛣️ Roadmap

Planned enhancements:

1. **Real-time Context Updates**: Live conversation context injection
2. **Multi-language Support**: Context extraction in different languages
3. **Visual Context Display**: Web dashboard showing active call contexts
4. **Context Analytics**: Insights on context usage and effectiveness
5. **Custom Memory Sources**: Support for external memory systems

## 💡 Best Practices

1. **Keep Memory Files Current**: Regular conversation logging improves context quality
2. **Update Phone Mappings**: Add new users as they join your system
3. **Monitor Context Size**: Very large contexts may slow call setup
4. **Test with Real Scenarios**: Use actual conversation patterns in testing
5. **Privacy First**: Be mindful of what context different callers should see

---

This feature transforms voice calls from generic interactions to contextually-aware conversations that feel natural and informed. The AI now truly knows who it's talking to and what you've been working on together.