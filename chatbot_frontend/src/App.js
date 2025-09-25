import { useState, useEffect } from "react";
import Login from "./components/Login";
import ChatWindow from "./components/ChatWindow";
import AdminDashboard from "./components/AdminDashboard";
import SuperAdminDashboard from "./components/SuperAdminDashboard";
import UserAdminDashboard from "./components/UserAdminDashboard";
import RegularUserDashboard from "./components/RegularUserDashboard";
import api from "./api/api";
import "./styles.css";

function App() {
  const [loggedIn, setLoggedIn] = useState(!!localStorage.getItem("access_token"));
  const [userRole, setUserRole] = useState(localStorage.getItem("user_role"));
  const [userData, setUserData] = useState(null);
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
          setUserData({
            username: localStorage.getItem("username"),
            role: localStorage.getItem("user_role"),
            website_id: localStorage.getItem("website_id")
          });
        } catch (err) {
          // Token is invalid, clear storage
          clearUserData();
        }
      }
      setIsValidating(false);
    };

    validateToken();
  }, []);

  const clearUserData = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_role");
    localStorage.removeItem("username");
    localStorage.removeItem("website_id");
    setLoggedIn(false);
    setUserRole(null);
    setUserData(null);
  };

  const handleLogout = () => {
    clearUserData();
  };

  const handleLogin = (loginData) => {
    setLoggedIn(true);
    setUserRole(loginData.role);
    setUserData(loginData);
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

  // Role-based dashboard rendering
  const renderDashboard = () => {
    switch (userRole) {
      case 'super_admin':
        return <SuperAdminDashboard onLogout={handleLogout} />;
      case 'user_admin':
      case 'admin': // Legacy support
        return <UserAdminDashboard onLogout={handleLogout} />;
      case 'user':
        return <RegularUserDashboard onLogout={handleLogout} />;
      default:
        return (
          <div className="error-container">
            <h2>Unknown user role: {userRole}</h2>
            <button onClick={handleLogout}>Logout</button>
          </div>
        );
    }
  };

  return (
    <div className="app-container">
      {renderDashboard()}
    </div>
  );
}

export default App;
