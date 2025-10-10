import { useState, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { DashboardLayout } from '@/components/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Plus,
  Pencil,
  Trash2,
  Users,
  Search,
  Loader2,
  Database,
  Upload,
  Download,
  FileCode,
} from 'lucide-react';
import { User, UserRole, FileItem, Prompt, Collection } from '@/types/auth';
import { toast } from 'sonner';
import { apiGet, apiPost, apiPut, apiDelete, apiUpload } from '@/utils/api';

type CollectionSummary = {
  collection_id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
};

type UploadStatus = 'pending' | 'success' | 'error';

export default function UserAdminDashboard() {
  const { user } = useAuth();

  const [collection, setCollection] = useState<Collection | null>(null);
  const [selectedCollectionId, setSelectedCollectionId] = useState<string>('');
  const [collectionDetails, setCollectionDetails] = useState<Collection | null>(null);
  const [knowledgeTab, setKnowledgeTab] = useState<'files' | 'prompts'>('files');

  const [users, setUsers] = useState<User[]>([]);
  const [isLoadingCollections, setIsLoadingCollections] = useState(true);
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);

  const [files, setFiles] = useState<FileItem[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);

  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [promptsLoading, setPromptsLoading] = useState(false);

  const [userSearchTerm, setUserSearchTerm] = useState('');
  const [fileSearchTerm, setFileSearchTerm] = useState('');
  const [promptSearchTerm, setPromptSearchTerm] = useState('');

  const [isUserDialogOpen, setIsUserDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);

  const [isFileDialogOpen, setIsFileDialogOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<Record<string, UploadStatus>>({});

  const [isPromptDialogOpen, setIsPromptDialogOpen] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<Prompt | null>(null);

  const [userFormData, setUserFormData] = useState({
    username: '',
    email: '',
    full_name: '',
    password: '',
    role: 'user' as UserRole,
  });

  const [promptFormData, setPromptFormData] = useState({
    name: '',
    description: '',
    content: '',
    is_active: true,
    is_default: false,
  });

  const fetchCollectionDetails = useCallback(
    async (collectionId: string) => {
      if (!user?.access_token || !collectionId) {
        setCollectionDetails(null);
        setCollection(null);
        return;
      }

      try {
        const response = await apiGet(
          `${import.meta.env.VITE_API_BASE_URL}/collections/${collectionId}`,
          user.access_token,
          false
        );

        if (response.ok) {
          const data: Collection = await response.json();
          setCollectionDetails(data);
          setCollection(data);
        } else {
          setCollectionDetails(null);
          setCollection(null);
        }
      } catch (error) {
        console.debug('Failed to fetch collection details', error);
        setCollectionDetails(null);
        setCollection(null);
      }
    },
    [user?.access_token]
  );

  const fetchCollections = useCallback(async () => {
    if (!user?.access_token) return;

    setIsLoadingCollections(true);
    try {
      const response = await apiGet(
        `${import.meta.env.VITE_API_BASE_URL}/collections/summary`,
        user.access_token,
        false
      );

      if (!response.ok) {
        throw new Error('Failed to load knowledge bases');
      }

      const data: CollectionSummary[] = await response.json();

      if (data.length > 0) {
        const target = data[0];
        setSelectedCollectionId(target.collection_id);
        await fetchCollectionDetails(target.collection_id);
      } else {
        setSelectedCollectionId('');
        setCollection(null);
      }
    } catch (error) {
      console.error('Failed to load knowledge bases', error);
      toast.error('Unable to load knowledge bases.');
      setSelectedCollectionId('');
      setCollection(null);
    } finally {
      setIsLoadingCollections(false);
    }
  }, [user?.access_token, fetchCollectionDetails]);

  const fetchUsers = useCallback(async () => {
    if (!selectedCollectionId || !user?.access_token) {
      setUsers([]);
      setIsLoadingUsers(false);
      return;
    }

    setIsLoadingUsers(true);
    try {
      const response = await apiGet(
        `${import.meta.env.VITE_API_BASE_URL}/users/?collection_id=${selectedCollectionId}`,
        user.access_token
      );

      if (response.ok) {
        const data: User[] = await response.json();
        setUsers(data);
      } else {
        setUsers([]);
      }
    } catch (error) {
      console.debug('Failed to fetch users', error);
      setUsers([]);
    } finally {
      setIsLoadingUsers(false);
    }
  }, [selectedCollectionId, user?.access_token]);

  const fetchFiles = useCallback(async () => {
    if (!selectedCollectionId || !user?.access_token) {
      setFiles([]);
      return;
    }

    setFilesLoading(true);
    try {
      const response = await apiGet(
        `${import.meta.env.VITE_API_BASE_URL}/files/list?collection_id=${selectedCollectionId}`,
        user.access_token
      );

      if (response.ok) {
        const data: FileItem[] = await response.json();
        setFiles(data);
      } else {
        setFiles([]);
      }
    } catch (error) {
      console.debug('Failed to fetch files', error);
      setFiles([]);
    } finally {
      setFilesLoading(false);
    }
  }, [selectedCollectionId, user?.access_token]);

  const fetchPrompts = useCallback(async () => {
    if (!selectedCollectionId || !user?.access_token) {
      setPrompts([]);
      return;
    }

    setPromptsLoading(true);
    try {
      const response = await apiGet(
        `${import.meta.env.VITE_API_BASE_URL}/prompts/?collection_id=${selectedCollectionId}`,
        user.access_token
      );

      if (response.ok) {
        const data: Prompt[] = await response.json();
        setPrompts(data);
      } else {
        setPrompts([]);
      }
    } catch (error) {
      console.debug('Failed to fetch prompts', error);
      setPrompts([]);
    } finally {
      setPromptsLoading(false);
    }
  }, [selectedCollectionId, user?.access_token]);

  useEffect(() => {
    fetchCollections();
  }, [fetchCollections]);

  const location = useLocation();

  const isUsersRoute = location.pathname.includes('/useradmin/users');
  const activeSection: 'users' | 'knowledge_base' = isUsersRoute ? 'users' : 'knowledge_base';

  useEffect(() => {
    if (!selectedCollectionId) {
      setCollectionDetails(null);
      setCollection(null);
      setUsers([]);
      setFiles([]);
      setPrompts([]);
      return;
    }

    void fetchCollectionDetails(selectedCollectionId);

    if (activeSection === 'users') {
      void fetchUsers();
    }

    if (activeSection === 'knowledge_base') {
      if (knowledgeTab === 'files') {
        void fetchFiles();
      }

      if (knowledgeTab === 'prompts') {
        void fetchPrompts();
      }
    }
  }, [selectedCollectionId, activeSection, knowledgeTab, fetchCollectionDetails, fetchUsers, fetchFiles, fetchPrompts]);

  const handleKnowledgeTabChange = (value: string) => {
    if (value === 'files' || value === 'prompts') {
      setKnowledgeTab(value);
    }
  };

  const openUserDialog = (userToEdit?: User) => {
    if (userToEdit) {
      setEditingUser(userToEdit);
      setUserFormData({
        username: userToEdit.username,
        email: userToEdit.email || '',
        full_name: userToEdit.full_name || '',
        password: '',
        role: (userToEdit.role as UserRole) || 'user',
      });
    } else {
      setEditingUser(null);
      setUserFormData({
        username: '',
        email: '',
        full_name: '',
        password: '',
        role: 'user',
      });
    }

    setIsUserDialogOpen(true);
  };

  const closeUserDialog = () => {
    setIsUserDialogOpen(false);
    setEditingUser(null);
    setUserFormData({
      username: '',
      email: '',
      full_name: '',
      password: '',
      role: 'user',
    });
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedCollectionId) {
      toast.error('Select a knowledge base before adding users.');
      return;
    }

    try {
      const response = await apiPost(
        `${import.meta.env.VITE_API_BASE_URL}/users/`,
        {
          username: userFormData.username,
          email: userFormData.email,
          full_name: userFormData.full_name,
          password: userFormData.password,
          role: 'user',
          collection_ids: [selectedCollectionId],
        },
        user?.access_token
      );

      if (!response.ok) {
        throw new Error('Failed to create user');
      }

      toast.success('User created successfully');
      closeUserDialog();
      fetchUsers();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create user');
    }
  };

  const handleUpdateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingUser) return;

    try {
      const payload: Record<string, unknown> = {
        email: userFormData.email,
        full_name: userFormData.full_name,
        role: 'user',
        collection_ids: selectedCollectionId ? [selectedCollectionId] : [],
      };

      if (userFormData.password && (!editingUser || editingUser.user_id !== user?.user_id)) {
        payload.password = userFormData.password;
      }

      const response = await apiPut(
        `${import.meta.env.VITE_API_BASE_URL}/users/${editingUser.user_id}`,
        payload,
        user?.access_token
      );

      if (!response.ok) {
        throw new Error('Failed to update user');
      }

      toast.success('User updated successfully');
      closeUserDialog();
      fetchUsers();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update user');
    }
  };

  const handleDeleteUser = async (userId: string, usernameToDelete: string) => {
    if (usernameToDelete === user?.username) {
      toast.error('You cannot delete your own account.');
      return;
    }

    if (!confirm('Are you sure you want to delete this user?')) {
      return;
    }

    try {
      const response = await apiDelete(
        `${import.meta.env.VITE_API_BASE_URL}/users/${userId}`,
        user?.access_token
      );

      if (!response.ok) {
        throw new Error('Failed to delete user');
      }

      toast.success('User deleted successfully');
      fetchUsers();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to delete user');
    }
  };

  const closeFileDialog = () => {
    setIsFileDialogOpen(false);
    setIsUploading(false);
    setUploadProgress({});
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = event.target.files;

    if (!selectedCollectionId || !selectedFiles || selectedFiles.length === 0) {
      return;
    }

    setIsUploading(true);
    const filesArray = Array.from(selectedFiles);
    const progress: Record<string, UploadStatus> = {};
    filesArray.forEach((file) => {
      progress[file.name] = 'pending';
    });
    setUploadProgress(progress);

    const formData = new FormData();
    filesArray.forEach((file) => {
      formData.append('uploaded_files', file);
    });
    formData.append('collection_id', selectedCollectionId);

    try {
      const response = await apiUpload(
        `${import.meta.env.VITE_API_BASE_URL}/files/upload`,
        formData,
        user?.access_token,
        false
      );

      if (!response.ok) {
        let errorMessage = 'Failed to upload files';
        try {
          const errorData = await response.json();
          if (typeof errorData?.detail === 'string') {
            errorMessage = errorData.detail;
          }
        } catch (parseError) {
          console.debug('Failed to parse upload error response', parseError);
        }

        setUploadProgress((prev) => {
          const updated: Record<string, UploadStatus> = {};
          Object.keys(prev).forEach((name) => {
            updated[name] = 'error';
          });
          return updated;
        });

        throw new Error(errorMessage);
      }

      const uploadedFiles: FileItem[] = await response.json();
      const uploadedNames = new Set(uploadedFiles.map((file) => file.file_name));

      setUploadProgress((prev) => {
        const updated: Record<string, UploadStatus> = {};
        Object.keys(prev).forEach((name) => {
          updated[name] = uploadedNames.size === 0 || uploadedNames.has(name) ? 'success' : 'success';
        });
        return updated;
      });

      toast.success(
        `Uploaded ${uploadedFiles.length}/${filesArray.length} file${filesArray.length > 1 ? 's' : ''}`
      );

      await fetchFiles();

      event.target.value = '';
      closeFileDialog();
    } catch (error) {
      console.error('Failed to upload files', error);
      toast.error(error instanceof Error ? error.message : 'Failed to upload files');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDownloadFile = async (fileId: string, fileName: string) => {
    try {
      const response = await apiGet(
        `${import.meta.env.VITE_API_BASE_URL}/files/download/${fileId}`,
        user?.access_token
      );

      if (!response.ok) {
        throw new Error('Failed to download file');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = fileName;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      toast.error('Failed to download file');
    }
  };

  const handleDeleteFile = async (fileId: string) => {
    if (!confirm('Are you sure you want to delete this file?')) {
      return;
    }

    try {
      const response = await apiDelete(
        `${import.meta.env.VITE_API_BASE_URL}/files/${fileId}`,
        user?.access_token
      );

      if (!response.ok) {
        throw new Error('Failed to delete file');
      }

      toast.success('File deleted successfully');
      fetchFiles();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to delete file');
    }
  };

  const openPromptDialog = (promptToEdit?: Prompt) => {
    if (promptToEdit) {
      setEditingPrompt(promptToEdit);
      setPromptFormData({
        name: promptToEdit.name,
        description: promptToEdit.description || '',
        content: promptToEdit.system_prompt,
        is_active: promptToEdit.is_active,
        is_default: promptToEdit.is_default,
      });
    } else {
      setEditingPrompt(null);
      setPromptFormData({
        name: '',
        description: '',
        content: '',
        is_active: true,
        is_default: false,
      });
    }

    setIsPromptDialogOpen(true);
  };

  const closePromptDialog = () => {
    setEditingPrompt(null);
    setIsPromptDialogOpen(false);
    setPromptFormData({
      name: '',
      description: '',
      content: '',
      is_active: true,
      is_default: false,
    });
  };

  const handleCreatePrompt = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedCollectionId) {
      toast.error('Select a knowledge base before creating prompts.');
      return;
    }

    try {
      const response = await apiPost(
        `${import.meta.env.VITE_API_BASE_URL}/prompts/`,
        {
          name: promptFormData.name,
          description: promptFormData.description,
          system_prompt: promptFormData.content,
          is_active: promptFormData.is_active,
          is_default: promptFormData.is_default,
          collection_id: selectedCollectionId,
        },
        user?.access_token
      );

      if (!response.ok) {
        throw new Error('Failed to create prompt');
      }

      toast.success('Prompt created successfully');
      closePromptDialog();
      fetchPrompts();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create prompt');
    }
  };

  const handleUpdatePrompt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingPrompt) return;

    try {
      const response = await apiPut(
        `${import.meta.env.VITE_API_BASE_URL}/prompts/${editingPrompt.prompt_id}`,
        {
          name: promptFormData.name,
          description: promptFormData.description,
          system_prompt: promptFormData.content,
          is_active: promptFormData.is_active,
          is_default: promptFormData.is_default,
        },
        user?.access_token
      );

      if (!response.ok) {
        throw new Error('Failed to update prompt');
      }

      toast.success('Prompt updated successfully');
      closePromptDialog();
      fetchPrompts();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update prompt');
    }
  };

  const handleDeletePrompt = async (promptId: string) => {
    if (!confirm('Are you sure you want to delete this prompt?')) {
      return;
    }

    try {
      const response = await apiDelete(
        `${import.meta.env.VITE_API_BASE_URL}/prompts/${promptId}`,
        user?.access_token
      );

      if (!response.ok) {
        throw new Error('Failed to delete prompt');
      }

      toast.success('Prompt deleted successfully');
      fetchPrompts();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to delete prompt');
    }
  };

  const filteredUsers = users.filter((userItem) => {
    const query = userSearchTerm.toLowerCase();
    return (
      userItem.username.toLowerCase().includes(query) ||
      (userItem.full_name || '').toLowerCase().includes(query) ||
      (userItem.email || '').toLowerCase().includes(query)
    );
  });

  const isEditingSelf = editingUser?.user_id === user?.user_id;

  const filteredFiles = files.filter((file) =>
    file.file_name?.toLowerCase().includes(fileSearchTerm.toLowerCase())
  );

  const filteredPrompts = prompts.filter((prompt) =>
    prompt.name?.toLowerCase().includes(promptSearchTerm.toLowerCase()) ||
    prompt.description?.toLowerCase().includes(promptSearchTerm.toLowerCase()) ||
    prompt.system_prompt?.toLowerCase().includes(promptSearchTerm.toLowerCase())
  );

  const formatFileSize = (bytes: number) => {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const index = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, index)).toFixed(2)} ${units[index]}`;
  };

  const formatDate = (value?: string | null) => {
    if (!value) return '—';
    try {
      return new Date(value).toLocaleDateString();
    } catch {
      return '—';
    }
  };

  const statusBadgeClass = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'processing':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-red-100 text-red-800';
    }
  };

  if (isLoadingCollections) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {collection ? (
          <Card>
            <CardHeader>
              <CardTitle>
              {collection.name ? `  ${collection.name}` : ''} Knowledge Base
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-1 text-sm text-muted-foreground">
                <p>
                  <span className="font-medium text-foreground">Name:</span> {collection.name}
                </p>
                <p>
                  <span className="font-medium text-foreground">Status:</span> {collection.is_active ? 'Active' : 'Inactive'}
                </p>
                <p>
                  <span className="font-medium text-foreground">Description:</span> {collectionDetails?.description || collection.description || 'No description provided.'}
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Knowledge Base</CardTitle>
              <CardDescription>No knowledge base assignment found.</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground">
                Please contact a super admin to assign a knowledge base to your account.
              </p>
            </CardContent>
          </Card>
        )}

        {collection && activeSection === 'users' && (
          <>
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Users className="h-5 w-5" />
                      Users
                    </CardTitle>
                   
                  </div>
                  <Button onClick={() => openUserDialog()} disabled={isLoadingUsers}>
                    <Plus className="mr-2 h-4 w-4" />
                    Add User
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center space-x-4 mb-4">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search users..."
                      value={userSearchTerm}
                      onChange={(e) => setUserSearchTerm(e.target.value)}
                      className="pl-10 w-64"
                    />
                  </div>
                </div>

                {isLoadingUsers ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  </div>
                ) : filteredUsers.length === 0 ? (
                  <div className="py-8 text-center text-muted-foreground">
                    {userSearchTerm ? 'No users match your search.' : 'No users assigned yet.'}
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Username</TableHead>
                        <TableHead>Full Name</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Role</TableHead>
                        <TableHead>Created</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredUsers.map((userItem) => (
                        <TableRow key={userItem.user_id}>
                          <TableCell className="font-medium">{userItem.username}</TableCell>
                          <TableCell>{userItem.full_name || '—'}</TableCell>
                          <TableCell>{userItem.email || '—'}</TableCell>
                          <TableCell className="capitalize">{userItem.role}</TableCell>
                          <TableCell className="text-muted-foreground">{formatDate(userItem.created_at)}</TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end space-x-2">
                              <Button variant="ghost" size="sm" onClick={() => openUserDialog(userItem)}>
                                <Pencil className="h-4 w-4 mr-1" />
                                Edit
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-destructive hover:text-destructive"
                                onClick={() => handleDeleteUser(userItem.user_id, userItem.username)}
                                disabled={userItem.username === user?.username}
                              >
                                <Trash2 className="h-4 w-4 mr-1" />
                                Delete
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>

            <Dialog open={isUserDialogOpen} onOpenChange={setIsUserDialogOpen}>
              <DialogContent className="max-w-md">
                <form onSubmit={editingUser ? handleUpdateUser : handleCreateUser}>
                  <DialogHeader>
                    <DialogTitle>{editingUser ? 'Edit User' : 'Add User'}</DialogTitle>
                    <DialogDescription>
                      {editingUser
                        ? 'Update user details within this knowledge base.'
                        : 'Create a new user scoped to this knowledge base.'}
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <Label htmlFor="username">
                        Username *{' '}
                        {editingUser && (
                          <span className="text-xs text-muted-foreground">(cannot be changed)</span>
                        )}
                      </Label>
                      <Input
                        id="username"
                        value={userFormData.username}
                        onChange={(e) => setUserFormData({ ...userFormData, username: e.target.value })}
                        required
                        disabled={Boolean(editingUser)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email">Email *</Label>
                      <Input
                        id="email"
                        type="email"
                        value={userFormData.email}
                        onChange={(e) => setUserFormData({ ...userFormData, email: e.target.value })}
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="full_name">Full Name *</Label>
                      <Input
                        id="full_name"
                        value={userFormData.full_name}
                        onChange={(e) => setUserFormData({ ...userFormData, full_name: e.target.value })}
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="password">
                        Password
                        {editingUser
                          ? isEditingSelf
                            ? ' (manage from Settings)'
                            : ' (optional — retain existing if left blank)'
                          : ' *'}
                      </Label>
                      <Input
                        id="password"
                        type="password"
                        value={userFormData.password}
                        onChange={(e) => setUserFormData({ ...userFormData, password: e.target.value })}
                        required={!editingUser}
                        disabled={isEditingSelf}
                      />
                      {isEditingSelf && (
                        <p className="text-xs text-muted-foreground">
                          Update your password from the Settings page.
                        </p>
                      )}
                    </div>
                  </div>
                  <DialogFooter>
                    <Button type="button" variant="outline" onClick={closeUserDialog}>
                      Cancel
                    </Button>
                    <Button type="submit">{editingUser ? 'Save Changes' : 'Create User'}</Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          </>
        )}

        {collection && activeSection === 'knowledge_base' && (
          <Tabs value={knowledgeTab} onValueChange={handleKnowledgeTabChange} className="space-y-6">
            <TabsList>
              <TabsTrigger value="files">Files</TabsTrigger>
              <TabsTrigger value="prompts">Prompts</TabsTrigger>
            </TabsList>

            <TabsContent value="files" className="space-y-6">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <Database className="h-5 w-5" />
                        Files
                      </CardTitle>
                      
                    </div>
                    <Button onClick={() => setIsFileDialogOpen(true)}>
                      <Upload className="mr-2 h-4 w-4" />
                      Upload File
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center space-x-4 mb-4">
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                      <Input
                        placeholder="Search files..."
                        value={fileSearchTerm}
                        onChange={(e) => setFileSearchTerm(e.target.value)}
                        className="pl-10 w-64"
                      />
                    </div>
                  </div>

                  {filesLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    </div>
                  ) : filteredFiles.length === 0 ? (
                    <div className="py-8 text-center text-muted-foreground">
                      {fileSearchTerm ? 'No files match your search.' : 'No files uploaded yet.'}
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>File Name</TableHead>
                          <TableHead>Size</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Uploaded</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filteredFiles.map((file) => (
                          <TableRow key={file.file_id}>
                            <TableCell className="font-medium">{file.file_name}</TableCell>
                            <TableCell>{formatFileSize(file.file_size)}</TableCell>
                            <TableCell>
                              <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${statusBadgeClass(file.processing_status)}`}>
                                {file.processing_status}
                              </span>
                            </TableCell>
                            <TableCell className="text-muted-foreground">{formatDate(file.upload_timestamp)}</TableCell>
                            <TableCell className="text-right">
                              <div className="flex items-center justify-end space-x-2">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleDownloadFile(file.file_id, file.file_name)}
                                  disabled={file.processing_status !== 'completed'}
                                >
                                  <Download className="h-4 w-4 mr-1" />
                                  Download
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="text-destructive hover:text-destructive"
                                  onClick={() => handleDeleteFile(file.file_id)}
                                >
                                  <Trash2 className="h-4 w-4 mr-1" />
                                  Delete
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>

              <Dialog open={isFileDialogOpen} onOpenChange={setIsFileDialogOpen}>
                <DialogContent className="max-w-lg">
                  <DialogHeader>
                    <DialogTitle>Upload File</DialogTitle>
                    <DialogDescription>
                      Upload documents to this knowledge base (PDF, DOC, DOCX, PPTX, XLSX, TXT, CSV – max 10MB each).
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="file-upload">Choose Files</Label>
                      <Input
                        id="file-upload"
                        type="file"
                        multiple
                        accept=".pdf,.doc,.docx,.pptx,.xlsx,.txt,.csv"
                        onChange={handleFileUpload}
                        disabled={isUploading}
                      />
                    </div>
                    {isUploading && (
                      <div className="space-y-2">
                        <Label className="text-sm font-medium">Upload Progress</Label>
                        <div className="space-y-1 text-sm">
                          {Object.entries(uploadProgress).map(([fileName, status]) => (
                            <div key={fileName} className="flex items-center justify-between">
                              <span className="truncate max-w-xs" title={fileName}>
                                {fileName}
                              </span>
                              <span
                                className={`text-xs font-semibold ${
                                  status === 'success'
                                    ? 'text-green-600'
                                    : status === 'error'
                                    ? 'text-red-600'
                                    : 'text-muted-foreground'
                                }`}
                              >
                                {status === 'pending' && 'Uploading...'}
                                {status === 'success' && 'Uploaded'}
                                {status === 'error' && 'Failed'}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  <DialogFooter>
                    <Button type="button" variant="outline" onClick={closeFileDialog} disabled={isUploading}>
                      Cancel
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </TabsContent>

            <TabsContent value="prompts" className="space-y-6">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <FileCode className="h-5 w-5" />
                        Prompts
                      </CardTitle>
                      <CardDescription>Manage custom prompts for this knowledge base.</CardDescription>
                    </div>
                    <Button onClick={() => openPromptDialog()}>
                      <Plus className="mr-2 h-4 w-4" />
                      Create Prompt
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center space-x-4 mb-4">
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                      <Input
                        placeholder="Search prompts..."
                        value={promptSearchTerm}
                        onChange={(e) => setPromptSearchTerm(e.target.value)}
                        className="pl-10 w-64"
                      />
                    </div>
                  </div>

                  {promptsLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    </div>
                  ) : filteredPrompts.length === 0 ? (
                    <div className="py-8 text-center text-muted-foreground">
                      {promptSearchTerm ? 'No prompts match your search.' : 'No prompts created yet.'}
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Name</TableHead>
                          <TableHead>Description</TableHead>
                          <TableHead>Active</TableHead>
                          <TableHead>Default</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filteredPrompts.map((prompt) => (
                          <TableRow key={prompt.prompt_id}>
                            <TableCell className="font-medium">{prompt.name}</TableCell>
                            <TableCell>{prompt.description || '—'}</TableCell>
                            <TableCell>{prompt.is_active ? 'Yes' : 'No'}</TableCell>
                            <TableCell>{prompt.is_default ? 'Yes' : 'No'}</TableCell>
                            <TableCell className="text-right">
                              <div className="flex items-center justify-end space-x-2">
                                <Button variant="ghost" size="sm" onClick={() => openPromptDialog(prompt)}>
                                  <Pencil className="h-4 w-4 mr-1" />
                                  Edit
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="text-destructive hover:text-destructive"
                                  onClick={() => handleDeletePrompt(prompt.prompt_id)}
                                >
                                  <Trash2 className="h-4 w-4 mr-1" />
                                  Delete
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>

              <Dialog open={isPromptDialogOpen} onOpenChange={setIsPromptDialogOpen}>
                <DialogContent className="max-w-2xl">
                  <form onSubmit={editingPrompt ? handleUpdatePrompt : handleCreatePrompt}>
                    <DialogHeader>
                      <DialogTitle>{editingPrompt ? 'Edit Prompt' : 'Create Prompt'}</DialogTitle>
                      <DialogDescription>
                        {editingPrompt
                          ? 'Update the existing prompt configuration.'
                          : 'Create a new prompt tailored to this knowledge base.'}
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Label htmlFor="prompt-name">Prompt Name *</Label>
                        <Input
                          id="prompt-name"
                          value={promptFormData.name}
                          onChange={(e) => setPromptFormData({ ...promptFormData, name: e.target.value })}
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="prompt-description">Description</Label>
                        <Input
                          id="prompt-description"
                          value={promptFormData.description}
                          onChange={(e) => setPromptFormData({ ...promptFormData, description: e.target.value })}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="prompt-content">Prompt Content *</Label>
                        <Textarea
                          id="prompt-content"
                          rows={6}
                          value={promptFormData.content}
                          onChange={(e) => setPromptFormData({ ...promptFormData, content: e.target.value })}
                          required
                        />
                      </div>
                      <div className="flex flex-col space-y-3 sm:flex-row sm:space-y-0 sm:space-x-6">
                        <label className="flex items-center space-x-2 text-sm">
                          <input
                            type="checkbox"
                            checked={promptFormData.is_active}
                            onChange={(e) => setPromptFormData({ ...promptFormData, is_active: e.target.checked })}
                          />
                          <span>Active</span>
                        </label>
                        <label className="flex items-center space-x-2 text-sm">
                          <input
                            type="checkbox"
                            checked={promptFormData.is_default}
                            onChange={(e) => setPromptFormData({ ...promptFormData, is_default: e.target.checked })}
                          />
                          <span>Set as default</span>
                        </label>
                      </div>
                    </div>
                    <DialogFooter>
                      <Button type="button" variant="outline" onClick={closePromptDialog}>
                        Cancel
                      </Button>
                      <Button type="submit">{editingPrompt ? 'Save Changes' : 'Create Prompt'}</Button>
                    </DialogFooter>
                  </form>
                </DialogContent>
              </Dialog>
            </TabsContent>
          </Tabs>
        )}
      </div>
    </DashboardLayout>
  );
}

