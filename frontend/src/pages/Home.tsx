import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import Navbar from "../components/Navbar";

function Home() {
  const { user, isAuthenticated, logout } = useAuth();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string>("");
  const [isUploaded, setIsUploaded] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file && file.type === "text/csv") {
      setSelectedFile(file);
      setUploadStatus("");
    } else {
      setUploadStatus("Please select a valid CSV file");
      setSelectedFile(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile || !user) return;

    setIsProcessing(true);
    setUploadStatus("Uploading...");

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("user_id", user.id || user.email);

    try {
      const response = await fetch("http://localhost:8000/upload-emails", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setUploadStatus(`Successfully uploaded ${data.count} emails`);
        setIsUploaded(true);
      } else {
        const error = await response.json();
        setUploadStatus(`Error: ${error.detail || "Upload failed"}`);
      }
    } catch (error) {
      setUploadStatus("Error: Could not connect to server");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSendVerifications = async () => {
    if (!user) return;

    setIsProcessing(true);
    setUploadStatus("Sending verification emails...");

    try {
      const response = await fetch("http://localhost:8000/send-verifications", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: user.id || user.email }),
      });

      if (response.ok) {
        const data = await response.json();
        setUploadStatus(`Sent ${data.sent} verification emails`);
      } else {
        const error = await response.json();
        setUploadStatus(`Error: ${error.detail || "Failed to send emails"}`);
      }
    } catch (error) {
      setUploadStatus("Error: Could not connect to server");
    } finally {
      setIsProcessing(false);
    }
  };

  // Logged out view with Administrator Login button
  if (!isAuthenticated || !user) {
    return (
      <main className="app-container">
        <section className="auth-card">
          <h1 className="auth-header">E‑Vote</h1>
          <p className="muted">Secure, auditable online voting</p>
          
          <div style={{ marginTop: "1.5rem" }}>
            <a 
              href="/login" 
              className="btn primary" 
              style={{ width: "100%", textAlign: "center", display: "block" }}
            >
              Administrator Login
            </a>
          </div>
        </section>
      </main>
    );
  }

  // Logged in view with voting navigation
  return (
    <>
      <Navbar />
      <main className="app-container">
        <section className="auth-card" style={{ maxWidth: "900px" }}>
          <h1 className="auth-header">Welcome to E‑Vote</h1>
          <p className="muted">Secure, auditable online voting</p>

          {/* Voting Features */}
          <div style={{ marginTop: "2rem" }}>
            <h2
              style={{
                fontSize: "1.1rem",
                fontWeight: "600",
                marginBottom: "1rem",
                color: "var(--text)",
              }}
            >
              Voting
            </h2>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
                gap: "1rem",
              }}
            >
              <Link
                to="/polls"
                style={{
                  textDecoration: "none",
                  padding: "1.5rem",
                  border: "1px solid rgba(11, 37, 64, 0.08)",
                  borderRadius: "12px",
                  background: "#fff",
                  transition: "all 0.2s",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.5rem",
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
              >
                <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>
                  🗳️
                </div>
                <h3
                  style={{
                    margin: 0,
                    fontSize: "1.1rem",
                    color: "var(--primary)",
                    fontWeight: "600",
                  }}
                >
                  View Active Polls
                </h3>
                <p
                  style={{
                    margin: 0,
                    fontSize: "0.9rem",
                    color: "var(--text-muted)",
                    lineHeight: "1.4",
                  }}
                >
                  Browse and vote on active polls
                </p>
              </Link>

              <Link
                to="/voting-history"
                style={{
                  textDecoration: "none",
                  padding: "1.5rem",
                  border: "1px solid rgba(11, 37, 64, 0.08)",
                  borderRadius: "12px",
                  background: "#fff",
                  transition: "all 0.2s",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.5rem",
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
              >
                <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>
                  📊
                </div>
                <h3
                  style={{
                    margin: 0,
                    fontSize: "1.1rem",
                    color: "var(--primary)",
                    fontWeight: "600",
                  }}
                >
                  My Voting History
                </h3>
                <p
                  style={{
                    margin: 0,
                    fontSize: "0.9rem",
                    color: "var(--text-muted)",
                    lineHeight: "1.4",
                  }}
                >
                  View your past votes and participation
                </p>
              </Link>
            </div>
          </div>

          {/* Admin Features */}
          <div style={{ marginTop: "3rem" }}>
            <h2
              style={{
                fontSize: "1.1rem",
                fontWeight: "600",
                marginBottom: "1rem",
                color: "var(--text)",
              }}
            >
              Administration
            </h2>
            <div
              style={{
                padding: "1.5rem",
                border: "1px solid rgba(11, 37, 64, 0.08)",
                borderRadius: "12px",
                background: "#fff",
              }}
            >
              <h3
                style={{
                  margin: "0 0 1rem 0",
                  fontSize: "1rem",
                  fontWeight: "600",
                }}
              >
                Upload Voter Emails
              </h3>

              <div className="form-field">
                <label htmlFor="csv-upload">Email List (CSV Format)</label>
                <input
                  id="csv-upload"
                  type="file"
                  accept=".csv"
                  onChange={handleFileChange}
                  style={{
                    padding: "0.75rem",
                    border: "1px solid rgba(11, 37, 64, 0.08)",
                    borderRadius: "8px",
                  }}
                />
              </div>

              <button
                className="btn primary"
                onClick={handleUpload}
                disabled={!selectedFile || isProcessing}
                style={{
                  marginTop: "1rem",
                  width: "100%",
                  opacity: !selectedFile || isProcessing ? 0.6 : 1,
                }}
              >
                {isProcessing ? "Processing..." : "Upload Emails File"}
              </button>

              {uploadStatus && (
                <p
                  className={uploadStatus.includes("Error") ? "error" : "muted"}
                  style={{ marginTop: "0.75rem", fontSize: "0.9rem" }}
                >
                  {uploadStatus}
                </p>
              )}

              {isUploaded && (
                <button
                  className="btn primary"
                  onClick={handleSendVerifications}
                  disabled={isProcessing}
                  style={{
                    marginTop: "1rem",
                    width: "100%",
                    background: "linear-gradient(180deg, var(--accent), #e67030)",
                  }}
                >
                  Send Verification Emails
                </button>
              )}
            </div>
          </div>
        </section>
      </main>
    </>
  );
}

export default Home;
