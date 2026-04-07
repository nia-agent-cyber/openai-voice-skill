"""
mcp_server.py — MCP server for openai-voice-skill.

Exposes voice skill capabilities as MCP tools for Claude Desktop and
any MCP-compatible client.

Usage:
    python scripts/mcp_server.py

Then add to ~/.claude/mcp.json:
    {
      "mcpServers": {
        "openai-voice-skill": {
          "command": "python",
          "args": ["/path/to/openai-voice-skill/scripts/mcp_server.py"]
        }
      }
    }
"""

import json
import os
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("openai-voice-skill")

WEBHOOK_BASE = os.environ.get("VOICE_WEBHOOK_BASE", "http://localhost:8080")
CALL_LOG_PATH = Path(os.environ.get(
    "VOICE_CALL_LOG",
    Path.home() / "repos" / "openai-voice-skill" / "call_log.json"
))
MEMORY_DIR = Path(os.environ.get(
    "VOICE_MEMORY_DIR",
    Path.home() / ".openclaw" / "workspace" / "memory"
))


@mcp.tool()
async def make_call(phone_number: str, message: str = "") -> dict:
    """Initiate an outbound phone call to the given number.

    Args:
        phone_number: E.164 phone number to call (e.g. +12025551234)
        message: Optional spoken message or instruction for the call

    Returns:
        dict with call_sid and status from the voice server
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{WEBHOOK_BASE}/call",
            json={"to": phone_number, "message": message},
        )
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def call_status(call_sid: str) -> dict:
    """Check the status of a call by its SID.

    Args:
        call_sid: Twilio call SID (e.g. CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx)

    Returns:
        dict with status and duration fields
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{WEBHOOK_BASE}/call/{call_sid}/status",
        )
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def join_google_meet(meet_url: str) -> dict:
    """Join a Google Meet conference via PSTN dial-in.

    Extracts the dial-in number and PIN from the Meet page, then
    initiates an outbound Twilio call that bridges into the meeting.

    Args:
        meet_url: Google Meet URL (e.g. https://meet.google.com/abc-defg-hij)

    Returns:
        dict with call_sid and dial_in_number used
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{WEBHOOK_BASE}/call/meet",
            json={"meet_url": meet_url},
        )
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def get_call_history(limit: int = 5) -> list:
    """List recent calls with summaries and transcript excerpts.

    Reads from call_log.json (if present) or recent memory files.

    Args:
        limit: Maximum number of calls to return (default 5)

    Returns:
        List of call records, most recent first
    """
    calls = []

    # Try call_log.json first
    if CALL_LOG_PATH.exists():
        try:
            data = json.loads(CALL_LOG_PATH.read_text())
            if isinstance(data, list):
                calls = data
            elif isinstance(data, dict) and "calls" in data:
                calls = data["calls"]
        except (json.JSONDecodeError, OSError):
            pass

    # Fall back to memory files if no log found
    if not calls and MEMORY_DIR.exists():
        memory_files = sorted(
            MEMORY_DIR.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for mf in memory_files[:limit]:
            try:
                entry = json.loads(mf.read_text())
                calls.append(entry)
            except (json.JSONDecodeError, OSError):
                continue

    return calls[:limit]


if __name__ == "__main__":
    mcp.run()
