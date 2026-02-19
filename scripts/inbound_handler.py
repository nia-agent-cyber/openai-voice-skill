#!/usr/bin/env python3
"""
Inbound Call Handler - T4 Implementation

This module provides inbound call authorization and session context
for the voice skill. It works alongside webhook-server.py without
modifying it.

Endpoints:
- POST /authorize - Check if a caller is authorized
- POST /context - Get session context for an authorized caller
- GET /callers - List known callers
- GET /missed-calls - List recent missed calls
- POST /missed-calls/callback - Mark missed call for callback
- GET /health - Health check

Usage:
    python inbound_handler.py

Environment:
    PORT - Server port (default: 8084)
    VOICE_ALLOWLIST - Comma-separated list of allowed phone numbers
    VOICE_POLICY - Policy: open, allowlist (default), pairing
"""

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PORT = int(os.getenv("PORT", "8084"))
VOICE_ALLOWLIST = os.getenv("VOICE_ALLOWLIST", "").split(",")
VOICE_POLICY = os.getenv("VOICE_POLICY", "allowlist")

# Try to load allowlist from config file
CONFIG_PATH = Path(__file__).parent.parent / "config" / "inbound.json"

def load_config() -> Dict[str, Any]:
    """Load inbound configuration from file or environment."""
    config = {
        "allowFrom": [],
        "policy": VOICE_POLICY,
        "voicemailEnabled": True,
        "afterHoursMessage": "I'm not available right now. Please leave a message.",
    }
    
    # Load from config file if exists
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                file_config = json.load(f)
                config.update(file_config)
                logger.info(f"Loaded config from {CONFIG_PATH}")
        except Exception as e:
            logger.warning(f"Failed to load config file: {e}")
    
    # Override with environment variables
    if VOICE_ALLOWLIST and VOICE_ALLOWLIST[0]:
        config["allowFrom"] = [n.strip() for n in VOICE_ALLOWLIST if n.strip()]
    
    if VOICE_POLICY:
        config["policy"] = VOICE_POLICY
    
    return config


# Data models
@dataclass
class CallerHistory:
    """Tracks history for a known caller."""
    phone: str
    name: Optional[str] = None
    call_count: int = 0
    last_call_at: Optional[str] = None
    notes: Optional[str] = None
    first_seen_at: Optional[str] = None


@dataclass
class MissedCall:
    """Record of a missed call."""
    timestamp: str
    from_number: str
    reason: str  # unauthorized, busy, no_answer, after_hours
    has_voicemail: bool = False
    voicemail_transcript: Optional[str] = None
    callback_scheduled: bool = False
    callback_scheduled_at: Optional[str] = None


# In-memory storage (replace with persistent storage in production)
caller_history: Dict[str, CallerHistory] = {}
missed_calls: List[MissedCall] = []

# Pydantic models for API
class AuthorizeRequest(BaseModel):
    caller_phone: str
    called_phone: Optional[str] = None
    caller_name: Optional[str] = None
    caller_city: Optional[str] = None
    caller_state: Optional[str] = None
    caller_country: Optional[str] = None


class AuthorizeResponse(BaseModel):
    authorized: bool
    reason: str
    message: str
    matched_entry: Optional[str] = None
    policy: str


class ContextRequest(BaseModel):
    caller_phone: str
    caller_name: Optional[str] = None
    caller_city: Optional[str] = None
    caller_state: Optional[str] = None
    caller_country: Optional[str] = None


class ContextResponse(BaseModel):
    session_key: str
    is_known_caller: bool
    caller_name: Optional[str] = None
    previous_call_count: int
    last_call_at: Optional[str] = None
    caller_notes: Optional[str] = None
    context_instructions: str


class MissedCallRecord(BaseModel):
    from_number: str
    reason: str
    voicemail_transcript: Optional[str] = None


app = FastAPI(title="Inbound Call Handler")


def normalize_phone(phone: str) -> str:
    """Normalize phone number to E.164 format."""
    if not phone:
        return ""
    # Remove all non-digit characters except leading +
    cleaned = re.sub(r'[^\d+]', '', phone)
    # Ensure it starts with +
    return cleaned if cleaned.startswith('+') else f'+{cleaned}'


def mask_phone(phone: str) -> str:
    """Mask phone number for logging."""
    if not phone or len(phone) < 7:
        return "****"
    return f"{phone[:4]}****{phone[-4:]}"


def check_allowlist(phone: str, allow_from: List[str]) -> Optional[str]:
    """
    Check if phone matches allowlist.
    
    Supports:
    - Exact match: "+14402915517"
    - Wildcard: "*"
    - Prefix match: "+1440*"
    """
    normalized = normalize_phone(phone)
    
    for entry in allow_from:
        if not entry:
            continue
            
        # Wildcard - allow all
        if entry.strip() == "*":
            return "*"
        
        entry_normalized = normalize_phone(entry.rstrip("*"))
        
        # Prefix match
        if entry.endswith("*"):
            if normalized.startswith(entry_normalized):
                return entry
        
        # Exact match
        if normalized == entry_normalized:
            return entry
    
    return None


