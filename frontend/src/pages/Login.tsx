import { useAuth } from "../hooks/useAuth";

function Login() {
  const { login } = useAuth()
  return (
    <div>
      <h1>Login Page</h1>
      <p>Welcome to E-Vote</p>
    </div>
  );
}

export default Login;
