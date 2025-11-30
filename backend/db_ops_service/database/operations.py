import uuid
import time
import psycopg
import logging
import json
from typing import Optional, Dict, Any, List
from models.User import User
from db_ops_service.database.connection import DatabaseManager

logger = logging.getLogger(__name__)
logging.basicConfig(filename='myapp.log', level=logging.INFO)

def create_user(cursor, user: User) -> User:
    """
    Create a new user in the database from User object.
    
    Args:
        cursor: Database cursor for executing queries
        user (User): User object containing email and password_hash
        
    Returns:
        User: Updated User object with generated verification_token and user_id from database
        
    Raises:
        psycopg.IntegrityError: If email already exists
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
    """
    try:
        verification_token = f"{uuid.uuid4()}-{int(time.time())}"
        query = """INSERT INTO users (email, password_hash, is_verified, verification_token) 
            VALUES (%s, %s, %s, %s) RETURNING id"""
        cursor.execute(query, (user.email, user.password_hash, False, verification_token))
        user_id = cursor.fetchone()[0]
        
        # Update the user object with the database-generated values
        user.user_id = user_id
        user.verification_token = verification_token
        user.is_verified = False
        
        return user
    except psycopg.IntegrityError as e:
        logger.error(f"User creation failed - email already exists: {str(e)}")
        raise
    except psycopg.DataError as e:
        logger.error(f"User creation failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"User creation failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"User creation failed - database error: {str(e)}")
        raise
    
def verify_user(cursor, user: User) -> User:
    """
    Mark user as verified by updating their verification status.
    
    Args:
        cursor: Database cursor for executing queries
        user (User): User object containing verification_token
        
    Returns:
        User: Updated User object with is_verified set to True
        
    Raises:
        psycopg.DataError: If token format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
        ValueError: If user's verification token is None
    """
    if user.verification_token is None:
        raise ValueError("User verification token cannot be None")
        
    try:
        query = "UPDATE users SET is_verified = %s WHERE verification_token = %s;"
        cursor.execute(query, (True, user.verification_token))
        if cursor.rowcount == 0:
            logger.warning(f"Verification failed - token not found: {user.verification_token}")
            raise ValueError(f"Verification token not found: {user.verification_token}")
        else:
            logger.info(f"User verified successfully with token: {user.verification_token}")
            # Update the user object
            user.is_verified = True
            return user
    except psycopg.DataError as e:
        logger.error(f"User verification failed - invalid token format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"User verification failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"User verification failed - database error: {str(e)}")
        raise
    
def update_user_password(cursor, user: User, new_password_hash: str) -> User:
    """
    Update user's password hash for rehashing purposes.
    
    Args:
        cursor: Database cursor for executing queries
        user (User): User object to update
        new_password_hash (str): New hashed password to store
        
    Returns:
        User: Updated User object with new password hash
        
    Raises:
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
        ValueError: If user not found in database
    """
    try:
        query = "UPDATE users SET password_hash = %s WHERE id = %s;"
        cursor.execute(query, (new_password_hash, user.user_id))
        if cursor.rowcount == 0:
            logger.warning(f"Password update failed - user not found: {user.user_id}")
            raise ValueError(f"User not found with ID: {user.user_id}")
        else:
            logger.info(f"Password hash updated successfully for user: {user.user_id}")
            # Update the user object
            user.password_hash = new_password_hash
            return user
    except psycopg.DataError as e:
        logger.error(f"Password update failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Password update failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Password update failed - database error: {str(e)}")
        raise

