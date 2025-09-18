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
    <div className="admin-settings">
      <div className="settings-section">
        <h3>Security Settings</h3>
        <div className="settings-card">
          <h4>Change Password</h4>
          <form onSubmit={handlePasswordChange} className="password-form">
            <div className="form-group">
              <label htmlFor="currentPassword">Current Password</label>
              <input
                type="password"
                id="currentPassword"
                name="currentPassword"
                value={passwordData.currentPassword}
                onChange={handleInputChange}
                required
                placeholder="Enter current password"
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="newPassword">New Password</label>
              <input
                type="password"
                id="newPassword"
                name="newPassword"
                value={passwordData.newPassword}
                onChange={handleInputChange}
                required
                placeholder="Enter new password"
                minLength="6"
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="confirmPassword">Confirm New Password</label>
              <input
                type="password"
                id="confirmPassword"
                name="confirmPassword"
                value={passwordData.confirmPassword}
                onChange={handleInputChange}
                required
                placeholder="Confirm new password"
                minLength="6"
              />
            </div>
            
            <button type="submit" disabled={loading} className="change-password-btn">
              {loading ? "Changing..." : "Change Password"}
            </button>
          </form>
          
          {message && (
            <div className={`message ${message.includes("success") ? "success" : "error"}`}>
              {message}
            </div>
          )}
        </div>
      </div>

      <div className="settings-section">
        <h3>System Information</h3>
        <div className="settings-card">
          <div className="info-grid">
            <div className="info-item">
              <span className="info-label">Admin User:</span>
              <span className="info-value">admin</span>
            </div>
            <div className="info-item">
              <span className="info-label">System Status:</span>
              <span className="info-value status-active">Active</span>
            </div>
            <div className="info-item">
              <span className="info-label">Last Login:</span>
              <span className="info-value">{new Date().toLocaleDateString()}</span>
            </div>
          </div>
          
          <button onClick={loadPromptStats} className="load-stats-btn">
            Load Usage Statistics
          </button>
          
          {promptStats && (
            <div className="prompt-stats">
              <h4>Usage Statistics</h4>
              <div className="stats-grid">
                <div className="stat-item">
                  <span className="stat-value">{promptStats.total_prompts || 0}</span>
                  <span className="stat-label">Total Prompts</span>
                </div>
                <div className="stat-item">
                  <span className="stat-value">{promptStats.today_prompts || 0}</span>
                  <span className="stat-label">Today's Prompts</span>
                </div>
                <div className="stat-item">
                  <span className="stat-value">{promptStats.total_files || 0}</span>
                  <span className="stat-label">Files Uploaded</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
