import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { getActivePolls, getUserVote } from "../services/pollService";
import type { Poll, UserVote } from "../types/poll.types";
import Navbar from "../components/Navbar";

interface VoteHistoryItem {
  poll: Poll;
  vote: UserVote;
  votedOptionText: string;
}

function VotingHistory() {
  const { isAuthenticated, user } = useAuth();
  const navigate = useNavigate();

  const [voteHistory, setVoteHistory] = useState<VoteHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/login");
      return;
    }

    const fetchVotingHistory = async () => {
      try {
        setIsLoading(true);
        setError("");

        // Step 1: Fetch all active polls
        const polls = await getActivePolls();

        // Step 2: Fetch user votes for all polls in parallel
        const votePromises = polls.map(async (poll) => {
          try {
            const vote = await getUserVote(poll.id);
            return { poll, vote };
          } catch (err) {
            // If fetching a vote fails, skip this poll
            return { poll, vote: null };
          }
        });

        const pollsWithVotes = await Promise.all(votePromises);

        // Step 3: Filter to only polls where user has voted
        const votedPolls = pollsWithVotes
          .filter((item) => item.vote !== null)
          .map((item) => {
            // Find the option text from the poll options
            const votedOption = item.poll.options.find(
              (option) => option.id === item.vote!.option_id
            );

            return {
              poll: item.poll,
              vote: item.vote!,
              votedOptionText: votedOption?.option_text || "Unknown option",
            };
          });

        // Step 4: Sort by most recently voted first
        votedPolls.sort((a, b) => {
          const dateA = new Date(a.vote.voted_at).getTime();
          const dateB = new Date(b.vote.voted_at).getTime();
          return dateB - dateA;
        });

        setVoteHistory(votedPolls);
      } catch (err) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Failed to load voting history. Please try again.");
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchVotingHistory();
  }, [isAuthenticated, navigate]);

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMinutes = Math.floor(diffMs / (1000 * 60));

    if (diffMinutes < 1) {
      return "Just now";
    } else if (diffMinutes < 60) {
      return `${diffMinutes} ${diffMinutes === 1 ? "minute" : "minutes"} ago`;
    } else if (diffHours < 24) {
      return `${diffHours} ${diffHours === 1 ? "hour" : "hours"} ago`;
    } else if (diffDays < 7) {
      return `${diffDays} ${diffDays === 1 ? "day" : "days"} ago`;
    } else {
      return date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    }
  };

  if (!isAuthenticated || !user) {
    return null;
  }

  return (
    <>
      <Navbar />
      <main className="app-container">
        <section className="auth-card" style={{ maxWidth: "900px" }}>
          <div
            style={{
              marginBottom: "1.5rem",
            }}
          >
            <h1 className="auth-header">Voting History</h1>
            <p className="muted">Your participation in polls</p>
          </div>

        {error && (
          <div role="alert" aria-live="assertive" className="error">
            {error}
          </div>
        )}

        {isLoading ? (
          <div
            style={{
              textAlign: "center",
              padding: "3rem 0",
              color: "var(--text-muted)",
            }}
          >
            <p>Loading voting history...</p>
          </div>
        ) : voteHistory.length === 0 ? (
          <div
            style={{
              textAlign: "center",
              padding: "3rem 0",
            }}
          >
            <div
              style={{
                fontSize: "3rem",
                marginBottom: "1rem",
              }}
            >
              🗳️
            </div>
            <p
              style={{
                color: "var(--text-muted)",
                fontSize: "1.1rem",
                marginBottom: "1rem",
              }}
            >
              No voting history yet
            </p>
            <p
              style={{
                color: "var(--text-muted)",
                fontSize: "0.9rem",
                marginBottom: "2rem",
              }}
            >
              You haven't voted on any polls. Check out the active polls to get
              started!
            </p>
            <Link
              to="/polls"
              className="btn primary"
              style={{ textDecoration: "none" }}
            >
              Browse Polls
            </Link>
          </div>
        ) : (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "1rem",
            }}
          >
            {voteHistory.map((item) => (
              <div
                key={item.poll.id}
                style={{
                  border: "1px solid rgba(11, 37, 64, 0.08)",
                  borderRadius: "12px",
                  padding: "1.5rem",
                  background: "#fff",
                  transition: "box-shadow 0.2s",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.boxShadow =
                    "0 4px 12px rgba(11, 37, 64, 0.08)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.boxShadow = "none";
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    gap: "1rem",
                    marginBottom: "1rem",
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <h3
                      style={{
                        margin: "0 0 0.5rem 0",
                        fontSize: "1.25rem",
                        color: "var(--text)",
                      }}
                    >
                      {item.poll.title}
                    </h3>

                    {item.poll.description && (
                      <p
                        style={{
                          margin: "0 0 0.75rem 0",
                          color: "var(--text-muted)",
                          fontSize: "0.9rem",
                          lineHeight: "1.4",
                        }}
                      >
                        {item.poll.description}
                      </p>
                    )}

                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.5rem",
                        marginBottom: "0.5rem",
                      }}
                    >
                      <span
                        style={{
                          fontSize: "0.85rem",
                          color: "var(--text-muted)",
                        }}
                      >
                        Your vote:
                      </span>
                      <span
                        style={{
                          fontSize: "0.9rem",
                          color: "var(--primary)",
                          fontWeight: "600",
                          padding: "0.25rem 0.75rem",
                          background: "rgba(25, 118, 210, 0.08)",
                          borderRadius: "6px",
                        }}
                      >
                        {item.votedOptionText}
                      </span>
                    </div>

                    <p
                      style={{
                        margin: 0,
                        fontSize: "0.85rem",
                        color: "var(--text-muted)",
                      }}
                    >
                      Voted {formatTimestamp(item.vote.voted_at)}
                    </p>
                  </div>

                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "0.5rem",
                      minWidth: "140px",
                    }}
                  >
                    <Link
                      to={`/polls/${item.poll.id}/results`}
                      className="btn primary"
                      style={{
                        textDecoration: "none",
                        textAlign: "center",
                        fontSize: "0.9rem",
                        padding: "0.6rem 1rem",
                      }}
                    >
                      View Results
                    </Link>
                    <Link
                      to={`/polls/${item.poll.id}`}
                      className="btn"
                      style={{
                        textDecoration: "none",
                        textAlign: "center",
                        fontSize: "0.9rem",
                        padding: "0.6rem 1rem",
                        background: "rgba(11, 37, 64, 0.05)",
                      }}
                    >
                      Change Vote
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {voteHistory.length > 0 && (
          <div
            style={{
              marginTop: "2rem",
              textAlign: "center",
              padding: "1rem",
              background: "rgba(11, 37, 64, 0.03)",
              borderRadius: "8px",
            }}
          >
            <p
              style={{
                margin: 0,
                color: "var(--text-muted)",
                fontSize: "0.9rem",
              }}
            >
              You've participated in {voteHistory.length}{" "}
              {voteHistory.length === 1 ? "poll" : "polls"}
            </p>
          </div>
        )}
      </section>
    </main>
    </>
  );
}

export default VotingHistory;
