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
    <div>
      <h1>Register</h1>
      {error && (
        <div style={{ color: "red", marginBottom: "1rem" }}>{error}</div>
      )}

      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="email">Email:</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <div>
          <label htmlFor="password">Password:</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            aria-describedby="passwordHelp"
          />
          <small id="passwordHelp">
            Password must be 8+ characters, include uppercase and lowercase
            letters, a digit, and a special character.
          </small>
        </div>

        <div>
          <label htmlFor="confirmPassword">Confirm Password:</label>
          <input
            id="confirmPassword"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
          />
          {!passwordsMatch && confirmPassword.length > 0 && (
            <p style={{ color: "red" }}>Passwords do not match.</p>
          )}
        </div>

        <button type="submit" disabled={!canSubmit || isLoading}>
          {isLoading ? "Registering..." : "Register"}
        </button>
      </form>

      <nav>
        <Link to="/">Back to Home</Link> {" | "}
        <Link to="/login">Already have an account? Login</Link>
      </nav>
    </div>
  );
}

export default Register;
