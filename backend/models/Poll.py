from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


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


class PollOption(BaseModel):
    """Pydantic model representing a poll option with vote count."""
    id: str
    poll_id: str
    option_text: str
    vote_count: int = 0

    class Config:
        from_attributes = True


class PollResponse(BaseModel):
    """Pydantic model for poll API responses with options and vote statistics."""
    id: str
    title: str
    description: Optional[str]
    created_by: int
    created_at: str
    expires_at: Optional[str]
    is_active: bool
    options: List[PollOption]
    total_votes: int = 0

    class Config:
        from_attributes = True

    def calculate_option_percentages(self) -> Dict[int, float]:
        """
        Calculate vote percentage for each option.

        Returns:
            Dict[int, float]: Mapping of option_id to percentage (0-100)
        """
        if self.total_votes == 0:
            return {option.id: 0.0 for option in self.options}

        return {
            option.id: round((option.vote_count / self.total_votes) * 100, 2)
            for option in self.options
        }


class Poll:
    """
    Poll model for internal database operations.
    Represents a poll that users can vote on.
    """

    def __init__(
        self,
        poll_id: str = "",
        title: str = "",
        description: Optional[str] = None,
        created_by: str = "",
        created_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        is_active: bool = True
    ) -> None:
        self.poll_id = poll_id
        self.title = title
        self.description = description
        self.created_by = created_by
        self.created_at = created_at or datetime.now()
        self.expires_at = expires_at
        self.is_active = is_active

    def __str__(self) -> str:
        return f"Poll(id={self.poll_id}, title='{self.title}', active={self.is_active})"

    def __repr__(self) -> str:
        return (f"Poll(poll_id={self.poll_id}, title='{self.title}', "
                f"description='{self.description}', created_by={self.created_by}, "
                f"created_at={self.created_at}, expires_at={self.expires_at}, "
                f"is_active={self.is_active})")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Poll):
            return NotImplemented
        return self.poll_id == other.poll_id and self.title == other.title

    def __hash__(self) -> int:
        return hash((self.poll_id, self.title))

    def __bool__(self) -> bool:
        return bool(self.poll_id) and bool(self.title)

    def to_api_dict(self) -> Dict[str, Any]:
        """
        Convert poll to dictionary for API responses.

        Returns:
            Dict[str, Any]: Poll data formatted for API response
        """
        return {
            "id": self.poll_id,
            "title": self.title,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active
        }

    def to_full_dict(self) -> Dict[str, Any]:
        """
        Convert poll to complete dictionary including all fields.

        Returns:
            Dict[str, Any]: Complete poll data
        """
        return {
            "poll_id": self.poll_id,
            "title": self.title,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active
        }

    def is_valid(self) -> bool:
        """
        Check if poll has all required fields populated.

        Returns:
            bool: True if poll has valid poll_id, title, and created_by
        """
        return bool(self.poll_id) and bool(self.title) and bool(self.created_by)

    def is_expired(self) -> bool:
        """
        Check if poll has expired based on expires_at timestamp.

        Returns:
            bool: True if poll has expired, False if still active or no expiration
        """
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def can_vote(self) -> bool:
        """
        Check if poll is currently accepting votes.

        Returns:
            bool: True if poll is active and not expired
        """
        return self.is_active and not self.is_expired()

    def deactivate(self) -> None:
        """Mark poll as inactive."""
        self.is_active = False

    def activate(self) -> None:
        """Mark poll as active (if not expired)."""
        if not self.is_expired():
            self.is_active = True

    @classmethod
    def from_dict(cls, poll_data: Dict[str, Any]) -> 'Poll':
        """
        Create a Poll object from dictionary data.

        Args:
            poll_data (Dict[str, Any]): Dictionary containing poll fields

        Returns:
            Poll: New Poll instance created from the data

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Handle both 'id' and 'poll_id' field names
        poll_id = poll_data.get('poll_id', poll_data.get('id', ''))

        # Handle datetime conversion
        created_at = poll_data.get('created_at')
        if created_at and isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        expires_at = poll_data.get('expires_at')
        if expires_at and isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)

        return cls(
            poll_id=poll_id,
            title=poll_data.get('title', ''),
            description=poll_data.get('description'),
            created_by=poll_data.get('created_by', ''),
            created_at=created_at,
            expires_at=expires_at,
            is_active=poll_data.get('is_active', True)
        )

    @classmethod
    def from_db_row(cls, row: tuple) -> 'Poll':
        """
        Create a Poll object from database row tuple.

        Args:
            row (tuple): Database row as tuple (id, title, description, created_by,
                        created_at, expires_at, is_active)

        Returns:
            Poll: New Poll instance created from database row

        Note:
            Expects row fields in the order: id, title, description, created_by,
            created_at, expires_at, is_active
        """
        return cls(
            poll_id=row[0],
            title=row[1],
            description=row[2],
            created_by=row[3],
            created_at=row[4],
            expires_at=row[5],
            is_active=row[6]
        )

    @classmethod
    def from_poll_create(cls, poll_create: PollCreate, created_by: int) -> 'Poll':
        """
        Create a Poll object from PollCreate Pydantic model.

        Args:
            poll_create (PollCreate): Pydantic model containing poll creation data
            created_by (int): ID of the user creating the poll

        Returns:
            Poll: New Poll instance ready for database insertion

        Note:
            poll_id will be assigned by database during insertion
            Options are handled separately in database operations
        """
        return cls(
            poll_id=0,  # Will be assigned by database
            title=poll_create.title,
            description=poll_create.description,
            created_by=created_by,
            created_at=datetime.now(),
            expires_at=poll_create.expires_at,
            is_active=True
        )


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

    def get_option_percentages(self) -> Dict[int, float]:
        """
        Calculate vote percentage for each option.

        Returns:
            Dict[int, float]: Mapping of option_id to percentage (0-100)
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
