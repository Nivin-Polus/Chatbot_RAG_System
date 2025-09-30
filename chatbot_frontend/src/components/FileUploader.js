import React, { useState, useEffect, useMemo, useCallback } from "react";
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

  const loadFiles = useCallback(async (options = { showErrors: true }) => {
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
      
      // Use setTimeout to prevent immediate re-renders
      setTimeout(() => {
        onStatsChange({ total: loaded.length });
        onFilesLoaded(loaded);
      }, 0);
    } catch (err) {
      console.error("Error loading files:", err);
      setFiles([]);
      setTimeout(() => {
        onFilesLoaded([]);
        onStatsChange({ total: 0 });
      }, 0);
      if (options.showErrors) {
        setMessage("Failed to load files: " + (err.response?.data?.detail || err.message));
      }
    } finally {
      setIsRefreshing(false);
    }
  }, [collectionId]);

  useEffect(() => {
    loadFiles({ showErrors: false });
  }, [collectionId]); // Only depend on collectionId, not loadFiles

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
        <div className="alert alert-warning">
          <span className="alert-icon">⚠️</span>
          <div>
            <h4 className="font-semibold">No collections available</h4>
            <p className="text-sm mt-1">Create a collection before uploading documents.</p>
          </div>
        </div>
      );
    }

    return (
      <div className="space-y-4">
        <div className="form-group">
          <label htmlFor="collection-picker" className="form-label">Collection</label>
          <select
            id="collection-picker"
            value={collectionId || ""}
            onChange={(e) => handleCollectionSelect(e.target.value || null)}
            className="form-select"
          >
            <option value="">Select a collection</option>
            {collections.map((collection) => (
              <option key={collection.collection_id} value={collection.collection_id}>
                {collection.name}
              </option>
            ))}
          </select>
        </div>
        {activeCollection && (
          <div className="bg-gray-50 rounded-lg p-4 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600 font-medium">Admin:</span>
              <span className="text-gray-900">{activeCollection.admin_email || 'N/A'}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600 font-medium">Website:</span>
              <span className="text-gray-900 truncate max-w-48">{activeCollection.website_url || 'N/A'}</span>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={`space-y-6 ${compact ? 'space-y-4' : ''}`}>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">📁 Collection Documents</h2>
          <p className="text-gray-600">Upload, organize, and manage documents per collection.</p>
        </div>
        {collectionId && (
          <div className="flex items-center space-x-4 text-sm text-gray-600">
            <span><strong>Collection ID:</strong> {collectionId}</span>
            <span><strong>Total Files:</strong> {files.length}</span>
          </div>
        )}
      </div>

      {renderCollectionPicker()}

      <div className="card">
        <div className="card-header">
          <h3 className="card-title">📤 Upload Documents</h3>
          <p className="card-subtitle">Supported: PDF, DOCX, PPTX, XLSX, TXT, CSV</p>
        </div>

        <div className="space-y-4">
          <div className={`border-2 border-dashed rounded-lg p-8 text-center transition-all duration-200 ${
            !collectionId 
              ? 'border-gray-300 bg-gray-50 cursor-not-allowed' 
              : 'border-primary-300 bg-primary-50 hover:border-primary-400 hover:bg-primary-100 cursor-pointer'
          }`}>
            <input
              type="file"
              multiple
              onChange={e => setSelectedFiles(Array.from(e.target.files))}
              accept=".pdf,.docx,.pptx,.xlsx,.txt,.csv"
              className="hidden"
              id="file-upload"
              disabled={!collectionId}
            />
            <label htmlFor="file-upload" className="cursor-pointer">
              <div className="space-y-4">
                <div className="text-6xl">📁</div>
                <div>
                  <h4 className="text-lg font-semibold text-gray-900">
                    {collectionId ? 'Drop files here or click to browse' : 'Select a collection to enable uploads'}
                  </h4>
                  <p className="text-gray-600 mt-2">
                    {collectionId ? 'Select multiple files to upload to this collection.' : 'Choose a collection above to upload documents.'}
                  </p>
                </div>
              </div>
            </label>
          </div>

          {selectedFiles.length > 0 && (
            <div className="bg-gray-50 rounded-lg p-4 space-y-4">
              <h4 className="text-lg font-semibold text-gray-900">📋 Selected Files ({selectedFiles.length})</h4>
              <div className="space-y-2">
                {selectedFiles.map((file, index) => (
                  <div key={index} className="flex items-center justify-between bg-white rounded-lg p-3 border border-gray-200">
                    <div className="flex items-center space-x-3">
                      <span className="text-xl">📄</span>
                      <span className="font-medium text-gray-900">{file.name}</span>
                    </div>
                    <span className="text-sm text-gray-500">{(file.size / 1024).toFixed(1)} KB</span>
                  </div>
                ))}
              </div>

              <div className="flex space-x-3">
                <button
                  onClick={handleUpload}
                  disabled={loading || !collectionId}
                  className="btn btn-primary flex-1"
                >
                  {loading ? (
                    <>
                      <div className="spinner mr-2"></div>
                      Uploading Files...
                    </>
                  ) : (
                    <>
                      <span className="mr-2">⬆️</span>
                      Upload {selectedFiles.length} Files
                    </>
                  )}
                </button>

                <button
                  onClick={() => setSelectedFiles([])}
                  className="btn btn-secondary"
                >
                  <span className="mr-2">🗑️</span>
                  Clear Selection
                </button>
              </div>
            </div>
          )}

          {message && (
            <div className={`alert ${message.includes("failed") ? "alert-error" : "alert-success"}`}>
              <span className="alert-icon">
                {message.includes("failed") ? "❌" : "✅"}
              </span>
              <span className="alert-message">{message}</span>
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="card-title">📚 Collection Document Library</h3>
              <p className="card-subtitle">
                {searchTerm.trim() ? `${filteredFiles.length} of ${files.length} documents` : `${files.length} documents`}
              </p>
            </div>
            <div className="flex items-center space-x-3">
              <input
                type="text"
                className="form-input w-64"
                placeholder="Search files..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
              <button 
                onClick={handleRefresh} 
                className="btn btn-secondary" 
                disabled={!collectionId || isRefreshing}
              >
                <span className="mr-2">🔄</span>
                {isRefreshing ? 'Refreshing...' : 'Refresh'}
              </button>
            </div>
          </div>
        </div>

        {!collectionId ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl">🎯</span>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Select a collection to view its documents</h3>
            <p className="text-gray-600">Choose a collection above to inspect its uploaded files.</p>
          </div>
        ) : files.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl">📭</span>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">No documents in this collection</h3>
            <p className="text-gray-600">Upload documents to make them available for retrieval.</p>
          </div>
        ) : filteredFiles.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl">🔍</span>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">No documents match your search</h3>
            <p className="text-gray-600">Try adjusting your keywords or clearing the search filter.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredFiles.map(file => (
              <div key={file.file_id} className="card group hover:shadow-medium transition-shadow duration-200">
                <div className="card-header">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="w-8 h-8 bg-primary-100 rounded-lg flex items-center justify-center">
                        <span className="text-primary-600 text-lg">📄</span>
                      </div>
                      <div>
                        <h4 className="card-title">{file.file_name}</h4>
                        <p className="card-subtitle">
                          {file.uploaded_by} • {file.upload_timestamp ? new Date(file.upload_timestamp).toLocaleDateString() : 'Unknown'}
                        </p>
                      </div>
                    </div>
                    <div className="flex space-x-1">
                      <button
                        onClick={() => handleDownload(file.file_id, file.file_name)}
                        className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-all duration-200"
                        title="Download file"
                      >
                        <span className="text-sm">📥</span>
                      </button>
                      <button
                        onClick={() => toggleExpanded(file.file_id)}
                        className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-all duration-200"
                        title="View details"
                      >
                        <span className="text-sm">{expandedFiles.has(file.file_id) ? '👁️' : '👁️‍🗨️'}</span>
                      </button>
                      <button
                        onClick={() => handleDelete(file.file_id)}
                        className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-error-600 hover:bg-error-50 rounded-lg transition-all duration-200"
                        title="Delete file"
                      >
                        <span className="text-sm">🗑️</span>
                      </button>
                    </div>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Status:</span>
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      file.processing_status === 'completed' 
                        ? 'bg-success-100 text-success-800' 
                        : 'bg-warning-100 text-warning-800'
                    }`}>
                      {file.processing_status === 'completed' ? 'Indexed' : 'Processing'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Uploader ID:</span>
                    <span className="font-medium">{file.uploader_id || 'N/A'}</span>
                  </div>
                </div>

                {expandedFiles.has(file.file_id) && (
                  <div className="border-t border-gray-200 pt-4 mt-4">
                    <div className="space-y-3">
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="text-gray-600 font-medium">File ID:</span>
                          <p className="text-gray-900 font-mono text-xs">{file.file_id}</p>
                        </div>
                        <div>
                          <span className="text-gray-600 font-medium">Collection ID:</span>
                          <p className="text-gray-900 font-mono text-xs">{file.collection_id || 'N/A'}</p>
                        </div>
                        <div>
                          <span className="text-gray-600 font-medium">Uploaded By:</span>
                          <p className="text-gray-900">{file.uploaded_by}</p>
                        </div>
                        <div>
                          <span className="text-gray-600 font-medium">Uploader ID:</span>
                          <p className="text-gray-900">{file.uploader_id || 'N/A'}</p>
                        </div>
                      </div>
                      <div className="text-sm">
                        <span className="text-gray-600 font-medium">Uploaded:</span>
                        <p className="text-gray-900">{file.upload_timestamp ? new Date(file.upload_timestamp).toLocaleString() : 'Unknown'}</p>
                      </div>

                      <div className="flex space-x-2 pt-3 border-t border-gray-100">
                        <button
                          onClick={() => handleDownload(file.file_id, file.file_name)}
                          className="btn btn-primary btn-sm"
                        >
                          <span className="mr-2">📥</span>
                          Download
                        </button>
                        {onManageAccess && (
                          <button
                            onClick={() => onManageAccess(file)}
                            className="btn btn-secondary btn-sm"
                          >
                            <span className="mr-2">🔐</span>
                            Manage Access
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete(file.file_id)}
                          className="btn btn-error btn-sm"
                        >
                          <span className="mr-2">🗑️</span>
                          Remove
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
