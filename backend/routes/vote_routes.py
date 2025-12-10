import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, status, Response
from backend.middleware import require_auth
from backend.models.vote_models import (
    VoteCreate,
    VoteResponse,
    UserVoteResponse,
    PollResultsResponse,
    PollResultOption
)
from backend.db_ops_service.database.operations import (
    get_poll_by_id,
    get_user_vote,
    create_vote,
    delete_vote,
    increment_vote_count,
    decrement_vote_count
)
from backend.db_ops_service.database.connection import DatabaseManager
import psycopg

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/polls", tags=["votes"])


def get_db_cursor():
    """Helper function to get database cursor from singleton DatabaseManager"""
    db = DatabaseManager()
    if db.cursor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    return db.cursor


@router.post("/{poll_id}/vote", response_model=VoteResponse)
@require_auth
async def cast_vote(
    request: Request,
    poll_id: str,
    vote_data: VoteCreate
):
    """
    Cast a vote on a poll or change an existing vote.

    This endpoint handles both new votes and vote changes atomically.
    When changing a vote, the old vote is deleted and the new vote is created
    in a single transaction to maintain data consistency.

    Args:
        request: FastAPI request object (contains user info from auth middleware)
        poll_id: UUID of the poll to vote on
        vote_data: Vote data containing the option_id

    Returns:
        VoteResponse: Vote confirmation with vote_id and option_id

    Raises:
        HTTPException: 400 for validation errors, 404 if poll not found, 500 for database errors
    """
    try:
        cursor = get_db_cursor()
        user_id = request.state.user["user_id"]
        option_id = vote_data.option_id

        # 1. Validate poll exists
        poll = get_poll_by_id(cursor, poll_id)
        if poll is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Poll not found"
            )

        # 2. Validate poll is active
        if not poll["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Poll is not active"
            )

        # 3. Validate poll not expired
        if poll["expires_at"]:
            expires_at = datetime.fromisoformat(poll["expires_at"].replace('Z', '+00:00'))
            if datetime.now(timezone.utc) >= expires_at:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Poll has expired"
                )

        # 4. Validate option belongs to this poll
        option_exists = False
        for option in poll["options"]:
            if option["id"] == option_id:
                option_exists = True
                break

        if not option_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid option_id for this poll"
            )

        # 5. Check if user already voted
        existing_vote = get_user_vote(cursor, user_id, poll_id)

        # Get connection for transaction management
        conn = cursor.connection

        if existing_vote:
            # User is changing their vote - handle atomically
            old_option_id = existing_vote["option_id"]

            # Only process if voting for a different option
            if old_option_id == option_id:
                # User is voting for the same option, return existing vote
                return VoteResponse(
                    message="Vote cast successfully",
                    vote_id=existing_vote["id"],
                    option_id=option_id
                )

            # Change vote atomically in a single transaction
            try:
                with conn.transaction():
                    # Delete old vote (we need to do this manually to be in same transaction)
                    delete_query = "DELETE FROM votes WHERE user_id=%s AND poll_id=%s"
                    cursor.execute(delete_query, (user_id, poll_id))

                    # Decrement old option's vote count
                    decrement_query = "UPDATE poll_options SET vote_count = vote_count - 1 WHERE id = %s"
                    cursor.execute(decrement_query, (old_option_id,))

                    # Create new vote
                    create_query = """INSERT INTO votes (user_id, poll_id, option_id)
                        VALUES (%s, %s, %s) RETURNING id, user_id, poll_id, option_id, voted_at"""
                    cursor.execute(create_query, (user_id, poll_id, option_id))
                    vote_row = cursor.fetchone()

                    # Increment new option's vote count
                    increment_query = "UPDATE poll_options SET vote_count = vote_count + 1 WHERE id = %s"
                    cursor.execute(increment_query, (option_id,))

                    vote_id = str(vote_row[0])
                    logger.info(f"Vote changed - user: {user_id}, poll: {poll_id}, from: {old_option_id}, to: {option_id}")

                    return VoteResponse(
                        message="Vote cast successfully",
                        vote_id=vote_id,
                        option_id=option_id
                    )

            except psycopg.DatabaseError as e:
                logger.error(f"Transaction failed during vote change: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to change vote"
                )
        else:
            # User is voting for the first time
            vote_result = create_vote(cursor, user_id, poll_id, option_id)
            logger.info(f"New vote cast - user: {user_id}, poll: {poll_id}, option: {option_id}")

            return VoteResponse(
                message="Vote cast successfully",
                vote_id=vote_result["id"],
                option_id=option_id
            )

    except HTTPException:
        raise
    except psycopg.IntegrityError as e:
        logger.error(f"Vote integrity error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Constraint violation - please try again"
        )
    except psycopg.DatabaseError as e:
        logger.error(f"Database error casting vote: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except Exception as e:
        logger.error(f"Unexpected error casting vote: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{poll_id}/user-vote", response_model=UserVoteResponse)
@require_auth
async def get_user_vote_endpoint(
    request: Request,
    poll_id: str,
    response: Response
):
    """
    Get the authenticated user's vote for a specific poll.

    Args:
        request: FastAPI request object (contains user info from auth middleware)
        poll_id: UUID of the poll
        response: FastAPI response object for setting status code

    Returns:
        UserVoteResponse: User's vote information
        204 No Content: If user hasn't voted on this poll
    """
    try:
        cursor = get_db_cursor()
        user_id = request.state.user["user_id"]

        vote = get_user_vote(cursor, user_id, poll_id)

        if vote is None:
            response.status_code = status.HTTP_204_NO_CONTENT
            return response

        logger.info(f"User vote retrieved - user: {user_id}, poll: {poll_id}")
        return UserVoteResponse(
            vote_id=vote["id"],
            option_id=vote["option_id"],
            voted_at=vote["voted_at"]
        )

    except psycopg.DatabaseError as e:
        logger.error(f"Database error retrieving user vote: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except Exception as e:
        logger.error(f"Unexpected error retrieving user vote: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{poll_id}/results", response_model=PollResultsResponse)
@require_auth
async def get_poll_results(
    request: Request,
    poll_id: str
):
    """
    Get poll results with vote counts and percentages.

    Calculates percentage for each option based on total votes.
    Handles division by zero when no votes have been cast.

    Args:
        request: FastAPI request object (contains user info from auth middleware)
        poll_id: UUID of the poll

    Returns:
        PollResultsResponse: Poll results with vote counts and percentages
    """
    try:
        cursor = get_db_cursor()

        # Get poll with vote counts
        poll = get_poll_by_id(cursor, poll_id)

        if poll is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Poll not found"
            )

        # Calculate total votes
        total_votes = sum(option["vote_count"] for option in poll["options"])

        # Build results with percentages
        result_options = []
        for option in poll["options"]:
            vote_count = option["vote_count"]

            # Handle division by zero
            if total_votes == 0:
                percentage = 0.0
            else:
                percentage = round((vote_count / total_votes) * 100, 1)

            result_options.append(PollResultOption(
                option_id=option["id"],
                option_text=option["option_text"],
                vote_count=vote_count,
                percentage=percentage
            ))

        logger.info(f"Poll results retrieved - poll: {poll_id}, total_votes: {total_votes}")

        return PollResultsResponse(
            poll_id=poll["id"],
            title=poll["title"],
            total_votes=total_votes,
            options=result_options
        )

    except HTTPException:
        raise
    except psycopg.DatabaseError as e:
        logger.error(f"Database error retrieving poll results: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except Exception as e:
        logger.error(f"Unexpected error retrieving poll results: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
