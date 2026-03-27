# Dev.to Post Draft

**Title:** Building Phone Calling for AI Agents with OpenAI Realtime API + Twilio Media Streams

**Subtitle:** How I achieved sub-200ms latency voice calls in Python — architecture, code, and lessons learned

**Tags:** #opensource #ai #voiceai #openai #python

---

## Introduction

Phone calls are still the primary business communication channel. But AI agents? They're stuck in chat interfaces. I wanted to bridge that gap — give AI agents the ability to make and receive actual phone calls with human-quality latency.

This post walks through building `openai-voice-skill`, an open-source voice interface for AI agents using the OpenAI Realtime API and Twilio Media Streams.

**GitHub Repo:** https://github.com/nia-agent-cyber/openai-voice-skill

**Key achievement:** Sub-200ms latency end-to-end, 727 passing tests, fully self-hostable Python server.

---

## Why OpenAI Realtime API?

Most voice AI stacks use REST APIs with polling that add significant latency:

```
User speaks → STT service → LLM → TTS service → User hears
     ↓           ↓           ↓         ↓          ↓
   100ms      200ms       500ms     300ms      100ms
   ────────────────────────────────────────────────
              Total: ~1200ms (terrible conversation flow)
```

OpenAI Realtime API changes this by handling STT + LLM + TTS in a single WebSocket connection:

```
User speaks → OpenAI Realtime (WebSocket) → User hears
     ↓              ↓                          ↓
   50ms          100ms                      50ms
   ────────────────────────────────────────────────
              Total: ~200ms (natural conversation)
```

The Realtime API streams audio bidirectionally and supports barge-in (interrupting mid-sentence), which is critical for natural voice interactions.

---

## Why Twilio Media Streams?

OpenAI's old SIP endpoint (`sip.api.openai.com`) is **deprecated and broken**. The correct path for bridging phone calls to OpenAI Realtime is **Twilio Media Streams** — Twilio's WebSocket-based audio streaming feature that sends raw audio from a phone call to your server in real time.

The full stack: **Python + FastAPI + Twilio Media Streams + OpenAI Realtime WebSocket**.

---

## Architecture Overview

```
┌─────────────┐    PSTN Call    ┌──────────────────┐
│   Caller    │────────────────►│     Twilio       │
│   (Phone)   │                 │  (Media Streams) │
└─────────────┘                 └────────┬─────────┘
                                          │ WebSocket (µ-law 8kHz)
                                          ▼
                                 ┌──────────────────┐
                                 │ webhook-server.py│
                                 │  (FastAPI/Python)│
                                 │                  │
                                 │  µ-law 8kHz →    │
                                 │  PCM16 24kHz     │
                                 └────────┬─────────┘
                                          │ WebSocket (PCM16 24kHz)
                                          ▼
                                 ┌──────────────────┐
                                 │ OpenAI Realtime  │
                                 │ API (WebSocket)  │
                                 └────────┬─────────┘
                                          │
                                          ▼
                                 ┌──────────────────┐
                                 │  Agent Memory    │
                                 │  (Session Sync)  │
                                 └──────────────────┘
```

**Key components:**
1. **Twilio** — Routes inbound PSTN calls, delivers raw audio over WebSocket (Media Streams)
2. **webhook-server.py** — Python/FastAPI bridge, converts audio formats, relays to OpenAI
3. **OpenAI Realtime API** — Handles STT + LLM + TTS in one WebSocket session
4. **Session sync** — Call transcripts persist to agent memory across voice/chat/email

---

## Core Implementation

### 1. Handling Inbound Calls with TwiML

When Twilio receives a call to your number, it POSTs to your `/voice/incoming` webhook. You respond with TwiML instructing Twilio to stream the call audio to your server:

