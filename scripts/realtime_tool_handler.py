#!/usr/bin/env python3
"""
Realtime Tool Handler - Handle function calls from OpenAI Realtime sessions.

This module manages WebSocket connections to OpenAI Realtime sessions
to receive and process function calls, executing them via OpenClaw.

Architecture:
    Voice Call -> OpenAI Realtime -> Function Call Event
                        |
                        v (WebSocket)
                Tool Handler -> OpenClaw Executor -> Result
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

from openclaw_executor import execute_openclaw_request, execute_openclaw_streaming

logger = logging.getLogger(__name__)

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime"
RECONNECT_DELAY = 2  # seconds
MAX_RECONNECT_ATTEMPTS = 3


class RealtimeToolHandler:
    """
    Handle tool/function calls for an OpenAI Realtime session.
    
    Connects via WebSocket to receive function call events and
    responds with results from the OpenClaw agent.
    """
    
    def __init__(
        self,
        session_id: str,
        call_id: str,
        model: str = "gpt-4o-realtime-preview",
        on_status_change: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialize handler for a specific session.
        
        Args:
            session_id: The Realtime session ID to connect to
            call_id: Our internal call ID for tracking
            model: The model being used for this session
            on_status_change: Callback for status updates
        """
        self.session_id = session_id
        self.call_id = call_id
        self.model = model
        self.on_status_change = on_status_change
        self.ws = None
        self.running = False
        self.stats = {
            "function_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0
        }
    
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
        """
        self.running = True
        reconnect_attempts = 0
        
        while self.running:
            try:
                if not self.ws or self.ws.closed:
                    if reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                        logger.warning(f"Max reconnect attempts reached for call {self.call_id}")
                        break
                    
                    connected = await self.connect()
                    if not connected:
                        reconnect_attempts += 1
                        await asyncio.sleep(RECONNECT_DELAY)
                        continue
                    
                    reconnect_attempts = 0
                
                # Listen for events
                await self._handle_events()
                
            except ConnectionClosed as e:
                logger.info(f"WebSocket closed for call {self.call_id}: {e}")
                if self.running:
                    reconnect_attempts += 1
                    await asyncio.sleep(RECONNECT_DELAY)
                    
            except Exception as e:
                logger.error(f"Error in tool handler for call {self.call_id}: {e}")
                if self.running:
                    await asyncio.sleep(RECONNECT_DELAY)
        
        self._notify_status("stopped")
        logger.info(f"Tool handler stopped for call {self.call_id}: {self.stats}")
    
    async def stop(self):
        """Stop the handler and close the connection."""
        self.running = False
        if self.ws and not self.ws.closed:
            await self.ws.close()
    
    async def _handle_events(self):
        """Process incoming events from the Realtime session."""
        async for message in self.ws:
            try:
                event = json.loads(message)
                event_type = event.get("type", "")
                
                # Log important events
                if event_type.startswith("response."):
                    logger.debug(f"Realtime event: {event_type}")
                
                # Handle function call completion
                if event_type == "response.function_call_arguments.done":
                    await self._handle_function_call(event)
                
                # Handle session end
                elif event_type == "session.closed":
                    logger.info(f"Session closed for call {self.call_id}")
                    self.running = False
                    break
                
                # Handle errors
                elif event_type == "error":
                    error = event.get("error", {})
                    logger.error(f"Realtime error: {error.get('message', 'Unknown error')}")
                    
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from Realtime: {message[:100]}")
            except Exception as e:
                logger.error(f"Error processing Realtime event: {e}")
    
    async def _handle_function_call(self, event: Dict[str, Any]):
        """
        Handle a function call from the Realtime session.
        
        Executes the function via OpenClaw with streaming support.
        Chunks are sent progressively so the user hears responses quickly.
        """
        call_id = event.get("call_id")
        name = event.get("name", "")
        arguments_str = event.get("arguments", "{}")
        
        self.stats["function_calls"] += 1
        logger.info(f"Function call received: {name} (call_id: {call_id})")
        
        try:
            arguments = json.loads(arguments_str)
        except json.JSONDecodeError:
            arguments = {}
        
        # Try streaming execution for ask_openclaw
        if name == "ask_openclaw":
            request = arguments.get("request", "")
            if not request:
                await self._send_function_result(
                    call_id, 
                    "I didn't receive a specific request. What would you like me to do?"
                )
                return
            
            try:
                await self._execute_streaming_function(call_id, request)
                return
            except Exception as e:
                logger.warning(f"Streaming execution failed, falling back to non-streaming: {e}")
                # Fall through to non-streaming execution
        
        # Non-streaming fallback
        result = await self._execute_function(name, arguments)
        await self._send_function_result(call_id, result)
    
    async def _execute_function(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a function and return the result (non-streaming fallback).
        
        Currently only supports ask_openclaw, but can be extended.
        """
        try:
            if name == "ask_openclaw":
                request = arguments.get("request", "")
                if not request:
                    return "I didn't receive a specific request. What would you like me to do?"
                
                logger.info(f"Executing OpenClaw request (non-streaming): {request[:80]}...")
                result = await execute_openclaw_request(request)
                
                self.stats["successful_calls"] += 1
                return result
            
            else:
                logger.warning(f"Unknown function: {name}")
                self.stats["failed_calls"] += 1
                return f"I don't know how to handle the '{name}' function."
                
        except Exception as e:
            logger.error(f"Function execution error: {e}")
            self.stats["failed_calls"] += 1
            return "I ran into an error processing that request. Please try again."
    
    async def _execute_streaming_function(self, call_id: str, request: str):
        """
        Execute ask_openclaw with streaming, sending chunks progressively.
        
        Each chunk is sent as a function_call_output (first chunk) or 
        follow-up message (subsequent chunks), with response.create triggered
        so the user hears each chunk immediately.
        
        Args:
            call_id: The function call ID from the Realtime session
            request: The user's request to process
        """
        logger.info(f"Executing OpenClaw request (streaming): {request[:80]}...")
        
        chunk_count = 0
        
        async for chunk in execute_openclaw_streaming(request):
            if not chunk or not chunk.strip():
                continue
            
            chunk = chunk.strip()
            chunk_count += 1
            
            logger.info(f"Streaming chunk {chunk_count}: {len(chunk)} chars")
            
            if chunk_count == 1:
                # First chunk: send as function_call_output (completes the function call)
                await self._send_function_result(call_id, chunk)
            else:
                # Subsequent chunks: send as follow-up content
                await self._send_followup_chunk(chunk)
        
        if chunk_count == 0:
            # No chunks yielded - send a default response
            logger.warning("Streaming yielded no chunks")
            await self._send_function_result(call_id, "Done.")
            self.stats["failed_calls"] += 1
        else:
            logger.info(f"Streaming complete: {chunk_count} chunks sent")
            self.stats["successful_calls"] += 1
    
    async def _send_followup_chunk(self, chunk: str):
        """
        Send a follow-up chunk after the initial function result.
        
        Sends as a function_call_output with a generated call_id,
        then triggers response.create so the model speaks it.
        """
        import websockets
        if not self.ws or self.ws.state != websockets.State.OPEN:
            logger.warning("Cannot send followup chunk - WebSocket closed")
            return
        
        try:
            # Generate a unique call_id for this continuation
            import uuid
            continuation_id = f"cont_{uuid.uuid4().hex[:8]}"
            
            # Send as an assistant message item for natural continuation
            await self.ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "input_text",
                            "text": chunk
                        }
                    ]
                }
            }))
            
            # Trigger response generation to speak this chunk
            await self.ws.send(json.dumps({
                "type": "response.create"
            }))
            
            logger.debug(f"Follow-up chunk sent ({len(chunk)} chars)")
            
        except Exception as e:
            logger.error(f"Failed to send follow-up chunk: {e}")
            raise
    
    async def _send_function_result(self, call_id: str, result: str):
        """Send function result back to the Realtime session."""
        # websockets 16.0+ uses 'state' instead of 'closed'
        import websockets
        if not self.ws or self.ws.state != websockets.State.OPEN:
            logger.warning("Cannot send function result - WebSocket closed")
            return
        
        try:
            # Create function call output
            await self.ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": result
                }
            }))
            
            # Trigger response generation to speak the result
            await self.ws.send(json.dumps({
                "type": "response.create"
            }))
            
            logger.info(f"Function result sent ({len(result)} chars)")
            
        except Exception as e:
            logger.error(f"Failed to send function result: {e}")
    
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
    model: str = "gpt-4o-realtime-preview"
) -> Optional[RealtimeToolHandler]:
    """
    Start a tool handler for a call session.
    
    Args:
        call_id: The call ID to track
        session_id: The Realtime session ID
        model: The model being used
        
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
        on_status_change=lambda cid, status: logger.info(f"Handler {cid}: {status}")
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
