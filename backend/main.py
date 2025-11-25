from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import logging
import psycopg
import os

from database.connection import DatabaseManager, get_database
from database.operations import get_user_by_email_as_user, create_user, verify_user, store_password_reset_token
from auth.password_utils import *
from auth.jwt_handler import generate_tokens
from models.User import User
from models.auth_models import *

# Logger
logger = logging.getLogger(__name__)
logging.basicConfig(filename='myapp.log', level=logging.INFO)

app = FastAPI()

# Configure CORS for Docker network
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://frontend:3000",  # Docker service name
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # More permissive for Docker
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.on_event("startup") 
async def startup():
    """
    Initialize database connection and create tables on application startup.
    
    Note:
        This function runs once when the FastAPI application starts
    """
    db = DatabaseManager()
    db.connect()
    db.initialize_tables()

@app.get("/")
async def read_root():
    """
    Health check endpoint to verify the API is running.
    
    Returns:
        dict: Simple message confirming backend is operational
    """
    return {"message": "Backend is running in Docker!"}

# TODO: Add proper exception/error handling
@app.post("/register")
async def register_user(user_data: UserRegistrationRequest, db: DatabaseManager = Depends(get_database)) -> RegistrationSuccessResponse:
    """
    Register a new user with proper database integration.
    
    Args:
        user_data (UserRegistrationRequest): User registration data containing email and password
        db (DatabaseManager): Database manager dependency
        
    Returns:
        dict: Registration success message with user data
        
    Note:
        Now uses centralized database connection via dependency injection
    """
    existing_user = get_user_by_email_as_user(db.get_cursor(), user_data.email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists, please log in."
        )
    
    # Create user object from registration data
    new_user = User.from_user_registration_request(user_data)
    
    password_strength = validate_password_strength(user_data.password)
    
    if not password_strength.get("valid"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=password_strength.get("message")
        )
    
    new_user.password_hash = hash_password(user_data.password)
    
    # Create user in database (this will update the user object with ID and verification token)
    created_user = create_user(db.get_cursor(), new_user)
    
    return RegistrationSuccessResponse(
        user=UserResponse(
            user_id=created_user.user_id, 
            email=created_user.email, 
            is_verified=created_user.is_verified, 
            created_at=str(created_user.created_at)
            ),
        verification_token=created_user.verification_token
        )

@app.post("/verify-email")
async def verify_email(request: EmailVerificationRequest, db: DatabaseManager = Depends(get_database)) -> MessageResponse:
    """
    Verify a user's email address using their verification token.

    Args:
        request (EmailVerificationRequest): Request containing the verification token
        db (DatabaseManager): Database manager dependency

    Returns:
        MessageResponse: Success message if verification succeeds

    Raises:
        HTTPException: If token is invalid, expired, or already used
    """
    try:
        # Create a User object with just the verification token set
        user_to_verify = User(
            user_id=None,
            email="",
            password_hash="",
            is_verified=False,
            verification_token=request.token,
            created_at=None
        )

        # Attempt to verify the user using the database operation
        verify_user(db.get_cursor(), user_to_verify)

        logger.info(f"Email verification successful for token: {request.token[:10]}...")

        return MessageResponse(message="Email verified successfully. You can now log in.")

    except ValueError as e:
        # Token not found or invalid
        logger.warning(f"Email verification failed - invalid token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    except psycopg.DatabaseError as e:
        # Database error during verification
        logger.error(f"Email verification failed - database error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during email verification. Please try again later."
        )
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Email verification failed - unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later."
        )

@app.post("/reset-password-request")
async def reset_password_request(request: PasswordResetRequest, db: DatabaseManager = Depends(get_database)) -> MessageResponse:
    """
    Generate and store a password reset token for a user.

    Args:
        request (PasswordResetRequest): Request containing the user's email address
        db (DatabaseManager): Database manager dependency

    Returns:
        MessageResponse: Success message (always returns success for security)

    Note:
        For security reasons, this endpoint always returns a success message regardless
        of whether the email exists in the database. This prevents email enumeration attacks.
        In a production environment, this would also trigger an email with the reset link.
    """
    try:
        # Generate and store reset token
        reset_token = store_password_reset_token(db.get_cursor(), request.email)

        # Log token generation (in production, this would send an email instead)
        if reset_token:
            logger.info(f"Password reset token generated for {request.email}: {reset_token[:10]}...")
            # TODO: Send email with reset link containing the token
        else:
            logger.info(f"Password reset requested for non-existent email: {request.email}")

        # Always return success message to prevent email enumeration
        return MessageResponse(
            message="If an account exists with that email, a password reset link has been sent."
        )

    except psycopg.DatabaseError as e:
        logger.error(f"Password reset request failed - database error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request. Please try again later."
        )
    except Exception as e:
        logger.error(f"Password reset request failed - unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later."
        )

@app.post("/login")
async def login_user(user_data: UserLoginRequest, db: DatabaseManager = Depends(get_database)) -> TokenResponse:
    """
    Authenticate a user and return a JWT token.
    
    Args:
        user_data (UserLoginRequest): User login data containing email and password
        db (DatabaseManager): Database manager dependency
        
    Returns:
        TokenResponse: Access token and token type
        
    Raises:
        HTTPException: If authentication fails
    """
    user = get_user_by_email_as_user(db.get_cursor(), user_data.email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email before logging in."
        )
    
    # Generate JWT token
    access_token = generate_tokens(user_id=user.user_id, email=user.email)
    
    return TokenResponse(access_token=access_token, token_type="bearer")
