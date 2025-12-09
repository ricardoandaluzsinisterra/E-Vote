from pydantic import BaseModel, EmailStr
from typing import Optional, List

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

class OTPRequest(BaseModel):
    email: EmailStr
    user_type: str = "voter"  

class OTPVerificationRequest(BaseModel):
    email: EmailStr
    otp: str
    user_type: str = "voter"

class OTPResponse(BaseModel):
    message: str
    email: str
    expires_in_seconds: int = 600
    

class CandidateRecord(BaseModel):
    """Candidate for election"""
    name: str
    party: Optional[str] = None
    description: Optional[str] = None

class CandidateUpload(BaseModel):
    """Request to upload candidates"""
    candidates: List[CandidateRecord]

class VoterRecord(BaseModel):
    """Eligible voter from admin's CSV"""
    email: EmailStr
    full_name: str
    phone_number: str
    voter_id: str  # National ID or unique identifier

class VoterUpload(BaseModel):
    """Request to upload voters"""
    voters: List[VoterRecord]

class VoterRegistrationRequest(BaseModel):
    """Voter registration with token"""
    token: str
    email: EmailStr
    password: str
    full_name: str
    phone_number: str
    voter_id: str

class VerifyAdminOTPRequest(BaseModel):
    """Admin OTP verification that also marks account as verified"""
    email: EmailStr
    otp: str