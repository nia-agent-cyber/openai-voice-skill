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
import math
import os
import struct
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

# ─── OpenClaw gateway ─────────────────────────────────────────────────────────

OPENCLAW_GATEWAY_URL = "http://localhost:18789"


def _read_openclaw_token() -> str:
    """Read gateway auth token from ~/.openclaw/openclaw.json"""
    try:
        p = Path.home() / ".openclaw" / "openclaw.json"
        if p.exists():
            data = json.loads(p.read_text())
            return data.get("gateway", {}).get("auth", {}).get("token", "")
    except Exception:
        pass
    return ""


OPENCLAW_TOKEN = os.getenv("OPENCLAW_TOKEN") or _read_openclaw_token()

# ─── Tier 1 Voice Tools ───────────────────────────────────────────────────────

# Tool definitions in OpenAI Realtime format
VOICE_TOOLS = [
    {
        "type": "function",
        "name": "memory_search",
        "description": (
            "Search Nia's memory files for information about a specific topic, person, or event. "
            "Use this when Remi asks 'do you remember when...' or 'what do you know about...'. "
            "Returns relevant excerpts from MEMORY.md and recent daily notes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for (e.g. 'Bakkt project', 'last week', 'Remi's goal')"
                }
            },
            "required": ["query"]
        }
    },
    {
        "type": "function",
        "name": "read_file",
        "description": (
            "Read the contents of a file in Nia's workspace or repos. "
            "Use this to read MEMORY.md, SOUL.md, project files, etc. "
            "Path should be absolute or relative to workspace root."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, e.g. 'MEMORY.md' or '/Users/nia/.openclaw/workspace/MEMORY.md'"
                }
            },
            "required": ["path"]
        }
    },
    {
        "type": "function",
        "name": "get_project_status",
        "description": (
            "Get the current status of a project by reading its STATUS.md file. "
            "Use this when Remi asks 'what's the status of [project]?' or 'how is [project] going?'. "
            "Known projects: voice (openai-voice-skill), trust (agent-trust), bakkt (bakkt-agent-app)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name, e.g. 'voice', 'bakkt', 'trust', or repo name like 'openai-voice-skill'"
                }
            },
            "required": ["project"]
        }
    },
    {
        "type": "function",
        "name": "memory_get",
        "description": (
            "Get memory content for a specific date or topic from Nia's daily memory files. "
            "Use this for 'what happened on [date]?' or 'what did we discuss last Tuesday?'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format, e.g. '2026-03-24'. Leave empty to get today."
                },
                "topic": {
                    "type": "string",
                    "description": "Topic keyword to search for within the date's memory. Optional."
                }
            },
            "required": []
        }
    },
    {
        "type": "function",
        "name": "cron_create",
        "description": (
            "Create a reminder or scheduled task. "
            "Use this when Remi says 'remind me at 3pm', 'set a reminder for tomorrow morning', etc. "
            "Sends a message to Remi at the specified time via Telegram."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "What to remind Remi about, e.g. 'Check the Bakkt deployment'"
                },
                "when": {
                    "type": "string",
                    "description": (
                        "When to send the reminder. Use natural language: "
                        "'in 30 minutes', 'at 3pm', 'tomorrow at 9am', '2026-03-24 15:00'"
                    )
                }
            },
            "required": ["message", "when"]
        }
    },
    {
        "type": "function",
        "name": "message_send",
        "description": (
            "Send a Telegram message to Remi. "
            "Use this when Remi asks you to 'send me that link', 'message me that', "
            "'drop that in Telegram', etc. Sends immediately."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The message text to send to Remi via Telegram"
                }
            },
            "required": ["text"]
        }
    },
    {
        "type": "function",
        "name": "sessions_send",
        "description": (
            "Send a note or message to Nia's main session (the OpenClaw agent). "
            "Use this when Remi says 'note that for later', 'remind yourself about this', "
            "'add that to your memory', etc. The note is injected into the main session."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": "The note or message to inject into the main session"
                }
            },
            "required": ["note"]
        }
    }
]

# ─── Tool handlers ────────────────────────────────────────────────────────────

