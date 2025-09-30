import { useState, useEffect } from "react";
import FileUploader from "./FileUploader";
import ChatWindow from "./ChatWindow";
import AdminSettings from "./AdminSettings";
import ActivityFeed from "./ActivityFeed";
import Layout from "./Layout";
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
  const [collections, setCollections] = useState([]);
  const [selectedCollectionId, setSelectedCollectionId] = useState(null);
  const [collectionFiles, setCollectionFiles] = useState([]);

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

  useEffect(() => {
    if (activeTab === "files") {
      loadCollections();
    }
  }, [activeTab]);

  useEffect(() => {
    if (!selectedCollectionId && collections.length > 0) {
      setSelectedCollectionId(collections[0].collection_id);
    }
  }, [collections, selectedCollectionId]);

  const loadCollections = async () => {
    try {
      const res = await api.get("/collections/");
      setCollections(res.data || []);
    } catch (err) {
      console.error("Failed to load collections:", err);
    }
  };

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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Welcome back, Admin!</h2>
          <p className="text-gray-600">Here's what's happening with your knowledge base today.</p>
        </div>
        <button
          onClick={loadDashboardStats}
          className="btn btn-secondary"
        >
          <span className="mr-2">🔄</span>
          Refresh
        </button>
      </div>
      
      <div className="stats-grid">
        <div className="card group hover:scale-105 transition-transform duration-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 mb-1">Documents</p>
              <p className="text-2xl font-bold text-gray-900">{stats.totalFiles}</p>
              <p className="text-xs text-gray-500 mt-1">
                {storageStats?.total_size_mb || 0} MB total
              </p>
            </div>
            <div className="p-3 rounded-lg bg-primary-100 text-primary-600">
              <span className="text-2xl">📚</span>
            </div>
          </div>
        </div>
        
        <div className="card group hover:scale-105 transition-transform duration-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 mb-1">Chat Sessions</p>
              <p className="text-2xl font-bold text-gray-900">{stats.totalChats}</p>
              <p className="text-xs text-gray-500 mt-1">
                {chatAnalytics?.active_users || 0} active users
              </p>
            </div>
            <div className="p-3 rounded-lg bg-success-100 text-success-600">
              <span className="text-2xl">💬</span>
            </div>
          </div>
        </div>
        
        <div className="card group hover:scale-105 transition-transform duration-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 mb-1">System Health</p>
              <p className="text-2xl font-bold text-gray-900">
                {systemHealth?.overall_status === "healthy" ? "99.9%" : "Issues"}
              </p>
              <p className={`text-xs mt-1 ${
                systemHealth?.overall_status === "healthy" ? "text-success-600" : "text-error-600"
              }`}>
                {systemHealth?.healthy_services || 0}/{systemHealth?.total_services || 4} services
              </p>
            </div>
            <div className={`p-3 rounded-lg ${
              systemHealth?.overall_status === "healthy" 
                ? "bg-success-100 text-success-600" 
                : "bg-error-100 text-error-600"
            }`}>
              <span className="text-2xl">⚡</span>
            </div>
          </div>
        </div>
        
        <div className="card group hover:scale-105 transition-transform duration-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 mb-1">Total Queries</p>
              <p className="text-2xl font-bold text-gray-900">{chatAnalytics?.total_queries || 0}</p>
              <p className="text-xs text-gray-500 mt-1">
                Avg {chatAnalytics?.avg_queries_per_session || 0} per session
              </p>
            </div>
            <div className="p-3 rounded-lg bg-warning-100 text-warning-600">
              <span className="text-2xl">🔍</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <div className="card-header">
            <div className="flex items-center justify-between">
              <h3 className="card-title">📊 System Health</h3>
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                systemHealth?.overall_status === "healthy" ? "bg-success-100 text-success-800" : 
                systemHealth?.overall_status === "degraded" ? "bg-warning-100 text-warning-800" : "bg-error-100 text-error-800"
              }`}>
                {systemHealth?.overall_status === "healthy" ? "All Systems Operational" : 
                 systemHealth?.overall_status === "degraded" ? "Some Services Degraded" : "System Issues Detected"}
              </span>
            </div>
          </div>
          <div className="space-y-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-600">Vector Database</span>
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  systemHealth?.services?.qdrant?.status === "healthy" ? "bg-success-100 text-success-800" : 
                  systemHealth?.services?.qdrant?.status === "degraded" ? "bg-warning-100 text-warning-800" : "bg-error-100 text-error-800"
                }`}>
                  {systemHealth?.services?.qdrant?.status === "healthy" ? "Online" : 
                   systemHealth?.services?.qdrant?.status === "degraded" ? "Degraded" : "Offline"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-600">AI Model</span>
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  systemHealth?.services?.ai_model?.status === "healthy" ? "bg-success-100 text-success-800" : "bg-error-100 text-error-800"
                }`}>
                  {systemHealth?.services?.ai_model?.status === "healthy" ? "Online" : "Offline"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-600">File Processing</span>
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  systemHealth?.services?.file_processing?.status === "healthy" ? "bg-success-100 text-success-800" : "bg-error-100 text-error-800"
                }`}>
                  {systemHealth?.services?.file_processing?.status === "healthy" ? "Online" : "Offline"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-600">Authentication</span>
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  systemHealth?.services?.authentication?.status === "healthy" ? "bg-success-100 text-success-800" : "bg-error-100 text-error-800"
                }`}>
                  {systemHealth?.services?.authentication?.status === "healthy" ? "Online" : "Offline"}
                </span>
              </div>
            </div>
            <button 
              className="w-full btn btn-secondary"
              onClick={loadSystemHealth}
              disabled={healthLoading}
            >
              {healthLoading ? (
                <>
                  <div className="spinner mr-2"></div>
                  Checking...
                </>
              ) : (
                <>
                  <span className="mr-2">🔄</span>
                  Refresh Health
                </>
              )}
            </button>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3 className="card-title">📊 Quick Actions</h3>
            <p className="card-subtitle">Quick access to system features</p>
          </div>
          <div className="space-y-3">
            <button 
              className="w-full btn btn-primary text-left justify-start"
              onClick={() => setActiveTab("files")}
            >
              <span className="mr-3">📁</span>
              <div>
                <div className="font-medium">Manage Files</div>
                <div className="text-xs opacity-75">Upload and organize documents</div>
              </div>
            </button>
            <button 
              className="w-full btn btn-secondary text-left justify-start"
              onClick={() => setActiveTab("chat")}
            >
              <span className="mr-3">💬</span>
              <div>
                <div className="font-medium">Start Chat</div>
                <div className="text-xs opacity-75">Ask questions about your documents</div>
              </div>
            </button>
            <button 
              className="w-full btn btn-secondary text-left justify-start"
              onClick={() => setActiveTab("activity")}
            >
              <span className="mr-3">📋</span>
              <div>
                <div className="font-medium">View Activity</div>
                <div className="text-xs opacity-75">Track all system activities</div>
              </div>
            </button>
            <button 
              className="w-full btn btn-secondary text-left justify-start"
              onClick={() => setActiveTab("analytics")}
            >
              <span className="mr-3">📊</span>
              <div>
                <div className="font-medium">Analytics</div>
                <div className="text-xs opacity-75">View usage statistics</div>
              </div>
            </button>
          </div>
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
        return (
          <FileUploader
            collections={collections}
            defaultCollectionId={selectedCollectionId}
            onCollectionChange={(value) => setSelectedCollectionId(value)}
            onFilesLoaded={(files) => setCollectionFiles(files)}
            onStatsChange={(data) =>
              setStats((prev) => ({
                ...prev,
                totalFiles: data?.total ?? prev.totalFiles
              }))
            }
            compact
          />
        );
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

  const sidebarProps = {
    isOpen: !sidebarCollapsed,
    onClose: () => setSidebarCollapsed(true),
    title: "RAG Admin",
    icon: "🤖",
    menuItems: menuItems.map(item => ({
      ...item,
      icon: () => <span className="text-xl">{item.icon}</span>
    })),
    activeTab,
    onTabChange: (tab) => {
      setActiveTab(tab);
      setSidebarCollapsed(true);
    },
    userInfo: {
      name: "Administrator",
      role: "System Admin"
    }
  };

  const headerContent = (
    <>
      <button className="p-2 text-gray-600 hover:text-gray-900" onClick={loadDashboardStats}>
        <span>🔄</span>
      </button>
      <button className="p-2 text-gray-600 hover:text-gray-900">
        <span>🔔</span>
      </button>
      <button className="p-2 text-gray-600 hover:text-gray-900">
        <span>❓</span>
      </button>
    </>
  );

  return (
    <Layout sidebarProps={sidebarProps} headerContent={headerContent}>
      {renderContent()}
    </Layout>
  );
}
