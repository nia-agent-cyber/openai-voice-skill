#!/usr/bin/env python3
"""
Test script for session memory functionality.

Tests the session memory manager without needing actual voice calls.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from session_memory import memory_manager

async def test_session_memory():
    """Test the session memory system."""
    print("🧪 Testing Session Memory System\n")
    
    # Test 1: Create a new session
    print("1. Testing session creation...")
    caller_number = "+15551234567"
    call_id = "test_call_memory_123"
    
    session = await memory_manager.get_or_create_session(caller_number, call_id)
    
    if session:
        print(f"   ✅ Session created: {session.session_id}")
        print(f"   📞 Caller: {session.caller_number}")
        print(f"   📊 Call count: {session.total_calls}")
        print(f"   🕒 First call: {session.first_call}")
    else:
        print("   ❌ Failed to create session")
        return
    
    # Test 2: Add memory entries
    print("\n2. Testing memory entries...")
    memory_entries = [
        ("conversation", "User asked about the weather in New York", 5),
        ("fact", "User prefers metric units for temperature", 8),
        ("conversation", "Discussed upcoming meeting tomorrow at 2 PM", 7),
        ("preference", "User likes brief responses", 6),
        ("function_call", "Called get_weather for New York, returned 22°C sunny", 4)
    ]
    
    for entry_type, content, importance in memory_entries:
        success = await memory_manager.add_memory_entry(
            session_id=session.session_id,
            entry_type=entry_type,
            content=content,
            importance=importance,
            metadata={"test": True, "call_id": call_id}
        )
        if success:
            print(f"   ✅ Added {entry_type}: {content[:40]}...")
        else:
            print(f"   ❌ Failed to add memory entry")
    
    # Test 3: Test session context generation
    print("\n3. Testing context generation...")
    context = memory_manager.get_context_for_agent(session)
    if context:
        print(f"   ✅ Generated context ({len(context)} chars)")
        print(f"   📝 Context preview: {context[:150]}...")
    else:
        print("   ❌ No context generated")
    
    # Test 4: Test session retrieval
    print("\n4. Testing session retrieval...")
    retrieved_session = await memory_manager.get_or_create_session(caller_number, "test_call_2")
    if retrieved_session:
        print(f"   ✅ Retrieved session: {retrieved_session.session_id}")
        print(f"   📊 Updated call count: {retrieved_session.total_calls}")
        print(f"   💭 Memory entries: {len(retrieved_session.memory_entries)}")
    else:
        print("   ❌ Failed to retrieve session")
    
    # Test 5: Test session summary update
    print("\n5. Testing session summary...")
    summary = "User inquired about weather and discussed an important meeting. Prefers metric units and brief responses."
    success = await memory_manager.update_session_summary(session.session_id, summary)
    if success:
        print(f"   ✅ Summary updated")
        print(f"   📄 Summary: {summary}")
    else:
        print("   ❌ Failed to update summary")
    
    # Test 6: Test preferences update
    print("\n6. Testing preferences...")
    preferences = {
        "temperature_unit": "celsius",
        "response_style": "brief",
        "timezone": "EST"
    }
    success = await memory_manager.update_session_preferences(session.session_id, preferences)
    if success:
        print(f"   ✅ Preferences updated")
        print(f"   ⚙️  Preferences: {preferences}")
    else:
        print("   ❌ Failed to update preferences")
    
    # Test 7: Test context with summary and preferences
    print("\n7. Testing enhanced context...")
    # Reload session to get updated data
    enhanced_session = await memory_manager.get_or_create_session(caller_number, "test_call_3")
    enhanced_context = memory_manager.get_context_for_agent(enhanced_session)
    
    print(f"   📝 Enhanced context ({len(enhanced_context)} chars)")
    print(f"   🔍 Context includes summary: {'summary' in enhanced_context.lower()}")
    print(f"   🔍 Context includes preferences: {'preferences' in enhanced_context.lower()}")
    
    # Test 8: Test different caller (new session)
    print("\n8. Testing multiple sessions...")
    caller_2 = "+15559876543"
    session_2 = await memory_manager.get_or_create_session(caller_2, "test_call_other")
    
    print(f"   ✅ New session created: {session_2.session_id}")
    print(f"   📊 New session calls: {session_2.total_calls}")
    print(f"   🆔 Different session ID: {session.session_id != session_2.session_id}")
    
    # Test 9: Memory statistics
    print("\n9. Testing memory statistics...")
    stats = memory_manager.get_memory_stats()
    print(f"   📊 Total sessions: {stats['total_sessions']}")
    print(f"   📝 Total memories: {stats['total_memories']}")
    print(f"   🔄 Active sessions (24h): {stats['active_sessions_24h']}")
    print(f"   📈 Avg memories/session: {stats['avg_memories_per_session']}")
    print(f"   💾 Active in memory: {stats['active_in_memory']}")
    print(f"   ⚙️  Memory enabled: {stats['enabled']}")
    
    # Test 10: Memory cleanup simulation
    print("\n10. Testing memory cleanup...")
    # This won't delete anything since our test data is new
    deleted_count = await memory_manager.cleanup_old_sessions()
    print(f"   🧹 Cleaned up {deleted_count} old sessions")
    
    # Test 11: Test memory with disabled setting (simulate)
    print("\n11. Testing disabled memory...")
    # Import the module-level variable
    from session_memory import ENABLE_SESSION_MEMORY
    
    # Create a mock disabled session
    disabled_session = await memory_manager.get_or_create_session("+15551111111", "disabled_test")
    if disabled_session.session_id == "disabled" or not ENABLE_SESSION_MEMORY:
        print("   ✅ Memory correctly disabled when setting is off")
    else:
        print("   ⚠️  Memory still working (current setting is enabled)")
    
    print("\n🎯 Session memory system test complete!")
    
    # Test database verification
    print("\n📋 Database verification:")
    if Path(memory_manager.db_path).exists():
        print(f"   ✅ Database file exists: {memory_manager.db_path}")
        print(f"   📏 File size: {Path(memory_manager.db_path).stat().st_size} bytes")
    else:
        print(f"   ❌ Database file missing: {memory_manager.db_path}")

if __name__ == "__main__":
    asyncio.run(test_session_memory())