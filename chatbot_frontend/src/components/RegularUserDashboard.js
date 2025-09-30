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
        <div className="card text-center py-12">
          <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl">📭</span>
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">No Files Available</h3>
          <p className="text-gray-600 mb-4">You don't have access to any files yet.</p>
          <p className="text-sm text-gray-500">Contact your administrator to get access to documents.</p>
        </div>
      );
    }

    const visibleFiles = activeCollectionId
      ? accessibleFiles.filter(file => String(file.collection_id) === String(activeCollectionId))
      : accessibleFiles;

    if (visibleFiles.length === 0) {
      return (
        <div className="card text-center py-12">
          <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl">📚</span>
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">No Files in This Collection</h3>
          <p className="text-gray-600 mb-4">You don't have access to files in this collection.</p>
          <p className="text-sm text-gray-500">Contact your administrator to request access.</p>
        </div>
      );
    }

    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {visibleFiles.map(fileAccess => (
          <div key={fileAccess.access_id} className="card group hover:shadow-medium transition-shadow duration-200">
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1 min-w-0">
                <h3 className="text-lg font-semibold text-gray-900 truncate">{fileAccess.file_name}</h3>
                <div className="flex flex-wrap gap-2 mt-2">
                  {fileAccess.can_read && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-success-100 text-success-800">
                      Read
                    </span>
                  )}
                  {fileAccess.can_download && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-800">
                      Download
                    </span>
                  )}
                </div>
              </div>
              {fileAccess.expires_at && new Date(fileAccess.expires_at) < new Date() && (
                <div className="flex-shrink-0">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-error-100 text-error-800">
                    ⚠️ Expired
                  </span>
                </div>
              )}
            </div>

            <div className="space-y-3 mb-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500">Size:</span>
                <span className="font-medium">{(fileAccess.file_size / 1024).toFixed(1)} KB</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500">Uploaded by:</span>
                <span className="font-medium truncate max-w-32">{fileAccess.uploader_name}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500">Access granted:</span>
                <span className="font-medium">{new Date(fileAccess.granted_at).toLocaleDateString()}</span>
              </div>
              {fileAccess.expires_at && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500">Expires:</span>
                  <span className="font-medium">{new Date(fileAccess.expires_at).toLocaleDateString()}</span>
                </div>
              )}
              {fileAccess.notes && (
                <div className="text-sm">
                  <span className="text-gray-500">Notes:</span>
                  <p className="text-gray-700 mt-1">{fileAccess.notes}</p>
                </div>
              )}
            </div>

            <div className="flex space-x-2">
              {fileAccess.can_download && (
                <button
                  className="btn btn-primary btn-sm flex-1"
                  onClick={() => downloadFile(fileAccess.file_id, fileAccess.file_name)}
                >
                  <span className="mr-2">📥</span>
                  Download
                </button>
              )}
              <button className="btn btn-secondary btn-sm flex-1">
                <span className="mr-2">💬</span>
                View in Chat
              </button>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const TabButton = ({ id, label, isActive, onClick }) => (
    <button
      className={`px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
        isActive
          ? 'bg-primary-600 text-white shadow-sm'
          : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
      }`}
      onClick={() => onClick(id)}
    >
      {label}
    </button>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-primary-600 rounded-lg flex items-center justify-center">
                <span className="text-white text-xl">💬</span>
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">My Chatbot</h1>
                <p className="text-sm text-gray-600">Knowledge Base Assistant</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-600">Welcome, {username}</span>
              <button 
                onClick={onLogout} 
                className="btn btn-secondary btn-sm"
              >
                <span className="mr-2">🚪</span>
                Logout
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex space-x-8">
            <TabButton id="chat" label="💬 Chat" isActive={activeTab === 'chat'} onClick={setActiveTab} />
            <TabButton id="files" label="📁 My Files" isActive={activeTab === 'files'} onClick={setActiveTab} />
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="spinner mr-3"></div>
            <span className="text-gray-600">Loading...</span>
          </div>
        )}

        {/* Chat Tab */}
        {activeTab === 'chat' && !loading && (
          <div className="space-y-6">
            <div className="card">
              <div className="flex items-start space-x-3">
                <div className="w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-primary-600 text-lg">💡</span>
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">AI Assistant Ready</h3>
                  <p className="text-gray-600">
                    You can ask questions about the documents you have access to. The AI will search through your accessible files to provide relevant answers.
                  </p>
                </div>
              </div>
            </div>

            {activeCollectionId ? (
              <ChatWindow
                collectionId={activeCollectionId}
                collections={collections}
              />
            ) : (
              <div className="card text-center py-12">
                <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <span className="text-2xl">📚</span>
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">No Collection Assigned</h3>
                <p className="text-gray-600 mb-4">
                  You have not been assigned to a collection yet. Please contact your administrator to get access to documents.
                </p>
                <button
                  onClick={() => window.location.reload()}
                  className="btn btn-primary"
                >
                  <span className="mr-2">🔄</span>
                  Refresh
                </button>
              </div>
            )}
          </div>
        )}

        {/* Accessible Files Tab */}
        {activeTab === 'files' && !loading && (
          <div className="space-y-8">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">Files You Can Access</h2>
              <p className="text-gray-600">View and download documents you have permission to access</p>
            </div>

            {renderAccessibleFiles()}

            <div className="card">
              <div className="card-header">
                <h3 className="card-title">How to Get More Access</h3>
                <p className="card-subtitle">Request additional file permissions</p>
              </div>
              <div className="space-y-4">
                <div className="bg-gray-50 rounded-lg p-4">
                  <h4 className="font-semibold text-gray-900 mb-3">To request access to more files:</h4>
                  <ol className="list-decimal list-inside space-y-2 text-sm text-gray-700">
                    <li>Contact your department administrator</li>
                    <li>Request access to specific files you need</li>
                    <li>Explain why you need access to those documents</li>
                  </ol>
                  <p className="mt-3 text-sm text-gray-600">
                    Your administrator can grant you read, download, or other permissions as needed.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default RegularUserDashboard;
