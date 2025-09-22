import { useState } from "react";
import api from "../api/api";

export default function AdminSettings() {
  const [passwordData, setPasswordData] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: ""
  });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
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

  const testBackendConnection = async () => {
    setLoading(true);
    setMessage('');
    setError('');
    
    try {
      console.log('Testing backend connection...');
      const response = await api.get('/health');
      console.log('Health check response:', response.data);
      setMessage(`✅ Backend connection successful! Status: ${response.data.status}`);
    } catch (error) {
      console.error('Backend connection test failed:', error);
      const errorMessage = error.message || 'Connection failed';
      
      if (error.code === 'ECONNREFUSED') {
        setError('❌ Backend server is not running on port 8000. Please start the backend server.');
      } else if (error.response?.status === 404) {
        setError('❌ Health endpoint not found. Backend may be running on different port.');
      } else {
        setError(`❌ Connection failed: ${errorMessage}`);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleResetFiles = async () => {
    if (!window.confirm('Are you sure you want to reset all files? This will permanently delete all uploaded documents and cannot be undone!')) {
      return;
    }

    setLoading(true);
    setMessage('');
    setError('');

    try {
      console.log('Attempting to reset files...');
      const response = await api.delete('/files/reset-all');
      console.log('Reset files response:', response.data);
      setMessage(`Successfully reset files. ${response.data.files_deleted} files deleted.`);
      // Refresh stats
      await loadPromptStats();
    } catch (error) {
      console.error('Reset files error:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to reset files';
      const statusCode = error.response?.status || 'Unknown';
      const fullUrl = error.config?.url || 'Unknown URL';
      
      setError(`Error ${statusCode}: ${errorMessage}`);
      setMessage(`Failed to reset files. URL: ${fullUrl}, Status: ${statusCode}`);
      
      // Additional debugging info
      if (error.code === 'ECONNREFUSED') {
        setError('Connection refused - Backend server may not be running on port 8000');
      } else if (error.response?.status === 404) {
        setError('Endpoint not found - Check if backend server is running and endpoint exists');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleResetEverything = async () => {
    if (!window.confirm('Are you absolutely sure you want to reset EVERYTHING? This will permanently delete:\n\n• All uploaded files\n• All vector embeddings\n• All activity logs\n• All cache data\n\nThis action CANNOT be undone!')) {
      return;
    }

    setLoading(true);
    setMessage('');
    setError('');

    try {
      console.log('Attempting to reset everything...');
      
      // Reset files first
      console.log('Step 1: Resetting files...');
      const filesResponse = await api.delete('/files/reset-all');
      console.log('Files reset response:', filesResponse.data);
      
      // Then reset everything else
      console.log('Step 2: Resetting system...');
      const systemResponse = await api.delete('/activity/reset-all');
      console.log('System reset response:', systemResponse.data);
      
      setMessage(`System reset completed successfully!\n\nFiles deleted: ${filesResponse.data.files_deleted}\nSystem components cleared: ${systemResponse.data.cleared.join(', ')}`);
      
      // Refresh stats
      await loadPromptStats();
    } catch (error) {
      console.error('Reset everything error:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to reset system';
      const statusCode = error.response?.status || 'Unknown';
      const fullUrl = error.config?.url || 'Unknown URL';
      
      setError(`Error ${statusCode}: ${errorMessage}`);
      setMessage(`Failed to reset system. URL: ${fullUrl}, Status: ${statusCode}`);
      
      // Additional debugging info
      if (error.code === 'ECONNREFUSED') {
        setError('Connection refused - Backend server may not be running on port 8000');
      } else if (error.response?.status === 404) {
        setError('Endpoint not found - Check if backend server is running and endpoint exists');
      }
    } finally {
      setLoading(false);
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
            
            {error && (
              <div className="alert alert-error">
                <span className="alert-icon">❌</span>
                <span className="alert-message">{error}</span>
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
              <button onClick={testBackendConnection} className="btn-secondary" disabled={loading}>
                <span className="btn-icon">🔗</span>
                {loading ? "Testing..." : "Test Backend Connection"}
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

        {/* System Reset Card */}
        <div className="settings-card danger-card">
          <div className="card-header">
            <div className="card-title">
              <span className="card-icon">⚠️</span>
              <h3>System Reset</h3>
            </div>
            <span className="card-badge danger">Danger Zone</span>
          </div>
          
          <div className="card-content">
            <div className="reset-section">
              <div className="reset-warning">
                <div className="warning-icon">🚨</div>
                <div className="warning-content">
                  <h4>Warning: This will permanently delete data!</h4>
                  <p>These actions cannot be undone. Use with extreme caution.</p>
                </div>
              </div>
              
              <div className="reset-actions">
                <button 
                  className="btn-danger"
                  onClick={() => handleResetFiles()}
                  disabled={loading}
                >
                  {loading ? "🔄 Resetting..." : "🗑️ Reset All Files"}
                </button>
                
                <button 
                  className="btn-danger"
                  onClick={() => handleResetEverything()}
                  disabled={loading}
                >
                  {loading ? "🔄 Resetting..." : "💥 Reset Everything"}
                </button>
              </div>
              
              <div className="reset-info">
                <div className="info-item">
                  <strong>Reset All Files:</strong> Deletes all uploaded documents and their vector embeddings
                </div>
                <div className="info-item">
                  <strong>Reset Everything:</strong> Clears all data including activities, cache, and vector database
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
