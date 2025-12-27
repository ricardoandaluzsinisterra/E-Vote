import { Route, Routes, Navigate } from "react-router-dom";
import Register from "./pages/Register.tsx";
import Login from "./pages/Login.tsx";
import Home from "./pages/Home.tsx";
import PollList from "./pages/PollList.tsx";
import PollDetail from "./pages/PollDetail.tsx";
import PollResults from "./pages/PollResults.tsx";
import VotingHistory from "./pages/VotingHistory.tsx";
import AdminLogin from "./pages/AdminLogin.tsx";
import AdminDashboard from "./pages/AdminDashboard.tsx";
import ProtectedRoute from "./components/ProtectedRoute";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/polls" element={<PollList />} />
      <Route path="/polls/:pollId" element={<PollDetail />} />
      <Route path="/polls/:pollId/results" element={<PollResults />} />
      <Route path="/voting-history" element={<VotingHistory />} />
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