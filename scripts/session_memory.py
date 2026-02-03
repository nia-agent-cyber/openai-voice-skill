#!/usr/bin/env python3
"""
Session Memory Module for OpenAI Voice Skill

Provides persistent conversation context across multiple calls.
Allows agents to remember previous conversations and maintain context.
"""

import asyncio
import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import hashlib

logger = logging.getLogger(__name__)

# Configuration
MEMORY_DATABASE_PATH = Path(os.getenv("MEMORY_DATABASE_PATH", "session_memory.db"))
ENABLE_SESSION_MEMORY = os.getenv("ENABLE_SESSION_MEMORY", "true").lower() == "true"
MEMORY_RETENTION_DAYS = int(os.getenv("MEMORY_RETENTION_DAYS", "30"))
MAX_MEMORY_ENTRIES_PER_SESSION = int(os.getenv("MAX_MEMORY_ENTRIES_PER_SESSION", "100"))
CONTEXT_SUMMARY_LENGTH = int(os.getenv("CONTEXT_SUMMARY_LENGTH", "500"))

@dataclass
class MemoryEntry:
    """Individual memory entry."""
    session_id: str
    timestamp: datetime
    entry_type: str  # 'conversation', 'fact', 'preference', 'function_call', 'summary'
    content: str
    metadata: Optional[Dict[str, Any]] = None
    importance: int = 1  # 1-10 scale, higher = more important

@dataclass
class SessionContext:
    """Session context with conversation history."""
    session_id: str
    caller_number: str
    first_call: datetime
    last_call: datetime
    total_calls: int
    memory_entries: List[MemoryEntry]
    summary: Optional[str] = None
    preferences: Dict[str, Any] = None

