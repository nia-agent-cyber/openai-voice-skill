#!/usr/bin/env python3
"""
Example script demonstrating OpenClaw Session Context Integration

This shows how the session context system works for voice calls.
"""

import asyncio
import json
import logging
from pathlib import Path

from openclaw_bridge import create_openclaw_bridge
from session_context import create_context_extractor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def demo_context_extraction():
    """Demonstrate context extraction and formatting."""
    
    print("🎯 OpenClaw Session Context Demo")
    print("=" * 50)
    
    # Create context extractor
    extractor = create_context_extractor()
    
    # Extract recent context
    print("\n1. Extracting recent session context...")
    context = extractor.extract_recent_context(
        hours_back=24,
        max_messages=10
    )
    
    print(f"   Found {len(context['conversation_history'])} recent messages")
    print(f"   Found {len(context['ongoing_projects'])} projects")
    print(f"   Found {len(context['recent_decisions'])} decisions")
    print(f"   Context summary: {context['context_summary']}")
    
    # Create OpenClaw bridge
    bridge = create_openclaw_bridge()
    
    # Simulate caller identification
    print("\n2. Testing caller identification...")
    
    test_numbers = ["+1234567890", "+1999999999"]  # Known and unknown
    
    for phone in test_numbers:
        caller_info = await bridge.identify_caller(phone)
        print(f"   {phone} -> {caller_info['name']} ({caller_info['relationship']})")
    
    # Demonstrate context formatting for voice
    print("\n3. Formatting context for voice call...")
    
    caller_info = await bridge.identify_caller("+1234567890")
    caller_context = await bridge.get_caller_context(caller_info)
    
    # Format for inbound call
    inbound_instructions = bridge.format_context_for_voice(
        caller_context,
        call_type="inbound"
    )
    
    print(f"   Generated {len(inbound_instructions)} chars of instructions")
    print("\n   Sample instructions:")
    print("   " + "-" * 40)
    print("   " + inbound_instructions[:200] + "...")
    print("   " + "-" * 40)
    
    # Format for outbound call
    outbound_instructions = bridge.format_context_for_voice(
        caller_context,
        call_type="outbound",
        initial_message="Following up on our conversation about the voice integration project"
    )
    
    print(f"\n   Outbound instructions: {len(outbound_instructions)} chars")
    print("   " + outbound_instructions[:200] + "...")
    
    print("\n✅ Context demo completed!")

async def demo_call_simulation():
    """Simulate a complete call flow with context."""
    
    print("\n📞 Call Flow Simulation")
    print("=" * 50)
    
    bridge = create_openclaw_bridge()
    
    # Simulate inbound call
    print("\n1. Simulating inbound call from +1234567890...")
    
    caller_info = await bridge.identify_caller("+1234567890")
    context = await bridge.get_caller_context(caller_info)
    
    print(f"   Caller: {caller_info['name']}")
    print(f"   Context items: {len(context['conversation_history'])} messages")
    
    # Simulate call context updates during call
    print("\n2. Simulating call context updates...")
    
    call_id = "sim_call_123"
    
    await bridge.update_call_context(call_id, {
        "user_mentioned_project": "voice integration",
        "discussed_topics": ["OpenAI API", "session context", "memory files"],
        "call_progress": "good"
    })
    
    print(f"   Updated context for call {call_id}")
    
    # Simulate call completion
    print("\n3. Simulating call completion...")
    
    call_summary = {
        "call_id": call_id,
        "caller_name": caller_info["name"],
        "duration_seconds": 180.5,
        "summary": "Discussed voice integration project progress",
        "key_points": [
            "Session context working well",
            "Need to test with different users", 
            "Deploy to production next week"
        ]
    }
    
    await bridge.finalize_call_context(call_id, call_summary)
    
    print(f"   Finalized call context and saved to memory")
    print("\n✅ Call simulation completed!")

def show_config_example():
    """Show example configuration setup."""
    
    print("\n⚙️  Configuration Setup")
    print("=" * 50)
    
    print("\n1. Phone Mapping Configuration:")
    print("   File: config/phone_mapping.json")
    print("   Purpose: Map phone numbers to OpenClaw users/sessions")
    
    example_config = {
        "+1234567890": {
            "name": "Your Name",
            "session_id": "main",
            "relationship": "primary_user",
            "preferred_name": "Your Name",
            "context_level": "full"
        }
    }
    
    print("\n   Example entry:")
    print("   " + json.dumps(example_config, indent=4))
    
    print("\n2. Environment Variables:")
    print("   OPENCLAW_WORKSPACE=/path/to/workspace")
    print("   PHONE_USER_MAPPING='{...}'  # JSON mapping as fallback")
    print("   OPENCLAW_API_URL=http://localhost:3000  # If using API")
    print("   OPENCLAW_API_KEY=your_api_key  # If using API")
    
    print("\n3. Workspace Structure Expected:")
    print("   workspace/")
    print("   ├── SOUL.md          # Agent identity")
    print("   ├── USER.md          # User profile")  
    print("   ├── MEMORY.md        # Long-term memory")
    print("   └── memory/")
    print("       ├── 2024-02-04.md  # Daily memory files")
    print("       └── ...")
    
    print("\n✅ Configuration info displayed!")

async def main():
    """Run the demo."""
    
    try:
        await demo_context_extraction()
        await demo_call_simulation()
        show_config_example()
        
        print("\n🎉 Demo completed successfully!")
        print("\nNext steps:")
        print("1. Configure your phone mapping in config/phone_mapping.json")
        print("2. Ensure your OpenClaw workspace has SOUL.md, USER.md, etc.")
        print("3. Start the webhook server: python webhook-server.py")
        print("4. Make a test call and see the context in action!")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"\n❌ Demo failed: {e}")
        print("\nTroubleshooting:")
        print("- Check that you're in an OpenClaw workspace directory")
        print("- Ensure memory files exist in memory/ subdirectory")
        print("- Check file permissions and paths")

if __name__ == "__main__":
    asyncio.run(main())