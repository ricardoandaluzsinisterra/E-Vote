from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import logging
import psycopg
import os

from database.connection import DatabaseManager, get_database
from database.operations import get_user_by_email_as_user, create_user
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
# TODO: Add email verification handling
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
    
    if not verify_password(user.password_hash, user_data.password):
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
