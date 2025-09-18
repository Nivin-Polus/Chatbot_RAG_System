import React, { useState, useEffect } from "react";
import api from "../api/api";

export default function FileUploader() {
  const [files, setFiles] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [expandedFiles, setExpandedFiles] = useState(new Set());

  const loadFiles = async () => {
    try {
      const res = await api.get("/files/list");
      setFiles(res.data);
      setMessage(""); // Clear any previous error messages
    } catch (err) {
      console.error("Failed to load files:", err);
      if (err.response?.status === 401) {
        setMessage("Authentication required. Please log in again.");
      } else {
        setMessage("Failed to load files: " + (err.response?.data?.detail || err.message));
      }
    }
  };

  useEffect(() => {
    loadFiles();
  }, []);

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;
    setLoading(true);
    
    let uploadedCount = 0;
    let failedCount = 0;
    
    for (const file of selectedFiles) {
      const formData = new FormData();
      formData.append("uploaded_file", file);
      
      try {
        await api.post("/files/upload", formData, {
          headers: { "Content-Type": "multipart/form-data" }
        });
        uploadedCount++;
      } catch (err) {
        console.error(`Failed to upload ${file.name}:`, err);
        if (err.response?.status === 401) {
          setMessage("Authentication expired. Please log in again.");
          setLoading(false);
          return;
        }
        failedCount++;
      }
    }
    
    setMessage(`Uploaded ${uploadedCount} files successfully${failedCount > 0 ? `, ${failedCount} failed` : ''}`);
    setSelectedFiles([]);
    loadFiles(); // Refresh file list
    setLoading(false);
  };

  const handleDelete = async (fileId) => {
    if (!window.confirm("Are you sure you want to delete this file?")) return;
    
    try {
      await api.delete(`/files/${fileId}`);
      setMessage("File deleted successfully");
      loadFiles(); // Refresh file list
    } catch (err) {
      setMessage("Delete failed: " + (err.response?.data?.detail || err.message));
    }
  };

  const toggleExpanded = (fileId) => {
    const newExpanded = new Set(expandedFiles);
    if (newExpanded.has(fileId)) {
      newExpanded.delete(fileId);
    } else {
      newExpanded.add(fileId);
    }
    setExpandedFiles(newExpanded);
  };

  return (
    <div className="modern-file-manager">
      <div className="file-manager-header">
        <h2>📁 File Management</h2>
        <p>Upload, organize, and manage your knowledge base documents</p>
      </div>

      {/* Modern Upload Card */}
      <div className="upload-card">
        <div className="upload-card-header">
          <h3>📤 Upload Documents</h3>
          <span className="upload-info">Supported: PDF, DOCX, PPTX, XLSX, TXT</span>
        </div>
        
        <div className="upload-card-content">
          <div className="upload-dropzone-modern">
            <input 
              type="file" 
              multiple
              onChange={e => setSelectedFiles(Array.from(e.target.files))} 
              accept=".pdf,.docx,.pptx,.xlsx,.txt"
              className="file-input-hidden"
              id="file-upload"
            />
            <label htmlFor="file-upload" className="upload-label">
              <div className="upload-visual">
                <div className="upload-icon-large">📁</div>
                <h4>Drop files here or click to browse</h4>
                <p>Select multiple files to upload to your knowledge base</p>
              </div>
            </label>
          </div>
          
          {selectedFiles.length > 0 && (
            <div className="selected-files-preview">
              <h4>📋 Selected Files ({selectedFiles.length})</h4>
              <div className="selected-files-list">
                {selectedFiles.map((file, index) => (
                  <div key={index} className="selected-file-item">
                    <span className="file-icon">📄</span>
                    <span className="file-name">{file.name}</span>
                    <span className="file-size">{(file.size / 1024).toFixed(1)} KB</span>
                  </div>
                ))}
              </div>
              
              <div className="upload-actions">
                <button 
                  onClick={handleUpload} 
                  disabled={loading}
                  className="btn-upload-primary"
                >
                  {loading ? (
                    <>
                      <span className="btn-spinner"></span>
                      Uploading Files...
                    </>
                  ) : (
                    <>
                      <span className="btn-icon">⬆️</span>
                      Upload {selectedFiles.length} Files
                    </>
                  )}
                </button>
                
                <button 
                  onClick={() => setSelectedFiles([])}
                  className="btn-clear"
                >
                  <span className="btn-icon">🗑️</span>
                  Clear Selection
                </button>
              </div>
            </div>
          )}
          
          {message && (
            <div className={`upload-alert ${message.includes("failed") ? "alert-error" : "alert-success"}`}>
              <span className="alert-icon">
                {message.includes("failed") ? "❌" : "✅"}
              </span>
              <span className="alert-message">{message}</span>
            </div>
          )}
        </div>
      </div>
      
      {/* Modern Files Library */}
      <div className="files-library-card">
        <div className="library-header">
          <div className="library-title">
            <h3>📚 Document Library</h3>
            <span className="files-count">{files.length} documents</span>
          </div>
          
          <div className="library-actions">
            <button onClick={loadFiles} className="btn-refresh">
              <span className="btn-icon">🔄</span>
              Refresh
            </button>
          </div>
        </div>
        
        {files.length === 0 ? (
          <div className="empty-state-modern">
            <div className="empty-illustration">📭</div>
            <h3>No documents in your library</h3>
            <p>Upload your first document to start building your knowledge base</p>
            <button 
              onClick={() => document.getElementById('file-upload').click()}
              className="btn-get-started"
            >
              <span className="btn-icon">📤</span>
              Upload Your First Document
            </button>
          </div>
        ) : (
          <div className="files-grid">
            {files.map(file => (
              <div key={file.file_id} className="file-card">
                <div className="file-card-header">
                  <div className="file-type-badge">📄</div>
                  <div className="file-actions-menu">
                    <button 
                      onClick={() => toggleExpanded(file.file_id)}
                      className="action-btn-small"
                      title="View details"
                    >
                      {expandedFiles.has(file.file_id) ? '👁️' : '👁️‍🗨️'}
                    </button>
                    <button 
                      onClick={() => handleDelete(file.file_id)}
                      className="action-btn-small delete"
                      title="Delete file"
                    >
                      🗑️
                    </button>
                  </div>
                </div>
                
                <div className="file-card-content">
                  <h4 className="file-title">{file.file_name}</h4>
                  <div className="file-meta">
                    <span className="meta-item">
                      <span className="meta-icon">👤</span>
                      {file.uploaded_by}
                    </span>
                    <span className="meta-item">
                      <span className="meta-icon">📅</span>
                      {new Date().toLocaleDateString()}
                    </span>
                  </div>
                  
                  <div className="file-status">
                    <span className="status-indicator active"></span>
                    <span className="status-text">Active in Knowledge Base</span>
                  </div>
                </div>
                
                {expandedFiles.has(file.file_id) && (
                  <div className="file-card-expanded">
                    <div className="expanded-content">
                      <div className="detail-row">
                        <span className="detail-label">File ID:</span>
                        <span className="detail-value">{file.file_id}</span>
                      </div>
                      <div className="detail-row">
                        <span className="detail-label">Full Name:</span>
                        <span className="detail-value">{file.file_name}</span>
                      </div>
                      <div className="detail-row">
                        <span className="detail-label">Uploaded By:</span>
                        <span className="detail-value">{file.uploaded_by}</span>
                      </div>
                      <div className="detail-row">
                        <span className="detail-label">Upload Date:</span>
                        <span className="detail-value">{new Date().toLocaleDateString()}</span>
                      </div>
                      
                      <div className="expanded-actions">
                        <button 
                          onClick={() => handleDelete(file.file_id)}
                          className="btn-danger-small"
                        >
                          <span className="btn-icon">🗑️</span>
                          Remove from Knowledge Base
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
