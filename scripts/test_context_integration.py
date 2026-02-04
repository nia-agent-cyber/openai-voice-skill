#!/usr/bin/env python3
"""
Test script for OpenClaw Session Context Integration

This tests the key functionality of the session context system.
"""

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

# Setup test environment
os.environ["OPENCLAW_WORKSPACE"] = str(Path.cwd() / "test_workspace")

from session_context import create_context_extractor
from openclaw_bridge import create_openclaw_bridge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContextIntegrationTest:
    """Test suite for session context integration."""
    
    def __init__(self):
        self.test_workspace = Path("test_workspace")
        self.passed_tests = 0
        self.total_tests = 0
        
    def setup_test_workspace(self):
        """Create a test workspace with sample files."""
        print("📁 Setting up test workspace...")
        
        # Create directories
        self.test_workspace.mkdir(exist_ok=True)
        (self.test_workspace / "memory").mkdir(exist_ok=True)
        (self.test_workspace / "config").mkdir(exist_ok=True)
        
        # Create SOUL.md
        soul_content = """# Agent Identity

You are Nia, an AI assistant. You're enthusiastic, positive, and curious about technology.
You work with developers on building agent infrastructure and AI systems.
"""
        (self.test_workspace / "SOUL.md").write_text(soul_content)
        
        # Create USER.md  
        user_content = """# User Profile

Primary user: Remi, a developer working on AI agent systems.
Interested in OpenAI APIs, voice integration, and automation.
Prefers direct, technical communication with occasional humor.
"""
        (self.test_workspace / "USER.md").write_text(user_content)
        
        # Create MEMORY.md
        memory_content = """# Long-term Memory

## Key Relationships
- Remi: Primary user, technical lead on voice projects
- Team: Working on OpenClaw agent infrastructure

## Important Projects  
- OpenAI Voice Skill: Integrating voice calls with session context
- Agent Memory System: Persistent memory across sessions

## Preferences
- Remi likes concise technical explanations
- Prefers to be addressed by name in voice calls
- Interested in practical implementations over theory
"""
        (self.test_workspace / "MEMORY.md").write_text(memory_content)
        
        # Create daily memory file
        today = datetime.now().strftime("%Y-%m-%d")
        daily_content = """# Daily Memory - {}

## 09:30 - Technical Discussion
**Remi:** Let's implement session context for voice calls
**Nia:** Great idea! This will make calls much more natural

## 10:15 - Planning Session  
**Remi:** We need to extract conversation history and format it for OpenAI
**Nia:** I'll work on the context extraction logic

## 14:20 - Implementation Progress
**Remi:** The session context bridge is working well in tests
**Nia:** Excellent! The voice calls should now have proper context

## Recent Decisions
- Decided to use phone number mapping for caller identification
- Will cache context for 5 minutes to improve performance
- Going with markdown format for memory files
""".format(today)
        
        (self.test_workspace / "memory" / f"{today}.md").write_text(daily_content)
        
        # Create phone mapping
        phone_mapping = {
            "+1234567890": {
                "name": "Remi",
                "session_id": "main", 
                "relationship": "primary_user",
                "preferred_name": "Remi",
                "context_level": "full"
            },
            "+1987654321": {
                "name": "Test Team Member",
                "session_id": "team",
                "relationship": "team_member", 
                "preferred_name": "teammate",
                "context_level": "work_only"
            },
            "+1555000000": {
                "name": "Unknown Person", 
                "session_id": "guest",
                "relationship": "unknown",
                "preferred_name": "caller",
                "context_level": "limited"
            }
        }
        
        mapping_file = self.test_workspace / "phone_mapping.json"
        mapping_file.write_text(json.dumps(phone_mapping, indent=2))
        
        print(f"   ✅ Test workspace created at {self.test_workspace}")
    
    def cleanup_test_workspace(self):
        """Clean up test workspace."""
        import shutil
        if self.test_workspace.exists():
            shutil.rmtree(self.test_workspace)
            print(f"   🧹 Cleaned up test workspace")
    
    async def test_context_extraction(self):
        """Test basic context extraction."""
        self.total_tests += 1
        print("\n🧪 Testing context extraction...")
        
        try:
            extractor = create_context_extractor()
            context = extractor.extract_recent_context(hours_back=24, max_messages=10)
            
            # Check extracted data
            assert len(context["conversation_history"]) > 0, "No conversation history extracted"
            assert context["user_info"].get("agent_identity"), "No agent identity found"
            assert context["context_summary"], "No context summary generated"
            
            print(f"   ✅ Found {len(context['conversation_history'])} conversations")
            print(f"   ✅ Generated context summary: {context['context_summary'][:100]}...")
            
            self.passed_tests += 1
            
        except Exception as e:
            print(f"   ❌ Context extraction failed: {e}")
    
    async def test_caller_identification(self):
        """Test caller identification by phone number."""
        self.total_tests += 1
        print("\n🧪 Testing caller identification...")
        
        try:
            bridge = create_openclaw_bridge()
            
            # Test known caller
            caller_info = await bridge.identify_caller("+1234567890")
            assert caller_info["name"] == "Remi", f"Expected Remi, got {caller_info['name']}"
            assert caller_info["known_caller"] == True, "Should be known caller"
            
            # Test unknown caller  
            unknown_info = await bridge.identify_caller("+1999999999")
            assert unknown_info["known_caller"] == False, "Should be unknown caller"
            
            print(f"   ✅ Known caller: {caller_info['name']} ({caller_info['relationship']})")
            print(f"   ✅ Unknown caller handled: {unknown_info['name']}")
            
            self.passed_tests += 1
            
        except Exception as e:
            print(f"   ❌ Caller identification failed: {e}")
    
    async def test_context_generation(self):
        """Test context generation for voice calls."""
        self.total_tests += 1
        print("\n🧪 Testing context generation for voice...")
        
        try:
            bridge = create_openclaw_bridge()
            
            # Get caller context
            caller_info = await bridge.identify_caller("+1234567890")
            context = await bridge.get_caller_context(caller_info)
            
            # Test inbound call formatting
            inbound_instructions = bridge.format_context_for_voice(
                context, 
                call_type="inbound"
            )
            
            assert len(inbound_instructions) > 100, "Instructions too short"
            assert "Remi" in inbound_instructions, "Caller name not in instructions"
            assert "voice conversation" in inbound_instructions.lower(), "Missing voice guidance"
            
            # Test outbound call formatting
            outbound_instructions = bridge.format_context_for_voice(
                context,
                call_type="outbound", 
                initial_message="Following up on our voice integration project"
            )
            
            assert "Following up" in outbound_instructions, "Initial message not included"
            assert len(outbound_instructions) > len(inbound_instructions), "Outbound should be longer"
            
            print(f"   ✅ Inbound instructions: {len(inbound_instructions)} chars")
            print(f"   ✅ Outbound instructions: {len(outbound_instructions)} chars")
            print(f"   ✅ Instructions include caller name and context")
            
            self.passed_tests += 1
            
        except Exception as e:
            print(f"   ❌ Context generation failed: {e}")
    
    async def test_context_security_levels(self):
        """Test different context security levels."""
        self.total_tests += 1
        print("\n🧪 Testing context security levels...")
        
        try:
            bridge = create_openclaw_bridge()
            
            # Test primary user (full context)
            primary_caller = await bridge.identify_caller("+1234567890")
            primary_context = await bridge.get_caller_context(primary_caller)
            
            # Test team member (filtered context)
            team_caller = await bridge.identify_caller("+1987654321") 
            team_context = await bridge.get_caller_context(team_caller)
            
            # Test unknown caller (limited context)
            unknown_caller = await bridge.identify_caller("+1555000000")
            unknown_context = await bridge.get_caller_context(unknown_caller)
            
            # Verify context levels
            assert len(primary_context["conversation_history"]) > 0, "Primary user should have conversations"
            assert len(unknown_context["conversation_history"]) == 0, "Unknown caller should have no conversations"
            
            print(f"   ✅ Primary user context: {len(primary_context['conversation_history'])} conversations")
            print(f"   ✅ Team member context: {len(team_context['conversation_history'])} conversations")  
            print(f"   ✅ Unknown caller context: {len(unknown_context['conversation_history'])} conversations")
            
            self.passed_tests += 1
            
        except Exception as e:
            print(f"   ❌ Context security levels test failed: {e}")
    
    async def test_call_memory_integration(self):
        """Test call memory recording."""
        self.total_tests += 1
        print("\n🧪 Testing call memory integration...")
        
        try:
            bridge = create_openclaw_bridge()
            
            # Simulate call context update
            call_id = "test_call_123"
            
            await bridge.update_call_context(call_id, {
                "test_update": True,
                "discussed_topics": ["voice integration", "context extraction"]
            })
            
            # Simulate call finalization
            call_summary = {
                "call_id": call_id,
                "caller_name": "Remi",
                "duration_seconds": 120.5,
                "summary": "Test call for context integration",
                "key_points": ["Context working", "Memory integration successful"]
            }
            
            await bridge.finalize_call_context(call_id, call_summary)
            
            # Check if memory was created
            today = datetime.now().strftime("%Y-%m-%d")
            memory_file = self.test_workspace / "memory" / f"{today}.md"
            
            if memory_file.exists():
                content = memory_file.read_text()
                assert "voice_call" in content.lower(), "Call type not recorded"
                assert "Remi" in content, "Caller name not recorded"
                
            print("   ✅ Call context updated successfully")
            print("   ✅ Call memory recorded")
            
            self.passed_tests += 1
            
        except Exception as e:
            print(f"   ❌ Call memory integration failed: {e}")
    
    def test_phone_mapping_config(self):
        """Test phone mapping configuration."""
        self.total_tests += 1
        print("\n🧪 Testing phone mapping configuration...")
        
        try:
            bridge = create_openclaw_bridge()
            
            # Check that mapping was loaded
            assert len(bridge.user_phone_mapping) >= 3, "Not enough phone mappings loaded"
            
            # Check specific mapping
            remi_mapping = bridge.user_phone_mapping.get("+1234567890")
            assert remi_mapping, "Remi's mapping not found"
            assert remi_mapping["name"] == "Remi", "Wrong name in mapping"
            assert remi_mapping["relationship"] == "primary_user", "Wrong relationship"
            
            print("   ✅ Phone mapping configuration loaded")
            print(f"   ✅ Found {len(bridge.user_phone_mapping)} phone mappings")
            
            self.passed_tests += 1
            
        except Exception as e:
            print(f"   ❌ Phone mapping test failed: {e}")
    
    async def run_all_tests(self):
        """Run all tests."""
        print("🧪 Starting OpenClaw Session Context Integration Tests")
        print("=" * 60)
        
        # Setup
        self.setup_test_workspace()
        
        try:
            # Run tests
            await self.test_context_extraction()
            await self.test_caller_identification()
            await self.test_context_generation()
            await self.test_context_security_levels()
            await self.test_call_memory_integration()
            self.test_phone_mapping_config()
            
            # Results
            print(f"\n📊 Test Results: {self.passed_tests}/{self.total_tests} passed")
            
            if self.passed_tests == self.total_tests:
                print("✅ All tests passed! Session context integration is working correctly.")
                return True
            else:
                print(f"❌ {self.total_tests - self.passed_tests} tests failed.")
                return False
                
        finally:
            # Cleanup
            self.cleanup_test_workspace()

async def main():
    """Run the test suite."""
    
    test_suite = ContextIntegrationTest()
    
    success = await test_suite.run_all_tests()
    
    if success:
        print("\n🎉 Session Context Integration is ready!")
        print("\nNext steps:")
        print("1. Configure your real phone mapping in config/phone_mapping.json")
        print("2. Ensure your OpenClaw workspace has proper memory files") 
        print("3. Start the webhook server: python webhook-server.py")
        print("4. Make a test call and enjoy context-aware voice conversations!")
    else:
        print("\n🔧 Some tests failed. Please check the errors above.")
        print("Make sure you're in a proper OpenClaw workspace directory.")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)