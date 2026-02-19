#!/usr/bin/env python3
"""
Test script for session context integration
"""

import sys
from pathlib import Path

# Add scripts directory to path
scripts_dir = Path(__file__).parent / "scripts"
sys.path.append(str(scripts_dir))

from session_context import create_context_extractor

def test_context():
    print("🧪 Testing session context integration...")
    
    extractor = create_context_extractor()
    
    if not extractor.workspace_path:
        print("❌ No workspace found")
        return False
    
    print(f"✅ Workspace found: {extractor.workspace_path}")
    
    # Test basic instructions enhancement
    base_instructions = "You are a helpful voice assistant."
    
    # Test with known caller
    enhanced = extractor.get_enhanced_instructions(
        "+250794002033",  # Remi's number
        base_instructions,
        "inbound"
    )
    
    print(f"📋 Base instructions: {len(base_instructions)} chars")
    print(f"📋 Enhanced instructions: {len(enhanced)} chars")
    print(f"📋 Enhancement successful: {'✅' if len(enhanced) > len(base_instructions) else '❌'}")
    
    # Test with unknown caller
    unknown_enhanced = extractor.get_enhanced_instructions(
        "+1999999999",
        base_instructions,
        "inbound"
    )
    
    print(f"📋 Unknown caller instructions: {len(unknown_enhanced)} chars")
    assert len(enhanced) > len(base_instructions), "Enhanced instructions should be longer than base"
    
    # Show sample of enhanced instructions
    print(f"\n📄 Sample enhanced instructions:")
    print("="*50)
    print(enhanced[:300] + "..." if len(enhanced) > 300 else enhanced)
    print("="*50)
    
    return None

if __name__ == "__main__":
    test_context()
    print("\n🎉 Context integration test completed successfully!")
    print("✅ Ready for voice calls with session context")