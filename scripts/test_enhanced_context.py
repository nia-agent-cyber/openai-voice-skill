#!/usr/bin/env python3
"""
Test script for enhanced session context extraction
"""

import sys
import os
from pathlib import Path

# Add the current directory to path to import session_context
sys.path.append(str(Path(__file__).parent))

from session_context import create_context_extractor

def test_context_extraction():
    """Test the enhanced context extraction functionality."""
    print("🧪 Testing Enhanced Session Context Extraction")
    print("=" * 50)
    
    # Create context extractor
    extractor = create_context_extractor()
    
    if not extractor.workspace_path:
        print("❌ No workspace path found")
        return False
    
    print(f"✅ Workspace found: {extractor.workspace_path}")
    
    # Test with Remi's number
    remi_phone = "+250794002033"
    base_instructions = "You are Nia, a helpful voice assistant."
    
    print(f"\n📞 Testing context for Remi ({remi_phone})")
    
    # Test enhanced instructions
    enhanced = extractor.get_enhanced_instructions(
        remi_phone, base_instructions, "inbound"
    )
    
    print(f"\n📝 Enhanced Instructions ({len(enhanced)} chars):")
    print("-" * 30)
    print(enhanced)
    print("-" * 30)
    
    # Test with unknown number
    unknown_phone = "+1999888777"
    print(f"\n📞 Testing context for unknown caller ({unknown_phone})")
    
    enhanced_unknown = extractor.get_enhanced_instructions(
        unknown_phone, base_instructions, "inbound"
    )
    
    print(f"\n📝 Enhanced Instructions for Unknown ({len(enhanced_unknown)} chars):")
    print("-" * 30)
    print(enhanced_unknown)
    print("-" * 30)
    
    # Verify key features
    checks = [
        ("Remi greeting", "Hi Remi" in enhanced),
        ("Primary user context", "primary user" in enhanced.lower()),
        ("Recent context", "recent" in enhanced.lower() or "context" in enhanced.lower()),
        ("Unknown caller handling", "unknown caller" in enhanced_unknown.lower()),
        ("Politeness for unknown", "polite" in enhanced_unknown.lower())
    ]
    
    print("\n✅ Feature Checks:")
    for check_name, result in checks:
        status = "✅" if result else "❌"
        print(f"{status} {check_name}")
    
    all_passed = all(result for _, result in checks)
    print(f"\n🎯 Overall: {'PASSED' if all_passed else 'NEEDS WORK'}")
    
    return all_passed

if __name__ == "__main__":
    success = test_context_extraction()
    sys.exit(0 if success else 1)