#!/usr/bin/env python3
"""
User Context Module - Derive timezone and location from phone numbers.

This module provides utilities to determine user context (timezone, location)
from phone numbers, either via:
1. Explicit mapping in phone_mapping.json
2. Inference from country code

Usage:
    from user_context import UserContextResolver
    
    resolver = UserContextResolver()
    context = resolver.get_context("+250794002033")
    # Returns: {"timezone": "Africa/Kigali", "location": "Rwanda", "name": "Remi", ...}
"""

import json
import logging
import os
import re
from datetime import datetime, timezone as tz
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

# Country code to timezone mapping (primary timezone for each country)
# This covers the most common cases - can be extended as needed
COUNTRY_CODE_TIMEZONES = {
    # North America
    "1": "America/New_York",  # US/Canada - default to Eastern, can be refined by area code
    
    # Europe
    "33": "Europe/Paris",       # France
    "44": "Europe/London",      # UK
    "49": "Europe/Berlin",      # Germany
    "31": "Europe/Amsterdam",   # Netherlands
    "32": "Europe/Brussels",    # Belgium
    "34": "Europe/Madrid",      # Spain
    "39": "Europe/Rome",        # Italy
    "41": "Europe/Zurich",      # Switzerland
    "43": "Europe/Vienna",      # Austria
    "45": "Europe/Copenhagen",  # Denmark
    "46": "Europe/Stockholm",   # Sweden
    "47": "Europe/Oslo",        # Norway
    "48": "Europe/Warsaw",      # Poland
    "351": "Europe/Lisbon",     # Portugal
    "353": "Europe/Dublin",     # Ireland
    "358": "Europe/Helsinki",   # Finland
    "380": "Europe/Kyiv",       # Ukraine
    "7": "Europe/Moscow",       # Russia (default to Moscow)
    
    # Africa
    "27": "Africa/Johannesburg",  # South Africa
    "20": "Africa/Cairo",         # Egypt
    "212": "Africa/Casablanca",   # Morocco
    "213": "Africa/Algiers",      # Algeria
    "216": "Africa/Tunis",        # Tunisia
    "234": "Africa/Lagos",        # Nigeria
    "250": "Africa/Kigali",       # Rwanda
    "254": "Africa/Nairobi",      # Kenya
    "255": "Africa/Dar_es_Salaam",# Tanzania
    "256": "Africa/Kampala",      # Uganda
    "233": "Africa/Accra",        # Ghana
    "225": "Africa/Abidjan",      # Ivory Coast
    "221": "Africa/Dakar",        # Senegal
    "237": "Africa/Douala",       # Cameroon
    "243": "Africa/Kinshasa",     # DR Congo
    "251": "Africa/Addis_Ababa",  # Ethiopia
    
    # Asia
    "81": "Asia/Tokyo",           # Japan
    "82": "Asia/Seoul",           # South Korea
    "86": "Asia/Shanghai",        # China
    "91": "Asia/Kolkata",         # India
    "92": "Asia/Karachi",         # Pakistan
    "93": "Asia/Kabul",           # Afghanistan
    "94": "Asia/Colombo",         # Sri Lanka
    "95": "Asia/Yangon",          # Myanmar
    "60": "Asia/Kuala_Lumpur",    # Malaysia
    "62": "Asia/Jakarta",         # Indonesia
    "63": "Asia/Manila",          # Philippines
    "65": "Asia/Singapore",       # Singapore
    "66": "Asia/Bangkok",         # Thailand
    "84": "Asia/Ho_Chi_Minh",     # Vietnam
    "852": "Asia/Hong_Kong",      # Hong Kong
    "853": "Asia/Macau",          # Macau
    "886": "Asia/Taipei",         # Taiwan
    "971": "Asia/Dubai",          # UAE
    "972": "Asia/Jerusalem",      # Israel
    "974": "Asia/Qatar",          # Qatar
    "966": "Asia/Riyadh",         # Saudi Arabia
    
    # Oceania
    "61": "Australia/Sydney",     # Australia (default to Sydney)
    "64": "Pacific/Auckland",     # New Zealand
    
    # South America
    "54": "America/Argentina/Buenos_Aires",  # Argentina
    "55": "America/Sao_Paulo",    # Brazil
    "56": "America/Santiago",     # Chile
    "57": "America/Bogota",       # Colombia
    "51": "America/Lima",         # Peru
    "58": "America/Caracas",      # Venezuela
    "52": "America/Mexico_City",  # Mexico
}

