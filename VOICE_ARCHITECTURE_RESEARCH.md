# Voice Architecture Research: OpenClaw Agent Integration

**Date:** February 4, 2026  
**Author:** Voice PM (subagent)  
**Status:** Research Complete - Recommendation Pending Review

---

## Executive Summary

Remi wants to understand what it would take to replace OpenAI Realtime as the "brain" during voice calls with the full OpenClaw agent (Claude + tools + memory + workspace). This document analyzes the architectural options, latency considerations, and implementation complexity.

**Key Finding:** A full replacement of OpenAI Realtime with STT → OpenClaw → TTS is **technically feasible** but introduces significant latency challenges. A **hybrid approach** (Option C) may provide the best balance of capability and user experience.

---

## Current Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────────┐
│   Caller    │────▶│    Twilio    │────▶│  OpenAI Realtime    │
│  (Phone)    │◀────│  (SIP/PSTN)  │◀────│  (GPT-4o-realtime)  │
└─────────────┘     └──────────────┘     └─────────────────────┘
                                                   │
                                                   │ After call ends
                                                   ▼
                                         ┌─────────────────────┐
                                         │  Session Bridge     │
                                         │  (Transcript Sync)  │
                                         └─────────────────────┘
                                                   │
                                                   ▼
                                         ┌─────────────────────┐
                                         │  OpenClaw Agent     │
                                         │  (Claude + Tools)   │
                                         └─────────────────────┘
```

### What Works Well
- **Ultra-low latency**: OpenAI Realtime has ~300-500ms total response time
- **Native speech handling**: No separate STT/TTS hops
- **Context injection**: Session context IS injected into instructions at call start
- **Transcript sync**: Conversations ARE synced to OpenClaw sessions after calls

### What's Missing
- **No live tool access**: Can't call tools during the conversation
- **No live memory access**: Can't read/write workspace files during the call
- **Different brain**: GPT-4o-realtime, not Claude
- **One-way context**: Context injected at start, but not updated during call
- **Post-hoc integration**: Cross-channel sync happens AFTER, not DURING

---

## Desired Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────────┐
│   Caller    │────▶│    Twilio    │────▶│   STT (Whisper)     │
│  (Phone)    │     │  (MediaStream│     └─────────────────────┘
└─────────────┘     │   WebSocket) │               │
       ▲            └──────────────┘               │ Text
       │                   ▲                       ▼
       │                   │             ┌─────────────────────┐
       │              Audio│             │   OpenClaw Agent    │
       │                   │             │   (Claude + Tools   │
       │                   │             │   + Memory + Full   │
       │            ┌──────┴──────┐      │   Workspace Access) │
       │            │  TTS Engine │      └─────────────────────┘
       │            │ (ElevenLabs │               │
       └────────────│  / OpenAI)  │◀──────────────┘
                    └─────────────┘         Text Response
```

### What This Enables
- **Same brain everywhere**: Claude via OpenClaw for Telegram, Discord, AND voice
- **Full tool access**: exec, read, write, browser, etc. during calls
- **Live memory access**: Can read/update MEMORY.md, workspace files in real-time
- **True channel parity**: Voice becomes just another channel, not a separate system

---

## Latency Analysis (Critical Factor)

Real-time conversation requires responses within **~1-2 seconds** to feel natural. Longer delays make conversations awkward and frustrating.

### OpenAI Realtime (Current)
| Component | Latency |
|-----------|---------|
| Twilio → OpenAI SIP | ~100ms |
| OpenAI internal STT | ~50ms (streaming) |
| OpenAI model inference | ~200-400ms |
| OpenAI internal TTS | ~50ms (streaming) |
| Audio return to Twilio | ~100ms |
| **Total** | **~300-500ms** |