async def tool_memory_search(query: str) -> str:
    """Search Nia's memory files for relevant content."""
    from datetime import timedelta
    query_lower = query.lower()
    results = []

    # Search MEMORY.md
    memory = read_file_safe(WORKSPACE_ROOT / "MEMORY.md", 8000)
    if memory:
        lines = memory.split('\n')
        for i, line in enumerate(lines):
            if query_lower in line.lower() and line.strip():
                context_start = max(0, i - 1)
                context_end = min(len(lines), i + 3)
                snippet = '\n'.join(lines[context_start:context_end]).strip()
                if snippet:
                    results.append(snippet)

    # Search last 7 days of daily memory
    for days_ago in range(7):
        date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        daily = read_file_safe(WORKSPACE_ROOT / "memory" / f"{date}.md", 3000)
        if daily:
            lines = daily.split('\n')
            for i, line in enumerate(lines):
                if query_lower in line.lower() and line.strip():
                    context_start = max(0, i - 1)
                    context_end = min(len(lines), i + 3)
                    snippet = '\n'.join(lines[context_start:context_end]).strip()
                    if snippet:
                        results.append(f"[{date}] {snippet}")

    if not results:
        return f"No memory found matching '{query}'."

    # Return up to 3 results, truncated to 1000 chars total
    combined = "\n---\n".join(results[:3])
    return combined[:1000]


async def tool_read_file(path: str) -> str:
    """Read a file from the workspace or repos (restricted to safe paths)."""
    allowed_prefixes = [
        str(WORKSPACE_ROOT),
        str(Path.home() / "repos"),
    ]

    p = Path(path)
    if not p.is_absolute():
        p = WORKSPACE_ROOT / path

    resolved = str(p.resolve())
    if not any(resolved.startswith(prefix) for prefix in allowed_prefixes):
        return f"Access denied: '{path}' is outside allowed directories."

    content = read_file_safe(p, 3000)
    if not content:
        return f"File not found or empty: {path}"
    return content


async def tool_get_project_status(project: str) -> str:
    """Read a project's STATUS.md."""
    project_map = {
        "voice": "openai-voice-skill",
        "voice skill": "openai-voice-skill",
        "openai-voice-skill": "openai-voice-skill",
        "trust": "agent-trust",
        "trust skill": "agent-trust",
        "agent-trust": "agent-trust",
        "bakkt": "bakkt-agent-app",
        "bakkt app": "bakkt-agent-app",
        "bakkt-agent-app": "bakkt-agent-app",
    }

    repo_name = project_map.get(project.lower().strip(), project.lower().replace(" ", "-"))
    status_path = Path.home() / "repos" / repo_name / "STATUS.md"
    content = read_file_safe(status_path, 2000)

    if not content:
        # Try exact name
        alt_path = Path.home() / "repos" / project / "STATUS.md"
        content = read_file_safe(alt_path, 2000)

    if not content:
        return f"No STATUS.md found for project '{project}'."
    return content


async def tool_memory_get(date: str = "", topic: str = "") -> str:
    """Get memory by date or topic."""
    if date:
        daily = read_file_safe(WORKSPACE_ROOT / "memory" / f"{date}.md", 3000)
        if daily:
            return daily
        return f"No memory found for {date}."

    if topic:
        return await tool_memory_search(topic)

    # Default: today
    today = datetime.now().strftime("%Y-%m-%d")
    content = read_file_safe(WORKSPACE_ROOT / "memory" / f"{today}.md", 2000)
    if content:
        return f"[{today}]\n{content}"
    return "No memory notes for today yet."


def _parse_when_to_at(when: str) -> str:
    """
    Convert natural language time to openclaw cron --at format.
    Supports: 'in N minutes', 'in N hours', 'at HH:MM', 'at Xpm', '+Nm', ISO strings.
    Returns the --at value string.
    """
    import re
    when_lower = when.strip().lower()

    # Already in +duration format
    if re.match(r'^\+\d+[mhsd]', when_lower):
        return when

    # "in N minutes" / "in N hours"
    m = re.match(r'in\s+(\d+)\s*(minute|minutes|min|m)', when_lower)
    if m:
        return f"+{m.group(1)}m"

    m = re.match(r'in\s+(\d+)\s*(hour|hours|hr|h)', when_lower)
    if m:
        return f"+{m.group(1)}h"

    # "at HH:MM" (24h)
    m = re.match(r'at\s+(\d{1,2}):(\d{2})', when_lower)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        now = datetime.now()
        target = now.replace(hour=h, minute=mn, second=0, microsecond=0)
        if target <= now:
            from datetime import timedelta
            target += timedelta(days=1)
        return target.strftime("%Y-%m-%dT%H:%M:%S")

    # "at Xpm" / "at Xam"
    m = re.match(r'at\s+(\d{1,2})\s*(am|pm)', when_lower)
    if m:
        h = int(m.group(1))
        if m.group(2) == 'pm' and h != 12:
            h += 12
        elif m.group(2) == 'am' and h == 12:
            h = 0
        now = datetime.now()
        target = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if target <= now:
            from datetime import timedelta
            target += timedelta(days=1)
        return target.strftime("%Y-%m-%dT%H:%M:%S")

    # ISO or other — pass through as-is
    return when


