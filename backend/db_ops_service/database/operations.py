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

def increment_vote_count(cursor, option_id: str) -> bool:
    """
    Atomically increment the vote_count for a specific poll option.

    This function uses SQL UPDATE to atomically increment the vote_count field
    in the poll_options table. It should be called within the same transaction
    as create_vote() to ensure data consistency.

    Args:
        cursor: Database cursor for executing queries
        option_id (str): UUID of the poll option to increment

    Returns:
        bool: True if increment was successful

    Raises:
        psycopg.DataError: If option_id format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors

    Transaction Notes:
        - This function should be called within the same transaction as create_vote()
        - When autocommit=True, use explicit BEGIN/COMMIT blocks for atomicity
        - If either create_vote() or increment_vote_count() fails, rollback both
    """
    try:
        query = "UPDATE poll_options SET vote_count = vote_count + 1 WHERE id = %s"
        cursor.execute(query, (option_id,))

        if cursor.rowcount == 0:
            logger.warning(f"Vote count increment failed - option not found: {option_id}")
            raise ValueError(f"Poll option not found with ID: {option_id}")

        logger.info(f"Vote count incremented successfully for option: {option_id}")
        return True
    except psycopg.DataError as e:
        logger.error(f"Vote count increment failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Vote count increment failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Vote count increment failed - database error: {str(e)}")
        raise

def decrement_vote_count(cursor, option_id: str) -> bool:
    """
    Atomically decrement the vote_count for a specific poll option.

    This function uses SQL UPDATE to atomically decrement the vote_count field
    in the poll_options table. It should be called within the same transaction
    as delete_vote() to ensure data consistency.

    Args:
        cursor: Database cursor for executing queries
        option_id (str): UUID of the poll option to decrement

    Returns:
        bool: True if decrement was successful

    Raises:
        psycopg.DataError: If option_id format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors

    Transaction Notes:
        - This function should be called within the same transaction as delete_vote()
        - When autocommit=True, use explicit BEGIN/COMMIT blocks for atomicity
        - If either delete_vote() or decrement_vote_count() fails, rollback both
    """
    try:
        query = "UPDATE poll_options SET vote_count = vote_count - 1 WHERE id = %s"
        cursor.execute(query, (option_id,))

        if cursor.rowcount == 0:
            logger.warning(f"Vote count decrement failed - option not found: {option_id}")
            raise ValueError(f"Poll option not found with ID: {option_id}")

        logger.info(f"Vote count decremented successfully for option: {option_id}")
        return True
    except psycopg.DataError as e:
        logger.error(f"Vote count decrement failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Vote count decrement failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Vote count decrement failed - database error: {str(e)}")
        raise

def create_vote(cursor, user_id: int, poll_id: str, option_id: str) -> Dict[str, Any]:
    """
    Create a new vote for a user on a specific poll option and increment the vote count atomically.

    This function performs two operations in a single transaction:
    1. Insert a new vote record into the votes table
    2. Increment the vote_count for the selected option in poll_options table

    The UNIQUE constraint on (user_id, poll_id) prevents duplicate votes.
    Both operations are executed atomically - if either fails, both are rolled back.

    Args:
        cursor: Database cursor for executing queries
        user_id (int): ID of the user casting the vote
        poll_id (str): UUID of the poll being voted on
        option_id (str): UUID of the selected poll option

    Returns:
        Dict[str, Any]: Vote data including id, user_id, poll_id, option_id, and voted_at

    Raises:
        psycopg.IntegrityError: If user already voted on this poll (duplicate vote detected)
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors

    Transaction Notes:
        - Uses explicit BEGIN/COMMIT blocks for atomic execution
        - If autocommit=True on connection, transaction is isolated via BEGIN
        - If vote insertion fails (e.g., duplicate), transaction is rolled back
        - If vote count increment fails, transaction is rolled back
    """
    try:
        # Start explicit transaction for atomic operations
        cursor.execute("BEGIN")

        try:
            # Insert new vote record
            query = """INSERT INTO votes (user_id, poll_id, option_id)
                VALUES (%s, %s, %s) RETURNING id, user_id, poll_id, option_id, voted_at"""
            cursor.execute(query, (user_id, poll_id, option_id))
            row = cursor.fetchone()

            # Increment vote count for the selected option
            increment_vote_count(cursor, option_id)

            # Commit transaction
            cursor.execute("COMMIT")

            vote_data = {
                "id": str(row[0]),
                "user_id": row[1],
                "poll_id": str(row[2]),
                "option_id": str(row[3]),
                "voted_at": row[4].isoformat() if row[4] else None
            }

            logger.info(f"Vote created successfully - user: {user_id}, poll: {poll_id}, option: {option_id}")
            return vote_data

        except Exception as e:
            # Rollback transaction on any error
            cursor.execute("ROLLBACK")
            raise

    except psycopg.IntegrityError as e:
        logger.error(f"Vote creation failed - duplicate vote or invalid foreign key: {str(e)}")
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

