# Streaming Tool Responses to OpenAI Realtime

**Author:** Nia (subagent)  
**Date:** 2026-02-04  
**Updated:** 2026-02-04 (Remi feedback)
**Status:** Proposal - **Time-to-First-Word Priority**

## Key Insight (Remi Feedback)

> Even with `response.create` overhead per chunk (~200-500ms), **time-to-first-word is the win**.

| Approach | User Experience |
|----------|----------------|
| Current | 30s silence → full response |
| Progressive | **2-5s** → first chunk → continues |

The overhead per chunk is acceptable because:
1. **Users perceive responsiveness from first audio** — 2-5s feels responsive
2. **30s silence feels broken** — users don't know if it's working
3. **Total time may be similar, but UX is dramatically better**

## Problem Statement

Current `ask_openclaw` function in `realtime_tool_handler.py`:
- Waits for full OpenClaw response (can be 2000+ chars)
- User hears nothing until entire response is ready
- Long responses = 30+ seconds of silence before speech begins
- Poor user experience for complex queries

**Goal:** Reduce time-to-first-word by streaming/chunking responses.

## Research Findings

### OpenAI Realtime API: Function Results Are NOT Streamable

After reviewing OpenAI's Realtime API documentation, I found a **critical limitation**:

**Function call outputs are atomic.** The `conversation.item.create` event with `type: "function_call_output"` expects a complete string in the `output` field. There is no:
- `function_call_output.delta` event
- Streaming function result mechanism
- Partial function output support

```javascript
// This is the ONLY way to return function results
{
  "type": "conversation.item.create",
  "item": {
    "type": "function_call_output",
    "call_id": "call_abc123",
    "output": "{ complete result here }"  // Must be complete
  }
}
```

After sending the function result, you trigger `response.create` to have the model speak.

### OpenClaw Agent: No Streaming Mode

Checked `openclaw agent --help` — no streaming output option exists. The CLI:
- Runs to completion
- Returns full response on stdout
- No progressive output mechanism

### What IS Streamable

OpenAI Realtime DOES stream its OWN outputs:
- `response.output_text.delta` — text generation deltas
- `response.output_audio.delta` — audio generation deltas
- `response.output_audio_transcript.delta` — transcript deltas

But these are for MODEL-generated content, not function results.

## Proposed Architecture

Given API limitations, Remi's chunking idea is the right approach — but requires a workaround.

### Option A: Progressive Response Pattern (Recommended)

**Concept:** Send partial results as conversation items, trigger model to speak each chunk.

```
User: "What's my schedule?"
|
v
OpenClaw starts executing (background)
|
v--- Chunk 1 ready (500 chars) --->  conversation.item.create (user message with partial info)
                                      response.create
                                      Model speaks: "Here's what I found so far..."
|
v--- Chunk 2 ready (500 chars) --->  conversation.item.create (user message with more info)  
                                      response.create
                                      Model speaks: "Additionally..."
|
v--- Final chunk ----------------->  conversation.item.create (function_call_output)
                                      response.create
                                      Model speaks: "And finally..."
```

**Implementation:**

