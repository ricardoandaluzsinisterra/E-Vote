import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import Dock from "../components/Dock";
import { useCallback, useMemo } from "react";

function Home() {
  const { user, isAuthenticated, logout } = useAuth();

  const isDevPreview = useMemo(() => {
    try {
      return localStorage.getItem("dev_preview") === "true";
    } catch {
      return false;
    }
  }, []);

  const enablePreview = useCallback(() => {
    localStorage.setItem("dev_preview", "true");
    // reload so AuthProvider picks up the preview flag
    window.location.reload();
  }, []);

  const exitPreview = useCallback(() => {
    localStorage.removeItem("dev_preview");
    window.location.reload();
  }, []);

  if (isAuthenticated && user) {
    return (
      <main className="app-container">
        <section className="auth-card" aria-labelledby="home-heading">
          <h1 id="home-heading" className="auth-header">
            Welcome
          </h1>
          {isDevPreview && (
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: "1rem",
                marginBottom: "0.75rem",
              }}
            >
              <p className="muted" style={{ margin: 0 }}>
                Preview mode — fake sign-in enabled
              </p>
              <button
                className="btn"
                onClick={exitPreview}
                aria-label="Exit preview"
              >
                Exit preview
              </button>
            </div>
          )}
          <p className="muted">Signed in as {user.email}</p>
          <div style={{ marginTop: "1rem" }}>
            <button
              className="btn primary"
              onClick={() => {
                logout();
                exitPreview();
              }}
            >
              Logout
            </button>
          </div>
        </section>
        <Dock />
      </main>
    );
  }

  return (
    <main className="app-container">
      <section className="auth-card" aria-labelledby="home-heading">
        <h1 id="home-heading" className="auth-header">
          E‑Vote
        </h1>
        <p className="muted">A simple, secure voting demo</p>
        <div style={{ marginTop: "1rem" }} className="auth-footer">
          <Link to="/login">Login</Link>
          <Link to="/register">Register</Link>
        </div>

        <div style={{ marginTop: "1rem" }}>
          <button className="btn" onClick={enablePreview}>
            Preview signed-in
          </button>
        </div>
      </section>
    </main>
  );
}

export default Home;