def authorize_caller(phone: str, config: Dict[str, Any]) -> AuthorizeResponse:
    """Authorize an incoming call based on config."""
    normalized = normalize_phone(phone)
    policy = config.get("policy", "allowlist")
    allow_from = config.get("allowFrom", [])
    
    # Open policy - accept all
    if policy == "open":
        return AuthorizeResponse(
            authorized=True,
            reason="allowed",
            message="Open policy - all calls accepted",
            policy="open"
        )
    
    # Pairing policy - check paired devices (falls back to allowlist)
    if policy == "pairing":
        matched = check_allowlist(normalized, allow_from)
        if matched:
            return AuthorizeResponse(
                authorized=True,
                reason="allowlist_match",
                message="Caller matches paired device",
                matched_entry=matched,
                policy="pairing"
            )
        return AuthorizeResponse(
            authorized=False,
            reason="denied",
            message="Caller not paired",
            policy="pairing"
        )
    
    # Allowlist policy (default)
    if not allow_from:
        return AuthorizeResponse(
            authorized=False,
            reason="not_configured",
            message="No allowlist configured - inbound calls disabled for security",
            policy="allowlist"
        )
    
    matched = check_allowlist(normalized, allow_from)
    if matched:
        return AuthorizeResponse(
            authorized=True,
            reason="allowlist_match",
            message=f"Caller matches allowlist entry: {matched}",
            matched_entry=matched,
            policy="allowlist"
        )
    
    return AuthorizeResponse(
        authorized=False,
        reason="denied",
        message="Caller not in allowlist",
        policy="allowlist"
    )


def build_context(request: ContextRequest) -> ContextResponse:
    """Build session context for an inbound call."""
    normalized = normalize_phone(request.caller_phone)
    session_key = f"voice:{normalized.replace('+', '')}"
    
    # Look up caller history
    history = caller_history.get(normalized)
    is_known = history is not None
    
    # Build context instructions
    parts = [
        "--- INBOUND CALL CONTEXT ---",
        "Call Direction: Inbound (caller reached you)",
    ]
    
    # Add location if available
    location_parts = [
        p for p in [request.caller_city, request.caller_state, request.caller_country]
        if p
    ]
    if location_parts:
        parts.append(f"Caller Location: {', '.join(location_parts)}")
    
    # Add caller name if available
    if request.caller_name:
        parts.append(f"Caller ID Name: {request.caller_name}")
    
    # Add history for known callers
    if is_known and history:
        parts.extend([
            "",
            "--- CALLER HISTORY ---",
        ])
        if history.name:
            parts.append(f"Known as: {history.name}")
        parts.append(f"Previous calls: {history.call_count}")
        if history.last_call_at:
            parts.append(f"Last call: {history.last_call_at}")
        if history.notes:
            parts.append(f"Notes: {history.notes}")
        parts.extend([
            "",
            "Since this is a returning caller, you may reference previous conversations if relevant.",
        ])
    else:
        parts.extend([
            "",
            "--- NEW CALLER ---",
            "This is the first call from this number. Be welcoming and ask how you can help.",
        ])
    
    parts.append("--- END CONTEXT ---")
    
    return ContextResponse(
        session_key=session_key,
        is_known_caller=is_known,
        caller_name=history.name if history else request.caller_name,
        previous_call_count=history.call_count if history else 0,
        last_call_at=history.last_call_at if history else None,
        caller_notes=history.notes if history else None,
        context_instructions="\n".join(parts)
    )


@app.post("/authorize", response_model=AuthorizeResponse)
async def authorize_inbound_call(request: AuthorizeRequest):
    """
    Authorize an inbound call.
    
    Returns whether the call should be accepted based on
    the configured policy and allowlist.
    """
    config = load_config()
    result = authorize_caller(request.caller_phone, config)
    
    logger.info(
        f"Authorization: {mask_phone(request.caller_phone)} -> "
        f"{result.authorized} ({result.reason})"
    )
    
    return result


@app.post("/context", response_model=ContextResponse)
async def get_session_context(request: ContextRequest):
    """
    Get session context for an authorized inbound call.
    
    Returns session key and context instructions to inject
    into the agent's system prompt.
    """
    context = build_context(request)
    
    logger.info(
        f"Context built: {mask_phone(request.caller_phone)} -> "
        f"session={context.session_key}, known={context.is_known_caller}"
    )
    
    return context


@app.post("/call-started")
async def record_call_started(request: ContextRequest):
    """
    Record that a call has started (updates caller history).
    """
    normalized = normalize_phone(request.caller_phone)
    now = datetime.now(timezone.utc).isoformat() + "Z"
    
    if normalized in caller_history:
        history = caller_history[normalized]
        history.call_count += 1
        history.last_call_at = now
        if request.caller_name and not history.name:
            history.name = request.caller_name
    else:
        caller_history[normalized] = CallerHistory(
            phone=normalized,
            name=request.caller_name,
            call_count=1,
            last_call_at=now,
            first_seen_at=now
        )
    
    logger.info(f"Call started: {mask_phone(request.caller_phone)}")
    return {"status": "recorded"}


