#!/usr/bin/env python3
"""
Security Utilities for Voice Channel Plugin

Provides security functions for:
- Input validation and sanitization
- Data encryption/decryption
- Error message sanitization
- API key authentication
"""

import re
import hmac
import hashlib
import secrets
import base64
import json
import logging
from typing import Optional, Dict, Any, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os

logger = logging.getLogger(__name__)

# Load encryption key from environment or generate one
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    # Generate a secure key if none provided (for development only)
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    logger.warning("Using auto-generated encryption key. Set ENCRYPTION_KEY environment variable in production!")

# Initialize encryption suite
try:
    cipher_suite = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)
except Exception as e:
    logger.error(f"Failed to initialize encryption: {e}")
    cipher_suite = None

class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass

class SecurityValidator:
    """Comprehensive input validation and security utilities."""
    
    # Regex patterns for validation
    PHONE_E164_PATTERN = r'^\+([1-9]\d{0,2})(\d{4,14})$'
    SESSION_ID_PATTERN = r'^[a-zA-Z0-9_-]{8,128}$'
    EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    UUID_PATTERN = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    
    # Dangerous characters that should be rejected
    DANGEROUS_CHARS = ['<', '>', '"', "'", '&', ';', '`', '|', '$', '(', ')', '{', '}', '[', ']', '\\']
    
    @staticmethod
    def validate_phone_number(phone: str, strict: bool = True) -> bool:
        """
        Enhanced phone number validation with security checks.
        
        Args:
            phone: Phone number to validate
            strict: Enable strict validation (recommended for production)
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not phone or not isinstance(phone, str):
            return False
        
        # Length check - prevent extremely long input
        if len(phone) > 20:
            return False
        
        # Check for dangerous characters
        if any(char in phone for char in SecurityValidator.DANGEROUS_CHARS):
            return False
        
        # Remove whitespace and common formatting
        cleaned_phone = phone.strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
        
        # Basic format validation
        if not re.match(SecurityValidator.PHONE_E164_PATTERN, cleaned_phone):
            return False
        
        match = re.match(SecurityValidator.PHONE_E164_PATTERN, cleaned_phone)
        if not match:
            return False
        
        country_code = match.group(1)
        number_part = match.group(2)
        
        # Enhanced validation checks
        if strict:
            # Total length validation
            total_digits = len(country_code) + len(number_part)
            if total_digits < 7 or total_digits > 15:
                return False
            
            # Reject obvious test/invalid patterns
            if number_part in ['0000000000', '1111111111', '1234567890', '9999999999']:
                return False
            
            # Country-specific validation
            if country_code == '1':  # US/Canada
                if len(number_part) != 10:
                    return False
                # Area code and exchange validation
                if number_part[0] in ['0', '1'] or number_part[3] in ['0', '1']:
                    return False
                # Reject N11 codes (like 911, 411, etc.)
                if number_part[1:3] == '11':
                    return False
            
            # Additional pattern checks
            if len(set(number_part)) == 1:  # All same digit
                return False
        
        return True
    
    @staticmethod
    def validate_session_id(session_id: str) -> bool:
        """
        Validate session ID format and security.
        
        Args:
            session_id: Session ID to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not session_id or not isinstance(session_id, str):
            return False
        
        # Length and format validation
        if not re.match(SecurityValidator.SESSION_ID_PATTERN, session_id):
            return False
        
        # Check for dangerous characters
        if any(char in session_id for char in SecurityValidator.DANGEROUS_CHARS):
            return False
        
        # Ensure reasonable entropy (not all same character)
        if len(set(session_id)) < 3:
            return False
        
        return True
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validate email address format.
        
        Args:
            email: Email address to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not email or not isinstance(email, str):
            return False
        
        if len(email) > 254:  # RFC 5321 limit
            return False
        
        # Check for dangerous characters
        if any(char in email for char in ['<', '>', '"', '\\', ';']):
            return False
        
        return bool(re.match(SecurityValidator.EMAIL_PATTERN, email))
    
    @staticmethod
    def sanitize_input(input_data: str, max_length: int = 1000) -> str:
        """
        Sanitize input string by removing dangerous characters.
        
        Args:
            input_data: Input string to sanitize
            max_length: Maximum allowed length
            
        Returns:
            str: Sanitized string
        """
        if not input_data or not isinstance(input_data, str):
            return ""
        
        # Truncate to max length
        sanitized = input_data[:max_length]
        
        # Remove dangerous characters
        for char in SecurityValidator.DANGEROUS_CHARS:
            sanitized = sanitized.replace(char, '')
        
        # Remove control characters
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)
        
        return sanitized.strip()
    
    @staticmethod
    def mask_sensitive_data(data: str, mask_char: str = '*', visible_chars: int = 4) -> str:
        """
        Mask sensitive data for logging.
        
        Args:
            data: Sensitive data to mask
            mask_char: Character to use for masking
            visible_chars: Number of characters to leave visible at start/end
            
        Returns:
            str: Masked string
        """
        if not data or len(data) <= visible_chars * 2:
            return mask_char * 8
        
        visible_start = data[:visible_chars]
        visible_end = data[-visible_chars:]
        mask_length = max(4, len(data) - visible_chars * 2)
        
        return f"{visible_start}{mask_char * mask_length}{visible_end}"

