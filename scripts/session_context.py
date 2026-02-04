#!/usr/bin/env python3
"""
OpenClaw Session Context Extraction + Bridge Event Emitter

This module provides:
1. Context extraction from OpenClaw sessions for voice calls
2. Event emission to the TypeScript session bridge for transcript sync

SCOPE DISCIPLINE: This module handles context extraction and bridge events.
It does NOT modify call initiation, SIP handling, or Twilio integration.
"""

import json
import logging
import os
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

import httpx  # For async HTTP (already a dep of webhook-server.py)

logger = logging.getLogger(__name__)

# Bridge configuration
BRIDGE_URL = os.getenv("OPENCLAW_BRIDGE_URL", "http://localhost:8082")
BRIDGE_ENABLED = os.getenv("OPENCLAW_BRIDGE_ENABLED", "true").lower() == "true"


class BridgeEventEmitter:
    """
    Emits call events to the TypeScript session bridge.
    
    This enables transcript sync between voice calls and OpenClaw sessions
    without modifying webhook-server.py.
    
    Events:
    - call_started: When a call begins (maps call_id to session)
    - transcript_update: Real-time transcript updates (if available)
    - call_ended: When a call ends (triggers transcript sync)
    """
    
    def __init__(self, bridge_url: str = BRIDGE_URL, enabled: bool = BRIDGE_ENABLED):
        self.bridge_url = bridge_url.rstrip('/')
        self.enabled = enabled
        self._http_client: Optional[httpx.Client] = None
    
    @property
    def http_client(self) -> httpx.Client:
        """Lazy-init HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=5.0)
        return self._http_client
    
    def emit_call_started(
        self,
        call_id: str,
        phone_number: str,
        direction: str = "inbound",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Emit call_started event to bridge."""
        return self._emit_event({
            "callId": call_id,
            "eventType": "call_started",
            "phoneNumber": phone_number,
            "direction": direction,
            "timestamp": datetime.now().isoformat(),
            "data": metadata or {}
        })
    
    def emit_transcript_update(
        self,
        call_id: str,
        speaker: str,
        content: str,
        timestamp: Optional[str] = None
    ) -> bool:
        """Emit real-time transcript update to bridge."""
        return self._emit_event({
            "callId": call_id,
            "eventType": "transcript_update",
            "phoneNumber": "",  # Not needed for updates
            "direction": "",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "timestamp": timestamp or datetime.now().isoformat(),
                "speaker": speaker,
                "content": content
            }
        })
    
    def emit_call_ended(
        self,
        call_id: str,
        phone_number: str,
        direction: str = "inbound",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Emit call_ended event to bridge (triggers transcript sync)."""
        return self._emit_event({
            "callId": call_id,
            "eventType": "call_ended",
            "phoneNumber": phone_number,
            "direction": direction,
            "timestamp": datetime.now().isoformat(),
            "data": metadata or {}
        })
    
    def _emit_event(self, event: Dict[str, Any]) -> bool:
        """Send event to bridge (fire-and-forget, non-blocking)."""
        if not self.enabled:
            logger.debug(f"Bridge disabled, skipping event: {event.get('eventType')}")
            return False
        
        def send():
            try:
                response = self.http_client.post(
                    f"{self.bridge_url}/call-event",
                    json=event,
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code == 200:
                    logger.debug(f"Bridge event sent: {event.get('eventType')} for {event.get('callId')}")
                else:
                    logger.warning(f"Bridge event failed: HTTP {response.status_code}")
                return response.status_code == 200
            except Exception as e:
                logger.debug(f"Bridge event send failed (bridge may not be running): {e}")
                return False
        
        # Fire-and-forget in background thread to avoid blocking
        thread = threading.Thread(target=send, daemon=True)
        thread.start()
        return True  # Returns immediately, actual result is async
    
    def close(self):
        """Close HTTP client."""
        if self._http_client:
            self._http_client.close()
            self._http_client = None


# Global bridge emitter instance
_bridge_emitter: Optional[BridgeEventEmitter] = None


def get_bridge_emitter() -> BridgeEventEmitter:
    """Get or create the global bridge emitter."""
    global _bridge_emitter
    if _bridge_emitter is None:
        _bridge_emitter = BridgeEventEmitter()
    return _bridge_emitter

class SessionContextExtractor:
    """
    Extracts and formats OpenClaw session context for voice calls.
    This is purely a context extraction utility - no call handling.
    """
    
    def __init__(self):
        self.workspace_path = self._find_workspace_path()
        self.memory_path = self.workspace_path / "memory" if self.workspace_path else None
        
    def _find_workspace_path(self) -> Optional[Path]:
        """Find the OpenClaw workspace directory."""
        # Try environment variable first
        workspace_env = os.getenv("OPENCLAW_WORKSPACE")
        if workspace_env:
            workspace_path = Path(workspace_env)
            if workspace_path.exists():
                return workspace_path
        
        # Try default locations
        home = Path.home()
        default_paths = [
            home / ".openclaw" / "workspace",
            home / ".openclaw" / "workspace-voice-coder",
            Path.cwd(),  # Current directory as fallback
        ]
        
        for path in default_paths:
            if path.exists() and (path / "SOUL.md").exists():
                logger.info(f"Found OpenClaw workspace at: {path}")
                return path
        
        logger.warning("Could not find OpenClaw workspace directory")
        return None
    
    def get_enhanced_instructions(self, caller_phone: str, base_instructions: str, 
                                call_type: str = "inbound", initial_message: str = None) -> str:
        """
        Get enhanced instructions by adding context to base instructions.
        
        This is the main public interface - takes base instructions and returns
        enhanced instructions with context. Falls back to base instructions if
        context extraction fails.
        
        Args:
            caller_phone: Phone number of caller/callee
            base_instructions: Original instructions from agent config
            call_type: "inbound" or "outbound"
            initial_message: Optional initial message for outbound calls
            
        Returns:
            Enhanced instructions string (or fallback to base if extraction fails)
        """
        try:
            if not self.workspace_path:
                logger.info("No workspace found - using base instructions")
                return self._add_initial_message(base_instructions, initial_message)
            
            # Extract context
            context = self._extract_context(caller_phone)
            
            # Enhance instructions
            enhanced = self._build_enhanced_instructions(
                base_instructions, context, call_type, initial_message
            )
            
            logger.info(f"Enhanced instructions created for {self._mask_phone(caller_phone)}: {len(enhanced)} chars")
            return enhanced
            
        except Exception as e:
            logger.warning(f"Context extraction failed: {e} - using base instructions")
            return self._add_initial_message(base_instructions, initial_message)
    
    def _extract_context(self, phone: str) -> Dict[str, Any]:
        """Extract context for a phone number."""
        context = {
            "caller_info": self._get_caller_info(phone),
            "recent_conversations": [],
            "context_summary": ""
        }
        
        try:
            # Get caller info from phone mapping
            caller_info = context["caller_info"]
            
            if caller_info.get("known_caller", False):
                # Extract recent conversations
                context["recent_conversations"] = self._get_recent_conversations()
                
                # Build context summary
                context["context_summary"] = self._build_context_summary(context)
            
        except Exception as e:
            logger.warning(f"Error extracting context: {e}")
        
        return context
    
    def _get_caller_info(self, phone: str) -> Dict[str, Any]:
        """Get caller information from phone mapping."""
        try:
            # Try to load phone mapping
            mapping_file = self.workspace_path / "phone_mapping.json"
            if mapping_file.exists():
                with open(mapping_file, 'r') as f:
                    mapping = json.load(f)
                
                normalized_phone = self._normalize_phone(phone)
                if normalized_phone in mapping:
                    caller_info = mapping[normalized_phone].copy()
                    caller_info["phone"] = normalized_phone
                    caller_info["known_caller"] = True
                    return caller_info
            
            # Unknown caller
            return {
                "phone": phone,
                "name": "Unknown Caller",
                "relationship": "unknown",
                "known_caller": False
            }
            
        except Exception as e:
            logger.warning(f"Error getting caller info: {e}")
            return {"phone": phone, "name": "Unknown", "known_caller": False}
    
    def _get_recent_conversations(self, days_back: int = 2) -> List[Dict[str, str]]:
        """Get recent conversations from memory files."""
        conversations = []
        
        try:
            if not self.workspace_path:
                return conversations
            
            # First, check for MEMORY.md in main session only (for primary user)
            memory_md = self.workspace_path / "MEMORY.md"
            if memory_md.exists():
                try:
                    content = memory_md.read_text(encoding='utf-8')
                    # Extract key context from MEMORY.md
                    recent_context = self._extract_memory_highlights(content)
                    if recent_context:
                        conversations.extend(recent_context)
                except Exception as e:
                    logger.debug(f"Could not read MEMORY.md: {e}")
            
            # Then check daily memory files
            if self.memory_path and self.memory_path.exists():
                for days in range(days_back):
                    date = datetime.now() - timedelta(days=days)
                    date_str = date.strftime("%Y-%m-%d")
                    memory_file = self.memory_path / f"{date_str}.md"
                    
                    if memory_file.exists():
                        content = memory_file.read_text(encoding='utf-8')
                        file_conversations = self._parse_conversations(content)
                        conversations.extend(file_conversations)
            
            # Return most recent conversations (prioritize quality over quantity for voice)
            return conversations[-8:] if conversations else []
            
        except Exception as e:
            logger.warning(f"Error getting recent conversations: {e}")
            return []
    
    def _extract_memory_highlights(self, content: str) -> List[Dict[str, str]]:
        """Extract key highlights from MEMORY.md for voice context."""
        highlights = []
        
        try:
            lines = content.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                
                # Track sections
                if line.startswith('##'):
                    current_section = line.replace('##', '').strip()
                    continue
                
                # Extract key information for voice context
                if current_section and line.startswith('-'):
                    # Bullet points often contain key info
                    context_item = line[1:].strip()
                    if len(context_item) > 10 and len(context_item) < 100:
                        highlights.append({
                            "time": "recent",
                            "speaker": "Memory",
                            "message": f"{current_section}: {context_item}",
                            "type": "memory_highlight"
                        })
                
                # Look for recent context or current focus
                if any(keyword in line.lower() for keyword in ['current', 'recent', 'working on', 'focus']):
                    if len(line) > 15 and len(line) < 120:
                        highlights.append({
                            "time": "recent", 
                            "speaker": "Context",
                            "message": line,
                            "type": "current_focus"
                        })
            
            # Limit to most relevant highlights
            return highlights[-3:] if highlights else []
            
        except Exception as e:
            logger.debug(f"Error extracting memory highlights: {e}")
            return []

    def _parse_conversations(self, content: str) -> List[Dict[str, str]]:
        """Parse conversations from memory file content."""
        conversations = []
        
        try:
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                
                # Look for conversation patterns like "14:30 - User: message"
                match = re.match(r'(\d{2}:\d{2})\s*[-:]?\s*(\w+):\s*(.+)', line)
                if match:
                    time_str, speaker, message = match.groups()
                    conversations.append({
                        "time": time_str,
                        "speaker": speaker,
                        "message": message[:100]  # Truncate for voice
                    })
                    
        except Exception as e:
            logger.warning(f"Error parsing conversations: {e}")
        
        return conversations
    
    def _build_context_summary(self, context: Dict[str, Any]) -> str:
        """Build a concise context summary."""
        try:
            caller_info = context.get("caller_info", {})
            conversations = context.get("recent_conversations", [])
            
            summary_parts = []
            
            if caller_info.get("name"):
                summary_parts.append(f"Caller: {caller_info['name']}")
            
            if conversations:
                summary_parts.append(f"Recent activity: {len(conversations)} messages")
            
            return " | ".join(summary_parts)
            
        except:
            return "Context available"
    
    def _build_enhanced_instructions(self, base_instructions: str, context: Dict[str, Any], 
                                   call_type: str, initial_message: str = None) -> str:
        """Build enhanced instructions with context."""
        try:
            enhanced = [base_instructions]
            
            caller_info = context.get("caller_info", {})
            conversations = context.get("recent_conversations", [])
            
            # Add caller context with personalized greetings
            if caller_info.get("known_caller"):
                name = caller_info.get("name", "caller")
                preferred_name = caller_info.get("preferred_name", name)
                relationship = caller_info.get("relationship", "unknown")
                
                enhanced.append(f"\\n\\nCALLER CONTEXT:")
                enhanced.append(f"You are speaking with {name} (address as {preferred_name}).")
                
                # Personalized greeting based on relationship
                if relationship == "primary_user":
                    enhanced.append("This is your primary user - be familiar, collaborative, and greet warmly.")
                    enhanced.append(f"Start by greeting: 'Hi {preferred_name}! Good to hear from you.'")
                elif relationship == "team_member":
                    enhanced.append("This is a team member - be professional but friendly.")
                    enhanced.append(f"Start by greeting: 'Hello {preferred_name}, how can I help?'")
                elif relationship == "client":
                    enhanced.append("This is a client - be professional and helpful.")
                    enhanced.append(f"Start by greeting: 'Good day, how may I assist you today?'")
                
                # Add recent conversation context (limited to avoid latency)
                if conversations:
                    enhanced.append("\\nRECENT CONTEXT:")
                    recent_topics = set()
                    for conv in conversations[-5:]:  # Last 5 for better context
                        # Extract key topics/entities from messages
                        message = conv['message'].lower()
                        if any(word in message for word in ['project', 'work', 'issue', 'feature']):
                            recent_topics.add("project work")
                        if any(word in message for word in ['call', 'voice', 'phone']):
                            recent_topics.add("voice/call topics")
                        if any(word in message for word in ['telegram', 'chat', 'message']):
                            recent_topics.add("messaging")
                    
                    if recent_topics:
                        enhanced.append(f"Recent topics discussed: {', '.join(recent_topics)}")
                        enhanced.append("You can reference these topics naturally in conversation.")
                    
                    # Include most recent specific message if relevant
                    if conversations:
                        last_conv = conversations[-1]
                        if len(last_conv['message']) < 80:  # Only short, relevant messages
                            enhanced.append(f"Last exchange: {last_conv['speaker']}: {last_conv['message']}")
            else:
                enhanced.append(f"\\n\\nUNKNOWN CALLER:")
                enhanced.append("Be polite, introduce yourself, and ask how you can help.")
                enhanced.append("Start by greeting: 'Hello, this is Nia. How can I assist you today?'")
            
            # Add call type specific context
            if call_type == "outbound":
                enhanced.append("\\nCALL TYPE: You initiated this call.")
                if initial_message:
                    enhanced.append(f"Override greeting with: {initial_message}")
            else:
                enhanced.append("\\nCALL TYPE: Incoming call - they called you.")
            
            enhanced.append("\\nSTYLE: Be natural, conversational, and concise. Keep responses under 30 seconds.")
            
            return "".join(enhanced)
            
        except Exception as e:
            logger.warning(f"Error building enhanced instructions: {e}")
            return self._add_initial_message(base_instructions, initial_message)
    
    def _add_initial_message(self, instructions: str, initial_message: str = None) -> str:
        """Add initial message to instructions (fallback case)."""
        if initial_message:
            return f"{instructions}\\n\\nStart the conversation by saying: {initial_message}"
        return instructions
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number to E.164 format."""
        clean = "".join(c for c in phone if c.isdigit() or c == "+")
        if not clean.startswith("+"):
            clean = "+" + clean
        return clean
    
    def _mask_phone(self, phone: str) -> str:
        """Mask phone number for logging."""
        if len(phone) > 4:
            return phone[:-4] + "****"
        return "****"


# Factory function for easy import
def create_context_extractor() -> SessionContextExtractor:
    """Create a new session context extractor instance."""
    return SessionContextExtractor()


# =============================================================================
# Bridge Integration Helpers
# =============================================================================
# These functions provide a simple interface for webhook-server.py to integrate
# with the OpenClaw session bridge WITHOUT modifying webhook-server.py directly.
#
# Instead, these can be called from call_recording.py or a small integration
# shim that wraps the existing webhook-server.py lifecycle hooks.
# =============================================================================

def notify_call_started(call_id: str, phone_number: str, direction: str = "inbound") -> bool:
    """
    Notify the bridge that a call has started.
    
    Call this when a new call is accepted (inbound or outbound).
    The bridge will map this call to an OpenClaw session.
    
    Args:
        call_id: Unique call identifier (e.g., Twilio CallSid or OpenAI call_id)
        phone_number: Phone number of the caller/callee
        direction: "inbound" or "outbound"
    
    Returns:
        True if event was queued for sending
    """
    return get_bridge_emitter().emit_call_started(call_id, phone_number, direction)


def notify_transcript_update(call_id: str, speaker: str, content: str) -> bool:
    """
    Send a real-time transcript update to the bridge.
    
    Call this when speech is transcribed during the call.
    
    Args:
        call_id: Call identifier
        speaker: "user" or "assistant"
        content: Transcribed text
    
    Returns:
        True if event was queued for sending
    """
    return get_bridge_emitter().emit_transcript_update(call_id, speaker, content)


def notify_call_ended(call_id: str, phone_number: str, direction: str = "inbound") -> bool:
    """
    Notify the bridge that a call has ended.
    
    Call this when a call completes. The bridge will:
    1. Fetch the full transcript from /history/{call_id}/transcript
    2. Inject it into the corresponding OpenClaw session
    
    Args:
        call_id: Call identifier
        phone_number: Phone number of the caller/callee
        direction: "inbound" or "outbound"
    
    Returns:
        True if event was queued for sending
    """
    return get_bridge_emitter().emit_call_ended(call_id, phone_number, direction)


def sync_call_to_session(call_id: str) -> bool:
    """
    Manually trigger a transcript sync for a call.
    
    Use this to force a sync without waiting for call_ended.
    
    Args:
        call_id: Call identifier
    
    Returns:
        True if sync request was sent
    """
    try:
        import httpx
        response = httpx.post(
            f"{BRIDGE_URL}/sync-transcript",
            json={"callId": call_id},
            timeout=5.0
        )
        return response.status_code == 200
    except Exception as e:
        logger.warning(f"Manual sync failed: {e}")
        return False


# =============================================================================
# Integration Guide
# =============================================================================
#
# To integrate with webhook-server.py WITHOUT modifying it:
#
# Option 1: Modify call_recording.py (RECOMMENDED)
# ------------------------------------------------
# Add calls to notify_call_started/notify_call_ended in the recording manager:
#
#   async def start_call_recording(self, call_id, call_type, from_num, to_num, metadata):
#       # ... existing code ...
#       from session_context import notify_call_started
#       phone = from_num if call_type == "inbound" else to_num
#       notify_call_started(call_id, phone, call_type)
#
#   async def end_call_recording(self, call_id, status):
#       # ... existing code ...
#       from session_context import notify_call_ended
#       record = self.get_call_record(call_id)
#       if record:
#           phone = record.caller_number or record.callee_number or ""
#           notify_call_ended(call_id, phone, record.call_type)
#
# Option 2: Create a wrapper script
# ---------------------------------
# Create a new script that imports and wraps webhook-server.py,
# adding bridge notifications to the appropriate lifecycle points.
#
# Option 3: Use environment hooks (if webhook-server supports them)
# -----------------------------------------------------------------
# Set OPENCLAW_BRIDGE_URL and check if webhook-server has any
# configurable callback hooks.
#
# =============================================================================