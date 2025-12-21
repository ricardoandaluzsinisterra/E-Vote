import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { getActivePolls } from "../services/pollService";
import type { Poll } from "../types/poll.types";
import Navbar from "../components/Navbar";

function PollList() {
  const { isAuthenticated, user } = useAuth();
  const navigate = useNavigate();
  const [polls, setPolls] = useState<Poll[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/login");
      return;
    }

    const fetchPolls = async () => {
      try {
        setIsLoading(true);
        setError("");
        const data = await getActivePolls();
        setPolls(data);
      } catch (err) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Failed to load polls. Please try again.");
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchPolls();
  }, [isAuthenticated, navigate]);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const isExpiringSoon = (expiresAt: string) => {
    const now = new Date();
    const expirationDate = new Date(expiresAt);
    const hoursUntilExpiration =
      (expirationDate.getTime() - now.getTime()) / (1000 * 60 * 60);
    return hoursUntilExpiration > 0 && hoursUntilExpiration <= 24;
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
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "1.5rem",
            }}
          >
            <div>
              <h1 className="auth-header">Active Polls</h1>
              <p className="muted">Browse and vote on polls</p>
            </div>
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
            <p>Loading polls...</p>
          </div>
        ) : polls.length === 0 ? (
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
              No active polls available at the moment
            </p>
            <p
              style={{
                color: "var(--text-muted)",
                fontSize: "0.9rem",
              }}
            >
              Check back later for new polls to vote on!
            </p>
          </div>
        ) : (
          <div
            style={{
              display: "grid",
              gap: "1rem",
              gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
            }}
          >
            {polls.map((poll) => (
              <div
                key={poll.id}
                style={{
                  border: "1px solid rgba(11, 37, 64, 0.08)",
                  borderRadius: "12px",
                  padding: "1.5rem",
                  background: "#fff",
                  transition: "box-shadow 0.2s, transform 0.2s",
                  cursor: "pointer",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.boxShadow =
                    "0 4px 12px rgba(11, 37, 64, 0.08)";
                  e.currentTarget.style.transform = "translateY(-2px)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.boxShadow = "none";
                  e.currentTarget.style.transform = "translateY(0)";
                }}
                onClick={() => navigate(`/polls/${poll.id}`)}
              >
                <h3
                  style={{
                    margin: "0 0 0.5rem 0",
                    fontSize: "1.25rem",
                    color: "var(--text)",
                  }}
                >
                  {poll.title}
                </h3>

                {poll.description && (
                  <p
                    style={{
                      margin: "0 0 1rem 0",
                      color: "var(--text-muted)",
                      fontSize: "0.9rem",
                      lineHeight: "1.4",
                    }}
                  >
                    {poll.description}
                  </p>
                )}

                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.5rem",
                    marginBottom: "1rem",
                  }}
                >
                  <div
                    style={{
                      fontSize: "0.85rem",
                      color: "var(--text-muted)",
                    }}
                  >
                    <strong>{poll.options.length}</strong>{" "}
                    {poll.options.length === 1 ? "option" : "options"}
                  </div>

                  {poll.expires_at && (
                    <div
                      style={{
                        fontSize: "0.85rem",
                        color: isExpiringSoon(poll.expires_at)
                          ? "#e67030"
                          : "var(--text-muted)",
                        fontWeight: isExpiringSoon(poll.expires_at)
                          ? "600"
                          : "normal",
                      }}
                    >
                      {isExpiringSoon(poll.expires_at) && "⚠️ "}
                      Expires: {formatDate(poll.expires_at)}
                    </div>
                  )}
                </div>

                <button
                  className="btn primary"
                  style={{ width: "100%" }}
                  onClick={(e) => {
                    e.stopPropagation();
                    navigate(`/polls/${poll.id}`);
                  }}
                >
                  Vote
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
    </>
  );
}

export default PollList;
