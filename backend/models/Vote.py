from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime, timezone

if TYPE_CHECKING:
    from models.vote_models import VoteCreate


class Vote:
    """
    Vote model for internal database operations.
    Represents a user's vote on a poll option.
    """

    def __init__(
        self,
        vote_id: str = "",
        user_id: str = "",
        poll_id: str = "",
        option_id: str = "",
        voted_at: Optional[datetime] = None
    ) -> None:
        self.vote_id = vote_id
        self.user_id = user_id
        self.poll_id = poll_id
        self.option_id = option_id
        self.voted_at = voted_at or datetime.now(timezone.utc)

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
        return bool(self.vote_id) and bool(self.user_id) and bool(self.poll_id)

    def to_api_dict(self) -> Dict[str, Any]:
        """
        Convert vote to dictionary for API responses.

        Returns:
            Dict[str, Any]: Vote data formatted for API response
        """
        return {
            "id": self.vote_id,
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
            "vote_id": self.vote_id,
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
        return bool(self.user_id) and bool(self.poll_id) and bool(self.option_id)

    def matches_user_and_poll(self, user_id: str, poll_id: str) -> bool:
        """
        Check if this vote matches a specific user and poll combination.
        Useful for duplicate vote validation.

        Args:
            user_id (str): User ID to check
            poll_id (str): Poll ID to check

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
        vote_id = vote_data.get('vote_id', vote_data.get('id', ''))

        # Handle datetime conversion with timezone awareness
        voted_at = vote_data.get('voted_at')
        if voted_at and isinstance(voted_at, str):
            voted_at = datetime.fromisoformat(voted_at)
            # Ensure timezone-aware (UTC)
            if voted_at.tzinfo is None:
                voted_at = voted_at.replace(tzinfo=timezone.utc)
            else:
                voted_at = voted_at.astimezone(timezone.utc)

        return cls(
            vote_id=vote_id,
            user_id=vote_data.get('user_id', ''),
            poll_id=vote_data.get('poll_id', ''),
            option_id=vote_data.get('option_id', ''),
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
        # Handle timezone conversion for datetime field
        voted_at = row[4]
        if voted_at and isinstance(voted_at, datetime):
            if voted_at.tzinfo is None:
                voted_at = voted_at.replace(tzinfo=timezone.utc)
            else:
                voted_at = voted_at.astimezone(timezone.utc)

        return cls(
            vote_id=row[0],
            user_id=row[1],
            poll_id=row[2],
            option_id=row[3],
            voted_at=voted_at
        )

    @classmethod
    def from_vote_create(cls, vote_create: 'VoteCreate', user_id: str) -> 'Vote':
        """
        Create a Vote object from VoteCreate Pydantic model.

        Args:
            vote_create (VoteCreate): Pydantic model containing vote creation data
            user_id (str): ID of the user casting the vote

        Returns:
            Vote: New Vote instance ready for database insertion

        Note:
            vote_id will be assigned by database during insertion
        """
        return cls(
            vote_id="",  # Will be assigned by database
            user_id=user_id,
            poll_id=vote_create.poll_id,
            option_id=vote_create.option_id,
            voted_at=datetime.now(timezone.utc)
        )
