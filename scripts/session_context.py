#!/usr/bin/env python3
"""
OpenClaw Session Context Extraction

This module provides functionality to extract conversation history and context
from OpenClaw sessions and format it for injection into OpenAI Realtime API
voice calls.
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)

class SessionContextExtractor:
    """
    Extracts and formats OpenClaw session context for voice calls.
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
    
    def extract_recent_context(self, 
                             session_id: Optional[str] = None,
                             hours_back: int = 24,
                             max_messages: int = 50) -> Dict[str, Any]:
        """
        Extract recent conversation context from OpenClaw session.
        
        Args:
            session_id: Specific session ID (if known)
            hours_back: How many hours of history to include
            max_messages: Maximum number of recent messages to include
        
        Returns:
            Dictionary containing formatted context for voice call
        """
        context = {
            "conversation_history": [],
            "user_info": {},
            "ongoing_projects": [],
            "recent_decisions": [],
            "context_summary": "",
            "extracted_at": datetime.now().isoformat()
        }
        
        if not self.workspace_path:
            logger.warning("No workspace path available for context extraction")
            return context
        
        try:
            # Extract user information
            context["user_info"] = self._extract_user_info()
            
            # Extract recent conversation history
            context["conversation_history"] = self._extract_conversation_history(
                hours_back, max_messages
            )
            
            # Extract ongoing projects and decisions
            context["ongoing_projects"] = self._extract_project_context()
            context["recent_decisions"] = self._extract_recent_decisions(hours_back)
            
            # Generate summary for voice context
            context["context_summary"] = self._generate_voice_summary(context)
            
            logger.info(f"Extracted context with {len(context['conversation_history'])} messages")
            
        except Exception as e:
            logger.error(f"Error extracting session context: {e}")
        
        return context
    
    def _extract_user_info(self) -> Dict[str, Any]:
        """Extract user information from SOUL.md and USER.md files."""
        user_info = {}
        
        try:
            # Read SOUL.md for agent identity
            soul_file = self.workspace_path / "SOUL.md"
            if soul_file.exists():
                content = soul_file.read_text(encoding='utf-8')
                user_info["agent_identity"] = self._extract_key_info(content, "agent")
            
            # Read USER.md for user information
            user_file = self.workspace_path / "USER.md"
            if user_file.exists():
                content = user_file.read_text(encoding='utf-8')
                user_info["user_profile"] = self._extract_key_info(content, "user")
                
            # Read MEMORY.md for long-term context (only in main session)
            memory_file = self.workspace_path / "MEMORY.md"
            if memory_file.exists():
                content = memory_file.read_text(encoding='utf-8')
                user_info["long_term_memory"] = self._extract_key_info(content, "memory")
                
        except Exception as e:
            logger.error(f"Error extracting user info: {e}")
        
        return user_info
    
    def _extract_conversation_history(self, hours_back: int, max_messages: int) -> List[Dict[str, Any]]:
        """Extract recent conversation history from memory files."""
        conversations = []
        
        if not self.memory_path or not self.memory_path.exists():
            return conversations
        
        try:
            # Get recent memory files (last few days)
            cutoff_date = datetime.now() - timedelta(hours=hours_back)
            memory_files = []
            
            for days_back in range(7):  # Look back up to 7 days
                date = datetime.now() - timedelta(days=days_back)
                date_str = date.strftime("%Y-%m-%d")
                memory_file = self.memory_path / f"{date_str}.md"
                
                if memory_file.exists():
                    stat = memory_file.stat()
                    file_date = datetime.fromtimestamp(stat.st_mtime)
                    if file_date >= cutoff_date:
                        memory_files.append((memory_file, file_date))
            
            # Sort by date (newest first)
            memory_files.sort(key=lambda x: x[1], reverse=True)
            
            # Extract conversations from memory files
            message_count = 0
            for memory_file, _ in memory_files:
                if message_count >= max_messages:
                    break
                    
                try:
                    content = memory_file.read_text(encoding='utf-8')
                    file_conversations = self._parse_memory_conversations(content)
                    conversations.extend(file_conversations)
                    message_count += len(file_conversations)
                except Exception as e:
                    logger.warning(f"Error reading memory file {memory_file}: {e}")
            
            # Limit to max_messages and reverse to chronological order
            conversations = conversations[:max_messages]
            conversations.reverse()
            
        except Exception as e:
            logger.error(f"Error extracting conversation history: {e}")
        
        return conversations
    
    def _extract_project_context(self) -> List[Dict[str, Any]]:
        """Extract information about ongoing projects."""
        projects = []
        
        try:
            # Look for common project indicators
            project_files = [
                "README.md", "PROJECT.md", "TODO.md", 
                "HEARTBEAT.md", "GOALS.md"
            ]
            
            for file_name in project_files:
                file_path = self.workspace_path / file_name
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        project_info = self._extract_project_info(content, file_name)
                        if project_info:
                            projects.append(project_info)
                    except Exception as e:
                        logger.warning(f"Error reading project file {file_name}: {e}")
        
        except Exception as e:
            logger.error(f"Error extracting project context: {e}")
        
        return projects
    
    def _extract_recent_decisions(self, hours_back: int) -> List[Dict[str, Any]]:
        """Extract recent decisions and conclusions from memory."""
        decisions = []
        
        try:
            if not self.memory_path:
                return decisions
                
            # Look through recent memory files for decision markers
            decision_keywords = [
                "decided", "conclusion", "resolved", "agreed", 
                "determined", "settled on", "going with"
            ]
            
            cutoff_date = datetime.now() - timedelta(hours=hours_back)
            
            for days_back in range(3):  # Last 3 days for decisions
                date = datetime.now() - timedelta(days=days_back)
                date_str = date.strftime("%Y-%m-%d")
                memory_file = self.memory_path / f"{date_str}.md"
                
                if memory_file.exists():
                    try:
                        content = memory_file.read_text(encoding='utf-8')
                        file_decisions = self._parse_decisions(content, decision_keywords)
                        decisions.extend(file_decisions)
                    except Exception as e:
                        logger.warning(f"Error parsing decisions from {memory_file}: {e}")
        
        except Exception as e:
            logger.error(f"Error extracting recent decisions: {e}")
        
        return decisions
    
    def _generate_voice_summary(self, context: Dict[str, Any]) -> str:
        """Generate a concise summary suitable for voice call context."""
        summary_parts = []
        
        try:
            # User context
            user_info = context.get("user_info", {})
            if user_info.get("user_profile"):
                summary_parts.append(f"User: {user_info['user_profile'][:200]}...")
            
            # Recent conversation highlights
            conversations = context.get("conversation_history", [])
            if conversations:
                recent_count = min(5, len(conversations))
                summary_parts.append(f"Recent activity: {recent_count} recent conversations")
                
                # Extract key topics from recent messages
                recent_topics = self._extract_topics_from_conversations(conversations[-recent_count:])
                if recent_topics:
                    summary_parts.append(f"Key topics: {', '.join(recent_topics)}")
            
            # Ongoing projects
            projects = context.get("ongoing_projects", [])
            if projects:
                project_names = [p.get("name", "Unknown") for p in projects[:3]]
                summary_parts.append(f"Active projects: {', '.join(project_names)}")
            
            # Recent decisions
            decisions = context.get("recent_decisions", [])
            if decisions:
                summary_parts.append(f"{len(decisions)} recent decisions/conclusions")
            
            return " | ".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error generating voice summary: {e}")
            return "Context available but summary generation failed"
    
    def format_for_openai_instructions(self, context: Dict[str, Any], 
                                     caller_info: Optional[Dict[str, str]] = None) -> str:
        """
        Format the extracted context into instructions for OpenAI Realtime API.
        
        Args:
            context: The extracted context from extract_recent_context()
            caller_info: Information about the caller (name, phone, etc.)
        
        Returns:
            Formatted instructions string for OpenAI
        """
        try:
            instructions = []
            
            # Base personality from user info
            user_info = context.get("user_info", {})
            if user_info.get("agent_identity"):
                instructions.append(f"Identity: {user_info['agent_identity']}")
            
            # Caller context
            if caller_info:
                caller_name = caller_info.get("name", "the caller")
                instructions.append(f"You are speaking with {caller_name}.")
                
                if caller_info.get("relationship"):
                    instructions.append(f"Relationship: {caller_info['relationship']}")
            
            # Recent conversation context
            conversations = context.get("conversation_history", [])
            if conversations:
                instructions.append(f"\nRecent conversation context:")
                
                # Include last few important exchanges
                recent_messages = conversations[-3:] if conversations else []
                for msg in recent_messages:
                    timestamp = msg.get("timestamp", "")
                    speaker = msg.get("speaker", "unknown")
                    content = msg.get("content", "")[:150]  # Truncate for voice
                    
                    if content:
                        instructions.append(f"- {speaker}: {content}")
            
            # Ongoing projects context
            projects = context.get("ongoing_projects", [])
            if projects:
                instructions.append(f"\nCurrent projects:")
                for project in projects[:2]:  # Limit to most relevant
                    name = project.get("name", "Unknown project")
                    status = project.get("status", "")
                    if status:
                        instructions.append(f"- {name}: {status}")
                    else:
                        instructions.append(f"- {name}")
            
            # Recent decisions/conclusions
            decisions = context.get("recent_decisions", [])
            if decisions:
                instructions.append(f"\nRecent decisions:")
                for decision in decisions[-2:]:  # Last 2 decisions
                    content = decision.get("content", "")[:100]
                    instructions.append(f"- {content}")
            
            # Voice-specific guidance
            instructions.append(f"\nVoice call guidance:")
            instructions.append(f"- This is a voice conversation, be natural and conversational")
            instructions.append(f"- Reference recent context when appropriate")
            instructions.append(f"- Ask follow-up questions about ongoing work")
            instructions.append(f"- Keep responses concise but engaging")
            
            return "\n".join(instructions)
            
        except Exception as e:
            logger.error(f"Error formatting OpenAI instructions: {e}")
            return "You are a helpful AI assistant having a voice conversation."
    
    # Helper methods
    
    def _extract_key_info(self, content: str, info_type: str) -> str:
        """Extract key information from markdown content."""
        try:
            # Remove markdown formatting and extract first few sentences
            clean_content = re.sub(r'[#*\-\[\]()]', '', content)
            clean_content = re.sub(r'\n+', ' ', clean_content)
            
            # Take first 300 characters for context
            return clean_content.strip()[:300]
        except:
            return ""
    
    def _parse_memory_conversations(self, content: str) -> List[Dict[str, Any]]:
        """Parse conversation entries from memory file content."""
        conversations = []
        
        try:
            # Look for conversation patterns (timestamp + speaker + content)
            patterns = [
                r'(\d{2}:\d{2})\s*[-:]?\s*(\w+):\s*(.+)',  # "14:30 - User: message"
                r'(\w+)\s*\((\d{2}:\d{2})\):\s*(.+)',       # "User (14:30): message"
                r'##\s*(\w+)\s*(.+)',                       # "## User message"
            ]
            
            lines = content.split('\n')
            current_conversation = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Try to match conversation patterns
                for pattern in patterns:
                    match = re.match(pattern, line)
                    if match:
                        if len(match.groups()) == 3:
                            time_or_speaker, speaker_or_time, content_part = match.groups()
                            
                            # Determine which is which
                            if ':' in time_or_speaker:  # Time format
                                timestamp, speaker, content = match.groups()
                            else:  # Speaker first
                                speaker, timestamp, content = match.groups()
                        else:
                            speaker = match.group(1)
                            content = match.group(2)
                            timestamp = ""
                        
                        conversations.append({
                            "timestamp": timestamp,
                            "speaker": speaker,
                            "content": content.strip(),
                            "type": "conversation"
                        })
                        break
            
        except Exception as e:
            logger.warning(f"Error parsing conversations: {e}")
        
        return conversations
    
    def _extract_project_info(self, content: str, filename: str) -> Optional[Dict[str, Any]]:
        """Extract project information from file content."""
        try:
            # Extract title (first header)
            title_match = re.search(r'^#\s*(.+)', content, re.MULTILINE)
            title = title_match.group(1) if title_match else filename
            
            # Extract first paragraph as description
            lines = content.split('\n')
            description = ""
            for line in lines:
                clean_line = line.strip()
                if clean_line and not clean_line.startswith('#'):
                    description = clean_line[:200]
                    break
            
            return {
                "name": title,
                "filename": filename,
                "description": description,
                "type": "project_file"
            }
            
        except:
            return None
    
    def _parse_decisions(self, content: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """Parse decision statements from content."""
        decisions = []
        
        try:
            lines = content.split('\n')
            
            for line in lines:
                line_lower = line.lower()
                
                # Check if line contains decision keywords
                for keyword in keywords:
                    if keyword in line_lower:
                        decisions.append({
                            "content": line.strip(),
                            "keyword": keyword,
                            "type": "decision"
                        })
                        break
                        
        except Exception as e:
            logger.warning(f"Error parsing decisions: {e}")
        
        return decisions
    
    def _extract_topics_from_conversations(self, conversations: List[Dict[str, Any]]) -> List[str]:
        """Extract key topics from recent conversations."""
        topics = []
        
        try:
            # Simple keyword extraction
            common_topics = []
            
            for conv in conversations:
                content = conv.get("content", "").lower()
                
                # Look for technical keywords
                tech_keywords = [
                    "api", "server", "database", "code", "bug", "feature",
                    "deploy", "test", "build", "project", "client", "user"
                ]
                
                for keyword in tech_keywords:
                    if keyword in content and keyword not in common_topics:
                        common_topics.append(keyword)
            
            return common_topics[:5]  # Top 5 topics
            
        except:
            return []


# Factory function for easy import
def create_context_extractor() -> SessionContextExtractor:
    """Create a new session context extractor instance."""
    return SessionContextExtractor()