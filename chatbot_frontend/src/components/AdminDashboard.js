import { useState, useEffect } from "react";
import FileUploader from "./FileUploader";
import ChatWindow from "./ChatWindow";
import AdminSettings from "./AdminSettings";
import ActivityFeed from "./ActivityFeed";
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
      id: "activity", 
      label: "Activity Feed", 
      icon: "📋",
      description: "Track All Activities"
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
            <span className="stat-change positive">
              {storageStats?.total_size_mb || 0} MB total
            </span>
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
            <span className={`status-badge ${
              systemHealth?.overall_status === "healthy" ? "active" : 
              systemHealth?.overall_status === "degraded" ? "warning" : "error"
            }`}>
              {systemHealth?.overall_status === "healthy" ? "All Systems Operational" : 
               systemHealth?.overall_status === "degraded" ? "Some Services Degraded" : "System Issues Detected"}
            </span>
          </div>
          <div className="card-content">
            <div className="health-metrics">
              <div className="metric">
                <span className="metric-label">Vector Database</span>
                <span className={`metric-status ${
                  systemHealth?.services?.qdrant?.status === "healthy" ? "online" : 
                  systemHealth?.services?.qdrant?.status === "degraded" ? "degraded" : "offline"
                }`}>
                  {systemHealth?.services?.qdrant?.status === "healthy" ? "Online" : 
                   systemHealth?.services?.qdrant?.status === "degraded" ? "Degraded" : "Offline"}
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
            <h3>📊 System Overview</h3>
            <p>Quick access to system features</p>
          </div>
          <div className="card-content">
            <div className="quick-actions">
              <button 
                className="quick-action-btn"
                onClick={() => setActiveTab("files")}
              >
                <span className="action-icon">📁</span>
                <span className="action-label">Manage Files</span>
                <span className="action-description">Upload and organize documents</span>
              </button>
              <button 
                className="quick-action-btn"
                onClick={() => setActiveTab("chat")}
              >
                <span className="action-icon">💬</span>
                <span className="action-label">Start Chat</span>
                <span className="action-description">Ask questions about your documents</span>
              </button>
              <button 
                className="quick-action-btn"
                onClick={() => setActiveTab("activity")}
              >
                <span className="action-icon">📋</span>
                <span className="action-label">View Activity</span>
                <span className="action-description">Track all system activities</span>
              </button>
              <button 
                className="quick-action-btn"
                onClick={() => setActiveTab("analytics")}
              >
                <span className="action-icon">📊</span>
                <span className="action-label">Analytics</span>
                <span className="action-description">View usage statistics</span>
              </button>
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
            onClick={() => setActiveTab("analytics")}
          >
            <span className="btn-icon">📊</span>
            View Analytics
          </button>
          <button 
            className="action-btn quaternary"
            onClick={() => setActiveTab("settings")}
          >
            <span className="btn-icon">⚙️</span>
            System Settings
          </button>
        </div>
      </div>
    </div>
  );

  const renderAnalytics = () => (
    <div className="analytics-dashboard">
      <div className="analytics-header">
        <h2>📊 Analytics Dashboard</h2>
        <p>Comprehensive usage and performance analytics</p>
        <button 
          className="refresh-btn"
          onClick={loadDashboardStats}
        >
          🔄 Refresh Data
        </button>
      </div>

      <div className="analytics-grid">
        <div className="analytics-card">
          <div className="card-header">
            <h3>💬 Chat Analytics</h3>
          </div>
          <div className="card-content">
            {chatAnalytics ? (
              <div className="analytics-metrics">
                <div className="metric-row">
                  <span className="metric-label">Total Sessions:</span>
                  <span className="metric-value">{chatAnalytics.total_sessions}</span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">Total Queries:</span>
                  <span className="metric-value">{chatAnalytics.total_queries}</span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">Active Users:</span>
                  <span className="metric-value">{chatAnalytics.active_users}</span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">Avg Queries/Session:</span>
                  <span className="metric-value">{chatAnalytics.avg_queries_per_session}</span>
                </div>
                <div className="most-active">
                  <h4>Most Active Users:</h4>
                  {chatAnalytics.most_active_users?.map((user, index) => (
                    <div key={index} className="active-user">
                      <span>{user.user_id}</span>
                      <span>{user.query_count} queries</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="loading">Loading analytics...</div>
            )}
          </div>
        </div>

        <div className="analytics-card">
          <div className="card-header">
            <h3>💾 Storage Analytics</h3>
          </div>
          <div className="card-content">
            {storageStats ? (
              <div className="analytics-metrics">
                <div className="metric-row">
                  <span className="metric-label">Total Files:</span>
                  <span className="metric-value">{storageStats.total_files}</span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">Total Size:</span>
                  <span className="metric-value">{storageStats.total_size_mb} MB</span>
                </div>
                <div className="file-types">
                  <h4>File Types:</h4>
                  {Object.entries(storageStats.file_types || {}).map(([type, count]) => (
                    <div key={type} className="file-type-row">
                      <span>{type}:</span>
                      <span>{count} files</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="loading">Loading storage stats...</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  const renderMonitoring = () => (
    <div className="monitoring-dashboard">
      <div className="monitoring-header">
        <h2>🔍 System Health Monitoring</h2>
        <p>Real-time system health and performance monitoring</p>
        <button 
          className="refresh-all-btn"
          onClick={loadSystemHealth}
          disabled={healthLoading}
        >
          {healthLoading ? "🔄 Refreshing..." : "🔄 Refresh All"}
        </button>
      </div>

      <div className="monitoring-grid">
        {systemHealth?.services && Object.entries(systemHealth.services).map(([serviceName, serviceData]) => (
          <div key={serviceName} className="service-card">
            <div className="service-header">
              <h3>
                {serviceName === "qdrant" && "🗃️ Vector Database"}
                {serviceName === "ai_model" && "🤖 AI Model"}
                {serviceName === "file_processing" && "📁 File Processing"}
                {serviceName === "authentication" && "🔐 Authentication"}
              </h3>
              <span className={`service-status ${serviceData.status}`}>
                {serviceData.status}
              </span>
            </div>
            <div className="service-details">
              {serviceData.status === "healthy" ? (
                <div className="service-metrics">
                  {serviceName === "qdrant" && (
                    <>
                      <div className="metric">Collection: {serviceData.kb_collection_exists ? "✅ Exists" : "❌ Missing"}</div>
                      <div className="metric">Points: {serviceData.kb_collection_points || 0}</div>
                    </>
                  )}
                  {serviceName === "ai_model" && (
                    <>
                      <div className="metric">Model: {serviceData.model}</div>
                      <div className="metric">Response Time: {serviceData.response_time_ms}ms</div>
                    </>
                  )}
                  {serviceName === "file_processing" && (
                    <>
                      <div className="metric">Directory: ✅ Writable</div>
                      <div className="metric">Max Size: {serviceData.max_file_size_mb}MB</div>
                    </>
                  )}
                  {serviceName === "authentication" && (
                    <>
                      <div className="metric">JWT: ✅ Configured</div>
                      <div className="metric">Database: {serviceData.database?.status}</div>
                    </>
                  )}
                </div>
              ) : (
                <div className="service-error">
                  <span className="error-message">{serviceData.error}</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="system-overview">
        <div className="overview-card">
          <h3>📊 System Overview</h3>
          <div className="overview-metrics">
            <div className="overview-metric">
              <span className="metric-label">Overall Status:</span>
              <span className={`metric-value status-${systemHealth?.overall_status}`}>
                {systemHealth?.overall_status}
              </span>
            </div>
            <div className="overview-metric">
              <span className="metric-label">Healthy Services:</span>
              <span className="metric-value">
                {systemHealth?.healthy_services}/{systemHealth?.total_services}
              </span>
            </div>
            <div className="overview-metric">
              <span className="metric-label">Health Check Time:</span>
              <span className="metric-value">{systemHealth?.health_check_time_ms}ms</span>
            </div>
            <div className="overview-metric">
              <span className="metric-label">Last Updated:</span>
              <span className="metric-value">
                {systemHealth?.timestamp ? new Date(systemHealth.timestamp).toLocaleString() : "Never"}
              </span>
            </div>
          </div>
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
      case "analytics":
        return renderAnalytics();
      case "activity":
        return <ActivityFeed />;
      case "monitoring":
        return renderMonitoring();
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
            <button className="header-btn" onClick={loadDashboardStats}>
              <span>🔄</span>
            </button>
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