### STT → OpenClaw → TTS Pipeline (Proposed)
| Component | Latency | Notes |
|-----------|---------|-------|
| Twilio MediaStream → WebSocket | ~100ms | Network hop |
| Audio buffering (for utterance) | ~500-1500ms | Wait for speech to end |
| Whisper API STT | ~500-1500ms | Depends on audio length |
| OpenClaw agent (Claude Sonnet) | ~1000-3000ms | Model inference + tool calls |
| TTS (ElevenLabs/OpenAI) | ~300-800ms | Text-to-speech generation |
| Audio streaming back | ~100ms | Network hop |
| **Total** | **~2.5-7+ seconds** | ⚠️ Unacceptable for conversation |

### The Latency Problem
- OpenAI Realtime achieves low latency by **tightly integrating** STT/LLM/TTS in one system
- The proposed pipeline has **4-5 separate network hops** and **no streaming overlap**
- Even with optimization, we're looking at **2-4x worse latency** than current

---

## Component Options

### Speech-to-Text (STT)

| Option | Latency | Quality | Cost | Real-time Ready |
|--------|---------|---------|------|-----------------|
| **OpenAI Whisper API** | 500-1500ms | Excellent | $0.006/min | ❌ Batch only |
| **Deepgram** | 200-400ms | Excellent | $0.0043/min | ✅ Streaming |
| **Assembly AI** | 300-500ms | Very Good | $0.0085/min | ✅ Streaming |
| **Google Speech-to-Text** | 200-400ms | Very Good | $0.004/min | ✅ Streaming |
| **Twilio Speech Recognition** | 200-400ms | Good | Included | ✅ Streaming |
| **Local Whisper (whisper.cpp)** | 100-300ms | Excellent | $0 | ⚠️ Requires GPU |

**Recommendation:** Deepgram or Google for real-time streaming. Whisper is best quality but batch-only (too slow).

### Text-to-Speech (TTS)

| Option | Latency (TTFB) | Quality | Cost | Streaming |
|--------|----------------|---------|------|-----------|
| **ElevenLabs** | 200-500ms | Excellent | $0.30/1K chars | ✅ Yes |
| **OpenAI TTS** | 300-600ms | Very Good | $0.015/1K chars | ✅ Yes |
| **Google Cloud TTS** | 200-400ms | Good | $0.016/1K chars | ✅ Yes |
| **Amazon Polly** | 100-300ms | Good | $0.004/1K chars | ✅ Yes |
| **PlayHT** | 300-500ms | Excellent | $0.30/1K chars | ✅ Yes |
| **sag (ElevenLabs CLI)** | 200-500ms | Excellent | Same as ElevenLabs | ✅ Yes |

**Recommendation:** ElevenLabs for quality, Amazon Polly for lowest latency.

### Audio Bridge (Twilio → Server)

| Option | Description | Complexity |
|--------|-------------|------------|
| **Twilio Media Streams** | WebSocket streaming of raw audio | Medium |
| **Twilio <Gather> verb** | Built-in speech rec, returns text | Low (but limited) |
| **Twilio + ngrok/Cloudflare** | Expose local server to Twilio | Medium |

**Recommendation:** Twilio Media Streams for full control over audio pipeline.

---

## Architectural Options

### Option A: Keep OpenAI Realtime + Add Tool Access

**Concept:** Enhance the current system to give OpenAI Realtime limited tool access via function calling.

**How it would work:**
```
OpenAI Realtime receives call
    ↓
Realtime can call "tools" (actually HTTP endpoints)
    ↓
Our server receives tool calls, executes via OpenClaw
    ↓
Results returned to Realtime to speak
```

**Pros:**
- Maintains ultra-low latency for conversation
- Minimal architecture change
- Tools available when needed

**Cons:**
- OpenAI Realtime function calling is limited/experimental
- Still GPT-4o-realtime, not Claude
- Tool calls add latency within conversation
- Complex state management between Realtime and OpenClaw
- Memory/context still not live-updated

**Effort:** Medium (2-4 weeks)
**Latency Impact:** ~500-1500ms when tools called, ~300-500ms otherwise
**Channel Parity:** Partial (tools yes, Claude no)

---

