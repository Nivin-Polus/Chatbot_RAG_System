import { useState, useEffect } from "react";
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
    } catch (err) {
      console.error("Failed to load files:", err);
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
    <div className="file-uploader">
      <h3>File Management</h3>
      <div className="upload-section">
        <input 
          type="file" 
          multiple
          onChange={e => setSelectedFiles(Array.from(e.target.files))} 
          accept=".pdf,.docx,.pptx,.xlsx,.txt"
        />
        <button onClick={handleUpload} disabled={selectedFiles.length === 0 || loading}>
          {loading ? `Uploading ${selectedFiles.length} files...` : `Upload ${selectedFiles.length} file(s)`}
        </button>
        {selectedFiles.length > 0 && (
          <div className="selected-files">
            <p>Selected files:</p>
            <ul>
              {selectedFiles.map((file, index) => (
                <li key={index}>{file.name}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      
      {message && <p className={message.includes("failed") ? "error" : "success"}>{message}</p>}
      
      <div className="files-list">
        <h4>Uploaded Files ({files.length})</h4>
        {files.length === 0 ? (
          <p>No files uploaded yet.</p>
        ) : (
          <div className="files-table">
            {files.map(file => (
              <div key={file.file_id} className="file-row">
                <div className="file-row-header" onClick={() => toggleExpanded(file.file_id)}>
                  <div className="file-info">
                    <span className="expand-icon">
                      {expandedFiles.has(file.file_id) ? '▼' : '▶'}
                    </span>
                    <span className="file-name">{file.file_name}</span>
                  </div>
                  <div className="file-actions">
                    <span className="file-meta">by {file.uploaded_by}</span>
                    <button 
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(file.file_id);
                      }}
                      className="delete-btn"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                {expandedFiles.has(file.file_id) && (
                  <div className="file-row-content">
                    <div className="file-details">
                      <p><strong>File ID:</strong> {file.file_id}</p>
                      <p><strong>Uploaded by:</strong> {file.uploaded_by}</p>
                      <p><strong>File Name:</strong> {file.file_name}</p>
                      <p><strong>Status:</strong> <span className="status-active">Active</span></p>
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
