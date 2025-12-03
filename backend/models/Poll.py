from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime, timezone

if TYPE_CHECKING:
    from models.poll_models import PollCreate

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
        created_by: int = 0,
        created_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        is_active: bool = True
    ) -> None:
        self.poll_id = poll_id
        self.title = title
        self.description = description
        self.created_by = created_by
        self.created_at = created_at or datetime.now(timezone.utc)
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
        return datetime.now(timezone.utc) > self.expires_at

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

        # Validate and convert created_by to integer
        created_by = poll_data.get('created_by', 0)
        if not isinstance(created_by, int):
            try:
                created_by = int(created_by)
            except (ValueError, TypeError):
                raise ValueError(f"created_by must be an integer, got {type(created_by)}")

        # Handle datetime conversion
        created_at = poll_data.get('created_at')
        if created_at and isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
            # Ensure timezone-aware (UTC)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            else:
                created_at = created_at.astimezone(timezone.utc)

        expires_at = poll_data.get('expires_at')
        if expires_at and isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
            # Ensure timezone-aware (UTC)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            else:
                expires_at = expires_at.astimezone(timezone.utc)

        return cls(
            poll_id=poll_id,
            title=poll_data.get('title', ''),
            description=poll_data.get('description'),
            created_by=created_by,
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
        # Handle timezone conversion for datetime fields
        created_at = row[4]
        if created_at and isinstance(created_at, datetime):
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            else:
                created_at = created_at.astimezone(timezone.utc)

        expires_at = row[5]
        if expires_at and isinstance(expires_at, datetime):
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            else:
                expires_at = expires_at.astimezone(timezone.utc)

        return cls(
            poll_id=row[0],
            title=row[1],
            description=row[2],
            created_by=row[3],
            created_at=created_at,
            expires_at=expires_at,
            is_active=row[6]
        )

    @classmethod
    def from_poll_create(cls, poll_create: 'PollCreate', created_by: int) -> 'Poll':
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
        # Handle timezone conversion for expires_at
        expires_at = poll_create.expires_at
        if expires_at and isinstance(expires_at, datetime):
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            else:
                expires_at = expires_at.astimezone(timezone.utc)

        return cls(
            poll_id="",  # Will be assigned by database
            title=poll_create.title,
            description=poll_create.description,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            is_active=True
        )