@app.post("/missed-call")
async def record_missed_call(request: MissedCallRecord):
    """Record a missed call for later follow-up."""
    now = datetime.now(timezone.utc).isoformat() + "Z"
    
    missed_call = MissedCall(
        timestamp=now,
        from_number=request.from_number,
        reason=request.reason,
        has_voicemail=bool(request.voicemail_transcript),
        voicemail_transcript=request.voicemail_transcript
    )
    
    missed_calls.append(missed_call)
    
    # Keep only last 100 missed calls
    if len(missed_calls) > 100:
        missed_calls.pop(0)
    
    logger.info(
        f"Missed call recorded: {mask_phone(request.from_number)} "
        f"({request.reason})"
    )
    
    return {"status": "recorded", "timestamp": now}


@app.get("/callers")
async def list_known_callers(limit: int = Query(50, le=100)):
    """List known callers (for admin/debugging)."""
    callers = [
        {
            "phone": mask_phone(h.phone),
            "name": h.name,
            "call_count": h.call_count,
            "last_call_at": h.last_call_at,
            "first_seen_at": h.first_seen_at,
        }
        for h in list(caller_history.values())[:limit]
    ]
    
    return {
        "callers": callers,
        "total": len(caller_history)
    }


@app.get("/missed-calls")
async def list_missed_calls(
    limit: int = Query(20, le=100),
    pending_only: bool = Query(False)
):
    """List recent missed calls."""
    calls = missed_calls[-limit:]
    
    if pending_only:
        calls = [c for c in calls if not c.callback_scheduled and c.has_voicemail]
    
    return {
        "missed_calls": [
            {
                "timestamp": c.timestamp,
                "from_number": mask_phone(c.from_number),
                "reason": c.reason,
                "has_voicemail": c.has_voicemail,
                "callback_scheduled": c.callback_scheduled,
            }
            for c in reversed(calls)
        ],
        "total": len(calls),
        "pending_callbacks": len([c for c in missed_calls if not c.callback_scheduled and c.has_voicemail])
    }


@app.post("/missed-calls/callback")
async def schedule_callback(timestamp: str):
    """Mark a missed call as scheduled for callback."""
    for call in missed_calls:
        if call.timestamp == timestamp:
            call.callback_scheduled = True
            call.callback_scheduled_at = datetime.now(timezone.utc).isoformat() + "Z"
            return {"status": "scheduled", "timestamp": timestamp}
    
    raise HTTPException(status_code=404, detail="Missed call not found")


@app.put("/callers/{phone}/notes")
async def update_caller_notes(phone: str, notes: str):
    """Update notes for a caller."""
    normalized = normalize_phone(phone)
    
    if normalized not in caller_history:
        raise HTTPException(status_code=404, detail="Caller not found")
    
    caller_history[normalized].notes = notes
    return {"status": "updated"}


@app.get("/config")
async def get_config():
    """Get current inbound configuration (without secrets)."""
    config = load_config()
    
    # Mask allowlist entries for privacy
    masked_allowlist = [
        entry if entry == "*" else mask_phone(entry)
        for entry in config.get("allowFrom", [])
    ]
    
    return {
        "policy": config.get("policy"),
        "allowlist_count": len(config.get("allowFrom", [])),
        "allowlist_preview": masked_allowlist[:5],
        "voicemail_enabled": config.get("voicemailEnabled", True),
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "known_callers": len(caller_history),
        "missed_calls": len(missed_calls),
        "pending_callbacks": len([c for c in missed_calls if not c.callback_scheduled and c.has_voicemail])
    }


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "Inbound Call Handler",
        "version": "1.0.0",
        "endpoints": {
            "authorize": "POST /authorize - Check if caller is authorized",
            "context": "POST /context - Get session context for caller",
            "call_started": "POST /call-started - Record call start",
            "missed_call": "POST /missed-call - Record missed call",
            "callers": "GET /callers - List known callers",
            "missed_calls": "GET /missed-calls - List missed calls",
            "callback": "POST /missed-calls/callback - Schedule callback",
            "config": "GET /config - Get current config",
            "health": "GET /health - Health check"
        }
    }


if __name__ == "__main__":
    logger.info("🎙️ Starting Inbound Call Handler")
    logger.info(f"   Port: {PORT}")
    logger.info(f"   Policy: {VOICE_POLICY}")
    logger.info(f"   Config file: {CONFIG_PATH}")
    
    config = load_config()
    allowlist_count = len(config.get("allowFrom", []))
    logger.info(f"   Allowlist entries: {allowlist_count}")
    
    if allowlist_count == 0 and config.get("policy") == "allowlist":
        logger.warning("⚠️  No allowlist configured - all inbound calls will be rejected!")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT)
