#!/usr/bin/env python3
"""
Nia Voice Server — Twilio Media Streams + OpenAI Realtime

Architecture:
  Inbound:  Phone → Twilio → POST /voice/incoming → TwiML <Connect><Stream>
            → wss://api.niavoice.org/media-stream → OpenAI Realtime WS
  Outbound: POST /call → Twilio dials person → on answer → same TwiML flow

Audio bridge:
  Twilio sends:  mulaw 8kHz (base64)
  OpenAI wants:  PCM16 24kHz (base64)
  OpenAI sends:  PCM16 24kHz (base64)
  Twilio wants:  mulaw 8kHz (base64)
  Conversion via audioop (stdlib < 3.13) or audioop-lts (3.13+).

Environment:
  OPENAI_API_KEY        - OpenAI API key
  TWILIO_ACCOUNT_SID    - Twilio account SID
  TWILIO_AUTH_TOKEN     - Twilio auth token
  TWILIO_PHONE_NUMBER   - Your Twilio number (E.164)
  PUBLIC_URL            - Public URL of this server (default: https://api.niavoice.org)
  PORT                  - Server port (default: 8080)
  ALLOW_INBOUND_CALLS   - Allow inbound calls (default: false)
"""

import asyncio
import base64
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# audioop: stdlib in Python < 3.13, audioop-lts on 3.13+
try:
    import audioop
    _AUDIOOP_SOURCE = "stdlib"
except ImportError:
    try:
        import audioop_lts as audioop
        _AUDIOOP_SOURCE = "audioop-lts"
    except ImportError:
        audioop = None
        _AUDIOOP_SOURCE = "UNAVAILABLE"

import httpx
import websockets
import websockets.exceptions
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
import uvicorn
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioException

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ─── Environment ──────────────────────────────────────────────────────────────

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", "8080"))
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://api.niavoice.org").rstrip("/")
ALLOW_INBOUND_CALLS = os.getenv("ALLOW_INBOUND_CALLS", "false").lower() == "true"

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# OpenAI Realtime
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"
OPENAI_VOICE = "shimmer"  # nova deprecated; shimmer is closest match

# Workspace paths for Nia's identity
WORKSPACE_ROOT = Path("/Users/nia/.openclaw/workspace")
SOUL_PATH = WORKSPACE_ROOT / "SOUL.md"
MEMORY_PATH = WORKSPACE_ROOT / "MEMORY.md"

# ─── Twilio client ────────────────────────────────────────────────────────────

twilio_client: Optional[TwilioClient] = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        logger.info("Twilio client initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize Twilio client: {e}")
else:
    logger.info("Twilio credentials not configured — outbound calls disabled")

# ─── Agent config ─────────────────────────────────────────────────────────────

CONFIG_PATH = Path(__file__).parent.parent / "config" / "agent.json"
DEFAULT_CONFIG: dict = {
    "name": "Nia",
    "instructions": "You are Nia, a helpful voice assistant. Be concise and conversational.",
    "voice": OPENAI_VOICE,
    "model": "gpt-4o-realtime-preview",
    "tools": []
}


def load_agent_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception as e:
            logger.warning(f"Failed to load config: {e}, using defaults")
    return DEFAULT_CONFIG


AGENT_CONFIG = load_agent_config()


# Known callers — maps phone number to name
KNOWN_CALLERS = {
    "+250794002033": "Remi",
}


def read_file_safe(path, max_chars=2000) -> str:
    """Read a file safely, returning empty string on error."""
    try:
        p = Path(path)
        if p.exists():
            text = p.read_text().strip()
            return text[:max_chars] if len(text) > max_chars else text
    except Exception:
        pass
    return ""


