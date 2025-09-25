import React, { useState, useEffect, useRef } from 'react';
import api from '../api/api';
import FileUploader from './FileUploader';
import ChatWindow from './ChatWindow';

const UserAdminDashboard = ({ onLogout }) => {
  const [activeTab, setActiveTab] = useState('files');
  const [files, setFiles] = useState([]);
  const [users, setUsers] = useState([]);
  const [website, setWebsite] = useState(null);
  const [loading, setLoading] = useState(false);
  const [collections, setCollections] = useState([]);
  const [selectedCollectionId, setSelectedCollectionId] = useState(null);
  const [prompts, setPrompts] = useState([]);
  const [promptLoading, setPromptLoading] = useState(false);
  const [promptError, setPromptError] = useState(null);
  const getDefaultPromptForm = () => ({
    name: '',
    description: '',
    system_prompt: '',
    user_prompt_template: '',
    context_template: '',
    model_name: 'claude-3-haiku-20240307',
    max_tokens: 4000,
    temperature: 0.7,
    is_active: true,
    is_default: false
  });
  const [promptDialogOpen, setPromptDialogOpen] = useState(false);
  const [promptDialogMode, setPromptDialogMode] = useState('view');
  const [promptForm, setPromptForm] = useState(getDefaultPromptForm());
  const [activePrompt, setActivePrompt] = useState(null);
  const [promptSubmitting, setPromptSubmitting] = useState(false);
  const currentUserIdRef = useRef(localStorage.getItem('user_id'));
  const [passwordDialog, setPasswordDialog] = useState({ open: false, user: null });
  const [passwordForm, setPasswordForm] = useState({ new_password: '', confirm_password: '' });

  // User Management
  const [newUser, setNewUser] = useState({
    username: '',
    password: '',
    email: '',
    full_name: '',
    role: 'user'
  });

  // File Access Management
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileAccessUsers, setFileAccessUsers] = useState([]);
  const [newFileAccess, setNewFileAccess] = useState({
    user_id: '',
    can_read: true,
    can_download: false,
    can_delete: false,
    expires_at: ''
  });

  const websiteId = localStorage.getItem('website_id');
  const username = localStorage.getItem('username');

  const handleDeleteUser = async (user) => {
    if (!user || !user.user_id) {
      return;
    }

    if (user.role === 'super_admin') {
      alert('Super admin accounts cannot be deleted.');
      return;
    }

    if (currentUserIdRef.current && String(currentUserIdRef.current) === String(user.user_id)) {
      alert('You cannot delete the account you are currently using.');
      return;
    }

    if (!window.confirm(`Are you sure you want to delete the user "${user.username}"?`)) {
      return;
    }

    try {
      await api.delete(`/users/${user.user_id}`);
      alert('User deleted successfully!');
      await loadUsers(selectedCollectionId);
    } catch (error) {
      alert('Error deleting user: ' + (error.response?.data?.detail || error.message));
    }
  };

  const openPasswordDialog = (user) => {
    if (!user) return;
    setPasswordForm({ new_password: '', confirm_password: '' });
    setPasswordDialog({ open: true, user });
  };

  const closePasswordDialog = () => {
    setPasswordDialog({ open: false, user: null });
  };

  const handleResetPassword = async () => {
    const { new_password, confirm_password } = passwordForm;
    const targetUser = passwordDialog.user;

    if (!targetUser) return;

    if (!new_password || new_password.length < 6) {
      alert('New password must be at least 6 characters long.');
      return;
    }

    if (new_password !== confirm_password) {
      alert('Passwords do not match.');
      return;
    }

    try {
      await api.post('/users/reset-password', {
        user_id: targetUser.user_id,
        new_password
      });
      alert('Password reset successfully!');
      closePasswordDialog();
    } catch (error) {
      alert('Error resetting password: ' + (error.response?.data?.detail || error.message));
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        if (activeTab === 'files') {
          await loadCollections();
        } else if (activeTab === 'prompts') {
          await loadCollections();
          if (selectedCollectionId) {
            await loadPrompts(selectedCollectionId);
          }
        } else if (activeTab === 'users') {
          const collectionsData = await loadCollections();
          const effectiveCollectionId = selectedCollectionId || collectionsData[0]?.collection_id;
          if (effectiveCollectionId) {
            await loadUsers(effectiveCollectionId);
          } else {
            setUsers([]);
          }
        } else if (activeTab === 'website') {
          await loadWebsite();
        }
      } catch (error) {
        console.error('Error loading data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [activeTab, selectedCollectionId]);

  const loadCollections = async () => {
    const params = websiteId ? { website_id: websiteId } : {};
    const res = await api.get('/collections/', { params });
    const filtered = res.data.filter(col => !websiteId || String(col.website_id) === String(websiteId));
    setCollections(filtered);

    if (filtered.length === 0) {
      if (selectedCollectionId !== null) {
        setSelectedCollectionId(null);
      }
    } else if (!selectedCollectionId || !filtered.some(col => String(col.collection_id) === String(selectedCollectionId))) {
      setSelectedCollectionId(filtered[0].collection_id);
    }

    return filtered;
  };

  const loadPrompts = async (collectionId) => {
    if (!collectionId) {
      setPrompts([]);
      return;
    }

    setPromptLoading(true);
    setPromptError(null);

    try {
      const collection = collections.find(col => String(col.collection_id) === String(collectionId));
      const params = { collection_id: collectionId };
      if (collection?.vector_db_id) {
        params.vector_db_id = collection.vector_db_id;
      }

      const res = await api.get('/prompts/', { params });
      const filteredPrompts = res.data.filter(prompt => String(prompt.collection_id) === String(collectionId));
      setPrompts(filteredPrompts);
    } catch (error) {
      console.error('Error loading prompts:', error);
      setPromptError(error.response?.data?.detail || error.message);
    } finally {
      setPromptLoading(false);
    }
  };

  const loadUsers = async (collectionIdParam) => {
    const targetCollectionId = collectionIdParam || selectedCollectionId;

    if (!targetCollectionId) {
      setUsers([]);
      return;
    }

    const params = { collection_id: targetCollectionId };
    if (websiteId) {
      params.website_id = websiteId;
    }

    const res = await api.get('/users/', { params });
    setUsers(res.data);
  };

  const loadWebsite = async () => {
    if (!websiteId) {
      setWebsite(null);
      return;
    }

    const res = await api.get(`/websites/${websiteId}`);
    setWebsite(res.data);
  };

  const openPromptDialog = (prompt) => {
    if (!prompt) return;
    setActivePrompt(prompt);
    setPromptDialogMode('edit');
    setPromptForm({
      name: prompt.name || '',
      description: prompt.description || '',
      system_prompt: prompt.system_prompt || '',
      user_prompt_template: prompt.user_prompt_template || '',
      context_template: prompt.context_template || '',
      model_name: prompt.model_name || 'claude-3-haiku-20240307',
      max_tokens: prompt.max_tokens ?? 4000,
      temperature: prompt.temperature ?? 0.7,
      is_active: prompt.is_active !== false,
      is_default: prompt.is_default === true
    });
    setPromptDialogOpen(true);
  };

  const closePromptDialog = () => {
    setPromptDialogOpen(false);
    setPromptDialogMode('view');
    setActivePrompt(null);
    setPromptSubmitting(false);
    setPromptForm(getDefaultPromptForm());
  };

  const handlePromptFieldChange = (field, value) => {
    setPromptForm(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const sanitizePromptPayload = () => {
    const payload = {
      ...promptForm,
      collection_id: selectedCollectionId,
      max_tokens: Number(promptForm.max_tokens),
      temperature: Number(promptForm.temperature)
    };

    if (!payload.description) delete payload.description;
    if (!payload.user_prompt_template) delete payload.user_prompt_template;
    if (!payload.context_template) delete payload.context_template;

    if (Number.isNaN(payload.max_tokens)) {
      throw new Error('Maximum tokens must be a valid number');
    }

    if (Number.isNaN(payload.temperature)) {
      throw new Error('Temperature must be a valid number');
    }

    return payload;
  };

  const handlePromptSubmit = async (e) => {
    e.preventDefault();
    if (!activePrompt) return;

    try {
      setPromptSubmitting(true);
      const payload = sanitizePromptPayload();
      await api.put(`/prompts/${activePrompt.prompt_id}`, payload);
      alert('Prompt updated successfully!');
      closePromptDialog();
      if (selectedCollectionId) {
        await loadPrompts(selectedCollectionId);
      }
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      alert('Error updating prompt: ' + detail);
    } finally {
      setPromptSubmitting(false);
    }
  };

  const handleTogglePromptActive = async (prompt) => {
    try {
      await api.put(`/prompts/${prompt.prompt_id}`, { is_active: !prompt.is_active });
      if (selectedCollectionId) {
        await loadPrompts(selectedCollectionId);
      }
    } catch (error) {
      alert('Error updating prompt status: ' + (error.response?.data?.detail || error.message));
    }
  };

  const handleSetDefaultPrompt = async (prompt) => {
    try {
      await api.put(`/prompts/${prompt.prompt_id}`, { is_default: true });
      if (selectedCollectionId) {
        await loadPrompts(selectedCollectionId);
      }
    } catch (error) {
      alert('Error setting default prompt: ' + (error.response?.data?.detail || error.message));
    }
  };

  const createUser = async (e) => {
    e.preventDefault();

    if (!selectedCollectionId) {
      alert('Please select a collection before creating a user.');
      return;
    }

    try {
      const userData = {
        ...newUser,
        website_id: websiteId,
        collection_id: selectedCollectionId
      };
      const response = await api.post('/users/', userData);

      setNewUser({
        username: '',
        password: '',
        email: '',
        full_name: '',
        role: 'user',
        collection_id: selectedCollectionId
      });

      await loadUsers(selectedCollectionId);
      alert('User created successfully!');
    } catch (error) {
      alert('Error creating user: ' + (error.response?.data?.detail || error.message));
    }
  };

  const grantFileAccess = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/files/${selectedFile.file_id}/access`, newFileAccess);
      setNewFileAccess({
        user_id: '',
        can_read: true,
        can_download: false,
        can_delete: false,
        expires_at: ''
      });
      loadFileAccess(selectedFile.file_id);
      alert('File access granted successfully!');
    } catch (error) {
      alert('Error granting access: ' + (error.response?.data?.detail || error.message));
    }
  };

  const loadFileAccess = async (fileId) => {
    try {
      const res = await api.get(`/files/${fileId}/access`);
      setFileAccessUsers(res.data);
    } catch (error) {
      console.error('Error loading file access:', error);
    }
  };

  const revokeFileAccess = async (accessId) => {
    if (window.confirm('Are you sure you want to revoke this access?')) {
      try {
        await api.delete(`/files/${selectedFile.file_id}/access/${accessId}`);
        loadFileAccess(selectedFile.file_id);
        alert('Access revoked successfully!');
      } catch (error) {
        alert('Error revoking access: ' + (error.response?.data?.detail || error.message));
      }
    }
  };

  const deleteFile = async (fileId) => {
    if (window.confirm('Are you sure you want to delete this file?')) {
      try {
        await api.delete(`/files/${fileId}`);
        setFiles(prev => prev.filter(file => file.file_id !== fileId));
        alert('File deleted successfully!');
      } catch (error) {
        alert('Error deleting file: ' + (error.response?.data?.detail || error.message));
      }
    }
  };

  const TabButton = ({ id, label, isActive, onClick }) => (
    <button
      className={`tab-button ${isActive ? 'active' : ''}`}
      onClick={() => onClick(id)}
    >
      {label}
    </button>
  );

  const selectedCollection = collections.find(col => col.collection_id === selectedCollectionId);

  return (
    <div className="user-admin-dashboard">
      <div className="dashboard-header">
        <h1>🏢 Department Admin Dashboard</h1>
        <div className="header-actions">
          <span className="user-info">Welcome, {username}</span>
          <span className="department-info">Department: {website?.name || 'Loading...'}</span>
          <button onClick={onLogout} className="logout-btn">Logout</button>
        </div>
      </div>

      <div className="dashboard-tabs">
        <TabButton id="files" label="📁 File Management" isActive={activeTab === 'files'} onClick={setActiveTab} />
        <TabButton id="prompts" label="🤖 Prompt Library" isActive={activeTab === 'prompts'} onClick={setActiveTab} />
        <TabButton id="users" label="👥 User Management" isActive={activeTab === 'users'} onClick={setActiveTab} />
        <TabButton id="chat" label="💬 Chat" isActive={activeTab === 'chat'} onClick={setActiveTab} />
        <TabButton id="website" label="🏢 Department Info" isActive={activeTab === 'website'} onClick={setActiveTab} />
      </div>

      <div className="dashboard-content">
        {loading && <div className="loading">Loading...</div>}

        {/* File Management Tab */}
        {activeTab === 'files' && (
          <div className="files-tab">
            <div className="section">
              <h2>Collection Document Library</h2>
              <FileUploader
                collections={collections}
                defaultCollectionId={selectedCollectionId}
                onCollectionChange={setSelectedCollectionId}
                onFilesLoaded={setFiles}
                onManageAccess={(file) => {
                  setSelectedFile(file);
                  loadFileAccess(file.file_id);
                }}
              />
            </div>

            {/* File Access Management Modal */}
            {selectedFile && (
              <div className="modal-overlay" onClick={() => setSelectedFile(null)}>
                <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                  <div className="modal-header">
                    <h2>Manage Access: {selectedFile.file_name}</h2>
                    <button className="close-btn" onClick={() => setSelectedFile(null)}>×</button>
                  </div>
                  
                  <div className="modal-body">
                    <div className="section">
                      <h3>Grant New Access</h3>
                      <form onSubmit={grantFileAccess}>
                        <select
                          value={newFileAccess.user_id}
                          onChange={(e) => setNewFileAccess({...newFileAccess, user_id: e.target.value})}
                          required
                        >
                          <option value="">Select User</option>
                          {users.map(user => (
                            <option key={user.user_id} value={user.user_id}>
                              {user.full_name} ({user.username})
                            </option>
                          ))}
                        </select>
                        <div className="permissions">
                          <label>
                            <input
                              type="checkbox"
                              checked={newFileAccess.can_read}
                              onChange={(e) => setNewFileAccess({...newFileAccess, can_read: e.target.checked})}
                            />
                            Can Read
                          </label>
                          <label>
                            <input
                              type="checkbox"
                              checked={newFileAccess.can_download}
                              onChange={(e) => setNewFileAccess({...newFileAccess, can_download: e.target.checked})}
                            />
                            Can Download
                          </label>
                          <label>
                            <input
                              type="checkbox"
                              checked={newFileAccess.can_delete}
                              onChange={(e) => setNewFileAccess({...newFileAccess, can_delete: e.target.checked})}
                            />
                            Can Delete
                          </label>
                        </div>
                        <input
                          type="datetime-local"
                          placeholder="Expires At (optional)"
                          value={newFileAccess.expires_at}
                          onChange={(e) => setNewFileAccess({...newFileAccess, expires_at: e.target.value})}
                        />
                        <button type="submit" className="grant-btn">Grant Access</button>
                      </form>
                    </div>

                    <div className="section">
                      <h3>Current Access</h3>
                      <div className="access-list">
                        {fileAccessUsers.map(access => (
                          <div key={access.access_id} className="access-item">
                            <div className="access-info">
                              <strong>{access.user_name}</strong>
                              <div className="permissions">
                                {access.can_read && <span className="perm">Read</span>}
                                {access.can_download && <span className="perm">Download</span>}
                                {access.can_delete && <span className="perm">Delete</span>}
                              </div>
                              {access.expires_at && (
                                <div className="expires">Expires: {new Date(access.expires_at).toLocaleDateString()}</div>
                              )}

        {/* Prompts Tab */}
        {activeTab === 'prompts' && (
          <div className="prompts-tab">
            <div className="section">
              <h2>Collection Prompt Library</h2>

              {collections.length > 0 ? (
                <>
                  <div className="form-row">
                    <select
                      value={selectedCollectionId || ''}
                      onChange={(e) => setSelectedCollectionId(e.target.value)}
                    >
                      {collections.map(collection => (
                        <option key={collection.collection_id} value={collection.collection_id}>
                          {collection.name}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="refresh-btn"
                      onClick={() => selectedCollectionId && loadPrompts(selectedCollectionId)}
                    >
                      Refresh
                    </button>
                  </div>

                  {selectedCollection && (
                    <div className="collection-summary">
                      <strong>Selected Collection:</strong> {selectedCollection.name}
                    </div>
                  )}

                  {promptLoading ? (
                    <div className="loading">Loading prompts...</div>
                  ) : promptError ? (
                    <div className="error">{promptError}</div>
                  ) : prompts.length === 0 ? (
                    <div className="empty-state">
                      No prompts have been configured for this collection yet.
                    </div>
                  ) : (
                    <div className="users-table">
                      <table>
                        <thead>
                          <tr>
                            <th>Name</th>
                            <th>Description</th>
                            <th>Model</th>
                            <th>Max Tokens</th>
                            <th>Temperature</th>
                            <th>Status</th>
                            <th>Default</th>
                            <th>Last Used</th>
                            <th>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {prompts.map(prompt => (
                            <tr key={prompt.prompt_id}>
                              <td>{prompt.name}</td>
                              <td>{prompt.description || '—'}</td>
                              <td>{prompt.model_name}</td>
                              <td>{prompt.max_tokens}</td>
                              <td>{prompt.temperature}</td>
                              <td>
                                <span className={`status ${prompt.is_active ? 'active' : 'inactive'}`}>
                                  {prompt.is_active ? 'Active' : 'Inactive'}
                                </span>
                              </td>
                              <td>{prompt.is_default ? 'Yes' : 'No'}</td>
                              <td>{prompt.last_used ? new Date(prompt.last_used).toLocaleString() : 'Never'}</td>
                              <td>
                                <div className="prompt-actions">
                                  <button className="btn-outline" onClick={() => openPromptDialog(prompt)}>View / Edit</button>
                                  <button className="btn-outline" onClick={() => handleTogglePromptActive(prompt)}>
                                    {prompt.is_active ? 'Deactivate' : 'Activate'}
                                  </button>
                                  {!prompt.is_default && (
                                    <button className="btn-primary" onClick={() => handleSetDefaultPrompt(prompt)}>
                                      Set Default
                                    </button>
                                  )}
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              ) : (
                <div className="empty-state">
                  No collections available. Create a collection first to manage prompts.
                </div>
              )}
            </div>
          </div>
        )}
                            </div>
                            <button 
                              className="revoke-btn"
                              onClick={() => revokeFileAccess(access.access_id)}
                            >
                              Revoke
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* User Management Tab */}
        {activeTab === 'users' && (
          <div className="users-tab">
            <div className="section">
              <h2>Create New User</h2>
              <form onSubmit={createUser} className="create-form">
                <div className="form-row">
                  <input
                    placeholder="Username"
                    value={newUser.username}
                    onChange={(e) => setNewUser({...newUser, username: e.target.value})}
                    required
                  />
                  <input
                    placeholder="Password"
                    type="password"
                    value={newUser.password}
                    onChange={(e) => setNewUser({...newUser, password: e.target.value})}
                    required
                  />
                </div>
                <div className="form-row">
                  <input
                    placeholder="Email"
                    type="email"
                    value={newUser.email}
                    onChange={(e) => setNewUser({...newUser, email: e.target.value})}
                    required
                  />
                  <input
                    placeholder="Full Name"
                    value={newUser.full_name}
                    onChange={(e) => setNewUser({...newUser, full_name: e.target.value})}
                    required
                  />
                </div>
                <select
                  value={newUser.role}
                  onChange={(e) => setNewUser({...newUser, role: e.target.value})}
                >
                  <option value="user">Regular User</option>
                </select>
                <button type="submit" className="create-btn">Create User</button>
              </form>
            </div>

            <div className="section">
              <h2>Department Users</h2>
              <div className="users-table">
                <table>
                  <thead>
                    <tr>
                      <th>Username</th>
                      <th>Full Name</th>
                      <th>Email</th>
                      <th>Role</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map(user => (
                      <tr key={user.user_id}>
                        <td>{user.username}</td>
                        <td>{user.full_name}</td>
                        <td>{user.email}</td>
                        <td>
                          <span className={`role-badge ${user.role}`}>
                            {user.role.replace('_', ' ').toUpperCase()}
                          </span>
                        </td>
                        <td>
                          <span className={`status ${user.is_active ? 'active' : 'inactive'}`}>
                            {user.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                        <td>
                          <button className="edit-btn">Edit</button>
                          <button
                            className="reset-btn"
                            onClick={() => openPasswordDialog(user)}
                            disabled={
                              user.role === 'super_admin' ||
                              (currentUserIdRef.current && String(currentUserIdRef.current) === String(user.user_id))
                            }
                          >
                            Reset Password
                          </button>
                          <button
                            className="delete-btn"
                            disabled={
                              user.role === 'super_admin' ||
                              user.role !== 'user' ||
                              (currentUserIdRef.current && String(currentUserIdRef.current) === String(user.user_id))
                            }
                            onClick={() => handleDeleteUser(user)}
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Chat Tab */}
        {activeTab === 'chat' && (
          <div className="chat-tab">
            <ChatWindow
              collections={collections}
              collectionId={selectedCollectionId}
            />
          </div>
        )}

        {/* Department Info Tab */}
        {activeTab === 'website' && website && (
          <div className="website-tab">
            <div className="website-info">
              <h2>{website.name}</h2>
              <div className="info-grid">
                <div className="info-item">
                  <label>Domain:</label>
                  <span>{website.domain}</span>
                </div>
                <div className="info-item">
                  <label>Description:</label>
                  <span>{website.description}</span>
                </div>
                <div className="info-item">
                  <label>Admin Email:</label>
                  <span>{website.admin_email}</span>
                </div>
                <div className="info-item">
                  <label>Status:</label>
                  <span className={`status ${website.is_active ? 'active' : 'inactive'}`}>
                    {website.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
              </div>
              
              <div className="quotas">
                <h3>Resource Quotas</h3>
                <div className="quota-item">
                  <label>Users:</label>
                  <div className="quota-bar">
                    <div 
                      className="quota-fill" 
                      style={{width: `${(website.user_count / website.max_users) * 100}%`}}
                    ></div>
                  </div>
                  <span>{website.user_count || 0} / {website.max_users}</span>
                </div>
                <div className="quota-item">
                  <label>Files:</label>
                  <div className="quota-bar">
                    <div 
                      className="quota-fill" 
                      style={{width: `${(website.file_count / website.max_files) * 100}%`}}
                    ></div>
                  </div>
                  <span>{website.file_count || 0} / {website.max_files}</span>
                </div>
                <div className="quota-item">
                  <label>Storage:</label>
                  <div className="quota-bar">
                    <div 
                      className="quota-fill" 
                      style={{width: `${(website.storage_used_mb / website.max_storage_mb) * 100}%`}}
                    ></div>
                  </div>
                  <span>{website.storage_used_mb || 0}MB / {website.max_storage_mb}MB</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {promptDialogOpen && activePrompt && (
        <div className="modal-overlay" onClick={closePromptDialog}>
          <div className="modal-content large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Edit Prompt: {activePrompt.name}</h2>
              <button className="close-btn" onClick={closePromptDialog}>×</button>
            </div>
            <form className="prompt-form" onSubmit={handlePromptSubmit}>
              <div className="form-row">
                <label>
                  Name
                  <input
                    value={promptForm.name}
                    onChange={(e) => handlePromptFieldChange('name', e.target.value)}
                    required
                  />
                </label>
                <label>
                  Model Name
                  <input
                    value={promptForm.model_name}
                    onChange={(e) => handlePromptFieldChange('model_name', e.target.value)}
                    required
                  />
                </label>
              </div>

              <label>
                Description
                <textarea
                  value={promptForm.description}
                  onChange={(e) => handlePromptFieldChange('description', e.target.value)}
                  rows={2}
                />
              </label>

              <label>
                System Prompt
                <textarea
                  value={promptForm.system_prompt}
                  onChange={(e) => handlePromptFieldChange('system_prompt', e.target.value)}
                  rows={8}
                  required
                />
              </label>

              <label>
                User Prompt Template (optional)
                <textarea
                  value={promptForm.user_prompt_template}
                  onChange={(e) => handlePromptFieldChange('user_prompt_template', e.target.value)}
                  rows={4}
                  placeholder="Use {query} and {context} placeholders to customize prompts"
                />
              </label>

              <label>
                Context Template (optional)
                <textarea
                  value={promptForm.context_template}
                  onChange={(e) => handlePromptFieldChange('context_template', e.target.value)}
                  rows={4}
                  placeholder="Customize how retrieved context is formatted"
                />
              </label>

              <div className="form-row">
                <label>
                  Max Tokens
                  <input
                    type="number"
                    value={promptForm.max_tokens}
                    onChange={(e) => handlePromptFieldChange('max_tokens', e.target.value)}
                    required
                  />
                </label>
                <label>
                  Temperature
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="2"
                    value={promptForm.temperature}
                    onChange={(e) => handlePromptFieldChange('temperature', e.target.value)}
                    required
                  />
                </label>
              </div>

              <div className="form-row">
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={promptForm.is_active}
                    onChange={(e) => handlePromptFieldChange('is_active', e.target.checked)}
                  />
                  Active
                </label>
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={promptForm.is_default}
                    onChange={(e) => handlePromptFieldChange('is_default', e.target.checked)}
                    disabled={activePrompt.is_default}
                  />
                  Set as Default
                </label>
              </div>

              <div className="modal-actions">
                <button type="button" className="btn-outline" onClick={closePromptDialog} disabled={promptSubmitting}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={promptSubmitting}>
                  {promptSubmitting ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {passwordDialog.open && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>Reset Password</h3>
            <p>Set a new password for <strong>{passwordDialog.user?.username}</strong>.</p>
            <input
              type="password"
              placeholder="New Password"
              value={passwordForm.new_password}
              onChange={(e) => setPasswordForm((prev) => ({ ...prev, new_password: e.target.value }))}
            />
            <input
              type="password"
              placeholder="Confirm Password"
              value={passwordForm.confirm_password}
              onChange={(e) => setPasswordForm((prev) => ({ ...prev, confirm_password: e.target.value }))}
            />
            <div className="modal-actions">
              <button className="secondary" onClick={closePasswordDialog}>Cancel</button>
              <button className="primary" onClick={handleResetPassword}>Update Password</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserAdminDashboard;
