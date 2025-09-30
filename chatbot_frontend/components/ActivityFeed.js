import React, { useState, useEffect } from "react";
import api from "../api/api";

export default function ActivityFeed() {
  const [activities, setActivities] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all"); // all, file_upload, chat_query, chat_session_start, file_delete

  const loadActivities = async () => {
    try {
      setLoading(true);
      const [activitiesRes, statsRes] = await Promise.all([
        api.get("/activity/recent?limit=50"),
        api.get("/activity/stats")
      ]);
      
      setActivities(activitiesRes.data.activities);
      setStats(statsRes.data);
      setError("");
    } catch (err) {
      console.error("Failed to load activities:", err);
      setError("Failed to load activities: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadActivities();
    // Refresh every 30 seconds
    const interval = setInterval(loadActivities, 30000);
    return () => clearInterval(interval);
  }, []);

  const getActivityIcon = (type) => {
    switch (type) {
      case "file_upload": return "📤";
      case "file_delete": return "🗑️";
      case "chat_query": return "🔍";
      case "chat_session_start": return "💬";
      case "settings_update": return "⚙️";
      default: return "📋";
    }
  };

  const getActivityTitle = (activity) => {
    switch (activity.type) {
      case "file_upload":
        return `Uploaded "${activity.details.file_name}"`;
      case "file_delete":
        return `Deleted file "${activity.details.file_name}"`;
      case "chat_query":
        return `Knowledge base query`;
      case "chat_session_start":
        return `Chat session started`;
      case "settings_update":
        return `Settings updated`;
      default:
        return activity.type.replace(/_/g, " ").toUpperCase();
    }
  };

  const getActivityDescription = (activity) => {
    switch (activity.type) {
      case "file_upload":
        return `File size: ${(activity.details.file_size / 1024).toFixed(1)} KB, Type: ${activity.details.file_type.toUpperCase()}`;
      case "chat_query":
        return `Question: "${activity.details.question}..."`;
      case "chat_session_start":
        return `Started with: "${activity.details.first_question}..."`;
      default:
        return "";
    }
  };

  const formatTimeAgo = (timestamp) => {
    const now = new Date();
    const activityTime = new Date(timestamp);
    const diffMs = now - activityTime;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
  };

  const filteredActivities = filter === "all" 
    ? activities 
    : activities.filter(activity => activity.type === filter);

  return (
    <div className="activity-feed-container">
      <div className="activity-header">
        <div className="activity-title">
          <h2>📊 Activity Feed</h2>
          <p>Track all system activities and user interactions</p>
        </div>
        
        <div className="activity-stats">
          <div className="stat-card">
            <div className="stat-number">{stats.total_files_uploaded || 0}</div>
            <div className="stat-label">Files Uploaded</div>
          </div>
          <div className="stat-card">
            <div className="stat-number">{stats.total_chat_sessions || 0}</div>
            <div className="stat-label">Chat Sessions</div>
          </div>
          <div className="stat-card">
            <div className="stat-number">{stats.total_queries || 0}</div>
            <div className="stat-label">Total Queries</div>
          </div>
        </div>
      </div>

      <div className="activity-controls">
        <div className="filter-buttons">
          <button 
            className={`filter-btn ${filter === "all" ? "active" : ""}`}
            onClick={() => setFilter("all")}
          >
            All Activities
          </button>
          <button 
            className={`filter-btn ${filter === "file_upload" ? "active" : ""}`}
            onClick={() => setFilter("file_upload")}
          >
            📤 Uploads
          </button>
          <button 
            className={`filter-btn ${filter === "chat_query" ? "active" : ""}`}
            onClick={() => setFilter("chat_query")}
          >
            🔍 Queries
          </button>
          <button 
            className={`filter-btn ${filter === "chat_session_start" ? "active" : ""}`}
            onClick={() => setFilter("chat_session_start")}
          >
            💬 Sessions
          </button>
          <button 
            className={`filter-btn ${filter === "file_delete" ? "active" : ""}`}
            onClick={() => setFilter("file_delete")}
          >
            🗑️ Deletes
          </button>
        </div>
        
        <button onClick={loadActivities} className="refresh-btn" disabled={loading}>
          {loading ? "🔄" : "🔄"} Refresh
        </button>
      </div>

      {error && (
        <div className="error-message">
          <span className="error-icon">❌</span>
          {error}
        </div>
      )}

      <div className="activity-list">
        {loading ? (
          <div className="loading-state">
            <div className="loading-spinner"></div>
            <p>Loading activities...</p>
          </div>
        ) : filteredActivities.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📭</div>
            <h3>No activities found</h3>
            <p>Activities will appear here as users interact with the system</p>
          </div>
        ) : (
          filteredActivities.map((activity, index) => (
            <div key={activity.id} className="activity-item">
              <div className="activity-icon">
                {getActivityIcon(activity.type)}
              </div>
              
              <div className="activity-content">
                <div className="activity-header-item">
                  <h4 className="activity-title-text">
                    {getActivityTitle(activity)}
                  </h4>
                  <span className="activity-time">
                    {formatTimeAgo(activity.timestamp)}
                  </span>
                </div>
                
                <div className="activity-description">
                  {getActivityDescription(activity)}
                </div>
                
                <div className="activity-meta">
                  <span className="activity-user">
                    👤 {activity.user}
                  </span>
                  <span className="activity-type">
                    {activity.type.replace(/_/g, " ").toUpperCase()}
                  </span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
