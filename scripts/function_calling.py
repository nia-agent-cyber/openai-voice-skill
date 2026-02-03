#!/usr/bin/env python3
"""
Function Calling Module for OpenAI Voice Skill

Enables AI agents to call external functions during voice conversations.
Supports OpenClaw-style tool integration and custom function definitions.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass
import httpx
import os

logger = logging.getLogger(__name__)

# Configuration
OPENCLAW_API_URL = os.getenv("OPENCLAW_API_URL", "http://localhost:8080")
OPENCLAW_API_KEY = os.getenv("OPENCLAW_API_KEY")
FUNCTION_TIMEOUT_SECONDS = int(os.getenv("FUNCTION_TIMEOUT_SECONDS", "30"))
ENABLE_FUNCTION_CALLING = os.getenv("ENABLE_FUNCTION_CALLING", "true").lower() == "true"

@dataclass
class FunctionResult:
    """Result of a function call."""
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: Optional[float] = None
    
@dataclass
class FunctionDefinition:
    """Definition of a callable function."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema
    handler: Optional[Callable] = None  # Python function handler
    openclaw_tool: Optional[str] = None  # OpenClaw tool name
    examples: Optional[List[str]] = None  # Example usage

class FunctionCallingManager:
    """Manages function calling during voice conversations."""
    
    def __init__(self):
        self.functions: Dict[str, FunctionDefinition] = {}
        self.openclaw_client = None
        self.call_history: Dict[str, List[Dict]] = {}  # Track function calls per conversation
        
        # Initialize OpenClaw client if configured
        if OPENCLAW_API_KEY:
            self.openclaw_client = httpx.AsyncClient(
                base_url=OPENCLAW_API_URL,
                headers={"Authorization": f"Bearer {OPENCLAW_API_KEY}"},
                timeout=FUNCTION_TIMEOUT_SECONDS
            )
        
        # Load default function definitions
        self._load_default_functions()
    
    def _load_default_functions(self):
        """Load default function definitions."""
        
        # Time/Date function
        self.register_function(
            name="get_current_time",
            description="Get the current date and time",
            parameters={
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Timezone (optional, defaults to UTC)",
                        "enum": ["UTC", "EST", "PST", "GMT"]
                    }
                }
            },
            handler=self._get_current_time,
            examples=["What time is it?", "What's the current date?"]
        )
        
        # Weather function (requires OpenClaw integration)
        self.register_function(
            name="get_weather",
            description="Get current weather information for a location",
            parameters={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or ZIP code"
                    }
                },
                "required": ["location"]
            },
            openclaw_tool="weather",
            examples=["What's the weather in New York?", "Is it raining in Seattle?"]
        )
        
        # Calendar function (requires OpenClaw integration)
        self.register_function(
            name="check_calendar",
            description="Check calendar events for today or a specific date",
            parameters={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (optional, defaults to today)"
                    }
                }
            },
            openclaw_tool="calendar",
            examples=["What's on my calendar today?", "Do I have any meetings tomorrow?"]
        )
        
        # Email function (requires OpenClaw integration)
        self.register_function(
            name="send_email",
            description="Send an email message",
            parameters={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject"
                    },
                    "message": {
                        "type": "string",
                        "description": "Email message content"
                    }
                },
                "required": ["to", "subject", "message"]
            },
            openclaw_tool="email",
            examples=["Send an email to John about the meeting", "Email my boss the report"]
        )
        
        logger.info(f"Loaded {len(self.functions)} default functions")
    
    def register_function(self, name: str, description: str, parameters: Dict[str, Any],
                         handler: Optional[Callable] = None, 
                         openclaw_tool: Optional[str] = None,
                         examples: Optional[List[str]] = None):
        """Register a new function definition."""
        if name in self.functions:
            logger.warning(f"Function {name} already registered, overwriting")
        
        self.functions[name] = FunctionDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            openclaw_tool=openclaw_tool,
            examples=examples
        )
        
        logger.info(f"Registered function: {name}")
    
    def get_openai_function_definitions(self) -> List[Dict[str, Any]]:
        """Get function definitions in OpenAI format for session configuration."""
        if not ENABLE_FUNCTION_CALLING:
            return []
        
        definitions = []
        for func in self.functions.values():
            definitions.append({
                "name": func.name,
                "description": func.description,
                "parameters": func.parameters
            })
        
        return definitions
    
    async def execute_function(self, call_id: str, function_name: str, 
                             arguments: Dict[str, Any]) -> FunctionResult:
        """Execute a function call."""
        if not ENABLE_FUNCTION_CALLING:
            return FunctionResult(
                success=False,
                result=None,
                error="Function calling is disabled"
            )
        
        if function_name not in self.functions:
            return FunctionResult(
                success=False,
                result=None,
                error=f"Unknown function: {function_name}"
            )
        
        function_def = self.functions[function_name]
        start_time = datetime.now()
        
        try:
            # Log function call
            self._log_function_call(call_id, function_name, arguments)
            
            if function_def.handler:
                # Execute Python handler
                result = await self._execute_python_handler(function_def.handler, arguments)
            elif function_def.openclaw_tool:
                # Execute via OpenClaw
                result = await self._execute_openclaw_tool(function_def.openclaw_tool, arguments)
            else:
                return FunctionResult(
                    success=False,
                    result=None,
                    error=f"No handler configured for function: {function_name}"
                )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return FunctionResult(
                success=True,
                result=result,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Function call failed: {function_name} - {e}")
            
            return FunctionResult(
                success=False,
                result=None,
                error=str(e),
                execution_time=execution_time
            )
    
    async def _execute_python_handler(self, handler: Callable, arguments: Dict[str, Any]) -> Any:
        """Execute a Python function handler."""
        if asyncio.iscoroutinefunction(handler):
            return await handler(**arguments)
        else:
            return handler(**arguments)
    
    async def _execute_openclaw_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a function via OpenClaw API."""
        if not self.openclaw_client:
            raise Exception("OpenClaw client not configured - missing OPENCLAW_API_KEY")
        
        # Map function arguments to OpenClaw tool parameters
        # This is a simplified mapping - real implementation would need tool-specific handling
        tool_params = self._map_arguments_to_tool_params(tool_name, arguments)
        
        response = await self.openclaw_client.post(
            f"/tools/{tool_name}",
            json=tool_params
        )
        
        if response.status_code != 200:
            raise Exception(f"OpenClaw tool call failed: {response.status_code} - {response.text}")
        
        return response.json()
    
    def _map_arguments_to_tool_params(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Map function arguments to OpenClaw tool parameters."""
        # Tool-specific parameter mapping
        if tool_name == "weather":
            return {"location": arguments.get("location")}
        elif tool_name == "calendar":
            return {"date": arguments.get("date")}
        elif tool_name == "email":
            return {
                "to": arguments.get("to"),
                "subject": arguments.get("subject"),
                "body": arguments.get("message")
            }
        else:
            # Default: pass arguments as-is
            return arguments
    
    def _log_function_call(self, call_id: str, function_name: str, arguments: Dict[str, Any]):
        """Log function call for debugging and analytics."""
        if call_id not in self.call_history:
            self.call_history[call_id] = []
        
        self.call_history[call_id].append({
            "timestamp": datetime.now().isoformat(),
            "function": function_name,
            "arguments": arguments
        })
        
        logger.info(f"Function call: {function_name} in call {call_id}")
    
    def get_call_function_history(self, call_id: str) -> List[Dict]:
        """Get function call history for a specific call."""
        return self.call_history.get(call_id, [])
    
    def clear_call_history(self, call_id: str):
        """Clear function call history for a call."""
        if call_id in self.call_history:
            del self.call_history[call_id]
    
    # Built-in function handlers
    
    async def _get_current_time(self, timezone: str = "UTC") -> Dict[str, Any]:
        """Get current time handler."""
        now = datetime.now()
        
        # Simple timezone handling (would need proper timezone lib for production)
        if timezone == "EST":
            # EST is UTC-5, but this is simplified
            now = datetime.now()  # Would need proper timezone conversion
        
        return {
            "datetime": now.isoformat(),
            "timezone": timezone,
            "readable": now.strftime("%A, %B %d, %Y at %I:%M %p")
        }

# Global instance
function_manager = FunctionCallingManager()