import random
import string
import logging
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def generate_otp(length: int = 6) -> str:
    """
    Generate a random numeric OTP code.
    
    Args:
        length: Length of OTP (default 6 digits)
    
    Returns:
        str: Numeric OTP code
    """
    return ''.join(random.choices(string.digits, k=length))

def create_otp_key(email: str, user_type: str) -> str:
    """
    Create Redis key for storing OTP.
    
    Args:
        email: User's email address
        user_type: "voter" or "admin"
    
    Returns:
        str: Redis key for OTP storage
    """
    return f"otp:{user_type}:{email}"

def create_otp_attempts_key(email: str, user_type: str) -> str:
    """
    Create Redis key for tracking OTP verification attempts.
    
    Args:
        email: User's email address
        user_type: "voter" or "admin"
    
    Returns:
        str: Redis key for attempt tracking
    """
    return f"otp:attempts:{user_type}:{email}"