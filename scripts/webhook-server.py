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
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import httpx
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import uvicorn
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioException
from twilio.request_validator import RequestValidator

# Import call recording functionality
from call_recording import recording_manager, CallRecord, TranscriptEntry

# Import function calling functionality
from function_calling import function_manager, FunctionResult

# Import session memory functionality
from session_memory import memory_manager, SessionContext, MemoryEntry

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

# Track active calls
active_calls: dict[str, dict] = {}

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
    """Validate phone number format (E.164) with stricter validation."""
    if not phone:
        return False
    
    # Reject common attack patterns
    if len(phone) > 20:  # Unreasonably long
        return False
    if phone.count('+') > 1:  # Multiple plus signs
        return False
    if any(char in phone for char in ['<', '>', '"', "'", '&', ';']):  # Injection chars
        return False
    
    # Stricter E.164 validation with country code validation
    # Must start with +, followed by 1-3 digit country code, then 4-14 digits
    pattern = r'^\+([1-9]\d{0,2})(\d{4,14})$'
    match = re.match(pattern, phone)
    
    if not match:
        return False
    
    country_code = match.group(1)
    number_part = match.group(2)
    
    # Validate common country codes and total length
    total_digits = len(country_code) + len(number_part)
    if total_digits < 7 or total_digits > 15:
        return False
    
    # Reject obviously invalid patterns
    if number_part == '0' * len(number_part):  # All zeros
        return False
    if number_part == '1' * len(number_part):  # All ones  
        return False
    
    # Additional validation for common patterns
    if len(country_code) == 1 and country_code == '1':  # US/Canada
        # Must be exactly 10 digits for US/Canada
        if len(number_part) != 10:
            return False
        # Area code can't start with 0 or 1
        if number_part[0] in ['0', '1']:
            return False
        # Exchange code can't start with 0 or 1
        if number_part[3] in ['0', '1']:
            return False
        return True
    elif len(country_code) == 2:  # Most European/international
        return 4 <= len(number_part) <= 12
    elif len(country_code) == 3:  # Some international
        return 4 <= len(number_part) <= 10
    
    return True


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
        
        logger.info(f"Initiating outbound call: {mask_phone_number(request.to)} via {sip_uri}")
        
        # Create Twilio call
        call = twilio_client.calls.create(
            to=request.to,
            from_=from_number,
            url=sip_uri,
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
        
        # Accept the call in background (don't block webhook response)
        background_tasks.add_task(accept_call, call_id, from_header)
        
        return JSONResponse({"status": "accepted", "call_id": call_id})
    
    elif event_type == "realtime.call.ended":
        call_data = event.get("data", {})
        call_id = call_data.get("call_id")
        
        # End call recording
        background_tasks.add_task(
            recording_manager.end_call_recording,
            call_id, "completed"
        )
        
        if call_id in active_calls:
            duration = time.time() - active_calls[call_id].get("started_at", time.time())
            logger.info(f"Call ended: {call_id} (duration: {duration:.1f}s)")
            del active_calls[call_id]
        
        return JSONResponse({"status": "noted"})
    
    elif event_type == "realtime.conversation.item.created":
        # Handle conversation items (including function calls)
        call_data = event.get("data", {})
        call_id = call_data.get("call_id")
        item = call_data.get("item", {})
        
        # Add to transcript if it's a message
        if item.get("type") == "message" and call_id:
            role = item.get("role", "unknown")
            content_items = item.get("content", [])
            
            for content_item in content_items:
                if content_item.get("type") == "text":
                    text = content_item.get("text", "")
                    await recording_manager.add_transcript_entry(
                        call_id=call_id,
                        speaker="assistant" if role == "assistant" else "user",
                        content=text,
                        event_type="conversation_message"
                    )
                    
                    # Add assistant responses to memory
                    if role == "assistant" and len(text.strip()) > 10:
                        # Get caller number from active calls
                        caller_info = active_calls.get(call_id)
                        if caller_info and caller_info.get("caller"):
                            caller = caller_info["caller"]
                            session_id = memory_manager._get_session_id(caller)
                            
                            # Add assistant message to memory
                            await memory_manager.add_memory_entry(
                                session_id=session_id,
                                entry_type="conversation",
                                content=f"Assistant responded: {text}",
                                importance=2,  # Lower importance for responses
                                metadata={"call_id": call_id, "type": "assistant_message"}
                            )
        
        return JSONResponse({"status": "noted"})
    
    elif event_type == "realtime.conversation.item.input_audio_transcription.completed":
        # Handle user speech transcription
        call_data = event.get("data", {})
        call_id = call_data.get("call_id")
        transcript = call_data.get("transcript", "")
        
        if call_id and transcript:
            await recording_manager.add_transcript_entry(
                call_id=call_id,
                speaker="user",
                content=transcript,
                event_type="speech_transcription"
            )
            
            # Add to session memory if significant
            if len(transcript.strip()) > 10:  # Only add substantial messages
                # Get caller number from active calls
                caller_info = active_calls.get(call_id)
                if caller_info and caller_info.get("caller"):
                    caller = caller_info["caller"]
                    session_id = memory_manager._get_session_id(caller)
                    
                    # Add user message to memory
                    await memory_manager.add_memory_entry(
                        session_id=session_id,
                        entry_type="conversation",
                        content=f"User said: {transcript}",
                        importance=3,  # Normal importance
                        metadata={"call_id": call_id, "type": "user_message"}
                    )
        
        return JSONResponse({"status": "noted"})
    
    elif event_type == "realtime.function_call_request":
        # Handle function call requests from the assistant
        call_data = event.get("data", {})
        call_id = call_data.get("call_id")
        function_call_id = call_data.get("call_id")  # Function call specific ID
        function_name = call_data.get("name")
        arguments_json = call_data.get("arguments", "{}")
        
        if not call_id or not function_name:
            logger.error(f"Invalid function call request: missing call_id or function_name")
            return JSONResponse({"status": "error", "message": "Invalid function call request"})
        
        try:
            arguments = json.loads(arguments_json) if arguments_json else {}
        except json.JSONDecodeError:
            logger.error(f"Invalid function arguments JSON: {arguments_json}")
            return JSONResponse({"status": "error", "message": "Invalid function arguments"})
        
        # Execute function in background and send result back to OpenAI
        background_tasks.add_task(
            execute_and_send_function_result,
            call_id, function_call_id, function_name, arguments
        )
        
        return JSONResponse({"status": "accepted"})
    
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
    
    # Get or create session context for this caller
    session = await memory_manager.get_or_create_session(caller, call_id)
    
    # Build agent instructions with session context
    base_instructions = AGENT_CONFIG["instructions"]
    session_context = memory_manager.get_context_for_agent(session)
    
    enhanced_instructions = base_instructions
    if session_context:
        enhanced_instructions = f"{base_instructions}\n\nContext from previous conversations:\n{session_context}"
    
    # Get function definitions for this session
    function_definitions = function_manager.get_openai_function_definitions()
    
    payload = {
        "type": "realtime",
        "model": AGENT_CONFIG["model"],
        "instructions": enhanced_instructions,
        "voice": AGENT_CONFIG["voice"],
        # Optional: add tools, turn detection settings, etc.
    }
    
    # Add function definitions if available
    if function_definitions:
        payload["tools"] = [
            {
                "type": "function",
                "function": func_def
            }
            for func_def in function_definitions
        ]
        logger.info(f"Added {len(function_definitions)} functions to call session")
    
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


async def execute_and_send_function_result(call_id: str, function_call_id: str, 
                                         function_name: str, arguments: Dict[str, Any]):
    """
    Execute a function call and send the result back to OpenAI.
    """
    logger.info(f"Executing function {function_name} for call {call_id}")
    
    # Execute the function
    result = await function_manager.execute_function(call_id, function_name, arguments)
    
    # Log the function call to transcript
    await recording_manager.add_transcript_entry(
        call_id=call_id,
        speaker="system",
        content=f"Function call: {function_name}({json.dumps(arguments)}) -> {result.result if result.success else result.error}",
        event_type="function_call",
        metadata={
            "function_name": function_name,
            "arguments": arguments,
            "success": result.success,
            "execution_time": result.execution_time
        }
    )
    
    # Add function call to session memory
    caller_info = active_calls.get(call_id)
    if caller_info and caller_info.get("caller"):
        caller = caller_info["caller"]
        session_id = memory_manager._get_session_id(caller)
        
        # Add function call to memory with high importance
        memory_content = f"Called function {function_name} with args {json.dumps(arguments)}"
        if result.success:
            memory_content += f" -> Success: {str(result.result)[:100]}"
        else:
            memory_content += f" -> Error: {result.error}"
        
        await memory_manager.add_memory_entry(
            session_id=session_id,
            entry_type="function_call",
            content=memory_content,
            importance=6,  # High importance for function calls
            metadata={
                "function_name": function_name,
                "arguments": arguments,
                "success": result.success,
                "call_id": call_id
            }
        )
    
    # Send result back to OpenAI
    url = f"https://api.openai.com/v1/realtime/calls/{call_id}/function_call_output"
    
    payload = {
        "call_id": function_call_id,
        "output": json.dumps(result.result) if result.success else json.dumps({"error": result.error})
    }
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                logger.info(f"Function result sent for {function_name} in call {call_id}")
            else:
                logger.error(f"Failed to send function result: {response.status_code} - {response.text}")
                
    except Exception as e:
        logger.error(f"Error sending function result for call {call_id}: {e}")


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
    Set up OpenAI Realtime session for outbound call.
    
    For outbound calls, we need to wait for the call to be answered
    before setting up the Realtime session. This is typically done
    via webhook events from Twilio.
    """
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set - cannot setup Realtime session")
        return
    
    # For outbound calls, we might need to wait for call answered event
    # This is a simplified version - in production you'd want more sophisticated
    # call state management based on Twilio webhooks
    
    try:
        # Update call status
        if call_id in active_calls:
            active_calls[call_id]["status"] = "setting_up_realtime"
        
        # Create custom instructions for outbound call
        instructions = AGENT_CONFIG["instructions"]
        if initial_message:
            instructions += f"\n\nStart the conversation by saying: {initial_message}"
        
        # Note: For outbound calls, OpenAI might require a different API endpoint
        # or flow. This is a placeholder for the actual implementation
        # which would depend on OpenAI's specific outbound call handling
        
        logger.info(f"Realtime session setup initiated for outbound call {call_id}")
        
        if call_id in active_calls:
            active_calls[call_id]["status"] = "realtime_ready"
            
    except Exception as e:
        logger.error(f"Error setting up Realtime session for call {call_id}: {e}")
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


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "agent": AGENT_CONFIG["name"],
        "active_calls": len(active_calls),
        "config_loaded": CONFIG_PATH.exists()
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

@app.get("/functions")
async def list_available_functions():
    """List all available functions for calling during conversations."""
    function_definitions = function_manager.get_openai_function_definitions()
    
    functions_info = []
    for func_name, func_def in function_manager.functions.items():
        functions_info.append({
            "name": func_name,
            "description": func_def.description,
            "parameters": func_def.parameters,
            "handler_type": "python" if func_def.handler else "openclaw" if func_def.openclaw_tool else "none",
            "openclaw_tool": func_def.openclaw_tool,
            "examples": func_def.examples
        })
    
    return {
        "enabled": function_manager.ENABLE_FUNCTION_CALLING,
        "total_functions": len(functions_info),
        "functions": functions_info
    }

@app.get("/history/{call_id}/functions")
async def get_call_functions(call_id: str):
    """Get function call history for a specific call."""
    function_history = function_manager.get_call_function_history(call_id)
    
    return {
        "call_id": call_id,
        "function_calls": len(function_history),
        "history": function_history
    }

@app.get("/memory/stats")
async def get_memory_stats():
    """Get session memory statistics."""
    return memory_manager.get_memory_stats()

@app.get("/memory/sessions")
async def list_sessions(limit: int = Query(20), offset: int = Query(0)):
    """List session memory entries with pagination."""
    # This is a simplified implementation - in production you'd want proper pagination
    with sqlite3.connect(memory_manager.db_path) as conn:
        cursor = conn.execute('''
            SELECT session_id, caller_number, first_call, last_call, total_calls, summary
            FROM sessions
            ORDER BY last_call DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                "session_id": row[0],
                "caller_number": mask_phone_number(row[1]),
                "first_call": row[2],
                "last_call": row[3],
                "total_calls": row[4],
                "summary": row[5][:100] + "..." if row[5] and len(row[5]) > 100 else row[5]
            })
        
        return {
            "sessions": sessions,
            "limit": limit,
            "offset": offset
        }

@app.get("/memory/sessions/{session_id}")
async def get_session_memory(session_id: str, limit: int = Query(50)):
    """Get memory entries for a specific session."""
    with sqlite3.connect(memory_manager.db_path) as conn:
        # Get session info
        cursor = conn.execute(
            'SELECT caller_number, first_call, last_call, total_calls, summary FROM sessions WHERE session_id = ?',
            (session_id,)
        )
        session_row = cursor.fetchone()
        
        if not session_row:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get memory entries
        cursor = conn.execute('''
            SELECT timestamp, entry_type, content, importance, metadata
            FROM memory_entries
            WHERE session_id = ?
            ORDER BY importance DESC, timestamp DESC
            LIMIT ?
        ''', (session_id, limit))
        
        memories = []
        for row in cursor.fetchall():
            memories.append({
                "timestamp": row[0],
                "entry_type": row[1],
                "content": row[2],
                "importance": row[3],
                "metadata": json.loads(row[4]) if row[4] else None
            })
        
        return {
            "session_id": session_id,
            "caller_number": mask_phone_number(session_row[0]),
            "first_call": session_row[1],
            "last_call": session_row[2],
            "total_calls": session_row[3],
            "summary": session_row[4],
            "memory_entries": memories
        }

@app.delete("/memory/sessions/{session_id}")
async def delete_session_memory(session_id: str):
    """Delete a session and all its memory entries."""
    with sqlite3.connect(memory_manager.db_path) as conn:
        # Check if session exists
        cursor = conn.execute('SELECT COUNT(*) FROM sessions WHERE session_id = ?', (session_id,))
        if cursor.fetchone()[0] == 0:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Delete memory entries
        conn.execute('DELETE FROM memory_entries WHERE session_id = ?', (session_id,))
        
        # Delete session
        conn.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))
        conn.commit()
    
    # Remove from active sessions cache
    if session_id in memory_manager.active_sessions:
        del memory_manager.active_sessions[session_id]
    
    return {"status": "deleted", "session_id": session_id}

@app.post("/memory/cleanup")
async def cleanup_old_memory():
    """Clean up old memory entries based on retention policy."""
    deleted_count = await memory_manager.cleanup_old_sessions()
    return {
        "status": "completed",
        "deleted_sessions": deleted_count
    }

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
