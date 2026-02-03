#!/usr/bin/env python3
"""
Call Recording and Transcription Module

Handles recording and transcription of OpenAI Realtime API calls.
Provides persistent storage for conversations, audio, and transcripts.
"""

import asyncio
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
import aiofiles
import asyncio
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Configuration
RECORDINGS_DIR = Path(os.getenv("RECORDINGS_DIR", "recordings"))
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "call_history.db"))
ENABLE_RECORDING = os.getenv("ENABLE_RECORDING", "true").lower() == "true"
ENABLE_TRANSCRIPTION = os.getenv("ENABLE_TRANSCRIPTION", "true").lower() == "true"
MAX_RECORDING_SIZE_MB = int(os.getenv("MAX_RECORDING_SIZE_MB", "100"))

@dataclass
class CallRecord:
    """Data class for call records."""
    call_id: str
    call_type: str  # 'inbound' or 'outbound'
    caller_number: Optional[str]
    callee_number: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    duration_seconds: Optional[float]
    status: str  # 'active', 'completed', 'failed', 'cancelled'
    recording_path: Optional[str]
    transcript_path: Optional[str]
    has_audio: bool = False
    has_transcript: bool = False
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class TranscriptEntry:
    """Data class for transcript entries."""
    call_id: str
    timestamp: datetime
    speaker: str  # 'user' or 'assistant'
    content: str
    event_type: str  # 'speech', 'audio_buffer', 'conversation_update'
    metadata: Optional[Dict[str, Any]] = None

