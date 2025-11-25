from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from models.Poll import Poll, PollOption


class PollOptionCreate(BaseModel):
    """Pydantic model for creating poll options."""
    option_text: str = Field(..., min_length=1, max_length=500, description="Text for the poll option")

    @field_validator('option_text')
    @classmethod
    def validate_option_text(cls, v: str) -> str:
        """Ensure option text is not empty or just whitespace."""
        if not v or not v.strip():
            raise ValueError("Option text cannot be empty or whitespace only")
        return v.strip()


class PollCreate(BaseModel):
    """Pydantic model for creating polls with validation."""
    title: str = Field(..., min_length=1, max_length=500, description="Title of the poll")
    description: Optional[str] = Field(None, max_length=2000, description="Description of the poll")
    options: List[str] = Field(..., min_items=2, max_items=10, description="List of poll options (2-10 required)")
    expires_at: Optional[datetime] = Field(None, description="Expiration datetime for the poll")

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Ensure title is not empty or just whitespace."""
        if not v or not v.strip():
            raise ValueError("Title cannot be empty or whitespace only")
        return v.strip()

    @field_validator('options')
    @classmethod
    def validate_options(cls, v: List[str]) -> List[str]:
        """Validate poll options list."""
        if len(v) < 2:
            raise ValueError("Poll must have at least 2 options")
        if len(v) > 10:
            raise ValueError("Poll cannot have more than 10 options")

        # Remove whitespace and check for empty options
        cleaned_options = []
        for option in v:
            cleaned = option.strip()
            if not cleaned:
                raise ValueError("Poll options cannot be empty or whitespace only")
            cleaned_options.append(cleaned)

        # Check for duplicate options
        if len(cleaned_options) != len(set(cleaned_options)):
            raise ValueError("Poll options must be unique")

        return cleaned_options

    @field_validator('expires_at')
    @classmethod
    def validate_expires_at(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure expiration date is in the future if provided."""
        if v is not None and v <= datetime.now():
            raise ValueError("Expiration date must be in the future")
        return v


class PollResponse(BaseModel):
    """Pydantic model for poll API responses with options and vote statistics."""
    id: str
    title: str
    description: Optional[str]
    created_by: str
    created_at: str
    expires_at: Optional[str]
    is_active: bool
    options: List[PollOption]
    total_votes: int = 0

    class Config:
        from_attributes = True

    def calculate_option_percentages(self) -> Dict[str, float]:
        """
        Calculate vote percentage for each option.

        Returns:
            Dict[str, float]: Mapping of option_id to percentage (0-100)
        """
        if self.total_votes == 0:
            return {option.id: 0.0 for option in self.options}

        return {
            option.id: round((option.vote_count / self.total_votes) * 100, 2)
            for option in self.options
        }


class PollWithOptions:
    """
    Extended Poll class that includes poll options and vote counts.
    Used for returning complete poll data with voting statistics.
    """

    def __init__(
        self,
        poll: Poll,
        options: List[Dict[str, Any]]
    ) -> None:
        self.poll = poll
        self.options = options

    def __str__(self) -> str:
        return f"PollWithOptions(poll={self.poll}, options_count={len(self.options)})"

    def __repr__(self) -> str:
        return f"PollWithOptions(poll={self.poll!r}, options={self.options!r})"

    def get_total_votes(self) -> int:
        """
        Calculate total votes across all options.

        Returns:
            int: Total number of votes
        """
        return sum(option.get('vote_count', 0) for option in self.options)

    def get_option_percentages(self) -> Dict[str, float]:
        """
        Calculate vote percentage for each option.

        Returns:
            Dict[str, float]: Mapping of option_id to percentage (0-100)
        """
        total_votes = self.get_total_votes()
        if total_votes == 0:
            return {option['id']: 0.0 for option in self.options}

        return {
            option['id']: round((option.get('vote_count', 0) / total_votes) * 100, 2)
            for option in self.options
        }

    def to_api_dict(self) -> Dict[str, Any]:
        """
        Convert poll with options to dictionary for API responses.

        Returns:
            Dict[str, Any]: Complete poll data with options and vote statistics
        """
        poll_dict = self.poll.to_api_dict()
        poll_dict['options'] = self.options
        poll_dict['total_votes'] = self.get_total_votes()
        poll_dict['option_percentages'] = self.get_option_percentages()
        return poll_dict

    def to_response(self) -> PollResponse:
        """
        Convert to PollResponse Pydantic model for API responses.

        Returns:
            PollResponse: Pydantic model ready for API serialization
        """
        poll_options = [
            PollOption(
                id=option['id'],
                poll_id=self.poll.poll_id,
                option_text=option['option_text'],
                vote_count=option.get('vote_count', 0)
            )
            for option in self.options
        ]

        return PollResponse(
            id=self.poll.poll_id,
            title=self.poll.title,
            description=self.poll.description,
            created_by=self.poll.created_by,
            created_at=self.poll.created_at.isoformat() if self.poll.created_at else datetime.now().isoformat(),
            expires_at=self.poll.expires_at.isoformat() if self.poll.expires_at else None,
            is_active=self.poll.is_active,
            options=poll_options,
            total_votes=self.get_total_votes()
        )
