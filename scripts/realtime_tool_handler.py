#!/usr/bin/env python3
"""
Realtime Tool Handler - Handle function calls from OpenAI Realtime sessions.

This module manages WebSocket connections to OpenAI Realtime sessions
to receive and process function calls, executing them via OpenClaw.

User context (timezone, location) is resolved from the caller's phone number
and passed to the OpenClaw executor so tools return correct results.

Architecture:
    Voice Call -> OpenAI Realtime -> Function Call Event
                        |
                        v (WebSocket)
                Tool Handler -> User Context -> OpenClaw Executor -> Result
                        |
                        v (WebSocket)
                Function Result -> OpenAI Realtime -> Voice Response
"""

import asyncio
import json
import logging
import os
from typing import Dict, Optional, Callable, Any

import websockets
from websockets.exceptions import ConnectionClosed

from openclaw_executor import (
    execute_openclaw_request, 
    execute_openclaw_streaming, 
    set_call_id,
    set_user_context
)

# Import user context resolver for timezone/location lookup
try:
    from user_context import get_user_context as resolve_user_context, UserContextResolver
    USER_CONTEXT_AVAILABLE = True
except ImportError:
    USER_CONTEXT_AVAILABLE = False
    def resolve_user_context(phone): return {}

# Import call context store for retrieving caller phone from shared storage
try:
    from call_context_store import get_user_phone as get_stored_user_phone
    CALL_CONTEXT_STORE_AVAILABLE = True
except ImportError:
    CALL_CONTEXT_STORE_AVAILABLE = False
    def get_stored_user_phone(call_id): return None

logger = logging.getLogger(__name__)

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime"

# Exponential backoff configuration
INITIAL_RECONNECT_DELAY = 0.5  # Start at 500ms
MAX_RECONNECT_DELAY = 30  # Cap at 30 seconds
MAX_RECONNECT_ATTEMPTS = 10  # Allow more attempts with backoff


