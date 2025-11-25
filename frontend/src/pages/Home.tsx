import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

function Home() {
  const { user, isAuthenticated, logout } = useAuth();

  if (isAuthenticated && user) {
    return (
      <div>
        <h1>Home Page</h1>
        <p>Welcome back, {user.email}!</p>
        <button onClick={logout}>Logout</button>
      </div>
    );
  }

  return (
    <div>
      <h1>Home Page</h1>
      <p>Welcome to E-Vote</p>
      <nav>
        <Link to="/login">Login</Link>
        {" | "}
        <Link to="/register">Register</Link>
      </nav>
    </div>
  );
}

export default Home;
