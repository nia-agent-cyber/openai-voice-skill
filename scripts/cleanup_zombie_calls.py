#!/usr/bin/env python3
"""
Zombie Call Cleanup Script

One-time migration script to clean up zombie calls from the database.
These are calls with status='active' and ended_at=null that have been
running for impossibly long durations (e.g., 60,000+ seconds).

Issue: #38 - Zombie calls / missing transcripts

Root Cause:
- webhook-server.py's handle_twilio_webhook() removes calls from active_calls
  when Twilio fires completion events (completed, busy, no-answer, etc.)
- BUT it doesn't call recording_manager.end_call_recording()
- So calls stay in the database with status='active', ended_at=null

This script:
1. Finds all zombie calls (active + older than threshold)
2. Marks them as 'timeout' status with proper ended_at and duration
3. Reports statistics

Usage:
    python cleanup_zombie_calls.py [--threshold SECONDS] [--dry-run]

Examples:
    # Dry run to see what would be cleaned
    python cleanup_zombie_calls.py --dry-run
    
    # Clean up calls older than 1 hour (default)
    python cleanup_zombie_calls.py
    
    # Clean up calls older than 5 minutes (for testing)
    python cleanup_zombie_calls.py --threshold 300
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta

# Add scripts directory to path for imports
sys.path.insert(0, '.')

from call_recording import recording_manager, STALE_CALL_THRESHOLD_SECONDS

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(
        description='Clean up zombie calls from the database'
    )
    parser.add_argument(
        '--threshold',
        type=int,
        default=STALE_CALL_THRESHOLD_SECONDS,
        help=f'Calls older than this (seconds) are cleaned up (default: {STALE_CALL_THRESHOLD_SECONDS})'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be cleaned without making changes'
    )
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"Zombie Call Cleanup - Issue #38")
    print(f"{'='*60}")
    print(f"Threshold: {args.threshold} seconds ({args.threshold/3600:.1f} hours)")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()
    
    # Get storage stats first
    stats = recording_manager.get_storage_stats()
    print(f"Database Stats:")
    print(f"  Total calls: {stats['total_calls']}")
    print(f"  Active calls: {stats['active_calls']}")
    print(f"  With transcripts: {stats['calls_with_transcripts']}")
    print(f"  With audio: {stats['calls_with_audio']}")
    print()
    
    # Get zombie calls
    zombies = recording_manager.get_zombie_calls(args.threshold)
    
    if not zombies:
        print("✅ No zombie calls found!")
        return 0
    
    print(f"Found {len(zombies)} zombie call(s):")
    print("-" * 60)
    
    for z in zombies:
        duration_hours = z['duration_seconds'] / 3600
        print(f"  {z['call_id'][:20]}...")
        print(f"    Type: {z['call_type']}")
        print(f"    Started: {z['started_at']}")
        print(f"    Duration: {z['duration_seconds']:.0f}s ({duration_hours:.1f}h)")
        print(f"    Has transcript: {z['has_transcript']}")
        print(f"    Has audio: {z['has_audio']}")
        print()
    
    if args.dry_run:
        print("-" * 60)
        print(f"DRY RUN: Would clean up {len(zombies)} call(s)")
        print("Run without --dry-run to perform cleanup")
        return 0
    
    # Perform cleanup
    print("-" * 60)
    print(f"Cleaning up {len(zombies)} zombie call(s)...")
    
    result = await recording_manager.cleanup_stale_calls(args.threshold)
    
    print()
    print(f"Cleanup Results:")
    print(f"  Cleaned: {result['cleaned_count']} call(s)")
    
    if result['errors']:
        print(f"  Errors: {len(result['errors'])}")
        for error in result['errors']:
            print(f"    - {error}")
    
    if result['cleaned_calls']:
        print()
        print("Cleaned calls:")
        for call in result['cleaned_calls']:
            print(f"  {call['call_id']}: {call['duration_seconds']:.0f}s → status={call['status']}")
    
    print()
    print("✅ Cleanup complete!")
    
    # Show updated stats
    stats_after = recording_manager.get_storage_stats()
    print()
    print(f"Updated Stats:")
    print(f"  Active calls: {stats['active_calls']} → {stats_after['active_calls']}")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