async def tool_cron_create(message: str, when: str) -> str:
    """Create a cron reminder via the OpenClaw cron CLI."""
    # Parse natural language time to --at format
    at_value = _parse_when_to_at(when)
    message_safe = message[:200]

    cmd = [
        "openclaw", "cron", "add",
        "--at", at_value,
        "--message", f"Reminder for Remi: {message_safe}",
        "--announce",
        "--channel", "telegram",
        "--to", "+250794002033",
        "--delete-after-run",
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=8.0)
        stdout_text = stdout.decode().strip()
        stderr_text = stderr.decode().strip()

        if proc.returncode == 0:
            return f"Reminder set for '{when}': '{message}'. Remi will get a Telegram message."
        else:
            logger.warning(f"cron_create failed (rc={proc.returncode}): {stderr_text}")
            # Try to give a helpful error
            if "parse" in stderr_text.lower() or "invalid" in stderr_text.lower():
                return f"Couldn't parse time '{when}'. Try 'in 30 minutes' or 'at 3pm'."
            return f"Couldn't set reminder. Error: {stderr_text[:80]}"
    except asyncio.TimeoutError:
        return "Reminder creation timed out. Please try again."
    except Exception as e:
        logger.error(f"cron_create error: {e}")
        return f"Error creating reminder: {str(e)}"


