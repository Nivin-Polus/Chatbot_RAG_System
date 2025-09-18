import { useState } from "react";
import FileUploader from "./FileUploader";
import ChatWindow from "./ChatWindow";
import AdminSettings from "./AdminSettings";

export default function AdminDashboard() {
  const [activeTab, setActiveTab] = useState("files");

  const tabs = [
    { id: "files", label: "File Management", icon: "📁" },
    { id: "chat", label: "Chat Assistant", icon: "💬" },
    { id: "settings", label: "Settings", icon: "⚙️" }
  ];

  const renderContent = () => {
    switch (activeTab) {
      case "files":
        return <FileUploader />;
      case "chat":
        return <ChatWindow />;
      case "settings":
        return <AdminSettings />;
      default:
        return <FileUploader />;
    }
  };

  return (
    <div className="admin-dashboard">
      <div className="dashboard-header">
        <h1>Admin Dashboard</h1>
        <p>Manage your knowledge base and system settings</p>
      </div>
      
      <div className="dashboard-tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-label">{tab.label}</span>
          </button>
        ))}
      </div>
      
      <div className="dashboard-content">
        {renderContent()}
      </div>
    </div>
  );
}
