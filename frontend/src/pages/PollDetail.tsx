import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import {
  getPollById,
  voteOnPoll,
  getUserVote,
} from "../services/pollService";
import type { Poll, UserVote } from "../types/poll.types";
import Navbar from "../components/Navbar";

function PollDetail() {
  const { pollId } = useParams<{ pollId: string }>();
  const { isAuthenticated, user } = useAuth();
  const navigate = useNavigate();

  const [poll, setPoll] = useState<Poll | null>(null);
  const [userVote, setUserVote] = useState<UserVote | null>(null);
  const [selectedOptionId, setSelectedOptionId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/login");
      return;
    }

    if (!pollId) {
      setError("Invalid poll ID");
      setIsLoading(false);
      return;
    }

    const fetchPollData = async () => {
      try {
        setIsLoading(true);
        setError("");

        const [pollData, voteData] = await Promise.all([
          getPollById(pollId),
          getUserVote(pollId),
        ]);

        setPoll(pollData);
        setUserVote(voteData);

        if (voteData) {
          setSelectedOptionId(voteData.option_id);
        }
      } catch (err) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Failed to load poll. Please try again.");
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchPollData();
  }, [pollId, isAuthenticated, navigate]);

  const isPollExpired = () => {
    if (!poll?.expires_at) return false;
    return new Date(poll.expires_at) < new Date();
  };

  const handleVote = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!pollId || !selectedOptionId) {
      setError("Please select an option");
      return;
    }

    if (isPollExpired()) {
      setError("This poll has expired");
      return;
    }

    try {
      setIsSubmitting(true);
      setError("");
      setSuccessMessage("");

      const response = await voteOnPoll(pollId, selectedOptionId);

      setUserVote({
        vote_id: response.vote_id,
        option_id: response.option_id,
        voted_at: new Date().toISOString(),
      });

      setSuccessMessage(
        userVote ? "Vote changed successfully!" : "Vote cast successfully!"
      );

      // Refresh poll data to get updated vote counts
      const updatedPoll = await getPollById(pollId);
      setPoll(updatedPoll);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to cast vote. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "long",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (!isAuthenticated || !user) {
    return null;
  }

  if (isLoading) {
    return (
      <>
        <Navbar />
        <main className="app-container">
          <section className="auth-card">
            <div
              style={{
                textAlign: "center",
                padding: "3rem 0",
                color: "var(--text-muted)",
              }}
            >
              <p>Loading poll...</p>
            </div>
          </section>
        </main>
      </>
    );
  }

  if (error && !poll) {
    return (
      <>
        <Navbar />
        <main className="app-container">
          <section className="auth-card">
            <div role="alert" aria-live="assertive" className="error">
              {error}
            </div>
            <Link
              to="/polls"
              className="btn"
              style={{ marginTop: "1rem", textDecoration: "none", display: "block", textAlign: "center" }}
            >
              Back to Polls
            </Link>
          </section>
        </main>
      </>
    );
  }

  if (!poll) {
    return null;
  }

  const isExpired = isPollExpired();
  const hasVoted = !!userVote;

  return (
    <>
      <Navbar />
      <main className="app-container">
      <section className="auth-card" style={{ maxWidth: "700px" }}>
        <div style={{ marginBottom: "1.5rem" }}>
          <Link
            to="/polls"
            style={{
              color: "var(--primary)",
              textDecoration: "none",
              fontSize: "0.9rem",
            }}
          >
            ← Back to Polls
          </Link>
        </div>

        <h1 className="auth-header" style={{ marginBottom: "0.5rem" }}>
          {poll.title}
        </h1>

        {poll.description && (
          <p
            className="muted"
            style={{ marginBottom: "1rem", lineHeight: "1.5" }}
          >
            {poll.description}
          </p>
        )}

        {poll.expires_at && (
          <p
            style={{
              fontSize: "0.85rem",
              color: isExpired ? "#e67030" : "var(--text-muted)",
              marginBottom: "1.5rem",
              fontWeight: isExpired ? "600" : "normal",
            }}
          >
            {isExpired ? "⚠️ Expired: " : "Expires: "}
            {formatDate(poll.expires_at)}
          </p>
        )}

        {isExpired && (
          <div
            role="alert"
            style={{
              padding: "1rem",
              background: "rgba(230, 112, 48, 0.1)",
              border: "1px solid rgba(230, 112, 48, 0.3)",
              borderRadius: "8px",
              marginBottom: "1.5rem",
              color: "#e67030",
            }}
          >
            This poll has expired. Voting is no longer allowed.
          </div>
        )}

        {successMessage && (
          <div
            role="alert"
            aria-live="polite"
            style={{
              padding: "1rem",
              background: "rgba(52, 211, 153, 0.1)",
              border: "1px solid rgba(52, 211, 153, 0.3)",
              borderRadius: "8px",
              marginBottom: "1.5rem",
              color: "#059669",
            }}
          >
            {successMessage}
          </div>
        )}

        {error && (
          <div role="alert" aria-live="assertive" className="error">
            {error}
          </div>
        )}

        <form onSubmit={handleVote}>
          <div style={{ marginBottom: "1.5rem" }}>
            <label
              style={{
                display: "block",
                fontWeight: "600",
                marginBottom: "1rem",
                color: "var(--text)",
              }}
            >
              Select your choice:
            </label>

            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {poll.options
                .sort((a, b) => a.display_order - b.display_order)
                .map((option) => (
                  <label
                    key={option.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      padding: "1rem",
                      border: "1px solid rgba(11, 37, 64, 0.08)",
                      borderRadius: "8px",
                      cursor: isExpired ? "not-allowed" : "pointer",
                      background:
                        selectedOptionId === option.id
                          ? "rgba(25, 118, 210, 0.05)"
                          : "#fff",
                      borderColor:
                        selectedOptionId === option.id
                          ? "var(--primary)"
                          : "rgba(11, 37, 64, 0.08)",
                      opacity: isExpired ? 0.6 : 1,
                      transition: "all 0.2s",
                    }}
                    onMouseEnter={(e) => {
                      if (!isExpired) {
                        e.currentTarget.style.borderColor = "var(--primary)";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (selectedOptionId !== option.id) {
                        e.currentTarget.style.borderColor =
                          "rgba(11, 37, 64, 0.08)";
                      }
                    }}
                  >
                    <input
                      type="radio"
                      name="poll-option"
                      value={option.id}
                      checked={selectedOptionId === option.id}
                      onChange={(e) => setSelectedOptionId(e.target.value)}
                      disabled={isExpired}
                      style={{
                        marginRight: "0.75rem",
                        width: "18px",
                        height: "18px",
                        cursor: isExpired ? "not-allowed" : "pointer",
                      }}
                    />
                    <span style={{ flex: 1, color: "var(--text)" }}>
                      {option.option_text}
                    </span>
                    {hasVoted && userVote.option_id === option.id && (
                      <span
                        style={{
                          fontSize: "0.85rem",
                          color: "var(--primary)",
                          fontWeight: "600",
                        }}
                      >
                        ✓ Your vote
                      </span>
                    )}
                  </label>
                ))}
            </div>
          </div>

          <div
            style={{
              display: "flex",
              gap: "1rem",
              flexDirection: "column",
            }}
          >
            <button
              type="submit"
              className="btn primary"
              disabled={isExpired || isSubmitting || !selectedOptionId}
              style={{
                width: "100%",
                opacity:
                  isExpired || isSubmitting || !selectedOptionId ? 0.6 : 1,
              }}
            >
              {isSubmitting
                ? "Submitting..."
                : hasVoted
                ? "Change Vote"
                : "Vote"}
            </button>

            <button
              type="button"
              className="btn"
              onClick={() => navigate(`/polls/${pollId}/results`)}
              style={{
                width: "100%",
                background: "rgba(11, 37, 64, 0.05)",
              }}
            >
              View Results
            </button>
          </div>
        </form>
      </section>
    </main>
    </>
  );
}

export default PollDetail;
