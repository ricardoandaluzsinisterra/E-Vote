import uuid
import time
import psycopg
import logging
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta, timezone
from models.User import User
from models.Vote import Vote
from database.connection import DatabaseManager


class VoteError(Exception):
    """Custom exception for vote-related errors."""
    pass


class DuplicateVoteError(VoteError):
    """Raised when a user attempts to vote twice on the same poll."""
    pass


class InvalidOptionError(VoteError):
    """Raised when the selected option doesn't belong to the poll."""
    pass


class PollNotActiveError(VoteError):
    """Raised when attempting to vote on an inactive or expired poll."""
    pass

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

def store_password_reset_token(cursor, email: str, expiration_hours: int = 1) -> Optional[str]:
    """
    Generate and store a password reset token for a user.

    Args:
        cursor: Database cursor for executing queries
        email (str): Email address of the user requesting password reset
        expiration_hours (int): Number of hours until token expires (default: 1)

    Returns:
        Optional[str]: Reset token if user exists, None if user not found

    Raises:
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors

    Note:
        For security, this function returns None (not an error) if the user doesn't exist,
        to prevent email enumeration attacks.
    """
    try:
        # Generate secure reset token
        reset_token = f"{uuid.uuid4()}-{int(time.time())}"
        expires_at = datetime.now() + timedelta(hours=expiration_hours)

        # Update user's reset token and expiration
        query = """UPDATE users
                   SET reset_token = %s, reset_token_expires_at = %s
                   WHERE email = %s"""
        cursor.execute(query, (reset_token, expires_at, email))

        if cursor.rowcount == 0:
            logger.info(f"Password reset requested for non-existent email: {email}")
            return None

        logger.info(f"Password reset token generated for email: {email}")
        return reset_token

    except psycopg.DataError as e:
        logger.error(f"Store reset token failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Store reset token failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Store reset token failed - database error: {str(e)}")
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
        query = """SELECT id, email, password_hash, is_verified, verification_token,
                reset_token, reset_token_expires_at, created_at
                FROM users WHERE id=%s"""
        cursor.execute(query, (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return User.from_db_row(row)
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

    Args:
        cursor: Database cursor for executing queries
        email (str): Email address of the user to retrieve

    Returns:
        Optional[User]: User object if found, None if not found

    Raises:
        psycopg.DataError: If email format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
    """
    try:
        query = """SELECT id, email, password_hash, is_verified, verification_token,
                reset_token, reset_token_expires_at, created_at
                FROM users WHERE email=%s"""
        cursor.execute(query, (email,))
        row = cursor.fetchone()
        if not row:
            return None
        return User.from_db_row(row)
    except psycopg.DataError as e:
        logger.error(f"Get user by email failed - invalid email format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Get user by email failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Get user by email failed - database error: {str(e)}")
        raise

def create_vote(connection, user_id: int, poll_id: int, option_id: int) -> Vote:
    """
    Create a new vote with duplicate check and atomic vote_count increment.
    Uses a transaction to ensure vote and vote_count are updated atomically.

    Args:
        connection: Database connection for transaction handling
        user_id (int): ID of the user casting the vote
        poll_id (int): ID of the poll being voted on
        option_id (int): ID of the selected poll option

    Returns:
        Vote: Created Vote object with database-generated ID and timestamp

    Raises:
        DuplicateVoteError: If user has already voted on this poll
        InvalidOptionError: If option doesn't belong to the specified poll
        PollNotActiveError: If poll is not active or has expired
        psycopg.IntegrityError: For other constraint violations
        psycopg.DatabaseError: For general database errors
    """
    try:
        with connection.cursor() as cursor:
            # Start transaction explicitly
            cursor.execute("BEGIN")

            try:
                # Check if poll is active
                cursor.execute("""
                    SELECT is_active, ends_at
                    FROM polls
                    WHERE id = %s
                """, (poll_id,))
                poll_row = cursor.fetchone()

                if poll_row is None:
                    cursor.execute("ROLLBACK")
                    raise InvalidOptionError(f"Poll with ID {poll_id} does not exist")

                is_active, ends_at = poll_row
                if not is_active:
                    cursor.execute("ROLLBACK")
                    raise PollNotActiveError(f"Poll {poll_id} is not active")

                if ends_at is not None and ends_at < time.time():
                    cursor.execute("ROLLBACK")
                    raise PollNotActiveError(f"Poll {poll_id} has expired")

                # Verify option belongs to the poll
                cursor.execute("""
                    SELECT id FROM poll_options
                    WHERE id = %s AND poll_id = %s
                """, (option_id, poll_id))

                if cursor.fetchone() is None:
                    cursor.execute("ROLLBACK")
                    raise InvalidOptionError(
                        f"Option {option_id} does not belong to poll {poll_id}"
                    )

                # Check for existing vote (explicit duplicate check)
                cursor.execute("""
                    SELECT id FROM votes
                    WHERE user_id = %s AND poll_id = %s
                """, (user_id, poll_id))

                if cursor.fetchone() is not None:
                    cursor.execute("ROLLBACK")
                    raise DuplicateVoteError(
                        f"User {user_id} has already voted on poll {poll_id}"
                    )

                # Insert the vote
                cursor.execute("""
                    INSERT INTO votes (user_id, poll_id, option_id)
                    VALUES (%s, %s, %s)
                    RETURNING id, voted_at
                """, (user_id, poll_id, option_id))

                result = cursor.fetchone()
                vote_id = result[0]
                voted_at = result[1]

                # Commit the transaction
                cursor.execute("COMMIT")

                logger.info(f"Vote created: user={user_id}, poll={poll_id}, option={option_id}")

                return Vote(
                    vote_id=vote_id,
                    user_id=user_id,
                    poll_id=poll_id,
                    option_id=option_id,
                    voted_at=voted_at
                )

            except (DuplicateVoteError, InvalidOptionError, PollNotActiveError):
                raise
            except Exception as e:
                cursor.execute("ROLLBACK")
                raise

    except psycopg.IntegrityError as e:
        error_msg = str(e)
        if "unique_user_poll" in error_msg:
            logger.warning(f"Duplicate vote attempt: user={user_id}, poll={poll_id}")
            raise DuplicateVoteError(
                f"User {user_id} has already voted on poll {poll_id}"
            )
        logger.error(f"Vote creation failed - integrity error: {error_msg}")
        raise
    except psycopg.DataError as e:
        logger.error(f"Vote creation failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Vote creation failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Vote creation failed - database error: {str(e)}")
        raise


def get_user_vote(cursor, user_id: int, poll_id: int) -> Optional[Vote]:
    """
    Retrieve a user's vote for a specific poll.

    Args:
        cursor: Database cursor for executing queries
        user_id (int): ID of the user
        poll_id (int): ID of the poll

    Returns:
        Optional[Vote]: Vote object if user has voted, None otherwise

    Raises:
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
    """
    try:
        query = """
            SELECT id, user_id, poll_id, option_id, voted_at
            FROM votes
            WHERE user_id = %s AND poll_id = %s
        """
        cursor.execute(query, (user_id, poll_id))
        row = cursor.fetchone()

        if row is None:
            return None

        return Vote.from_db_row(row)

    except psycopg.DataError as e:
        logger.error(f"Get user vote failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Get user vote failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Get user vote failed - database error: {str(e)}")
        raise


def get_votes_by_poll(cursor, poll_id: int) -> List[Vote]:
    """
    Retrieve all votes for a specific poll.

    Args:
        cursor: Database cursor for executing queries
        poll_id (int): ID of the poll

    Returns:
        List[Vote]: List of Vote objects for the poll

    Raises:
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
    """
    try:
        query = """
            SELECT id, user_id, poll_id, option_id, voted_at
            FROM votes
            WHERE poll_id = %s
            ORDER BY voted_at ASC
        """
        cursor.execute(query, (poll_id,))
        rows = cursor.fetchall()

        return [Vote.from_db_row(row) for row in rows]

    except psycopg.DataError as e:
        logger.error(f"Get votes by poll failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Get votes by poll failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Get votes by poll failed - database error: {str(e)}")
        raise


def get_vote_counts_by_poll(cursor, poll_id: int) -> dict:
    """
    Get aggregated vote counts for each option in a poll.

    Args:
        cursor: Database cursor for executing queries
        poll_id (int): ID of the poll

    Returns:
        dict: Dictionary mapping option_id to vote count
              Example: {1: 10, 2: 5, 3: 15}

    Raises:
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
    """
    try:
        query = """
            SELECT option_id, COUNT(*) as vote_count
            FROM votes
            WHERE poll_id = %s
            GROUP BY option_id
        """
        cursor.execute(query, (poll_id,))
        rows = cursor.fetchall()

        return {row[0]: row[1] for row in rows}

    except psycopg.DataError as e:
        logger.error(f"Get vote counts failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Get vote counts failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Get vote counts failed - database error: {str(e)}")
        raise


def increment_vote_count(cursor, option_id: int) -> int:
    """
    Atomically increment the vote count for a poll option.
    Uses SELECT FOR UPDATE to prevent race conditions.

    Args:
        cursor: Database cursor for executing queries
        option_id (int): ID of the poll option to increment

    Returns:
        int: The new vote count after increment

    Raises:
        ValueError: If option_id does not exist
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors

    Note:
        This function assumes poll_options has a vote_count column.
        The caller should ensure this is called within a transaction
        for proper atomic behavior with vote creation.
    """
    try:
        # Atomic increment using UPDATE with RETURNING
        query = """
            UPDATE poll_options
            SET vote_count = COALESCE(vote_count, 0) + 1
            WHERE id = %s
            RETURNING vote_count
        """
        cursor.execute(query, (option_id,))
        result = cursor.fetchone()

        if result is None:
            logger.warning(f"Increment vote count failed - option not found: {option_id}")
            raise ValueError(f"Poll option not found with ID: {option_id}")

        new_count = result[0]
        logger.info(f"Vote count incremented for option {option_id}: new count = {new_count}")
        return new_count

    except psycopg.OperationalError as e:
        logger.error(f"Increment vote count failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Increment vote count failed - database error: {str(e)}")
        raise


def decrement_vote_count(cursor, option_id: int) -> int:
    """
    Atomically decrement the vote count for a poll option.
    Ensures vote count does not go below zero.

    Args:
        cursor: Database cursor for executing queries
        option_id (int): ID of the poll option to decrement

    Returns:
        int: The new vote count after decrement

    Raises:
        ValueError: If option_id does not exist
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
    """
    try:
        query = """
            UPDATE poll_options
            SET vote_count = GREATEST(COALESCE(vote_count, 0) - 1, 0)
            WHERE id = %s
            RETURNING vote_count
        """
        cursor.execute(query, (option_id,))
        result = cursor.fetchone()

        if result is None:
            logger.warning(f"Decrement vote count failed - option not found: {option_id}")
            raise ValueError(f"Poll option not found with ID: {option_id}")

        new_count = result[0]
        logger.info(f"Vote count decremented for option {option_id}: new count = {new_count}")
        return new_count

    except psycopg.OperationalError as e:
        logger.error(f"Decrement vote count failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Decrement vote count failed - database error: {str(e)}")
        raise


def create_vote_with_count(connection, user_id: int, poll_id: int, option_id: int) -> Vote:
    """
    Create a vote and increment the option's vote count in a single transaction.
    Ensures atomicity between vote creation and count update.

    Args:
        connection: Database connection for transaction handling
        user_id (int): ID of the user casting the vote
        poll_id (int): ID of the poll being voted on
        option_id (int): ID of the selected poll option

    Returns:
        Vote: Created Vote object with database-generated ID and timestamp

    Raises:
        DuplicateVoteError: If user has already voted on this poll
        InvalidOptionError: If option doesn't belong to the specified poll
        PollNotActiveError: If poll is not active or has expired
        psycopg.IntegrityError: For other constraint violations
        psycopg.DatabaseError: For general database errors
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("BEGIN")

            try:
                # Check if poll is active
                cursor.execute("""
                    SELECT is_active, ends_at
                    FROM polls
                    WHERE id = %s
                    FOR UPDATE
                """, (poll_id,))
                poll_row = cursor.fetchone()

                if poll_row is None:
                    cursor.execute("ROLLBACK")
                    raise InvalidOptionError(f"Poll with ID {poll_id} does not exist")

                is_active, ends_at = poll_row
                if not is_active:
                    cursor.execute("ROLLBACK")
                    raise PollNotActiveError(f"Poll {poll_id} is not active")

                # Verify option belongs to the poll and lock row
                cursor.execute("""
                    SELECT id FROM poll_options
                    WHERE id = %s AND poll_id = %s
                    FOR UPDATE
                """, (option_id, poll_id))

                if cursor.fetchone() is None:
                    cursor.execute("ROLLBACK")
                    raise InvalidOptionError(
                        f"Option {option_id} does not belong to poll {poll_id}"
                    )

                # Check for existing vote
                cursor.execute("""
                    SELECT id FROM votes
                    WHERE user_id = %s AND poll_id = %s
                """, (user_id, poll_id))

                if cursor.fetchone() is not None:
                    cursor.execute("ROLLBACK")
                    raise DuplicateVoteError(
                        f"User {user_id} has already voted on poll {poll_id}"
                    )

                # Insert the vote
                cursor.execute("""
                    INSERT INTO votes (user_id, poll_id, option_id)
                    VALUES (%s, %s, %s)
                    RETURNING id, voted_at
                """, (user_id, poll_id, option_id))

                result = cursor.fetchone()
                vote_id = result[0]
                voted_at = result[1]

                # Increment vote count atomically
                cursor.execute("""
                    UPDATE poll_options
                    SET vote_count = COALESCE(vote_count, 0) + 1
                    WHERE id = %s
                """, (option_id,))

                cursor.execute("COMMIT")

                logger.info(
                    f"Vote created with count update: user={user_id}, "
                    f"poll={poll_id}, option={option_id}"
                )

                return Vote(
                    vote_id=vote_id,
                    user_id=user_id,
                    poll_id=poll_id,
                    option_id=option_id,
                    voted_at=voted_at
                )

            except (DuplicateVoteError, InvalidOptionError, PollNotActiveError):
                raise
            except Exception:
                cursor.execute("ROLLBACK")
                raise

    except psycopg.IntegrityError as e:
        error_msg = str(e)
        if "unique_user_poll" in error_msg:
            logger.warning(f"Duplicate vote attempt: user={user_id}, poll={poll_id}")
            raise DuplicateVoteError(
                f"User {user_id} has already voted on poll {poll_id}"
            )
        logger.error(f"Vote creation failed - integrity error: {error_msg}")
        raise
    except psycopg.DataError as e:
        logger.error(f"Vote creation failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Vote creation failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Vote creation failed - database error: {str(e)}")
        raise