class RealtimeToolHandler:
    """
    Handle tool/function calls for an OpenAI Realtime session.
    
    Connects via WebSocket to receive function call events and
    responds with results from the OpenClaw agent.
    
    User context (timezone, location) is resolved from the caller's phone
    number and passed to tools for accurate time/location responses.
    """
    
    def __init__(
        self,
        session_id: str,
        call_id: str,
        model: str = "gpt-4o-realtime-preview",
        on_status_change: Optional[Callable[[str, str], None]] = None,
        caller_phone: Optional[str] = None
    ):
        """
        Initialize handler for a specific session.
        
        Args:
            session_id: The Realtime session ID to connect to
            call_id: Our internal call ID for tracking
            model: The model being used for this session
            on_status_change: Callback for status updates
            caller_phone: Caller's phone number for context resolution (E.164 format)
        """
        self.session_id = session_id
        self.call_id = call_id
        self.model = model
        self.on_status_change = on_status_change
        self.caller_phone = caller_phone
        self.ws = None
        self.running = False
        self.stats = {
            "function_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0
        }
        
        # Resolve user context from phone number
        self.user_context = self._resolve_user_context()
    
    def _resolve_user_context(self) -> Dict[str, Any]:
        """
        Resolve user context (timezone, location, name) from caller phone.
        
        Tries multiple sources for the phone number:
        1. Directly passed caller_phone parameter
        2. Call context store (populated by webhook-server)
        
        Returns empty dict if phone not available or context unavailable.
        """
        # Try to get phone from direct parameter or call context store
        phone = self.caller_phone
        
        if not phone and CALL_CONTEXT_STORE_AVAILABLE:
            # Try to retrieve from shared call context store
            phone = get_stored_user_phone(self.call_id)
            if phone:
                self.caller_phone = phone  # Cache for later use
                logger.info(f"[call_id={self.call_id}] Retrieved user phone from context store: {phone}")
        
        if not phone:
            logger.debug(f"[call_id={self.call_id}] No caller phone available - using empty context")
            return {}
        
        if not USER_CONTEXT_AVAILABLE:
            logger.warning(f"[call_id={self.call_id}] User context module not available")
            return {"phone": phone}  # Return phone even if we can't resolve timezone
        
        try:
            context = resolve_user_context(phone)
            if context:
                logger.info(
                    f"[call_id={self.call_id}] Resolved user context for {phone}: "
                    f"timezone={context.get('timezone')}, location={context.get('location')}, "
                    f"name={context.get('name')}"
                )
            return context
        except Exception as e:
            logger.error(f"[call_id={self.call_id}] Error resolving user context: {e}")
            return {"phone": phone}
    
    async def connect(self) -> bool:
        """
        Connect to the Realtime session via WebSocket sideband.
        
        Uses ?call_id= to connect to the existing call's control channel,
        NOT ?model= which would create a new empty session.
        
        Returns:
            True if connected successfully
        """
        if not OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY not set - cannot connect to Realtime")
            return False
        
        # CRITICAL: Connect to the call's sideband using call_id, not model
        # Using ?model= creates a NEW session; ?call_id= joins the existing call
        url = f"{OPENAI_REALTIME_URL}?call_id={self.call_id}"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            # Note: OpenAI-Beta header not needed for GA API
        }
        
        try:
            print(f"[TOOL_HANDLER] Attempting sideband connection to: {url}")
            self.ws = await websockets.connect(
                url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=10
            )
            
            print(f"[TOOL_HANDLER] ✅ Connected to Realtime session for call {self.call_id}")
            logger.info(f"Connected to Realtime session for call {self.call_id}")
            self._notify_status("connected")
            return True
            
        except Exception as e:
            print(f"[TOOL_HANDLER] ❌ Failed to connect: {type(e).__name__}: {e}")
            logger.error(f"Failed to connect to Realtime: {e}")
            self._notify_status("connection_failed")
            return False
    
    async def start(self):
        """
        Start handling events for this session.
        
        This runs until the session ends or connection is lost.
        Uses exponential backoff for reconnection attempts.
        """
        self.running = True
        reconnect_attempts = 0
        
        while self.running:
            try:
                if not self.ws or self.ws.state != websockets.State.OPEN:
                    if reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                        logger.error(f"[call_id={self.call_id}] Max reconnect attempts ({MAX_RECONNECT_ATTEMPTS}) reached, giving up")
                        break
                    
                    connected = await self.connect()
                    if not connected:
                        reconnect_attempts += 1
                        delay = self._get_backoff_delay(reconnect_attempts)
                        logger.warning(
                            f"[call_id={self.call_id}] Connection attempt {reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS} failed, "
                            f"retrying in {delay:.1f}s (exponential backoff)"
                        )
                        await asyncio.sleep(delay)
                        continue
                    
                    if reconnect_attempts > 0:
                        logger.info(f"[call_id={self.call_id}] Reconnected successfully after {reconnect_attempts} attempts")
                    reconnect_attempts = 0
                
                # Listen for events
                await self._handle_events()
                
            except ConnectionClosed as e:
                reconnect_attempts += 1
                delay = self._get_backoff_delay(reconnect_attempts)
                logger.warning(
                    f"[call_id={self.call_id}] WebSocket closed (code={e.code}, reason={e.reason}), "
                    f"attempt {reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS}, retrying in {delay:.1f}s"
                )
                if self.running:
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                reconnect_attempts += 1
                delay = self._get_backoff_delay(reconnect_attempts)
                logger.error(
                    f"[call_id={self.call_id}] Unexpected error in tool handler: {type(e).__name__}: {e}, "
                    f"attempt {reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS}, retrying in {delay:.1f}s"
                )
                if self.running:
                    await asyncio.sleep(delay)
        
        self._notify_status("stopped")
        logger.info(f"[call_id={self.call_id}] Tool handler stopped. Stats: {self.stats}")
    
    def _get_backoff_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay with jitter.
        
        Formula: min(MAX_DELAY, INITIAL_DELAY * 2^(attempt-1)) + random jitter
        """
        import random
        base_delay = INITIAL_RECONNECT_DELAY * (2 ** (attempt - 1))
        capped_delay = min(base_delay, MAX_RECONNECT_DELAY)
        # Add 10% jitter to prevent thundering herd
        jitter = capped_delay * 0.1 * random.random()
        return capped_delay + jitter
    
    async def stop(self):
        """Stop the handler and close the connection."""
        self.running = False
        if self.ws and self.ws.state == websockets.State.OPEN:
            await self.ws.close()
    
    async def _handle_events(self):
        """Process incoming events from the Realtime session."""
        async for message in self.ws:
            try:
                event = json.loads(message)
                event_type = event.get("type", "")
                
                # Log important events
                if event_type.startswith("response."):
                    logger.debug(f"[call_id={self.call_id}] Realtime event: {event_type}")
                
                # Handle function call completion
                if event_type == "response.function_call_arguments.done":
                    await self._handle_function_call(event)
                
                # Handle session end
                elif event_type == "session.closed":
                    logger.info(f"[call_id={self.call_id}] Session closed by server")
                    self.running = False
                    break
                
                # Handle errors
                elif event_type == "error":
                    error = event.get("error", {})
                    error_code = error.get("code", "unknown")
                    error_msg = error.get("message", "Unknown error")
                    logger.error(f"[call_id={self.call_id}] Realtime API error (code={error_code}): {error_msg}")
                    
            except json.JSONDecodeError:
                logger.warning(f"[call_id={self.call_id}] Invalid JSON from Realtime: {message[:100]}")
            except Exception as e:
                logger.error(f"[call_id={self.call_id}] Error processing event: {type(e).__name__}: {e}")
    
    async def _handle_function_call(self, event: Dict[str, Any]):
        """
        Handle a function call from the Realtime session.
        
        Executes the function via OpenClaw with streaming support.
        Chunks are sent progressively so the user hears responses quickly.
        
        CRITICAL: This method MUST send a response to the user in all cases.
        An unhandled exception here would leave the voice call hanging.
        
        User context (timezone, location) is set before execution so that
        tools return results appropriate for the caller.
        """
        function_call_id = event.get("call_id")  # OpenAI function call ID
        name = event.get("name", "")
        arguments_str = event.get("arguments", "{}")
        
        # Set call_id for error tracking in executor logs
        set_call_id(self.call_id)
        
        # Set user context for this call (timezone, location)
        # This ensures tools like time/weather use the correct context
        set_user_context(self.user_context)
        
        self.stats["function_calls"] += 1
        logger.info(f"[call_id={self.call_id}] Function call received: {name} (function_call_id: {function_call_id})")
        
        # Wrap ENTIRE function call handling in try/except to guarantee we always respond
        try:
            try:
                arguments = json.loads(arguments_str)
            except json.JSONDecodeError:
                logger.warning(f"[call_id={self.call_id}] Invalid JSON arguments: {arguments_str[:100]}")
                arguments = {}
            
            # Try streaming execution for ask_openclaw
            if name == "ask_openclaw":
                request = arguments.get("request", "")
                if not request:
                    logger.warning(f"[call_id={self.call_id}] ask_openclaw called with empty request")
                    await self._send_function_result_safe(
                        function_call_id, 
                        "I didn't receive a specific request. What would you like me to do?"
                    )
                    return
                
                try:
                    await self._execute_streaming_function(function_call_id, request)
                    return
                except Exception as e:
                    logger.warning(f"[call_id={self.call_id}] Streaming execution failed, falling back to non-streaming: {type(e).__name__}: {e}")
                    # Fall through to non-streaming execution
            
            # Non-streaming fallback
            result = await self._execute_function(name, arguments)
            await self._send_function_result_safe(function_call_id, result)
            
        except Exception as e:
            # Last resort: catch ANY exception and send a graceful error response
            logger.error(f"[call_id={self.call_id}] Critical error in function call handler: {type(e).__name__}: {e}")
            self.stats["failed_calls"] += 1
            
            # Try to send an error response - if this also fails, log it but don't re-raise
            await self._send_function_result_safe(
                function_call_id,
                "I'm sorry, I ran into an unexpected error. Please try again."
            )
    
    async def _execute_function(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a function and return the result (non-streaming fallback).
        
        Currently only supports ask_openclaw, but can be extended.
        
        This method ALWAYS returns a string (never raises). Errors are caught
        and converted to user-friendly error messages.
        """
        try:
            if name == "ask_openclaw":
                request = arguments.get("request", "")
                if not request:
                    return "I didn't receive a specific request. What would you like me to do?"
                
                logger.info(f"[call_id={self.call_id}] Executing OpenClaw request (non-streaming): {request[:80]}...")
                
                try:
                    result = await execute_openclaw_request(request)
                    
                    # Validate result
                    if not result or not isinstance(result, str):
                        logger.warning(f"[call_id={self.call_id}] Empty or invalid result from executor")
                        self.stats["failed_calls"] += 1
                        return "I processed your request but didn't get a response. Please try again."
                    
                    self.stats["successful_calls"] += 1
                    return result
                    
                except asyncio.TimeoutError:
                    logger.error(f"[call_id={self.call_id}] OpenClaw request timed out")
                    self.stats["failed_calls"] += 1
                    return "That request took too long. Could you try asking in a simpler way?"
                    
                except Exception as exec_error:
                    logger.error(f"[call_id={self.call_id}] OpenClaw execution error: {type(exec_error).__name__}: {exec_error}")
                    self.stats["failed_calls"] += 1
                    return "I ran into a problem processing that request. Let me know if you'd like to try again."
            
            else:
                logger.warning(f"[call_id={self.call_id}] Unknown function: {name}")
                self.stats["failed_calls"] += 1
                return f"I don't know how to handle the '{name}' function."
                
        except Exception as e:
            # Catch-all for any unexpected errors
            logger.error(f"[call_id={self.call_id}] Unexpected function execution error: {type(e).__name__}: {e}")
            self.stats["failed_calls"] += 1
            return "I'm sorry, something unexpected went wrong. Please try again."
    
    async def _execute_streaming_function(self, function_call_id: str, request: str):
        """
        Execute ask_openclaw with streaming, sending chunks progressively.
        
        Each chunk is sent as a function_call_output (first chunk) or 
        follow-up message (subsequent chunks), with response.create triggered
        so the user hears each chunk immediately.
        
        Args:
            function_call_id: The OpenAI function call ID for the response
            request: The user's request to process
            
        Raises:
            Exception: Propagated on critical failure (caller should fall back to non-streaming)
        """
        logger.info(f"[call_id={self.call_id}] Executing streaming request: {request[:80]}...")
        
        chunk_count = 0
        first_chunk_sent = False
        
        try:
            async for chunk in execute_openclaw_streaming(request):
                if not chunk or not chunk.strip():
                    continue
                
                chunk = chunk.strip()
                chunk_count += 1
                
                logger.debug(f"[call_id={self.call_id}] Streaming chunk {chunk_count}: {len(chunk)} chars")
                
                try:
                    if chunk_count == 1:
                        # First chunk: send as function_call_output (completes the function call)
                        await self._send_function_result(function_call_id, chunk)
                        first_chunk_sent = True
                    else:
                        # Subsequent chunks: send as follow-up content
                        await self._send_followup_chunk(chunk)
                except Exception as send_error:
                    # Log send error but continue streaming - connection may recover
                    logger.warning(f"[call_id={self.call_id}] Failed to send chunk {chunk_count}: {type(send_error).__name__}: {send_error}")
                    # If we couldn't send the first chunk, re-raise to trigger fallback
                    if chunk_count == 1 and not first_chunk_sent:
                        raise
            
            if chunk_count == 0:
                # No chunks yielded - send a default response
                logger.warning(f"[call_id={self.call_id}] Streaming yielded no chunks")
                await self._send_function_result(function_call_id, "Done.")
                self.stats["failed_calls"] += 1
            else:
                logger.info(f"[call_id={self.call_id}] Streaming complete: {chunk_count} chunks sent")
                self.stats["successful_calls"] += 1
                
        except Exception as e:
            logger.error(f"[call_id={self.call_id}] Streaming execution error: {type(e).__name__}: {e}")
            
            # If we already sent the first chunk, the function call is "complete" from Realtime's perspective
            # Send a graceful error message as follow-up
            if first_chunk_sent:
                try:
                    await self._send_followup_chunk("I'm sorry, I encountered an error while processing. Let me try again if you ask.")
                except Exception:
                    pass  # Best effort
                self.stats["failed_calls"] += 1
            else:
                # No chunks sent yet - re-raise to trigger fallback to non-streaming
                raise
    
    async def _send_followup_chunk(self, chunk: str):
        """
        Send a follow-up chunk after the initial function result.
        
        Sends as an assistant message item, then triggers response.create
        so the model speaks it.
        """
        if not self.ws or self.ws.state != websockets.State.OPEN:
            logger.warning(f"[call_id={self.call_id}] Cannot send followup chunk - WebSocket closed")
            return
        
        try:
            # Send as an assistant message item for natural continuation
            await self.ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": chunk
                        }
                    ]
                }
            }))
            
            # Trigger response generation to speak this chunk
            await self.ws.send(json.dumps({
                "type": "response.create"
            }))
            
            logger.debug(f"[call_id={self.call_id}] Follow-up chunk sent ({len(chunk)} chars)")
            
        except Exception as e:
            logger.error(f"[call_id={self.call_id}] Failed to send follow-up chunk: {type(e).__name__}: {e}")
            raise
    
    async def _send_function_result(self, function_call_id: str, result: str):
        """
        Send function result back to the Realtime session.
        
        Raises exception on failure - use _send_function_result_safe for guaranteed no-throw.
        """
        # websockets 16.0+ uses 'state' instead of 'closed'
        import websockets
        if not self.ws or self.ws.state != websockets.State.OPEN:
            logger.warning(f"[call_id={self.call_id}] Cannot send function result - WebSocket closed")
            return
        
        try:
            # Create function call output
            await self.ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": function_call_id,
                    "output": result
                }
            }))
            
            # Trigger response generation to speak the result
            await self.ws.send(json.dumps({
                "type": "response.create"
            }))
            
            logger.info(f"[call_id={self.call_id}] Function result sent ({len(result)} chars)")
            
        except Exception as e:
            logger.error(f"[call_id={self.call_id}] Failed to send function result: {type(e).__name__}: {e}")
            raise
    
    async def _send_function_result_safe(self, function_call_id: str, result: str):
        """
        Send function result back to the Realtime session (no-throw version).
        
        This method catches all exceptions and logs them, guaranteeing it won't
        raise. Use this in error handlers to avoid cascading failures.
        """
        try:
            await self._send_function_result(function_call_id, result)
        except Exception as e:
            # Log but don't raise - this is a last-resort send attempt
            logger.error(f"[call_id={self.call_id}] Failed to send function result (safe): {type(e).__name__}: {e}")
    
    def _notify_status(self, status: str):
        """Notify status change callback if configured."""
        if self.on_status_change:
            try:
                self.on_status_change(self.call_id, status)
            except Exception as e:
                logger.warning(f"Status callback error: {e}")