### Option B: Full STT → OpenClaw → TTS Pipeline

**Concept:** Completely replace OpenAI Realtime with our own pipeline.

**How it would work:**
```
Twilio receives call
    ↓
<Stream> to our WebSocket server
    ↓
Audio → Deepgram/Google STT (streaming)
    ↓
Text → OpenClaw agent (Claude + full tools)
    ↓
Response text → ElevenLabs TTS (streaming)
    ↓
Audio chunks → back to Twilio <Play>
```

**Implementation Requirements:**
1. **WebSocket Server**: Handle Twilio Media Streams
2. **VAD (Voice Activity Detection)**: Know when user finished speaking
3. **Streaming STT Integration**: Deepgram or Google
4. **OpenClaw Session Injection**: Route text through agent turn
5. **Streaming TTS Integration**: ElevenLabs or OpenAI
6. **Audio Format Conversion**: Twilio uses mulaw 8kHz, TTS outputs various formats
7. **Interruption Handling**: Stop TTS when user interrupts

**Pros:**
- Full channel parity (same agent everywhere)
- Claude as the brain
- Full tool access (exec, read, write, browser, etc.)
- Live memory/workspace access
- True integration with OpenClaw ecosystem

**Cons:**
- **~2-4 second response latency minimum** ⚠️
- Complex real-time audio engineering
- Multiple vendor dependencies
- Higher infrastructure costs
- Interruption handling is hard
- Error handling for each component
- Could feel robotic/slow to users

**Effort:** High (6-10 weeks)
**Latency Impact:** 2-4+ seconds (unacceptable for natural conversation)
**Channel Parity:** Full

---

### Option C: Hybrid Approach (Recommended)

**Concept:** Use OpenAI Realtime for most conversations, but hand off to OpenClaw for tool-heavy requests.

**How it would work:**
```
Normal conversation: OpenAI Realtime (fast)
    │
    │ User says "check my email" or "send a message"
    ▼
OpenAI Realtime: "Let me check that for you, one moment..."
    │
    │ (Brief hold music or silence)
    ▼
Backend: Tool request routed to OpenClaw agent
    │
    ▼
OpenClaw: Execute tools (email, file access, etc.)
    │
    ▼
Result injected back to Realtime as context
    │
    ▼
OpenAI Realtime: "You have 3 new emails. The first one is from..."
```

**Variant C2: Progressive Enhancement**

Start with enhanced context injection (already built!), then add:
1. **Phase 1**: Better pre-call context (done ✅)
2. **Phase 2**: Post-call memory sync (done ✅)
3. **Phase 3**: Mid-call tool escalation (new)
4. **Phase 4**: Real-time context updates (new)

**Pros:**
- Maintains fast conversation flow
- Tools available when needed
- Progressive enhancement path
- Leverages existing work
- Lower risk, iterative approach

**Cons:**
- Still not full Claude
- Handoff moments feel different
- Complex state management
- Some capabilities still limited

**Effort:** Medium-High (4-6 weeks for Phase 3-4)
**Latency Impact:** ~300-500ms normal, ~2-4s during tool calls
**Channel Parity:** High (tools + context, but different model for speech)

---

## Effort & Complexity Estimates

| Option | Dev Time | Infra Complexity | Risk Level | Maintenance |
|--------|----------|------------------|------------|-------------|
| **A: Realtime + Tools** | 2-4 weeks | Low | Medium | Low |
| **B: Full Pipeline** | 6-10 weeks | High | High | High |
| **C: Hybrid** | 4-6 weeks | Medium | Medium | Medium |

### Option B Detailed Breakdown (if pursued)

| Component | Effort | Notes |
|-----------|--------|-------|
| WebSocket audio server | 1-2 weeks | Handle Twilio Media Streams |
| STT integration | 1 week | Deepgram/Google streaming |
| VAD implementation | 1 week | Tricky to get right |
| OpenClaw session routing | 1-2 weeks | Inject audio-originated messages |
| TTS integration | 1 week | ElevenLabs/OpenAI streaming |
| Audio format conversion | 0.5 week | mulaw ↔ PCM ↔ MP3 |
| Interruption handling | 1-2 weeks | Complex state management |
| Testing & refinement | 2+ weeks | Real-world edge cases |

