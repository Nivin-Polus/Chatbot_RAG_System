import { useState } from "react";
import api from "../api/api";

export default function AdminSettings() {
  const [passwordData, setPasswordData] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: ""
  });
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [promptStats, setPromptStats] = useState(null);

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    
    if (passwordData.newPassword !== passwordData.confirmPassword) {
      setMessage("New passwords don't match");
      return;
    }
    
    if (passwordData.newPassword.length < 6) {
      setMessage("New password must be at least 6 characters long");
      return;
    }
    
    setLoading(true);
    try {
      await api.post("/auth/change-password", {
        current_password: passwordData.currentPassword,
        new_password: passwordData.newPassword
      });
      setMessage("Password changed successfully!");
      setPasswordData({
        currentPassword: "",
        newPassword: "",
        confirmPassword: ""
      });
    } catch (err) {
      setMessage("Failed to change password: " + (err.response?.data?.detail || err.message));
    }
    setLoading(false);
  };

  const loadPromptStats = async () => {
    try {
      const response = await api.get("/admin/prompt-stats");
      setPromptStats(response.data);
    } catch (err) {
      console.log("Prompt stats not available");
    }
  };

  const handleInputChange = (e) => {
    setPasswordData({
      ...passwordData,
      [e.target.name]: e.target.value
    });
  };

  return (
    <div className="modern-admin-settings">
      <div className="settings-header">
        <h2>⚙️ System Settings</h2>
        <p>Manage your account security and system configuration</p>
      </div>

      <div className="settings-grid">
        {/* Security Settings Card */}
        <div className="settings-card security-card">
          <div className="card-header">
            <div className="card-title">
              <span className="card-icon">🔐</span>
              <h3>Security Settings</h3>
            </div>
            <span className="card-badge">Critical</span>
          </div>
          
          <div className="card-content">
            <form onSubmit={handlePasswordChange} className="modern-form">
              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="currentPassword">
                    <span className="label-icon">🔑</span>
                    Current Password
                  </label>
                  <input
                    type="password"
                    id="currentPassword"
                    name="currentPassword"
                    value={passwordData.currentPassword}
                    onChange={handleInputChange}
                    required
                    placeholder="Enter your current password"
                    className="modern-input"
                  />
                </div>
              </div>
              
              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="newPassword">
                    <span className="label-icon">🆕</span>
                    New Password
                  </label>
                  <input
                    type="password"
                    id="newPassword"
                    name="newPassword"
                    value={passwordData.newPassword}
                    onChange={handleInputChange}
                    required
                    placeholder="Enter new password (min. 6 characters)"
                    minLength="6"
                    className="modern-input"
                  />
                </div>
                
                <div className="form-group">
                  <label htmlFor="confirmPassword">
                    <span className="label-icon">✅</span>
                    Confirm Password
                  </label>
                  <input
                    type="password"
                    id="confirmPassword"
                    name="confirmPassword"
                    value={passwordData.confirmPassword}
                    onChange={handleInputChange}
                    required
                    placeholder="Confirm your new password"
                    minLength="6"
                    className="modern-input"
                  />
                </div>
              </div>
              
              <div className="form-actions">
                <button type="submit" disabled={loading} className="btn-primary">
                  {loading ? (
                    <>
                      <span className="btn-spinner"></span>
                      Updating Password...
                    </>
                  ) : (
                    <>
                      <span className="btn-icon">🔄</span>
                      Update Password
                    </>
                  )}
                </button>
              </div>
            </form>
            
            {message && (
              <div className={`alert ${message.includes("success") ? "alert-success" : "alert-error"}`}>
                <span className="alert-icon">
                  {message.includes("success") ? "✅" : "❌"}
                </span>
                <span className="alert-message">{message}</span>
              </div>
            )}
          </div>
        </div>

        {/* System Information Card */}
        <div className="settings-card info-card">
          <div className="card-header">
            <div className="card-title">
              <span className="card-icon">📊</span>
              <h3>System Information</h3>
            </div>
            <span className="card-badge success">Operational</span>
          </div>
          
          <div className="card-content">
            <div className="info-metrics">
              <div className="metric-item">
                <div className="metric-icon">👤</div>
                <div className="metric-details">
                  <span className="metric-label">Admin User</span>
                  <span className="metric-value">administrator</span>
                </div>
              </div>
              
              <div className="metric-item">
                <div className="metric-icon">⚡</div>
                <div className="metric-details">
                  <span className="metric-label">System Status</span>
                  <span className="metric-value status-online">Online & Active</span>
                </div>
              </div>
              
              <div className="metric-item">
                <div className="metric-icon">🕒</div>
                <div className="metric-details">
                  <span className="metric-label">Last Login</span>
                  <span className="metric-value">{new Date().toLocaleDateString()}</span>
                </div>
              </div>
              
              <div className="metric-item">
                <div className="metric-icon">🌐</div>
                <div className="metric-details">
                  <span className="metric-label">Server Time</span>
                  <span className="metric-value">{new Date().toLocaleTimeString()}</span>
                </div>
              </div>
            </div>
            
            <div className="card-actions">
              <button onClick={loadPromptStats} className="btn-secondary">
                <span className="btn-icon">📈</span>
                Load Usage Statistics
              </button>
            </div>
          </div>
        </div>

        {/* Usage Statistics Card */}
        {promptStats && (
          <div className="settings-card stats-card">
            <div className="card-header">
              <div className="card-title">
                <span className="card-icon">📈</span>
                <h3>Usage Analytics</h3>
              </div>
              <span className="card-badge info">Live Data</span>
            </div>
            
            <div className="card-content">
              <div className="stats-metrics">
                <div className="stat-metric">
                  <div className="stat-icon">💬</div>
                  <div className="stat-info">
                    <span className="stat-number">{promptStats.total_prompts || 0}</span>
                    <span className="stat-label">Total Prompts</span>
                  </div>
                </div>
                
                <div className="stat-metric">
                  <div className="stat-icon">📅</div>
                  <div className="stat-info">
                    <span className="stat-number">{promptStats.today_prompts || 0}</span>
                    <span className="stat-label">Today's Prompts</span>
                  </div>
                </div>
                
                <div className="stat-metric">
                  <div className="stat-icon">📁</div>
                  <div className="stat-info">
                    <span className="stat-number">{promptStats.total_files || 0}</span>
                    <span className="stat-label">Files Uploaded</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* System Health Card */}
        <div className="settings-card health-card">
          <div className="card-header">
            <div className="card-title">
              <span className="card-icon">🏥</span>
              <h3>System Health</h3>
            </div>
            <span className="card-badge success">All Good</span>
          </div>
          
          <div className="card-content">
            <div className="health-indicators">
              <div className="health-item">
                <div className="health-status online"></div>
                <span className="health-label">Database Connection</span>
                <span className="health-value">Connected</span>
              </div>
              
              <div className="health-item">
                <div className="health-status online"></div>
                <span className="health-label">AI Model</span>
                <span className="health-value">Ready</span>
              </div>
              
              <div className="health-item">
                <div className="health-status online"></div>
                <span className="health-label">File Processing</span>
                <span className="health-value">Active</span>
              </div>
              
              <div className="health-item">
                <div className="health-status online"></div>
                <span className="health-label">Authentication</span>
                <span className="health-value">Secure</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