def get_user_by_id(cursor, user_id: int) -> Optional[User]:
    """
    Retrieve a user from database by their ID and return as User object.
    
    Args:
        cursor: Database cursor for executing queries
        user_id (int): ID of the user to retrieve
        
    Returns:
        Optional[User]: User object if found, None if not found
        
    Raises:
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
    """
    try:
        query = """SELECT id, email, password_hash, is_verified, verification_token, created_at 
                FROM users WHERE id=%s"""
        cursor.execute(query, (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return User(
            user_id=row[0],
            email=row[1],
            password_hash=row[2],
            is_verified=row[3],
            verification_token=row[4],
            created_at=row[5]
        )
    except psycopg.DataError as e:
        logger.error(f"Get user by ID failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Get user by ID failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Get user by ID failed - database error: {str(e)}")
        raise

def get_user_by_email_as_user(cursor, email: str) -> Optional[User]:
    """
    Retrieve a user from database by their email and return as User object.
    Uses Redis (if available) to cache user lookup by email.
    """
    try:
        # Attempt to read from Redis cache first
        redis_client = DatabaseManager().redis_client
        cache_key = f"user:email:{email}"
        if redis_client:
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    return User(
                        user_id=data.get("user_id"),
                        email=data.get("email"),
                        password_hash=data.get("password_hash"),
                        is_verified=data.get("is_verified"),
                        verification_token=data.get("verification_token"),
                        created_at=data.get("created_at")
                    )
            except Exception as e:
                logger.warning(f"Redis get failed for key {cache_key}: {e}")

        # Fallback to Postgres
        query = """SELECT id, email, password_hash, is_verified, verification_token, created_at 
                FROM users WHERE email=%s"""
        cursor.execute(query, (email,))
        row = cursor.fetchone()
        if not row:
            return None

        user = User(
            user_id=row[0],
            email=row[1],
            password_hash=row[2],
            is_verified=row[3],
            verification_token=row[4],
            created_at=row[5]
        )

        # Cache result in Redis for subsequent lookups
        if redis_client:
            try:
                redis_client.set(cache_key, json.dumps({
                    "user_id": user.user_id,
                    "email": user.email,
                    "password_hash": user.password_hash,
                    "is_verified": user.is_verified,
                    "verification_token": user.verification_token,
                    "created_at": str(user.created_at)
                }), ex=3600)
            except Exception as e:
                logger.warning(f"Failed to cache user in Redis: {e}")

        return user
    except psycopg.DataError as e:
        logger.error(f"Get user by email failed - invalid email format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Get user by email failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Get user by email failed - database error: {str(e)}")
        raise

def cast_vote(cursor, user_id: int, poll_id: int, option_id: int) -> Dict[str, Any]:
    """
    Cast a vote for a user on a specific poll option.

    Args:
        cursor: Database cursor for executing queries
        user_id (int): ID of the user casting the vote
        poll_id (int): ID of the poll being voted on
        option_id (int): ID of the selected poll option

    Returns:
        Dict[str, Any]: Vote data including id, user_id, poll_id, option_id, and voted_at

    Raises:
        psycopg.IntegrityError: If user has already voted on this poll or foreign key constraint fails
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
    """
    try:
        query = """INSERT INTO votes (user_id, poll_id, option_id)
            VALUES (%s, %s, %s) RETURNING id, user_id, poll_id, option_id, voted_at"""
        cursor.execute(query, (user_id, poll_id, option_id))
        row = cursor.fetchone()

        vote_data = {
            "id": str(row[0]),
            "user_id": row[1],
            "poll_id": row[2],
            "option_id": row[3],
            "voted_at": row[4].isoformat() if row[4] else None
        }

        logger.info(f"Vote cast successfully - user: {user_id}, poll: {poll_id}, option: {option_id}")
        return vote_data
    except psycopg.IntegrityError as e:
        logger.error(f"Vote casting failed - duplicate vote or invalid foreign key: {str(e)}")
        raise
    except psycopg.DataError as e:
        logger.error(f"Vote casting failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Vote casting failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Vote casting failed - database error: {str(e)}")
        raise

def get_user_vote(cursor, user_id: int, poll_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve a user's vote for a specific poll.

    Args:
        cursor: Database cursor for executing queries
        user_id (int): ID of the user
        poll_id (int): ID of the poll

    Returns:
        Optional[Dict[str, Any]]: Vote data if found, None if user hasn't voted on this poll

    Raises:
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
    """
    try:
        query = """SELECT id, user_id, poll_id, option_id, voted_at
                FROM votes WHERE user_id=%s AND poll_id=%s"""
        cursor.execute(query, (user_id, poll_id))
        row = cursor.fetchone()

        if not row:
            return None

        vote_data = {
            "id": str(row[0]),
            "user_id": row[1],
            "poll_id": row[2],
            "option_id": row[3],
            "voted_at": row[4].isoformat() if row[4] else None
        }

        logger.info(f"User vote retrieved - user: {user_id}, poll: {poll_id}")
        return vote_data
    except psycopg.DataError as e:
        logger.error(f"Get user vote failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Get user vote failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Get user vote failed - database error: {str(e)}")
        raise

def get_poll_votes(cursor, poll_id: int) -> List[Dict[str, Any]]:
    """
    Get all votes for a specific poll.

    Args:
        cursor: Database cursor for executing queries
        poll_id (int): ID of the poll

    Returns:
        List[Dict[str, Any]]: List of all votes for the poll

    Raises:
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
    """
    try:
        query = """SELECT id, user_id, poll_id, option_id, voted_at
                FROM votes WHERE poll_id=%s"""
        cursor.execute(query, (poll_id,))
        rows = cursor.fetchall()

        votes = []
        for row in rows:
            vote_data = {
                "id": str(row[0]),
                "user_id": row[1],
                "poll_id": row[2],
                "option_id": row[3],
                "voted_at": row[4].isoformat() if row[4] else None
            }
            votes.append(vote_data)

        logger.info(f"Poll votes retrieved - poll: {poll_id}, count: {len(votes)}")
        return votes
    except psycopg.DataError as e:
        logger.error(f"Get poll votes failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Get poll votes failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Get poll votes failed - database error: {str(e)}")
        raise

def delete_vote(cursor, user_id: int, poll_id: int) -> bool:
    """
    Delete a user's vote from a poll.

    Args:
        cursor: Database cursor for executing queries
        user_id (int): ID of the user
        poll_id (int): ID of the poll

    Returns:
        bool: True if vote was deleted, False if no vote was found

    Raises:
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
    """
    try:
        query = "DELETE FROM votes WHERE user_id=%s AND poll_id=%s"
        cursor.execute(query, (user_id, poll_id))

        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Vote deleted successfully - user: {user_id}, poll: {poll_id}")
        else:
            logger.info(f"No vote found to delete - user: {user_id}, poll: {poll_id}")

        return deleted
    except psycopg.DataError as e:
        logger.error(f"Delete vote failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Delete vote failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Delete vote failed - database error: {str(e)}")
        raise
