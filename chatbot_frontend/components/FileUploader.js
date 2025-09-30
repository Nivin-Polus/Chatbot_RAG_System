import React, { useState, useEffect, useMemo } from "react";
import api from "../api/api";

export default function FileUploader({
  collections = [],
  defaultCollectionId = null,
  onStatsChange = () => {},
  onCollectionChange = () => {},
  onFilesLoaded = () => {},
  onManageAccess = null,
  compact = false
}) {
  const [files, setFiles] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [collectionId, setCollectionId] = useState(defaultCollectionId);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [expandedFiles, setExpandedFiles] = useState(new Set());
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");

  const activeCollection = useMemo(() => {
    if (!collectionId) return null;
    return collections.find((col) => col.collection_id === collectionId) || null;
  }, [collectionId, collections]);

  useEffect(() => {
    if (defaultCollectionId && defaultCollectionId !== collectionId) {
      setCollectionId(defaultCollectionId);
      onCollectionChange(defaultCollectionId);
    }
    if (!defaultCollectionId && collectionId) {
      setCollectionId(null);
      onCollectionChange(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultCollectionId]);

  useEffect(() => {
    setSearchTerm("");
  }, [collectionId]);

  const loadFiles = async (options = { showErrors: true }) => {
    if (!collectionId) {
      setFiles([]);
      onFilesLoaded([]);
      onStatsChange({ total: 0 });
      return;
    }

    try {
      setIsRefreshing(true);
      const res = await api.get(`/files/list`, {
        params: { collection_id: collectionId }
      });
      const loaded = res.data || [];
      setFiles(loaded);
      setMessage("");
      onStatsChange({ total: loaded.length });
      onFilesLoaded(loaded);
    } catch (err) {
      console.error("Failed to load files:", err);
      if (!options.showErrors) return;
      if (err.response?.status === 401) {
        setMessage("Authentication required. Please log in again.");
      } else {
        setMessage("Failed to load files: " + (err.response?.data?.detail || err.message));
      }
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadFiles({ showErrors: false });
  }, [collectionId]);

  const handleUpload = async () => {
    if (!collectionId) {
      setMessage("Select a collection before uploading files.");
      return;
    }

    if (selectedFiles.length === 0) return;
    setLoading(true);

    let uploadedCount = 0;
    let failedCount = 0;

    for (const file of selectedFiles) {
      const formData = new FormData();
      formData.append("uploaded_file", file);
      formData.append("collection_id", collectionId);

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
    await loadFiles();
    setLoading(false);
  };

  const handleDelete = async (fileId) => {
    if (!collectionId) return;
    if (!window.confirm("Are you sure you want to delete this file?")) return;

    try {
      await api.delete(`/files/${fileId}`);
      setMessage("File deleted successfully");
      await loadFiles();
    } catch (err) {
      setMessage("Delete failed: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleDownload = async (fileId, fileName) => {
    try {
      const response = await api.get(`/files/download/${fileId}`, {
        responseType: 'blob'
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', fileName);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      setMessage("File downloaded successfully");
    } catch (err) {
      console.error("Download failed:", err);
      setMessage("Download failed: " + (err.response?.data?.detail || err.message));
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

  const handleRefresh = () => loadFiles();

  const handleCollectionSelect = (value) => {
    setCollectionId(value);
    onCollectionChange(value);
  };

  const filteredFiles = useMemo(() => {
    if (!searchTerm.trim()) return files;
    const term = searchTerm.trim().toLowerCase();
    return files.filter((file) => {
      const nameMatch = file.file_name?.toLowerCase().includes(term);
      const uploaderMatch = file.uploaded_by?.toLowerCase().includes(term);
      const sourceMatch = file.source?.toLowerCase().includes(term);
      return nameMatch || uploaderMatch || sourceMatch;
    });
  }, [files, searchTerm]);

  const renderCollectionPicker = () => {
    if (!collections || collections.length === 0) {
      return (
        <div className="collection-banner warning">
          <span>⚠️</span>
          <div>
            <h4>No collections available</h4>
            <p>Create a collection before uploading documents.</p>
          </div>
        </div>
      );
    }

    return (
      <div className="collection-selector">
        <label htmlFor="collection-picker">Collection</label>
        <select
          id="collection-picker"
          value={collectionId || ""}
          onChange={(e) => handleCollectionSelect(e.target.value || null)}
        >
          <option value="">Select a collection</option>
          {collections.map((collection) => (
            <option key={collection.collection_id} value={collection.collection_id}>
              {collection.name}
            </option>
          ))}
        </select>
        {activeCollection && (
          <div className="collection-summary">
            <span><strong>Admin:</strong> {activeCollection.admin_email || 'N/A'}</span>
            <span><strong>Website:</strong> {activeCollection.website_url || 'N/A'}</span>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={`modern-file-manager ${compact ? 'compact' : ''}`}>
      <div className="file-manager-header">
        <div>
          <h2>📁 Collection Documents</h2>
          <p>Upload, organize, and manage documents per collection.</p>
        </div>
        {collectionId && (
          <div className="header-stats">
            <span><strong>Collection ID:</strong> {collectionId}</span>
            <span><strong>Total Files:</strong> {files.length}</span>
          </div>
        )}
      </div>

      {renderCollectionPicker()}

      <div className="upload-card">
        <div className="upload-card-header">
          <h3>📤 Upload Documents</h3>
          <span className="upload-info">Supported: PDF, DOCX, PPTX, XLSX, TXT</span>
        </div>

        <div className="upload-card-content">
          <div className={`upload-dropzone-modern ${!collectionId ? 'disabled' : ''}`}>
            <input
              type="file"
              multiple
              onChange={e => setSelectedFiles(Array.from(e.target.files))}
              accept=".pdf,.docx,.pptx,.xlsx,.txt"
              className="file-input-hidden"
              id="file-upload"
              disabled={!collectionId}
            />
            <label htmlFor="file-upload" className="upload-label">
              <div className="upload-visual">
                <div className="upload-icon-large">📁</div>
                <h4>{collectionId ? 'Drop files here or click to browse' : 'Select a collection to enable uploads'}</h4>
                <p>{collectionId ? 'Select multiple files to upload to this collection.' : 'Choose a collection above to upload documents.'}</p>
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
                  disabled={loading || !collectionId}
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

      <div className="files-library-card">
        <div className="library-header">
          <div className="library-title">
            <h3>📚 Collection Document Library</h3>
            <span className="files-count">
              {searchTerm.trim() ? `${filteredFiles.length} of ${files.length} documents` : `${files.length} documents`}
            </span>
          </div>

          <div className="library-actions">
            <input
              type="text"
              className="search-input"
              placeholder="Search files..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
            <button onClick={handleRefresh} className="btn-refresh" disabled={!collectionId || isRefreshing}>
              <span className="btn-icon">🔄</span>
              {isRefreshing ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>

        {!collectionId ? (
          <div className="empty-state-modern">
            <div className="empty-illustration">🎯</div>
            <h3>Select a collection to view its documents</h3>
            <p>Choose a collection above to inspect its uploaded files.</p>
          </div>
        ) : files.length === 0 ? (
          <div className="empty-state-modern">
            <div className="empty-illustration">📭</div>
            <h3>No documents in this collection</h3>
            <p>Upload documents to make them available for retrieval.</p>
          </div>
        ) : filteredFiles.length === 0 ? (
          <div className="empty-state-modern">
            <div className="empty-illustration">🔍</div>
            <h3>No documents match your search</h3>
            <p>Try adjusting your keywords or clearing the search filter.</p>
          </div>
        ) : (
          <div className="files-grid">
            {filteredFiles.map(file => (
              <div key={file.file_id} className="file-card">
                <div className="file-card-header">
                  <div className="file-type-badge">📄</div>
                  <div className="file-actions-menu">
                    <button
                      onClick={() => handleDownload(file.file_id, file.file_name)}
                      className="action-btn-small download"
                      title="Download file"
                    >
                      📥
                    </button>
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
                      <span className="meta-icon">🆔</span>
                      {file.uploader_id || 'N/A'}
                    </span>
                    <span className="meta-item">
                      <span className="meta-icon">📅</span>
                      {file.upload_timestamp ? new Date(file.upload_timestamp).toLocaleString() : 'Unknown'}
                    </span>
                  </div>

                  <div className="file-status">
                    <span className={`status-indicator ${file.processing_status === 'completed' ? 'active' : 'pending'}`}></span>
                    <span className="status-text">{file.processing_status === 'completed' ? 'Indexed' : 'Processing'}</span>
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
                        <span className="detail-label">Collection ID:</span>
                        <span className="detail-value">{file.collection_id || 'N/A'}</span>
                      </div>
                      <div className="detail-row">
                        <span className="detail-label">Uploaded By:</span>
                        <span className="detail-value">{file.uploaded_by}</span>
                      </div>
                      <div className="detail-row">
                        <span className="detail-label">Uploader ID:</span>
                        <span className="detail-value">{file.uploader_id || 'N/A'}</span>
                      </div>
                      <div className="detail-row">
                        <span className="detail-label">Uploaded:</span>
                        <span className="detail-value">{file.upload_timestamp ? new Date(file.upload_timestamp).toLocaleString() : 'Unknown'}</span>
                      </div>

                      <div className="expanded-actions">
                        <button
                          onClick={() => handleDownload(file.file_id, file.file_name)}
                          className="btn-download-small"
                        >
                          <span className="btn-icon">📥</span>
                          Download Original File
                        </button>
                        {onManageAccess && (
                          <button
                            onClick={() => onManageAccess(file)}
                            className="btn-secondary-small"
                          >
                            <span className="btn-icon">🔐</span>
                            Manage Access
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete(file.file_id)}
                          className="btn-danger-small"
                        >
                          <span className="btn-icon">🗑️</span>
                          Remove from Collection
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
