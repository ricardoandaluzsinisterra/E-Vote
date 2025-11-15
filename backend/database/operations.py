import uuid
import time
import psycopg
import logging
from typing import Optional
from models.User import User
from database.connection import DatabaseManager

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
        query = """SELECT id, email, password_hash, is_verified, verification_token, created_at 
                FROM users WHERE email=%s"""
        cursor.execute(query, (email,))
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
        logger.error(f"Get user by email failed - invalid email format: {str(e)}")
        raise
    except psycopg.OperationalError as e:
        logger.error(f"Get user by email failed - database connection issue: {str(e)}")
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Get user by email failed - database error: {str(e)}")
        raise