class CallRecordingManager:
    """Manages call recording, transcription, and storage."""
    
    def __init__(self):
        self.db_path = DATABASE_PATH
        self.recordings_dir = RECORDINGS_DIR
        self.recordings_dir.mkdir(exist_ok=True)
        self._init_database()
        
    def _init_database(self):
        """Initialize SQLite database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS calls (
                    call_id TEXT PRIMARY KEY,
                    call_type TEXT NOT NULL,
                    caller_number TEXT,
                    callee_number TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    duration_seconds REAL,
                    status TEXT NOT NULL,
                    recording_path TEXT,
                    transcript_path TEXT,
                    has_audio BOOLEAN DEFAULT FALSE,
                    has_transcript BOOLEAN DEFAULT FALSE,
                    metadata TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS transcripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    speaker TEXT NOT NULL,
                    content TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (call_id) REFERENCES calls (call_id)
                )
            ''')
            
            # Indexes for better query performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_calls_started_at ON calls(started_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_transcripts_call_id ON transcripts(call_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_transcripts_timestamp ON transcripts(timestamp)')
            
            conn.commit()
        
        logger.info("Call recording database initialized")
    
    async def start_call_recording(self, call_id: str, call_type: str, 
                                 caller_number: Optional[str] = None, 
                                 callee_number: Optional[str] = None,
                                 metadata: Optional[Dict[str, Any]] = None) -> CallRecord:
        """Start recording a new call."""
        if not ENABLE_RECORDING:
            logger.debug(f"Recording disabled for call {call_id}")
            return None
            
        call_record = CallRecord(
            call_id=call_id,
            call_type=call_type,
            caller_number=caller_number,
            callee_number=callee_number,
            started_at=datetime.utcnow(),
            ended_at=None,
            duration_seconds=None,
            status='active',
            recording_path=None,
            transcript_path=None,
            metadata=metadata
        )
        
        # Create audio recording file path
        if ENABLE_RECORDING:
            timestamp_str = call_record.started_at.strftime("%Y%m%d_%H%M%S")
            call_record.recording_path = str(
                self.recordings_dir / f"{call_id}_{timestamp_str}.wav"
            )
        
        # Create transcript file path
        if ENABLE_TRANSCRIPTION:
            timestamp_str = call_record.started_at.strftime("%Y%m%d_%H%M%S")
            call_record.transcript_path = str(
                self.recordings_dir / f"{call_id}_{timestamp_str}_transcript.json"
            )
        
        # Save to database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO calls (call_id, call_type, caller_number, callee_number, 
                                 started_at, status, recording_path, transcript_path, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                call_record.call_id,
                call_record.call_type,
                call_record.caller_number,
                call_record.callee_number,
                call_record.started_at.isoformat(),
                call_record.status,
                call_record.recording_path,
                call_record.transcript_path,
                json.dumps(metadata) if metadata else None
            ))
            conn.commit()
        
        logger.info(f"Started recording for call {call_id}")
        return call_record
    
    async def end_call_recording(self, call_id: str, status: str = 'completed') -> Optional[CallRecord]:
        """End recording for a call."""
        with sqlite3.connect(self.db_path) as conn:
            # Get current call record
            cursor = conn.execute(
                'SELECT * FROM calls WHERE call_id = ?', (call_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                logger.warning(f"Call record not found for {call_id}")
                return None
            
            # Calculate duration
            ended_at = datetime.utcnow()
            started_at = datetime.fromisoformat(row[4])  # started_at column
            duration_seconds = (ended_at - started_at).total_seconds()
            
            # Update call record
            conn.execute('''
                UPDATE calls 
                SET ended_at = ?, duration_seconds = ?, status = ?
                WHERE call_id = ?
            ''', (ended_at.isoformat(), duration_seconds, status, call_id))
            conn.commit()
        
        logger.info(f"Ended recording for call {call_id} (duration: {duration_seconds:.1f}s)")
        return await self.get_call_record(call_id)
    
    async def add_transcript_entry(self, call_id: str, speaker: str, content: str,
                                 event_type: str = 'speech', 
                                 metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Add a transcript entry for a call."""
        if not ENABLE_TRANSCRIPTION:
            return False
            
        entry = TranscriptEntry(
            call_id=call_id,
            timestamp=datetime.utcnow(),
            speaker=speaker,
            content=content,
            event_type=event_type,
            metadata=metadata
        )
        
        # Save to database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO transcripts (call_id, timestamp, speaker, content, event_type, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                entry.call_id,
                entry.timestamp.isoformat(),
                entry.speaker,
                entry.content,
                entry.event_type,
                json.dumps(metadata) if metadata else None
            ))
            conn.commit()
        
        # Update call record to indicate it has transcript
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'UPDATE calls SET has_transcript = TRUE WHERE call_id = ?',
                (call_id,)
            )
            conn.commit()
        
        # Also append to transcript file for easy reading
        call_record = await self.get_call_record(call_id)
        if call_record and call_record.transcript_path:
            await self._append_to_transcript_file(call_record.transcript_path, entry)
        
        return True
    
    async def _append_to_transcript_file(self, transcript_path: str, entry: TranscriptEntry):
        """Append transcript entry to JSON file."""
        try:
            # Read existing transcript
            transcript_file = Path(transcript_path)
            if transcript_file.exists():
                async with aiofiles.open(transcript_file, 'r') as f:
                    content = await f.read()
                    transcript_data = json.loads(content) if content.strip() else []
            else:
                transcript_data = []
            
            # Append new entry
            transcript_data.append({
                'timestamp': entry.timestamp.isoformat(),
                'speaker': entry.speaker,
                'content': entry.content,
                'event_type': entry.event_type,
                'metadata': entry.metadata
            })
            
            # Write back to file
            async with aiofiles.open(transcript_file, 'w') as f:
                await f.write(json.dumps(transcript_data, indent=2))
                
        except Exception as e:
            logger.error(f"Error writing transcript file {transcript_path}: {e}")
    
    async def get_call_record(self, call_id: str) -> Optional[CallRecord]:
        """Get call record by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT * FROM calls WHERE call_id = ?', (call_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return CallRecord(
                call_id=row[0],
                call_type=row[1],
                caller_number=row[2],
                callee_number=row[3],
                started_at=datetime.fromisoformat(row[4]),
                ended_at=datetime.fromisoformat(row[5]) if row[5] else None,
                duration_seconds=row[6],
                status=row[7],
                recording_path=row[8],
                transcript_path=row[9],
                has_audio=bool(row[10]),
                has_transcript=bool(row[11]),
                metadata=json.loads(row[12]) if row[12] else None
            )
    
    async def list_calls(self, limit: int = 50, offset: int = 0, 
                        call_type: Optional[str] = None) -> List[CallRecord]:
        """List call records with pagination."""
        query = 'SELECT * FROM calls'
        params = []
        
        if call_type:
            query += ' WHERE call_type = ?'
            params.append(call_type)
        
        query += ' ORDER BY started_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            calls = []
            for row in rows:
                calls.append(CallRecord(
                    call_id=row[0],
                    call_type=row[1],
                    caller_number=row[2],
                    callee_number=row[3],
                    started_at=datetime.fromisoformat(row[4]),
                    ended_at=datetime.fromisoformat(row[5]) if row[5] else None,
                    duration_seconds=row[6],
                    status=row[7],
                    recording_path=row[8],
                    transcript_path=row[9],
                    has_audio=bool(row[10]),
                    has_transcript=bool(row[11]),
                    metadata=json.loads(row[12]) if row[12] else None
                ))
            
            return calls
    
    async def get_call_transcript(self, call_id: str) -> List[TranscriptEntry]:
        """Get transcript entries for a call."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT call_id, timestamp, speaker, content, event_type, metadata
                FROM transcripts 
                WHERE call_id = ? 
                ORDER BY timestamp ASC
            ''', (call_id,))
            rows = cursor.fetchall()
            
            entries = []
            for row in rows:
                entries.append(TranscriptEntry(
                    call_id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    speaker=row[2],
                    content=row[3],
                    event_type=row[4],
                    metadata=json.loads(row[5]) if row[5] else None
                ))
            
            return entries
    
    async def delete_call_record(self, call_id: str, delete_files: bool = False) -> bool:
        """Delete call record and optionally associated files."""
        # Get call record first
        call_record = await self.get_call_record(call_id)
        if not call_record:
            return False
        
        # Delete from database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM transcripts WHERE call_id = ?', (call_id,))
            conn.execute('DELETE FROM calls WHERE call_id = ?', (call_id,))
            conn.commit()
        
        # Delete associated files if requested
        if delete_files:
            if call_record.recording_path:
                recording_file = Path(call_record.recording_path)
                if recording_file.exists():
                    recording_file.unlink()
            
            if call_record.transcript_path:
                transcript_file = Path(call_record.transcript_path)
                if transcript_file.exists():
                    transcript_file.unlink()
        
        logger.info(f"Deleted call record {call_id}")
        return True
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Call counts
            cursor = conn.execute('SELECT COUNT(*) FROM calls')
            total_calls = cursor.fetchone()[0]
            
            cursor = conn.execute('SELECT COUNT(*) FROM calls WHERE status = "active"')
            active_calls = cursor.fetchone()[0]
            
            cursor = conn.execute('SELECT COUNT(*) FROM calls WHERE has_audio = TRUE')
            calls_with_audio = cursor.fetchone()[0]
            
            cursor = conn.execute('SELECT COUNT(*) FROM calls WHERE has_transcript = TRUE')
            calls_with_transcripts = cursor.fetchone()[0]
            
            # Storage usage
            recordings_size = sum(f.stat().st_size for f in self.recordings_dir.rglob('*') if f.is_file())
            
            return {
                'total_calls': total_calls,
                'active_calls': active_calls,
                'calls_with_audio': calls_with_audio,
                'calls_with_transcripts': calls_with_transcripts,
                'recordings_directory': str(self.recordings_dir),
                'recordings_size_mb': recordings_size / 1024 / 1024,
                'recording_enabled': ENABLE_RECORDING,
                'transcription_enabled': ENABLE_TRANSCRIPTION
            }

# Global instance
recording_manager = CallRecordingManager()