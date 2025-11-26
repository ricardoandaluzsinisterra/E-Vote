import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

function Home() {
  const { user, isAuthenticated, logout } = useAuth();

  if (isAuthenticated && user) {
    return (
      <main className="app-container">
        <section className="auth-card" aria-labelledby="home-heading">
          <h1 id="home-heading" className="auth-header">
            Welcome
          </h1>
          <p className="muted">Signed in as {user.email}</p>
          <div style={{ marginTop: "1rem" }}>
            <button className="btn primary" onClick={logout}>
              Logout
            </button>
          </div>
        </section>
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
        <div className="auth-footer" style={{ marginTop: "1rem" }}>
          <Link to="/login">Login</Link>
          <Link to="/register">Register</Link>
        </div>
      </section>
    </main>
  );
}

export default Home;
