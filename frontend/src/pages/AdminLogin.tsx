import { useAuth } from "../hooks/useAuth";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

function AdminLogin() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      await login(email, password);
      navigate("/admin/dashboard");
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Login failed. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="app-container">
      <section className="auth-card" aria-labelledby="login-heading">
        <h1 id="login-heading" className="auth-header">
          Sign in
        </h1>

        {error && (
          <div role="alert" aria-live="assertive" className="error">
            {error}
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          aria-describedby={error ? "error-message" : undefined}
        >
          <div className="form-field">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              aria-required="true"
              autoComplete="email"
              placeholder="you@example.com"
            />
          </div>

          <div className="form-field">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              aria-required="true"
              autoComplete="current-password"
              placeholder="Your password"
            />
          </div>

          <div>
            <button className="btn primary" type="submit" disabled={isLoading}>
              {isLoading ? "Logging in..." : "Sign in"}
            </button>
          </div>
        </form>

        <div className="auth-footer muted">
          <Link to="/">Home</Link>
          <span className="muted">Can't login? Contact us</span>
        </div>
      </section>
    </main>
  );
}

export default AdminLogin;
