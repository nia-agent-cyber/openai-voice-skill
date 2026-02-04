#!/usr/bin/env python3
"""
OpenClaw Integration Bridge

This module provides the interface between the voice calling system and
OpenClaw session management. It handles:

1. User session identification by phone number
2. Conversation history retrieval
3. Memory file access
4. Session state synchronization
5. Context injection for voice calls
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import httpx

from session_context import SessionContextExtractor

logger = logging.getLogger(__name__)

class OpenClawBridge:
    """
    Bridge between voice calling system and OpenClaw session management.
    """
    
    def __init__(self):
        self.context_extractor = SessionContextExtractor()
        self.user_phone_mapping = self._load_phone_mapping()
        self.session_cache = {}  # Cache for session data
        self.cache_ttl = 300  # 5 minutes cache TTL
        
        # OpenClaw API configuration (if available)
        self.openclaw_api_url = os.getenv("OPENCLAW_API_URL", "http://localhost:3000")
        self.openclaw_api_key = os.getenv("OPENCLAW_API_KEY")
        
    def _load_phone_mapping(self) -> Dict[str, Dict[str, str]]:
        """
        Load phone number to user mapping from configuration.
        
        Returns mapping: {phone_number: {name, session_id, relationship}}
        """
        mapping = {}
        
        try:
            # Try to load from workspace config
            if self.context_extractor.workspace_path:
                config_file = self.context_extractor.workspace_path / "phone_mapping.json"
                if config_file.exists():
                    with open(config_file, 'r') as f:
                        mapping = json.load(f)
                        logger.info(f"Loaded phone mapping for {len(mapping)} numbers")
            
            # Also check environment variable for additional mappings
            env_mapping = os.getenv("PHONE_USER_MAPPING")
            if env_mapping:
                try:
                    env_data = json.loads(env_mapping)
                    mapping.update(env_data)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON in PHONE_USER_MAPPING environment variable")
        
        except Exception as e:
            logger.error(f"Error loading phone mapping: {e}")
        
        # Default mapping for common test numbers
        if not mapping:
            mapping = {
                # Example mappings - replace with actual user data
                "+1234567890": {
                    "name": "Remi",
                    "session_id": "main",
                    "relationship": "primary_user",
                    "preferred_name": "Remi"
                }
            }
            logger.info("Using default phone mapping")
        
        return mapping
    
    async def identify_caller(self, phone_number: str) -> Optional[Dict[str, str]]:
        """
        Identify caller by phone number.
        
        Args:
            phone_number: E.164 formatted phone number
            
        Returns:
            Dictionary with caller information or None if unknown
        """
        try:
            # Normalize phone number (remove spaces, dashes, etc.)
            normalized_phone = self._normalize_phone_number(phone_number)
            
            # Check direct mapping first
            if normalized_phone in self.user_phone_mapping:
                caller_info = self.user_phone_mapping[normalized_phone].copy()
                caller_info["phone"] = normalized_phone
                caller_info["known_caller"] = True
                logger.info(f"Identified caller: {caller_info.get('name', 'Unknown')} ({normalized_phone})")
                return caller_info
            
            # Try OpenClaw API lookup if available
            if self.openclaw_api_key:
                api_result = await self._lookup_caller_via_api(normalized_phone)
                if api_result:
                    return api_result
            
            # Unknown caller
            logger.info(f"Unknown caller: {normalized_phone}")
            return {
                "phone": normalized_phone,
                "name": "Unknown Caller",
                "session_id": "guest",
                "relationship": "unknown",
                "known_caller": False
            }
            
        except Exception as e:
            logger.error(f"Error identifying caller {phone_number}: {e}")
            return None
    
    async def get_caller_context(self, caller_info: Dict[str, str]) -> Dict[str, Any]:
        """
        Get full session context for a caller.
        
        Args:
            caller_info: Caller information from identify_caller()
            
        Returns:
            Complete context dictionary for voice call
        """
        try:
            session_id = caller_info.get("session_id", "guest")
            cache_key = f"{session_id}_{caller_info.get('phone', '')}"
            
            # Check cache first
            if cache_key in self.session_cache:
                cached_data = self.session_cache[cache_key]
                if time.time() - cached_data["cached_at"] < self.cache_ttl:
                    logger.debug(f"Using cached context for {caller_info.get('name', 'caller')}")
                    return cached_data["context"]
            
            # Extract fresh context
            logger.info(f"Extracting context for {caller_info.get('name', 'caller')}")
            
            # Get session context using the extractor
            base_context = self.context_extractor.extract_recent_context(
                session_id=session_id,
                hours_back=24,
                max_messages=20
            )
            
            # Enhance with caller-specific information
            enhanced_context = self._enhance_context_for_caller(base_context, caller_info)
            
            # Cache the result
            self.session_cache[cache_key] = {
                "context": enhanced_context,
                "cached_at": time.time()
            }
            
            logger.info(f"Context extracted for {caller_info.get('name', 'caller')}: "
                       f"{len(enhanced_context.get('conversation_history', []))} messages, "
                       f"{len(enhanced_context.get('ongoing_projects', []))} projects")
            
            return enhanced_context
            
        except Exception as e:
            logger.error(f"Error getting caller context: {e}")
            return {
                "conversation_history": [],
                "user_info": {"error": "Context extraction failed"},
                "ongoing_projects": [],
                "recent_decisions": [],
                "context_summary": f"Context for {caller_info.get('name', 'caller')} - extraction failed",
                "caller_info": caller_info
            }
    
    def format_context_for_voice(self, context: Dict[str, Any], 
                                call_type: str = "inbound",
                                initial_message: Optional[str] = None) -> str:
        """
        Format context into OpenAI Realtime API instructions.
        
        Args:
            context: Full context from get_caller_context()
            call_type: "inbound" or "outbound"
            initial_message: Optional initial message for outbound calls
            
        Returns:
            Formatted instructions string
        """
        try:
            caller_info = context.get("caller_info", {})
            caller_name = caller_info.get("name", "the caller")
            relationship = caller_info.get("relationship", "unknown")
            
            # Build personalized instructions
            instructions = []
            
            # Base identity and relationship
            instructions.append(f"You are Nia, an AI assistant. You're speaking with {caller_name}.")
            
            if relationship == "primary_user":
                instructions.append("This is your primary user - be familiar and collaborative.")
            elif relationship == "team_member":
                instructions.append("This is a team member - be professional but friendly.")
            elif relationship == "unknown":
                instructions.append("This is an unknown caller - be polite and helpful but cautious.")
            
            # Call context
            if call_type == "outbound":
                if initial_message:
                    instructions.append(f"You initiated this call to: {initial_message}")
                else:
                    instructions.append("You initiated this call as a follow-up.")
            else:
                instructions.append("They called you.")
            
            # Recent conversation context
            conversations = context.get("conversation_history", [])
            if conversations and caller_info.get("known_caller", False):
                instructions.append("\nRecent conversation context:")
                
                # Include relevant recent exchanges
                recent_relevant = self._find_relevant_conversations(conversations, caller_name)
                
                if recent_relevant:
                    instructions.append("Previous discussion highlights:")
                    for conv in recent_relevant[-3:]:  # Last 3 relevant messages
                        timestamp = conv.get("timestamp", "")
                        content = conv.get("content", "")[:100]  # Truncate for voice
                        if content:
                            instructions.append(f"- {timestamp}: {content}")
                else:
                    instructions.append("- Recent chat history available")
            
            # Current projects/work
            projects = context.get("ongoing_projects", [])
            if projects and caller_info.get("known_caller", False):
                instructions.append("\nCurrent projects context:")
                for project in projects[:2]:
                    name = project.get("name", "Unnamed project")
                    description = project.get("description", "")[:100]
                    instructions.append(f"- {name}: {description}")
            
            # Recent decisions/conclusions
            decisions = context.get("recent_decisions", [])
            if decisions and caller_info.get("known_caller", False):
                instructions.append("\nRecent decisions:")
                for decision in decisions[-2:]:
                    content = decision.get("content", "")[:80]
                    instructions.append(f"- {content}")
            
            # Voice call behavior guidance
            instructions.append("\nVoice conversation guidelines:")
            instructions.append("- Be natural, conversational, and engaging")
            instructions.append("- Keep responses concise but informative")
            
            if caller_info.get("known_caller", False):
                instructions.append("- Reference shared context when relevant")
                instructions.append("- Ask about ongoing work and projects")
                instructions.append("- Follow up on previous conversations naturally")
            else:
                instructions.append("- Ask how you can help them today")
                instructions.append("- Be helpful but don't assume prior context")
            
            formatted_instructions = "\n".join(instructions)
            
            logger.debug(f"Generated {len(formatted_instructions)} chars of context for {caller_name}")
            return formatted_instructions
            
        except Exception as e:
            logger.error(f"Error formatting context for voice: {e}")
            return f"You are Nia, an AI assistant, speaking with {context.get('caller_info', {}).get('name', 'someone')}. Be helpful and conversational."
    
    async def update_call_context(self, call_id: str, context_updates: Dict[str, Any]):
        """
        Update context during an active call (e.g., from conversation events).
        
        Args:
            call_id: Active call identifier
            context_updates: Context updates to apply
        """
        try:
            # Store call context updates for future reference
            context_file = self._get_call_context_file(call_id)
            
            existing_context = {}
            if context_file.exists():
                with open(context_file, 'r') as f:
                    existing_context = json.load(f)
            
            # Merge updates
            existing_context.update(context_updates)
            existing_context["last_updated"] = datetime.now().isoformat()
            
            # Save updated context
            context_file.parent.mkdir(parents=True, exist_ok=True)
            with open(context_file, 'w') as f:
                json.dump(existing_context, f, indent=2)
            
            logger.debug(f"Updated call context for {call_id}")
            
        except Exception as e:
            logger.error(f"Error updating call context for {call_id}: {e}")
    
    async def finalize_call_context(self, call_id: str, call_summary: Dict[str, Any]):
        """
        Finalize call context and save to memory.
        
        Args:
            call_id: Completed call identifier
            call_summary: Summary of the call (duration, key points, etc.)
        """
        try:
            # Load call context
            context_file = self._get_call_context_file(call_id)
            call_context = {}
            
            if context_file.exists():
                with open(context_file, 'r') as f:
                    call_context = json.load(f)
            
            # Create memory entry
            memory_entry = {
                "timestamp": datetime.now().isoformat(),
                "call_id": call_id,
                "type": "voice_call",
                "caller": call_summary.get("caller_name", "unknown"),
                "duration": call_summary.get("duration_seconds", 0),
                "summary": call_summary.get("summary", "Voice call completed"),
                "key_points": call_summary.get("key_points", []),
                "context": call_context
            }
            
            # Append to today's memory file
            await self._append_to_memory(memory_entry)
            
            # Clean up temporary context file
            if context_file.exists():
                context_file.unlink()
            
            logger.info(f"Finalized call context for {call_id}")
            
        except Exception as e:
            logger.error(f"Error finalizing call context for {call_id}: {e}")
    
    # Helper methods
    
    def _normalize_phone_number(self, phone: str) -> str:
        """Normalize phone number to standard E.164 format."""
        # Remove all non-digit characters except leading +
        clean_phone = "".join(c for c in phone if c.isdigit() or c == "+")
        
        # Ensure it starts with +
        if not clean_phone.startswith("+"):
            clean_phone = "+" + clean_phone
        
        return clean_phone
    
    async def _lookup_caller_via_api(self, phone_number: str) -> Optional[Dict[str, str]]:
        """Lookup caller information via OpenClaw API (if available)."""
        try:
            if not self.openclaw_api_key:
                return None
            
            headers = {"Authorization": f"Bearer {self.openclaw_api_key}"}
            url = f"{self.openclaw_api_url}/api/users/lookup"
            params = {"phone": phone_number}
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "phone": phone_number,
                        "name": data.get("name", "Unknown"),
                        "session_id": data.get("session_id", "guest"),
                        "relationship": data.get("relationship", "unknown"),
                        "known_caller": True
                    }
                    
        except Exception as e:
            logger.warning(f"API caller lookup failed: {e}")
        
        return None
    
    def _enhance_context_for_caller(self, base_context: Dict[str, Any], 
                                   caller_info: Dict[str, str]) -> Dict[str, Any]:
        """Enhance base context with caller-specific information."""
        enhanced = base_context.copy()
        enhanced["caller_info"] = caller_info
        
        # Adjust context based on caller relationship
        relationship = caller_info.get("relationship", "unknown")
        
        if relationship == "primary_user":
            # Include full context for primary user
            pass  # Use full context as-is
        elif relationship == "team_member":
            # Include work-related context, filter personal details
            enhanced = self._filter_personal_context(enhanced)
        else:
            # Limited context for unknown callers
            enhanced = self._limit_context_for_unknown(enhanced)
        
        return enhanced
    
    def _filter_personal_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Filter personal information for team members."""
        filtered = context.copy()
        
        # Remove personal memory details
        user_info = filtered.get("user_info", {})
        if "long_term_memory" in user_info:
            del user_info["long_term_memory"]
        
        # Keep only work-related conversations
        conversations = filtered.get("conversation_history", [])
        work_conversations = [
            conv for conv in conversations
            if self._is_work_related_conversation(conv)
        ]
        filtered["conversation_history"] = work_conversations
        
        return filtered
    
    def _limit_context_for_unknown(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Limit context for unknown callers."""
        return {
            "conversation_history": [],  # No conversation history
            "user_info": {"agent_identity": context.get("user_info", {}).get("agent_identity", "")},
            "ongoing_projects": [],  # No project details
            "recent_decisions": [],  # No decisions
            "context_summary": "Limited context for unknown caller",
            "caller_info": context.get("caller_info", {})
        }
    
    def _find_relevant_conversations(self, conversations: List[Dict[str, Any]], 
                                   caller_name: str) -> List[Dict[str, Any]]:
        """Find conversations relevant to the current caller."""
        relevant = []
        
        for conv in conversations:
            # Include conversations involving this caller
            speaker = conv.get("speaker", "")
            content = conv.get("content", "").lower()
            
            if (speaker.lower() == caller_name.lower() or 
                caller_name.lower() in content):
                relevant.append(conv)
        
        return relevant
    
    def _is_work_related_conversation(self, conversation: Dict[str, Any]) -> bool:
        """Check if a conversation is work-related."""
        content = conversation.get("content", "").lower()
        
        work_keywords = [
            "project", "task", "code", "api", "server", "client",
            "meeting", "deadline", "feature", "bug", "deploy",
            "build", "test", "development", "design"
        ]
        
        return any(keyword in content for keyword in work_keywords)
    
    def _get_call_context_file(self, call_id: str) -> Path:
        """Get the path for storing call context."""
        if self.context_extractor.workspace_path:
            context_dir = self.context_extractor.workspace_path / "call_contexts"
            return context_dir / f"{call_id}.json"
        else:
            # Fallback to temp directory
            return Path.cwd() / "temp" / "call_contexts" / f"{call_id}.json"
    
    async def _append_to_memory(self, memory_entry: Dict[str, Any]):
        """Append memory entry to today's memory file."""
        try:
            if not self.context_extractor.memory_path:
                logger.warning("No memory path available for saving call memory")
                return
            
            today = datetime.now().strftime("%Y-%m-%d")
            memory_file = self.context_extractor.memory_path / f"{today}.md"
            
            # Format memory entry as markdown
            timestamp = memory_entry["timestamp"]
            call_type = memory_entry["type"]
            caller = memory_entry["caller"]
            summary = memory_entry["summary"]
            
            memory_text = f"\n## {timestamp} - {call_type.title()}\n"
            memory_text += f"**Caller:** {caller}\n"
            memory_text += f"**Duration:** {memory_entry.get('duration', 0):.1f}s\n"
            memory_text += f"**Summary:** {summary}\n"
            
            key_points = memory_entry.get("key_points", [])
            if key_points:
                memory_text += "**Key Points:**\n"
                for point in key_points:
                    memory_text += f"- {point}\n"
            
            memory_text += "\n"
            
            # Append to memory file
            self.context_extractor.memory_path.mkdir(exist_ok=True)
            with open(memory_file, 'a', encoding='utf-8') as f:
                f.write(memory_text)
            
            logger.info(f"Appended call memory to {memory_file}")
            
        except Exception as e:
            logger.error(f"Error appending to memory: {e}")


# Factory function
def create_openclaw_bridge() -> OpenClawBridge:
    """Create a new OpenClaw bridge instance."""
    return OpenClawBridge()