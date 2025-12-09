from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime


class PollOption(BaseModel):
    """Poll option model for responses"""
    id: str
    poll_id: str
    option_text: str
    vote_count: int
    display_order: int


class PollResponse(BaseModel):
    """Poll response model with options and vote counts"""
    id: str
    title: str
    description: Optional[str] = None
    created_by: int
    created_at: str
    expires_at: Optional[str] = None
    is_active: bool
    options: List[PollOption]


class PollCreate(BaseModel):
    """Poll creation request model"""
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    expires_at: Optional[datetime] = None
    options: List[str] = Field(..., min_items=2, max_items=10)

    @validator('options')
    def validate_options(cls, options):
        """Validate that options are not empty and no duplicates exist"""
        if not options:
            raise ValueError("At least 2 options are required")

        # Check for duplicates
        if len(options) != len(set(options)):
            raise ValueError("Duplicate options are not allowed")

        # Check that each option is not empty
        for option in options:
            if not option.strip():
                raise ValueError("Options cannot be empty")

        return options

    @validator('expires_at')
    def validate_expires_at(cls, expires_at):
        """Validate that expires_at is in the future"""
        if expires_at is not None and expires_at <= datetime.utcnow():
            raise ValueError("expires_at must be in the future")
        return expires_at


class PollCreatedResponse(BaseModel):
    """Response model for successful poll creation"""
    id: str
    title: str
    description: Optional[str] = None
    created_by: int
    created_at: str
    expires_at: Optional[str] = None
    is_active: bool
    options: List[PollOption]
