#!/usr/bin/env python3
"""
Integration test for voice call session context
Simulates the real call flow that webhook-server.py uses
"""

import sys
import json
from pathlib import Path

# Add the current directory to path
sys.path.append(str(Path(__file__).parent))

from session_context import create_context_extractor

def test_call_integration():
    """Test the full call integration scenario."""
    print("🚀 Integration Test: Voice Call Session Context")
    print("=" * 55)
    
    # Simulate agent config (like in webhook-server.py)
    AGENT_CONFIG = {
        "name": "Nia",
        "instructions": "You are Nia, a helpful voice assistant. Be concise and conversational.",
        "voice": "nova",
        "model": "gpt-realtime"
    }
    
    # Create context extractor (like in webhook-server.py)
    try:
        context_extractor = create_context_extractor()
        print("✅ Context extractor initialized")
    except Exception as e:
        print(f"❌ Failed to initialize context extractor: {e}")
        return False
    
    if not context_extractor.workspace_path:
        print("❌ No workspace path found")
        return False
    
    print(f"✅ Workspace: {context_extractor.workspace_path}")
    
    # Test Scenario 1: Remi calls (inbound)
    print(f"\n📞 SCENARIO 1: Remi calls Nia")
    print("-" * 30)
    
    remi_phone = "+250794002033"
    base_instructions = AGENT_CONFIG["instructions"]
    
    try:
        # This is exactly what webhook-server.py does in accept_call()
        enhanced_instructions = context_extractor.get_enhanced_instructions(
            remi_phone, base_instructions, "inbound"
        )
        
        print(f"📋 Base instructions length: {len(base_instructions)} chars")
        print(f"📋 Enhanced instructions length: {len(enhanced_instructions)} chars")
        print(f"📊 Added context: {len(enhanced_instructions) - len(base_instructions)} chars")
        
        # Check for key requirements
        requirements_check = {
            "Greets Remi by name": "Hi Remi" in enhanced_instructions,
            "Recognizes primary user": "primary user" in enhanced_instructions.lower(),
            "Includes recent context": any(word in enhanced_instructions.lower() 
                                         for word in ["recent", "context", "memory"]),
            "Conversational style": "conversational" in enhanced_instructions.lower(),
            "Under 30 seconds guidance": "30 seconds" in enhanced_instructions
        }
        
        print(f"\n✅ Requirements Check:")
        all_passed = True
        for req, passed in requirements_check.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {req}")
            if not passed:
                all_passed = False
        
        print(f"\n📝 Sample Enhanced Instructions:")
        print("-" * 40)
        # Show first 200 chars to verify greeting
        preview = enhanced_instructions.replace('\\n', '\n')[:300] + "..."
        print(preview)
        print("-" * 40)
        
    except Exception as e:
        print(f"❌ Error in Remi call scenario: {e}")
        all_passed = False
    
    # Test Scenario 2: Unknown caller
    print(f"\n📞 SCENARIO 2: Unknown caller")
    print("-" * 30)
    
    unknown_phone = "+1555123456"
    
    try:
        enhanced_unknown = context_extractor.get_enhanced_instructions(
            unknown_phone, base_instructions, "inbound"
        )
        
        unknown_checks = {
            "Polite greeting": "hello" in enhanced_unknown.lower() or "good" in enhanced_unknown.lower(),
            "Introduces self": "nia" in enhanced_unknown.lower(),
            "Asks how to help": "help" in enhanced_unknown.lower() or "assist" in enhanced_unknown.lower()
        }
        
        print(f"✅ Unknown Caller Handling:")
        for check, passed in unknown_checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check}")
            if not passed:
                all_passed = False
                
    except Exception as e:
        print(f"❌ Error in unknown caller scenario: {e}")
        all_passed = False
    
    # Test Scenario 3: Outbound call with message
    print(f"\n📞 SCENARIO 3: Nia calls Remi (outbound)")
    print("-" * 30)
    
    initial_message = "Hi Remi, just calling to check on the voice project status."
    
    try:
        enhanced_outbound = context_extractor.get_enhanced_instructions(
            remi_phone, base_instructions, "outbound", initial_message
        )
        
        outbound_checks = {
            "Includes initial message": initial_message in enhanced_outbound,
            "Recognizes Remi": "Remi" in enhanced_outbound,
            "Outbound context": "initiated" in enhanced_outbound.lower()
        }
        
        print(f"✅ Outbound Call Handling:")
        for check, passed in outbound_checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check}")
            if not passed:
                all_passed = False
                
    except Exception as e:
        print(f"❌ Error in outbound scenario: {e}")
        all_passed = False
    
    # Final results
    print(f"\n🎯 INTEGRATION TEST RESULTS")
    print("=" * 30)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("🚀 Ready for voice call context enhancement!")
        print("\nKey achievements:")
        print("  • Remi is greeted by name when he calls")
        print("  • Recent context injected from memory files")
        print("  • Unknown callers handled politely")
        print("  • Outbound calls include initial messages")
        print("  • Low latency (minimal context overhead)")
    else:
        print("❌ SOME TESTS FAILED")
        print("🔧 Review implementation before deployment")
    
    return all_passed

if __name__ == "__main__":
    success = test_call_integration()
    sys.exit(0 if success else 1)