```python
async def _execute_function_streaming(self, name: str, arguments: Dict[str, Any], call_id: str):
    """Execute function with progressive response delivery."""
    
    if name != "ask_openclaw":
        # Non-OpenClaw functions: use original atomic approach
        return await self._execute_function(name, arguments)
    
    request = arguments.get("request", "")
    
    # Start OpenClaw in background, capture output progressively
    process = await asyncio.create_subprocess_exec(
        "openclaw", "agent",
        "--message", request,
        "--session-id", "voice-assistant",
        "--local",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    buffer = ""
    chunks_sent = 0
    
    # Read output progressively
    while True:
        chunk = await process.stdout.read(200)  # Read in small increments
        if not chunk:
            break
        
        buffer += chunk.decode()
        
        # Check if we have enough for a smart chunk
        smart_chunk = extract_smart_chunk(buffer, min_chars=400, max_chars=600)
        
        if smart_chunk:
            buffer = buffer[len(smart_chunk):]
            chunks_sent += 1
            
            # Send intermediate result as a context message
            await self._send_intermediate_chunk(smart_chunk, chunks_sent)
    
    # Send any remaining buffer as final chunk (as proper function output)
    if buffer.strip():
        await self._send_function_result(call_id, buffer.strip())
    elif chunks_sent == 0:
        await self._send_function_result(call_id, "Done.")


async def _send_intermediate_chunk(self, chunk: str, chunk_num: int):
    """Send intermediate chunk as assistant context, trigger speech."""
    
    # Add as an assistant message (not function output)
    # This allows the model to speak it immediately
    await self.ws.send(json.dumps({
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "assistant",
            "content": [{
                "type": "output_text",
                "text": f"[Part {chunk_num}] {chunk}"
            }]
        }
    }))
    
    # Trigger model to speak this chunk
    await self.ws.send(json.dumps({
        "type": "response.create",
        "response": {
            "output_modalities": ["audio"],
            "instructions": "Read the previous message naturally, as a continuation of your response."
        }
    }))
```

**Pros:**
- Achieves streaming effect for user
- Uses supported API features
- Works with current OpenAI Realtime

**Cons:**
- Adds conversation items (context grows)
- Multiple `response.create` calls = higher latency per chunk
- May sound disjointed if not handled carefully

### Option B: Out-of-Band Response Injection

Use `conversation: "none"` to create responses that don't pollute the main conversation:

```python
async def _send_streaming_chunk(self, chunk: str):
    """Inject speech without adding to conversation history."""
    
    await self.ws.send(json.dumps({
        "type": "response.create",
        "response": {
            "conversation": "none",  # Don't add to history
            "output_modalities": ["audio"],
            "instructions": f"Say exactly this: {chunk}"
        }
    }))
```

**Pros:**
- Keeps conversation history clean
- Each chunk is independent

**Cons:**
- Still multiple response.create round-trips
- "Say exactly this" may cause unnatural speech
- No continuity between chunks

### Option C: Wait for OpenAI Streaming Function Support

OpenAI may add streaming function results in the future. Signs this could happen:
- They added `conversation.item.added` and `conversation.item.done` events in GA
- Documentation mentions "loading time" for items
- MCP tool listing mentioned as potential streaming use case

**Current status:** Not available as of Feb 2026.

## Smart Chunking Algorithm

For any streaming approach, smart chunking is essential:

```python
import re

def extract_smart_chunk(text: str, min_chars: int = 400, max_chars: int = 600) -> str | None:
    """
    Extract a chunk that ends at a natural boundary.
    Returns None if no suitable chunk is available yet.
    """
    if len(text) < min_chars:
        return None
    
    # Prefer paragraph breaks
    para_match = re.search(r'^.{' + str(min_chars) + r',' + str(max_chars) + r'}(?=\n\n|\n- |\n\d+\.)', text)
    if para_match:
        return para_match.group(0)
    
    # Fall back to sentence boundaries
    # Look for ., !, ? followed by space or newline
    sentence_match = re.search(
        r'^.{' + str(min_chars) + r',' + str(max_chars) + r'}[.!?](?=\s|$)', 
        text
    )
    if sentence_match:
        return sentence_match.group(0)
    
    # Fall back to clause boundaries (comma, semicolon)
    clause_match = re.search(
        r'^.{' + str(min_chars) + r',' + str(max_chars) + r'}[,;](?=\s)', 
        text
    )
    if clause_match:
        return clause_match.group(0)
    
    # Last resort: break at word boundary
    if len(text) >= max_chars:
        word_match = re.search(r'^.{' + str(min_chars) + r',' + str(max_chars) + r'}\b', text)
        if word_match:
            return word_match.group(0)
    
    return None
```

**Chunking priorities:**
1. Paragraph breaks (`\n\n`) — most natural pause point
2. List items (`\n- `, `\n1. `) — logical groupings  
3. Sentence endings (`.`, `!`, `?`) — complete thoughts
4. Clause endings (`,`, `;`) — acceptable pause points
5. Word boundaries (last resort) — never mid-word

