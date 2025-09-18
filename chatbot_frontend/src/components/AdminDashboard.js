import { useState, useEffect } from "react";
import FileUploader from "./FileUploader";
import ChatWindow from "./ChatWindow";
import AdminSettings from "./AdminSettings";
import api from "../api/api";

export default function AdminDashboard() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [stats, setStats] = useState({
    totalFiles: 0,
    totalChats: 0,
    systemStatus: "Active",
    lastActivity: new Date().toLocaleDateString()
  });
  const [recentActivity, setRecentActivity] = useState([]);
  const [activityLoading, setActivityLoading] = useState(false);

  const menuItems = [
    { 
      id: "dashboard", 
      label: "Dashboard", 
      icon: "🏠",
      description: "Overview & Analytics"
    },
    { 
      id: "files", 
      label: "File Management", 
      icon: "📁",
      description: "Upload & Manage Documents"
    },
    { 
      id: "chat", 
      label: "Chat Assistant", 
      icon: "💬",
      description: "AI Chat Interface"
    },
    { 
      id: "settings", 
      label: "Settings", 
      icon: "⚙️",
      description: "System Configuration"
    }
  ];

  useEffect(() => {
    loadDashboardStats();
  }, []);

  const loadDashboardStats = async () => {
    try {
      const filesRes = await api.get("/files/list");
      setStats(prev => ({
        ...prev,
        totalFiles: filesRes.data.length
      }));
    } catch (err) {
      console.error("Failed to load stats:", err);
    }
  };

  const renderDashboardOverview = () => (
    <div className="dashboard-overview">
      <div className="dashboard-welcome">
        <h2>Welcome back, Admin!</h2>
        <p>Here's what's happening with your knowledge base today.</p>
      </div>
      
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">📚</div>
          <div className="stat-content">
            <h3>{stats.totalFiles}</h3>
            <p>Documents</p>
            <span className="stat-change positive">+2 this week</span>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon">💬</div>
          <div className="stat-content">
            <h3>156</h3>
            <p>Chat Sessions</p>
            <span className="stat-change positive">+12 today</span>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon">⚡</div>
          <div className="stat-content">
            <h3>99.9%</h3>
            <p>Uptime</p>
            <span className="stat-change neutral">Last 30 days</span>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon">🔍</div>
          <div className="stat-content">
            <h3>2.3k</h3>
            <p>Queries</p>
            <span className="stat-change positive">+18% this month</span>
          </div>
        </div>
      </div>

      <div className="dashboard-cards">
        <div className="dashboard-card">
          <div className="card-header">
            <h3>📊 System Health</h3>
            <span className="status-badge active">All Systems Operational</span>
          </div>
          <div className="card-content">
            <div className="health-metrics">
              <div className="metric">
                <span className="metric-label">Vector Database</span>
                <span className="metric-status online">Online</span>
              </div>
              <div className="metric">
                <span className="metric-label">AI Model</span>
                <span className="metric-status online">Online</span>
              </div>
              <div className="metric">
                <span className="metric-label">File Processing</span>
                <span className="metric-status online">Online</span>
              </div>
              <div className="metric">
                <span className="metric-label">Authentication</span>
                <span className="metric-status online">Online</span>
              </div>
            </div>
          </div>
        </div>

        <div className="dashboard-card">
          <div className="card-header">
            <h3>📈 Recent Activity</h3>
          </div>
          <div className="card-content">
            <div className="activity-list">
              <div className="activity-item">
                <div className="activity-icon">📄</div>
                <div className="activity-details">
                  <p>New document uploaded</p>
                  <span className="activity-time">2 minutes ago</span>
                </div>
              </div>
              <div className="activity-item">
                <div className="activity-icon">💬</div>
                <div className="activity-details">
                  <p>Chat session started</p>
                  <span className="activity-time">5 minutes ago</span>
                </div>
              </div>
              <div className="activity-item">
                <div className="activity-icon">🔍</div>
                <div className="activity-details">
                  <p>Knowledge base query</p>
                  <span className="activity-time">8 minutes ago</span>
                </div>
              </div>
              <div className="activity-item">
                <div className="activity-icon">⚙️</div>
                <div className="activity-details">
                  <p>Settings updated</p>
                  <span className="activity-time">1 hour ago</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="quick-actions">
        <h3>Quick Actions</h3>
        <div className="action-buttons">
          <button 
            className="action-btn primary"
            onClick={() => setActiveTab("files")}
          >
            <span className="btn-icon">📤</span>
            Upload Documents
          </button>
          <button 
            className="action-btn secondary"
            onClick={() => setActiveTab("chat")}
          >
            <span className="btn-icon">💬</span>
            Start Chat
          </button>
          <button 
            className="action-btn tertiary"
            onClick={() => setActiveTab("settings")}
          >
            <span className="btn-icon">⚙️</span>
            System Settings
          </button>
        </div>
      </div>
    </div>
  );

  const renderContent = () => {
    switch (activeTab) {
      case "dashboard":
        return renderDashboardOverview();
      case "files":
        return <FileUploader />;
      case "chat":
        return <ChatWindow />;
      case "settings":
        return <AdminSettings />;
      default:
        return renderDashboardOverview();
    }
  };

  return (
    <div className="modern-admin-dashboard">
      {/* Sidebar Navigation */}
      <div className={`admin-sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-header">
          <div className="logo">
            <span className="logo-icon">🤖</span>
            {!sidebarCollapsed && <span className="logo-text">RAG Admin</span>}
          </div>
          <button 
            className="sidebar-toggle"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          >
            {sidebarCollapsed ? '→' : '←'}
          </button>
        </div>
        
        <nav className="sidebar-nav">
          {menuItems.map(item => (
            <button
              key={item.id}
              className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
              onClick={() => setActiveTab(item.id)}
              title={sidebarCollapsed ? item.label : ''}
            >
              <span className="nav-icon">{item.icon}</span>
              {!sidebarCollapsed && (
                <div className="nav-content">
                  <span className="nav-label">{item.label}</span>
                  <span className="nav-description">{item.description}</span>
                </div>
              )}
            </button>
          ))}
        </nav>
        
        {!sidebarCollapsed && (
          <div className="sidebar-footer">
            <div className="user-info">
              <div className="user-avatar">👤</div>
              <div className="user-details">
                <span className="user-name">Administrator</span>
                <span className="user-role">System Admin</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      <div className="admin-main-content">
        <div className="content-header">
          <div className="breadcrumb">
            <span className="breadcrumb-item">Admin</span>
            <span className="breadcrumb-separator">/</span>
            <span className="breadcrumb-item active">
              {menuItems.find(item => item.id === activeTab)?.label || 'Dashboard'}
            </span>
          </div>
          
          <div className="header-actions">
            <button className="header-btn">
              <span>🔔</span>
            </button>
            <button className="header-btn">
              <span>❓</span>
            </button>
          </div>
        </div>
        
        <div className="content-body">
          {renderContent()}
        </div>
      </div>
    </div>
  );
}