# Country code to country name mapping
COUNTRY_CODE_NAMES = {
    "1": "United States/Canada",
    "33": "France",
    "44": "United Kingdom",
    "49": "Germany",
    "31": "Netherlands",
    "32": "Belgium",
    "34": "Spain",
    "39": "Italy",
    "41": "Switzerland",
    "43": "Austria",
    "45": "Denmark",
    "46": "Sweden",
    "47": "Norway",
    "48": "Poland",
    "351": "Portugal",
    "353": "Ireland",
    "358": "Finland",
    "380": "Ukraine",
    "7": "Russia",
    "27": "South Africa",
    "20": "Egypt",
    "212": "Morocco",
    "213": "Algeria",
    "216": "Tunisia",
    "234": "Nigeria",
    "250": "Rwanda",
    "254": "Kenya",
    "255": "Tanzania",
    "256": "Uganda",
    "233": "Ghana",
    "225": "Ivory Coast",
    "221": "Senegal",
    "237": "Cameroon",
    "243": "DR Congo",
    "251": "Ethiopia",
    "81": "Japan",
    "82": "South Korea",
    "86": "China",
    "91": "India",
    "92": "Pakistan",
    "60": "Malaysia",
    "62": "Indonesia",
    "63": "Philippines",
    "65": "Singapore",
    "66": "Thailand",
    "84": "Vietnam",
    "852": "Hong Kong",
    "886": "Taiwan",
    "971": "UAE",
    "972": "Israel",
    "974": "Qatar",
    "966": "Saudi Arabia",
    "61": "Australia",
    "64": "New Zealand",
    "54": "Argentina",
    "55": "Brazil",
    "56": "Chile",
    "57": "Colombia",
    "51": "Peru",
    "58": "Venezuela",
    "52": "Mexico",
}


