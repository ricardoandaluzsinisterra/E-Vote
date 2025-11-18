from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class VoteCreate(BaseModel):
    """Pydantic model for incoming vote creation requests."""
    poll_id: int = Field(..., gt=0, description="ID of the poll being voted on")
    option_id: int = Field(..., gt=0, description="ID of the selected poll option")

    @field_validator('poll_id', 'option_id')
    @classmethod
    def validate_positive_ids(cls, v: int, info) -> int:
        """Ensure IDs are positive integers."""
        if v <= 0:
            raise ValueError(f"{info.field_name} must be a positive integer")
        return v


class VoteResponse(BaseModel):
    """Pydantic model for vote API responses."""
    id: str
    user_id: int
    poll_id: int
    option_id: int
    voted_at: str

    class Config:
        from_attributes = True


class Vote:
    """
    Vote model for internal database operations.
    Represents a user's vote on a poll option.
    """

    def __init__(
        self,
        vote_id: Optional[UUID] = None,
        user_id: int = 0,
        poll_id: int = 0,
        option_id: int = 0,
        voted_at: Optional[datetime] = None
    ) -> None:
        self.vote_id = vote_id
        self.user_id = user_id
        self.poll_id = poll_id
        self.option_id = option_id
        self.voted_at = voted_at or datetime.now()

    def __str__(self) -> str:
        return f"Vote(id={self.vote_id}, user={self.user_id}, poll={self.poll_id}, option={self.option_id})"

    def __repr__(self) -> str:
        return (f"Vote(vote_id={self.vote_id}, user_id={self.user_id}, "
                f"poll_id={self.poll_id}, option_id={self.option_id}, "
                f"voted_at={self.voted_at})")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vote):
            return NotImplemented
        return (self.vote_id == other.vote_id and
                self.user_id == other.user_id and
                self.poll_id == other.poll_id)

    def __hash__(self) -> int:
        return hash((self.vote_id, self.user_id, self.poll_id))

    def __bool__(self) -> bool:
        return self.vote_id is not None and self.user_id > 0 and self.poll_id > 0

    def to_api_dict(self) -> Dict[str, Any]:
        """
        Convert vote to dictionary for API responses.

        Returns:
            Dict[str, Any]: Vote data formatted for API response
        """
        return {
            "id": str(self.vote_id) if self.vote_id else None,
            "user_id": self.user_id,
            "poll_id": self.poll_id,
            "option_id": self.option_id,
            "voted_at": self.voted_at.isoformat() if self.voted_at else None
        }

    def to_full_dict(self) -> Dict[str, Any]:
        """
        Convert vote to complete dictionary including all fields.

        Returns:
            Dict[str, Any]: Complete vote data
        """
        return {
            "vote_id": str(self.vote_id) if self.vote_id else None,
            "user_id": self.user_id,
            "poll_id": self.poll_id,
            "option_id": self.option_id,
            "voted_at": self.voted_at.isoformat() if self.voted_at else None
        }

    def is_valid(self) -> bool:
        """
        Check if vote has all required fields populated.

        Returns:
            bool: True if vote has valid user_id, poll_id, and option_id
        """
        return self.user_id > 0 and self.poll_id > 0 and self.option_id > 0

    def matches_user_and_poll(self, user_id: int, poll_id: int) -> bool:
        """
        Check if this vote matches a specific user and poll combination.
        Useful for duplicate vote validation.

        Args:
            user_id (int): User ID to check
            poll_id (int): Poll ID to check

        Returns:
            bool: True if vote matches the user and poll
        """
        return self.user_id == user_id and self.poll_id == poll_id

    @classmethod
    def from_dict(cls, vote_data: Dict[str, Any]) -> 'Vote':
        """
        Create a Vote object from dictionary data.

        Args:
            vote_data (Dict[str, Any]): Dictionary containing vote fields

        Returns:
            Vote: New Vote instance created from the data

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Handle both 'id' and 'vote_id' field names
        vote_id = vote_data.get('vote_id') or vote_data.get('id')

        # Convert string UUID to UUID object if needed
        if vote_id and isinstance(vote_id, str):
            vote_id = UUID(vote_id)

        # Handle datetime conversion
        voted_at = vote_data.get('voted_at')
        if voted_at and isinstance(voted_at, str):
            voted_at = datetime.fromisoformat(voted_at)

        return cls(
            vote_id=vote_id,
            user_id=vote_data.get('user_id', 0),
            poll_id=vote_data.get('poll_id', 0),
            option_id=vote_data.get('option_id', 0),
            voted_at=voted_at
        )

    @classmethod
    def from_db_row(cls, row: tuple) -> 'Vote':
        """
        Create a Vote object from database row tuple.

        Args:
            row (tuple): Database row as tuple (id, user_id, poll_id, option_id, voted_at)

        Returns:
            Vote: New Vote instance created from database row

        Note:
            Expects row fields in the order: id, user_id, poll_id, option_id, voted_at
        """
        return cls(
            vote_id=row[0],
            user_id=row[1],
            poll_id=row[2],
            option_id=row[3],
            voted_at=row[4]
        )

    @classmethod
    def from_vote_create(cls, vote_create: VoteCreate, user_id: int) -> 'Vote':
        """
        Create a Vote object from VoteCreate Pydantic model.

        Args:
            vote_create (VoteCreate): Pydantic model containing poll_id and option_id
            user_id (int): ID of the user creating the vote

        Returns:
            Vote: New Vote instance ready for database insertion

        Note:
            vote_id will be generated by the database (UUID)
            voted_at will be set to current timestamp
        """
        return cls(
            vote_id=None,  # Will be generated by database
            user_id=user_id,
            poll_id=vote_create.poll_id,
            option_id=vote_create.option_id,
            voted_at=datetime.now()
        )

    def to_response(self) -> VoteResponse:
        """
        Convert Vote object to VoteResponse Pydantic model for API responses.

        Returns:
            VoteResponse: Pydantic model ready for API serialization
        """
        return VoteResponse(
            id=str(self.vote_id) if self.vote_id else "",
            user_id=self.user_id,
            poll_id=self.poll_id,
            option_id=self.option_id,
            voted_at=self.voted_at.isoformat() if self.voted_at else datetime.now().isoformat()
        )
