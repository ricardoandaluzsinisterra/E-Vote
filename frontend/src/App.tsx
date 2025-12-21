import { Route, Routes } from "react-router-dom";
import Register from "./pages/Register.tsx";
import Login from "./pages/Login.tsx";
import Home from "./pages/Home.tsx";
import PollList from "./pages/PollList.tsx";
import PollDetail from "./pages/PollDetail.tsx";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/polls" element={<PollList />} />
      <Route path="/polls/:pollId" element={<PollDetail />} />
    </Routes>
  );
}

export default App;