# Active handlers tracking
active_handlers: Dict[str, RealtimeToolHandler] = {}


async def start_tool_handler(
    call_id: str,
    session_id: str,
    model: str = "gpt-4o-realtime-preview",
    caller_phone: Optional[str] = None
) -> Optional[RealtimeToolHandler]:
    """
    Start a tool handler for a call session.
    
    Args:
        call_id: The call ID to track
        session_id: The Realtime session ID
        model: The model being used
        caller_phone: Caller's phone number (E.164 format) for context resolution.
                     This is used to determine timezone and location for tool calls.
        
    Returns:
        The handler if started successfully, None otherwise
    """
    # Clean up any existing handler for this call
    if call_id in active_handlers:
        await active_handlers[call_id].stop()
    
    handler = RealtimeToolHandler(
        session_id=session_id,
        call_id=call_id,
        model=model,
        on_status_change=lambda cid, status: logger.info(f"Handler {cid}: {status}"),
        caller_phone=caller_phone
    )
    
    # Start in background
    asyncio.create_task(handler.start())
    active_handlers[call_id] = handler
    
    logger.info(f"Tool handler started for call {call_id}")
    return handler


async def stop_tool_handler(call_id: str):
    """Stop the tool handler for a call."""
    if call_id in active_handlers:
        await active_handlers[call_id].stop()
        del active_handlers[call_id]
        logger.info(f"Tool handler stopped for call {call_id}")


def get_active_handlers() -> Dict[str, Dict[str, Any]]:
    """Get status of all active handlers."""
    return {
        call_id: {
            "session_id": handler.session_id,
            "running": handler.running,
            "stats": handler.stats
        }
        for call_id, handler in active_handlers.items()
    }


# Cleanup on module exit
import atexit

def _cleanup():
    """Cleanup all handlers on exit."""
    for handler in active_handlers.values():
        handler.running = False

atexit.register(_cleanup)
