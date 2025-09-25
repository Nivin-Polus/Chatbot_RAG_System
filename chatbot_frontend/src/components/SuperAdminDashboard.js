import React, { useState, useEffect, useRef, useCallback } from 'react';
import api from '../api/api';
import FileUploader from './FileUploader';
import ChatWindow from './ChatWindow';
import './SuperAdminDashboard.css';

// Material UI Components
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  List,
  Typography,
  Divider,
  IconButton,
  Container,
  Grid,
  Card,
  CardContent,
  CardHeader,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  TextField,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Chip,
  LinearProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Snackbar,
  Alert,
  FormControlLabel,
  Switch
} from '@mui/material';
import ChatIcon from '@mui/icons-material/Chat';

import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  Collections as CollectionsIcon,
  People as PeopleIcon,
  SmartToy as PromptIcon,
  ExitToApp as LogoutIcon,
  Add as AddIcon,
  ChevronLeft as ChevronLeftIcon,
  Notifications as NotificationsIcon,
  AccountCircle
} from '@mui/icons-material';


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
    admin_password: ''
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

  const ChangeUserPasswordDialog = () => (
    <Dialog open={userPasswordDialog.open} onClose={closeUserPasswordDialog} maxWidth="sm" fullWidth>
      <DialogTitle>Reset Password</DialogTitle>
      <DialogContent>
        <Typography variant="body2" sx={{ mb: 2 }}>
          Set a new password for <strong>{userPasswordDialog.user?.username}</strong>.
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="New Password"
              type="password"
              value={userPasswordForm.new_password}
              onChange={(e) => setUserPasswordForm((prev) => ({ ...prev, new_password: e.target.value }))}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Confirm Password"
              type="password"
              value={userPasswordForm.confirm_password}
              onChange={(e) => setUserPasswordForm((prev) => ({ ...prev, confirm_password: e.target.value }))}
            />
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={closeUserPasswordDialog}>Cancel</Button>
        <Button variant="contained" onClick={handleResetUserPassword}>Update Password</Button>
      </DialogActions>
    </Dialog>
  );

  const ChangeSelfPasswordDialog = () => (
    <Dialog open={selfPasswordDialog} onClose={closeSelfPasswordDialog} maxWidth="sm" fullWidth>
      <DialogTitle>Change Your Password</DialogTitle>
      <DialogContent>
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Current Password"
              type="password"
              value={selfPasswordForm.current_password}
              onChange={(e) => setSelfPasswordForm((prev) => ({ ...prev, current_password: e.target.value }))}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="New Password"
              type="password"
              value={selfPasswordForm.new_password}
              onChange={(e) => setSelfPasswordForm((prev) => ({ ...prev, new_password: e.target.value }))}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Confirm Password"
              type="password"
              value={selfPasswordForm.confirm_password}
              onChange={(e) => setSelfPasswordForm((prev) => ({ ...prev, confirm_password: e.target.value }))}
            />
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={closeSelfPasswordDialog}>Cancel</Button>
        <Button variant="contained" onClick={handleChangeOwnPassword}>Change Password</Button>
      </DialogActions>
    </Dialog>
  );

  const EditCollectionDialog = () => (
    <Dialog open={editCollectionDialog.open} onClose={closeEditCollectionDialog} maxWidth="sm" fullWidth>
      <DialogTitle>Edit Collection</DialogTitle>
      <DialogContent>
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Collection Name"
              value={editCollectionForm.name}
              onChange={(e) => handleEditCollectionFieldChange('name', e.target.value)}
              required
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Description"
              multiline
              rows={3}
              value={editCollectionForm.description}
              onChange={(e) => handleEditCollectionFieldChange('description', e.target.value)}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Website URL"
              type="url"
              value={editCollectionForm.website_url}
              onChange={(e) => handleEditCollectionFieldChange('website_url', e.target.value)}
            />
          </Grid>
          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Switch
                  checked={editCollectionForm.is_active}
                  onChange={(e) => handleEditCollectionFieldChange('is_active', e.target.checked)}
                />
              }
              label={editCollectionForm.is_active ? 'Active' : 'Inactive'}
            />
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={closeEditCollectionDialog}>Cancel</Button>
        <Button variant="contained" onClick={handleSaveCollection}>
          Save Changes
        </Button>
      </DialogActions>
    </Dialog>
  );

  const EditUserDialog = () => (
    <Dialog open={editUserDialog.open} onClose={closeEditUserDialog} maxWidth="sm" fullWidth>
      <DialogTitle>Edit User</DialogTitle>
      <DialogContent>
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Full Name"
              value={editUserForm.full_name}
              onChange={(e) => handleEditUserFieldChange('full_name', e.target.value)}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Email"
              type="email"
              value={editUserForm.email}
              onChange={(e) => handleEditUserFieldChange('email', e.target.value)}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <InputLabel>Role</InputLabel>
              <Select
                value={editUserForm.role}
                label="Role"
                onChange={(e) => handleEditUserFieldChange('role', e.target.value)}
              >
                <MenuItem value="super_admin" disabled>Super Admin</MenuItem>
                <MenuItem value="user_admin">User Admin</MenuItem>
                <MenuItem value="user">Regular User</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth disabled={editUserForm.role === 'super_admin'}>
              <InputLabel>Collection</InputLabel>
              <Select
                value={editUserForm.collection_id || ''}
                label="Collection"
                onChange={(e) => handleEditUserFieldChange('collection_id', e.target.value)}
              >
                <MenuItem value="">None</MenuItem>
                {dashboardData.collections.map((collection) => (
                  <MenuItem key={collection.collection_id} value={collection.collection_id}>
                    {collection.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={closeEditUserDialog}>Cancel</Button>
        <Button variant="contained" onClick={handleSaveUser}>Save Changes</Button>
      </DialogActions>
    </Dialog>
  );

  const handleDeleteUser = async (user) => {
    if (!user || !user.user_id) {
      return;
    }

    if (user.role === 'super_admin') {
      showNotification('Super admin accounts cannot be deleted.', 'warning');
      return;
    }

    const currentUserId = currentUserIdRef.current;
    if (currentUserId && String(currentUserId) === String(user.user_id)) {
      showNotification('You cannot delete the account you are currently using.', 'warning');
      return;
    }

    const confirmed = window.confirm(`Are you sure you want to delete the user "${user.username}"?`);
    if (!confirmed) {
      return;
    }

    try {
      await api.delete(`/users/${user.user_id}`);
      showNotification('User deleted successfully!');
      await loadData(true);
    } catch (error) {
      showNotification('Error deleting user: ' + (error.response?.data?.detail || error.message), 'error');
    }
  };

  const handleCloseNotification = () => {
    setNotification((prev) => ({ ...prev, open: false }));
  };

  const handleCollectionChange = useCallback((collectionId) => {
    setSelectedCollectionId(collectionId);
  }, []);

  const openUserPasswordDialog = (user) => {
    if (!user) return;
    setUserPasswordForm({ new_password: '', confirm_password: '' });
    setUserPasswordDialog({ open: true, user });
  };

  const closeUserPasswordDialog = () => {
    setUserPasswordDialog({ open: false, user: null });
  };

  const handleResetUserPassword = async () => {
    const { new_password, confirm_password } = userPasswordForm;
    if (!userPasswordDialog.user) return;

    if (!new_password || new_password.length < 6) {
      showNotification('New password must be at least 6 characters.', 'warning');
      return;
    }

    if (new_password !== confirm_password) {
      showNotification('Passwords do not match.', 'warning');
      return;
    }

    try {
      await api.post('/users/reset-password', {
        user_id: userPasswordDialog.user.user_id,
        new_password
      });
      showNotification('Password reset successfully!');
      closeUserPasswordDialog();
    } catch (error) {
      showNotification('Error resetting password: ' + (error.response?.data?.detail || error.message), 'error');
    }
  };

  const openSelfPasswordDialog = () => {
    setSelfPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
    setSelfPasswordDialog(true);
  };

  const closeSelfPasswordDialog = () => {
    setSelfPasswordDialog(false);
  };

  const handleChangeOwnPassword = async () => {
    const { current_password, new_password, confirm_password } = selfPasswordForm;

    if (!current_password) {
      showNotification('Current password is required.', 'warning');
      return;
    }

    if (!new_password || new_password.length < 6) {
      showNotification('New password must be at least 6 characters.', 'warning');
      return;
    }

    if (new_password !== confirm_password) {
      showNotification('Passwords do not match.', 'warning');
      return;
    }

    try {
      await api.post('/auth/change-password', {
        current_password,
        new_password
      });
      showNotification('Password changed successfully!');
      closeSelfPasswordDialog();
    } catch (error) {
      showNotification('Error changing password: ' + (error.response?.data?.detail || error.message), 'error');
    }
  };

  const openEditCollectionDialog = (collection) => {
    if (!collection) return;
    setEditCollectionForm({
      name: collection.name || '',
      description: collection.description || '',
      website_url: collection.website_url || '',
      is_active: collection.is_active !== false
    });
    setEditCollectionDialog({ open: true, collection });
  };

  const closeEditCollectionDialog = () => {
    setEditCollectionDialog({ open: false, collection: null });
  };

  const handleEditCollectionFieldChange = (field, value) => {
    setEditCollectionForm((prev) => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSaveCollection = async () => {
    const collection = editCollectionDialog.collection;
    if (!collection) return;

    try {
      const payload = {
        name: editCollectionForm.name,
        description: editCollectionForm.description,
        website_url: editCollectionForm.website_url,
        is_active: editCollectionForm.is_active
      };

      await api.put(`/collections/${collection.collection_id}`, payload);
      showNotification('Collection updated successfully!');
      closeEditCollectionDialog();
      await loadCollections(true);
    } catch (error) {
      showNotification('Error updating collection: ' + (error.response?.data?.detail || error.message), 'error');
    }
  };

  const openEditUserDialog = (user) => {
    if (!user) return;
    setEditUserForm({
      full_name: user.full_name || '',
      email: user.email || '',
      role: user.role || 'user'
    });
    setEditUserDialog({ open: true, user });
  };

  const closeEditUserDialog = () => {
    setEditUserDialog({ open: false, user: null });
  };

  const handleEditUserFieldChange = (field, value) => {
    setEditUserForm((prev) => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSaveUser = async () => {
    const user = editUserDialog.user;
    if (!user) return;

    try {
      const payload = {
        full_name: editUserForm.full_name,
        email: editUserForm.email,
        role: editUserForm.role
      };

      await api.put(`/users/${user.user_id}`, payload);
      showNotification('User updated successfully!');
      closeEditUserDialog();
      await loadUsers(true);
    } catch (error) {
      showNotification('Error updating user: ' + (error.response?.data?.detail || error.message), 'error');
    }
  };

  const handleNewCollectionChange = useCallback((field, value) => {
    setNewCollection(prev => ({ ...prev, [field]: value }));
  }, []);

const handleNewUserChange = useCallback((field, value) => {
    setNewUser(prev => ({ ...prev, [field]: value }));
  }, []);

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  useEffect(() => {
    if (!loadedTabsRef.current.has('overview')) {
      loadedTabsRef.current.add('overview');
      loadData(true, 'overview');
    }
  }, []);

  useEffect(() => {
    const needsLoad = !loadedTabsRef.current.has(activeTab);
    if (needsLoad) {
      loadedTabsRef.current.add(activeTab);
      loadData(true);
    }
  }, [activeTab]);

  useEffect(() => {
    if (!dashboardData.collections.length) {
      return;
    }

    if (activeTab === 'collections' || activeTab === 'files') {
      setSelectedCollectionId((prev) => prev || dashboardData.collections[0].collection_id);
    }
  }, [activeTab, dashboardData.collections]);

  useEffect(() => {
    if (!dashboardData.collections.length) {
      return;
    }

    const fallbackCollectionId = selectedCollectionId || dashboardData.collections[0].collection_id;

    setNewUser((prev) => {
      if (prev.collection_id === fallbackCollectionId) {
        return prev;
      }
      return {
        ...prev,
        collection_id: fallbackCollectionId
      };
    });
  }, [dashboardData.collections, selectedCollectionId]);

  const loadData = async (force = false, tabOverride = null) => {
    const tabToLoad = tabOverride || activeTab;
    const hasData = () => {
      switch (tabToLoad) {
        case 'collections':
          return dashboardData.collections.length > 0;
        case 'users':
          return dashboardData.users.length > 0;
        case 'prompts':
          return dashboardData.prompts.length > 0;
        case 'overview':
        default:
          return Object.keys(dashboardData.systemStats).length > 0;
      }
    };

    if (!force && hasData()) {
      return;
    }

    setLoading(true);
    try {
      switch (tabToLoad) {
        case 'overview':
          await loadOverviewData(force);
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
        case 'files':
          await loadCollections(force);
          break;
        case 'chat':
          await Promise.all([loadCollections(force), loadPrompts(force)]);
          break;
        default:
          await loadOverviewData(force);
      }
    } catch (error) {
      showNotification('Error loading data: ' + (error.response?.data?.detail || error.message), 'error');
    } finally {
      setLoading(false);
    }
  };

  const loadOverviewData = async (force = false) => {
    try {
      const [collectionsRes, usersRes, promptsRes] = await Promise.all([
        api.get('/collections/'),
        api.get('/users/'),
        api.get('/prompts/')
      ]);

      const systemStats = {
        totalCollections: collectionsRes.data.length,
        totalUsers: usersRes.data.length,
        totalPrompts: promptsRes.data.length,
        activeCollections: collectionsRes.data.filter(c => c.is_active).length,
        activeUsers: usersRes.data.filter(u => u.is_active).length,
        superAdmins: usersRes.data.filter(u => u.role === 'super_admin').length,
        userAdmins: usersRes.data.filter(u => u.role === 'user_admin').length,
        regularUsers: usersRes.data.filter(u => u.role === 'user').length
      };

      const groupedPrompts = promptsRes.data.reduce((acc, prompt) => {
        const key = prompt.collection_id || 'global';
        if (!acc[key]) acc[key] = [];
        acc[key].push(prompt);
        return acc;
      }, {});

      setDashboardData(prev => ({
        collections: force ? collectionsRes.data : prev.collections.length ? prev.collections : collectionsRes.data,
        users: force ? usersRes.data : prev.users.length ? prev.users : usersRes.data,
        prompts: force ? promptsRes.data : prev.prompts.length ? prev.prompts : promptsRes.data,
        systemStats
      }));
      setCollectionPrompts(groupedPrompts);
    } catch (error) {
      showNotification('Error loading overview data', 'error');
    }
  };

  const loadCollections = async (force = false) => {
    if (!force && dashboardData.collections.length > 0) {
      if (!selectedCollectionId && dashboardData.collections.length) {
        setSelectedCollectionId(dashboardData.collections[0].collection_id);
      }
      if (!chatCollectionId && dashboardData.collections.length) {
        setChatCollectionId(dashboardData.collections[0].collection_id);
      }
      return dashboardData.collections;
    }

    const response = await api.get('/collections/');
    setDashboardData(prev => ({ ...prev, collections: response.data }));

    if (!selectedCollectionId && response.data.length) {
      setSelectedCollectionId(response.data[0].collection_id);
    }

    if (!chatCollectionId && response.data.length) {
      setChatCollectionId(response.data[0].collection_id);
    }

    return response.data;
  };

  const loadUsers = async (force = false) => {
    if (!force && dashboardData.users.length > 0) return;
    const response = await api.get('/users/');
    setDashboardData(prev => ({ ...prev, users: response.data }));
  };

  const loadPrompts = async (force = false) => {
    if (!force && dashboardData.prompts.length > 0) return;
    const response = await api.get('/prompts/');

    const grouped = response.data.reduce((acc, prompt) => {
      const key = prompt.collection_id || 'global';
      if (!acc[key]) acc[key] = [];
      acc[key].push(prompt);
      return acc;
    }, {});

    setDashboardData(prev => ({ ...prev, prompts: response.data }));
    setCollectionPrompts(grouped);
  };

  const resolveCollectionById = (collectionId) =>
    dashboardData.collections.find((c) => c.collection_id === collectionId);

  const handlePromptCollectionFilterChange = async (event) => {
    const value = event.target.value;
    setPromptCollectionFilter(value);
    await loadPrompts(true);
  };

  const openPromptDialog = (mode, collectionId = null, prompt = null) => {
    const base = getDefaultPromptForm();
    const resolvedCollectionId = collectionId || (
      promptCollectionFilter !== 'all'
        ? promptCollectionFilter
        : selectedCollectionId || dashboardData.collections[0]?.collection_id || ''
    );
    const collectionData = resolveCollectionById(resolvedCollectionId);

    if (mode === 'edit' && prompt) {
      setPromptForm({
        ...base,
        ...prompt,
        collection_id: prompt.collection_id || resolvedCollectionId || '',
        vector_db_id: prompt.vector_db_id || collectionData?.vector_db_id || ''
      });
    } else {
      setPromptForm({
        ...base,
        collection_id: resolvedCollectionId || '',
        vector_db_id: collectionData?.vector_db_id || ''
      });
    }

    setPromptDialog({ open: true, mode, prompt: prompt || null });
  };

  const closePromptDialog = () => {
    setPromptDialog({ open: false, mode: 'create', prompt: null });
    setPromptForm(getDefaultPromptForm());
  };

  const handlePromptFieldChange = (field, value) => {
    setPromptForm((prev) => ({
      ...prev,
      [field]: field === 'max_tokens' ? Number(value) : field === 'temperature' ? Number(value) : value
    }));
  };

  const sanitizePromptPayload = (form) => {
    const payload = {
      ...form,
      max_tokens: Number(form.max_tokens),
      temperature: Number(form.temperature)
    };

    const optionalFields = ['collection_id', 'vector_db_id', 'description', 'user_prompt_template', 'context_template'];
    optionalFields.forEach((field) => {
      if (payload[field] === '' || payload[field] === null) {
        delete payload[field];
      }
    });

    if (Number.isNaN(payload.max_tokens)) {
      throw new Error('Maximum tokens must be a valid number');
    }

    if (Number.isNaN(payload.temperature)) {
      throw new Error('Temperature must be a valid number');
    }

    return payload;
  };

  const handlePromptSubmit = async () => {
    try {
      if (!promptForm.collection_id) {
        showNotification('Please select a collection for this prompt', 'error');
        return;
      }

      const payload = sanitizePromptPayload(promptForm);

      if (promptDialog.mode === 'create') {
        await api.post('/prompts/', payload);
        showNotification('Prompt created successfully!');
      } else if (promptDialog.prompt) {
        await api.put(`/prompts/${promptDialog.prompt.prompt_id}`, payload);
        showNotification('Prompt updated successfully!');
      }

      closePromptDialog();
      await loadPrompts(true);
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      showNotification(`Error saving prompt: ${detail}`, 'error');
    }
  };

  const handleDeletePrompt = async (prompt) => {
    if (!window.confirm(`Delete prompt "${prompt.name}"? This action cannot be undone.`)) {
      return;
    }
    try {
      await api.delete(`/prompts/${prompt.prompt_id}`);
      showNotification('Prompt deleted successfully!');
      await loadPrompts(true);
    } catch (error) {
      showNotification('Error deleting prompt: ' + (error.response?.data?.detail || error.message), 'error');
    }
  };

  const handleSetDefaultPrompt = async (prompt) => {
    try {
      await api.put(`/prompts/${prompt.prompt_id}`, { is_default: true });
      showNotification('Default prompt updated successfully!');
      await loadPrompts(true);
    } catch (error) {
      showNotification('Error updating default prompt: ' + (error.response?.data?.detail || error.message), 'error');
    }
  };

  const handleTogglePromptActive = async (prompt) => {
    try {
      await api.put(`/prompts/${prompt.prompt_id}`, { is_active: !prompt.is_active });
      showNotification('Prompt status updated successfully!');
      await loadPrompts(true);
    } catch (error) {
      showNotification('Error updating prompt status: ' + (error.response?.data?.detail || error.message), 'error');
    }
  };

  const handleViewPrompts = async (collectionId) => {
    await loadPrompts(true);
    setPromptCollectionFilter(collectionId || 'all');
    setActiveTab('prompts');
  };

  // Collection Management
  const handleCreateCollection = async () => {
    try {
      await api.post('/collections/', newCollection);
      setNewCollection({
        name: '',
        description: '',
        website_url: '',
        admin_email: '',
        admin_username: '',
        admin_password: ''
      });
      setCreateDialogOpen(false);
      showNotification('Collection created successfully!');
      loadData(true);
    } catch (error) {
      showNotification('Error creating collection: ' + (error.response?.data?.detail || error.message), 'error');
    }
  };

  const deleteCollection = async (collectionId) => {
    if (window.confirm('Are you sure you want to delete this collection? This will delete all associated data.')) {
      try {
        await api.delete(`/collections/${collectionId}`);
        loadData(true);
        showNotification('Collection deleted successfully!');
      } catch (error) {
        showNotification('Error deleting collection', 'error');
      }
    }
  };

  // User Management
  const handleCreateUser = async () => {
    try {
      await api.post('/users/', newUser);
      setNewUser({
        username: '',
        password: '',
        email: '',
        full_name: '',
        role: 'user_admin',
        collection_id: ''
      });
      setCreateDialogOpen(false);
      showNotification('User created successfully!');
      loadData(true);
    } catch (error) {
      showNotification('Error creating user: ' + (error.response?.data?.detail || error.message), 'error');
    }
  };

  const openCreateDialog = (type) => {
    setDialogType(type);
    if (type === 'user') {
      const defaultCollectionId = dashboardData.collections[0]?.collection_id || '';
      setNewUser((prev) => ({
        ...prev,
        collection_id: defaultCollectionId
      }));
    }
    setCreateDialogOpen(true);
  };

  // Stats Cards Component
  const StatCard = ({ title, value, subtitle, icon, color }) => (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={8}>
            <Typography color="textSecondary" gutterBottom variant="overline">
              {title}
            </Typography>
            <Typography variant="h4" component="div">
              {value}
            </Typography>
            <Typography variant="body2" color="textSecondary">
              {subtitle}
            </Typography>
          </Grid>
          <Grid item xs={4}>
            <Box
              sx={{
                color: color,
                fontSize: '3rem',
                display: 'flex',
                justifyContent: 'center'
              }}
            >
              {icon}
            </Box>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );

  const PromptDialog = () => (
    <Dialog open={promptDialog.open} onClose={closePromptDialog} maxWidth="md" fullWidth>
      <DialogTitle>
        {promptDialog.mode === 'edit' ? 'Edit Prompt' : 'Create Prompt'}
      </DialogTitle>
      <DialogContent>
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={12} md={6}>
            <FormControl fullWidth disabled>
              <InputLabel>Collection</InputLabel>
              <Select
                value={promptForm.collection_id}
                label="Collection"
                onChange={(e) => handlePromptFieldChange('collection_id', e.target.value)}
              >
                {dashboardData.collections.map((collection) => (
                  <MenuItem key={collection.collection_id} value={collection.collection_id}>
                    {collection.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>Vector Database (Optional)</InputLabel>
              <Select
                value={promptForm.vector_db_id || ''}
                label="Vector Database (Optional)"
                onChange={(e) => handlePromptFieldChange('vector_db_id', e.target.value)}
              >
                <MenuItem value="">Use Collection Default</MenuItem>
                {dashboardData.collections
                  .filter((collection) => collection.vector_db_id)
                  .map((collection) => (
                    <MenuItem key={collection.vector_db_id} value={collection.vector_db_id}>
                      {collection.name} — {collection.vector_db_id}
                    </MenuItem>
                  ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Prompt Name"
              value={promptForm.name}
              onChange={(e) => handlePromptFieldChange('name', e.target.value)}
              required
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Description"
              value={promptForm.description}
              onChange={(e) => handlePromptFieldChange('description', e.target.value)}
              multiline
              rows={2}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="System Prompt"
              value={promptForm.system_prompt}
              onChange={(e) => handlePromptFieldChange('system_prompt', e.target.value)}
              multiline
              rows={6}
              required
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="User Prompt Template (optional)"
              value={promptForm.user_prompt_template}
              onChange={(e) => handlePromptFieldChange('user_prompt_template', e.target.value)}
              multiline
              rows={3}
              placeholder="Use {query} and {context} placeholders to customize user prompts"
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Context Template (optional)"
              value={promptForm.context_template}
              onChange={(e) => handlePromptFieldChange('context_template', e.target.value)}
              multiline
              rows={3}
              placeholder="Customize how retrieved document chunks are presented"
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              type="number"
              label="Max Tokens"
              value={promptForm.max_tokens}
              onChange={(e) => handlePromptFieldChange('max_tokens', e.target.value)}
              required
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              type="number"
              inputProps={{ step: 0.1, min: 0, max: 2 }}
              label="Temperature"
              value={promptForm.temperature}
              onChange={(e) => handlePromptFieldChange('temperature', e.target.value)}
              required
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              label="Model Name"
              value={promptForm.model_name}
              onChange={(e) => handlePromptFieldChange('model_name', e.target.value)}
              required
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <FormControlLabel
              control={
                <Switch
                  checked={promptForm.is_active}
                  onChange={(e) => handlePromptFieldChange('is_active', e.target.checked)}
                />
              }
              label={promptForm.is_active ? 'Active' : 'Inactive'}
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <FormControlLabel
              control={
                <Switch
                  checked={promptForm.is_default}
                  onChange={(e) => handlePromptFieldChange('is_default', e.target.checked)}
                  disabled={promptDialog.mode !== 'create' && promptDialog.prompt?.is_default}
                />
              }
              label={promptForm.is_default ? 'Default for Collection' : 'Set as Default'}
            />
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={closePromptDialog}>Cancel</Button>
        <Button variant="contained" onClick={handlePromptSubmit}>
          {promptDialog.mode === 'edit' ? 'Update Prompt' : 'Create Prompt'}
        </Button>
      </DialogActions>
    </Dialog>
  );

  // Sidebar Menu Items
  const menuItems = [
    { id: 'overview', label: 'Dashboard', icon: <DashboardIcon /> },
    { id: 'collections', label: 'Collections', icon: <CollectionsIcon /> },
    { id: 'files', label: 'Files', icon: <CollectionsIcon /> },
    { id: 'users', label: 'Users', icon: <PeopleIcon /> },
    { id: 'prompts', label: 'Prompts', icon: <PromptIcon /> },
    { id: 'chat', label: 'Chat Debug', icon: <ChatIcon /> },
  ];

  // Drawer Content
  const drawer = (
    <Box sx={{ overflow: 'auto' }}>
      <Toolbar sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 1 }}>
        <Typography variant="h6" noWrap component="div" sx={{ display: 'flex', alignItems: 'center' }}>
          <CollectionsIcon sx={{ mr: 1 }} />
          Super Admin
        </Typography>
      </Toolbar>
      <Divider />
      <List>
        {menuItems.map((item) => (
          <Button
            key={item.id}
            fullWidth
            startIcon={item.icon}
            onClick={() => setActiveTab(item.id)}
            sx={{
              justifyContent: 'flex-start',
              px: 3,
              py: 1.5,
              my: 0.5,
              mx: 1,
              borderRadius: 1,
              backgroundColor: activeTab === item.id ? 'primary.main' : 'transparent',
              color: activeTab === item.id ? 'white' : 'text.primary',
              '&:hover': {
                backgroundColor: activeTab === item.id ? 'primary.dark' : 'action.hover',
              }
            }}
          >
            {item.label}
          </Button>
        ))}
      </List>
    </Box>
  );

  // Overview Tab Content
  const OverviewTab = () => (
    <Box>
      <Grid container spacing={3}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="TOTAL COLLECTIONS"
            value={dashboardData.systemStats.totalCollections || 0}
            subtitle={`${dashboardData.systemStats.activeCollections || 0} Active`}
            icon="📚"
            color="#4caf50"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="TOTAL USERS"
            value={dashboardData.systemStats.totalUsers || 0}
            subtitle={`${dashboardData.systemStats.activeUsers || 0} Active`}
            icon="👥"
            color="#2196f3"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="AI PROMPTS"
            value={dashboardData.systemStats.totalPrompts || 0}
            subtitle="Across all collections"
            icon="🤖"
            color="#ff9800"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="ADMIN USERS"
            value={dashboardData.systemStats.userAdmins || 0}
            subtitle="Management team"
            icon="⚡"
            color="#9c27b0"
          />
        </Grid>
      </Grid>

      <Grid container spacing={3} sx={{ mt: 1 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader title="User Distribution" />
            <CardContent>
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: 1 }}>
                    <Chip label="Super Admin" color="primary" />
                    <Typography variant="h6">{dashboardData.systemStats.superAdmins || 0}</Typography>
                  </Box>
                </Grid>
                <Grid item xs={12}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: 1 }}>
                    <Chip label="User Admin" color="secondary" />
                    <Typography variant="h6">{dashboardData.systemStats.userAdmins || 0}</Typography>
                  </Box>
                </Grid>
                <Grid item xs={12}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: 1 }}>
                    <Chip label="Regular User" color="success" />
                    <Typography variant="h6">{dashboardData.systemStats.regularUsers || 0}</Typography>
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader title="Recent Activity" />
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <NotificationsIcon color="success" sx={{ mr: 2 }} />
                <Typography>System is running smoothly</Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <NotificationsIcon color="info" sx={{ mr: 2 }} />
                <Typography>Last data refresh: {new Date().toLocaleTimeString()}</Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <NotificationsIcon color="success" sx={{ mr: 2 }} />
                <Typography>All services operational</Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );

  // Collections Tab Content
  const CollectionsTab = () => (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Collection Management</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => openCreateDialog('collection')}
        >
          Create Collection
        </Button>
      </Box>

      {dashboardData.collections.length === 0 ? (
        <Card>
          <CardContent sx={{ textAlign: 'center', py: 6 }}>
            <CollectionsIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h5" gutterBottom>
              No Collections Yet
            </Typography>
            <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
              Start by creating your first collection to organize your AI resources
            </Typography>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => openCreateDialog('collection')}
            >
              Create Your First Collection
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Grid container spacing={3}>
          {dashboardData.collections.map((collection) => (
            <Grid item xs={12} md={6} lg={4} key={collection.collection_id}>
              <Card sx={{ height: '100%' }}>
                <CardHeader
                  title={collection.name}
                  action={
                    <Chip
                      label={collection.is_active ? 'Active' : 'Inactive'}
                      color={collection.is_active ? 'success' : 'default'}
                      size="small"
                    />
                  }
                />
                <CardContent>
                  <Typography variant="body2" color="textSecondary" gutterBottom>
                    <strong>ID:</strong> {collection.collection_id}
                  </Typography>
                  <Typography variant="body2" color="textSecondary" gutterBottom>
                    <strong>Website:</strong> {collection.website_url || 'Not assigned'}
                  </Typography>
                  <Typography variant="body2" color="textSecondary" gutterBottom>
                    <strong>Admin:</strong> {collection.admin_email}
                  </Typography>
                  <Typography variant="body2" color="textSecondary" gutterBottom>
                    <strong>Users:</strong> {collection.user_count || 0}
                  </Typography>
                  <Typography variant="body2" color="textSecondary" gutterBottom>
                    <strong>Prompts:</strong> {collection.prompt_count || 0}
                  </Typography>
                  {collection.description && (
                    <Typography variant="body2" color="textSecondary">
                      <strong>Description:</strong> {collection.description}
                    </Typography>
                  )}
                </CardContent>
                <Box sx={{ p: 2, display: 'flex', gap: 1 }}>
                  <Button size="small" variant="outlined" onClick={() => {
                    setSelectedCollectionId(collection.collection_id);
                    setActiveTab('files');
                  }}>Manage Documents</Button>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => handleViewPrompts(collection.collection_id)}
                  >
                    View Prompts
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => openEditCollectionDialog(collection)}
                  >
                    Edit
                  </Button>
                  <Button size="small" color="error" onClick={() => deleteCollection(collection.collection_id)}>
                    Delete
                  </Button>
                </Box>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );

  const FilesTab = ({ collections, selectedCollectionId, onCollectionChange, onFilesLoaded }) => {
    const handleCollectionChange = useCallback((collectionId) => {
      onCollectionChange(collectionId);
    }, [onCollectionChange]);

    return (
      <Box>
        <Typography variant="h4" sx={{ mb: 3 }}>Collection Document Library</Typography>
        {collections && collections.length ? (
          <FileUploader
            collections={collections}
            defaultCollectionId={selectedCollectionId}
            onCollectionChange={handleCollectionChange}
            onFilesLoaded={onFilesLoaded}
            compact
          />
        ) : (
          <Card>
            <CardContent sx={{ textAlign: 'center', py: 6 }}>
              <Typography variant="h5" gutterBottom>
                No collections available
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Create a collection first to manage documents.
              </Typography>
            </CardContent>
          </Card>
        )}
      </Box>
    );
  };


  // Users Tab Content
  const UsersTab = () => (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">User Management</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => openCreateDialog('user')}
        >
          Create User
        </Button>
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Username</TableCell>
              <TableCell>Full Name</TableCell>
              <TableCell>Role</TableCell>
              <TableCell>Collection</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {dashboardData.users.map((user) => (
              <TableRow key={user.user_id}>
                <TableCell>{user.username}</TableCell>
                <TableCell>{user.full_name}</TableCell>
                <TableCell>
                  <Chip
                    label={user.role.replace('_', ' ').toUpperCase()}
                    color={
                      user.role === 'super_admin' ? 'primary' :
                      user.role === 'user_admin' ? 'secondary' : 'default'
                    }
                    size="small"
                  />
                </TableCell>
                <TableCell>
                  {(() => {
                    if (user.role === 'super_admin') {
                      return 'Global';
                    }

                    const collectionIds = user.collection_ids || [];

                    if (!collectionIds.length) {
                      return user.role === 'user_admin' ? 'No Collection Assigned' : 'No Access';
                    }

                    const names = collectionIds.map((cid) => {
                      const collection = resolveCollectionById(cid);
                      return collection?.name || cid;
                    });

                    return names.join(', ');
                  })()}
                </TableCell>
                <TableCell>
                  <Chip
                    label={user.is_active ? 'Active' : 'Inactive'}
                    color={user.is_active ? 'success' : 'default'}
                    size="small"
                  />
                </TableCell>
                <TableCell>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    {user.role === 'user_admin' && user.collection_id && (
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => handleViewPrompts(user.collection_id)}
                      >
                        View Prompts
                      </Button>
                    )}
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => openEditUserDialog(user)}
                    >
                      Edit
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      color="info"
                      onClick={() => openUserPasswordDialog(user)}
                    >
                      Change Password
                    </Button>
                    <Button
                      size="small"
                      color="error"
                      disabled={
                        user.role === 'super_admin' ||
                        (currentUserIdRef.current && String(currentUserIdRef.current) === String(user.user_id))
                      }
                      onClick={() => handleDeleteUser(user)}
                    >
                      Delete
                    </Button>
                  </Box>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );

  // Prompts Tab Content
  const PromptsTab = () => {
    const collectionOptions = dashboardData.collections.map((collection) => ({
      value: collection.collection_id,
      label: collection.name
    }));

    const getPromptsForCollection = (collectionId) => {
      if (collectionId === 'all') {
        return dashboardData.prompts;
      }
      return collectionPrompts[collectionId] || [];
    };

    const filteredCollectionIds = promptCollectionFilter === 'all'
      ? Object.keys(collectionPrompts)
      : [promptCollectionFilter];

    return (
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, flexWrap: 'wrap', gap: 2 }}>
          <Typography variant="h4">Prompt Management</Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <FormControl sx={{ minWidth: 220 }}>
              <InputLabel id="prompt-collection-filter-label">Collection</InputLabel>
              <Select
                labelId="prompt-collection-filter-label"
                value={promptCollectionFilter}
                label="Collection"
                onChange={handlePromptCollectionFilterChange}
              >
                <MenuItem value="all">All Collections</MenuItem>
                {collectionOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => openPromptDialog('create')}
            >
              Create Prompt
            </Button>
          </Box>
        </Box>

        {filteredCollectionIds.length === 0 ? (
          <Card>
            <CardContent sx={{ textAlign: 'center', py: 6 }}>
              <PromptIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h5" gutterBottom>
                No prompts found
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Create your first prompt to customize responses for your collections.
              </Typography>
            </CardContent>
          </Card>
        ) : (
          filteredCollectionIds.map((collectionId) => {
            const prompts = getPromptsForCollection(collectionId);
            if (!prompts.length) return null;
            const collection = resolveCollectionById(collectionId);
            return (
              <Box key={collectionId} sx={{ mb: 4 }}>
                <Typography variant="h5" sx={{ mb: 2 }}>
                  {collection?.name || 'Unassigned Collection'}
                </Typography>
                <Grid container spacing={3}>
                  {prompts.map((prompt) => (
                    <Grid item xs={12} md={6} lg={4} key={prompt.prompt_id}>
                      <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                        <CardHeader
                          title={prompt.name}
                          subheader={prompt.description}
                          action={
                            <Box>
                              {prompt.is_default && (
                                <Chip label="Default" color="primary" size="small" sx={{ mr: 1 }} />
                              )}
                              <Chip
                                label={prompt.is_active ? 'Active' : 'Inactive'}
                                color={prompt.is_active ? 'success' : 'default'}
                                size="small"
                              />
                            </Box>
                          }
                        />
                        <CardContent sx={{ flexGrow: 1 }}>
                          <Typography variant="body2" color="textSecondary" gutterBottom>
                            <strong>Model:</strong> {prompt.model_name}
                          </Typography>
                          <Typography variant="body2" color="textSecondary" gutterBottom>
                            <strong>Max Tokens:</strong> {prompt.max_tokens}
                          </Typography>
                          <Typography variant="body2" color="textSecondary" gutterBottom>
                            <strong>Temperature:</strong> {prompt.temperature}
                          </Typography>
                          <Typography variant="body2" color="textSecondary" gutterBottom>
                            <strong>Usage Count:</strong> {prompt.usage_count || 0}
                          </Typography>
                          {prompt.last_used && (
                            <Typography variant="body2" color="textSecondary">
                              <strong>Last Used:</strong> {new Date(prompt.last_used).toLocaleString()}
                            </Typography>
                          )}
                        </CardContent>
                        <Box sx={{ p: 2, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                          <Button size="small" variant="outlined" onClick={() => openPromptDialog('edit', collectionId, prompt)}>
                            Edit
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            color={prompt.is_active ? 'warning' : 'success'}
                            onClick={() => handleTogglePromptActive(prompt)}
                          >
                            {prompt.is_active ? 'Deactivate' : 'Activate'}
                          </Button>
                          {!prompt.is_default && (
                            <Button size="small" variant="contained" onClick={() => handleSetDefaultPrompt(prompt)}>
                              Set Default
                            </Button>
                          )}
                          <Button size="small" color="error" onClick={() => handleDeletePrompt(prompt)}>
                            Delete
                          </Button>
                        </Box>
                      </Card>
                    </Grid>
                  ))}
                </Grid>
              </Box>
            );
          })
        )}
      </Box>
    );
  };

  // Create Dialog Content
  const CreateDialog = () => (
    <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} maxWidth="md" fullWidth>
      <DialogTitle>
        {dialogType === 'collection' ? 'Create New Collection' : 'Create New User'}
      </DialogTitle>
      <DialogContent>
        <Grid container spacing={2} sx={{ mt: 1 }}>
          {dialogType === 'collection' ? (
            <>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Collection Name"
                  value={newCollection.name}
                  onChange={(e) => handleNewCollectionChange('name', e.target.value)}
                  required
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Description"
                  multiline
                  rows={3}
                  value={newCollection.description}
                  onChange={(e) => setNewCollection({ ...newCollection, description: e.target.value })}
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Website URL"
                  type="url"
                  value={newCollection.website_url}
                  onChange={(e) => setNewCollection({ ...newCollection, website_url: e.target.value })}
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Admin Username"
                  value={newCollection.admin_username}
                  onChange={(e) => setNewCollection({ ...newCollection, admin_username: e.target.value })}
                  required
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Admin Password"
                  type="password"
                  value={newCollection.admin_password}
                  onChange={(e) => setNewCollection({ ...newCollection, admin_password: e.target.value })}
                  required
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Admin Email"
                  type="email"
                  value={newCollection.admin_email}
                  onChange={(e) => setNewCollection({ ...newCollection, admin_email: e.target.value })}
                  required
                />
              </Grid>
            </>
          ) : (
            <>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Username"
                  value={newUser.username}
                  onChange={(e) => handleNewUserChange('username', e.target.value)}
                  required
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Password"
                  type="password"
                  value={newUser.password}
                  onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                  required
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Email"
                  type="email"
                  value={newUser.email}
                  onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                  required
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Full Name"
                  value={newUser.full_name}
                  onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })}
                  required
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel>Role</InputLabel>
                  <Select
                    value={newUser.role}
                    label="Role"
                    onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                  >
                    <MenuItem value="user_admin">User Admin</MenuItem>
                    <MenuItem value="user">Regular User</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth disabled={!dashboardData.collections.length}>
                  <InputLabel>Collection</InputLabel>
                  <Select
                    value={newUser.collection_id || ''}
                    label="Collection"
                    onChange={(e) => setNewUser({ ...newUser, collection_id: e.target.value })}
                    required
                  >
                    {dashboardData.collections.map((collection) => (
                      <MenuItem key={collection.collection_id} value={collection.collection_id}>
                        {collection.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
            </>
          )}
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
        <Button
          variant="contained"
          onClick={dialogType === 'collection' ? handleCreateCollection : handleCreateUser}
        >
          Create
        </Button>
      </DialogActions>
    </Dialog>
  );

  const renderContent = () => {
    if (loading) return <LinearProgress />;

    switch (activeTab) {
      case 'overview':
        return <OverviewTab />;
      case 'collections':
        return <CollectionsTab />;
      case 'files':
        return (
          <FilesTab
            collections={dashboardData.collections}
            selectedCollectionId={selectedCollectionId}
            onCollectionChange={setSelectedCollectionId}
            onFilesLoaded={setCollectionFiles}
          />
        );
      case 'users':
        return <UsersTab />;
      case 'prompts':
        return <PromptsTab />;
      case 'chat':
        return <ChatTab />;
      default:
        return <OverviewTab />;
    }
  };

  const ChatTab = () => {
    const collections = dashboardData.collections;
    const promptsForCollection = chatCollectionId
      ? dashboardData.prompts.filter((prompt) => prompt.collection_id === chatCollectionId)
      : [];
    const defaultPrompt = promptsForCollection.find((prompt) => prompt.is_default) || promptsForCollection[0];

    return (
      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Chat Test Bench
              </Typography>
              <Typography variant="body2" color="textSecondary" gutterBottom>
                Select a collection to test retrieval and prompt configuration.
              </Typography>

              <FormControl fullWidth margin="normal">
                <InputLabel>Collection</InputLabel>
                <Select
                  value={chatCollectionId}
                  label="Collection"
                  onChange={(event) => setChatCollectionId(event.target.value)}
                >
                  {collections.map((collection) => (
                    <MenuItem key={collection.collection_id} value={collection.collection_id}>
                      {collection.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {chatCollectionId && (
                <Box mt={2}>
                  <Typography variant="subtitle2" gutterBottom>
                    Active Prompt Details
                  </Typography>
                  {defaultPrompt ? (
                    <Box>
                      <Typography variant="body2"><strong>Name:</strong> {defaultPrompt.name}</Typography>
                      <Typography variant="body2"><strong>Model:</strong> {defaultPrompt.model_name}</Typography>
                      <Typography variant="body2"><strong>Temperature:</strong> {defaultPrompt.temperature}</Typography>
                      <Typography variant="body2"><strong>Max Tokens:</strong> {defaultPrompt.max_tokens}</Typography>
                    </Box>
                  ) : (
                    <Typography variant="body2" color="textSecondary">
                      No prompts configured for this collection yet.
                    </Typography>
                  )}
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={8}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ height: '100%' }}>
              <ChatWindow collectionId={chatCollectionId} key={chatCollectionId || 'no-collection'} />
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    );
  };

  const drawerWidth = 240;

  return (
    <Box sx={{ display: 'flex' }}>
      {/* Snackbar Notification */}
      <Snackbar
        open={notification.open}
        autoHideDuration={6000}
        onClose={handleCloseNotification}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Alert onClose={handleCloseNotification} severity={notification.severity} sx={{ width: '100%' }}>
          {notification.message}
        </Alert>
      </Snackbar>

      {/* Create Dialog */}
      <CreateDialog />
      <PromptDialog />
      <EditCollectionDialog />
      <EditUserDialog />
      <ChangeUserPasswordDialog />
      <ChangeSelfPasswordDialog />

      {/* App Bar */}
      <AppBar
        position="fixed"
        sx={{
          width: { sm: `calc(100% - ${drawerWidth}px)` },
          ml: { sm: `${drawerWidth}px` },
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { sm: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            {menuItems.find(item => item.id === activeTab)?.label || 'Dashboard'}
          </Typography>
          <IconButton color="inherit">
            <AccountCircle />
          </IconButton>
          <Typography variant="body2" sx={{ ml: 1 }}>
            {localStorage.getItem('username') || 'Super Admin'}
          </Typography>
          <Button color="inherit" onClick={openSelfPasswordDialog} sx={{ ml: 2 }}>
            Change Password
          </Button>
          <IconButton color="inherit" onClick={onLogout} sx={{ ml: 2 }}>
            <LogoutIcon />
          </IconButton>
        </Toolbar>
      </AppBar>

      {/* Sidebar Drawer */}
      <Box
        component="nav"
        sx={{ width: { sm: drawerWidth }, flexShrink: { sm: 0 } }}
      >
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', sm: 'none' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', sm: 'block' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>

      {/* Main Content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { sm: `calc(100% - ${drawerWidth}px)` },
        }}
      >
        <Toolbar />
        <Container maxWidth="xl">
          {renderContent()}
        </Container>
      </Box>
    </Box>
  );
};

export default SuperAdminDashboard;