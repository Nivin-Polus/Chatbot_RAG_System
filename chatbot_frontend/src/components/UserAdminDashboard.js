import React, { useState, useEffect, useRef } from 'react';
import api from '../api/api';
import FileUploader from './FileUploader';
import ChatWindow from './ChatWindow';
import Layout from './Layout';

// Modern icon components
const FilesIcon = () => <span className="w-6 h-6 text-xl">📁</span>;
const UsersIcon = () => <span className="w-6 h-6 text-xl">👥</span>;
const PromptsIcon = () => <span className="w-6 h-6 text-xl">🤖</span>;
const ChatIcon = () => <span className="w-6 h-6 text-xl">💬</span>;
const LogoutIcon = () => <span className="w-6 h-6 text-xl">🚪</span>;
const AddIcon = () => <span className="w-6 h-6 text-xl">➕</span>;
const EditIcon = () => <span className="w-6 h-6 text-xl">✏️</span>;
const DeleteIcon = () => <span className="w-6 h-6 text-xl">🗑️</span>;
const MenuIcon = () => <span className="w-6 h-6 text-xl">☰</span>;
const CloseIcon = () => <span className="w-6 h-6 text-xl">✕</span>;

const UserAdminDashboard = ({ onLogout }) => {
  const [activeTab, setActiveTab] = useState('files');
  const [loading, setLoading] = useState(false);
  const [collections, setCollections] = useState([]);
  const [selectedCollectionId, setSelectedCollectionId] = useState(null);
  const [prompts, setPrompts] = useState([]);
  const [promptLoading, setPromptLoading] = useState(false);
  const [selectedPromptId, setSelectedPromptId] = useState(null);
  const [editingPrompt, setEditingPrompt] = useState(null);
  const [editPromptForm, setEditPromptForm] = useState({});
  const [users, setUsers] = useState([]);
  const [website, setWebsite] = useState(null);
  const [passwordDialog, setPasswordDialog] = useState({ open: false, user: null });
  const [passwordForm, setPasswordForm] = useState({ new_password: '', confirm_password: '' });
  const [mobileOpen, setMobileOpen] = useState(false);

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
  const [promptError, setPromptError] = useState(null);

  const websiteId = localStorage.getItem('website_id');
  const username = localStorage.getItem('username');

  // Navigation items
  const menuItems = [
    { id: 'files', label: 'Files', icon: FilesIcon, description: 'Manage documents and file access' },
    { id: 'users', label: 'Users', icon: UsersIcon, description: 'Manage user accounts' },
    { id: 'prompts', label: 'Prompts', icon: PromptsIcon, description: 'Configure AI prompts' },
    { id: 'chat', label: 'Chat', icon: ChatIcon, description: 'Test chat interface' }
  ];

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        await Promise.all([
          loadCollections(),
          loadWebsite()
        ]);
      } catch (error) {
        console.error('Error initializing dashboard:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Load users and prompts when collection is selected
  useEffect(() => {
    if (selectedCollectionId) {
      loadUsers(selectedCollectionId);
      loadPrompts(selectedCollectionId);
    }
  }, [selectedCollectionId]);

  const loadCollections = async () => {
    try {
      const response = await api.get('/collections/');
      const userCollections = response.data || [];
      setCollections(userCollections);
      
      if (userCollections.length > 0 && !selectedCollectionId) {
        setSelectedCollectionId(userCollections[0].collection_id);
      }
    } catch (error) {
      console.error('Error loading collections:', error);
      setCollections([]);
    }
  };

  const loadPrompts = async (collectionId) => {
    if (!collectionId) return;
    
    setPromptLoading(true);
    setPromptError(null);
    try {
      const response = await api.get(`/prompts/?collection_id=${collectionId}`);
      setPrompts(response.data || []);
    } catch (error) {
      console.error('Error loading prompts:', error);
      setPromptError('Failed to load prompts');
    } finally {
      setPromptLoading(false);
    }
  };

  const loadUsers = async (collectionId) => {
    try {
      // For UserAdmin, filter users by collection
      const params = collectionId ? { collection_id: collectionId } : {};
      const response = await api.get('/users/', { params });
      setUsers(response.data || []);
    } catch (error) {
      console.error('Error loading users:', error);
      setUsers([]);
    }
  };

  const loadWebsite = async () => {
    try {
      const response = await api.get(`/websites/${websiteId}`);
      setWebsite(response.data);
    } catch (error) {
      console.error('Error loading website:', error);
    }
  };

  const handleDeleteUser = async (user) => {
    if (!user || !user.user_id) return;
    
    if (!window.confirm(`Are you sure you want to delete user "${user.username}"?`)) {
      return;
    }

    try {
      await api.delete(`/users/${user.user_id}`);
      setUsers(prev => prev.filter(u => u.user_id !== user.user_id));
    } catch (error) {
      console.error('Error deleting user:', error);
      alert('Failed to delete user: ' + (error.response?.data?.detail || error.message));
    }
  };

  const openPasswordDialog = (user) => {
    setPasswordDialog({ open: true, user });
    setPasswordForm({ new_password: '', confirm_password: '' });
  };

  const closePasswordDialog = () => {
    setPasswordDialog({ open: false, user: null });
  };

  const handleResetPassword = async () => {
    if (!passwordDialog.user) return;
    
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      alert('Passwords do not match');
      return;
    }

    if (passwordForm.new_password.length < 6) {
      alert('Password must be at least 6 characters long');
      return;
    }

    try {
      await api.put(`/users/${passwordDialog.user.user_id}/password`, {
        new_password: passwordForm.new_password
      });
      alert('Password updated successfully');
      closePasswordDialog();
    } catch (error) {
      console.error('Error updating password:', error);
      alert('Failed to update password: ' + (error.response?.data?.detail || error.message));
    }
  };

  const createUser = async (e) => {
    e.preventDefault();
    
    if (newUser.password.length < 6) {
      alert('Password must be at least 6 characters long');
      return;
    }

    try {
      const userData = {
        ...newUser,
        website_id: websiteId,
        collection_id: selectedCollectionId // Assign user to current collection
      };
      
      const response = await api.post('/users/', userData);
      setUsers(prev => [...prev, response.data]);
      setNewUser({
        username: '',
        password: '',
        email: '',
        full_name: '',
        role: 'user'
      });
      alert('User created successfully');
    } catch (error) {
      console.error('Error creating user:', error);
      alert('Failed to create user: ' + (error.response?.data?.detail || error.message));
    }
  };

  const grantFileAccess = async () => {
    // File access management not implemented yet
    alert('File access management feature coming soon');
  };

  const loadFileAccess = async (fileId) => {
    try {
      // File access management not implemented yet
      console.log('File access management feature coming soon');
      setFileAccessUsers([]);
    } catch (error) {
      console.error('Error loading file access:', error);
      setFileAccessUsers([]);
    }
  };

  const revokeFileAccess = async (accessId) => {
    // File access management not implemented yet
    alert('File access management feature coming soon');
  };

  const startEditingPrompt = (prompt) => {
    setEditingPrompt(prompt);
    setEditPromptForm({
      name: prompt.name || '',
      description: prompt.description || '',
      system_prompt: prompt.system_prompt || '',
      user_prompt_template: prompt.user_prompt_template || '',
      context_template: prompt.context_template || '',
      model_name: prompt.model_name || 'claude-3-haiku-20240307',
      max_tokens: prompt.max_tokens || 4000,
      temperature: prompt.temperature || 0.7,
      is_active: prompt.is_active !== false
    });
  };

  const cancelEditingPrompt = () => {
    setEditingPrompt(null);
    setEditPromptForm({});
  };

  const savePromptChanges = async () => {
    if (!editingPrompt) return;

    try {
      const promptData = {
        ...editPromptForm,
        collection_id: selectedCollectionId
      };

      console.log('Updating prompt with data:', promptData);
      const response = await api.put(`/prompts/${editingPrompt.prompt_id}`, promptData);
      console.log('Prompt update response:', response.data);
      
      setPrompts(prev => prev.map(p => 
        p.prompt_id === editingPrompt.prompt_id 
          ? { ...p, ...response.data }
          : p
      ));
      
      setEditingPrompt(null);
      setEditPromptForm({});
      alert('Prompt updated successfully');
    } catch (error) {
      console.error('Error updating prompt:', error);
      alert('Failed to update prompt: ' + (error.response?.data?.detail || error.message));
    }
  };

  // Tab Button Component
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

  // Files Tab Component
  const FilesTab = () => (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">File Management</h2>
        <p className="text-gray-600">Upload and manage documents in your collection</p>
      </div>
      <FileUploader
        collections={collections}
        defaultCollectionId={selectedCollectionId}
        onCollectionChange={setSelectedCollectionId}
        onManageAccess={(file) => {
          setSelectedFile(file);
          loadFileAccess(file.file_id);
        }}
      />
    </div>
  );

  // Users Tab Component
  const UsersTab = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">User Management</h2>
          <p className="text-gray-600">Manage user accounts and permissions</p>
        </div>
        <button
          onClick={() => {
            setPasswordDialog({ open: true, user: { username: 'test_user' } });
          }}
          className="btn btn-secondary"
        >
          Test Password Modal
        </button>
        <button
          onClick={() => setActiveTab('users')}
          className="btn btn-primary"
        >
          <AddIcon />
          Create User
        </button>
      </div>

      {/* Create User Form */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Create New User</h3>
        </div>
        <form onSubmit={createUser} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="form-group">
              <label className="form-label">Username</label>
              <input
                type="text"
                className="form-input"
                value={newUser.username}
                onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Email</label>
              <input
                type="email"
                className="form-input"
                value={newUser.email}
                onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Full Name</label>
              <input
                type="text"
                className="form-input"
                value={newUser.full_name}
                onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Password</label>
              <input
                type="password"
                className="form-input"
                value={newUser.password}
                onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                required
                minLength="6"
              />
            </div>
          </div>
          <button type="submit" className="btn btn-primary">
            <AddIcon />
            Create User
          </button>
        </form>
      </div>

      {/* Users List */}
      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>User</th>
              <th>Email</th>
              <th>Role</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.user_id}>
                <td>
                  <div className="flex items-center">
                    <div className="w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center mr-3">
                      <span className="text-primary-600 text-sm">👤</span>
                    </div>
                    <div>
                      <div className="font-medium text-gray-900">{user.full_name || user.username}</div>
                      <div className="text-sm text-gray-500">@{user.username}</div>
                    </div>
                  </div>
                </td>
                <td className="font-medium">{user.email}</td>
                <td>
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                    {user.role.toUpperCase()}
                  </span>
                </td>
                <td>
                  <div className="flex space-x-1">
                    <button
                      onClick={() => openPasswordDialog(user)}
                      className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-warning-600 hover:bg-warning-50 rounded-lg transition-all duration-200"
                      title="Reset password"
                    >
                      <span className="text-sm">🔑</span>
                    </button>
                    <button
                      onClick={() => handleDeleteUser(user)}
                      className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-error-600 hover:bg-error-50 rounded-lg transition-all duration-200"
                      title="Delete user"
                    >
                      <span className="text-sm">🗑️</span>
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  // Prompts Tab Component
  const PromptsTab = () => (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">AI Prompts</h2>
        <p className="text-gray-600">Configure AI prompts for your collection</p>
      </div>

      {promptLoading ? (
        <div className="card text-center py-12">
          <div className="spinner mx-auto mb-4"></div>
          <p className="text-gray-600">Loading prompts...</p>
        </div>
      ) : promptError ? (
        <div className="alert alert-error">
          <span className="alert-icon">❌</span>
          <span className="alert-message">{promptError}</span>
        </div>
      ) : prompts.length === 0 ? (
        <div className="card text-center py-12">
          <div className="text-6xl mb-4">🤖</div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">No Prompts Found</h3>
          <p className="text-gray-600">Prompts will appear here when available for this collection</p>
        </div>
      ) : (
        <div className="space-y-4">
          {prompts.map((prompt) => (
            <div key={prompt.prompt_id} className="card">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-2">
                    <h3 className="text-lg font-semibold text-gray-900">{prompt.name}</h3>
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      prompt.is_active 
                        ? 'bg-success-100 text-success-800' 
                        : 'bg-gray-100 text-gray-800'
                    }`}>
                      {prompt.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  <p className="text-gray-600 mb-3">{prompt.description}</p>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-gray-500">Model:</span>
                      <span className="ml-2 font-medium">{prompt.model_name}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Max Tokens:</span>
                      <span className="ml-2 font-medium">{prompt.max_tokens}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Temperature:</span>
                      <span className="ml-2 font-medium">{prompt.temperature}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Status:</span>
                      <span className="ml-2 font-medium">{prompt.is_active ? 'Active' : 'Inactive'}</span>
                    </div>
                  </div>
                </div>
                <div className="flex space-x-1 ml-4">
                  <button
                    onClick={() => startEditingPrompt(prompt)}
                    className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-all duration-200"
                    title="Edit prompt"
                  >
                    <span className="text-sm">✏️</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  // Chat Tab Component
  const ChatTab = () => (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Chat Interface</h2>
        <p className="text-gray-600">Test the AI chat functionality</p>
      </div>
      <div className="card">
        <ChatWindow collections={collections} />
      </div>
    </div>
  );

  // Render content based on active tab
  const renderContent = () => {
    switch (activeTab) {
      case 'files':
        return <FilesTab />;
      case 'users':
        return <UsersTab />;
      case 'prompts':
        return <PromptsTab />;
      case 'chat':
        return <ChatTab />;
      default:
        return <FilesTab />;
    }
  };

  const sidebarProps = {
    isOpen: !mobileOpen,
    onClose: () => setMobileOpen(true),
    title: "User Admin",
    icon: "👤",
    menuItems: menuItems.map(item => ({
      ...item,
      icon: item.icon
    })),
    activeTab,
    onTabChange: (tab) => {
      setActiveTab(tab);
      setMobileOpen(false);
    },
    userInfo: {
      name: username,
      role: "User Admin"
    },
    onLogout
  };

  const headerContent = (
    <>
      <button className="p-2 text-gray-600 hover:text-gray-900" onClick={onLogout}>
        <LogoutIcon />
      </button>
    </>
  );

  return (
    <>
      <Layout sidebarProps={sidebarProps} headerContent={headerContent}>
        {renderContent()}
      </Layout>

      {/* Password Reset Dialog */}
      {passwordDialog.open && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
          <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Reset Password for {passwordDialog.user?.username}
            </h3>
            <div className="space-y-4">
              <div className="form-group">
                <label className="form-label">New Password</label>
                <input
                  type="password"
                  className="form-input"
                  value={passwordForm.new_password}
                  onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Confirm Password</label>
                <input
                  type="password"
                  className="form-input"
                  value={passwordForm.confirm_password}
                  onChange={(e) => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })}
                  required
                />
              </div>
              <div className="flex space-x-3">
                <button
                  onClick={closePasswordDialog}
                  className="btn btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  onClick={handleResetPassword}
                  className="btn btn-primary flex-1"
                >
                  Update Password
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit Prompt Dialog */}
      {editingPrompt && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-xl font-semibold text-gray-900">Edit Prompt</h3>
                <button
                  onClick={cancelEditingPrompt}
                  className="text-gray-400 hover:text-gray-600 text-2xl"
                >
                  ×
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="form-label">Name</label>
                  <input
                    type="text"
                    className="form-input"
                    value={editPromptForm.name || ''}
                    onChange={(e) => setEditPromptForm({ ...editPromptForm, name: e.target.value })}
                    placeholder="Enter prompt name"
                  />
                </div>

                <div>
                  <label className="form-label">Description</label>
                  <textarea
                    className="form-input"
                    rows="3"
                    value={editPromptForm.description || ''}
                    onChange={(e) => setEditPromptForm({ ...editPromptForm, description: e.target.value })}
                    placeholder="Enter prompt description"
                  />
                </div>

                <div>
                  <label className="form-label">System Prompt</label>
                  <textarea
                    className="form-input"
                    rows="8"
                    value={editPromptForm.system_prompt || ''}
                    onChange={(e) => setEditPromptForm({ ...editPromptForm, system_prompt: e.target.value })}
                    placeholder="Enter the system prompt for AI responses"
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="form-label">AI Model</label>
                    <select
                      className="form-input"
                      value={editPromptForm.ai_model || 'claude-3-haiku-20240307'}
                      onChange={(e) => setEditPromptForm({ ...editPromptForm, ai_model: e.target.value })}
                    >
                      <option value="claude-3-haiku-20240307">Claude 3 Haiku</option>
                      <option value="claude-3-sonnet-20240229">Claude 3 Sonnet</option>
                      <option value="claude-3-opus-20240229">Claude 3 Opus</option>
                    </select>
                  </div>

                  <div>
                    <label className="form-label">Max Tokens</label>
                    <input
                      type="number"
                      className="form-input"
                      value={editPromptForm.max_tokens || 1000}
                      onChange={(e) => setEditPromptForm({ ...editPromptForm, max_tokens: parseInt(e.target.value) })}
                      min="100"
                      max="4000"
                    />
                  </div>

                  <div>
                    <label className="form-label">Temperature</label>
                    <input
                      type="number"
                      step="0.1"
                      className="form-input"
                      value={editPromptForm.temperature || 0.0}
                      onChange={(e) => setEditPromptForm({ ...editPromptForm, temperature: parseFloat(e.target.value) })}
                      min="0"
                      max="1"
                    />
                  </div>
                </div>
              </div>

              <div className="flex space-x-3 mt-6 pt-4 border-t">
                <button
                  onClick={cancelEditingPrompt}
                  className="btn btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  onClick={savePromptChanges}
                  className="btn btn-primary flex-1"
                >
                  Save Changes
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default UserAdminDashboard;
