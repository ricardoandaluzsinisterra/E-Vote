import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import DarkVeil from "../components/DarkVeil";

function Home() {
  const [isDark, setIsDark] = useState<boolean>(
    typeof window !== "undefined" && window.matchMedia
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
      : false
  );

  useEffect(() => {
    if (!window.matchMedia) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => setIsDark(e.matches);
    mq.addEventListener?.("change", handler);
    return () => mq.removeEventListener?.("change", handler);
  }, []);

  // tune shader props per theme
  const veilProps = isDark
    ? {
        hueShift: -160, // blue tint
        noiseIntensity: 0.02,
        scanlineIntensity: 0.02,
        speed: 0.3,
        scanlineFrequency: 0.002,
        warpAmount: 0.02,
        resolutionScale: 1
      }
    : {
        hueShift: 90, // stronger shift toward orange
        cssFilter: "hue-rotate(90deg) saturate(1.25) brightness(1.05)",
        noiseIntensity: 0.03,
        scanlineIntensity: 0.03,
        speed: 0.7,
        scanlineFrequency: 0.003,
        warpAmount: 0.04,
        resolutionScale: 1
      };

  return (
    <div className="landing-page dark-veil" style={{ position: "relative" }}>
      <DarkVeil {...veilProps} />
      <div
        className="darkveil-tint"
        style={{
          background: isDark ? "rgba(30,110,255,0.18)" : "rgba(255,140,40,0.6)"
        }}
      />
      <div className="darkveil-wrapper">
        {/* Navigation Header */}
        <header className="landing-nav">
          <div className="nav-container">
            <div className="nav-brand">
              <h1 className="brand-name">E‑Vote</h1>
            </div>
            <nav className="nav-links">
              <Link to="/admin/login" className="admin-login-btn">
                Administrator Login
              </Link>
            </nav>
          </div>
        </header>

        {/* Hero Section */}
        <main className="hero-section">
          <div className="hero-container">
            <div className="hero-content">
              <h1 className="hero-title">
                Secure Digital Voting
                <span className="gradient-text">Made Simple</span>
              </h1>
              <p className="hero-description">
                Transform your elections with our cutting-edge platform.
                Auditable, transparent, and accessible voting for the modern
                world.
              </p>
              <div className="hero-features">
                <div className="feature-item">
                  <div className="feature-icon">🔐</div>
                  <span>End-to-end encryption</span>
                </div>
                <div className="feature-item">
                  <div className="feature-icon">📊</div>
                  <span>Real-time results</span>
                </div>
                <div className="feature-item">
                  <div className="feature-icon">✅</div>
                  <span>Auditable records</span>
                </div>
              </div>
              <div className="hero-cta">
                <Link to="/admin/login" className="btn primary large">
                  Get Started
                </Link>
                <button className="btn secondary large">Learn More</button>
              </div>
            </div>
          </div>
        </main>

        {/* Features Section */}
        <section className="features-section">
          <div className="features-container">
            <h2 className="section-title">Why Choose E‑Vote?</h2>
            <div className="features-grid">
              <div className="feature-card">
                <div className="feature-card-icon">🛡️</div>
                <h3>Secure by Design</h3>
                <p>
                  Military-grade encryption and multi-factor authentication
                  ensure your elections remain tamper-proof.
                </p>
              </div>
              <div className="feature-card">
                <div className="feature-card-icon">⚡</div>
                <h3>Lightning Fast</h3>
                <p>
                  Results in real-time with our optimized infrastructure that
                  scales to millions of voters.
                </p>
              </div>
              <div className="feature-card">
                <div className="feature-card-icon">📱</div>
                <h3>Accessible Everywhere</h3>
                <p>
                  Vote from any device, anywhere. Our responsive design works
                  seamlessly across all platforms.
                </p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

export default Home;