class SessionMemoryManager:
    """Manages session memory and conversation context."""
    
    def __init__(self):
        self.db_path = MEMORY_DATABASE_PATH
        self.active_sessions: Dict[str, SessionContext] = {}
        self._init_database()
        
    def _init_database(self):
        """Initialize SQLite database for session memory."""
        with sqlite3.connect(self.db_path) as conn:
            # Sessions table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    caller_number TEXT NOT NULL,
                    first_call TEXT NOT NULL,
                    last_call TEXT NOT NULL,
                    total_calls INTEGER DEFAULT 1,
                    summary TEXT,
                    preferences TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            
            # Memory entries table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    entry_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    importance INTEGER DEFAULT 1,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            ''')
            
            # Indexes for performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_caller ON sessions(caller_number)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_last_call ON sessions(last_call)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_memory_session ON memory_entries(session_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_memory_timestamp ON memory_entries(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_memory_importance ON memory_entries(importance)')
            
            conn.commit()
        
        logger.info("Session memory database initialized")
    
    def _get_session_id(self, caller_number: str) -> str:
        """Generate consistent session ID for a caller."""
        # Use hash of phone number for consistent session ID
        return hashlib.sha256(caller_number.encode()).hexdigest()[:16]
    
    async def get_or_create_session(self, caller_number: str, call_id: str) -> SessionContext:
        """Get existing session or create new one."""
        if not ENABLE_SESSION_MEMORY:
            # Return empty session if memory disabled
            return SessionContext(
                session_id="disabled",
                caller_number=caller_number,
                first_call=datetime.utcnow(),
                last_call=datetime.utcnow(),
                total_calls=1,
                memory_entries=[],
                summary=None,
                preferences={}
            )
        
        session_id = self._get_session_id(caller_number)
        
        # Check if session is already in memory
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.last_call = datetime.utcnow()
            session.total_calls += 1
            return session
        
        # Load from database or create new
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT * FROM sessions WHERE session_id = ?', (session_id,)
            )
            row = cursor.fetchone()
            
            if row:
                # Load existing session
                session = SessionContext(
                    session_id=row[0],
                    caller_number=row[1],
                    first_call=datetime.fromisoformat(row[2]),
                    last_call=datetime.utcnow(),
                    total_calls=row[4] + 1,
                    memory_entries=[],
                    summary=row[5],
                    preferences=json.loads(row[6]) if row[6] else {}
                )
                
                # Load memory entries
                memory_cursor = conn.execute('''
                    SELECT timestamp, entry_type, content, metadata, importance
                    FROM memory_entries 
                    WHERE session_id = ? 
                    ORDER BY importance DESC, timestamp DESC
                    LIMIT ?
                ''', (session_id, MAX_MEMORY_ENTRIES_PER_SESSION))
                
                for mem_row in memory_cursor.fetchall():
                    entry = MemoryEntry(
                        session_id=session_id,
                        timestamp=datetime.fromisoformat(mem_row[0]),
                        entry_type=mem_row[1],
                        content=mem_row[2],
                        metadata=json.loads(mem_row[3]) if mem_row[3] else None,
                        importance=mem_row[4]
                    )
                    session.memory_entries.append(entry)
                
                # Update call count in database
                conn.execute('''
                    UPDATE sessions 
                    SET last_call = ?, total_calls = ?, updated_at = ?
                    WHERE session_id = ?
                ''', (
                    session.last_call.isoformat(),
                    session.total_calls,
                    datetime.utcnow().isoformat(),
                    session_id
                ))
                conn.commit()
                
            else:
                # Create new session
                now = datetime.utcnow()
                session = SessionContext(
                    session_id=session_id,
                    caller_number=caller_number,
                    first_call=now,
                    last_call=now,
                    total_calls=1,
                    memory_entries=[],
                    summary=None,
                    preferences={}
                )
                
                # Save to database
                conn.execute('''
                    INSERT INTO sessions 
                    (session_id, caller_number, first_call, last_call, total_calls, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    session_id,
                    caller_number,
                    now.isoformat(),
                    now.isoformat(),
                    1,
                    now.isoformat(),
                    now.isoformat()
                ))
                conn.commit()
        
        # Cache in memory
        self.active_sessions[session_id] = session
        
        logger.info(f"Session loaded/created: {session_id} for {caller_number} (call #{session.total_calls})")
        return session
    
    async def add_memory_entry(self, session_id: str, entry_type: str, content: str,
                             importance: int = 1, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Add a memory entry to a session."""
        if not ENABLE_SESSION_MEMORY or session_id == "disabled":
            return False
        
        entry = MemoryEntry(
            session_id=session_id,
            timestamp=datetime.utcnow(),
            entry_type=entry_type,
            content=content,
            metadata=metadata,
            importance=importance
        )
        
        # Add to active session if loaded
        if session_id in self.active_sessions:
            self.active_sessions[session_id].memory_entries.append(entry)
            
            # Keep only most important/recent entries
            if len(self.active_sessions[session_id].memory_entries) > MAX_MEMORY_ENTRIES_PER_SESSION:
                # Sort by importance desc, then timestamp desc
                self.active_sessions[session_id].memory_entries.sort(
                    key=lambda x: (x.importance, x.timestamp), reverse=True
                )
                self.active_sessions[session_id].memory_entries = \
                    self.active_sessions[session_id].memory_entries[:MAX_MEMORY_ENTRIES_PER_SESSION]
        
        # Save to database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO memory_entries (session_id, timestamp, entry_type, content, metadata, importance)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                entry.session_id,
                entry.timestamp.isoformat(),
                entry.entry_type,
                entry.content,
                json.dumps(metadata) if metadata else None,
                entry.importance
            ))
            conn.commit()
        
        logger.info(f"Memory entry added: {entry_type} for session {session_id}")
        return True
    
    async def update_session_summary(self, session_id: str, summary: str) -> bool:
        """Update session summary."""
        if not ENABLE_SESSION_MEMORY or session_id == "disabled":
            return False
        
        # Update active session
        if session_id in self.active_sessions:
            self.active_sessions[session_id].summary = summary
        
        # Update database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE sessions 
                SET summary = ?, updated_at = ?
                WHERE session_id = ?
            ''', (summary, datetime.utcnow().isoformat(), session_id))
            conn.commit()
        
        return True
    
    async def update_session_preferences(self, session_id: str, preferences: Dict[str, Any]) -> bool:
        """Update session preferences."""
        if not ENABLE_SESSION_MEMORY or session_id == "disabled":
            return False
        
        # Update active session
        if session_id in self.active_sessions:
            self.active_sessions[session_id].preferences.update(preferences)
        
        # Get current preferences to merge
        current_preferences = preferences
        if session_id in self.active_sessions:
            current_preferences = self.active_sessions[session_id].preferences.copy()
            current_preferences.update(preferences)
        
        # Update database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE sessions 
                SET preferences = ?, updated_at = ?
                WHERE session_id = ?
            ''', (
                json.dumps(current_preferences),
                datetime.utcnow().isoformat(),
                session_id
            ))
            conn.commit()
        
        return True
    
    def get_context_for_agent(self, session: SessionContext) -> str:
        """Generate context string for agent instructions."""
        if not ENABLE_SESSION_MEMORY or session.session_id == "disabled":
            return ""
        
        context_parts = []
        
        # Basic session info
        if session.total_calls > 1:
            context_parts.append(f"This is call #{session.total_calls} with this caller.")
            context_parts.append(f"First call was on {session.first_call.strftime('%Y-%m-%d')}.")
        
        # Session summary
        if session.summary:
            context_parts.append(f"Previous conversation summary: {session.summary}")
        
        # Recent important memories
        important_memories = [
            entry for entry in session.memory_entries 
            if entry.importance >= 7  # High importance memories
        ][:5]  # Last 5 important memories
        
        if important_memories:
            context_parts.append("Important context from previous conversations:")
            for memory in important_memories:
                context_parts.append(f"- {memory.content}")
        
        # Preferences
        if session.preferences:
            pref_strings = []
            for key, value in session.preferences.items():
                pref_strings.append(f"{key}: {value}")
            if pref_strings:
                context_parts.append(f"User preferences: {', '.join(pref_strings)}")
        
        # Recent conversation snippets
        recent_conversations = [
            entry for entry in session.memory_entries 
            if entry.entry_type == 'conversation'
        ][:3]  # Last 3 conversation snippets
        
        if recent_conversations:
            context_parts.append("Recent conversation topics:")
            for conv in recent_conversations:
                context_parts.append(f"- {conv.content[:100]}...")
        
        context = "\n".join(context_parts)
        
        # Truncate if too long
        if len(context) > CONTEXT_SUMMARY_LENGTH:
            context = context[:CONTEXT_SUMMARY_LENGTH] + "..."
        
        return context
    
    async def cleanup_old_sessions(self) -> int:
        """Clean up old sessions based on retention policy."""
        cutoff_date = datetime.utcnow() - timedelta(days=MEMORY_RETENTION_DAYS)
        
        with sqlite3.connect(self.db_path) as conn:
            # Count sessions to be deleted
            cursor = conn.execute(
                'SELECT COUNT(*) FROM sessions WHERE last_call < ?',
                (cutoff_date.isoformat(),)
            )
            count = cursor.fetchone()[0]
            
            if count > 0:
                # Delete memory entries first
                conn.execute('''
                    DELETE FROM memory_entries 
                    WHERE session_id IN (
                        SELECT session_id FROM sessions WHERE last_call < ?
                    )
                ''', (cutoff_date.isoformat(),))
                
                # Delete sessions
                conn.execute(
                    'DELETE FROM sessions WHERE last_call < ?',
                    (cutoff_date.isoformat(),)
                )
                conn.commit()
                
                logger.info(f"Cleaned up {count} old sessions")
        
        return count
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory system statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Session counts
            cursor = conn.execute('SELECT COUNT(*) FROM sessions')
            total_sessions = cursor.fetchone()[0]
            
            cursor = conn.execute('SELECT COUNT(*) FROM memory_entries')
            total_memories = cursor.fetchone()[0]
            
            # Active sessions (last 24 hours)
            yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
            cursor = conn.execute(
                'SELECT COUNT(*) FROM sessions WHERE last_call >= ?', (yesterday,)
            )
            active_sessions = cursor.fetchone()[0]
            
            # Average memories per session
            avg_memories = total_memories / total_sessions if total_sessions > 0 else 0
            
            return {
                'enabled': ENABLE_SESSION_MEMORY,
                'total_sessions': total_sessions,
                'total_memories': total_memories,
                'active_sessions_24h': active_sessions,
                'avg_memories_per_session': round(avg_memories, 2),
                'retention_days': MEMORY_RETENTION_DAYS,
                'max_entries_per_session': MAX_MEMORY_ENTRIES_PER_SESSION,
                'active_in_memory': len(self.active_sessions)
            }

# Global instance
memory_manager = SessionMemoryManager()