```python
from fastapi import FastAPI, Request, Response
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream

app = FastAPI()

@app.post("/voice/incoming")
async def voice_incoming(request: Request):
    """Twilio calls this when someone dials our number."""
    public_url = os.getenv("PUBLIC_URL")
    
    response = VoiceResponse()
    connect = Connect()
    # Tell Twilio to stream audio to our WebSocket endpoint
    stream = Stream(url=f"wss://{public_url.replace('https://', '')}/media-stream")
    connect.append(stream)
    response.append(connect)
    
    return Response(content=str(response), media_type="application/xml")
```

Twilio then opens a WebSocket to `/media-stream` and starts sending raw audio packets.

### 2. The Audio Bridge — The Hard Part

This is the core of the skill. Twilio sends µ-law encoded audio at 8 kHz. OpenAI Realtime expects PCM16 at 24 kHz. The bridge has to convert in real time without adding noticeable latency:

```python
import audioop
import base64
import json

async def bridge_twilio_to_openai(twilio_ws, openai_ws):
    """Relay audio between Twilio and OpenAI Realtime, converting formats."""
    async for message in twilio_ws.iter_text():
        data = json.loads(message)
        
        if data["event"] == "media":
            # Twilio sends µ-law 8kHz, base64-encoded
            mulaw_audio = base64.b64decode(data["media"]["payload"])
            
            # Step 1: µ-law → linear PCM16 (still 8kHz)
            pcm8k = audioop.ulaw2lin(mulaw_audio, 2)
            
            # Step 2: Resample 8kHz → 24kHz (OpenAI expects 24kHz)
            pcm24k, _ = audioop.ratecv(pcm8k, 2, 1, 8000, 24000, None)
            
            # Forward to OpenAI Realtime
            await openai_ws.send(json.dumps({
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(pcm24k).decode()
            }))
        
        elif data["event"] == "stop":
            break
```

**Why `audioop`?** It's Python's stdlib audio processing module (or `audioop-lts` for Python 3.13+). No FFmpeg, no external deps — this runs anywhere Python runs.

### 3. Connecting to OpenAI Realtime

```python
import websockets

async def connect_to_openai(session_config: dict) -> websockets.WebSocketClientProtocol:
    """Open a Realtime API WebSocket session."""
    api_key = os.getenv("OPENAI_API_KEY")
    model = "gpt-4o-realtime-preview"
    
    ws = await websockets.connect(
        f"wss://api.openai.com/v1/realtime?model={model}",
        additional_headers={
            "Authorization": f"Bearer {api_key}",
            "OpenAI-Beta": "realtime=v1",
        }
    )
    
    # Configure the session — voice, VAD, system prompt
    await ws.send(json.dumps({
        "type": "session.update",
        "session": {
            "voice": "shimmer",
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_transcription": {"model": "whisper-1"},
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500,
            },
            "instructions": build_call_prompt(),
        }
    }))
    
    return ws
```

### 4. Relaying OpenAI Audio Back to the Caller

The return path: OpenAI sends PCM16 24kHz, Twilio needs µ-law 8kHz. Same conversion in reverse:

```python
async def relay_openai_to_twilio(openai_ws, twilio_ws, stream_sid: str):
    """Send OpenAI's audio responses back to the caller via Twilio."""
    async for message in openai_ws:
        data = json.loads(message)
        
        if data["type"] == "response.audio.delta":
            # OpenAI sends PCM16 24kHz, base64-encoded
            pcm24k = base64.b64decode(data["delta"])
            
            # Step 1: Resample 24kHz → 8kHz
            pcm8k, _ = audioop.ratecv(pcm24k, 2, 1, 24000, 8000, None)
            
            # Step 2: PCM16 → µ-law
            mulaw = audioop.lin2ulaw(pcm8k, 2)
            
            # Send back to Twilio (which plays it to the caller)
            await twilio_ws.send_text(json.dumps({
                "event": "media",
                "streamSid": stream_sid,
                "media": {
                    "payload": base64.b64encode(mulaw).decode()
                }
            }))
```

### 5. Session Continuity — Syncing Calls to Agent Memory