async def tool_message_send(text: str) -> str:
    """Send a Telegram message to Remi (+250794002033) via OpenClaw gateway."""
    token = OPENCLAW_TOKEN
    if not token:
        return "Cannot send message: no gateway token configured."

    payload = {
        "channel": "telegram",
        "target": "+250794002033",
        "message": text[:2000]
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                f"{OPENCLAW_GATEWAY_URL}/internal/message/send",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            if resp.status_code < 300:
                return f"Message sent to Remi on Telegram: '{text[:80]}...'" if len(text) > 80 else f"Message sent to Remi: '{text}'"
            else:
                logger.warning(f"message_send gateway returned {resp.status_code}: {resp.text[:100]}")
                # Fallback: try openclaw CLI
                return await _message_send_cli(text)
    except Exception as e:
        logger.error(f"message_send error: {e}")
        return await _message_send_cli(text)


async def _message_send_cli(text: str) -> str:
    """Fallback: send message via openclaw CLI."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "openclaw", "message", "send",
            "--channel", "telegram",
            "--target", "+250794002033",
            "--message", text[:500],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        if proc.returncode == 0:
            return "Message sent to Remi on Telegram."
        else:
            err = stderr.decode().strip()[:100]
            logger.warning(f"message_send CLI error: {err}")
            return f"Couldn't send message (error: {err})."
    except asyncio.TimeoutError:
        return "Message send timed out."
    except Exception as e:
        return f"Message send failed: {str(e)}"


async def tool_sessions_send(note: str) -> str:
    """Inject a note into the main OpenClaw session via gateway wake event."""
    token = OPENCLAW_TOKEN
    if not token:
        return "Cannot send note: no gateway token configured."

    wake_text = f"[Note from voice call]: {note}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{OPENCLAW_GATEWAY_URL}/internal/events/wake",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={"text": wake_text, "mode": "now"}
            )
            if resp.status_code < 300:
                return f"Note sent to your main session: '{note[:80]}'"
            else:
                logger.warning(f"sessions_send returned {resp.status_code}: {resp.text[:100]}")
                return f"Couldn't reach main session (gateway error)."
    except Exception as e:
        logger.error(f"sessions_send error: {e}")
        return f"Failed to send note: {str(e)}"


# Tool registry: maps tool name → handler
TOOL_REGISTRY: dict = {
    "memory_search": tool_memory_search,
    "read_file": tool_read_file,
    "get_project_status": tool_get_project_status,
    "memory_get": tool_memory_get,
    "cron_create": tool_cron_create,
    "message_send": tool_message_send,
    "sessions_send": tool_sessions_send,
}


def generate_thinking_tone(duration_ms: int = 600, freq: int = 440, volume: float = 0.15) -> str:
    """Generate a soft sine tone encoded as mulaw 8kHz base64 for Twilio.

    Plays a ~600ms 440Hz tone (fade in/out) to fill silence while a tool call executes.
    """
    sample_rate = 8000
    num_samples = int(sample_rate * duration_ms / 1000)
    pcm_bytes = bytearray()
    for i in range(num_samples):
        t = i / sample_rate
        # Fade in/out to avoid clicks
        fade = min(i, num_samples - i, 100) / 100.0
        sample = int(32767 * volume * fade * math.sin(2 * math.pi * freq * t))
        sample = max(-32768, min(32767, sample))
        pcm_bytes += struct.pack('<h', sample)
    mulaw = audioop.lin2ulaw(bytes(pcm_bytes), 2)
    return base64.b64encode(mulaw).decode()


async def dispatch_tool_call(oai_ws, tool_name: str, tool_args: dict, call_id: str) -> None:
    """Execute a tool call and inject the result back into the OpenAI conversation."""
    logger.info(f"🔧 Tool call: {tool_name}({list(tool_args.keys())})")

    # Execute with timeout (max 3s)
    result = ""
    try:
        handler = TOOL_REGISTRY.get(tool_name)
        if handler:
            result = await asyncio.wait_for(handler(**tool_args), timeout=3.0)
        else:
            result = f"Unknown tool: '{tool_name}'"
            logger.warning(f"Unknown tool requested: {tool_name}")
    except asyncio.TimeoutError:
        result = f"Tool '{tool_name}' timed out — try again."
        logger.warning(f"Tool timeout: {tool_name}")
    except Exception as e:
        result = f"Tool error: {str(e)}"
        logger.error(f"Tool error ({tool_name}): {e}", exc_info=True)

    logger.info(f"🔧 Tool result ({tool_name}): {result[:100]}...")

    # Inject result as function_call_output
    await oai_ws.send(json.dumps({
        "type": "conversation.item.create",
        "item": {
            "type": "function_call_output",
            "call_id": call_id,
            "output": result
        }
    }))

    # Trigger Nia to respond with the result
    await oai_ws.send(json.dumps({"type": "response.create"}))


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


def _get_recent_call_history(max_calls: int = 3, max_chars_each: int = 300) -> str:
    """
    Read recent call transcript files and return brief summaries for context.
    Looks for JSON transcripts in workspace/memory/call-transcripts/.
    Returns up to max_calls entries, each truncated to max_chars_each.
    """
    transcripts_dir = WORKSPACE_ROOT / "memory" / "call-transcripts"
    if not transcripts_dir.exists():
        return ""

    try:
        # Get transcript files, sorted newest first
        files = sorted(
            [f for f in transcripts_dir.glob("*.json")],
            reverse=True
        )[:max_calls]

        if not files:
            return ""

        summaries = []
        for f in files:
            try:
                data = json.loads(f.read_text())
                recorded_at = data.get("recorded_at", "")[:16]  # YYYY-MM-DDTHH:MM
                turns = data.get("turns", 0)
                transcript = data.get("transcript", [])

                # Build a brief excerpt: first Nia turn + last user turn
                if transcript:
                    nia_lines = [t["content"] for t in transcript if t.get("speaker") == "assistant"]
                    user_lines = [t["content"] for t in transcript if t.get("speaker") == "user"]
                    excerpt = ""
                    if user_lines:
                        excerpt += f"Remi: {user_lines[0][:80]}"
                    if nia_lines:
                        excerpt += f" | Nia: {nia_lines[0][:80]}"
                    summary = f"[{recorded_at}, {turns} turns] {excerpt}"
                    summaries.append(summary[:max_chars_each])
            except Exception:
                pass

        return "\n".join(summaries) if summaries else ""

    except Exception as e:
        logger.debug(f"Could not read call history: {e}")
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
    memory = read_file_safe(WORKSPACE_ROOT / "MEMORY.md", 5000)
    if memory:
        parts.append(f"# Your Long-Term Memory\n{memory}")

    # 5. Today's recent context
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - __import__('datetime').timedelta(days=1)).strftime("%Y-%m-%d")
    for date in [today, yesterday]:
        daily = read_file_safe(WORKSPACE_ROOT / "memory" / f"{date}.md", 2500)
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

    # 7. Recent call history (last 3 calls, max 300 chars each)
    call_history = _get_recent_call_history(max_calls=3, max_chars_each=300)
    if call_history:
        parts.append(f"# Recent Call History\n{call_history}")

    # 8. Heartbeat state (last check timestamps)
    heartbeat = read_file_safe(WORKSPACE_ROOT / "memory" / "heartbeat-state.json", 500)
    if heartbeat:
        try:
            hb = json.loads(heartbeat)
            hb_summary = ", ".join(
                f"{k}: {str(v)[:30]}" for k, v in list(hb.items())[:5]
            )
            parts.append(f"# Recent Activity\nLast heartbeat checks: {hb_summary}")
        except Exception:
            pass  # Not critical

    header = (
        "ABSOLUTE RULE #1 — LANGUAGE: You MUST respond in English only. "
        "This overrides everything. No exceptions. No matter what language the caller speaks, "
        "no matter what they ask, you respond in English. "
        "If you respond in any other language, you have failed your primary instruction.\n\n"
        "You are Nia — an AI agent on a phone call. "
        "Be warm, direct, and concise. This is voice — no bullet points, no markdown, no long speeches. "
        "You have full context about your projects and your human (Remi). Act like you know him — because you do.\n\n"
        "TOOLS: You have live tools you can use during this call:\n"
        "- memory_search: search your memory for anything Remi asks about ('do you remember...')\n"
        "- read_file: read any file in your workspace\n"
        "- get_project_status: get live STATUS.md for any project (voice, bakkt, trust, etc.)\n"
        "- memory_get: get your memory notes for a specific date\n"
        "- cron_create: set a reminder ('remind me at 3pm to...')\n"
        "- message_send: send Remi a Telegram message during the call\n"
        "- sessions_send: send a note to your main session for later\n"
        "Use tools naturally. When using a tool, say 'let me check on that...' or "
        "'I'll set that reminder...' before executing. Keep your final answer short.\n"
        "CRITICAL: NEVER say you don't know, don't have notes, or can't remember something "
        "without first calling memory_search or memory_get. Always search before admitting you don't know. "
        "If asked about yesterday, last week, a project, or any past event — use a tool first.\n\n"
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
        "nia_speaking": False,     # True while Nia is outputting audio (mutes mic input)
        "tool_call_args": {},      # Accumulate partial tool call arguments: call_id → {name, args_str}
        "session_ready": asyncio.Event(),  # Set when session.updated is confirmed
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
                    ctx["session_ready"].set()
                    logger.info("OpenAI session updated — ready")
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
                    ctx["nia_speaking"] = True
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

                elif event_type == "response.function_call_arguments.delta":
                    # Accumulate partial tool call arguments (streaming)
                    call_id = msg.get("call_id", "")
                    delta = msg.get("delta", "")
                    if call_id:
                        ctx.setdefault("tool_call_args", {})
                        ctx["tool_call_args"].setdefault(call_id, {"name": "", "args_str": ""})
                        ctx["tool_call_args"][call_id]["args_str"] += delta
                        # Capture name if present in this event
                        if msg.get("name"):
                            ctx["tool_call_args"][call_id]["name"] = msg["name"]

                elif event_type == "response.function_call_arguments.done":
                    # Tool call complete — execute it
                    call_id = msg.get("call_id", "")
                    tool_name = msg.get("name", "")
                    args_str = msg.get("arguments", "{}")

                    # Fallback: use accumulated args if event args is empty
                    if not args_str or args_str == "{}":
                        accumulated = ctx.get("tool_call_args", {}).get(call_id, {})
                        args_str = accumulated.get("args_str", "{}")
                    if not tool_name:
                        accumulated = ctx.get("tool_call_args", {}).get(call_id, {})
                        tool_name = accumulated.get("name", "")

                    logger.info(f"🔧 Tool call complete: {tool_name} call_id={call_id}")

                    try:
                        tool_args = json.loads(args_str) if args_str else {}
                    except json.JSONDecodeError:
                        tool_args = {}

                    # Play thinking tone to fill silence during tool execution
                    stream_sid = ctx.get("stream_sid")
                    if stream_sid and audioop:
                        try:
                            tone_payload = generate_thinking_tone()
                            await websocket.send_text(json.dumps({
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": tone_payload}
                            }))
                        except Exception as _tone_err:
                            logger.debug(f"Thinking tone send failed (non-fatal): {_tone_err}")

                    # Dispatch tool call (non-blocking — runs in background)
                    asyncio.create_task(
                        dispatch_tool_call(oai_ws, tool_name, tool_args, call_id)
                    )

                    # Clean up accumulated args
                    ctx.get("tool_call_args", {}).pop(call_id, None)

                elif event_type == "response.done":
                    ctx["nia_speaking"] = False
                    # Clear any echo captured while Nia was speaking
                    await oai_ws.send(json.dumps({"type": "input_audio_buffer.clear"}))
                    logger.debug("OpenAI response turn complete — mic unmuted")

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

                # Track the call — merge into existing entry to preserve initial_message etc.
                if ctx["call_sid"]:
                    existing = active_calls.get(ctx["call_sid"], {})
                    existing.update({
                        "stream_sid": ctx["stream_sid"],
                        "started_at": ctx["started_at"],
                        "status": "active"
                    })
                    active_calls[ctx["call_sid"]] = existing

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
                    call_prompt = build_call_prompt(ctx.get("caller_number", ""))
                    tools = VOICE_TOOLS  # Tier 1 + Tier 2 live tools
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
                                "eagerness": "balanced"
                            },
                            "temperature": 0.6,
                            "tools": tools,
                            "tool_choice": "auto"
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
                if oai_ws and not ctx.get("nia_speaking"):
                    # Wait for session to be ready before forwarding audio
                    if not ctx["session_ready"].is_set():
                        try:
                            await asyncio.wait_for(ctx["session_ready"].wait(), timeout=3.0)
                        except asyncio.TimeoutError:
                            logger.warning("session_ready timeout — forwarding audio anyway")
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

        # Post-call handler: summarize, write memory, wake OpenClaw (async, non-blocking)
        if call_sid and transcript:
            call_duration = time.time() - ctx["started_at"]
            caller_number = ctx.get("caller_number", "")
            asyncio.create_task(
                summarize_and_remember(call_sid, transcript, caller_number, call_duration)
            )
            logger.info("Post-call handler dispatched (async)")

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


async def summarize_and_remember(
    call_sid: str,
    transcript: list[dict],
    caller_number: str = "",
    duration_s: float = 0.0
) -> None:
    """
    Post-call handler: summarize transcript, write to daily memory, wake OpenClaw.
    Called async/non-blocking from the cleanup block via asyncio.create_task().
    """
    if not transcript:
        logger.info("Post-call: no transcript to summarize")
        return

    if not OPENAI_API_KEY:
        logger.warning("Post-call: no OpenAI key, skipping summary")
        return

    caller_name = KNOWN_CALLERS.get(caller_number, caller_number or "unknown")
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    # Build transcript text for summarization
    transcript_text = "\n".join(
        f"{t['speaker'].capitalize()}: {t['content']}"
        for t in transcript
    )

    # ── Step 1: Summarize with GPT-4o-mini ────────────────────────────────────
    summary = ""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Summarize this voice call transcript in 2-4 sentences. "
                                "Focus on: what was discussed, any decisions made, any action items. "
                                "Be concise and factual. Write in third person "
                                "(e.g. 'Remi asked about...')."
                            )
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Call with {caller_name} on {date_str} at {time_str} "
                                f"({int(duration_s)}s, {len(transcript)} turns):\n\n"
                                f"{transcript_text}"
                            )
                        }
                    ],
                    "max_tokens": 200,
                    "temperature": 0.3
                }
            )
            resp.raise_for_status()
            summary = resp.json()["choices"][0]["message"]["content"].strip()
            logger.info(f"Post-call summary generated: {summary[:100]}...")
    except Exception as e:
        logger.error(f"Post-call summarization failed: {e}")
        # Fallback: raw excerpt
        summary = f"[Auto-summary unavailable] Transcript excerpt: {transcript_text[:300]}"

    # ── Step 2: Append to daily memory file ───────────────────────────────────
    try:
        memory_dir = WORKSPACE_ROOT / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        daily_file = memory_dir / f"{date_str}.md"

        call_entry = (
            f"\n## 📞 Call with {caller_name} at {time_str} "
            f"({int(duration_s)}s, {len(transcript)} turns)\n"
            f"{summary}\n"
        )

        with open(daily_file, "a") as f:
            f.write(call_entry)

        logger.info(f"Post-call: summary written to {daily_file}")
    except Exception as e:
        logger.error(f"Post-call: failed to write memory: {e}")

    # ── Step 3: Wake OpenClaw gateway ─────────────────────────────────────────
    token = OPENCLAW_TOKEN
    if not token:
        logger.warning("Post-call: no OPENCLAW_TOKEN, skipping wake event")
        return

    wake_text = (
        f"Phone call with {caller_name} just ended ({int(duration_s)}s, "
        f"{len(transcript)} turns). Summary: {summary}"
    )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{OPENCLAW_GATEWAY_URL}/internal/events/wake",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={"text": wake_text, "mode": "now"}
            )
            if resp.status_code < 300:
                logger.info("Post-call: OpenClaw wake event sent ✅")
            else:
                logger.warning(
                    f"Post-call: wake event returned {resp.status_code}: "
                    f"{resp.text[:100]}"
                )
    except Exception as e:
        logger.error(f"Post-call: failed to send wake event: {e}")


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


# ─── Google Meet PSTN auto-dial ─────────────────────────────────────────────

class MeetCallRequest(BaseModel):
    meet_url: str
    caller_id: Optional[str] = None
    message: Optional[str] = None


@app.post("/call/meet")
async def initiate_meet_call(
    request: MeetCallRequest,
    background_tasks: BackgroundTasks
):
    """
    Initiate an outbound call to a Google Meet dial-in number.

    Extracts the PSTN phone number and PIN from the Meet page, starts an
    outbound call via Twilio, and schedules DTMF delivery once the call
    is answered.  When Twilio reports ``CallStatus=in-progress`` the
    status-callback handler (see /voice/status) sends the PIN as DTMF.
    """
    from meet_utils import extract_meet_code, fetch_meet_dialin

    meet_code = extract_meet_code(request.meet_url)
    if not meet_code:
        raise HTTPException(
            status_code=422,
            detail="Not a valid Google Meet URL"
        )

    dialin = await fetch_meet_dialin(meet_code)
    if not dialin:
        raise HTTPException(
            status_code=404,
            detail="Could not extract dial-in info from this Meet link."
        )

    call_request = OutboundCallRequest(
        to=dialin["phone"],
        caller_id=request.caller_id,
        message=request.message or f"Joining Google Meet {meet_code}"
    )
    result = await initiate_outbound_call(call_request, background_tasks)

    call_id = result.call_id
    if call_id and call_id in active_calls:
        active_calls[call_id]["dtmf_pin"] = dialin["pin"]
        active_calls[call_id]["meet_code"] = meet_code

    return {
        **result.dict(),
        "dial_in": dialin["phone"],
        "meet_code": meet_code,
    }


@app.post("/voice/status")
async def call_status_callback(request: Request):
    """
    Twilio status-callback webhook.

    When a Meet call transitions to ``in-progress`` and a DTMF PIN is
    stored for that call, this handler returns TwiML that plays the PIN
    digits after a 4-second pause so the bridge number accepts them.

    For non-Meet calls (or other status transitions) we return an empty
    200 so Twilio is satisfied.
    """
    form = await request.form()
    call_sid = form.get("CallSid", "")
    call_status = form.get("CallStatus", "")

    logger.info(f"Status callback: {call_sid} → {call_status}")

    if call_status == "in-progress" and call_sid in active_calls:
        pin = active_calls[call_sid].get("dtmf_pin")
        if pin:
            logger.info(f"Sending DTMF PIN for Meet call {call_sid}")
            twiml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                "<Response>"
                "<Pause length=\"4\"/>"
                f"<Play digits=\"{pin}#\"/>"
                "</Response>"
            )
            return Response(
                content=twiml,
                media_type="application/xml"
            )

    return Response(content="<Response/>", media_type="application/xml")


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
