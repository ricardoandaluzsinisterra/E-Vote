import { Route, Routes, Navigate } from "react-router-dom";
import Register from "./pages/Register.tsx";
import Login from "./pages/Login.tsx";
import Home from "./pages/Home.tsx";
import AdminLogin from "./pages/AdminLogin.tsx";
import AdminDashboard from "./pages/AdminDashboard.tsx";
import ProtectedRoute from "./components/ProtectedRoute";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/admin/login" element={<AdminLogin />} />
      <Route
        path="/admin/dashboard"
        element={
          <ProtectedRoute>
            <AdminDashboard />
          </ProtectedRoute>
        }
      />
      <Route path="/home" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