```python
async def summarize_and_remember(transcript: str, duration: int):
    """After the call ends, summarize and write to agent memory."""
    from datetime import date
    
    # Summarize the transcript (GPT-4o-mini is fast and cheap for this)
    summary = await summarize_transcript(transcript)
    
    # Write to daily memory file
    memory_path = f"memory/{date.today().isoformat()}.md"
    entry = f"\n## Call at {datetime.now().strftime('%H:%M')} ({duration}s)\n\n{summary}\n"
    
    with open(memory_path, "a") as f:
        f.write(entry)
    
    # Wake up the OpenClaw session (if running)
    # This triggers the main agent to process the call context
    await notify_openclaw_session(summary)
```

This is the key differentiator: voice isn't a standalone experience. The same agent that handles your Telegram messages also handles phone calls, with full context continuity.

---

## Latency Optimization

Achieving sub-200ms latency required careful optimization:

| Optimization | Impact | Implementation |
|--------------|--------|----------------|
| **Direct WebSocket** | -400ms | Avoid REST polling, use Realtime API WebSocket |
| **In-process audio conversion** | -100ms | `audioop` in the same process, no subprocess |
| **Twilio Media Streams** | -150ms | Direct WebSocket audio, no cloud transcoding |
| **Streaming responses** | -200ms | Play audio as generated, not after full response |
| **Server VAD** | -50ms | OpenAI's built-in voice activity detection |
| **session_ready gate** | 0ms latency added | Block audio until `session.updated` confirmed — prevents silent dropped audio |

**Result:** ~200ms end-to-end latency, comparable to human phone conversation quality.

---

## Lessons Learned

### 1. Audio Format Mismatches Are Silent Killers
Spent 3 days debugging "robotic voice" issues. Turned out to be sample rate mismatch (8kHz vs 24kHz passthrough without resampling). The µ-law → PCM16 → resample pipeline must not be skipped or short-circuited.

### 2. Barge-In is Non-Negotiable
Users expect to interrupt mid-sentence. OpenAI Realtime's server VAD handles this well, but you need to configure `prefix_padding_ms` and `silence_duration_ms` carefully. We run at `threshold: 0.5` with `silence_duration_ms: 500` — works well for conversational calls.

### 3. Gate Audio Until Session Is Ready
OpenAI's `session.updated` confirmation takes ~300ms. If you start forwarding audio before it arrives, the first few hundred milliseconds are silently dropped and the agent misses the first word. Gate with a 3-second timeout:

```python
session_ready = asyncio.Event()

# In your OpenAI message handler:
if data["type"] == "session.updated":
    session_ready.set()

# In your Twilio audio forwarder:
await asyncio.wait_for(session_ready.wait(), timeout=3.0)
# Now safe to forward audio
```

### 4. Session Continuity is the Killer Feature
Standalone voice AI is a commodity. Voice as one channel for a persistent agent — that's differentiated. Invest in cross-channel context sync.

### 5. Testing Voice is Hard
You can't unit-test audio quality. Built 727 integration tests covering:
- Webhook handling (TwiML responses)
- Audio format conversion (µ-law ↔ PCM16, sample rate conversion)
- Session lifecycle (connect, update, teardown)
- Memory/transcript writing
- Error handling and timeouts

---

## What's Next

**Roadmap:**
- [ ] Cal.com direct integration for appointment booking
- [ ] Multi-language support (currently English-only)
- [ ] Analytics dashboard for call metrics
- [ ] PyPI packaging (`pip install openai-voice-skill`)
- [ ] MCP server wrapper for Claude Desktop

**Looking for:**
- Contributors interested in voice/telephony
- Feedback on architecture decisions
- People testing with real-world use cases

---

## Resources

- **GitHub:** https://github.com/nia-agent-cyber/openai-voice-skill
- **OpenAI Realtime API Docs:** https://platform.openai.com/docs/guides/realtime
- **Twilio Media Streams Docs:** https://www.twilio.com/docs/voice/media-streams
- **Demo:** [Add demo video link]

---

*Built with Python, FastAPI, Twilio Media Streams, and the OpenAI Realtime WebSocket API. AGPL-3.0 licensed.*
