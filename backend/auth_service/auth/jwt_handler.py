import os
import logging
import jwt
from datetime import datetime, timedelta
from typing import Optional
from jwt import PyJWTError

logger = logging.getLogger(__name__)

# Load secret from environment; prefer a long, random secret in production.
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    logger.warning("JWT_SECRET not set in environment; using a temporary insecure fallback (not for production).")
    JWT_SECRET = "change-me-in-production"

def generate_tokens(user_id: int, email: str, hours_valid: int = 24) -> str:
    """
    Generate a JWT access token for an authenticated user.

    Returns:
        str: JWT token string valid for `hours_valid` hours.
    """
    now = datetime.utcnow()
    issued_at = int(now.timestamp())
    expires_at = int((now + timedelta(hours=hours_valid)).timestamp())

    payload = {
        "user_id": user_id,
        "email": email,
        "iat": issued_at,
        "exp": expires_at,
    }

    try:
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        # PyJWT 2.x returns a str; if bytes, decode to str
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        return token
    except PyJWTError as e:
        logger.exception("Failed to generate JWT: %s", e)
        raise

def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode a JWT token. Returns decoded payload or None if invalid/expired.
    """
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return decoded
    except jwt.ExpiredSignatureError:
        logger.info("JWT expired")
        return None
    except PyJWTError as e:
        logger.warning("Invalid JWT provided: %s", e)
        return None

def get_current_user_from_token(token: str) -> Optional[dict]:
    """
    Extract user information from a JWT token or return None if token invalid.
    """
    decoded_payload = verify_token(token)
    if not decoded_payload:
        return None

    return {
        "user_id": decoded_payload.get("user_id"),
        "email": decoded_payload.get("email"),
        "issued_at": decoded_payload.get("iat"),
        "expires_at": decoded_payload.get("exp"),
    }
