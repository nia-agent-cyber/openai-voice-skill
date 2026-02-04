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
import re
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import httpx
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Query, Depends, Header
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioException
from twilio.request_validator import RequestValidator

# Import call recording functionality
from call_recording import recording_manager, CallRecord, TranscriptEntry

# Import tool handler for OpenClaw integration
try:
    from realtime_tool_handler import start_tool_handler, stop_tool_handler, get_active_handlers
    TOOL_HANDLER_AVAILABLE = True
    logger.info("OpenClaw tool handler integration enabled")
except ImportError as e:
    logger.warning(f"Tool handler not available: {e}")
    TOOL_HANDLER_AVAILABLE = False
    
    async def start_tool_handler(*args, **kwargs):
        pass
    async def stop_tool_handler(*args, **kwargs):
        pass
    def get_active_handlers():
        return {}

# Import security utilities
from security_utils import (
    validator, encryptor, error_sanitizer, api_auth,
    ValidationError, SecurityValidator, DataEncryption, ErrorSanitizer
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import session context extraction (purely additive - no call handling)
try:
    from session_context import create_context_extractor
    context_extractor = create_context_extractor()
    logger.info("Session context integration enabled")
except ImportError as e:
    logger.warning(f"Session context integration not available: {e}")
    context_extractor = None

# Load environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_PROJECT_ID = os.getenv("OPENAI_PROJECT_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
PORT = int(os.getenv("PORT", "8080"))

# Security configuration
REQUIRE_WEBHOOK_SIGNATURE = os.getenv("REQUIRE_WEBHOOK_SIGNATURE", "true").lower() == "true"
REQUIRE_API_KEY_AUTH = os.getenv("REQUIRE_API_KEY_AUTH", "true").lower() == "true"
ENCRYPT_SESSION_DATA = os.getenv("ENCRYPT_SESSION_DATA", "true").lower() == "true"
ENABLE_ERROR_SANITIZATION = os.getenv("ENABLE_ERROR_SANITIZATION", "true").lower() == "true"

# Twilio configuration for outbound calls
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Initialize Twilio client if credentials are available
twilio_client = None
twilio_validator = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        twilio_validator = RequestValidator(TWILIO_AUTH_TOKEN)
        logger.info("Twilio client and validator initialized for outbound calls")
    except Exception as e:
        logger.warning(f"Failed to initialize Twilio client: {e}")
else:
    logger.info("Twilio credentials not configured - outbound calls disabled")

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

# Track active calls with encryption support
active_calls: dict[str, dict] = {}

# Session context integration handled via context_extractor above

# Security utilities
security = HTTPBearer(auto_error=False)

def create_secure_call_data(call_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create call data with sensitive information encrypted if enabled."""
    if not ENCRYPT_SESSION_DATA:
        return call_data
    
    # Identify sensitive fields
    sensitive_fields = ['caller_number', 'callee_number', 'to', 'from', 'sip_headers', 'metadata']
    secure_data = call_data.copy()
    
    for field in sensitive_fields:
        if field in secure_data and secure_data[field]:
            encrypted = encryptor.encrypt_data(secure_data[field])
            if encrypted:
                secure_data[f"{field}_encrypted"] = encrypted
                # Keep only masked version for logging
                if field in ['caller_number', 'callee_number', 'to', 'from']:
                    secure_data[field] = validator.mask_sensitive_data(str(secure_data[field]))
                else:
                    del secure_data[field]
    
    return secure_data

def get_decrypted_call_data(call_id: str, field: str) -> Optional[Any]:
    """Get decrypted call data for a specific field."""
    if call_id not in active_calls:
        return None
    
    call_data = active_calls[call_id]
    encrypted_field = f"{field}_encrypted"
    
    if encrypted_field in call_data:
        return encryptor.decrypt_data(call_data[encrypted_field], return_json=True)
    
    return call_data.get(field)

def sanitize_error_response(error: Exception, error_type: str = 'internal') -> str:
    """Sanitize error message for API response."""
    if not ENABLE_ERROR_SANITIZATION:
        return str(error)
    
    return error_sanitizer.sanitize_error_message(str(error), error_type)

async def verify_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> bool:
    """Verify API key for service-to-service authentication."""
    if not REQUIRE_API_KEY_AUTH:
        return True
    
    if not credentials:
        raise HTTPException(
            status_code=401, 
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if not api_auth.validate_api_key(credentials.credentials):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    return True

# Pydantic models for API requests
class OutboundCallRequest(BaseModel):
    to: str  # Phone number to call
    caller_id: Optional[str] = None  # Override default caller ID
    message: Optional[str] = None  # Optional initial message
    
class OutboundCallResponse(BaseModel):
    status: str
    call_id: Optional[str] = None
    message: str

# Call history API models
class CallHistoryRequest(BaseModel):
    limit: int = 50
    offset: int = 0
    call_type: Optional[str] = None

class CallRecordResponse(BaseModel):
    call_id: str
    call_type: str
    caller_number: Optional[str]
    callee_number: Optional[str]
    started_at: str
    ended_at: Optional[str]
    duration_seconds: Optional[float]
    status: str
    has_audio: bool
    has_transcript: bool
    metadata: Optional[Dict[str, Any]]

class TranscriptResponse(BaseModel):
    transcript: List[Dict[str, Any]]
    call_info: CallRecordResponse

app = FastAPI(title="OpenAI Voice Server")


def mask_phone_number(phone: str) -> str:
    """Mask phone number for logging to protect PII."""
    if not phone or len(phone) < 7:
        return "****"
    return f"{phone[:3]}****{phone[-4:]}"


def validate_phone_number(phone: str) -> bool:
    """Enhanced phone number validation using security utilities."""
    return validator.validate_phone_number(phone, strict=True)


def get_base_url() -> str:
    """Get the base URL for this server."""
    # Use PUBLIC_URL if set (for production deployments with cloudflare tunnel, etc.)
    public_url = os.getenv("PUBLIC_URL")
    if public_url:
        # Remove trailing slash if present
        return public_url.rstrip('/')
    
    # Fallback to localhost construction for local development
    port = os.getenv("PORT", "8080")
    host = os.getenv("HOST", "localhost")
    protocol = os.getenv("PROTOCOL", "http")
    return f"{protocol}://{host}:{port}"


def verify_webhook_signature(request_body: bytes, signature: str, timestamp: str) -> bool:
    """Enhanced webhook signature verification with security checks."""
    # Enforce signature verification in production
    if REQUIRE_WEBHOOK_SIGNATURE and not WEBHOOK_SECRET:
        logger.error("Webhook signature verification required but WEBHOOK_SECRET not configured")
        return False
    
    if not WEBHOOK_SECRET:
        if REQUIRE_WEBHOOK_SIGNATURE:
            return False
        logger.warning("Webhook signature verification skipped - WEBHOOK_SECRET not configured")
        return True
    
    if not signature or not timestamp:
        if REQUIRE_WEBHOOK_SIGNATURE:
            logger.warning("Missing signature or timestamp in webhook request")
            return False
        return True
    
    try:
        # Validate timestamp to prevent replay attacks
        timestamp_int = int(timestamp)
        current_time = int(time.time())
        time_diff = abs(current_time - timestamp_int)
        
        # Reject requests older than 5 minutes or from the future
        if time_diff > 300:
            logger.warning(f"Webhook timestamp too old or invalid: {time_diff}s difference")
            return False
        
        # OpenAI uses: v1,base64(HMAC-SHA256(timestamp.body))
        message = f"{timestamp}.{request_body.decode()}"
        expected = hmac.new(
            WEBHOOK_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Handle signature format
        if signature.startswith("v1,"):
            signature = signature[3:]
        
        # Use secure comparison to prevent timing attacks
        is_valid = hmac.compare_digest(expected, signature)
        
        if not is_valid:
            logger.warning("Invalid webhook signature detected")
        
        return is_valid
        
    except (ValueError, TypeError) as e:
        logger.warning(f"Error validating webhook signature: {e}")
        return False


def verify_twilio_signature(url: str, params: dict, signature: str) -> bool:
    """Verify Twilio webhook signature using RequestValidator."""
    if not twilio_validator:
        logger.warning("Twilio validator not configured - skipping signature validation")
        return True  # Skip validation if no validator configured
    
    try:
        return twilio_validator.validate(url, params, signature)
    except Exception as e:
        logger.error(f"Error validating Twilio signature: {e}")
        return False


@app.post("/call", response_model=OutboundCallResponse)
async def initiate_outbound_call(request: OutboundCallRequest, background_tasks: BackgroundTasks):
    """
    Initiate an outbound call using Twilio to connect to OpenAI Realtime API.
    
    This endpoint:
    1. Validates the phone number
    2. Uses Twilio to place a call to the OpenAI SIP endpoint  
    3. Returns the call ID for tracking
    """
    # Validate Twilio is configured
    if not twilio_client:
        raise HTTPException(
            status_code=503, 
            detail="Outbound calling not configured - missing Twilio credentials"
        )
    
    # Early input validation - reject malformed input immediately
    if not request.to or not isinstance(request.to, str):
        raise HTTPException(
            status_code=400,
            detail="Phone number is required and must be a string"
        )
    
    # Remove any whitespace or common formatting
    phone_cleaned = request.to.strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    request.to = phone_cleaned
    
    # Validate phone number format with enhanced validation
    if not validate_phone_number(request.to):
        raise HTTPException(
            status_code=400,
            detail="Invalid phone number format - must be E.164 format with valid country code (e.g. +1234567890)"
        )
    
    # Additional validation for caller_id if provided
    if request.caller_id and not validate_phone_number(request.caller_id.strip()):
        raise HTTPException(
            status_code=400,
            detail="Invalid caller_id format - must be E.164 format with valid country code"
        )
    
    # Validate OpenAI configuration
    if not OPENAI_PROJECT_ID:
        raise HTTPException(
            status_code=500,
            detail="OpenAI project ID not configured - required for SIP endpoint"
        )
    
    try:
        # Use provided caller ID or default
        from_number = request.caller_id or TWILIO_PHONE_NUMBER
        if not from_number:
            raise HTTPException(
                status_code=500,
                detail="No caller ID configured - set TWILIO_PHONE_NUMBER or provide caller_id"
            )
        
        # Create OpenAI SIP URI
        sip_uri = f"sip:{OPENAI_PROJECT_ID}@sip.api.openai.com;transport=tls"
        
        # Construct TwiML webhook URL
        twiml_url = f"{get_base_url()}/twiml/outbound?sip_uri={urllib.parse.quote(sip_uri)}"
        
        logger.info(f"Initiating outbound call: {mask_phone_number(request.to)} via {sip_uri}")
        logger.info(f"Using TwiML webhook URL: {twiml_url}")
        
        # Create Twilio call
        call = twilio_client.calls.create(
            to=request.to,
            from_=from_number,
            url=twiml_url,  # Use TwiML webhook URL instead of SIP URI
            timeout=30,
            record=False  # We'll handle recording separately if needed
        )
        
        # Track the call
        call_data = {
            "type": "outbound",
            "to": request.to,
            "from": from_number,
            "started_at": time.time(),
            "twilio_call_sid": call.sid,
            "openai_project_id": OPENAI_PROJECT_ID,
            "status": "initiated"
        }
        
        active_calls[call.sid] = call_data
        
        logger.info(f"Outbound call initiated: {call.sid} to {mask_phone_number(request.to)}")
        
        # Start call recording for outbound call
        background_tasks.add_task(
            recording_manager.start_call_recording,
            call.sid, "outbound", from_number, request.to,
            {"initial_message": request.message, "twilio_call_sid": call.sid}
        )
        
        # Set up OpenAI Realtime session in background
        background_tasks.add_task(setup_outbound_realtime_session, call.sid, request.message)
        
        return OutboundCallResponse(
            status="initiated", 
            call_id=call.sid,
            message=f"Call initiated to {request.to}"
        )
        
    except TwilioException as e:
        logger.error(f"Twilio error initiating call: {e}")
        raise HTTPException(status_code=400, detail=f"Call failed: {str(e)}")
    except Exception as e:
        logger.error(f"Error initiating outbound call: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle OpenAI webhook events.
    
    Primary event: realtime.call.incoming
    """
    body = await request.body()
    
    # Check if this is a Twilio webhook by looking for CallStatus or Twilio signature
    twilio_signature = request.headers.get("X-Twilio-Signature")
    is_twilio_webhook = twilio_signature is not None
    
    # Parse form data for Twilio webhooks, JSON for OpenAI
    if is_twilio_webhook:
        # Twilio sends form data
        form_data = await request.form()
        event = dict(form_data)
        
        # Validate Twilio signature
        url = str(request.url)
        if not verify_twilio_signature(url, event, twilio_signature):
            logger.warning("Invalid Twilio webhook signature")
            raise HTTPException(status_code=401, detail="Invalid Twilio signature")
        
        # Handle Twilio webhook events (for outbound calls)
        return await handle_twilio_webhook(event)
    else:
        # Handle OpenAI webhooks
        # Verify OpenAI signature if configured
        signature = request.headers.get("webhook-signature", "")
        timestamp = request.headers.get("webhook-timestamp", "")
        
        if WEBHOOK_SECRET and not verify_webhook_signature(body, signature, timestamp):
            logger.warning("Invalid OpenAI webhook signature")
            raise HTTPException(status_code=401, detail="Invalid OpenAI signature")
        
        try:
            event = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")
        
        event_type = event.get("type")
        event_id = event.get("id")
        
        logger.info(f"OpenAI webhook received: {event_type} (id: {event_id})")
    
    # Handle OpenAI webhook events (for both inbound and outbound)
    
    if event_type == "realtime.call.incoming":
        # Handle incoming call
        call_data = event.get("data", {})
        call_id = call_data.get("call_id")
        sip_headers = call_data.get("sip_headers", [])
        
        # Extract caller info from SIP headers
        from_header = next((h["value"] for h in sip_headers if h["name"] == "From"), "unknown")
        to_header = next((h["value"] for h in sip_headers if h["name"] == "To"), "unknown")
        
        logger.info(f"Incoming call: {call_id} from {mask_phone_number(from_header)} to {mask_phone_number(to_header)}")
        
        # Start call recording
        background_tasks.add_task(
            recording_manager.start_call_recording,
            call_id, "inbound", from_header, to_header,
            {"sip_headers": sip_headers}
        )
        
        # Check for pre-prepared instructions (for outbound calls that arrive via OpenAI webhook)
        enhanced_instructions = None
        matched_call_id = None
        
        # Strategy 1: Match by destination number (most reliable)
        caller_number = re.search(r'\+?[\d]+', from_header or "")
        caller_number = caller_number.group() if caller_number else None
        
        if caller_number:
            for stored_call_id, call_data in active_calls.items():
                if (call_data.get("enhanced_instructions") and 
                    call_data.get("status") == "realtime_ready" and
                    call_data.get("to") == caller_number):
                    enhanced_instructions = call_data.get("enhanced_instructions")
                    matched_call_id = stored_call_id
                    logger.info(f"Matched call {call_id} to outbound call {stored_call_id} by destination number")
                    break
        
        # Strategy 2: Fallback to time window (most recent call within 60 seconds)
        if not enhanced_instructions:
            best_call_id = None
            best_time_diff = float('inf')
            
            for stored_call_id, call_data in active_calls.items():
                if call_data.get("enhanced_instructions") and call_data.get("status") == "realtime_ready":
                    time_diff = time.time() - call_data.get("started_at", 0)
                    if time_diff < 60 and time_diff < best_time_diff:
                        enhanced_instructions = call_data.get("enhanced_instructions")
                        matched_call_id = stored_call_id
                        best_time_diff = time_diff
            
            if enhanced_instructions:
                logger.info(f"Matched call {call_id} to outbound call {matched_call_id} by time window ({best_time_diff:.1f}s ago)")
        
        # Link OpenAI call ID to matched outbound call
        if matched_call_id and enhanced_instructions:
            active_calls[matched_call_id]["openai_call_id"] = call_id
        
        # Accept the call in background (don't block webhook response)
        background_tasks.add_task(accept_call, call_id, from_header, enhanced_instructions)
        
        return JSONResponse({"status": "accepted", "call_id": call_id})
    
    elif event_type == "realtime.call.ended":
        call_data = event.get("data", {})
        call_id = call_data.get("call_id")
        
        # End call recording
        background_tasks.add_task(
            recording_manager.end_call_recording,
            call_id, "completed"
        )
        
        # Stop tool handler for this call
        if TOOL_HANDLER_AVAILABLE:
            background_tasks.add_task(stop_tool_handler, call_id)
        
        # Finalize OpenClaw session context
        if call_id in active_calls:
            call_info = active_calls[call_id]
            duration = time.time() - call_info.get("started_at", time.time())
            
            # Log call completion
            caller_name = call_info.get("caller", call_info.get("to", "Unknown"))
            
            logger.info(f"Call ended: {call_id} (duration: {duration:.1f}s)")
            del active_calls[call_id]
        
        return JSONResponse({"status": "noted"})
    
    else:
        logger.debug(f"Unhandled event type: {event_type}")
        return JSONResponse({"status": "ignored"})


async def accept_call(call_id: str, caller: str, enhanced_instructions: str = None):
    """
    Accept an incoming call with agent configuration and session context.
    
    This calls OpenAI's accept endpoint to bridge the SIP call
    to a Realtime session with our custom instructions enhanced with
    OpenClaw session context.
    
    For outbound calls, enhanced_instructions should be pre-prepared.
    For inbound calls, context will be generated from caller info.
    """
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set - cannot accept call")
        return
    
    url = f"https://api.openai.com/v1/realtime/calls/{call_id}/accept"
    
    # CONTEXT INJECTION: Use pre-prepared instructions for outbound calls,
    # or enhance instructions with session context for inbound calls
    instructions = AGENT_CONFIG["instructions"]
    
    if enhanced_instructions:
        # Use pre-prepared instructions (for outbound calls)
        instructions = enhanced_instructions
        logger.info(f"Using pre-prepared instructions for call {call_id} ({len(instructions)} chars)")
    elif context_extractor:
        # Generate instructions for inbound calls
        try:
            instructions = context_extractor.get_enhanced_instructions(
                caller, AGENT_CONFIG["instructions"], "inbound"
            )
            logger.info(f"Generated enhanced instructions for inbound call {call_id} ({len(instructions)} chars)")
        except Exception as e:
            logger.warning(f"Context enhancement failed, using base instructions: {e}")
            instructions = AGENT_CONFIG["instructions"]
    
    payload = {
        "type": "realtime",
        "model": AGENT_CONFIG["model"],
        "instructions": instructions,
        # Note: voice parameter not supported in accept endpoint
    }
    
    # Add tools if configured
    if AGENT_CONFIG.get("tools"):
        payload["tools"] = AGENT_CONFIG["tools"]
        payload["tool_choice"] = "auto"
        logger.info(f"Session configured with {len(AGENT_CONFIG['tools'])} tool(s)")
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Call {call_id} accepted successfully with enhanced instructions ({len(instructions)} chars)")
                
                # Store call data (only if not already stored for outbound calls)
                if call_id not in active_calls:
                    active_calls[call_id] = {
                        "caller": caller,
                        "started_at": time.time(),
                        "config": AGENT_CONFIG["name"],
                        "type": "inbound" if not enhanced_instructions else "outbound",
                        "instructions_length": len(instructions)
                    }
                else:
                    # Update existing call data for outbound calls
                    active_calls[call_id].update({
                        "openai_call_id": call_id,
                        "realtime_accepted": True,
                        "instructions_length": len(instructions)
                    })
                
                # Start tool handler if tools are configured
                if TOOL_HANDLER_AVAILABLE and AGENT_CONFIG.get("tools"):
                    try:
                        # Extract session ID from response if available
                        response_data = response.json()
                        session_id = response_data.get("session_id", call_id)
                        
                        # Start handler in background
                        asyncio.create_task(start_tool_handler(
                            call_id=call_id,
                            session_id=session_id,
                            model=AGENT_CONFIG["model"]
                        ))
                        logger.info(f"Tool handler started for call {call_id}")
                    except Exception as e:
                        logger.warning(f"Failed to start tool handler: {e}")
                
            else:
                logger.error(f"Failed to accept call: {response.status_code} - {response.text}")
    
    except Exception as e:
        logger.error(f"Error accepting call {call_id}: {e}")


async def handle_twilio_webhook(event: dict):
    """Handle Twilio webhook events for outbound calls."""
    call_sid = event.get("CallSid")
    call_status = event.get("CallStatus")
    
    if not call_sid or not call_status:
        return JSONResponse({"status": "ignored", "reason": "missing call data"})
    
    logger.info(f"Twilio webhook: {call_sid} status = {call_status}")
    
    # Update call tracking
    if call_sid in active_calls:
        active_calls[call_sid]["twilio_status"] = call_status
        active_calls[call_sid]["last_updated"] = time.time()
    
    # Handle different call statuses
    if call_status == "answered":
        logger.info(f"Outbound call answered: {call_sid}")
        # Set up OpenAI Realtime session now that call is answered
        await setup_outbound_realtime_session(call_sid)
        
    elif call_status in ["completed", "busy", "no-answer", "canceled", "failed"]:
        logger.info(f"Outbound call ended: {call_sid} ({call_status})")
        if call_sid in active_calls:
            duration = time.time() - active_calls[call_sid].get("started_at", time.time())
            logger.info(f"Call {call_sid} duration: {duration:.1f}s")
            del active_calls[call_sid]
    
    return JSONResponse({"status": "processed"})


async def setup_outbound_realtime_session(call_id: str, initial_message: Optional[str] = None):
    """
    Set up OpenAI Realtime session for outbound call with session context.
    
    For outbound calls, we need to wait for the call to be answered
    before setting up the Realtime session. This includes injecting
    OpenClaw session context for the person being called.
    """
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set - cannot setup Realtime session")
        return
    
    try:
        # Update call status
        if call_id in active_calls:
            active_calls[call_id]["status"] = "setting_up_realtime"
        
        # CONTEXT INJECTION: Enhance instructions for outbound call
        callee_phone = active_calls.get(call_id, {}).get("to", "unknown")
        instructions = AGENT_CONFIG["instructions"]
        
        if context_extractor:
            try:
                instructions = context_extractor.get_enhanced_instructions(
                    callee_phone, AGENT_CONFIG["instructions"], "outbound", initial_message
                )
            except Exception as e:
                logger.warning(f"Outbound context enhancement failed, using base: {e}")
                if initial_message:
                    instructions += f"\n\nStart the conversation by saying: {initial_message}"
        else:
            # Fallback: original logic
            if initial_message:
                instructions += f"\n\nStart the conversation by saying: {initial_message}"
        
        logger.info(f"Setting up outbound realtime session for {mask_phone_number(callee_phone)}")
        
        # Store enhanced call information
        if call_id in active_calls:
            active_calls[call_id].update({
                "instructions_ready": True,
                "enhanced_instructions": instructions,
                "status": "realtime_ready",
                "instructions_length": len(instructions)
            })
        
        logger.info(f"Outbound realtime session prepared ({len(instructions)} chars) - ready for call answer event")
            
    except Exception as e:
        logger.error(f"Error setting up outbound Realtime session for call {call_id}: {e}")
        
        # Fallback: prepare basic instructions
        try:
            basic_instructions = AGENT_CONFIG["instructions"]
            if initial_message:
                basic_instructions += f"\n\nStart the conversation by saying: {initial_message}"
            
            if call_id in active_calls:
                active_calls[call_id].update({
                    "enhanced_instructions": basic_instructions,
                    "status": "realtime_ready",
                    "fallback_mode": True
                })
                
            logger.info(f"Outbound call {call_id} prepared with fallback instructions")
            
        except Exception as fallback_error:
            logger.error(f"Fallback outbound setup also failed: {fallback_error}")
            if call_id in active_calls:
                active_calls[call_id]["status"] = "realtime_failed"


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


@app.delete("/call/{call_id}")
async def cancel_outbound_call(call_id: str):
    """Cancel an active outbound call."""
    if not twilio_client:
        raise HTTPException(
            status_code=503,
            detail="Twilio not configured - cannot cancel calls"
        )
    
    if call_id not in active_calls:
        raise HTTPException(status_code=404, detail="Call not found")
    
    call_data = active_calls[call_id]
    if call_data.get("type") != "outbound":
        raise HTTPException(status_code=400, detail="Can only cancel outbound calls")
    
    try:
        # Cancel the Twilio call
        twilio_call_sid = call_data.get("twilio_call_sid", call_id)
        call = twilio_client.calls(twilio_call_sid).update(status='canceled')
        
        logger.info(f"Canceled outbound call: {call_id}")
        
        # Remove from active calls
        if call_id in active_calls:
            del active_calls[call_id]
        
        return {"status": "canceled", "call_id": call_id}
        
    except TwilioException as e:
        logger.error(f"Error canceling call {call_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to cancel: {str(e)}")


@app.get("/calls")
async def list_calls():
    """List active calls."""
    call_list = []
    
    for call_id, data in active_calls.items():
        call_info = {
            "call_id": call_id,
            "type": data.get("type", "inbound"),
            "duration": time.time() - data.get("started_at", time.time()),
            "status": data.get("status", "unknown"),
            "agent": data.get("config", AGENT_CONFIG["name"])
        }
        
        # Add type-specific fields
        if data.get("type") == "outbound":
            call_info.update({
                "to": data.get("to", "unknown"),
                "from": data.get("from", "unknown"),
                "twilio_status": data.get("twilio_status", "unknown")
            })
        else:
            call_info["caller"] = data.get("caller", "unknown")
        
        call_list.append(call_info)
    
    return {
        "active_calls": len(active_calls),
        "calls": call_list
    }


@app.get("/twiml/outbound")
@app.post("/twiml/outbound")
async def outbound_twiml(request: Request, sip_uri: Optional[str] = Query(None)):
    """
    TwiML endpoint for outbound calls.
    Returns XML instructions for Twilio to dial the SIP URI.
    """
    # Get SIP URI from query parameters
    if not sip_uri:
        raise HTTPException(
            status_code=400,
            detail="Missing required parameter: sip_uri"
        )
    
    # Generate TwiML XML for dialing the SIP URI
    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial>
        <Sip>{sip_uri}</Sip>
    </Dial>
</Response>'''
    
    logger.info(f"Generated TwiML for SIP URI: {sip_uri}")
    return Response(content=twiml, media_type="application/xml")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "agent": AGENT_CONFIG["name"],
        "active_calls": len(active_calls),
        "config_loaded": CONFIG_PATH.exists(),
        "tools_enabled": TOOL_HANDLER_AVAILABLE and bool(AGENT_CONFIG.get("tools")),
        "tool_count": len(AGENT_CONFIG.get("tools", []))
    }


@app.get("/tools/status")
async def tool_handlers_status():
    """Get status of active tool handlers."""
    handlers = get_active_handlers()
    tools = AGENT_CONFIG.get("tools", [])
    
    return {
        "tool_handler_available": TOOL_HANDLER_AVAILABLE,
        "configured_tools": [t.get("name") for t in tools],
        "active_handlers": len(handlers),
        "handlers": handlers
    }


# Call History API Endpoints

@app.get("/history", response_model=List[CallRecordResponse])
async def get_call_history(
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    call_type: Optional[str] = Query(None, regex="^(inbound|outbound)$")
):
    """Get call history with pagination."""
    calls = await recording_manager.list_calls(limit, offset, call_type)
    
    return [CallRecordResponse(
        call_id=call.call_id,
        call_type=call.call_type,
        caller_number=call.caller_number,
        callee_number=call.callee_number,
        started_at=call.started_at.isoformat(),
        ended_at=call.ended_at.isoformat() if call.ended_at else None,
        duration_seconds=call.duration_seconds,
        status=call.status,
        has_audio=call.has_audio,
        has_transcript=call.has_transcript,
        metadata=call.metadata
    ) for call in calls]

@app.get("/history/{call_id}", response_model=CallRecordResponse)
async def get_call_details(call_id: str):
    """Get details for a specific call."""
    call = await recording_manager.get_call_record(call_id)
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    return CallRecordResponse(
        call_id=call.call_id,
        call_type=call.call_type,
        caller_number=call.caller_number,
        callee_number=call.callee_number,
        started_at=call.started_at.isoformat(),
        ended_at=call.ended_at.isoformat() if call.ended_at else None,
        duration_seconds=call.duration_seconds,
        status=call.status,
        has_audio=call.has_audio,
        has_transcript=call.has_transcript,
        metadata=call.metadata
    )

@app.get("/history/{call_id}/transcript", response_model=TranscriptResponse)
async def get_call_transcript(call_id: str):
    """Get transcript for a specific call."""
    call = await recording_manager.get_call_record(call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    transcript_entries = await recording_manager.get_call_transcript(call_id)
    
    transcript_data = [{
        "timestamp": entry.timestamp.isoformat(),
        "speaker": entry.speaker,
        "content": entry.content,
        "event_type": entry.event_type,
        "metadata": entry.metadata
    } for entry in transcript_entries]
    
    return TranscriptResponse(
        transcript=transcript_data,
        call_info=CallRecordResponse(
            call_id=call.call_id,
            call_type=call.call_type,
            caller_number=call.caller_number,
            callee_number=call.callee_number,
            started_at=call.started_at.isoformat(),
            ended_at=call.ended_at.isoformat() if call.ended_at else None,
            duration_seconds=call.duration_seconds,
            status=call.status,
            has_audio=call.has_audio,
            has_transcript=call.has_transcript,
            metadata=call.metadata
        )
    )

@app.get("/history/{call_id}/audio")
async def get_call_audio(call_id: str):
    """Download audio recording for a specific call."""
    call = await recording_manager.get_call_record(call_id)
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    if not call.recording_path:
        raise HTTPException(status_code=404, detail="No audio recording available")
    
    recording_path = Path(call.recording_path)
    if not recording_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    return FileResponse(
        recording_path,
        media_type="audio/wav",
        filename=f"call_{call_id}_audio.wav"
    )

@app.delete("/history/{call_id}")
async def delete_call_record(call_id: str, delete_files: bool = Query(False)):
    """Delete a call record and optionally its files."""
    success = await recording_manager.delete_call_record(call_id, delete_files)
    
    if not success:
        raise HTTPException(status_code=404, detail="Call not found")
    
    return {"status": "deleted", "call_id": call_id}

@app.get("/storage/stats")
async def get_storage_stats():
    """Get storage statistics for recordings."""
    return recording_manager.get_storage_stats()

@app.get("/")
async def root():
    """Root endpoint with basic info."""
    endpoints = {
        "webhook": "POST /webhook - Handle OpenAI/Twilio webhooks",
        "calls": "GET /calls - List active calls",
        "health": "GET /health - Health check",
        "history": "GET /history - Get call history",
        "call_details": "GET /history/{call_id} - Get call details",
        "transcript": "GET /history/{call_id}/transcript - Get call transcript",
        "audio": "GET /history/{call_id}/audio - Download call audio"
    }
    
    # Add outbound call endpoints if Twilio is configured
    if twilio_client:
        endpoints.update({
            "initiate_call": "POST /call - Initiate outbound call",
            "cancel_call": "DELETE /call/{call_id} - Cancel outbound call"
        })
    
    storage_stats = recording_manager.get_storage_stats()
    
    return {
        "service": "OpenAI Voice Server",
        "agent": AGENT_CONFIG["name"],
        "outbound_calls_enabled": twilio_client is not None,
        "recording_enabled": storage_stats["recording_enabled"],
        "transcription_enabled": storage_stats["transcription_enabled"],
        "total_recorded_calls": storage_stats["total_calls"],
        "endpoints": endpoints
    }


if __name__ == "__main__":
    # Startup checks
    if not OPENAI_API_KEY:
        logger.warning("⚠️  OPENAI_API_KEY not set - calls will fail")
    if not OPENAI_PROJECT_ID:
        logger.warning("⚠️  OPENAI_PROJECT_ID not set - needed for SIP config")
    
    logger.info(f"🎙️  Starting OpenAI Voice Server")
    logger.info(f"   Agent: {AGENT_CONFIG['name']}")
    logger.info(f"   Voice: {AGENT_CONFIG['voice']}")
    logger.info(f"   Port: {PORT}")
    
    if OPENAI_PROJECT_ID:
        logger.info(f"   SIP URI: sip:{OPENAI_PROJECT_ID}@sip.api.openai.com;transport=tls")
    
    # Outbound calling status
    if twilio_client:
        logger.info(f"📞 Outbound calling: ENABLED")
        if TWILIO_PHONE_NUMBER:
            logger.info(f"   Default caller ID: {TWILIO_PHONE_NUMBER}")
        else:
            logger.warning("⚠️  TWILIO_PHONE_NUMBER not set - caller ID required per call")
    else:
        logger.info(f"📞 Outbound calling: DISABLED (configure Twilio to enable)")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT)
