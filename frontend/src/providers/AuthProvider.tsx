import { useState, useEffect, type ReactNode } from "react";
import { AuthContext } from "../contexts/AuthContext";
import type {
  AuthContextType,
  User,
  LoginResponse,
  RegisterResponse,
} from "../types/auth.types";
import { decodeJWT } from "../utils/jwt";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [user, setUser] = useState<User | null>(null);

  const isAuthenticated = !!token && !!user;

  useEffect(() => {
    // Check localStorage for existing token
    const storedToken = localStorage.getItem("auth_token");

    if (storedToken) {
      // Try to decode the token so we can restore the user on page refresh
      try {
        const decoded = decodeJWT(storedToken);
        setToken(storedToken);
        setUser({
          user_id: decoded.user_id,
          email: decoded.email,
          // Force verified on frontend so unverified users can view UI while backend verification is not implemented
          is_verified: true,
        });
      } catch (err) {
        // If decoding fails, remove invalid token
        localStorage.removeItem("auth_token");
        setToken(null);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    } else {
      // Allow a development preview mode: if `dev_preview` is set
      // the app will behave as if a user is signed in (useful for styling)
      const devPreview = localStorage.getItem("dev_preview");
      if (devPreview === "true") {
        // populate a minimal fake user so pages render as authenticated
        setToken("dev_token");
        setUser({
          user_id: 0,
          email: "dev@example.com",
          is_verified: true,
        });
        setIsLoading(false);
      } else {
        setIsLoading(false);
      }
    }
  }, []);

  const login = async (email: string, password: string) => {
    const response = await fetch("http://localhost:8000/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    // Handle specific error cases
    if (response.status === 403) {
      const error = await response.json();
      throw new Error(error.detail);
    }

    if (!response.ok) {
      throw new Error("Login failed");
    }

    const data: LoginResponse = await response.json();
    const token = data.access_token;

    // Decode and store token
    const decoded = decodeJWT(token);

    localStorage.setItem("auth_token", token);
    setToken(token);
    setUser({
      user_id: decoded.user_id,
      email: decoded.email,
      is_verified: true,
    });
  };

  const register = async (email: string, password: string) => {
    try {
      const response = await fetch("http://localhost:8000/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        throw new Error("Registration failed");
      }

      const data: RegisterResponse = await response.json();

      //TODO: After registration, user needs to log in
      // Or automatically log them in here
      console.log("Registration successful:", data);
    } catch (error) {
      console.error("Registration error:", error);
      throw error;
    }
  };

  const logout = () => {
    localStorage.removeItem("auth_token");
    // clear dev preview as well when logging out
    localStorage.removeItem("dev_preview");
    setToken(null);
    setUser(null);
  };

  const value: AuthContextType = {
    user,
    token,
    isAuthenticated,
    isLoading,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