---

## Recommendation

### Short-term (Now): Continue with Current Architecture + Enhanced Context

The current system with session context injection (already built!) provides:
- Context-aware greetings
- Cross-channel continuity
- Transcript sync for memory

This is **80% of the benefit with 20% of the effort**.

### Medium-term (1-2 months): Option C Hybrid with Tool Escalation

Add the ability for OpenAI Realtime to "escalate" to OpenClaw for tool calls:
1. User requests tool action
2. Realtime says "one moment"
3. Backend calls OpenClaw
4. Results returned to Realtime
5. Realtime speaks results

This provides **tool access without sacrificing conversation latency**.

### Long-term (3-6 months): Evaluate Full Pipeline When Conditions Improve

The STT → LLM → TTS pipeline will become more viable as:
- Streaming LLMs get faster (Claude's streaming improves)
- Latency budgets shrink (better infrastructure)
- OpenAI releases better Realtime function calling
- We accumulate more voice call data to understand user expectations

### NOT Recommended: Full pipeline (Option B) today

The **~3-4 second latency** would significantly degrade user experience. Voice conversations are fundamentally different from chat — users expect near-instant responses. A slow voice agent feels broken, not just slow.

---

## Next Steps

If Remi approves this direction:

1. **Immediate**: No changes needed — current system is working well
2. **Phase 3 (2-4 weeks)**: Implement tool escalation in hybrid mode
   - Add "tool intent" detection in Realtime instructions
   - Build escalation endpoint for OpenClaw tool calls
   - Design graceful handoff UX ("one moment...")
3. **Phase 4 (2-4 weeks)**: Real-time context updates
   - Push context changes to active calls
   - Enable "hey, you just got an email" notifications during calls
4. **Ongoing**: Monitor OpenAI Realtime function calling maturity

---

## Appendix: Technical References

### Twilio Media Streams Example
```javascript
// TwiML to start media stream
<Response>
  <Connect>
    <Stream url="wss://your-server.com/media-stream" />
  </Connect>
</Response>

// WebSocket handler
ws.on('message', (data) => {
  const msg = JSON.parse(data);
  if (msg.event === 'media') {
    const audio = Buffer.from(msg.media.payload, 'base64');
    // Send to STT...
  }
});
```

### Deepgram Streaming Example
```javascript
const deepgram = new Deepgram(DEEPGRAM_API_KEY);
const connection = deepgram.transcription.live({
  punctuate: true,
  interim_results: true,
  endpointing: 500, // ms of silence to end utterance
});

connection.on('transcriptReceived', (transcript) => {
  if (transcript.is_final) {
    // Send to OpenClaw...
  }
});
```

### ElevenLabs Streaming TTS
```python
from elevenlabs import stream

audio_stream = elevenlabs.generate(
    text="Hello world",
    voice="Rachel",
    stream=True
)

# Stream to Twilio...
for chunk in audio_stream:
    websocket.send(chunk)
```

---

## Summary Table

| Criteria | Option A | Option B | Option C |
|----------|----------|----------|----------|
| **Latency** | ✅ Fast | ❌ Slow | ✅ Fast (mostly) |
| **Tool Access** | ⚠️ Limited | ✅ Full | ✅ Full |
| **Claude as Brain** | ❌ No | ✅ Yes | ❌ No (except tools) |
| **Memory Access** | ⚠️ Static | ✅ Live | ⚠️ Limited |
| **Effort** | Low-Medium | High | Medium |
| **Risk** | Low | High | Medium |
| **User Experience** | ✅ Good | ⚠️ Degraded | ✅ Good |
| **Recommendation** | Maybe | No | **Yes** |

---

*Document created for Voice Project PM research task. Ready for review.*
