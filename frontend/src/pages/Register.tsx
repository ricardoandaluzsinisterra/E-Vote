import { useAuth } from "../hooks/useAuth";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { isPasswordSecure } from "../utils/validators";

function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const passwordsMatch = password === confirmPassword;
  const passwordIsValid = isPasswordSecure(password);
  const canSubmit = email && passwordIsValid && passwordsMatch;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!passwordIsValid) {
      setError("Password does not meet security requirements.");
      return;
    }

    if (!passwordsMatch) {
      setError("Passwords don't match.");
      return;
    }

    setIsLoading(true);

    try {
      await register(email, password);
      alert(
        "Registration successful! Please check your email to verify your account."
      );
      navigate("/login");
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Registration failed. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="app-container">
      <section className="auth-card" aria-labelledby="register-heading">
        <h1 id="register-heading" className="auth-header">
          Create account
        </h1>

        {error && (
          <div role="alert" aria-live="assertive" className="error">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
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
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              aria-describedby="passwordHelp"
              autoComplete="new-password"
              placeholder="At least 8 characters"
            />
            <small id="passwordHelp" className="muted">
              Password must be 8+ characters, include upper & lower letters, a
              digit and a special character.
            </small>
          </div>

          <div className="form-field">
            <label htmlFor="confirmPassword">Confirm password</label>
            <input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              aria-required="true"
              autoComplete="new-password"
              placeholder="Repeat password"
            />
            {!passwordsMatch && confirmPassword.length > 0 && (
              <p className="error">Passwords do not match.</p>
            )}
          </div>

          <div>
            <button
              className="btn primary"
              type="submit"
              disabled={!canSubmit || isLoading}
            >
              {isLoading ? "Creating..." : "Create account"}
            </button>
          </div>
        </form>

        <div className="auth-footer muted">
          <Link to="/">Home</Link>
          <Link to="/login">Sign in</Link>
        </div>
      </section>
    </main>
  );
}

export default Register;
