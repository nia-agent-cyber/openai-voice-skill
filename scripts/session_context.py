#!/usr/bin/env python3
"""
OpenClaw Session Context Extraction

This module provides functionality to extract conversation history and context
from OpenClaw sessions and format it for injection into OpenAI Realtime API
voice calls.

SCOPE DISCIPLINE: This module ONLY extracts context. It does NOT modify 
call initiation, SIP handling, or Twilio integration.
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

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
            if not self.memory_path or not self.memory_path.exists():
                return conversations
            
            # Look at recent memory files
            for days in range(days_back):
                date = datetime.now() - timedelta(days=days)
                date_str = date.strftime("%Y-%m-%d")
                memory_file = self.memory_path / f"{date_str}.md"
                
                if memory_file.exists():
                    content = memory_file.read_text(encoding='utf-8')
                    file_conversations = self._parse_conversations(content)
                    conversations.extend(file_conversations)
            
            # Return most recent 5 conversations
            return conversations[-5:] if conversations else []
            
        except Exception as e:
            logger.warning(f"Error getting recent conversations: {e}")
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
            
            # Add caller context
            if caller_info.get("known_caller"):
                name = caller_info.get("name", "caller")
                relationship = caller_info.get("relationship", "unknown")
                
                enhanced.append(f"\\n\\nCALLER CONTEXT:")
                enhanced.append(f"You are speaking with {name}.")
                
                if relationship == "primary_user":
                    enhanced.append("This is your primary user - be familiar and collaborative.")
                elif relationship == "team_member":
                    enhanced.append("This is a team member - be professional but friendly.")
                
                # Add recent conversation context
                if conversations:
                    enhanced.append("\\nRecent conversation highlights:")
                    for conv in conversations[-3:]:  # Last 3 messages
                        enhanced.append(f"- {conv['time']}: {conv['speaker']}: {conv['message']}")
            else:
                enhanced.append(f"\\n\\nYou are speaking with an unknown caller. Be polite and helpful.")
            
            # Add call type context
            if call_type == "outbound":
                enhanced.append("\\nYou initiated this call.")
                if initial_message:
                    enhanced.append(f"Start by saying: {initial_message}")
            else:
                enhanced.append("\\nThey called you.")
            
            enhanced.append("\\nBe natural, conversational, and concise in this voice conversation.")
            
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