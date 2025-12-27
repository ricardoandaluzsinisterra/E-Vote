import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { getPollResults } from "../services/pollService";
import type { PollResults as PollResultsType } from "../types/poll.types";
import Navbar from "../components/Navbar";

function PollResults() {
  const { pollId } = useParams<{ pollId: string }>();
  const { isAuthenticated, user } = useAuth();
  const navigate = useNavigate();

  const [results, setResults] = useState<PollResultsType | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

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

    const fetchResults = async () => {
      try {
        setIsLoading(true);
        setError("");
        const data = await getPollResults(pollId);
        setResults(data);
      } catch (err) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Failed to load results. Please try again.");
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchResults();
  }, [pollId, isAuthenticated, navigate]);

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
              <p>Loading results...</p>
            </div>
          </section>
        </main>
      </>
    );
  }

  if (error || !results) {
    return (
      <>
        <Navbar />
        <main className="app-container">
          <section className="auth-card">
            {error && (
              <div role="alert" aria-live="assertive" className="error">
                {error}
              </div>
            )}
            <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
              <Link
                to={`/polls/${pollId}`}
                className="btn"
                style={{ flex: 1, textDecoration: "none", textAlign: "center" }}
              >
                Back to Poll
              </Link>
              <Link
                to="/polls"
                className="btn"
                style={{ flex: 1, textDecoration: "none", textAlign: "center" }}
              >
                All Polls
              </Link>
            </div>
          </section>
        </main>
      </>
    );
  }

  // Sort options by vote count (highest first)
  const sortedOptions = [...results.options].sort(
    (a, b) => b.vote_count - a.vote_count
  );

  // Find the highest vote count to determine winner(s)
  const maxVotes = sortedOptions.length > 0 ? sortedOptions[0].vote_count : 0;

  return (
    <>
      <Navbar />
      <main className="app-container">
      <section className="auth-card" style={{ maxWidth: "800px" }}>
        <div style={{ marginBottom: "1.5rem" }}>
          <div
            style={{
              display: "flex",
              gap: "1rem",
              marginBottom: "1rem",
              fontSize: "0.9rem",
            }}
          >
            <Link
              to={`/polls/${pollId}`}
              style={{
                color: "var(--primary)",
                textDecoration: "none",
              }}
            >
              ← Back to Poll
            </Link>
            <span style={{ color: "var(--text-muted)" }}>|</span>
            <Link
              to="/polls"
              style={{
                color: "var(--primary)",
                textDecoration: "none",
              }}
            >
              All Polls
            </Link>
          </div>
        </div>

        <h1 className="auth-header" style={{ marginBottom: "0.5rem" }}>
          {results.title}
        </h1>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            marginBottom: "2rem",
          }}
        >
          <p
            className="muted"
            style={{ margin: 0, fontSize: "1rem", fontWeight: "600" }}
          >
            Total Votes: {results.total_votes}
          </p>
        </div>

        {results.total_votes === 0 ? (
          <div
            style={{
              textAlign: "center",
              padding: "3rem 0",
              color: "var(--text-muted)",
            }}
          >
            <p>No votes have been cast yet.</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            {sortedOptions.map((option, index) => {
              const isWinner = option.vote_count === maxVotes && maxVotes > 0;
              const barColor = isWinner
                ? "linear-gradient(90deg, #10b981, #059669)"
                : "linear-gradient(90deg, #94a3b8, #64748b)";
              const textColor = isWinner ? "#059669" : "var(--text)";

              return (
                <div
                  key={option.option_id}
                  style={{
                    padding: "1.5rem",
                    border: isWinner
                      ? "2px solid #10b981"
                      : "1px solid rgba(11, 37, 64, 0.08)",
                    borderRadius: "12px",
                    background: isWinner
                      ? "rgba(16, 185, 129, 0.03)"
                      : "#fff",
                    position: "relative",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      marginBottom: "1rem",
                      gap: "1rem",
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "0.75rem",
                          marginBottom: "0.25rem",
                        }}
                      >
                        {isWinner && (
                          <span
                            style={{
                              fontSize: "1.5rem",
                              lineHeight: 1,
                            }}
                          >
                            🏆
                          </span>
                        )}
                        <h3
                          style={{
                            margin: 0,
                            fontSize: "1.1rem",
                            color: textColor,
                            fontWeight: isWinner ? "700" : "600",
                          }}
                        >
                          {option.option_text}
                        </h3>
                      </div>
                      {isWinner && (
                        <p
                          style={{
                            margin: "0.25rem 0 0 2.25rem",
                            fontSize: "0.85rem",
                            color: "#059669",
                            fontWeight: "600",
                          }}
                        >
                          Leading
                        </p>
                      )}
                    </div>

                    <div
                      style={{
                        textAlign: "right",
                        minWidth: "120px",
                      }}
                    >
                      <div
                        style={{
                          fontSize: "1.5rem",
                          fontWeight: "700",
                          color: textColor,
                          lineHeight: 1,
                        }}
                      >
                        {option.percentage.toFixed(1)}%
                      </div>
                      <div
                        style={{
                          fontSize: "0.9rem",
                          color: "var(--text-muted)",
                          marginTop: "0.25rem",
                        }}
                      >
                        {option.vote_count}{" "}
                        {option.vote_count === 1 ? "vote" : "votes"}
                      </div>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div
                    style={{
                      width: "100%",
                      height: "12px",
                      background: "rgba(11, 37, 64, 0.05)",
                      borderRadius: "6px",
                      overflow: "hidden",
                      position: "relative",
                    }}
                  >
                    <div
                      style={{
                        width: `${option.percentage}%`,
                        height: "100%",
                        background: barColor,
                        borderRadius: "6px",
                        transition: "width 0.6s ease-out",
                      }}
                    />
                  </div>

                  {/* Rank indicator */}
                  {!isWinner && (
                    <div
                      style={{
                        position: "absolute",
                        top: "1rem",
                        left: "1rem",
                        width: "24px",
                        height: "24px",
                        borderRadius: "50%",
                        background: "rgba(11, 37, 64, 0.05)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "0.75rem",
                        fontWeight: "600",
                        color: "var(--text-muted)",
                      }}
                    >
                      {index + 1}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <div style={{ marginTop: "2rem" }}>
          <Link
            to={`/polls/${pollId}`}
            className="btn primary"
            style={{
              width: "100%",
              textDecoration: "none",
              display: "block",
              textAlign: "center",
            }}
          >
            Back to Vote
          </Link>
        </div>
      </section>
    </main>
    </>
  );
}

export default PollResults;
