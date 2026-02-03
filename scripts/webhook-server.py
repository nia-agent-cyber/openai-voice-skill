#!/usr/bin/env python3
"""
OpenAI Realtime SIP Voice Server

Handles incoming calls via OpenAI's native SIP integration.
Much lower latency than multi-hop STT→LLM→TTS solutions.

Usage:
    python webhook-server.py

Environment:
    OPENAI_API_KEY - Your OpenAI API key
    OPENAI_PROJECT_ID - Your OpenAI project ID
    WEBHOOK_SECRET - Secret for validating webhook signatures (optional)
    PORT - Server port (default: 8080)
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_PROJECT_ID = os.getenv("OPENAI_PROJECT_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
PORT = int(os.getenv("PORT", "8080"))

# Load agent config
CONFIG_PATH = Path(__file__).parent.parent / "config" / "agent.json"
DEFAULT_CONFIG = {
    "name": "Assistant",
    "instructions": "You are a helpful voice assistant. Be concise and conversational.",
    "voice": "alloy",
    "model": "gpt-realtime"
}

def load_agent_config():
    """Load agent configuration from file or use defaults."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                config = json.load(f)
                return {**DEFAULT_CONFIG, **config}
        except Exception as e:
            logger.warning(f"Failed to load config: {e}, using defaults")
    return DEFAULT_CONFIG

AGENT_CONFIG = load_agent_config()

# Track active calls
active_calls: dict[str, dict] = {}

app = FastAPI(title="OpenAI Voice Server")


def verify_webhook_signature(request_body: bytes, signature: str, timestamp: str) -> bool:
    """Verify OpenAI webhook signature."""
    if not WEBHOOK_SECRET:
        return True  # Skip verification if no secret configured
    
    # OpenAI uses: v1,base64(HMAC-SHA256(timestamp.body))
    message = f"{timestamp}.{request_body.decode()}"
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Signature format: v1,<signature>
    if signature.startswith("v1,"):
        signature = signature[3:]
    
    return hmac.compare_digest(expected, signature)


@app.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle OpenAI webhook events.
    
    Primary event: realtime.call.incoming
    """
    body = await request.body()
    
    # Verify signature if configured
    signature = request.headers.get("webhook-signature", "")
    timestamp = request.headers.get("webhook-timestamp", "")
    
    if WEBHOOK_SECRET and not verify_webhook_signature(body, signature, timestamp):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    event_type = event.get("type")
    event_id = event.get("id")
    
    logger.info(f"Webhook received: {event_type} (id: {event_id})")
    
    if event_type == "realtime.call.incoming":
        # Handle incoming call
        call_data = event.get("data", {})
        call_id = call_data.get("call_id")
        sip_headers = call_data.get("sip_headers", [])
        
        # Extract caller info from SIP headers
        from_header = next((h["value"] for h in sip_headers if h["name"] == "From"), "unknown")
        to_header = next((h["value"] for h in sip_headers if h["name"] == "To"), "unknown")
        
        logger.info(f"Incoming call: {call_id} from {from_header} to {to_header}")
        
        # Accept the call in background (don't block webhook response)
        background_tasks.add_task(accept_call, call_id, from_header)
        
        return JSONResponse({"status": "accepted", "call_id": call_id})
    
    elif event_type == "realtime.call.ended":
        call_data = event.get("data", {})
        call_id = call_data.get("call_id")
        
        if call_id in active_calls:
            duration = time.time() - active_calls[call_id].get("started_at", time.time())
            logger.info(f"Call ended: {call_id} (duration: {duration:.1f}s)")
            del active_calls[call_id]
        
        return JSONResponse({"status": "noted"})
    
    else:
        logger.debug(f"Unhandled event type: {event_type}")
        return JSONResponse({"status": "ignored"})


async def accept_call(call_id: str, caller: str):
    """
    Accept an incoming call with agent configuration.
    
    This calls OpenAI's accept endpoint to bridge the SIP call
    to a Realtime session with our custom instructions.
    """
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set - cannot accept call")
        return
    
    url = f"https://api.openai.com/v1/realtime/calls/{call_id}/accept"
    
    payload = {
        "type": "realtime",
        "model": AGENT_CONFIG["model"],
        "instructions": AGENT_CONFIG["instructions"],
        "voice": AGENT_CONFIG["voice"],
        # Optional: add tools, turn detection settings, etc.
    }
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Call {call_id} accepted successfully")
                active_calls[call_id] = {
                    "caller": caller,
                    "started_at": time.time(),
                    "config": AGENT_CONFIG["name"]
                }
            else:
                logger.error(f"Failed to accept call: {response.status_code} - {response.text}")
    
    except Exception as e:
        logger.error(f"Error accepting call {call_id}: {e}")


async def reject_call(call_id: str, reason: str = "busy"):
    """Reject an incoming call."""
    if not OPENAI_API_KEY:
        return
    
    url = f"https://api.openai.com/v1/realtime/calls/{call_id}/reject"
    
    # Map reason to SIP status code
    status_codes = {
        "busy": 486,
        "unavailable": 480,
        "declined": 603
    }
    
    payload = {"status_code": status_codes.get(reason, 603)}
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, headers=headers, timeout=10)
            logger.info(f"Call {call_id} rejected ({reason})")
    except Exception as e:
        logger.error(f"Error rejecting call {call_id}: {e}")


@app.get("/calls")
async def list_calls():
    """List active calls."""
    return {
        "active_calls": len(active_calls),
        "calls": [
            {
                "call_id": call_id,
                "caller": data["caller"],
                "duration": time.time() - data["started_at"],
                "agent": data["config"]
            }
            for call_id, data in active_calls.items()
        ]
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "agent": AGENT_CONFIG["name"],
        "active_calls": len(active_calls),
        "config_loaded": CONFIG_PATH.exists()
    }


@app.get("/")
async def root():
    """Root endpoint with basic info."""
    return {
        "service": "OpenAI Voice Server",
        "agent": AGENT_CONFIG["name"],
        "endpoints": {
            "webhook": "POST /webhook",
            "calls": "GET /calls",
            "health": "GET /health"
        }
    }


if __name__ == "__main__":
    # Startup checks
    if not OPENAI_API_KEY:
        logger.warning("⚠️  OPENAI_API_KEY not set - calls will fail")
    if not OPENAI_PROJECT_ID:
        logger.warning("⚠️  OPENAI_PROJECT_ID not set - needed for Twilio SIP config")
    
    logger.info(f"🎙️  Starting OpenAI Voice Server")
    logger.info(f"   Agent: {AGENT_CONFIG['name']}")
    logger.info(f"   Voice: {AGENT_CONFIG['voice']}")
    logger.info(f"   Port: {PORT}")
    
    if OPENAI_PROJECT_ID:
        logger.info(f"   SIP URI: sip:{OPENAI_PROJECT_ID}@sip.api.openai.com;transport=tls")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT)