class UserContextResolver:
    """
    Resolve user context (timezone, location, name) from phone numbers.
    
    Priority:
    1. Explicit mapping in phone_mapping.json (highest priority)
    2. Country code inference (fallback)
    """
    
    def __init__(self, mapping_path: Optional[Path] = None):
        """
        Initialize the resolver.
        
        Args:
            mapping_path: Path to phone_mapping.json. If None, looks in 
                         parent directory of this script.
        """
        if mapping_path is None:
            # Default: look in repo root
            script_dir = Path(__file__).parent
            mapping_path = script_dir.parent / "phone_mapping.json"
        
        self.mapping_path = mapping_path
        self.phone_mapping = self._load_mapping()
    
    def _load_mapping(self) -> Dict[str, Dict[str, Any]]:
        """Load phone mapping from JSON file."""
        if not self.mapping_path.exists():
            logger.warning(f"Phone mapping not found at {self.mapping_path}")
            return {}
        
        try:
            with open(self.mapping_path, 'r') as f:
                data = json.load(f)
                # Filter out comments
                return {k: v for k, v in data.items() if not k.startswith("_")}
        except Exception as e:
            logger.error(f"Error loading phone mapping: {e}")
            return {}
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number to E.164 format."""
        # Remove all non-digit characters except leading +
        clean = "".join(c for c in phone if c.isdigit() or c == "+")
        if not clean.startswith("+"):
            clean = "+" + clean
        return clean
    
    def _extract_country_code(self, phone: str) -> Optional[str]:
        """
        Extract country code from phone number.
        
        Returns the country code (without +) or None if not determinable.
        """
        phone = self._normalize_phone(phone)
        if not phone.startswith("+"):
            return None
        
        # Remove the leading +
        digits = phone[1:]
        
        # Try matching from longest to shortest country codes
        # Most country codes are 1-3 digits
        for length in [3, 2, 1]:
            if len(digits) >= length:
                code = digits[:length]
                if code in COUNTRY_CODE_TIMEZONES:
                    return code
        
        return None
    
    def _infer_from_country_code(self, phone: str) -> Dict[str, Any]:
        """
        Infer timezone and location from phone country code.
        
        Returns context dict with inferred values.
        """
        country_code = self._extract_country_code(phone)
        
        if not country_code:
            logger.debug(f"Could not extract country code from {phone}")
            return {}
        
        result = {
            "country_code": country_code,
            "inferred": True,  # Flag that this was inferred, not explicit
        }
        
        if country_code in COUNTRY_CODE_TIMEZONES:
            result["timezone"] = COUNTRY_CODE_TIMEZONES[country_code]
        
        if country_code in COUNTRY_CODE_NAMES:
            result["location"] = COUNTRY_CODE_NAMES[country_code]
        
        logger.debug(f"Inferred context for {phone}: {result}")
        return result
    
    def get_context(self, phone: str) -> Dict[str, Any]:
        """
        Get full user context for a phone number.
        
        Args:
            phone: Phone number in any format (will be normalized)
            
        Returns:
            Context dictionary with available fields:
            - name: User's name (if known)
            - timezone: IANA timezone string (e.g., "Africa/Kigali")
            - location: Location description (e.g., "Rwanda")
            - relationship: User relationship (if mapped)
            - session_id: OpenClaw session ID (if mapped)
            - known_user: True if user is in phone_mapping
            - inferred: True if timezone/location was inferred from country code
        """
        phone = self._normalize_phone(phone)
        
        # Start with inferred context from country code
        context = self._infer_from_country_code(phone)
        context["phone"] = phone
        context["known_user"] = False
        
        # Override with explicit mapping if available
        if phone in self.phone_mapping:
            explicit = self.phone_mapping[phone]
            context.update(explicit)
            context["known_user"] = True
            context["inferred"] = False
            logger.info(f"Found explicit mapping for {phone}: {explicit.get('name', 'Unknown')}")
        
        # Ensure we have sensible defaults
        if "name" not in context:
            context["name"] = "Unknown Caller"
        
        return context
    
    def get_current_time_for_user(self, phone: str) -> Optional[str]:
        """
        Get the current time formatted for a user's timezone.
        
        Args:
            phone: User's phone number
            
        Returns:
            Current time string in user's timezone, or None if timezone unknown
        """
        context = self.get_context(phone)
        timezone_str = context.get("timezone")
        
        if not timezone_str:
            return None
        
        try:
            from zoneinfo import ZoneInfo
            user_tz = ZoneInfo(timezone_str)
            now = datetime.now(user_tz)
            return now.strftime("%Y-%m-%d %H:%M:%S %Z")
        except Exception as e:
            logger.warning(f"Error getting time for timezone {timezone_str}: {e}")
            return None
    
    def format_context_for_agent(self, phone: str) -> str:
        """
        Format user context as a string suitable for injecting into agent requests.
        
        This creates a context prefix that can be prepended to tool requests
        so the OpenClaw agent knows the user's timezone and location.
        
        Args:
            phone: User's phone number
            
        Returns:
            Context string like "[User context: timezone=Africa/Kigali, location=Rwanda]"
        """
        context = self.get_context(phone)
        
        parts = []
        
        if context.get("name") and context["name"] != "Unknown Caller":
            parts.append(f"user={context['name']}")
        
        if context.get("timezone"):
            parts.append(f"timezone={context['timezone']}")
        
        if context.get("location"):
            parts.append(f"location={context['location']}")
        
        if not parts:
            return ""
        
        return f"[User context: {', '.join(parts)}] "


# Global singleton instance
_resolver: Optional[UserContextResolver] = None


def get_resolver() -> UserContextResolver:
    """Get or create the global UserContextResolver instance."""
    global _resolver
    if _resolver is None:
        _resolver = UserContextResolver()
    return _resolver


def get_user_context(phone: str) -> Dict[str, Any]:
    """Convenience function to get user context for a phone number."""
    return get_resolver().get_context(phone)


def format_context_for_agent(phone: str) -> str:
    """Convenience function to format context for agent requests."""
    return get_resolver().format_context_for_agent(phone)


# CLI test interface
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.DEBUG)
    
    test_numbers = sys.argv[1:] if len(sys.argv) > 1 else [
        "+250794002033",  # Rwanda (explicit mapping)
        "+14155551234",   # US
        "+447911123456",  # UK
        "+81312345678",   # Japan
        "+919876543210",  # India
        "+5511987654321", # Brazil
    ]
    
    resolver = UserContextResolver()
    
    for phone in test_numbers:
        print(f"\n{'='*60}")
        print(f"Phone: {phone}")
        print(f"{'='*60}")
        
        context = resolver.get_context(phone)
        for key, value in context.items():
            print(f"  {key}: {value}")
        
        current_time = resolver.get_current_time_for_user(phone)
        if current_time:
            print(f"  current_time: {current_time}")
        
        agent_context = resolver.format_context_for_agent(phone)
        if agent_context:
            print(f"  agent_prefix: {agent_context}")
