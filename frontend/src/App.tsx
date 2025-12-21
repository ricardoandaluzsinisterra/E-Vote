import { Route, Routes } from "react-router-dom";
import Register from "./pages/Register.tsx";
import Login from "./pages/Login.tsx";
import Home from "./pages/Home.tsx";
import PollList from "./pages/PollList.tsx";
import PollDetail from "./pages/PollDetail.tsx";
import PollResults from "./pages/PollResults.tsx";
import VotingHistory from "./pages/VotingHistory.tsx";

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
    </Routes>
  );
}

export default App;
