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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">📊 Activity Feed</h2>
          <p className="text-gray-600">Track all system activities and user interactions</p>
        </div>
        <button
          onClick={loadActivities}
          className="btn btn-secondary"
          disabled={loading}
        >
          {loading ? (
            <>
              <div className="spinner mr-2"></div>
              Refreshing...
            </>
          ) : (
            <>
              <span className="mr-2">🔄</span>
              Refresh
            </>
          )}
        </button>
      </div>
      
      <div className="stats-grid">
        <div className="card group hover:scale-105 transition-transform duration-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 mb-1">Files Uploaded</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total_files_uploaded || 0}</p>
            </div>
            <div className="p-3 rounded-lg bg-primary-100 text-primary-600">
              <span className="text-2xl">📤</span>
            </div>
          </div>
        </div>
        <div className="card group hover:scale-105 transition-transform duration-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 mb-1">Chat Sessions</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total_chat_sessions || 0}</p>
            </div>
            <div className="p-3 rounded-lg bg-success-100 text-success-600">
              <span className="text-2xl">💬</span>
            </div>
          </div>
        </div>
        <div className="card group hover:scale-105 transition-transform duration-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 mb-1">Total Queries</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total_queries || 0}</p>
            </div>
            <div className="p-3 rounded-lg bg-warning-100 text-warning-600">
              <span className="text-2xl">🔍</span>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Filter Activities</h3>
        </div>
        <div className="flex flex-wrap gap-2">
          <button 
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
              filter === "all" 
                ? "bg-primary-600 text-white shadow-sm" 
                : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
            }`}
            onClick={() => setFilter("all")}
          >
            All Activities
          </button>
          <button 
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
              filter === "file_upload" 
                ? "bg-primary-600 text-white shadow-sm" 
                : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
            }`}
            onClick={() => setFilter("file_upload")}
          >
            📤 Uploads
          </button>
          <button 
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
              filter === "chat_query" 
                ? "bg-primary-600 text-white shadow-sm" 
                : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
            }`}
            onClick={() => setFilter("chat_query")}
          >
            🔍 Queries
          </button>
          <button 
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
              filter === "chat_session_start" 
                ? "bg-primary-600 text-white shadow-sm" 
                : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
            }`}
            onClick={() => setFilter("chat_session_start")}
          >
            💬 Sessions
          </button>
          <button 
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
              filter === "file_delete" 
                ? "bg-primary-600 text-white shadow-sm" 
                : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
            }`}
            onClick={() => setFilter("file_delete")}
          >
            🗑️ Deletes
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-error">
          <span className="alert-icon">❌</span>
          <span className="alert-message">{error}</span>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Recent Activities</h3>
        </div>
        <div className="space-y-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="spinner mr-3"></div>
              <span className="text-gray-600">Loading activities...</span>
            </div>
          ) : filteredActivities.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">📭</span>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">No activities found</h3>
              <p className="text-gray-600">Activities will appear here as users interact with the system</p>
            </div>
          ) : (
            filteredActivities.map((activity, index) => (
              <div key={activity.id} className="flex items-start space-x-4 p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors duration-200">
                <div className="flex-shrink-0 w-10 h-10 bg-white rounded-full flex items-center justify-center shadow-sm">
                  <span className="text-xl">{getActivityIcon(activity.type)}</span>
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between">
                    <h4 className="text-sm font-semibold text-gray-900">
                      {getActivityTitle(activity)}
                    </h4>
                    <span className="text-xs text-gray-500 ml-2">
                      {formatTimeAgo(activity.timestamp)}
                    </span>
                  </div>
                  
                  {getActivityDescription(activity) && (
                    <p className="text-sm text-gray-600 mt-1">
                      {getActivityDescription(activity)}
                    </p>
                  )}
                  
                  <div className="flex items-center space-x-4 mt-2">
                    <span className="text-xs text-gray-500">
                      👤 {activity.user}
                    </span>
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-200 text-gray-800">
                      {activity.type.replace(/_/g, " ").toUpperCase()}
                    </span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
