from typing import Optional, Dict, Any
from datetime import datetime
from models.auth_models import UserRegistrationRequest


class User:
    def __init__(
        self,
        user_id: int,
        email: str,
        password_hash: str,
        is_verified: bool = False,
        verification_token: Optional[str] = None,
        created_at: Optional[datetime] = None
    ) -> None:
        self.user_id = user_id
        self.email = email
        self.password_hash = password_hash
        self.is_verified = is_verified
        self.verification_token = verification_token
        self.created_at = created_at or datetime.now()

    def __str__(self) -> str:
        return f"User(id={self.user_id}, email={self.email}, verified={self.is_verified})"

    def __repr__(self) -> str:
        return (f"User(user_id={self.user_id}, email='{self.email}', "
                f"password_hash='***', is_verified={self.is_verified}, "
                f"verification_token='{self.verification_token}', "
                f"created_at={self.created_at})")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, User):
            return NotImplemented
        return self.user_id == other.user_id and self.email == other.email

    def __hash__(self) -> int:
        return hash((self.user_id, self.email))

    def __bool__(self) -> bool:
        return self.user_id is not None and self.email is not None

    def to_api_dict(self) -> Dict[str, Any]:
        """
        Convert user to dictionary safe for API responses (excludes sensitive data).
        
        Returns:
            Dict[str, Any]: User data without password_hash or verification_token
        """
        return {
            "user_id": self.user_id,
            "email": self.email,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def to_full_dict(self) -> Dict[str, Any]:
        """
        Convert user to complete dictionary including all fields (for internal use).
        
        Returns:
            Dict[str, Any]: Complete user data including sensitive fields
            
        Warning:
            Contains password_hash and verification_token - use only for internal operations
        """
        return {
            "user_id": self.user_id,
            "email": self.email,
            "password_hash": self.password_hash,
            "is_verified": self.is_verified,
            "verification_token": self.verification_token,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def is_verified_status(self) -> bool:
        """
        Check if user's email has been verified.
        
        Returns:
            bool: True if email is verified, False otherwise
        """
        return self.is_verified

    def can_login(self) -> bool:
        """
        Check if user is allowed to authenticate/login.
        
        Returns:
            bool: True if user can login (currently requires email verification)
        """
        return self.is_verified

    @classmethod
    def from_dict(cls, user_data: Dict[str, Any]) -> 'User':
        """
        Create a User object from dictionary data.
        
        Args:
            user_data (Dict[str, Any]): Dictionary containing user fields
            
        Returns:
            User: New User instance created from the data
            
        Raises:
            ValueError: If required fields are missing or invalid
            
        Note:
            Handles both database row data and API request data.
            Missing optional fields will use default values.
        """
        # Handle different field name variations that might come from different sources
        user_id = user_data.get('user_id')
        if user_id is None:
            raise ValueError("user_id field is required")
        
        # Ensure user_id is an integer
        if not isinstance(user_id, int):
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                raise ValueError(f"user_id must be an integer, got {type(user_id)}")
        
        created_at = user_data.get('created_at')
        
        return cls(
            user_id=user_id,
            email=user_data['email'],
            password_hash=user_data['password_hash'],
            is_verified=user_data.get('is_verified', False),
            verification_token=user_data.get('verification_token'),
            created_at=created_at
        )

    @classmethod
    def from_db_row(cls, row: tuple) -> 'User':
        """
        Create a User object from database row tuple.
        
        Args:
            row (tuple): Database row as tuple (id, email, password_hash, is_verified, verification_token, created_at)
            
        Returns:
            User: New User instance created from database row
            
        Note:
            Expects row fields in the order: id, email, password_hash, is_verified, verification_token, created_at
        """
        return cls(
            user_id=row[0],
            email=row[1], 
            password_hash=row[2],
            is_verified=row[3],
            verification_token=row[4],
            created_at=row[5]
        )

    @classmethod
    def from_user_registration_request(cls, registration_data: UserRegistrationRequest) -> 'User':
        """
        Create a User object from UserRegistrationRequest Pydantic model for processing registration.
        
        Args:
            registration_data (UserRegistrationRequest): Pydantic model containing email and password
            
        Returns:
            User: New User instance ready for registration processing
            
        Note:
            - user_id is set to 0 since it will be assigned by database during insertion
            - Password will need to be hashed before database storage
            - User will be created as unverified (is_verified=False)
            - Verification token will be generated during database creation
        """
        return cls(
            user_id=0,  # Will be assigned by database during insertion
            email=str(registration_data.email),
            password_hash=registration_data.password,  
            is_verified=False,
            verification_token=None, 
            created_at=datetime.now()
        )