def build_call_prompt(caller_number: str = "") -> str:
    """
    Build a rich, per-call system prompt with full OpenClaw context.
    Called fresh on each incoming call so context is always current.
    """
    parts: list[str] = []

    # 1. Core identity
    soul = read_file_safe(WORKSPACE_ROOT / "SOUL.md", 2000)
    identity = read_file_safe(WORKSPACE_ROOT / "IDENTITY.md", 800)
    if soul:
        parts.append(f"# Who You Are\n{soul}")
    if identity:
        parts.append(f"# Your Identity Details\n{identity}")

    # 2. Who you're talking to
    caller_name = KNOWN_CALLERS.get(caller_number, "someone")
    parts.append(
        f"# This Call\nYou are on a phone call with {caller_name} "
        f"({caller_number or 'unknown number'}). "
        f"You called them (or they called you). "
        f"Speak naturally and concisely — this is voice, not text. "
        f"Always respond in English by default, unless the caller explicitly and clearly requests another language. "
        f"Keep responses short (1-3 sentences). Don't use bullet points or markdown."
    )

    # 3. Who Remi is
    user_context = read_file_safe(WORKSPACE_ROOT / "USER.md", 1500)
    if user_context:
        parts.append(f"# About {caller_name}\n{user_context}")

    # 4. Long-term memory
    memory = read_file_safe(WORKSPACE_ROOT / "MEMORY.md", 2500)
    if memory:
        parts.append(f"# Your Long-Term Memory\n{memory}")

    # 5. Today's recent context
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - __import__('datetime').timedelta(days=1)).strftime("%Y-%m-%d")
    for date in [today, yesterday]:
        daily = read_file_safe(WORKSPACE_ROOT / "memory" / f"{date}.md", 1000)
        if daily:
            parts.append(f"# Recent Context ({date})\n{daily}")
            break

    # 6. Project pulse (brief status summaries)
    project_statuses = []
    for proj, repo in [("Voice skill", "openai-voice-skill"), ("Trust skill", "agent-trust"), ("Bakkt app", "bakkt-agent-app")]:
        status = read_file_safe(Path.home() / "repos" / repo / "STATUS.md", 400)
        if status:
            # Just first 400 chars — enough for a pulse
            project_statuses.append(f"**{proj}:** {status[:300]}")
    if project_statuses:
        parts.append("# Project Status\n" + "\n\n".join(project_statuses))

    header = (
        "You are Nia — an AI agent on a phone call. "
        "Be warm, direct, and concise. This is voice — no bullet points, no markdown, no long speeches. "
        "You have full context about your projects and your human (Remi). Act like you know him — because you do.\n\n"
    )

    prompt = header + "\n\n---\n\n".join(parts)
    logger.info(f"Built call prompt: {len(prompt)} chars, caller={caller_name} ({caller_number})")
    return prompt


# Static fallback prompt (used before first call)
NIA_SYSTEM_PROMPT = build_call_prompt()
logger.info(f"Identity prompt ready ({len(NIA_SYSTEM_PROMPT)} chars)")

# ─── Active call tracking ─────────────────────────────────────────────────────

active_calls: dict[str, dict] = {}


def mask_phone(phone: str) -> str:
    """Mask phone number for safe logging."""
    if not phone or len(phone) < 7:
        return "****"
    return f"{phone[:3]}****{phone[-4:]}"


def validate_phone(phone: str) -> bool:
    """Validate E.164 format phone number."""
    import re
    return bool(re.match(r'^\+[1-9]\d{6,14}$', phone.strip()))


# ─── Derived URLs ─────────────────────────────────────────────────────────────

# WebSocket URL for Twilio Media Streams
MEDIA_STREAM_WS_URL = (
    PUBLIC_URL
    .replace("https://", "wss://")
    .replace("http://", "ws://")
) + "/media-stream"

# ─── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(title="Nia Voice Server — Twilio Media Streams")


# ─── Pydantic models ──────────────────────────────────────────────────────────

class OutboundCallRequest(BaseModel):
    to: str
    caller_id: Optional[str] = None
    message: Optional[str] = None


class OutboundCallResponse(BaseModel):
    status: str
    call_id: Optional[str] = None
    message: str


# ─── /voice/incoming ─────────────────────────────────────────────────────────

@app.post("/voice/incoming")
async def voice_incoming(request: Request):
    """
    Twilio voice webhook for both inbound and answered outbound calls.
    Returns TwiML that connects the call to our Media Stream WebSocket.
    """
    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{MEDIA_STREAM_WS_URL}"/>
    </Connect>
