import jwt
from datetime import datetime, timedelta

key = "secret"

def generate_tokens(user_id: int, email: str) -> str:
    """
    Generate a JWT access token for authenticated user.
    
    Args:
        user_id (int): User's database ID
        email (str): User's email address
        
    Returns:
        str: JWT token string valid for 24 hours
        
    Raises:
        jwt.InvalidKeyError: If signing key is invalid
        jwt.InvalidAlgorithmError: If algorithm is not supported
        
    Note:
        Token payload includes: user_id, email, iat (issued at), exp (expires at)
    """
    now = datetime.now()
    issued_at = int(now.timestamp())
    
    expires_at = int((now + timedelta(hours = 24)).timestamp())
    
    payload = {
        "user_id" : user_id,
        "email" : email,
        "iat" : issued_at,
        "exp" : expires_at
    }
    
    try:
        token = jwt.encode(payload, key, algorithm="HS256")
        return token
    except jwt.InvalidKeyError:
        raise
    except jwt.InvalidAlgorithmError:
        raise

def verify_token(token: str) -> dict:
    """
    Verify and decode a JWT token.
    
    Args:
        token (str): JWT token string to verify
        
    Returns:
        dict: Decoded token payload containing user_id, email, iat, exp
        
    Raises:
        jwt.ExpiredSignatureError: If token has expired
        jwt.InvalidKeyError: If verification key is invalid
        jwt.InvalidTokenError: If token format is invalid
    """
    try:
        decoded = jwt.decode(token, key, algorithms=["HS256"])
        return decoded
    except jwt.ExpiredSignatureError:
        raise
    except jwt.InvalidKeyError:
        raise
    except jwt.InvalidTokenError:
        raise

def get_current_user_from_token(token: str) -> dict:
    """
    Extract user information from a JWT token.
    
    Args:
        token (str): JWT token string to decode
        
    Returns:
        dict: User information containing:
              - user_id: User's database ID
              - email: User's email address  
              - issued_at: Token creation timestamp
              - expires_at: Token expiration timestamp
              
    Raises:
        jwt.ExpiredSignatureError: If token has expired
        jwt.InvalidKeyError: If verification key is invalid
        jwt.InvalidTokenError: If token format is invalid
    """
    decoded_payload = verify_token(token)
    
    return {
        "user_id": decoded_payload.get("user_id"),
        "email": decoded_payload.get("email"),
        "issued_at": decoded_payload.get("iat"),
        "expires_at": decoded_payload.get("exp")
    }
