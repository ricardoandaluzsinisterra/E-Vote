from pydantic import BaseModel, EmailStr
from typing import Optional

class UserRegistrationRequest(BaseModel):
    email: EmailStr
    password: str

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    user_id: int
    email: str
    is_verified: bool
    created_at: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class EmailVerificationRequest(BaseModel):
    token: str

class MessageResponse(BaseModel):
    message: str

class UserProfile(BaseModel):
    user_id: int
    email: str
    is_verified: bool
    created_at: Optional[str] = None
    
class RegistrationSuccessResponse(BaseModel):
    message: str = "Registration successful"
    user: UserResponse
    verification_token: Optional[str] = None


class VerificationTokenRequest(BaseModel):
    verification_token: str


class UpdatePasswordRequest(BaseModel):
    user_id: int
    new_password: str
