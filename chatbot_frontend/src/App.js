import { useState } from "react";
import Login from "./components/Login";
import ChatWindow from "./components/ChatWindow";
import FileUploader from "./components/FileUploader";
import "./styles.css";

function App() {
  const [loggedIn, setLoggedIn] = useState(!!localStorage.getItem("access_token"));
  const [userRole, setUserRole] = useState(localStorage.getItem("user_role"));

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
          // Admin Interface
          <div className="admin-layout">
            <div className="left-panel">
              <FileUploader />
            </div>
            <div className="right-panel">
              <ChatWindow />
            </div>
          </div>
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
