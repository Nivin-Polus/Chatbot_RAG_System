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
    <div className="file-uploader-fullwidth">
      {/* Compact Upload Section */}
      <div className="upload-section-compact">
        <div className="upload-row">
          <div className="upload-dropzone-inline">
            <div className="upload-content">
              <span className="upload-icon-small">📤</span>
              <span className="upload-text">Drop files here or click to browse</span>
              <input 
                type="file" 
                multiple
                onChange={e => setSelectedFiles(Array.from(e.target.files))} 
                accept=".pdf,.docx,.pptx,.xlsx,.txt"
                className="file-input-hidden"
              />
            </div>
          </div>
          
          {selectedFiles.length > 0 && (
            <div className="upload-actions">
              <span className="selected-count">{selectedFiles.length} files selected</span>
              <button 
                onClick={handleUpload} 
                disabled={loading}
                className="upload-btn-compact"
              >
                {loading ? (
                  <>
                    <span className="spinner-small"></span>
                    Uploading...
                  </>
                ) : (
                  <>
                    ⬆️ Upload Files
                  </>
                )}
              </button>
            </div>
          )}
          
          <button onClick={loadFiles} className="refresh-btn-compact">
            🔄 Refresh
          </button>
        </div>
        
        {message && (
          <div className={`message-compact ${message.includes("failed") ? "error" : "success"}`}>
            <span className="message-icon">
              {message.includes("failed") ? "❌" : "✅"}
            </span>
            {message}
          </div>
        )}
      </div>
      
      {/* Full Width Files Table */}
      <div className="files-table-container">
        <div className="files-table-header">
          <h3>📚 Document Library ({files.length} files)</h3>
        </div>
        
        {files.length === 0 ? (
          <div className="empty-state-table">
            <div className="empty-icon">📭</div>
            <h3>No documents uploaded yet</h3>
            <p>Upload your first document to get started with the knowledge base</p>
          </div>
        ) : (
          <div className="files-table-wrapper">
            <table className="files-table">
              <thead>
                <tr>
                  <th className="col-icon"></th>
                  <th className="col-name">Document Name</th>
                  <th className="col-uploader">Uploaded By</th>
                  <th className="col-date">Upload Date</th>
                  <th className="col-status">Status</th>
                  <th className="col-actions">Actions</th>
                </tr>
              </thead>
              <tbody>
                {files.map(file => (
                  <React.Fragment key={file.file_id}>
                    <tr className="file-row">
                      <td className="file-icon-cell">
                        <div className="file-type-icon">📄</div>
                      </td>
                      <td className="file-name-cell">
                        <div className="file-name-wrapper">
                          <span className="file-name-primary">{file.file_name}</span>
                          <span className="file-id-secondary">ID: {file.file_id}</span>
                        </div>
                      </td>
                      <td className="file-uploader-cell">{file.uploaded_by}</td>
                      <td className="file-date-cell">{new Date().toLocaleDateString()}</td>
                      <td className="file-status-cell">
                        <span className="status-badge-table">✅ Active</span>
                      </td>
                      <td className="file-actions-cell">
                        <div className="action-buttons">
                          <button 
                            onClick={() => toggleExpanded(file.file_id)}
                            className="btn-view"
                            title="View details"
                          >
                            {expandedFiles.has(file.file_id) ? '👁️ Hide' : '👁️ View'}
                          </button>
                          <button 
                            onClick={() => handleDelete(file.file_id)}
                            className="btn-delete"
                            title="Delete file"
                          >
                            🗑️ Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                    {expandedFiles.has(file.file_id) && (
                      <tr className="file-details-row">
                        <td colSpan="6">
                          <div className="file-details-expanded">
                            <div className="details-grid">
                              <div className="detail-group">
                                <label>File ID:</label>
                                <span>{file.file_id}</span>
                              </div>
                              <div className="detail-group">
                                <label>File Name:</label>
                                <span>{file.file_name}</span>
                              </div>
                              <div className="detail-group">
                                <label>Uploaded By:</label>
                                <span>{file.uploaded_by}</span>
                              </div>
                              <div className="detail-group">
                                <label>Upload Date:</label>
                                <span>{new Date().toLocaleDateString()}</span>
                              </div>
                              <div className="detail-group">
                                <label>Status:</label>
                                <span className="status-active">✅ Active in Knowledge Base</span>
                              </div>
                              <div className="detail-group">
                                <label>Actions:</label>
                                <div className="detail-actions">
                                  <button 
                                    onClick={() => handleDelete(file.file_id)}
                                    className="btn-delete-detail"
                                  >
                                    🗑️ Remove from Knowledge Base
                                  </button>
                                </div>
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