def get_user_vote(cursor, user_id: int, poll_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a user's vote for a specific poll with option details.

    This function queries the votes table and joins with poll_options to include
    the option text and other details in the returned vote data.

    Args:
        cursor: Database cursor for executing queries
        user_id (int): ID of the user
        poll_id (str): UUID of the poll

    Returns:
        Optional[Dict[str, Any]]: Vote data if found, None if user hasn't voted on this poll.
            Returned dict includes: id, user_id, poll_id, option_id, voted_at,
            option_text, and vote_count

    Raises:
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
    """
    try:
        query = """
            SELECT v.id, v.user_id, v.poll_id, v.option_id, v.voted_at,
                   po.option_text, po.vote_count, po.display_order
            FROM votes v
            JOIN poll_options po ON v.option_id = po.id
            WHERE v.user_id=%s AND v.poll_id=%s
        """
        cursor.execute(query, (user_id, poll_id))
        row = cursor.fetchone()

        if not row:
            return None

        vote_data = {
            "id": str(row[0]),
            "user_id": row[1],
            "poll_id": str(row[2]),
            "option_id": str(row[3]),
            "voted_at": row[4].isoformat() if row[4] else None,
            "option_text": row[5],
            "vote_count": row[6],
            "display_order": row[7]
        }

        logger.info(f"User vote retrieved - user: {user_id}, poll: {poll_id}, option: {vote_data['option_text']}")
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

def get_poll_votes(cursor, poll_id: str) -> List[Dict[str, Any]]:
    """
    Get all votes for a specific poll with option details and aggregated data.

    This function queries all votes for a poll and joins with poll_options to include
    option text and vote counts. The returned data includes both individual vote records
    and aggregated vote count information per option.

    Args:
        cursor: Database cursor for executing queries
        poll_id (str): UUID of the poll

    Returns:
        List[Dict[str, Any]]: List of all votes for the poll with option details.
            Each dict includes: id, user_id, poll_id, option_id, voted_at,
            option_text, vote_count, and display_order

    Raises:
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
    """
    try:
        query = """
            SELECT v.id, v.user_id, v.poll_id, v.option_id, v.voted_at,
                   po.option_text, po.vote_count, po.display_order
            FROM votes v
            JOIN poll_options po ON v.option_id = po.id
            WHERE v.poll_id=%s
            ORDER BY v.voted_at DESC
        """
        cursor.execute(query, (poll_id,))
        rows = cursor.fetchall()

        votes = []
        for row in rows:
            vote_data = {
                "id": str(row[0]),
                "user_id": row[1],
                "poll_id": str(row[2]),
                "option_id": str(row[3]),
                "voted_at": row[4].isoformat() if row[4] else None,
                "option_text": row[5],
                "vote_count": row[6],
                "display_order": row[7]
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

# Alias for get_poll_votes to match naming convention in requirements
def get_votes_by_poll(cursor, poll_id: str) -> List[Dict[str, Any]]:
    """
    Alias for get_poll_votes(). Get all votes for a specific poll with option details.

    See get_poll_votes() documentation for full details.

    Args:
        cursor: Database cursor for executing queries
        poll_id (str): UUID of the poll

    Returns:
        List[Dict[str, Any]]: List of all votes for the poll with option details
    """
    return get_poll_votes(cursor, poll_id)

def delete_vote(cursor, user_id: int, poll_id: str) -> bool:
    """
    Delete a user's vote from a poll and decrement the vote count atomically.

    This function performs two operations in a single transaction:
    1. Retrieve the option_id from the vote being deleted
    2. Delete the vote record from the votes table
    3. Decrement the vote_count for the selected option in poll_options table

    Both operations are executed atomically - if either fails, both are rolled back.

    Args:
        cursor: Database cursor for executing queries
        user_id (int): ID of the user
        poll_id (str): UUID of the poll

    Returns:
        bool: True if vote was deleted, False if no vote was found

    Raises:
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors

    Transaction Notes:
        - Uses explicit BEGIN/COMMIT blocks for atomic execution
        - If autocommit=True on connection, transaction is isolated via BEGIN
        - If vote deletion fails (e.g., not found), returns False without error
        - If vote count decrement fails, transaction is rolled back
    """
    try:
        # Start explicit transaction for atomic operations
        cursor.execute("BEGIN")

        try:
            # First, get the option_id from the vote to be deleted
            query = "SELECT option_id FROM votes WHERE user_id=%s AND poll_id=%s"
            cursor.execute(query, (user_id, poll_id))
            row = cursor.fetchone()

            if not row:
                # No vote found, rollback and return False
                cursor.execute("ROLLBACK")
                logger.info(f"No vote found to delete - user: {user_id}, poll: {poll_id}")
                return False

            option_id = str(row[0])

            # Delete the vote record
            delete_query = "DELETE FROM votes WHERE user_id=%s AND poll_id=%s"
            cursor.execute(delete_query, (user_id, poll_id))

            # Decrement vote count for the option
            decrement_vote_count(cursor, option_id)

            # Commit transaction
            cursor.execute("COMMIT")

            logger.info(f"Vote deleted successfully - user: {user_id}, poll: {poll_id}, option: {option_id}")
            return True

        except Exception as e:
            # Rollback transaction on any error
            cursor.execute("ROLLBACK")
            raise

    except psycopg.DataError as e:
        logger.error(f"Delete vote failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Delete vote failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Delete vote failed - database error: {str(e)}")
        raise

def create_poll(cursor, title: str, description: str, created_by: int, expires_at, options: List[str]) -> Dict[str, Any]:
    """
    Create a new poll with associated options.

    Args:
        cursor: Database cursor for executing queries
        title (str): Title of the poll
        description (str): Description of the poll
        created_by (int): User ID of the poll creator
        expires_at: Expiration timestamp (datetime or None)
        options (List[str]): List of option texts for the poll

    Returns:
        Dict[str, Any]: Poll data including id, title, description, created_by, created_at, expires_at, is_active, and options

    Raises:
        psycopg.IntegrityError: If foreign key constraint fails or CHECK constraint fails
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
        ValueError: If options list is empty
    """
    if not options:
        raise ValueError("Poll must have at least one option")

    try:
        # Insert poll
        poll_query = """INSERT INTO polls (title, description, created_by, expires_at)
            VALUES (%s, %s, %s, %s) RETURNING id, title, description, created_by, created_at, expires_at, is_active"""
        cursor.execute(poll_query, (title, description, created_by, expires_at))
        poll_row = cursor.fetchone()

        poll_data = {
            "id": str(poll_row[0]),
            "title": poll_row[1],
            "description": poll_row[2],
            "created_by": poll_row[3],
            "created_at": poll_row[4].isoformat() if poll_row[4] else None,
            "expires_at": poll_row[5].isoformat() if poll_row[5] else None,
            "is_active": poll_row[6],
            "options": []
        }

        # Insert poll options
        option_query = """INSERT INTO poll_options (poll_id, option_text, display_order)
            VALUES (%s, %s, %s) RETURNING id, poll_id, option_text, vote_count, display_order"""

        for index, option_text in enumerate(options):
            cursor.execute(option_query, (poll_data["id"], option_text, index))
            option_row = cursor.fetchone()
            poll_data["options"].append({
                "id": str(option_row[0]),
                "poll_id": str(option_row[1]),
                "option_text": option_row[2],
                "vote_count": option_row[3],
                "display_order": option_row[4]
            })

        logger.info(f"Poll created successfully - id: {poll_data['id']}, title: {title}, options: {len(options)}")
        return poll_data
    except psycopg.IntegrityError as e:
        logger.error(f"Poll creation failed - integrity constraint violation: {str(e)}")
        raise
    except psycopg.DataError as e:
        logger.error(f"Poll creation failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Poll creation failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Poll creation failed - database error: {str(e)}")
        raise

def get_poll_by_id(cursor, poll_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a poll by its ID with all associated options.

    Args:
        cursor: Database cursor for executing queries
        poll_id (str): UUID of the poll

    Returns:
        Optional[Dict[str, Any]]: Poll data with options if found, None if not found

    Raises:
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
    """
    try:
        # Get poll data
        poll_query = """SELECT id, title, description, created_by, created_at, expires_at, is_active
                FROM polls WHERE id=%s"""
        cursor.execute(poll_query, (poll_id,))
        poll_row = cursor.fetchone()

        if not poll_row:
            return None

        poll_data = {
            "id": str(poll_row[0]),
            "title": poll_row[1],
            "description": poll_row[2],
            "created_by": poll_row[3],
            "created_at": poll_row[4].isoformat() if poll_row[4] else None,
            "expires_at": poll_row[5].isoformat() if poll_row[5] else None,
            "is_active": poll_row[6],
            "options": []
        }

        # Get poll options
        options_query = """SELECT id, poll_id, option_text, vote_count, display_order
                FROM poll_options WHERE poll_id=%s ORDER BY display_order"""
        cursor.execute(options_query, (poll_id,))
        option_rows = cursor.fetchall()

        for option_row in option_rows:
            poll_data["options"].append({
                "id": str(option_row[0]),
                "poll_id": str(option_row[1]),
                "option_text": option_row[2],
                "vote_count": option_row[3],
                "display_order": option_row[4]
            })

        logger.info(f"Poll retrieved - id: {poll_id}, options: {len(poll_data['options'])}")
        return poll_data
    except psycopg.DataError as e:
        logger.error(f"Get poll by ID failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Get poll by ID failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Get poll by ID failed - database error: {str(e)}")
        raise

def get_active_polls(cursor) -> List[Dict[str, Any]]:
    """
    Get all active polls with their options using a single JOIN query.

    Optimized to eliminate N+1 query pattern by fetching polls and options
    in a single database query, then grouping results in Python.

    Args:
        cursor: Database cursor for executing queries

    Returns:
        List[Dict[str, Any]]: List of active polls with their options

    Raises:
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
    """
    try:
        # Single query with LEFT JOIN to fetch polls and their options
        # This eliminates the N+1 query pattern by reducing N+1 queries to just 1
        query = """
            SELECT p.id, p.title, p.description, p.created_by, p.created_at, p.expires_at, p.is_active,
                   po.id, po.poll_id, po.option_text, po.vote_count, po.display_order
            FROM polls p
            LEFT JOIN poll_options po ON p.id = po.poll_id
            WHERE p.is_active = TRUE
            ORDER BY p.created_at DESC, po.display_order
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        # Group results by poll_id to structure the response
        polls_dict = {}
        for row in rows:
            poll_id = str(row[0])

            # Create poll entry if it doesn't exist
            if poll_id not in polls_dict:
                polls_dict[poll_id] = {
                    "id": poll_id,
                    "title": row[1],
                    "description": row[2],
                    "created_by": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                    "expires_at": row[5].isoformat() if row[5] else None,
                    "is_active": row[6],
                    "options": []
                }

            # Add option if it exists (LEFT JOIN may return NULL for polls without options)
            if row[7] is not None:
                polls_dict[poll_id]["options"].append({
                    "id": str(row[7]),
                    "poll_id": str(row[8]),
                    "option_text": row[9],
                    "vote_count": row[10],
                    "display_order": row[11]
                })

        # Convert dict to list, maintaining order from ORDER BY clause
        polls = list(polls_dict.values())

        logger.info(f"Active polls retrieved - count: {len(polls)}")
        return polls
    except psycopg.DataError as e:
        logger.error(f"Get active polls failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Get active polls failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Get active polls failed - database error: {str(e)}")
        raise

def get_user_polls(cursor, user_id: int) -> List[Dict[str, Any]]:
    """
    Get all polls created by a specific user with their options.

    Args:
        cursor: Database cursor for executing queries
        user_id (int): ID of the user

    Returns:
        List[Dict[str, Any]]: List of polls created by the user with their options

    Raises:
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
    """
    try:
        # Get all polls by user
        polls_query = """SELECT id, title, description, created_by, created_at, expires_at, is_active
                FROM polls WHERE created_by=%s ORDER BY created_at DESC"""
        cursor.execute(polls_query, (user_id,))
        poll_rows = cursor.fetchall()

        polls = []
        for poll_row in poll_rows:
            poll_data = {
                "id": str(poll_row[0]),
                "title": poll_row[1],
                "description": poll_row[2],
                "created_by": poll_row[3],
                "created_at": poll_row[4].isoformat() if poll_row[4] else None,
                "expires_at": poll_row[5].isoformat() if poll_row[5] else None,
                "is_active": poll_row[6],
                "options": []
            }

            # Get options for this poll
            options_query = """SELECT id, poll_id, option_text, vote_count, display_order
                    FROM poll_options WHERE poll_id=%s ORDER BY display_order"""
            cursor.execute(options_query, (str(poll_row[0]),))
            option_rows = cursor.fetchall()

            for option_row in option_rows:
                poll_data["options"].append({
                    "id": str(option_row[0]),
                    "poll_id": str(option_row[1]),
                    "option_text": option_row[2],
                    "vote_count": option_row[3],
                    "display_order": option_row[4]
                })

            polls.append(poll_data)

        logger.info(f"User polls retrieved - user: {user_id}, count: {len(polls)}")
        return polls
    except psycopg.DataError as e:
        logger.error(f"Get user polls failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Get user polls failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Get user polls failed - database error: {str(e)}")
        raise

def update_poll_status(cursor, poll_id: str, is_active: bool) -> bool:
    """
    Update the active status of a poll.

    Args:
        cursor: Database cursor for executing queries
        poll_id (str): UUID of the poll
        is_active (bool): New active status

    Returns:
        bool: True if poll was updated, False if poll not found

    Raises:
        psycopg.DataError: If data format is invalid
        psycopg.OperationalError: If database connection issue
        psycopg.DatabaseError: For general database errors
    """
    try:
        query = "UPDATE polls SET is_active=%s WHERE id=%s"
        cursor.execute(query, (is_active, poll_id))

        updated = cursor.rowcount > 0
        if updated:
            logger.info(f"Poll status updated - id: {poll_id}, is_active: {is_active}")
        else:
            logger.warning(f"Poll not found for status update - id: {poll_id}")

        return updated
    except psycopg.DataError as e:
        logger.error(f"Update poll status failed - invalid data format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Update poll status failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Update poll status failed - database error: {str(e)}")
        raise
