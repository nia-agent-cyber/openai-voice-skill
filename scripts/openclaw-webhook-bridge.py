#!/usr/bin/env python3
"""
OpenClaw Voice Channel Integration Bridge

This extends the existing webhook server to provide integration with the
OpenClaw TypeScript channel plugin. It adds:

1. OpenClaw session awareness
2. Context injection from TypeScript plugin
3. Webhook event forwarding to TypeScript
4. Session state synchronization

This runs alongside the existing webhook-server.py and adds OpenClaw-specific
functionality without disrupting the core voice call handling.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
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
TYPESCRIPT_WEBHOOK_URL = os.getenv("TYPESCRIPT_WEBHOOK_URL", "http://localhost:8081/python-webhook")
TYPESCRIPT_HEALTH_URL = os.getenv("TYPESCRIPT_HEALTH_URL", "http://localhost:8081/health")
BRIDGE_PORT = int(os.getenv("BRIDGE_PORT", "8082"))

# OpenClaw session tracking
openclaw_sessions: Dict[str, Dict[str, Any]] = {}  # call_id -> session_data
session_call_map: Dict[str, str] = {}  # openclaw_session_id -> call_id

app = FastAPI(title="OpenClaw Voice Bridge", version="1.0.0")

# Pydantic models
class OpenClawCallRequest(BaseModel):
    to: str
    caller_id: Optional[str] = None
    message: Optional[str] = None
    openclaw_session_id: str
    context: Optional[Dict[str, Any]] = None

class ContextInjectionRequest(BaseModel):
    call_id: str
    openclaw_session_id: str
    context: Dict[str, Any]

class WebhookEventRequest(BaseModel):
    call_id: str
    event_type: str
    data: Dict[str, Any]
    timestamp: Optional[str] = None

@app.post("/openclaw/call")
async def initiate_openclaw_call(request: OpenClawCallRequest, background_tasks: BackgroundTasks):
    """
    Initiate a call with OpenClaw session context.
    
    This endpoint receives requests from the TypeScript plugin and:
    1. Tracks the OpenClaw session mapping
    2. Forwards the call to the main webhook server
    3. Injects the provided context
    """
    try:
        # Track OpenClaw session
        session_data = {
            "openclaw_session_id": request.openclaw_session_id,
            "phone_number": request.to,
            "caller_id": request.caller_id,
            "context": request.context or {},
            "created_at": datetime.now().isoformat(),
            "status": "initiating"
        }
        
        # Forward to main webhook server
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8080/call",
                json={
                    "to": request.to,
                    "caller_id": request.caller_id,
                    "message": request.message
                },
                timeout=30
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Main webhook server error: {response.text}"
                )
            
            call_response = response.json()
            call_id = call_response["call_id"]
            
            # Store session mapping
            openclaw_sessions[call_id] = session_data
            session_call_map[request.openclaw_session_id] = call_id
            
            logger.info(f"OpenClaw call initiated: {call_id} for session {request.openclaw_session_id}")
            
            # Inject context in background
            if request.context:
                background_tasks.add_task(inject_call_context, call_id, request.context)
            
            # Notify TypeScript plugin
            background_tasks.add_task(
                notify_typescript_plugin,
                "call_initiated",
                {
                    "call_id": call_id,
                    "openclaw_session_id": request.openclaw_session_id,
                    "phone_number": request.to,
                    "direction": "outbound"
                }
            )
            
            return {
                "status": "initiated",
                "call_id": call_id,
                "openclaw_session_id": request.openclaw_session_id,
                "message": f"OpenClaw call initiated to {request.to}"
            }
            
    except Exception as e:
        logger.error(f"Error initiating OpenClaw call: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/openclaw/context")
async def inject_context(request: ContextInjectionRequest):
    """
    Inject or update OpenClaw context for an active call.
    """
    call_id = request.call_id
    
    if call_id not in openclaw_sessions:
        openclaw_sessions[call_id] = {
            "openclaw_session_id": request.openclaw_session_id,
            "context": {},
            "created_at": datetime.now().isoformat()
        }
    
    # Update context
    openclaw_sessions[call_id]["context"].update(request.context)
    openclaw_sessions[call_id]["context_updated_at"] = datetime.now().isoformat()
    
    logger.info(f"Context injected for call {call_id}")
    
    return {"status": "context_injected", "call_id": call_id}

@app.delete("/openclaw/call/{openclaw_session_id}")
async def end_openclaw_call(openclaw_session_id: str):
    """
    End a call by OpenClaw session ID.
    """
    call_id = session_call_map.get(openclaw_session_id)
    if not call_id:
        raise HTTPException(status_code=404, detail="OpenClaw session not found")
    
    try:
        # Forward to main webhook server
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"http://localhost:8080/call/{call_id}")
            
            # Clean up tracking regardless of response
            cleanup_session_mapping(call_id, openclaw_session_id)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Main server returned {response.status_code} for call end")
                return {"status": "ended", "call_id": call_id, "note": "cleaned_up_locally"}
                
    except Exception as e:
        logger.error(f"Error ending OpenClaw call: {e}")
        # Still clean up locally
        cleanup_session_mapping(call_id, openclaw_session_id)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/openclaw/sessions")
async def get_openclaw_sessions():
    """
    Get all active OpenClaw sessions.
    """
    return {
        "active_sessions": len(openclaw_sessions),
        "sessions": list(openclaw_sessions.values())
    }

@app.get("/openclaw/session/{openclaw_session_id}")
async def get_openclaw_session(openclaw_session_id: str):
    """
    Get specific OpenClaw session details.
    """
    call_id = session_call_map.get(openclaw_session_id)
    if not call_id or call_id not in openclaw_sessions:
        raise HTTPException(status_code=404, detail="OpenClaw session not found")
    
    session_data = openclaw_sessions[call_id]
    
    # Get current call status from main server
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8080/calls", timeout=5)
            if response.status_code == 200:
                active_calls = response.json().get("calls", [])
                current_call = next((c for c in active_calls if c["call_id"] == call_id), None)
                if current_call:
                    session_data["current_status"] = current_call
    except Exception:
        pass  # Continue without current status
    
    return session_data

@app.post("/webhook/forward")
async def forward_webhook_event(request: WebhookEventRequest, background_tasks: BackgroundTasks):
    """
    Receive webhook events from the main server and forward to TypeScript plugin.
    This would typically be called by a modified version of the main webhook server.
    """
    call_id = request.call_id
    event_type = request.event_type
    
    # Check if this is an OpenClaw-managed call
    if call_id in openclaw_sessions:
        session_data = openclaw_sessions[call_id]
        openclaw_session_id = session_data["openclaw_session_id"]
        
        # Update session status based on event
        update_session_status(call_id, event_type, request.data)
        
        # Forward to TypeScript plugin
        background_tasks.add_task(
            notify_typescript_plugin,
            event_type,
            {
                "call_id": call_id,
                "openclaw_session_id": openclaw_session_id,
                **request.data
            }
        )
        
        # Clean up if call ended
        if event_type in ["call_ended", "call_failed"]:
            cleanup_session_mapping(call_id, openclaw_session_id)
    
    return {"status": "forwarded"}

@app.get("/health")
async def health_check():
    """
    Health check that includes connectivity to main server and TypeScript plugin.
    """
    health_status = {
        "bridge": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_openclaw_sessions": len(openclaw_sessions)
    }
    
    # Check main webhook server
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8080/health", timeout=5)
            health_status["main_server"] = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception:
        health_status["main_server"] = "unreachable"
    
    # Check TypeScript plugin
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(TYPESCRIPT_HEALTH_URL, timeout=5)
            health_status["typescript_plugin"] = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception:
        health_status["typescript_plugin"] = "unreachable"
    
    return health_status

async def inject_call_context(call_id: str, context: Dict[str, Any]):
    """
    Inject context into a call (background task).
    
    This could involve updating the call instructions, setting variables, etc.
    For now, we just store it for reference.
    """
    try:
        # Store context in our tracking
        if call_id in openclaw_sessions:
            openclaw_sessions[call_id]["context"].update(context)
            
        # Future enhancement: Actually inject into OpenAI Realtime session
        # This would require additional API calls or integration points
        
        logger.info(f"Context injection completed for call {call_id}")
        
    except Exception as e:
        logger.error(f"Error injecting context for call {call_id}: {e}")

async def notify_typescript_plugin(event_type: str, data: Dict[str, Any]):
    """
    Send webhook event to TypeScript plugin (background task).
    """
    try:
        webhook_payload = {
            "call_id": data.get("call_id"),
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                TYPESCRIPT_WEBHOOK_URL,
                json=webhook_payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.debug(f"Webhook event {event_type} sent to TypeScript plugin")
            else:
                logger.warning(f"TypeScript webhook returned {response.status_code}")
                
    except Exception as e:
        logger.error(f"Error notifying TypeScript plugin: {e}")

def update_session_status(call_id: str, event_type: str, event_data: Dict[str, Any]):
    """
    Update session status based on webhook events.
    """
    if call_id not in openclaw_sessions:
        return
    
    session = openclaw_sessions[call_id]
    
    status_mapping = {
        "call_ringing": "ringing",
        "call_answered": "active", 
        "call_ended": "ended",
        "call_failed": "failed"
    }
    
    if event_type in status_mapping:
        session["status"] = status_mapping[event_type]
        session["last_event"] = event_type
        session["last_updated"] = datetime.now().isoformat()
    
    # Store transcript updates
    if event_type == "transcript_updated" and "transcript" in event_data:
        if "transcript_entries" not in session:
            session["transcript_entries"] = []
        
        session["transcript_entries"].append({
            "timestamp": datetime.now().isoformat(),
            "speaker": event_data.get("speaker", "unknown"),
            "text": event_data["transcript"],
            "confidence": event_data.get("confidence")
        })

def cleanup_session_mapping(call_id: str, openclaw_session_id: str):
    """
    Clean up session mappings when a call ends.
    """
    if call_id in openclaw_sessions:
        del openclaw_sessions[call_id]
    
    if openclaw_session_id in session_call_map:
        del session_call_map[openclaw_session_id]
    
    logger.info(f"Cleaned up session mapping for call {call_id}")

@app.on_event("startup")
async def startup_event():
    """
    Startup tasks.
    """
    logger.info("🌉 OpenClaw Voice Bridge starting up...")
    
    # Check connectivity to main server
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8080/health", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Main webhook server connectivity verified")
            else:
                logger.warning("⚠️ Main webhook server returned non-200 status")
    except Exception as e:
        logger.error(f"❌ Cannot reach main webhook server: {e}")
    
    logger.info(f"🌉 OpenClaw Voice Bridge ready on port {BRIDGE_PORT}")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Cleanup on shutdown.
    """
    logger.info("🌉 OpenClaw Voice Bridge shutting down...")
    
    # End any active OpenClaw sessions
    for call_id, session in list(openclaw_sessions.items()):
        try:
            openclaw_session_id = session["openclaw_session_id"]
            logger.info(f"Cleaning up session {openclaw_session_id} (call {call_id})")
            cleanup_session_mapping(call_id, openclaw_session_id)
        except Exception as e:
            logger.error(f"Error cleaning up session {call_id}: {e}")

if __name__ == "__main__":
    logger.info("🌉 Starting OpenClaw Voice Channel Integration Bridge")
    logger.info(f"   Bridge Port: {BRIDGE_PORT}")
    logger.info(f"   TypeScript Plugin Webhook: {TYPESCRIPT_WEBHOOK_URL}")
    logger.info(f"   Main Webhook Server: http://localhost:8080")
    
    uvicorn.run(app, host="0.0.0.0", port=BRIDGE_PORT)