</Response>'''

    logger.info(f"TwiML /voice/incoming → stream: {MEDIA_STREAM_WS_URL}")
    return Response(content=twiml, media_type="application/xml")


# ─── /media-stream WebSocket ──────────────────────────────────────────────────

@app.websocket("/media-stream")
async def media_stream_ws(websocket: WebSocket):
    """
    Bidirectional audio bridge: Twilio Media Streams ↔ OpenAI Realtime.

    Twilio sends mulaw 8kHz → we convert to PCM16 24kHz → OpenAI
    OpenAI sends PCM16 24kHz → we convert to mulaw 8kHz → Twilio
    """
    await websocket.accept()
    logger.info("Twilio Media Stream WebSocket connected")

    if not audioop:
        logger.error("audioop unavailable — install audioop-lts. Closing stream.")
        await websocket.close(code=1011, reason="audioop not available")
        return

    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set. Closing stream.")
        await websocket.close(code=1011, reason="OpenAI API key not configured")
        return

    # ── Shared mutable state (one dict = no closure capture issues) ──────────
    ctx: dict = {
        "stream_sid": None,
        "call_sid": None,
        "openai_ws": None,
        "started_at": time.time(),
        "transcript": [],
        "ratecv_state_in": None,   # resampling state: Twilio→OpenAI
        "ratecv_state_out": None,  # resampling state: OpenAI→Twilio
        "openai_task": None,
    }

    # ── OpenAI receiver coroutine ─────────────────────────────────────────────

    async def receive_from_openai():
        """Forward OpenAI Realtime audio/events to Twilio."""
        oai_ws = ctx["openai_ws"]
        try:
            async for raw_msg in oai_ws:
                msg = json.loads(raw_msg)
                event_type = msg.get("type", "")

                if event_type == "session.created":
                    logger.info("OpenAI session created")

                elif event_type == "session.updated":
                    logger.info("OpenAI session updated")
                    # Trigger initial greeting for outbound calls
                    call_sid = ctx.get("call_sid")
                    initial_msg = active_calls.get(call_sid, {}).get("initial_message")
                    if initial_msg:
                        await oai_ws.send(json.dumps({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "message",
                                "role": "user",
                                "content": [{"type": "input_text", "text": f"[Start the call by saying this naturally]: {initial_msg}"}]
                            }
                        }))
                        await oai_ws.send(json.dumps({"type": "response.create"}))
                        logger.info(f"Triggered initial greeting for {call_sid}")

                elif event_type == "response.audio.delta":
                    # PCM16 24kHz → mulaw 8kHz → Twilio
                    delta = msg.get("delta", "")
                    ctx.setdefault("audio_chunks_sent", 0)
                    if delta:
                        # Wait up to 2s for stream_sid if not yet set (race condition guard)
                        if ctx.get("stream_sid") is None:
                            waited = 0.0
                            while ctx.get("stream_sid") is None and waited < 2.0:
                                await asyncio.sleep(0.05)
                                waited += 0.05
                            if ctx.get("stream_sid") is None:
                                logger.warning(f"⚠️ stream_sid still None after 2s wait — dropping audio chunk")
                        if ctx.get("stream_sid"):
                            pcm24 = base64.b64decode(delta)
                            # Resample 24kHz → 8kHz
                            pcm8, ctx["ratecv_state_out"] = audioop.ratecv(
                                pcm24, 2, 1, 24000, 8000, ctx["ratecv_state_out"]
                            )
                            # PCM16 → mulaw
                            mulaw = audioop.lin2ulaw(pcm8, 2)
                            payload = base64.b64encode(mulaw).decode()
                            ctx["audio_chunks_sent"] += 1
                            if ctx["audio_chunks_sent"] == 1:
                                logger.info(f"🔊 First audio chunk → Twilio (streamSid={ctx['stream_sid']})")
                            await websocket.send_text(json.dumps({
                                "event": "media",
                                "streamSid": ctx["stream_sid"],
                                "media": {"payload": payload}
                            }))

                elif event_type == "response.audio_transcript.done":
                    text = msg.get("transcript", "").strip()
                    if text:
                        ctx["transcript"].append({
                            "speaker": "assistant",
                            "content": text,
                            "timestamp": datetime.now().isoformat()
                        })
                        logger.info(f"[Nia] {text[:120]}")

                elif event_type == "conversation.item.input_audio_transcription.completed":
                    text = msg.get("transcript", "").strip()
                    if text:
                        ctx["transcript"].append({
                            "speaker": "user",
                            "content": text,
                            "timestamp": datetime.now().isoformat()
                        })
                        logger.info(f"[User] {text[:120]}")

                elif event_type == "response.done":
                    logger.debug("OpenAI response turn complete")

                elif event_type == "error":
                    logger.error(f"OpenAI Realtime error: {msg.get('error', msg)}")

                else:
                    logger.debug(f"OpenAI event: {event_type}")

        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"OpenAI WS closed: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"OpenAI receiver error: {e}", exc_info=True)

    # ── Main Twilio event loop ────────────────────────────────────────────────

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            event = msg.get("event")

            if event == "connected":
                logger.info("Twilio: stream connected")

            elif event == "start":
                start_data = msg.get("start", {})
                ctx["stream_sid"] = start_data.get("streamSid")
                ctx["call_sid"] = start_data.get("callSid")
                # Resolve caller number: for outbound calls it's stored in active_calls
                ctx["caller_number"] = active_calls.get(ctx["call_sid"], {}).get("to", "")
                caller_name = KNOWN_CALLERS.get(ctx["caller_number"], ctx["caller_number"] or "unknown")
                logger.info(
                    f"Stream started — streamSid={ctx['stream_sid']}, "
                    f"callSid={ctx['call_sid']}, caller={caller_name}"
                )

                # Track the call
                if ctx["call_sid"]:
                    active_calls[ctx["call_sid"]] = {
                        "type": "inbound",
                        "stream_sid": ctx["stream_sid"],
                        "started_at": ctx["started_at"],
                        "status": "active"
                    }

                # ── Connect to OpenAI Realtime ──────────────────────────────
                try:
                    logger.info(f"Connecting to OpenAI Realtime: {OPENAI_REALTIME_URL}")
                    oai_ws = await websockets.connect(
                        OPENAI_REALTIME_URL,
                        additional_headers={
                            "Authorization": f"Bearer {OPENAI_API_KEY}",
                            "OpenAI-Beta": "realtime=v1"
                        }
                    )
                    ctx["openai_ws"] = oai_ws
                    logger.info("OpenAI Realtime WS connected")

                    # ── Send session.update with fresh per-call context ─────
                    tools = AGENT_CONFIG.get("tools", [])
                    call_prompt = build_call_prompt(ctx.get("caller_number", ""))
                    session_config = {
                        "type": "session.update",
                        "session": {
                            "modalities": ["text", "audio"],
                            "instructions": call_prompt,
                            "voice": OPENAI_VOICE,
                            "input_audio_format": "pcm16",
                            "output_audio_format": "pcm16",
                            "input_audio_transcription": {
                                "model": "whisper-1"
                            },
                            "turn_detection": {
                                "type": "semantic_vad",
                                "eagerness": "low",
                                "prefix_padding_ms": 300,
                                "silence_duration_ms": 800
                            },
                            "input_audio_noise_suppression": {
                                "type": "near_field"
                            },
                            "tools": tools,
                            "tool_choice": "auto" if tools else "none"
                        }
                    }
                    await oai_ws.send(json.dumps(session_config))
                    logger.info(
                        f"session.update sent (voice={OPENAI_VOICE}, "
                        f"tools={len(tools)}, prompt={len(call_prompt)}c, "
                        f"caller={KNOWN_CALLERS.get(ctx.get('caller_number',''), 'unknown')})"
                    )

                    # ── Start OpenAI receiver task ──────────────────────────
                    ctx["openai_task"] = asyncio.create_task(receive_from_openai())

                except Exception as e:
                    logger.error(f"Failed to connect to OpenAI Realtime: {e}", exc_info=True)

            elif event == "media":
                # Twilio mulaw 8kHz → PCM16 24kHz → OpenAI
                oai_ws = ctx["openai_ws"]
                if oai_ws:
                    mulaw_b64 = msg.get("media", {}).get("payload", "")
                    if mulaw_b64:
                        mulaw_bytes = base64.b64decode(mulaw_b64)
                        # mulaw → linear PCM 8kHz
                        linear8 = audioop.ulaw2lin(mulaw_bytes, 2)
                        # resample 8kHz → 24kHz
                        linear24, ctx["ratecv_state_in"] = audioop.ratecv(
                            linear8, 2, 1, 8000, 24000, ctx["ratecv_state_in"]
                        )
                        # Forward to OpenAI
                        await oai_ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": base64.b64encode(linear24).decode()
                        }))

            elif event == "stop":
                logger.info(f"Stream stopped: {ctx['stream_sid']}")
                break

            else:
                logger.debug(f"Twilio event: {event}")

    except WebSocketDisconnect:
        logger.info("Twilio WebSocket disconnected")
    except Exception as e:
        logger.error(f"Media stream error: {e}", exc_info=True)

    finally:
        # ── Cleanup ───────────────────────────────────────────────────────────

        # Cancel OpenAI receiver task
        task = ctx.get("openai_task")
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        # Close OpenAI WebSocket
        oai_ws = ctx.get("openai_ws")
        if oai_ws:
            try:
                await oai_ws.close()
                logger.info("OpenAI WS closed")
            except Exception:
                pass

        # Save transcript
        call_sid = ctx["call_sid"]
        transcript = ctx["transcript"]
        if call_sid and transcript:
            _save_transcript(call_sid, transcript)

        # Update active calls
        if call_sid and call_sid in active_calls:
            duration = time.time() - ctx["started_at"]
            active_calls[call_sid]["status"] = "completed"
            active_calls[call_sid]["duration"] = round(duration, 1)
            logger.info(
                f"Call {call_sid} done — "
                f"duration={duration:.1f}s, turns={len(transcript)}"
            )

        logger.info("Media stream WebSocket closed and cleaned up")


def _save_transcript(call_sid: str, transcript: list[dict]) -> None:
    """Persist call transcript to workspace/memory/call-transcripts/."""
    try:
        transcripts_dir = WORKSPACE_ROOT / "memory" / "call-transcripts"
        transcripts_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = transcripts_dir / f"{ts}_{call_sid}.json"

        data = {
            "call_sid": call_sid,
            "recorded_at": datetime.now().isoformat(),
            "turns": len(transcript),
            "transcript": transcript
        }
        path.write_text(json.dumps(data, indent=2))
        logger.info(f"Transcript saved → {path}")

    except Exception as e:
        logger.error(f"Failed to save transcript for {call_sid}: {e}")


# ─── Outbound calls ───────────────────────────────────────────────────────────

@app.post("/call", response_model=OutboundCallResponse)
async def initiate_outbound_call(
    request: OutboundCallRequest,
    background_tasks: BackgroundTasks
):
    """
    Initiate an outbound call via Twilio.
    When the callee answers, Twilio hits /voice/incoming which spins up
    the Media Stream bridge to OpenAI Realtime.
    """
    if not twilio_client:
        raise HTTPException(
            status_code=503,
            detail="Outbound calling not configured — missing Twilio credentials"
        )

    if not request.to or not isinstance(request.to, str):
        raise HTTPException(status_code=400, detail="Phone number is required")

    phone = (
        request.to.strip()
        .replace(' ', '')
        .replace('-', '')
        .replace('(', '')
        .replace(')', '')
    )

    if not validate_phone(phone):
        raise HTTPException(
            status_code=400,
            detail="Invalid phone number — use E.164 format (e.g. +1234567890)"
        )

    if request.caller_id and not validate_phone(request.caller_id.strip()):
        raise HTTPException(
            status_code=400,
            detail="Invalid caller_id — use E.164 format"
        )

    from_number = request.caller_id or TWILIO_PHONE_NUMBER
    if not from_number:
        raise HTTPException(
            status_code=500,
            detail="No caller ID — set TWILIO_PHONE_NUMBER or provide caller_id"
        )

    # Point Twilio to /voice/incoming when call is answered
    twiml_url = f"{PUBLIC_URL}/voice/incoming"
    logger.info(
        f"Initiating outbound: {mask_phone(phone)} from {mask_phone(from_number)} "
        f"(TwiML: {twiml_url})"
    )

    try:
        call = twilio_client.calls.create(
            to=phone,
            from_=from_number,
            url=twiml_url,
            timeout=30,
        )

        active_calls[call.sid] = {
            "type": "outbound",
            "to": phone,
            "from": from_number,
            "started_at": time.time(),
            "twilio_call_sid": call.sid,
            "status": "initiated",
            "initial_message": request.message or None
        }

        logger.info(f"Outbound call created: {call.sid} → {mask_phone(phone)}")

        return OutboundCallResponse(
            status="initiated",
            call_id=call.sid,
            message=f"Call initiated to {phone}"
        )

    except TwilioException as e:
        logger.error(f"Twilio error: {e}")
        raise HTTPException(status_code=400, detail=f"Call failed: {str(e)}")
    except Exception as e:
        logger.error(f"Error initiating outbound call: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/call/{call_id}")
async def cancel_outbound_call(call_id: str):
    """Cancel an active outbound call."""
    if not twilio_client:
        raise HTTPException(status_code=503, detail="Twilio not configured")

    if call_id not in active_calls:
        raise HTTPException(status_code=404, detail="Call not found")

    call_data = active_calls[call_id]
    if call_data.get("type") != "outbound":
        raise HTTPException(status_code=400, detail="Can only cancel outbound calls")

    try:
        twilio_client.calls(call_id).update(status='canceled')
        del active_calls[call_id]
        logger.info(f"Call {call_id} canceled")
        return {"status": "canceled", "call_id": call_id}
    except TwilioException as e:
        raise HTTPException(status_code=400, detail=f"Failed to cancel: {str(e)}")


# ─── Standard endpoints ───────────────────────────────────────────────────────

@app.get("/calls")
async def list_calls():
    """List active calls."""
    return {
        "active_calls": len(active_calls),
        "calls": [
            {
                "call_id": cid,
                "type": d.get("type", "unknown"),
                "status": d.get("status", "unknown"),
                "duration": round(time.time() - d.get("started_at", time.time()), 1),
                "to": d.get("to"),
                "from": d.get("from"),
            }
            for cid, d in active_calls.items()
        ]
    }


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "ok",
        "architecture": "twilio-media-streams + openai-realtime",
        "agent": AGENT_CONFIG["name"],
        "voice": OPENAI_VOICE,
        "active_calls": len(active_calls),
        "audioop": _AUDIOOP_SOURCE,
        "twilio_configured": twilio_client is not None,
        "openai_configured": bool(OPENAI_API_KEY),
        "stream_url": MEDIA_STREAM_WS_URL,
        "inbound_calls_enabled": ALLOW_INBOUND_CALLS,
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Nia Voice Server",
        "architecture": "Twilio Media Streams + OpenAI Realtime",
        "agent": AGENT_CONFIG["name"],
        "voice": OPENAI_VOICE,
        "stream_url": MEDIA_STREAM_WS_URL,
        "endpoints": {
            "voice_incoming":  "POST /voice/incoming — Twilio voice webhook (TwiML)",
            "media_stream":    f"WS   {MEDIA_STREAM_WS_URL} — audio bridge",
            "outbound_call":   "POST /call — initiate outbound call",
            "cancel_call":     "DELETE /call/{id} — cancel outbound call",
            "calls":           "GET  /calls — list active calls",
            "health":          "GET  /health — health check",
        }
    }


# ─── Startup hook ─────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    if not OPENAI_API_KEY:
        logger.warning("⚠️  OPENAI_API_KEY not set — calls will fail")
    if audioop is None:
        logger.error("❌  audioop not available — run: pip install audioop-lts")
    else:
        logger.info(f"✅  audioop loaded from: {_AUDIOOP_SOURCE}")

    # Update Twilio phone number webhook
    asyncio.create_task(_update_twilio_webhook())

    logger.info(f"🎙️  Nia Voice Server ready (Twilio Media Streams)")
    logger.info(f"   Voice:      {OPENAI_VOICE}")
    logger.info(f"   Stream URL: {MEDIA_STREAM_WS_URL}")
    logger.info(f"   Port:       {PORT}")
    logger.info(f"   Inbound:    {'enabled' if ALLOW_INBOUND_CALLS else 'disabled'}")


async def _update_twilio_webhook():
    """Update the Twilio phone number webhook to /voice/incoming."""
    if not twilio_client or not TWILIO_PHONE_NUMBER:
        logger.info("Skipping Twilio webhook update (no client or phone number)")
        return

    try:
        numbers = twilio_client.incoming_phone_numbers.list(
            phone_number=TWILIO_PHONE_NUMBER,
            limit=1
        )
        if not numbers:
            logger.warning(f"Phone {TWILIO_PHONE_NUMBER} not found in Twilio account")
            return

        voice_url = f"{PUBLIC_URL}/voice/incoming"
        twilio_client.incoming_phone_numbers(numbers[0].sid).update(
            voice_url=voice_url,
            voice_method="POST"
        )
        logger.info(f"✅  Twilio webhook updated: {TWILIO_PHONE_NUMBER} → {voice_url}")

    except Exception as e:
        logger.warning(f"Could not update Twilio webhook: {e}")


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("🎙️  Starting Nia Voice Server (Twilio Media Streams + OpenAI Realtime)")
    logger.info(f"   Voice:      {OPENAI_VOICE}")
    logger.info(f"   Stream URL: {MEDIA_STREAM_WS_URL}")
    logger.info(f"   Port:       {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
