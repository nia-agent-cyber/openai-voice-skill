# MCP Server Plan — openai-voice-skill

**Created by:** Voice PM (session: voice-pm-cycle-2)
**Date:** 2026-04-07

---

## Goal

Package the voice skill as an **MCP (Model Context Protocol) server** so users can install it via:

```bash
claude mcp add openai-voice-skill
```

This gives the skill native discoverability in Claude Desktop, Claude Code, and any MCP-compatible client — directly complementing our pending PR #791 in anthropics/skills.

---

## What to Build

A Python MCP server (`scripts/mcp_server.py`) that exposes the voice skill's core capabilities as MCP tools.

### MCP Tools to Expose

1. **`make_call`** — Initiate an outbound call to a phone number
   - Input: `phone_number` (string), `message` (string, optional)
   - Action: POST to `http://localhost:8080/call`
   - Returns: call SID, status

2. **`call_status`** — Check status of a call
   - Input: `call_sid` (string)
   - Action: GET from Twilio API or local state
   - Returns: status, duration

3. **`join_google_meet`** — Join a Google Meet via PSTN
   - Input: `meet_url` (string)
   - Action: POST to `http://localhost:8080/call/meet`
   - Returns: call SID, dial-in number used

4. **`get_call_history`** — List recent calls with summaries
   - Input: `limit` (int, default 5)
   - Action: read from `~/repos/openai-voice-skill/call_log.json` or memory files
   - Returns: list of calls with transcript excerpts

---

## Implementation Approach

Use the `mcp` Python package (official Anthropic MCP SDK):

```bash
pip install mcp
```

Example server structure (`scripts/mcp_server.py`):

```python
from mcp.server.fastmcp import FastMCP
import httpx, json

mcp = FastMCP("openai-voice-skill")
WEBHOOK_BASE = "http://localhost:8080"

@mcp.tool()
async def make_call(phone_number: str, message: str = "") -> dict:
    """Initiate a phone call to the given number."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{WEBHOOK_BASE}/call", json={
            "to": phone_number,
            "message": message
        })
        return resp.json()

@mcp.tool()
async def join_google_meet(meet_url: str) -> dict:
    """Join a Google Meet conference via PSTN dial-in."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{WEBHOOK_BASE}/call/meet", json={
            "meet_url": meet_url
        })
        return resp.json()

if __name__ == "__main__":
    mcp.run()
```

---

## Files to Create/Modify

| File | Action | Notes |
|------|--------|-------|
| `scripts/mcp_server.py` | CREATE | Main MCP server |
| `scripts/requirements.txt` | MODIFY | Add `mcp>=1.0.0`, `httpx` |
| `mcp.json` | CREATE | MCP manifest for Claude Desktop |
| `tests/test_mcp_server.py` | CREATE | Unit tests (mock httpx) |
| `README.md` | MODIFY | Add MCP installation section |

---

## MCP Manifest (`mcp.json`)

```json
{
  "name": "openai-voice-skill",
  "version": "1.0.0",
  "description": "Real-time phone calling and Google Meet joining for AI agents",
  "server": {
    "command": "python",
    "args": ["scripts/mcp_server.py"],
    "env": {}
  },
  "tools": [
    "make_call",
    "call_status",
    "join_google_meet",
    "get_call_history"
  ]
}
```

---

## Acceptance Criteria

1. `python scripts/mcp_server.py` starts without error
2. MCP server lists 4 tools when queried
3. `make_call` correctly POSTs to `http://localhost:8080/call`
4. `join_google_meet` correctly POSTs to `http://localhost:8080/call/meet`
5. All new tests pass (`pytest tests/test_mcp_server.py`)
6. Existing 670+ tests still pass (no regressions)
7. README has installation instructions for Claude Desktop users
8. PR opened with all changes

---

## GitHub Issue

Create a GitHub issue for tracking: "feat: Add MCP server — voice calling tools for Claude Desktop"

---

## PR Instructions

After implementation:
1. `git checkout -b feat/mcp-server`
2. Commit all changes
3. Push and open PR: `gh pr create --title "feat: Add MCP server for Claude Desktop integration" --body "..."`
4. PR body should include: what was added, how to test, links to MCP docs

---

## Installation Instructions for README (add these)

```markdown
## Claude Desktop / MCP Integration

Install as an MCP server in Claude Desktop:

```bash
# 1. Install the MCP package
pip install mcp httpx

# 2. Start the voice server (see Setup above)
python scripts/webhook-server.py

# 3. Add to Claude Desktop's MCP config (~/.claude/mcp.json)
{
  "mcpServers": {
    "openai-voice-skill": {
      "command": "python",
      "args": ["/path/to/openai-voice-skill/scripts/mcp_server.py"]
    }
  }
}
```

Then in Claude Desktop, you can say:
- "Call +1234567890"
- "Join this Google Meet: https://meet.google.com/xxx-yyyy-zzz"
- "What calls did Nia make today?"
```
