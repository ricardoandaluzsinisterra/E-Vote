from pydantic import BaseModel, Field
from typing import List, Optional


class VoteCreate(BaseModel):
    """Vote creation request model"""
    option_id: str = Field(..., description="UUID of the poll option to vote for")


class VoteResponse(BaseModel):
    """Response after casting a vote"""
    message: str
    vote_id: str
    option_id: str


class UserVoteResponse(BaseModel):
    """Response for user's vote on a specific poll"""
    vote_id: str
    option_id: str
    voted_at: str


class PollResultOption(BaseModel):
    """Poll option with vote count and percentage"""
    option_id: str
    option_text: str
    vote_count: int
    percentage: float


class PollResultsResponse(BaseModel):
    """Response for poll results with vote counts and percentages"""
    poll_id: str
    title: str
    total_votes: int
    options: List[PollResultOption]
