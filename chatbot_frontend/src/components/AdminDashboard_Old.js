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
  const [systemHealth, setSystemHealth] = useState(null);
  const [chatAnalytics, setChatAnalytics] = useState(null);
  const [storageStats, setStorageStats] = useState(null);
  const [healthLoading, setHealthLoading] = useState(false);

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
      id: "analytics", 
      label: "Analytics", 
      icon: "📊",
      description: "Usage & Performance"
    },
    { 
      id: "monitoring", 
      label: "System Health", 
      icon: "🔍",
      description: "Health & Monitoring"
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
      // Load system overview
      const overviewRes = await api.get("/system/stats/overview");
      const overview = overviewRes.data;
      
      // Update stats
      setStats(prev => ({
        ...prev,
        totalFiles: overview.storage_statistics?.total_files || 0,
        totalChats: overview.chat_analytics?.total_sessions || 0,
        systemStatus: overview.system_health?.overall_status === "healthy" ? "Active" : "Issues Detected"
      }));
      
      setSystemHealth(overview.system_health);
      setChatAnalytics(overview.chat_analytics);
      setStorageStats(overview.storage_statistics);
      
    } catch (err) {
      console.error("Failed to load stats:", err);
      // Fallback to basic file list
      try {
        const filesRes = await api.get("/files/list");
        setStats(prev => ({
          ...prev,
          totalFiles: filesRes.data.length
        }));
      } catch (fallbackErr) {
        console.error("Failed to load fallback stats:", fallbackErr);
      }
    }
  };

  const loadSystemHealth = async () => {
    setHealthLoading(true);
    try {
      const healthRes = await api.get("/system/health/detailed");
      setSystemHealth(healthRes.data);
    } catch (err) {
      console.error("Failed to load system health:", err);
    }
    setHealthLoading(false);
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
            <h3>{stats.totalChats}</h3>
            <p>Chat Sessions</p>
            <span className="stat-change positive">
              {chatAnalytics?.active_users || 0} active users
            </span>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon">⚡</div>
          <div className="stat-content">
            <h3>{systemHealth?.overall_status === "healthy" ? "99.9%" : "Issues"}</h3>
            <p>System Health</p>
            <span className={`stat-change ${systemHealth?.overall_status === "healthy" ? "positive" : "negative"}`}>
              {systemHealth?.healthy_services || 0}/{systemHealth?.total_services || 4} services
            </span>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon">🔍</div>
          <div className="stat-content">
            <h3>{chatAnalytics?.total_queries || 0}</h3>
            <p>Total Queries</p>
            <span className="stat-change positive">
              Avg {chatAnalytics?.avg_queries_per_session || 0} per session
            </span>
          </div>
        </div>
      </div>

      <div className="dashboard-cards">
        <div className="dashboard-card">
          <div className="card-header">
            <h3>📊 System Health</h3>
            <span className={`status-badge ${systemHealth?.overall_status === "healthy" ? "active" : "warning"}`}>
              {systemHealth?.overall_status === "healthy" ? "All Systems Operational" : "System Issues Detected"}
            </span>
          </div>
          <div className="card-content">
            <div className="health-metrics">
              <div className="metric">
                <span className="metric-label">Vector Database</span>
                <span className={`metric-status ${systemHealth?.services?.qdrant?.status === "healthy" ? "online" : "offline"}`}>
                  {systemHealth?.services?.qdrant?.status === "healthy" ? "Online" : "Offline"}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">AI Model</span>
                <span className={`metric-status ${systemHealth?.services?.ai_model?.status === "healthy" ? "online" : "offline"}`}>
                  {systemHealth?.services?.ai_model?.status === "healthy" ? "Online" : "Offline"}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">File Processing</span>
                <span className={`metric-status ${systemHealth?.services?.file_processing?.status === "healthy" ? "online" : "offline"}`}>
                  {systemHealth?.services?.file_processing?.status === "healthy" ? "Online" : "Offline"}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">Authentication</span>
                <span className={`metric-status ${systemHealth?.services?.authentication?.status === "healthy" ? "online" : "offline"}`}>
                  {systemHealth?.services?.authentication?.status === "healthy" ? "Online" : "Offline"}
                </span>
              </div>
            </div>
            <button 
              className="refresh-health-btn"
              onClick={loadSystemHealth}
              disabled={healthLoading}
            >
              {healthLoading ? "🔄 Checking..." : "🔄 Refresh Health"}
            </button>
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
    </div>

    <div className="analytics-grid">
      <div className="analytics-card">
        <div className="card-header">
          <h3>💬 Chat Analytics</h3>

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
