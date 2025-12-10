import logging
from functools import wraps
import jwt
from fastapi import Request, HTTPException, status
from backend.auth_service.auth.jwt_handler import JWT_SECRET

logger = logging.getLogger(__name__)


def require_auth(func):
    """
    Decorator to protect API endpoints with JWT authentication.

    Extracts and validates JWT token from Authorization header,
    then stores user info in request.state.user.

    Raises:
        HTTPException: 401 if authentication fails
    """
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        # Check Bearer format
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        token = parts[1]

        # Verify token and extract payload
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])

            # Store user info in request state
            request.state.user = {
                "user_id": decoded.get("user_id"),
                "email": decoded.get("email")
            }

            # Call the original function
            return await func(request, *args, **kwargs)

        except jwt.ExpiredSignatureError:
            logger.info("JWT expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        except jwt.InvalidSignatureError:
            logger.warning("JWT signature verification failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token signature verification failed"
            )
        except jwt.PyJWTError as e:
            logger.warning("Invalid JWT provided: %s", e)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token signature verification failed"
            )

    return wrapper
