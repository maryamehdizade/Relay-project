import { Routes, Route, Navigate } from "react-router-dom";

import Login from "./pages/Login";
import Chat from "./pages/Chat";
import Documents from "./pages/Documents";

import "./App.css";


function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={<Login />}
      />

      <Route
        path="/chat"
        element={<Chat />}
      />

      <Route
        path="/documents"
        element={<Documents />}
      />

      <Route
        path="*"
        element={
          <Navigate to="/login" replace />
        }
      />
    </Routes>
  );
}

export default App;