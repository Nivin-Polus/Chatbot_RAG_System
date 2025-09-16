import { useState } from "react";
import Login from "./components/Login";
import ChatWindow from "./components/ChatWindow";
import FileUploader from "./components/FileUploader";
import "./styles.css";

function App() {
  const [loggedIn, setLoggedIn] = useState(!!localStorage.getItem("access_token"));

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    setLoggedIn(false);
  };

  if (!loggedIn) {
    return <Login onLogin={() => setLoggedIn(true)} />;
  }

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Knowledge Base Chatbot</h1>
        <button className="logout-btn" onClick={handleLogout}>
          Logout
        </button>
      </header>
      <div className="main-content">
        <div className="left-panel">
          <FileUploader />
        </div>
        <div className="right-panel">
          <ChatWindow />
        </div>
      </div>
    </div>
  );
}

export default App;
