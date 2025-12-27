import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

function Navbar() {
  const { user, logout, isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated || !user) {
    return null;
  }

  const isActive = (path: string) => {
    if (path === "/polls" && location.pathname.startsWith("/polls")) {
      return true;
    }
    return location.pathname === path;
  };

  return (
    <nav
      style={{
        background: "linear-gradient(180deg, var(--primary), #1565c0)",
        borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
        padding: "0.75rem 0",
        marginBottom: "2rem",
      }}
    >
      <div
        style={{
          maxWidth: "1200px",
          margin: "0 auto",
          padding: "0 1.5rem",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "2rem",
        }}
      >
        <Link
          to="/"
          style={{
            color: "#fff",
            textDecoration: "none",
            fontSize: "1.25rem",
            fontWeight: "700",
            letterSpacing: "-0.02em",
          }}
        >
          E‑Vote
        </Link>

        <div
          style={{
            display: "flex",
            gap: "0.5rem",
            alignItems: "center",
            flex: 1,
          }}
        >
          <Link
            to="/polls"
            style={{
              color: "#fff",
              textDecoration: "none",
              padding: "0.5rem 1rem",
              borderRadius: "6px",
              fontSize: "0.9rem",
              fontWeight: "500",
              background: isActive("/polls")
                ? "rgba(255, 255, 255, 0.2)"
                : "transparent",
              transition: "background 0.2s",
            }}
            onMouseEnter={(e) => {
              if (!isActive("/polls")) {
                e.currentTarget.style.background = "rgba(255, 255, 255, 0.1)";
              }
            }}
            onMouseLeave={(e) => {
              if (!isActive("/polls")) {
                e.currentTarget.style.background = "transparent";
              }
            }}
          >
            Polls
          </Link>

          <Link
            to="/voting-history"
            style={{
              color: "#fff",
              textDecoration: "none",
              padding: "0.5rem 1rem",
              borderRadius: "6px",
              fontSize: "0.9rem",
              fontWeight: "500",
              background: isActive("/voting-history")
                ? "rgba(255, 255, 255, 0.2)"
                : "transparent",
              transition: "background 0.2s",
            }}
            onMouseEnter={(e) => {
              if (!isActive("/voting-history")) {
                e.currentTarget.style.background = "rgba(255, 255, 255, 0.1)";
              }
            }}
            onMouseLeave={(e) => {
              if (!isActive("/voting-history")) {
                e.currentTarget.style.background = "transparent";
              }
            }}
          >
            History
          </Link>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "1rem",
          }}
        >
          <span
            style={{
              color: "rgba(255, 255, 255, 0.9)",
              fontSize: "0.85rem",
            }}
          >
            {user.email}
          </span>
          <button
            onClick={logout}
            style={{
              background: "rgba(255, 255, 255, 0.15)",
              color: "#fff",
              border: "1px solid rgba(255, 255, 255, 0.3)",
              padding: "0.5rem 1rem",
              borderRadius: "6px",
              fontSize: "0.85rem",
              fontWeight: "500",
              cursor: "pointer",
              transition: "all 0.2s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "rgba(255, 255, 255, 0.25)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "rgba(255, 255, 255, 0.15)";
            }}
          >
            Logout
          </button>
        </div>
      </div>
    </nav>
  );
}

export default Navbar;
