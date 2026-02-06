#!/usr/bin/env python3
"""
Call Context Store - Shared storage for call context between modules.

This module provides a simple in-memory store for call context (caller phone,
timezone, location) that can be accessed by both webhook-server.py and
realtime_tool_handler.py without circular imports.

Usage in webhook-server.py:
    from call_context_store import store_call_context
    store_call_context(call_id, caller_phone=from_header)

Usage in realtime_tool_handler.py:
    from call_context_store import get_call_context
    context = get_call_context(call_id)
"""

import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

# In-memory store for call contexts
# Key: call_id, Value: context dict
_call_contexts: Dict[str, Dict[str, Any]] = {}


def store_call_context(
    call_id: str,
    caller_phone: Optional[str] = None,
    callee_phone: Optional[str] = None,
    call_type: str = "unknown",
    **extra
) -> None:
    """
    Store context for a call.
    
    Args:
        call_id: The call ID
        caller_phone: Caller's phone number (for inbound) or our number (for outbound)
        callee_phone: Callee's phone number (for outbound) or our number (for inbound)
        call_type: "inbound" or "outbound"
        **extra: Any additional context to store
    """
    # Determine the user's phone based on call type
    # For inbound: user is the caller
    # For outbound: user is the callee
    user_phone = caller_phone if call_type == "inbound" else callee_phone
    
    context = {
        "caller_phone": caller_phone,
        "callee_phone": callee_phone,
        "call_type": call_type,
        "user_phone": user_phone,
        **extra
    }
    
    _call_contexts[call_id] = context
    logger.info(f"[call_id={call_id}] Stored call context: user_phone={user_phone}, type={call_type}")


def get_call_context(call_id: str) -> Dict[str, Any]:
    """
    Get stored context for a call.
    
    Args:
        call_id: The call ID
        
    Returns:
        Context dict, or empty dict if not found
    """
    context = _call_contexts.get(call_id, {})
    if not context:
        logger.debug(f"[call_id={call_id}] No stored call context found")
    return context


def get_user_phone(call_id: str) -> Optional[str]:
    """
    Get the user's phone number for a call.
    
    This is the caller's phone for inbound calls, or the callee's phone
    for outbound calls.
    
    Args:
        call_id: The call ID
        
    Returns:
        User's phone number, or None if not available
    """
    context = get_call_context(call_id)
    return context.get("user_phone")


def clear_call_context(call_id: str) -> None:
    """
    Clear stored context for a call (e.g., when call ends).
    
    Args:
        call_id: The call ID to clear
    """
    if call_id in _call_contexts:
        del _call_contexts[call_id]
        logger.debug(f"[call_id={call_id}] Cleared call context")


def get_all_contexts() -> Dict[str, Dict[str, Any]]:
    """Get all stored call contexts (for debugging)."""
    return _call_contexts.copy()
