import logging
from typing import List
from fastapi import APIRouter, Request, HTTPException, status
from backend.middleware import require_auth
from backend.models.poll_models import (
    PollResponse,
    PollCreate,
    PollCreatedResponse,
    PollOption
)
from backend.db_ops_service.database.operations import (
    get_active_polls,
    get_poll_by_id,
    create_poll
)
from backend.db_ops_service.database.connection import DatabaseManager
import psycopg

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/polls", tags=["polls"])


def get_db_cursor():
    """Helper function to get database cursor from singleton DatabaseManager"""
    db = DatabaseManager()
    if db.cursor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    return db.cursor


@router.get("", response_model=List[PollResponse])
@require_auth
async def get_polls(
    request: Request,
    active_only: bool = True
):
    """
    Get all polls with their options and vote counts.

    Args:
        request: FastAPI request object (contains user info from auth middleware)
        active_only: Filter to only active polls (default: True)

    Returns:
        List[PollResponse]: List of polls with options and vote counts
    """
    try:
        cursor = get_db_cursor()

        if active_only:
            polls = get_active_polls(cursor)
        else:
            # For now, only active polls are supported
            # Future enhancement could add get_all_polls() function
            polls = get_active_polls(cursor)

        logger.info(f"Retrieved {len(polls)} polls for user {request.state.user['user_id']}")
        return polls

    except psycopg.DatabaseError as e:
        logger.error(f"Database error retrieving polls: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except Exception as e:
        logger.error(f"Unexpected error retrieving polls: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{poll_id}", response_model=PollResponse)
@require_auth
async def get_poll(
    request: Request,
    poll_id: str
):
    """
    Get a specific poll by ID with its options and vote counts.

    Args:
        request: FastAPI request object (contains user info from auth middleware)
        poll_id: UUID of the poll to retrieve

    Returns:
        PollResponse: Poll with options and vote counts

    Raises:
        HTTPException: 404 if poll not found
    """
    try:
        cursor = get_db_cursor()
        poll = get_poll_by_id(cursor, poll_id)

        if poll is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Poll not found"
            )

        logger.info(f"Retrieved poll {poll_id} for user {request.state.user['user_id']}")
        return poll

    except HTTPException:
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Database error retrieving poll {poll_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except Exception as e:
        logger.error(f"Unexpected error retrieving poll {poll_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("", response_model=PollCreatedResponse, status_code=status.HTTP_201_CREATED)
@require_auth
async def create_new_poll(
    request: Request,
    poll_data: PollCreate
):
    """
    Create a new poll with options.

    Args:
        request: FastAPI request object (contains user info from auth middleware)
        poll_data: Poll creation data including title, description, expires_at, and options

    Returns:
        PollCreatedResponse: Created poll with options

    Raises:
        HTTPException: 400 if validation fails, 500 if database error
    """
    try:
        cursor = get_db_cursor()
        user_id = request.state.user["user_id"]

        # Create poll using database operation
        poll = create_poll(
            cursor=cursor,
            title=poll_data.title,
            description=poll_data.description,
            created_by=user_id,
            expires_at=poll_data.expires_at,
            options=poll_data.options
        )

        logger.info(f"Poll {poll['id']} created by user {user_id}")
        return poll

    except ValueError as e:
        logger.warning(f"Poll creation validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except psycopg.IntegrityError as e:
        logger.error(f"Poll creation integrity error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid poll data or constraint violation"
        )
    except psycopg.DatabaseError as e:
        logger.error(f"Database error creating poll: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except Exception as e:
        logger.error(f"Unexpected error creating poll: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
