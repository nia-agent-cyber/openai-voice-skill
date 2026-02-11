# Competitive Pipeline Analysis: VisionClaw

**Date:** 2026-02-11
**Analyst:** Voice PM
**Subject:** VisionClaw (github.com/sseanliu/VisionClaw) voice pipeline comparison

---

## Executive Summary

VisionClaw is an iOS app for Meta Ray-Ban smart glasses that provides real-time voice + vision AI using Gemini Live API with optional OpenClaw integration. While targeting a different modality (wearables vs phone calls), their approach reveals several techniques we could adopt and confirms areas where we're ahead.

**Key Finding:** VisionClaw and our skill are **complementary, not competitive**. They solve wearables; we solve telephony. But their architectural patterns offer learnings.

---

## VisionClaw Architecture

### Overview

```
Smart Glasses / iPhone Camera
       │
       ├── Video: JPEG (~1fps, 50% quality)
       ├── Audio: PCM Int16, 16kHz mono
       │
       ▼
iOS App (GeminiLiveService + AudioManager)
       │
       ├── WebSocket → Gemini Live API
       │      ├── Audio response (PCM 24kHz)
       │      └── Tool calls (execute)
       │
       └── HTTP → OpenClaw Gateway
              └── /v1/chat/completions (session continuity)
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| `GeminiLiveService.swift` | WebSocket | Gemini Live API client, message routing |
| `AudioManager.swift` | Audio | Mic capture, playback, resampling |
| `GeminiSessionViewModel.swift` | Session | Lifecycle management, state coordination |
| `OpenClawBridge.swift` | Integration | OpenClaw HTTP client with conversation history |
| `ToolCallRouter.swift` | Routing | Async tool execution with cancellation |

---

## Our Architecture (openai-voice-skill)

```
Phone Call (PSTN)
       │
       ▼
Twilio SIP → Webhook Server (8080)
                    │
                    ├── WebSocket → OpenAI Realtime API
                    │
                    └── HTTP → Session Bridge (8082)
                               └── OpenClaw session sync

+ Inbound Handler (8084) - Authorization, caller history
+ Metrics Server (8083) - Call observability
```

---

## Detailed Comparison

### 1. Voice AI Provider

| Aspect | VisionClaw | Our Skill |
|--------|------------|-----------|
| **Provider** | Gemini Live API | OpenAI Realtime API |
| **Protocol** | Native WebSocket | Native WebSocket |
| **Audio In** | 16kHz PCM Int16 | 24kHz PCM (Twilio) |
| **Audio Out** | 24kHz PCM | 24kHz PCM |
| **Latency Tracking** | ✅ Built-in (speech end → first audio) | ❌ Not implemented |

**Insight:** Both use native WebSocket audio (not STT→LLM→TTS). Gemini's auto VAD with configurable sensitivity is interesting.

### 2. Audio Handling

| Aspect | VisionClaw | Our Skill |
|--------|------------|-----------|
| **Capture** | AVAudioEngine with resampling | Twilio media stream |
| **Chunking** | ~100ms chunks (3200 bytes) | Twilio-determined |
| **Echo Cancellation** | iOS `.voiceChat` mode | Twilio handles |
| **Interruption** | Stop playback on `interrupted` event | Twilio barge-in |
| **Mic Muting** | Client-side during AI speech (iPhone mode) | Not applicable |

**Insight:** VisionClaw handles edge cases we don't face (co-located mic/speaker echo). Their 100ms chunking strategy is explicit and tuned.

### 3. Session Management

| Aspect | VisionClaw | Our Skill |
|--------|------------|-----------|
| **Session ID** | `agent:main:glass:<timestamp>` | Session bridge generates |
| **Conversation History** | Client-side array (max 10 turns) | OpenClaw manages |
| **Continuity** | `x-openclaw-session-key` header | Session bridge sync |
| **State Observation** | 100ms polling loop | Event-driven |

**Insight:** VisionClaw maintains conversation history client-side for context window management. Our session bridge handles this, but we could add metrics on conversation depth.

### 4. Tool Calling

| Aspect | VisionClaw | Our Skill |
|--------|------------|-----------|
| **Strategy** | Single `execute` tool → OpenClaw | Direct tool calls |
| **Cancellation** | ✅ In-flight task cancellation | ❌ Not implemented |
| **Status Tracking** | `ToolCallStatus` enum (idle/executing/completed/failed/cancelled) | Metrics server logs |
| **Acknowledgment** | Verbal ack before tool call (system prompt) | Not enforced |

**Insight:** VisionClaw's tool cancellation pattern is smart—if user interrupts, cancel pending tool work. Their verbal acknowledgment pattern ("Sure, let me add that") before tool calls improves UX.

### 5. Configuration & Secrets

| Aspect | VisionClaw | Our Skill |
|--------|------------|-----------|
| **Secrets Management** | `Secrets.swift` (gitignored) | `.env` file |
| **Config Structure** | `GeminiConfig` static enum | Environment variables |
| **Health Check** | Ping gateway before session | Not explicit |

---

## What They Do Differently (Techniques Worth Adopting)

### 1. Latency Tracking ⭐ HIGH VALUE

```swift
// VisionClaw tracks time from user speech end to first AI audio
private var lastUserSpeechEnd: Date?
private var responseLatencyLogged = false

// On transcription received:
lastUserSpeechEnd = Date()

