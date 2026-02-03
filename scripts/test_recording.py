#!/usr/bin/env python3
"""
Test script for call recording functionality.

Tests the call recording manager without needing actual calls.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from call_recording import recording_manager

async def test_recording_system():
    """Test the call recording system."""
    print("🧪 Testing Call Recording System\n")
    
    # Test 1: Start a call recording
    print("1. Testing call recording start...")
    call_id = "test_call_123"
    call_record = await recording_manager.start_call_recording(
        call_id=call_id,
        call_type="inbound",
        caller_number="+15551234567",
        callee_number="+15559876543",
        metadata={"test": True, "source": "test_script"}
    )
    
    if call_record:
        print(f"   ✅ Call recording started: {call_record.call_id}")
        print(f"   📁 Recording path: {call_record.recording_path}")
        print(f"   📄 Transcript path: {call_record.transcript_path}")
    else:
        print("   ❌ Failed to start recording (might be disabled)")
    
    # Test 2: Add transcript entries
    print("\n2. Testing transcript entries...")
    entries = [
        ("user", "Hello, this is a test call", "speech"),
        ("assistant", "Hi! How can I help you today?", "speech"),
        ("user", "I'm just testing the recording system", "speech"),
        ("assistant", "Great! The recording system is working perfectly.", "speech")
    ]
    
    for speaker, content, event_type in entries:
        success = await recording_manager.add_transcript_entry(
            call_id=call_id,
            speaker=speaker,
            content=content,
            event_type=event_type,
            metadata={"test_entry": True}
        )
        if success:
            print(f"   ✅ Added {speaker}: {content[:30]}...")
        else:
            print(f"   ❌ Failed to add transcript entry")
    
    # Test 3: Get call record
    print("\n3. Testing call record retrieval...")
    retrieved_call = await recording_manager.get_call_record(call_id)
    if retrieved_call:
        print(f"   ✅ Retrieved call: {retrieved_call.call_id}")
        print(f"   📊 Status: {retrieved_call.status}")
        print(f"   📝 Has transcript: {retrieved_call.has_transcript}")
    else:
        print("   ❌ Failed to retrieve call record")
    
    # Test 4: Get transcript
    print("\n4. Testing transcript retrieval...")
    transcript = await recording_manager.get_call_transcript(call_id)
    print(f"   📝 Transcript entries: {len(transcript)}")
    for entry in transcript:
        print(f"   📄 {entry.speaker}: {entry.content}")
    
    # Test 5: List calls
    print("\n5. Testing call listing...")
    calls = await recording_manager.list_calls(limit=10)
    print(f"   📋 Total calls found: {len(calls)}")
    for call in calls:
        print(f"   📞 {call.call_id}: {call.call_type} ({call.status})")
    
    # Test 6: End call recording
    print("\n6. Testing call recording end...")
    ended_call = await recording_manager.end_call_recording(call_id, "completed")
    if ended_call:
        print(f"   ✅ Call ended: {ended_call.call_id}")
        print(f"   ⏱️  Duration: {ended_call.duration_seconds:.2f}s")
    else:
        print("   ❌ Failed to end call recording")
    
    # Test 7: Storage stats
    print("\n7. Testing storage statistics...")
    stats = recording_manager.get_storage_stats()
    print(f"   📊 Total calls: {stats['total_calls']}")
    print(f"   📞 Active calls: {stats['active_calls']}")
    print(f"   🎵 Calls with audio: {stats['calls_with_audio']}")
    print(f"   📝 Calls with transcripts: {stats['calls_with_transcripts']}")
    print(f"   💾 Storage size: {stats['recordings_size_mb']:.2f} MB")
    print(f"   🎙️  Recording enabled: {stats['recording_enabled']}")
    print(f"   📄 Transcription enabled: {stats['transcription_enabled']}")
    
    # Test 8: Check transcript file
    if call_record and call_record.transcript_path:
        print(f"\n8. Testing transcript file...")
        transcript_path = Path(call_record.transcript_path)
        if transcript_path.exists():
            print(f"   ✅ Transcript file exists: {transcript_path}")
            with open(transcript_path) as f:
                transcript_data = json.load(f)
            print(f"   📄 File contains {len(transcript_data)} entries")
        else:
            print(f"   ❌ Transcript file not found: {transcript_path}")
    
    print("\n🎯 Call recording system test complete!")
    
    # Cleanup (optional)
    print("\nCleanup:")
    deleted = await recording_manager.delete_call_record(call_id, delete_files=True)
    if deleted:
        print("   ✅ Test call record deleted")
    else:
        print("   ❌ Failed to delete test call record")

if __name__ == "__main__":
    asyncio.run(test_recording_system())