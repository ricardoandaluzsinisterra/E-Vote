from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator


# ==================== Request Models ====================

class VoteCreate(BaseModel):
    """Pydantic model for creating votes with validation."""
    poll_id: str = Field(..., min_length=1, description="ID of the poll to vote on")
    option_id: str = Field(..., min_length=1, description="ID of the selected poll option")

    @field_validator('poll_id', 'option_id')
    @classmethod
    def validate_ids(cls, v: str) -> str:
        """Ensure IDs are non-empty strings."""
        if not v or not v.strip():
            raise ValueError("ID must be a non-empty string")
        return v.strip()


class VoteUpdate(BaseModel):
    """Pydantic model for updating votes (changing vote option)."""
    option_id: str = Field(..., min_length=1, description="New option ID to vote for")

    @field_validator('option_id')
    @classmethod
    def validate_option_id(cls, v: str) -> str:
        """Ensure option ID is non-empty."""
        if not v or not v.strip():
            raise ValueError("Option ID must be a non-empty string")
        return v.strip()


# ==================== Response Models ====================

class VoteResponse(BaseModel):
    """Pydantic model for vote API responses."""
    id: str = Field(..., description="Unique identifier for the vote")
    user_id: str = Field(..., description="ID of the user who cast the vote")
    poll_id: str = Field(..., description="ID of the poll that was voted on")
    option_id: str = Field(..., description="ID of the selected option")
    voted_at: str = Field(..., description="ISO format timestamp of when the vote was cast")

    class Config:
        from_attributes = True


class VoteConfirmation(BaseModel):
    """Pydantic model for vote creation/update confirmation responses."""
    message: str = Field(..., description="Confirmation message")
    vote: VoteResponse = Field(..., description="The vote that was created or updated")


class VoteDeletedResponse(BaseModel):
    """Pydantic model for vote deletion confirmation responses."""
    message: str = Field(default="Vote deleted successfully", description="Confirmation message")
    vote_id: str = Field(..., description="ID of the vote that was deleted")
    poll_id: str = Field(..., description="ID of the poll the vote was on")


class UserVoteStatus(BaseModel):
    """Pydantic model for checking if user has voted on a poll."""
    has_voted: bool = Field(..., description="Whether the user has voted on this poll")
    poll_id: str = Field(..., description="ID of the poll being checked")
    vote: Optional[VoteResponse] = Field(None, description="The user's vote if they have voted")


# ==================== Helper Models ====================

class VoteWithDetails:
    """
    Extended Vote class that includes additional poll/option details.
    Used for returning complete vote data with context.
    """

    def __init__(
        self,
        vote: Any,  # Using Any to avoid circular import with Vote
        poll_title: Optional[str] = None,
        option_text: Optional[str] = None
    ) -> None:
        self.vote = vote
        self.poll_title = poll_title
        self.option_text = option_text

    def __str__(self) -> str:
        return f"VoteWithDetails(vote={self.vote}, poll='{self.poll_title}')"

    def __repr__(self) -> str:
        return (f"VoteWithDetails(vote={self.vote!r}, poll_title={self.poll_title!r}, "
                f"option_text={self.option_text!r})")

    def to_api_dict(self) -> Dict[str, Any]:
        """
        Convert vote with details to dictionary for API responses.

        Returns:
            Dict[str, Any]: Complete vote data with poll/option context
        """
        vote_dict = self.vote.to_api_dict()
        if self.poll_title:
            vote_dict['poll_title'] = self.poll_title
        if self.option_text:
            vote_dict['option_text'] = self.option_text
        return vote_dict

    def to_response(self) -> VoteResponse:
        """
        Convert to VoteResponse Pydantic model for API responses.

        Returns:
            VoteResponse: Pydantic model ready for API serialization
        """
        return VoteResponse(
            id=self.vote.vote_id,
            user_id=self.vote.user_id,
            poll_id=self.vote.poll_id,
            option_id=self.vote.option_id,
            voted_at=self.vote.voted_at.isoformat() if self.vote.voted_at else datetime.now(timezone.utc).isoformat()
        )