// On first audio response:
let latency = Date().timeIntervalSince(speechEnd)
NSLog("[Latency] %.0fms (user speech end -> first audio)", latency * 1000)
```

**Recommendation:** Add latency tracking to our metrics server. This is the key metric for voice UX.

### 2. Tool Call Cancellation ⭐ MEDIUM VALUE

```swift
func cancelToolCalls(ids: [String]) {
  for id in ids {
    if let task = inFlightTasks[id] {
      task.cancel()
      inFlightTasks.removeValue(forKey: id)
    }
  }
}
```

**Recommendation:** If user interrupts during a long tool execution, we should cancel the pending work rather than let it complete and speak stale results.

### 3. Verbal Acknowledgment Pattern ⭐ HIGH VALUE

From their system prompt:
> IMPORTANT: Before calling execute, ALWAYS speak a brief acknowledgment first. For example:
> - "Sure, let me add that to your shopping list." then call execute.
> - "Got it, searching for that now." then call execute.
> Never call execute silently -- the user needs verbal confirmation.

**Recommendation:** Add this pattern to our voice system prompt. Users need to know something is happening, especially for slow tool calls.

### 4. Gateway Health Check ⭐ LOW VALUE

They ping the gateway before starting a session:
```swift
func checkConnection() async {
  let (_, response) = try await pingSession.data(for: request)
  if let http = response as? HTTPURLResponse, (200...499).contains(http.statusCode) {
    connectionState = .connected
  }
}
```

**Recommendation:** Already implicit in our architecture (Twilio connects to working server or fails), but could add explicit health endpoint for observability.

---

## Where We're Ahead

### 1. Production Infrastructure ✅

| Our Advantage | VisionClaw Lacks |
|---------------|------------------|
| Inbound call handling with authorization | Client-initiated only |
| Voicemail + after-hours messaging | None |
| Metrics/observability server | Basic logging only |
| Caller history context | Manual session key |
| Multi-tier architecture | Single client app |

### 2. PSTN Integration ✅

VisionClaw requires internet + glasses + phone. We work with any phone.

### 3. Enterprise Features ✅

| Feature | Us | Them |
|---------|-----|------|
| Allowlist policies | ✅ | ❌ |
| Call recording/transcripts | ✅ | Local only |
| Session continuity (survive disconnects) | ✅ | ❌ |
| Missed call → callback flow | ✅ | ❌ |

### 4. Agent-Native Integration ✅

Our session bridge syncs transcripts bidirectionally with OpenClaw sessions. VisionClaw only sends tasks out, doesn't receive context back.

---

## What We Could Learn/Adopt

| Priority | Improvement | Effort | Impact |
|----------|-------------|--------|--------|
| **P1** | Add latency tracking (speech end → audio start) | Low | High |
| **P1** | Verbal ack pattern in system prompt | Low | High |
| **P2** | Tool call cancellation on barge-in | Medium | Medium |
| **P3** | Connection state machine (disconnected/connecting/ready/error) | Low | Low |
| **P3** | Explicit audio chunk sizing documentation | Low | Low |

---

## Specific Improvements Based on Their Techniques

### Improvement 1: Latency Metrics (P1)

**File:** `scripts/metrics_server.py`

Add tracking for:
- `speech_end_to_first_audio_ms` — Core UX metric
- `tool_call_duration_ms` — Time in tool execution
- `session_duration_ms` — Total call length

### Improvement 2: System Prompt Enhancement (P1)

**File:** `scripts/webhook-server.py` or system prompt config

Add to voice system prompt:
```
Before executing any tool or action, ALWAYS speak a brief acknowledgment first.
Examples:
- "Let me look that up for you." (then search)
- "I'll send that message now." (then send)
- "Adding that to your list." (then add)

This keeps the user informed that their request was heard and is being processed.
```

### Improvement 3: Barge-In Tool Cancellation (P2)

**Concept:** When OpenAI Realtime sends an interruption event, cancel any pending tool calls.

This prevents:
- User: "What's the weather?"
- AI: (starts weather lookup)
- User: "Never mind, call John instead"
- AI: (completes weather, then speaks stale result)

---

## Strategic Implications

### Market Positioning

VisionClaw targets **wearables enthusiasts + developers**. We target **SMBs + agents needing phone access**.

**No direct competition.** In fact, VisionClaw users who need phone calling would need us.

### Integration Opportunity

VisionClaw uses OpenClaw gateway. We ARE an OpenClaw skill. A user could:
1. Wear smart glasses (VisionClaw + Gemini)
2. Say "Call John and tell him I'll be late"
3. VisionClaw → OpenClaw → Our voice skill → PSTN call

**We're complementary infrastructure.**

### Technical Validation

VisionClaw's success with Gemini Live validates our bet on native voice WebSocket APIs (OpenAI Realtime). The industry is moving away from STT→LLM→TTS pipelines.

---

## Action Items

| # | Action | Owner | Status |
|---|--------|-------|--------|
| 1 | Add latency tracking to metrics_server.py | Coder | TODO |
| 2 | Update voice system prompt with verbal ack pattern | PM | TODO |
| 3 | Research OpenAI Realtime interruption events for tool cancellation | Coder | TODO |
| 4 | Document our audio pipeline specs (sample rate, chunking) | PM | TODO |

---

## Conclusion

VisionClaw is well-engineered for its wearables use case. Key learnings:

1. **Latency tracking is essential** — They measure it; we should too
2. **Verbal acknowledgments improve UX** — Easy win via system prompt
3. **Tool cancellation matters** — Especially for voice where interruption is natural
4. **We're ahead on production features** — Authorization, voicemail, metrics, PSTN

**Recommendation:** Adopt P1 improvements (latency tracking, verbal acks) in next sprint. These are low-effort, high-impact changes validated by VisionClaw's implementation.

---

*Analysis complete. Committed to docs/COMPETITIVE_ANALYSIS_VISIONCLAW.md*
