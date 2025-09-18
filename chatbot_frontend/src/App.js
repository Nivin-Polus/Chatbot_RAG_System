import { useState, useEffect } from "react";
import Login from "./components/Login";
import ChatWindow from "./components/ChatWindow";
import AdminDashboard from "./components/AdminDashboard";
import api from "./api/api";
import "./styles.css";

function App() {
  const [loggedIn, setLoggedIn] = useState(!!localStorage.getItem("access_token"));
  const [userRole, setUserRole] = useState(localStorage.getItem("user_role"));
  const [isValidating, setIsValidating] = useState(true);

  // Validate token on app start
  useEffect(() => {
    const validateToken = async () => {
      const token = localStorage.getItem("access_token");
      if (token) {
        try {
          // Try to make a simple authenticated request
          await api.get("/files/list");
          setLoggedIn(true);
          setUserRole(localStorage.getItem("user_role"));
        } catch (err) {
          // Token is invalid, clear storage
          localStorage.removeItem("access_token");
          localStorage.removeItem("user_role");
          setLoggedIn(false);
          setUserRole(null);
        }
      }
      setIsValidating(false);
    };

    validateToken();
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_role");
    setLoggedIn(false);
    setUserRole(null);
  };

  const handleLogin = () => {
    setLoggedIn(true);
    setUserRole(localStorage.getItem("user_role"));
  };

  // Show loading while validating token
  if (isValidating) {
    return (
      <div className="app-container">
        <div className="loading-container">
          <h2>Validating session...</h2>
        </div>
      </div>
    );
  }

  if (!loggedIn) {
    return <Login onLogin={handleLogin} />;
  }

  const isAdmin = userRole === "admin";

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Knowledge Base Chatbot</h1>
        <div className="header-info">
          <span className="user-role">Role: {userRole}</span>
          <button className="logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>
      <div className="main-content">
        {isAdmin ? (
          // Admin Interface - New Dashboard
          <AdminDashboard />
        ) : (
          // User Interface - Only Chat
          <div className="user-layout">
            <ChatWindow />
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
