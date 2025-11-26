import React, { useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export default function Dock() {
  const { isAuthenticated, logout } = useAuth();

  const isDevPreview = useMemo(() => {
    try {
      return localStorage.getItem("dev_preview") === "true";
    } catch {
      return false;
    }
  }, []);

  const enablePreview = useCallback(() => {
    localStorage.setItem("dev_preview", "true");
    window.location.reload();
  }, []);

  const exitPreview = useCallback(() => {
    localStorage.removeItem("dev_preview");
    window.location.reload();
  }, []);

  return (
    <nav className="dock" aria-label="Quick actions">
      <ul className="dock-list">
        <li className="dock-item">
          <Link to="/" className="dock-btn" title="Home" aria-label="Home">
            <span className="dock-icon">🏠</span>
            <span className="dock-label">Home</span>
          </Link>
        </li>

        {!isAuthenticated && (
          <>
            <li className="dock-item">
              <Link
                to="/login"
                className="dock-btn"
                title="Login"
                aria-label="Login"
              >
                <span className="dock-icon">🔐</span>
                <span className="dock-label">Login</span>
              </Link>
            </li>

            <li className="dock-item">
              <Link
                to="/register"
                className="dock-btn"
                title="Register"
                aria-label="Register"
              >
                <span className="dock-icon">✍️</span>
                <span className="dock-label">Register</span>
              </Link>
            </li>
          </>
        )}

        {!isAuthenticated && !isDevPreview && (
          <li className="dock-item">
            <button
              className="dock-btn"
              onClick={enablePreview}
              aria-label="Preview signed-in"
            >
              <span className="dock-icon">👁️</span>
              <span className="dock-label">Preview</span>
            </button>
          </li>
        )}

        {(isDevPreview || isAuthenticated) && (
          <>
            {isDevPreview && (
              <li className="dock-item">
                <button
                  className="dock-btn"
                  onClick={exitPreview}
                  aria-label="Exit preview"
                >
                  <span className="dock-icon">🚪</span>
                  <span className="dock-label">Exit preview</span>
                </button>
              </li>
            )}

            <li className="dock-item">
              <button
                className="dock-btn dock-logout"
                onClick={() => {
                  logout();
                }}
                aria-label="Logout"
              >
                <span className="dock-icon">⇦</span>
                <span className="dock-label">Logout</span>
              </button>
            </li>
          </>
        )}
      </ul>
    </nav>
  );
}
