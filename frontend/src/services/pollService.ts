import { getAuthHeaders } from "../utils/api";
import type {
  Poll,
  CreatePollRequest,
  VoteResponse,
  UserVote,
  PollResults,
} from "../types/poll.types";

const API_BASE_URL = "http://localhost:8000";

export async function getActivePolls(): Promise<Poll[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/polls`, {
      method: "GET",
      headers: getAuthHeaders(),
    });

    if (response.status === 401) {
      throw new Error("Unauthenticated. Please log in again.");
    }

    if (!response.ok) {
      throw new Error("Failed to fetch active polls");
    }

    const data: Poll[] = await response.json();
    return data;
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("An unexpected error occurred while fetching polls");
  }
}

export async function getPollById(pollId: string): Promise<Poll> {
  try {
    const response = await fetch(`${API_BASE_URL}/polls/${pollId}`, {
      method: "GET",
      headers: getAuthHeaders(),
    });

    if (response.status === 401) {
      throw new Error("Unauthenticated. Please log in again.");
    }

    if (response.status === 404) {
      throw new Error("Poll not found");
    }

    if (!response.ok) {
      throw new Error("Failed to fetch poll");
    }

    const data: Poll = await response.json();
    return data;
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("An unexpected error occurred while fetching poll");
  }
}

export async function createPoll(pollData: CreatePollRequest): Promise<Poll> {
  try {
    const response = await fetch(`${API_BASE_URL}/polls`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify(pollData),
    });

    if (response.status === 401) {
      throw new Error("Unauthenticated. Please log in again.");
    }

    if (response.status === 400) {
      const error = await response.json();
      throw new Error(error.detail || "Invalid poll data");
    }

    if (!response.ok) {
      throw new Error("Failed to create poll");
    }

    const data: Poll = await response.json();
    return data;
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("An unexpected error occurred while creating poll");
  }
}

export async function voteOnPoll(
  pollId: string,
  optionId: string
): Promise<VoteResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/polls/${pollId}/vote`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ option_id: optionId }),
    });

    if (response.status === 401) {
      throw new Error("Unauthenticated. Please log in again.");
    }

    if (response.status === 404) {
      throw new Error("Poll or option not found");
    }

    if (response.status === 400) {
      const error = await response.json();
      throw new Error(error.detail || "Invalid vote data");
    }

    if (!response.ok) {
      throw new Error("Failed to cast vote");
    }

    const data: VoteResponse = await response.json();
    return data;
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("An unexpected error occurred while voting");
  }
}

export async function getUserVote(pollId: string): Promise<UserVote | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/polls/${pollId}/user-vote`, {
      method: "GET",
      headers: getAuthHeaders(),
    });

    if (response.status === 401) {
      throw new Error("Unauthenticated. Please log in again.");
    }

    if (response.status === 404) {
      // User hasn't voted on this poll yet
      return null;
    }

    if (!response.ok) {
      throw new Error("Failed to fetch user vote");
    }

    const data: UserVote = await response.json();
    return data;
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("An unexpected error occurred while fetching user vote");
  }
}

export async function getPollResults(pollId: string): Promise<PollResults> {
  try {
    const response = await fetch(`${API_BASE_URL}/polls/${pollId}/results`, {
      method: "GET",
      headers: getAuthHeaders(),
    });

    if (response.status === 401) {
      throw new Error("Unauthenticated. Please log in again.");
    }

    if (response.status === 404) {
      throw new Error("Poll not found");
    }

    if (!response.ok) {
      throw new Error("Failed to fetch poll results");
    }

    const data: PollResults = await response.json();
    return data;
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("An unexpected error occurred while fetching poll results");
  }
}
