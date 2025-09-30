import React, { useState, useEffect } from 'react';
import api from '../api/api';
import ChatWindow from './ChatWindow';

const RegularUserDashboard = ({ onLogout }) => {
  const [activeTab, setActiveTab] = useState('chat');
  const [accessibleFiles, setAccessibleFiles] = useState([]);
  const [collections, setCollections] = useState([]);
  const [activeCollectionId, setActiveCollectionId] = useState(null);
  const [loading, setLoading] = useState(false);

  const username = localStorage.getItem('username');

  useEffect(() => {
    const initialize = async () => {
      setLoading(true);
      try {
        await loadCollections();
        await loadAccessibleFiles();
      } catch (error) {
        console.error('Error initializing dashboard:', error);
      } finally {
        setLoading(false);
      }
    };

    initialize();
  }, []);

  const loadCollections = async () => {
    try {
      const res = await api.get('/collections/');
      const allowedCollections = Array.isArray(res.data) ? res.data : [];
      setCollections(allowedCollections);

      if (allowedCollections.length > 0) {
        setActiveCollectionId((prev) => {
          if (prev && allowedCollections.some(col => String(col.collection_id) === String(prev))) {
            return prev;
          }
          return allowedCollections[0].collection_id;
        });
      } else {
        setActiveCollectionId(null);
      }
    } catch (error) {
      console.error('Error loading collections:', error);
      setCollections([]);
      setActiveCollectionId(null);
    }
  };

  const loadAccessibleFiles = async () => {
    try {
      const res = await api.get('/users/me/accessible-files');
      setAccessibleFiles(res.data);
    } catch (error) {
      console.error('Error loading accessible files:', error);
    }
  };

  const downloadFile = async (fileId, fileName) => {
    try {
      const response = await api.get(`/files/download/${fileId}`, {
        responseType: 'blob'
      });
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', fileName);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      alert('Error downloading file: ' + (error.response?.data?.detail || error.message));
    }
  };

  const renderAccessibleFiles = () => {
    if (accessibleFiles.length === 0) {
      return (
        <div className="no-files">
          <p>You don't have access to any files yet.</p>
          <p>Contact your administrator to get access to documents.</p>
        </div>
      );
    }

    const visibleFiles = activeCollectionId
      ? accessibleFiles.filter(file => String(file.collection_id) === String(activeCollectionId))
      : accessibleFiles;

    if (visibleFiles.length === 0) {
      return (
        <div className="no-files">
          <p>You don't have access to files in this collection.</p>
          <p>Contact your administrator to request access.</p>
        </div>
      );
    }

    return (
      <div className="files-grid">
        {visibleFiles.map(fileAccess => (
          <div key={fileAccess.access_id} className="file-card">
            <div className="file-header">
              <h3>{fileAccess.file_name}</h3>
              <div className="permissions">
                {fileAccess.can_read && <span className="perm read">Read</span>}
                {fileAccess.can_download && <span className="perm download">Download</span>}
              </div>
            </div>

            <div className="file-info">
              <p><strong>Size:</strong> {(fileAccess.file_size / 1024).toFixed(1)} KB</p>
              <p><strong>Uploaded by:</strong> {fileAccess.uploader_name}</p>
              <p><strong>Access granted:</strong> {new Date(fileAccess.granted_at).toLocaleDateString()}</p>
              {fileAccess.expires_at && (
                <p><strong>Expires:</strong> {new Date(fileAccess.expires_at).toLocaleDateString()}</p>
              )}
              {fileAccess.notes && (
                <p><strong>Notes:</strong> {fileAccess.notes}</p>
              )}
            </div>

            <div className="file-actions">
              {fileAccess.can_download && (
                <button
                  className="download-btn"
                  onClick={() => downloadFile(fileAccess.file_id, fileAccess.file_name)}
                >
                  Download
                </button>
              )}
              <button className="view-btn">View in Chat</button>
            </div>

            {fileAccess.expires_at && new Date(fileAccess.expires_at) < new Date() && (
              <div className="expired-notice">
                ⚠️ Access has expired
              </div>
            )}
          </div>
        ))}
      </div>
    );
  };

  const TabButton = ({ id, label, isActive, onClick }) => (
    <button
      className={`tab-button ${isActive ? 'active' : ''}`}
      onClick={() => onClick(id)}
    >
      {label}
    </button>
  );

  return (
    <div className="regular-user-dashboard">
      <div className="dashboard-header">
        <h1>💬 My Chatbot</h1>
        <div className="header-actions">
          <span className="user-info">Welcome, {username}</span>
          <button onClick={onLogout} className="logout-btn">Logout</button>
        </div>
      </div>

      <div className="dashboard-tabs">
        <TabButton id="chat" label="💬 Chat" isActive={activeTab === 'chat'} onClick={setActiveTab} />
        <TabButton id="files" label="📁 My Files" isActive={activeTab === 'files'} onClick={setActiveTab} />
      </div>

      <div className="dashboard-content">
        {loading && <div className="loading">Loading...</div>}

        {/* Chat Tab */}
        {activeTab === 'chat' && (
          <div className="chat-tab">
            <div className="chat-info">
              <p>💡 You can ask questions about the documents you have access to. The AI will search through your accessible files to provide relevant answers.</p>
            </div>
            {activeCollectionId ? (
              <ChatWindow
                collectionId={activeCollectionId}
                collections={collections}
              />
            ) : (
              <div className="no-collection">
                <p>You have not been assigned to a collection yet. Please contact your administrator.</p>
              </div>
            )}
          </div>
        )}

        {/* Accessible Files Tab */}
        {activeTab === 'files' && (
          <div className="files-tab">
            <div className="section">
              <h2>Files You Can Access</h2>
              {renderAccessibleFiles()}
            </div>

            <div className="section">
              <h2>How to Get More Access</h2>
              <div className="help-info">
                <ol>
                  <li>Contact your department administrator</li>
                  <li>Request access to specific files you need</li>
                  <li>Explain why you need access to those documents</li>
                </ol>
                <p>Your administrator can grant you read, download, or other permissions as needed.</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default RegularUserDashboard;
