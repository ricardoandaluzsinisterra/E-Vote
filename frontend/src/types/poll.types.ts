export interface PollOption {
  id: string;
  poll_id: string;
  option_text: string;
  vote_count: number;
  display_order: number;
}

export interface Poll {
  id: string;
  title: string;
  description?: string;
  created_by: number;
  created_at: string;
  expires_at?: string;
  is_active: boolean;
  options: PollOption[];
}

export interface CreatePollOption {
  option_text: string;
  display_order: number;
}

export interface CreatePollRequest {
  title: string;
  description?: string;
  expires_at?: string;
  options: CreatePollOption[];
}

export interface VoteResponse {
  message: string;
  vote_id: string;
  option_id: string;
}

export interface UserVote {
  vote_id: string;
  option_id: string;
  voted_at: string;
}

export interface PollResultOption {
  option_id: string;
  option_text: string;
  vote_count: number;
  percentage: number;
}

export interface PollResults {
  poll_id: string;
  title: string;
  total_votes: number;
  options: PollResultOption[];
}
