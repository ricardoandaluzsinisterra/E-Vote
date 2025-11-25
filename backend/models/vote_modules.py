from typing import Optional
from pydantic import BaseModel, Field, field_validator
from models.Vote import Vote


class VoteCreate(BaseModel):
    """Pydantic model for incoming vote creation requests."""
    poll_id: str = Field(..., min_length=1, description="ID of the poll being voted on")
    option_id: str = Field(..., min_length=1, description="ID of the selected poll option")

    @field_validator('poll_id', 'option_id')
    @classmethod
    def validate_ids(cls, v: str, info) -> str:
        """Ensure IDs are non-empty strings."""
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v.strip()


class VoteResponse(BaseModel):
    """Pydantic model for vote API responses."""
    id: str
    user_id: str
    poll_id: str
    option_id: str
    voted_at: str

    class Config:
        from_attributes = True
