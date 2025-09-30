import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import api from '../api/api';
import FileUploader from './FileUploader';
import ChatWindow from './ChatWindow';
import Layout from './Layout';

// Modern icon components using emojis and SVG
const DashboardIcon = () => <span className="w-6 h-6 text-xl">📊</span>;
const CollectionsIcon = () => <span className="w-6 h-6 text-xl">📚</span>;
const PeopleIcon = () => <span className="w-6 h-6 text-xl">👥</span>;
const PromptIcon = () => <span className="w-6 h-6 text-xl">🤖</span>;
const LogoutIcon = () => <span className="w-6 h-6 text-xl">🚪</span>;
const AddIcon = () => <span className="w-6 h-6 text-xl">➕</span>;
const ChatIcon = () => <span className="w-6 h-6 text-xl">💬</span>;
const AccountCircle = () => <span className="w-6 h-6 text-xl">👤</span>;
const NotificationsIcon = () => <span className="w-6 h-6 text-xl">🔔</span>;
const MenuIcon = () => <span className="w-6 h-6 text-xl">☰</span>;
const CloseIcon = () => <span className="w-6 h-6 text-xl">✕</span>;

const SuperAdminDashboard = ({ onLogout }) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState({ open: false, message: '', severity: 'success' });
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [dialogType, setDialogType] = useState(''); // 'collection' or 'user'

  const getDefaultPromptForm = () => ({
    collection_id: '',
    name: '',
    description: '',
    system_prompt: '',
    user_prompt_template: '',
    context_template: '',
    vector_db_id: '',
    model_name: 'claude-3-haiku-20240307',
    max_tokens: 4000,
    temperature: 0.7,
    is_active: true,
    is_default: false
  });

  // Consolidated data state
  const [dashboardData, setDashboardData] = useState({
    collections: [],
    users: [],
    prompts: [],
    systemStats: {}
  });
  const loadedTabsRef = useRef(new Set());
  const [selectedCollectionId, setSelectedCollectionId] = useState(null);
  const [collectionPrompts, setCollectionPrompts] = useState({});
  const [promptDialog, setPromptDialog] = useState({ open: false, mode: 'create', prompt: null });
  const [healthOverview, setHealthOverview] = useState(null);
  const [resetDialog, setResetDialog] = useState({ open: false, password: '' });
  const [promptForm, setPromptForm] = useState(getDefaultPromptForm);
  const [promptCollectionFilter, setPromptCollectionFilter] = useState('all');
  const [chatCollectionId, setChatCollectionId] = useState('');
  const [collectionFiles, setCollectionFiles] = useState([]);
  const [editUserDialog, setEditUserDialog] = useState({ open: false, user: null });
  const [editUserForm, setEditUserForm] = useState({
    full_name: '',
    email: '',
    role: 'user'
  });
  const [editCollectionDialog, setEditCollectionDialog] = useState({ open: false, collection: null });
  const [editCollectionForm, setEditCollectionForm] = useState({
    name: '',
    description: '',
    website_url: '',
    is_active: true
  });
  const [userPasswordDialog, setUserPasswordDialog] = useState({ open: false, user: null });
  const [userPasswordForm, setUserPasswordForm] = useState({
    new_password: '',
    confirm_password: ''
  });
  const [selfPasswordDialog, setSelfPasswordDialog] = useState(false);
  const [selfPasswordForm, setSelfPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  });

  // Form states
  const [newCollection, setNewCollection] = useState({
    name: '',
    description: '',
    website_url: '',
    admin_email: '',
    admin_username: '',
    admin_password: '',
    is_active: true
  });

  const [newUser, setNewUser] = useState({
    username: '',
    email: '',
    password: '',
    full_name: '',
    role: 'user_admin',
    collection_id: ''
  });

  const currentUserIdRef = React.useRef(localStorage.getItem('user_id'));

  const showNotification = (message, severity = 'success') => {
    setNotification({ open: true, message, severity });
  };

  useEffect(() => {
    if (!notification.open) return;

    const timer = setTimeout(() => {
      setNotification(prev => ({ ...prev, open: false }));
    }, 4000);

    return () => clearTimeout(timer);
  }, [notification.open]);

  // Navigation items
  const menuItems = [
    { id: 'overview', label: 'Overview', icon: DashboardIcon, description: 'System overview and statistics' },
    { id: 'collections', label: 'Collections', icon: CollectionsIcon, description: 'Manage document collections' },
    { id: 'files', label: 'Files', icon: CollectionsIcon, description: 'File management' },
    { id: 'users', label: 'Users', icon: PeopleIcon, description: 'User management' },
    { id: 'prompts', label: 'Prompts', icon: PromptIcon, description: 'AI prompt management' },
    { id: 'chat', label: 'Chat', icon: ChatIcon, description: 'Test chat interface' },
    { id: 'reset', label: 'Reset', icon: CloseIcon, description: 'Reset system to defaults (requires superadmin password)' }
  ];

  // Load data function
  const loadData = useCallback(async (force = false, tabOverride = null) => {
    const tabToLoad = tabOverride || activeTab;
    const hasData = () => {
      switch (tabToLoad) {
        case 'overview':
          return dashboardData.systemStats && Object.keys(dashboardData.systemStats).length > 0;
        case 'collections':
          return dashboardData.collections && dashboardData.collections.length > 0;
        case 'users':
          return dashboardData.users && dashboardData.users.length > 0;
        case 'prompts':
          return dashboardData.prompts && dashboardData.prompts.length > 0;
        default:
          return false;
      }
    };

    if (!force && hasData() && loadedTabsRef.current.has(tabToLoad)) {
      return;
    }

    setLoading(true);
    try {
      switch (tabToLoad) {
        case 'overview':
          await Promise.all([loadOverviewData(force), loadHealth(force)]);
          break;
        case 'collections':
          await loadCollections(force);
          break;
        case 'users':
          await loadUsers(force);
          break;
        case 'prompts':
          await loadPrompts(force);
          break;
      }
      loadedTabsRef.current.add(tabToLoad);
    } catch (error) {
      console.error(`Error loading ${tabToLoad} data:`, error);
      showNotification(`Failed to load ${tabToLoad} data`, 'error');
    } finally {
      setLoading(false);
    }
  }, [activeTab, dashboardData]);

  const loadOverviewData = async (force = false) => {
    try {
      // Load all data and calculate stats from actual arrays (like old frontend)
      const [collectionsRes, usersRes, promptsRes] = await Promise.all([
        api.get('/collections/'),
        api.get('/users/'),
        api.get('/prompts/')
      ]);
      
      // Calculate stats from actual data
      const systemStats = {
        total_collections: collectionsRes.data.length,
        total_users: usersRes.data.length,
        total_files: 0, // Will be updated when files are loaded
        total_prompts: promptsRes.data.length
      };
      
      setDashboardData(prev => ({
        ...prev,
        collections: collectionsRes.data,
        users: usersRes.data,
        prompts: promptsRes.data,
        systemStats
      }));
    } catch (error) {
      console.error('Error loading overview data:', error);
      // Fallback to basic stats
      setDashboardData(prev => ({
        ...prev,
        systemStats: {
          total_collections: 0,
          total_users: 0,
          total_files: 0,
          total_prompts: 0
        }
      }));
    }
  };

  const loadCollections = async (force = false) => {
    try {
      const response = await api.get('/collections/');
      setDashboardData(prev => ({
        ...prev,
        collections: response.data || [],
        systemStats: {
          ...prev.systemStats,
          total_collections: response.data?.length || 0
        }
      }));
    } catch (error) {
      console.error('Error loading collections:', error);
      setDashboardData(prev => ({
        ...prev,
        collections: []
      }));
    }
  };

  const saveCollectionChanges = async () => {
    if (!editCollectionDialog.collection) return;

    try {
      const collectionData = {
        name: editCollectionForm.name,
        description: editCollectionForm.description,
        website_url: editCollectionForm.website_url,
        is_active: editCollectionForm.is_active
      };

      await api.put(`/collections/${editCollectionDialog.collection.collection_id}`, collectionData);
      
      // Update local state
      setDashboardData(prev => ({
        ...prev,
        collections: prev.collections.map(c => 
          c.collection_id === editCollectionDialog.collection.collection_id 
            ? { ...c, ...collectionData }
            : c
        )
      }));
      
      setEditCollectionDialog({ open: false, collection: null });
      showNotification('Collection updated successfully!');
    } catch (error) {
      console.error('Error updating collection:', error);
      showNotification('Failed to update collection: ' + (error.response?.data?.detail || error.message), 'error');
    }
  };

  const savePromptChanges = async () => {
    try {
      if (promptDialog.mode === 'create') {
        // Create new prompt
        console.log('Creating prompt with data:', promptForm);
        const response = await api.post('/prompts/', promptForm);
        console.log('Prompt create response:', response.data);
        
        // Refresh prompts data
        await loadPrompts();
        showNotification('Prompt created successfully!');
      } else {
        // Update existing prompt
        console.log('Updating prompt with data:', promptForm);
        const response = await api.put(`/prompts/${promptDialog.prompt.prompt_id}`, promptForm);
        console.log('Prompt update response:', response.data);
        
        // Update local state
        setDashboardData(prev => ({
          ...prev,
          prompts: prev.prompts.map(p => 
            p.prompt_id === promptDialog.prompt.prompt_id 
              ? { ...p, ...response.data }
              : p
          )
        }));
        
        // Also update collection prompts if it's in there
        if (promptForm.collection_id) {
          setCollectionPrompts(prev => ({
            ...prev,
            [promptForm.collection_id]: prev[promptForm.collection_id]?.map(p => 
              p.prompt_id === promptDialog.prompt.prompt_id 
                ? { ...p, ...response.data }
                : p
            ) || []
          }));
        }
        
        showNotification('Prompt updated successfully!');
      }
      
      setPromptDialog({ open: false, mode: 'create', prompt: null });
      setPromptForm(getDefaultPromptForm());
      
    } catch (error) {
      console.error('Error saving prompt:', error);
      showNotification('Failed to save prompt: ' + (error.response?.data?.detail || error.message), 'error');
    }
  };

  const loadUsers = async (force = false) => {
    try {
      const response = await api.get('/users/');
      setDashboardData(prev => ({
        ...prev,
        users: response.data || [],
        systemStats: {
          ...prev.systemStats,
          total_users: response.data?.length || 0
        }
      }));
    } catch (error) {
      console.error('Error loading users:', error);
      setDashboardData(prev => ({
        ...prev,
        users: []
      }));
    }
  };

  const loadPrompts = async (force = false) => {
    try {
      const response = await api.get('/prompts/');
      setDashboardData(prev => ({
        ...prev,
        prompts: response.data || [],
        systemStats: {
          ...prev.systemStats,
          total_prompts: response.data?.length || 0
        }
      }));
    } catch (error) {
      console.error('Error loading prompts:', error);
      setDashboardData(prev => ({
        ...prev,
        prompts: []
      }));
    }
  };

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Health loader
  const loadHealth = async () => {
    try {
      const res = await api.get('/health');
      setHealthOverview(res.data || null);
    } catch (error) {
      console.error('Error loading health:', error);
      setHealthOverview(null);
    }
  };

  // Stat Card Component
  const StatCard = ({ title, value, subtitle, icon: Icon, color = 'primary' }) => (
    <div className="card group hover:scale-105 transition-transform duration-200">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600 mb-1">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
        </div>
        <div className={`p-3 rounded-lg bg-${color}-100 text-${color}-600`}>
          <Icon />
        </div>
      </div>
    </div>
  );

  // Reset Tab Component
  const ResetTab = () => (
    <div className="space-y-6">
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Reset System to Defaults</h3>
          <p className="card-subtitle">This deletes all data and recreates default superadmin, admin, user, one collection and prompt. Enter superadmin password to confirm.</p>
        </div>
        <div className="space-y-4">
          <div className="form-group">
            <label className="form-label">Superadmin Password</label>
            <input
              type="password"
              className="form-input"
              value={resetDialog.password}
              onChange={(e) => setResetDialog({ ...resetDialog, password: e.target.value })}
              placeholder="Enter superadmin password"
            />
          </div>
          <div className="p-3 rounded-md bg-error-50 text-error-700 text-sm">
            <strong>Warning:</strong> This is destructive and cannot be undone.
          </div>
          <div className="flex space-x-3">
            <button
              onClick={() => setResetDialog({ open: false, password: '' })}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              onClick={async () => {
                if (!resetDialog.password) { showNotification('Please enter superadmin password', 'error'); return; }
                if (!window.confirm('Are you sure you want to reset the entire system to defaults?')) return;
                try {
                  setLoading(true);
                  await api.post('/health/reset', { password: resetDialog.password });
                  showNotification('System reset successfully to default state', 'success');
                  setResetDialog({ open: false, password: '' });
                  await Promise.all([
                    loadCollections(true),
                    loadUsers(true),
                    loadPrompts(true),
                    loadOverviewData(true),
                    loadHealth(true)
                  ]);
                  setActiveTab('overview');
                } catch (error) {
                  console.error('Error resetting system:', error);
                  showNotification(`Reset failed: ${error.response?.data?.detail || error.message}`, 'error');
                } finally {
                  setLoading(false);
                }
              }}
              className="btn btn-primary"
            >
              Reset System
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  // Overview Tab Component
  const badge = (status) => {
    const ok = status === 'healthy';
    const warn = status === 'degraded';
    const cls = ok ? 'bg-success-100 text-success-800' : warn ? 'bg-warning-100 text-warning-800' : 'bg-error-100 text-error-800';
    const label = ok ? 'Healthy' : warn ? 'Degraded' : 'Unhealthy';
    return <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${cls}`}>{label}</span>;
  };

  const OverviewTab = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">System Overview</h2>
          <p className="text-gray-600">Monitor your knowledge base system performance</p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={() => loadData(true, 'overview')}
            className="btn btn-secondary"
            disabled={loading}
          >
            {loading ? (
              <>
                <div className="spinner"></div>
                Refreshing...
              </>
            ) : (
              <>
                <span>🔄</span>
                Refresh
              </>
            )}
          </button>
          <button
            onClick={() => {
              setDialogType('collection');
              setCreateDialogOpen(true);
            }}
            className="btn btn-primary"
          >
            <AddIcon />
            Test Modal
          </button>
        </div>
      </div>

      <div className="stats-grid">
          <StatCard
          title="Total Collections"
          value={dashboardData.systemStats?.total_collections || 0}
          subtitle="Document collections"
          icon={CollectionsIcon}
          color="primary"
        />
          <StatCard
          title="Total Users"
          value={dashboardData.systemStats?.total_users || 0}
          subtitle="Registered users"
          icon={PeopleIcon}
          color="success"
        />
          <StatCard
          title="Total Files"
          value={dashboardData.systemStats?.total_files || 0}
          subtitle="Uploaded documents"
          icon={CollectionsIcon}
          color="warning"
        />
          <StatCard
          title="Total Prompts"
          value={dashboardData.systemStats?.total_prompts || 0}
          subtitle="AI prompts configured"
          icon={PromptIcon}
          color="error"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Quick Actions</h3>
            <p className="card-subtitle">Common administrative tasks</p>
          </div>
          <div className="space-y-3">
            <button
              onClick={() => setActiveTab('collections')}
              className="w-full btn btn-primary text-left justify-start"
            >
              <CollectionsIcon />
              Manage Collections
            </button>
            <button
              onClick={() => setActiveTab('users')}
              className="w-full btn btn-secondary text-left justify-start"
            >
              <PeopleIcon />
              Manage Users
            </button>
            <button
              onClick={() => setActiveTab('prompts')}
              className="w-full btn btn-secondary text-left justify-start"
            >
              <PromptIcon />
              Configure Prompts
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className="w-full btn btn-secondary text-left justify-start"
            >
              <ChatIcon />
              Test Chat Interface
            </button>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3 className="card-title">System Health</h3>
            <p className="card-subtitle">Current system status</p>
          </div>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-600">Vector DB (Qdrant)</span>
              {badge(healthOverview?.services?.qdrant?.status || 'unhealthy')}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-600">AI Model</span>
              {badge(healthOverview?.services?.ai_model?.status || 'unhealthy')}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-600">File Processing</span>
              {badge(healthOverview?.services?.file_processing?.status || 'unhealthy')}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-600">Authentication</span>
              {badge(healthOverview?.services?.authentication?.status || 'unhealthy')}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // Collections Tab Component
  const CollectionsTab = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Collections</h2>
          <p className="text-gray-600">Manage document collections and their settings</p>
        </div>
        <button
          onClick={() => {
            setDialogType('collection');
            setCreateDialogOpen(true);
          }}
          className="btn btn-primary"
        >
          <AddIcon />
          Create Collection
        </button>
      </div>

      {dashboardData.collections.length === 0 ? (
        <div className="card text-center py-12">
          <div className="text-6xl mb-4">📚</div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">No Collections Found</h3>
          <p className="text-gray-600 mb-4">Create your first collection to start organizing documents</p>
          <button
            onClick={() => {
              setDialogType('collection');
              setCreateDialogOpen(true);
            }}
            className="btn btn-primary"
          >
            <AddIcon />
            Create Collection
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {dashboardData.collections.map((collection) => (
            <div key={collection.collection_id} className="card group hover:shadow-medium transition-shadow duration-200 relative">
              {/* Action buttons positioned absolutely to the right */}
              <div className="absolute top-4 right-4 flex space-x-1 z-10">
                <button
                  onClick={() => {
                    setEditCollectionDialog({ open: true, collection });
                    setEditCollectionForm({
                      name: collection.name,
                      description: collection.description || '',
                      website_url: collection.website_url || '',
                      is_active: collection.is_active
                    });
                  }}
                  className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-all duration-200"
                  title="Edit collection"
                >
                  <span className="text-sm">✏️</span>
                </button>
                <button
                  onClick={async () => {
                    if (window.confirm(`Are you sure you want to delete "${collection.name}"? This action cannot be undone.`)) {
                      try {
                        setLoading(true);
                        await api.delete(`/collections/${collection.collection_id}`);
                        showNotification(`Collection "${collection.name}" deleted successfully`, 'success');
                        // Refresh collections data
                        await loadCollections(true);
                        await loadOverviewData(true);
                      } catch (error) {
                        console.error('Error deleting collection:', error);
                        showNotification(`Failed to delete collection: ${error.response?.data?.detail || error.message}`, 'error');
                      } finally {
                        setLoading(false);
                      }
                    }
                  }}
                  className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-error-600 hover:bg-error-50 rounded-lg transition-all duration-200"
                  title="Delete collection"
                >
                  <span className="text-sm">🗑️</span>
                </button>
              </div>
              
              <div className="card-header pr-20">
                <div>
                  <h3 className="card-title">{collection.name}</h3>
                  <p className="card-subtitle">{collection.description || 'No description'}</p>
                </div>
              </div>
              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">Admin Email:</span>
                  <span className="font-medium">{collection.admin_email || 'N/A'}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">Website:</span>
                  <span className="font-medium truncate max-w-32">{collection.website_url || 'N/A'}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">Status:</span>
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    collection.is_active 
                      ? 'bg-success-100 text-success-800' 
                      : 'bg-gray-100 text-gray-800'
                  }`}>
                    {collection.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  // Users Tab Component
  const UsersTab = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Users</h2>
          <p className="text-gray-600">Manage system users and their permissions</p>
        </div>
        <button
          onClick={() => {
            setDialogType('user');
            setCreateDialogOpen(true);
          }}
          className="btn btn-primary"
        >
          <AddIcon />
          Create User
        </button>
      </div>

      {dashboardData.users.length === 0 ? (
        <div className="card text-center py-12">
          <div className="text-6xl mb-4">👥</div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">No Users Found</h3>
          <p className="text-gray-600 mb-4">Create your first user to start managing access</p>
          <button
            onClick={() => {
              setDialogType('user');
              setCreateDialogOpen(true);
            }}
            className="btn btn-primary"
          >
            <AddIcon />
            Create User
          </button>
        </div>
      ) : (
        <UsersGroupedByCollection
          collections={dashboardData.collections}
          users={dashboardData.users}
        />
      )}
    </div>
  );

  const UsersGroupedByCollection = ({ collections = [], users = [] }) => {
    const { groupedUsers, unassignedUsers } = useMemo(() => {
      const grouped = {};
      const unassigned = [];

      users.forEach((user) => {
        const assignedCollections = user.collection_ids && user.collection_ids.length > 0
          ? user.collection_ids
          : [];

        if (assignedCollections.length === 0) {
          unassigned.push(user);
          return;
        }

        assignedCollections.forEach((collectionId) => {
          if (!grouped[collectionId]) {
            grouped[collectionId] = [];
          }
          grouped[collectionId].push(user);
        });
      });

      return { groupedUsers: grouped, unassignedUsers: unassigned };
    }, [users]);

    const renderUserCard = (user, keyPrefix) => {
      const roleClass = user.role === 'super_admin'
        ? 'bg-error-100 text-error-800'
        : user.role === 'user_admin'
        ? 'bg-warning-100 text-warning-800'
        : 'bg-success-100 text-success-800';

      const statusClass = user.is_active
        ? 'bg-success-100 text-success-800'
        : 'bg-gray-100 text-gray-800';

      return (
        <div key={`${keyPrefix}-${user.user_id}`} className="card shadow-sm">
          <div className="flex items-start justify-between">
            <div className="flex items-center">
              <div className="w-10 h-10 bg-primary-100 rounded-full flex items-center justify-center mr-3">
                <AccountCircle />
              </div>
              <div>
                <div className="font-medium text-gray-900">{user.full_name || user.username}</div>
                <div className="text-sm text-gray-500">@{user.username}</div>
              </div>
            </div>
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${roleClass}`}>
              {user.role.replace('_', ' ').toUpperCase()}
            </span>
          </div>
          <div className="mt-4 space-y-2 text-sm text-gray-600">
            <div className="flex items-center justify-between">
              <span className="font-medium text-gray-700">Email</span>
              <span className="text-gray-900 font-medium">{user.email || 'N/A'}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-medium text-gray-700">Status</span>
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusClass}`}>
                {user.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
            <div>
              <span className="font-medium text-gray-700">Collections</span>
              <div className="mt-2 flex flex-wrap gap-2">
                {(user.collection_ids && user.collection_ids.length > 0)
                  ? user.collection_ids.map((collectionId) => {
                      const collection = collections.find((c) => c.collection_id === collectionId);
                      const label = collection ? collection.name : collectionId;
                      return (
                        <span
                          key={`${user.user_id}-${collectionId}`}
                          className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-primary-50 text-primary-700"
                        >
                          {label}
                        </span>
                      );
                    })
                  : (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                      None
                    </span>
                  )}
              </div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              onClick={async () => {
                try {
                  setLoading(true);
                  await api.put(`/users/${user.user_id}`, { is_active: !user.is_active });
                  showNotification(`User "${user.username}" ${user.is_active ? 'disabled' : 'activated'}`, 'success');
                  await loadUsers(true);
                  await loadOverviewData(true);
                } catch (error) {
                  console.error('Error toggling user state:', error);
                  showNotification(`Failed to update user: ${error.response?.data?.detail || error.message}`, 'error');
                } finally {
                  setLoading(false);
                }
              }}
              className="btn btn-secondary btn-sm"
              title={user.is_active ? 'Disable user' : 'Activate user'}
            >
              {user.is_active ? 'Disable' : 'Activate'}
            </button>
            <button
              onClick={() => {
                setEditUserDialog({ open: true, user });
                setEditUserForm({
                  full_name: user.full_name || '',
                  email: user.email || '',
                  role: user.role || 'user'
                });
              }}
              className="btn btn-tertiary btn-sm"
              title="Edit user"
            >
              Edit
            </button>
            <button
              onClick={() => {
                setUserPasswordDialog({ open: true, user });
              }}
              className="btn btn-tertiary btn-sm"
              title="Reset password"
            >
              Reset Password
            </button>
            <button
              onClick={async () => {
                if (window.confirm(`Are you sure you want to delete user "${user.username}"? This action cannot be undone.`)) {
                  try {
                    setLoading(true);
                    await api.delete(`/users/${user.user_id}`);
                    showNotification(`User "${user.username}" deleted successfully`, 'success');
                    await loadUsers(true);
                    await loadOverviewData(true);
                  } catch (error) {
                    console.error('Error deleting user:', error);
                    showNotification(`Failed to delete user: ${error.response?.data?.detail || error.message}`, 'error');
                  } finally {
                    setLoading(false);
                  }
                }
              }}
              className="btn btn-danger btn-sm"
              title="Delete user"
            >
              Delete
            </button>
          </div>
        </div>
      );
    };

    const collectionCards = (collections || []).map((collection) => {
      const usersForCollection = groupedUsers[collection.collection_id] || [];

      return (
        <div key={collection.collection_id} className="card">
          <div className="card-header flex flex-col md:flex-row md:items-center md:justify-between">
            <div>
              <h3 className="card-title">{collection.name}</h3>
              <p className="card-subtitle">Users assigned to {collection.name}</p>
            </div>
            <div className="text-sm text-gray-500 mt-2 md:mt-0">
              {usersForCollection.length} {usersForCollection.length === 1 ? 'user' : 'users'}
            </div>
          </div>
          {usersForCollection.length === 0 ? (
            <div className="p-6 text-sm text-gray-500">
              No users assigned to this collection yet.
            </div>
          ) : (
            <div className="p-6 pt-0">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {usersForCollection.map((user) => renderUserCard(user, collection.collection_id))}
              </div>
            </div>
          )}
        </div>
      );
    });

    return (
      <div className="space-y-6">
        {collectionCards}
        {unassignedUsers.length > 0 && (
          <div className="card">
            <div className="card-header flex flex-col md:flex-row md:items-center md:justify-between">
              <div>
                <h3 className="card-title">Global & Unassigned Users</h3>
                <p className="card-subtitle">Users without a specific collection assignment</p>
              </div>
              <div className="text-sm text-gray-500 mt-2 md:mt-0">
                {unassignedUsers.length} {unassignedUsers.length === 1 ? 'user' : 'users'}
              </div>
            </div>
            <div className="p-6 pt-0">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {unassignedUsers.map((user) => renderUserCard(user, 'global'))}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Prompts Tab Component
  const PromptsTab = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">AI Prompts</h2>
          <p className="text-gray-600">Configure AI prompts for different collections</p>
        </div>
        <button
          onClick={() => {
            // Reset form for new prompt
            setPromptForm(getDefaultPromptForm());
            setPromptDialog({ open: true, mode: 'create', prompt: null });
          }}
          className="btn btn-primary"
        >
          <AddIcon />
              Create Prompt
        </button>
      </div>

      {dashboardData.prompts.length === 0 ? (
        <div className="card text-center py-12">
          <div className="text-6xl mb-4">🤖</div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">No Prompts Found</h3>
          <p className="text-gray-600 mb-4">Create your first AI prompt to customize responses</p>
          <button
            onClick={() => {
              // Reset form for new prompt
              setPromptForm(getDefaultPromptForm());
              setPromptDialog({ open: true, mode: 'create', prompt: null });
            }}
            className="btn btn-primary"
          >
            <AddIcon />
            Create Prompt
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {dashboardData.prompts.map((prompt) => (
            <div key={prompt.prompt_id} className="card">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-2">
                    <h3 className="text-lg font-semibold text-gray-900">{prompt.name}</h3>
                              {prompt.is_default && (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-800">
                        Default
                      </span>
                    )}
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
                      <span className="text-gray-500">Collection:</span>
                      <span className="ml-2 font-medium">
                        {(() => {
                          if (!prompt.collection_id) return 'All';
                          const collection = dashboardData.collections.find(c => c.collection_id === prompt.collection_id);
                          return collection ? collection.name : prompt.collection_id;
                        })()}
                      </span>
                    </div>
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
                  </div>
                </div>
                <div className="flex space-x-1 ml-4">
                  <button
                    onClick={() => {
                      // Populate form with existing prompt data
                      setPromptForm({
                        collection_id: prompt.collection_id || '',
                        name: prompt.name || '',
                        description: prompt.description || '',
                        system_prompt: prompt.system_prompt || '',
                        user_prompt_template: prompt.user_prompt_template || '',
                        context_template: prompt.context_template || '',
                        vector_db_id: prompt.vector_db_id || '',
                        model_name: prompt.model_name || 'claude-3-haiku-20240307',
                        max_tokens: prompt.max_tokens || 4000,
                        temperature: prompt.temperature || 0.7,
                        is_active: prompt.is_active !== undefined ? prompt.is_active : true,
                        is_default: prompt.is_default !== undefined ? prompt.is_default : false
                      });
                      setPromptDialog({ open: true, mode: 'edit', prompt });
                    }}
                    className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-all duration-200"
                    title="Edit prompt"
                  >
                    <span className="text-sm">✏️</span>
                  </button>
                  <button
                    onClick={async () => {
                      if (window.confirm(`Are you sure you want to delete prompt "${prompt.name}"? This action cannot be undone.`)) {
                        try {
                          setLoading(true);
                          await api.delete(`/prompts/${prompt.prompt_id}`);
                          showNotification(`Prompt "${prompt.name}" deleted successfully`, 'success');
                          // Refresh prompts data
                          await loadPrompts(true);
                          await loadOverviewData(true);
                        } catch (error) {
                          console.error('Error deleting prompt:', error);
                          showNotification(`Failed to delete prompt: ${error.response?.data?.detail || error.message}`, 'error');
                        } finally {
                          setLoading(false);
                        }
                      }
                    }}
                    className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-error-600 hover:bg-error-50 rounded-lg transition-all duration-200"
                    title="Delete prompt"
                  >
                    <span className="text-sm">🗑️</span>
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
        <ChatWindow collections={dashboardData.collections} />
      </div>
    </div>
  );

  // Memoized callbacks for FileUploader to prevent infinite re-renders
  const handleCollectionChange = useCallback((collectionId) => {
    setSelectedCollectionId(collectionId);
  }, []);

  const handleFilesLoaded = useCallback((files) => {
    setCollectionFiles(files);
  }, []);

  const handleStatsChange = useCallback((stats) => {
    // Update file stats if needed
    console.log('File stats updated:', stats);
  }, []);

  // Use collections directly (simplified to avoid useMemo issues)
  const memoizedCollections = dashboardData.collections || [];

  // Files Tab Component
  const FilesTab = () => (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">File Management</h2>
        <p className="text-gray-600">Upload and manage documents across collections</p>
      </div>
      <FileUploader
        collections={memoizedCollections}
        defaultCollectionId={selectedCollectionId}
        onCollectionChange={handleCollectionChange}
        onFilesLoaded={handleFilesLoaded}
        onStatsChange={handleStatsChange}
      />
    </div>
  );

  // Render content based on active tab
  const renderContent = () => {
    switch (activeTab) {
      case 'overview':
        return <OverviewTab />;
      case 'collections':
        return <CollectionsTab />;
      case 'files':
        return <FilesTab />;
      case 'users':
        return <UsersTab />;
      case 'prompts':
        return <PromptsTab />;
      case 'chat':
        return <ChatTab />;
      case 'reset':
        return <ResetTab />;
      default:
        return <OverviewTab />;
    }
  };

  const sidebarProps = {
    isOpen: !mobileOpen,
    onClose: () => setMobileOpen(true),
    title: "Super Admin",
    icon: "🤖",
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
      name: "Super Administrator",
      role: "Full Access"
    },
    onLogout
  };

  const headerContent = (
    <>
      <button
        className="inline-flex items-center space-x-2 px-4 py-2 rounded-lg bg-red-500 text-white font-semibold shadow-sm hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-400 focus:ring-offset-1 transition"
        onClick={onLogout}
      >
        <span className="text-lg">🚪</span>
        <span>Logout</span>
      </button>
    </>
  );

  return (
    <>
      <Layout sidebarProps={sidebarProps} headerContent={headerContent}>
        {renderContent()}
      </Layout>

      {/* Create Collection/User Dialog */}
      {createDialogOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
          <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
        {dialogType === 'collection' ? 'Create New Collection' : 'Create New User'}
            </h3>
            <div className="space-y-4">
          {dialogType === 'collection' ? (
            <>
                  <div className="form-group">
                    <label className="form-label">Collection Name</label>
                    <input
                      type="text"
                      className="form-input"
                  value={newCollection.name}
                      onChange={(e) => setNewCollection({ ...newCollection, name: e.target.value })}
                  required
                />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Description</label>
                    <textarea
                      className="form-textarea"
                  value={newCollection.description}
                  onChange={(e) => setNewCollection({ ...newCollection, description: e.target.value })}
                />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Website URL</label>
                    <input
                  type="url"
                      className="form-input"
                  value={newCollection.website_url}
                  onChange={(e) => setNewCollection({ ...newCollection, website_url: e.target.value })}
                />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Admin Email</label>
                    <input
                      type="email"
                      className="form-input"
                      value={newCollection.admin_email}
                      onChange={(e) => setNewCollection({ ...newCollection, admin_email: e.target.value })}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Admin Username</label>
                    <input
                      type="text"
                      className="form-input"
                  value={newCollection.admin_username}
                  onChange={(e) => setNewCollection({ ...newCollection, admin_username: e.target.value })}
                  required
                />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Admin Password</label>
                    <input
                  type="password"
                      className="form-input"
                  value={newCollection.admin_password}
                  onChange={(e) => setNewCollection({ ...newCollection, admin_password: e.target.value })}
                  required
                />
                  </div>
            </>
          ) : (
            <>
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
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Role</label>
                    <select
                      className="form-select"
                    value={newUser.role}
                    onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                  >
                      <option value="user_admin">User Admin</option>
                      <option value="user">Regular User</option>
                      <option value="super_admin">Super Admin</option>
                    </select>
                  </div>
                  {newUser.role !== 'super_admin' && (
                    <div className="form-group">
                      <label className="form-label">Collection <span className="text-red-500">*</span></label>
                      <select
                        className="form-select"
                        value={newUser.collection_id}
                        onChange={(e) => setNewUser({ ...newUser, collection_id: e.target.value })}
                        required
                      >
                        <option value="">Select Collection</option>
                        {dashboardData.collections.map(collection => (
                          <option key={collection.collection_id} value={collection.collection_id}>
                          {collection.name}
                          </option>
                      ))}
                      </select>
                    </div>
                  )}
            </>
          )}
              <div className="flex space-x-3">
                <button
                  onClick={() => setCreateDialogOpen(false)}
                  className="btn btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  onClick={async () => {
                    try {
                      setLoading(true);
                      
                      if (dialogType === 'collection') {
                        // Create collection
                        const response = await api.post('/collections/', newCollection);
                        showNotification(`Collection "${newCollection.name}" created successfully!`, 'success');
                        
                        // Reset form
                        setNewCollection({
                          name: '',
                          description: '',
                          website_url: '',
                          admin_email: '',
                          admin_username: '',
                          admin_password: '',
                          is_active: true
                        });
                        
                        // Refresh data
                        await loadCollections(true);
                        await loadOverviewData(true);
                        
                      } else {
                        // Validate user form
                        if (!newUser.username || !newUser.password || !newUser.email) {
                          showNotification('Please fill in all required fields', 'error');
                          return;
                        }
                        
                        if (newUser.role !== 'super_admin' && !newUser.collection_id) {
                          showNotification('Please select a collection for non-super-admin users', 'error');
                          return;
                        }
                        
                        // Create user
                        const response = await api.post('/users/', newUser);
                        showNotification(`User "${newUser.username}" created successfully!`, 'success');
                        
                        // Reset form
                        setNewUser({
                          username: '',
                          email: '',
                          full_name: '',
                          password: '',
                          role: 'user_admin',
                          collection_id: ''
                        });
                        
                        // Refresh data
                        await loadUsers(true);
                        await loadOverviewData(true);
                      }
                      
                      setCreateDialogOpen(false);
                      
                    } catch (error) {
                      console.error(`Error creating ${dialogType}:`, error);
                      showNotification(
                        `Failed to create ${dialogType}: ${error.response?.data?.detail || error.message}`, 
                        'error'
                      );
                    } finally {
                      setLoading(false);
                    }
                  }}
                  className="btn btn-primary flex-1"
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit User Dialog */}
      {editUserDialog.open && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
          <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Edit User: {editUserDialog.user?.username}
            </h3>
            <div className="space-y-4">
              <div className="form-group">
                <label className="form-label">Full Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={editUserForm.full_name}
                  onChange={(e) => setEditUserForm({ ...editUserForm, full_name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Email</label>
                <input
                  type="email"
                  className="form-input"
                  value={editUserForm.email}
                  onChange={(e) => setEditUserForm({ ...editUserForm, email: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Role</label>
                <select
                  className="form-select"
                  value={editUserForm.role}
                  onChange={(e) => setEditUserForm({ ...editUserForm, role: e.target.value })}
                >
                  <option value="user_admin">User Admin</option>
                  <option value="user">Regular User</option>
                </select>
              </div>
              <div className="flex space-x-3">
                <button
                  onClick={() => setEditUserDialog({ open: false, user: null })}
                  className="btn btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    setEditUserDialog({ open: false, user: null });
                    showNotification('User updated successfully!');
                  }}
                  className="btn btn-primary flex-1"
                >
                  Update
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit Collection Dialog */}
      {editCollectionDialog.open && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
          <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Edit Collection: {editCollectionDialog.collection?.name}
            </h3>
            <div className="space-y-4">
              <div className="form-group">
                <label className="form-label">Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={editCollectionForm.name}
                  onChange={(e) => setEditCollectionForm({ ...editCollectionForm, name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <textarea
                  className="form-textarea"
                  value={editCollectionForm.description}
                  onChange={(e) => setEditCollectionForm({ ...editCollectionForm, description: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Website URL</label>
                <input
                  type="url"
                  className="form-input"
                  value={editCollectionForm.website_url}
                  onChange={(e) => setEditCollectionForm({ ...editCollectionForm, website_url: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    className="mr-2"
                    checked={editCollectionForm.is_active}
                    onChange={(e) => setEditCollectionForm({ ...editCollectionForm, is_active: e.target.checked })}
                  />
                  Active
                </label>
              </div>
              <div className="flex space-x-3">
                <button
                  onClick={() => setEditCollectionDialog({ open: false, collection: null })}
                  className="btn btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  onClick={saveCollectionChanges}
                  className="btn btn-primary flex-1"
                >
                  Update
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* User Password Dialog */}
      {userPasswordDialog.open && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
          <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Reset Password for {userPasswordDialog.user?.username}
            </h3>
            <div className="space-y-4">
              <div className="form-group">
                <label className="form-label">New Password</label>
                <input
                  type="password"
                  className="form-input"
                  value={userPasswordForm.new_password}
                  onChange={(e) => setUserPasswordForm({ ...userPasswordForm, new_password: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Confirm Password</label>
                <input
                  type="password"
                  className="form-input"
                  value={userPasswordForm.confirm_password}
                  onChange={(e) => setUserPasswordForm({ ...userPasswordForm, confirm_password: e.target.value })}
                  required
                />
              </div>
              <div className="flex space-x-3">
                <button
                  onClick={() => setUserPasswordDialog({ open: false, user: null })}
                  className="btn btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  onClick={async () => {
                    if (!userPasswordForm.new_password || userPasswordForm.new_password !== userPasswordForm.confirm_password) {
                      showNotification('Passwords do not match', 'error');
                      return;
                    }
                    try {
                      setLoading(true);
                      await api.post('/users/reset-password', {
                        user_id: userPasswordDialog.user?.user_id,
                        new_password: userPasswordForm.new_password
                      });
                      setUserPasswordDialog({ open: false, user: null });
                      setUserPasswordForm({ new_password: '', confirm_password: '' });
                      showNotification('Password updated successfully!');
                    } catch (error) {
                      console.error('Error updating password:', error);
                      showNotification(`Failed to update password: ${error.response?.data?.detail || error.message}`, 'error');
                    } finally {
                      setLoading(false);
                    }
                  }}
                  className="btn btn-primary flex-1"
                >
                  Update Password
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Self Password Dialog */}
      {selfPasswordDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
          <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Change Your Password
            </h3>
            <div className="space-y-4">
              <div className="form-group">
                <label className="form-label">Current Password</label>
                <input
                  type="password"
                  className="form-input"
                  value={selfPasswordForm.current_password}
                  onChange={(e) => setSelfPasswordForm({ ...selfPasswordForm, current_password: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">New Password</label>
                <input
                  type="password"
                  className="form-input"
                  value={selfPasswordForm.new_password}
                  onChange={(e) => setSelfPasswordForm({ ...selfPasswordForm, new_password: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Confirm Password</label>
                <input
                  type="password"
                  className="form-input"
                  value={selfPasswordForm.confirm_password}
                  onChange={(e) => setSelfPasswordForm({ ...selfPasswordForm, confirm_password: e.target.value })}
                  required
                />
              </div>
              <div className="flex space-x-3">
                <button
                  onClick={() => setSelfPasswordDialog(false)}
                  className="btn btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    setSelfPasswordDialog(false);
                    showNotification('Password changed successfully!');
                  }}
                  className="btn btn-primary flex-1"
                >
            Change Password
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Prompt Dialog */}
      {promptDialog.open && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
          <div className="bg-white rounded-xl p-6 w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              {promptDialog.mode === 'create' ? 'Create New Prompt' : 'Edit Prompt'}
            </h3>
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="form-group">
                  <label className="form-label">Collection</label>
                  <select
                    className="form-select"
                    value={promptForm.collection_id}
                    onChange={(e) => setPromptForm({ ...promptForm, collection_id: e.target.value })}
                    required
                  >
                    <option value="">Select Collection</option>
                    {dashboardData.collections.map(collection => (
                      <option key={collection.collection_id} value={collection.collection_id}>
                        {collection.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Name</label>
                  <input
                    type="text"
                    className="form-input"
                    value={promptForm.name}
                    onChange={(e) => setPromptForm({ ...promptForm, name: e.target.value })}
                    required
                  />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <textarea
                  className="form-textarea"
                  value={promptForm.description}
                  onChange={(e) => setPromptForm({ ...promptForm, description: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">System Prompt</label>
                <textarea
                  className="form-textarea"
                  value={promptForm.system_prompt}
                  onChange={(e) => setPromptForm({ ...promptForm, system_prompt: e.target.value })}
                  rows={4}
                />
              </div>
              <div className="form-group">
                <label className="form-label">User Prompt Template</label>
                <textarea
                  className="form-textarea"
                  value={promptForm.user_prompt_template}
                  onChange={(e) => setPromptForm({ ...promptForm, user_prompt_template: e.target.value })}
                  rows={3}
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="form-group">
                  <label className="form-label">Model Name</label>
                  <input
                    type="text"
                    className="form-input"
                    value={promptForm.model_name}
                    onChange={(e) => setPromptForm({ ...promptForm, model_name: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Max Tokens</label>
                  <input
                    type="number"
                    className="form-input"
                    value={promptForm.max_tokens}
                    onChange={(e) => setPromptForm({ ...promptForm, max_tokens: parseInt(e.target.value) })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Temperature</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="2"
                    className="form-input"
                    value={promptForm.temperature}
                    onChange={(e) => setPromptForm({ ...promptForm, temperature: parseFloat(e.target.value) })}
                  />
                </div>
              </div>
              <div className="flex items-center space-x-4">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    className="mr-2"
                    checked={promptForm.is_active}
                    onChange={(e) => setPromptForm({ ...promptForm, is_active: e.target.checked })}
                  />
                  Active
                </label>
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    className="mr-2"
                    checked={promptForm.is_default}
                    onChange={(e) => setPromptForm({ ...promptForm, is_default: e.target.checked })}
                  />
                  Default
                </label>
              </div>
              <div className="flex space-x-3">
                <button
                  onClick={() => setPromptDialog({ open: false, mode: 'create', prompt: null })}
                  className="btn btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  onClick={savePromptChanges}
                  className="btn btn-primary flex-1"
                >
                  {promptDialog.mode === 'create' ? 'Create' : 'Update'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Notification */}
      {notification.open && (
        <div className="fixed top-4 right-4 z-[9999]">
          <div className={`alert ${
            notification.severity === 'success' ? 'alert-success' :
            notification.severity === 'error' ? 'alert-error' :
            notification.severity === 'warning' ? 'alert-warning' : 'alert-info'
          }`}>
            <span className="mr-2">
              {notification.severity === 'success' ? '✅' :
               notification.severity === 'error' ? '❌' :
               notification.severity === 'warning' ? '⚠️' : 'ℹ️'}
            </span>
            {notification.message}
            <button
              onClick={() => setNotification({ ...notification, open: false })}
              className="ml-4 text-current opacity-70 hover:opacity-100"
            >
              ✕
            </button>
          </div>
        </div>
      )}
    </>
  );
};

export default SuperAdminDashboard;