## API Limitations & Challenges

### 1. Multiple Response Overhead
Each `response.create` has latency (~200-500ms). Sending 4 chunks = 0.8-2s of overhead.

**Decision (per Remi):** Accept this overhead. Time-to-first-word matters more than total latency.
- 4 chunks × 300ms overhead = ~1.2s extra
- But user hears something at 2-5s instead of 30s
- Net UX win is huge

**Tuning:** Larger chunks = fewer round trips, but longer initial wait. Start with ~500 chars.

### 2. Conversation Context Growth
If using Option A, each chunk adds to conversation. Long sessions = expensive context.

**Mitigation:** Use Option B with `conversation: "none"`, or periodically trim history.

### 3. Interruption Handling
If user interrupts during streaming, need to:
- Cancel in-progress OpenClaw process
- Cancel pending response.create
- Handle partial state

**Mitigation:** Track streaming state, handle `input_audio_buffer.speech_started` events.

### 4. Concurrency
Multiple `response.create` calls may conflict. Only one response can write to default conversation at a time.

**Mitigation:** Use response IDs and metadata to track; queue chunks if needed.

### 5. Voice Continuity
Multiple responses may sound choppy or use different intonation.

**Mitigation:** Use consistent `instructions` prompting for natural continuation.

## Recommendation

**Start with Option A (Progressive Response Pattern)** because:

1. Uses fully supported API features
2. Provides genuine streaming UX improvement
3. Can be refined based on real-world testing
4. Simpler than managing out-of-band responses

**Implementation phases (revised priority: time-to-first-word):**

1. **Phase 1 (MVP):** Progressive response pattern
   - Don't wait for full OpenClaw response
   - As soon as ~400-600 chars accumulate, send chunk
   - User hears first chunk while rest continues
   - Target: **2-5s to first audio**

2. **Phase 2:** Smart boundary detection
   - Sentence/paragraph-aware chunking
   - Natural pause points for better speech flow

3. **Phase 3:** Subprocess streaming
   - Read OpenClaw stdout line-by-line
   - Chunk progressively as data arrives (if CLI streams)

4. **Phase 4:** Handle interruptions gracefully
   - Cancel in-progress process on user speech
   - Clean up partial state

5. **Phase 5:** Native OpenClaw streaming (future)
   - Request `--stream` flag from OpenClaw team
   - Cleanest long-term solution

## Alternative: OpenClaw Streaming Support

Long-term, the cleanest solution is adding streaming output to `openclaw agent`:

```bash
openclaw agent --message "query" --stream
```

This would emit output progressively, allowing the tool handler to:
- Read chunks as they're generated
- Send to Realtime API immediately
- Achieve true streaming without buffering full response

**Current status (2026-02-04):** Checked `openclaw agent --help` — **no `--stream` flag exists**.

**Action item:** File feature request with OpenClaw team. This is Phase 5 in implementation plan.

**Note:** Even without native OpenClaw streaming, the progressive response pattern still works — we just buffer/chunk on the receiving side.

## Files to Modify

1. **`scripts/realtime_tool_handler.py`**
   - Add `_execute_function_streaming()` method
   - Add `_send_intermediate_chunk()` method
   - Add chunking logic

2. **`scripts/openclaw_executor.py`**
   - Add streaming execution mode
   - Yield chunks instead of returning full string

3. **New file: `scripts/smart_chunker.py`**
   - Smart boundary detection
   - Configurable chunk sizes
   - Text cleanup for voice output

## References

- [OpenAI Realtime API Conversations Guide](https://platform.openai.com/docs/guides/realtime-conversations)
- [Realtime Client Events Reference](https://platform.openai.com/docs/api-reference/realtime-client-events)
- [Current implementation: realtime_tool_handler.py](../scripts/realtime_tool_handler.py)
- [Current implementation: openclaw_executor.py](../scripts/openclaw_executor.py)