class DataEncryption:
    """Handle encryption/decryption of sensitive data in memory."""
    
    @staticmethod
    def encrypt_data(data: Union[str, Dict, Any]) -> Optional[str]:
        """
        Encrypt sensitive data for storage.
        
        Args:
            data: Data to encrypt (will be JSON serialized)
            
        Returns:
            Optional[str]: Base64 encoded encrypted data, or None if encryption fails
        """
        if not cipher_suite:
            logger.error("Encryption not available - cipher suite not initialized")
            return None
        
        try:
            # Convert to JSON if not string
            if isinstance(data, str):
                json_data = data
            else:
                json_data = json.dumps(data, default=str)
            
            # Encrypt and encode
            encrypted = cipher_suite.encrypt(json_data.encode())
            return base64.b64encode(encrypted).decode()
        
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return None
    
    @staticmethod
    def decrypt_data(encrypted_data: str, return_json: bool = False) -> Optional[Union[str, Dict]]:
        """
        Decrypt sensitive data.
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            return_json: Whether to parse as JSON
            
        Returns:
            Decrypted data or None if decryption fails
        """
        if not cipher_suite:
            logger.error("Encryption not available - cipher suite not initialized")
            return None
        
        try:
            # Decode and decrypt
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            decrypted = cipher_suite.decrypt(encrypted_bytes).decode()
            
            if return_json:
                return json.loads(decrypted)
            else:
                return decrypted
        
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return None

class ErrorSanitizer:
    """Sanitize error messages to prevent information leakage."""
    
    # Sensitive patterns that should be removed from error messages
    SENSITIVE_PATTERNS = [
        r'file ".*?"',  # File paths
        r'line \d+',    # Line numbers
        r'at 0x[0-9a-f]+',  # Memory addresses
        r'[A-Za-z]:\\[^"]*',  # Windows file paths
        r'/[^"]*\.py',  # Unix file paths
        r'Traceback \(most recent call last\):.*',  # Full tracebacks
        r'API[_\s]KEY[_\s]*[:=][^"\s]*',  # API keys
        r'password[_\s]*[:=][^"\s]*',  # Passwords
        r'token[_\s]*[:=][^"\s]*',  # Tokens
    ]
    
    # Generic error messages for different categories
    GENERIC_ERRORS = {
        'validation': 'Invalid input provided',
        'authentication': 'Authentication failed',
        'authorization': 'Access denied',
        'database': 'Database operation failed',
        'network': 'Network request failed',
        'internal': 'Internal server error occurred',
        'timeout': 'Request timeout occurred',
        'configuration': 'Service configuration error'
    }
    
    @staticmethod
    def sanitize_error_message(error_message: str, error_type: str = 'internal') -> str:
        """
        Sanitize error message to remove sensitive information.
        
        Args:
            error_message: Original error message
            error_type: Type of error for appropriate generic message
            
        Returns:
            str: Sanitized error message
        """
        if not error_message:
            return ErrorSanitizer.GENERIC_ERRORS.get(error_type, 'An error occurred')
        
        sanitized = str(error_message)
        
        # Remove sensitive patterns
        for pattern in ErrorSanitizer.SENSITIVE_PATTERNS:
            sanitized = re.sub(pattern, '[REDACTED]', sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        # If message is too revealing, use generic message
        revealing_keywords = ['traceback', 'exception', 'error in', 'failed to', 'cannot connect', 'sqlalchemy', 'psycopg', 'mysql']
        if any(keyword in sanitized.lower() for keyword in revealing_keywords):
            return ErrorSanitizer.GENERIC_ERRORS.get(error_type, 'An error occurred')
        
        return sanitized[:200]  # Limit length

class APIKeyAuth:
    """Handle API key authentication for service-to-service calls."""
    
    def __init__(self, api_keys: Optional[Dict[str, str]] = None):
        """
        Initialize API key authentication.
        
        Args:
            api_keys: Dictionary of valid API keys and their descriptions
        """
        self.api_keys = api_keys or {}
        
        # Load API keys from environment
        env_api_key = os.getenv("SERVICE_API_KEY")
        if env_api_key:
            self.api_keys["primary"] = env_api_key
        
        # Load additional keys from environment (SERVICE_API_KEY_1, SERVICE_API_KEY_2, etc.)
        for i in range(1, 10):
            env_key = os.getenv(f"SERVICE_API_KEY_{i}")
            if env_key:
                self.api_keys[f"key_{i}"] = env_key
    
    def validate_api_key(self, api_key: str) -> bool:
        """
        Validate API key using secure comparison.
        
        Args:
            api_key: API key to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not api_key or not isinstance(api_key, str):
            return False
        
        # Remove Bearer prefix if present
        if api_key.startswith('Bearer '):
            api_key = api_key[7:]
        
        # Use hmac.compare_digest for secure comparison to prevent timing attacks
        for valid_key in self.api_keys.values():
            if hmac.compare_digest(api_key, valid_key):
                return True
        
        return False
    
    def generate_api_key(self, length: int = 32) -> str:
        """
        Generate a new secure API key.
        
        Args:
            length: Length of the API key
            
        Returns:
            str: New API key
        """
        return secrets.token_urlsafe(length)

# Global instances
validator = SecurityValidator()
encryptor = DataEncryption()
error_sanitizer = ErrorSanitizer()
api_auth = APIKeyAuth()