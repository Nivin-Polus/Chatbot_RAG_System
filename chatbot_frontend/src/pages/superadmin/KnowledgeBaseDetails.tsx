import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { DashboardLayout } from '@/components/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
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
  ArrowLeft, 
  Upload, 
  Download, 
  Trash2, 
  Search, 
  Loader2, 
  Plus, 
  Pencil, 
  Database,
  FileCode,
  Settings
} from 'lucide-react';
import { Collection, FileItem, Prompt } from '@/types/auth';
import { toast } from 'sonner';
import { apiGet, apiPost, apiPut, apiDelete, apiUpload } from '@/utils/api';

export default function KnowledgeBaseDetails() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const [collection, setCollection] = useState<Collection | null>(null);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filesLoading, setFilesLoading] = useState(false);
  const [promptsLoading, setPromptsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [editFormData, setEditFormData] = useState({
    name: '',
    description: '',
    website_url: '',
    admin_email: '',
    is_active: true,
  });
  const getInitialTab = () => {
    const tabParam = searchParams.get('tab');
    if (tabParam === 'files' || tabParam === 'prompts') {
      return tabParam;
    }
    return 'overview';
  };

  const [activeTab, setActiveTab] = useState<string>(getInitialTab);

  // File management state
  const [isFileDialogOpen, setIsFileDialogOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<Record<string, 'pending' | 'success' | 'error'>>({});

  // Prompt management state
  const [isPromptDialogOpen, setIsPromptDialogOpen] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<Prompt | null>(null);
  const [promptFormData, setPromptFormData] = useState({
    name: '',
    description: '',
    content: '',
    is_active: true,
    is_default: false,
  });

  const fetchCollection = useCallback(async () => {
    if (!id) return;
    
    try {
      const response = await apiGet(
        `${import.meta.env.VITE_API_BASE_URL}/collections/${id}`,
        user?.access_token
      );
      
      if (response.ok) {
        const data = await response.json();
        setCollection(data);
      } else {
        toast.error('Failed to fetch knowledge base details');
        navigate('/superadmin');
      }
    } catch (error) {
      toast.error('Failed to fetch knowledge base details');
      navigate('/superadmin');
    } finally {
      setIsLoading(false);
    }
  }, [id, user?.access_token, navigate]);

  useEffect(() => {
    fetchCollection();
  }, [fetchCollection]);

  useEffect(() => {
    const tabParam = searchParams.get('tab');
    if (tabParam && (tabParam === 'overview' || tabParam === 'files' || tabParam === 'prompts') && tabParam !== activeTab) {
      setActiveTab(tabParam);
    }
  }, [searchParams, activeTab]);

  useEffect(() => {
    if (activeTab === 'files' && id && user?.access_token) {
      const fetchFiles = async () => {
        setFilesLoading(true);
        try {
          const response = await apiGet(
            `${import.meta.env.VITE_API_BASE_URL}/files/list?collection_id=${id}`,
            user?.access_token
          );
          
          if (response.ok) {
            const data = await response.json();
            setFiles(data);
          }
        } catch (error) {
          console.error('Failed to fetch files:', error);
        } finally {
          setFilesLoading(false);
        }
      };

      fetchFiles();
    }
  }, [activeTab, id, user?.access_token]);

  useEffect(() => {
    if (activeTab === 'prompts' && id && user?.access_token) {
      const fetchPrompts = async () => {
        setPromptsLoading(true);
        try {
          const response = await apiGet(
            `${import.meta.env.VITE_API_BASE_URL}/prompts/?collection_id=${id}`,
            user?.access_token
          );
          
          if (response.ok) {
            const data = await response.json();
            setPrompts(data);
          }
        } catch (error) {
          console.error('Failed to fetch prompts:', error);
        } finally {
          setPromptsLoading(false);
        }
      };

      fetchPrompts();
    }
  }, [activeTab, id, user?.access_token]);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = event.target.files;
    if (!selectedFiles || selectedFiles.length === 0 || !id) return;

    setIsUploading(true);
    const filesArray = Array.from(selectedFiles);
    const initialProgress: Record<string, 'pending' | 'success' | 'error'> = {};
    filesArray.forEach((file) => {
      initialProgress[file.name] = 'pending';
    });
    setUploadProgress(initialProgress);

    const formData = new FormData();
    filesArray.forEach((file) => {
      formData.append('uploaded_files', file);
    });
    formData.append('collection_id', id);

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
          } else if (Array.isArray(errorData?.detail)) {
            errorMessage = errorData.detail
              .map((item) => (typeof item?.msg === 'string' ? item.msg : '') )
              .filter(Boolean)
              .join('; ') || errorMessage;
          }
        } catch (parseError) {
          console.error('Failed to parse upload error response', parseError);
        }
        setUploadProgress((prev) => {
          const updated: Record<string, 'pending' | 'success' | 'error'> = {};
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
        const updated: Record<string, 'pending' | 'success' | 'error'> = {};
        Object.keys(prev).forEach((name) => {
          updated[name] = uploadedNames.size === 0 || uploadedNames.has(name) ? 'success' : 'success';
        });
        return updated;
      });

      const refreshResponse = await apiGet(
        `${import.meta.env.VITE_API_BASE_URL}/files/list?collection_id=${id}`,
        user?.access_token
      );
      if (refreshResponse.ok) {
        const data = await refreshResponse.json();
        setFiles(data);
      }

      toast.success(
        `Uploaded ${uploadedFiles.length}/${filesArray.length} file${filesArray.length > 1 ? 's' : ''}`
      );

      event.target.value = '';
      setIsFileDialogOpen(false);
    } catch (error) {
      console.error('Failed to upload files', error);
      toast.error(error instanceof Error ? error.message : 'Failed to upload files');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDownload = async (fileId: string, fileName: string) => {
    try {
      const response = await apiGet(
        `${import.meta.env.VITE_API_BASE_URL}/files/download/${fileId}`,
        user?.access_token
      );

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        throw new Error('Download failed');
      }
    } catch (error) {
      toast.error('Failed to download file');
    }
  };

  const handleDeleteFile = async (fileId: string) => {
    if (!confirm('Are you sure you want to delete this file?')) return;

    try {
      const response = await apiDelete(
        `${import.meta.env.VITE_API_BASE_URL}/files/${fileId}`,
        user?.access_token
      );

      if (response.ok) {
        toast.success('File deleted successfully');
        
        // Refresh files
        const refreshResponse = await apiGet(
          `${import.meta.env.VITE_API_BASE_URL}/files/list?collection_id=${id}`,
          user?.access_token
        );
        if (refreshResponse.ok) {
          const data = await refreshResponse.json();
          setFiles(data);
        }
      } else {
        throw new Error('Delete failed');
      }
    } catch (error) {
      toast.error('Failed to delete file');
    }
  };

  const handleCreatePrompt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;

    try {
      const response = await apiPost(
        `${import.meta.env.VITE_API_BASE_URL}/prompts/`,
        {
          name: promptFormData.name,
          description: promptFormData.description,
          system_prompt: promptFormData.content,
          is_active: promptFormData.is_active,
          is_default: promptFormData.is_default,
          collection_id: id,
        },
        user?.access_token
      );

      if (response.ok) {
        toast.success('Prompt created successfully');
        setIsPromptDialogOpen(false);
        setPromptFormData({ name: '', description: '', content: '', is_active: true, is_default: false });
        
        // Refresh prompts
        const refreshResponse = await apiGet(
          `${import.meta.env.VITE_API_BASE_URL}/prompts/?collection_id=${id}`,
          user?.access_token
        );
        if (refreshResponse.ok) {
          const data = await refreshResponse.json();
          setPrompts(data);
        }
      } else {
        throw new Error('Failed to create prompt');
      }
    } catch (error) {
      toast.error('Failed to create prompt');
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

      if (response.ok) {
        toast.success('Prompt updated successfully');
        setIsPromptDialogOpen(false);
        setEditingPrompt(null);
        setPromptFormData({ name: '', description: '', content: '', is_active: true, is_default: false });
        
        // Refresh prompts
        const refreshResponse = await apiGet(
          `${import.meta.env.VITE_API_BASE_URL}/prompts/?collection_id=${id}`,
          user?.access_token
        );
        if (refreshResponse.ok) {
          const data = await refreshResponse.json();
          setPrompts(data);
        }
      } else {
        throw new Error('Failed to update prompt');
      }
    } catch (error) {
      toast.error('Failed to update prompt');
    }
  };

  const handleDeletePrompt = async (promptId: string) => {
    if (!confirm('Are you sure you want to delete this prompt?')) return;

    try {
      const response = await apiDelete(
        `${import.meta.env.VITE_API_BASE_URL}/prompts/${promptId}`,
        user?.access_token
      );

      if (response.ok) {
        toast.success('Prompt deleted successfully');
        
        // Refresh prompts
        const refreshResponse = await apiGet(
          `${import.meta.env.VITE_API_BASE_URL}/prompts/?collection_id=${id}`,
          user?.access_token
        );
        if (refreshResponse.ok) {
          const data = await refreshResponse.json();
          setPrompts(data);
        }
      } else {
        throw new Error('Failed to delete prompt');
      }
    } catch (error) {
      toast.error('Failed to delete prompt');
    }
  };

  const openEditPromptDialog = (prompt: Prompt) => {
    setEditingPrompt(prompt);
      setPromptFormData({
        name: prompt.name,
        description: prompt.description || '',
        content: prompt.system_prompt,
        is_active: prompt.is_active,
        is_default: prompt.is_default,
      });
    setIsPromptDialogOpen(true);
  };

  const closePromptDialog = () => {
    setIsPromptDialogOpen(false);
    setEditingPrompt(null);
    setPromptFormData({ name: '', description: '', content: '', is_active: true, is_default: false });
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const filteredFiles = files.filter(file =>
    file.file_name?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredPrompts = prompts.filter(prompt =>
    prompt.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    prompt.description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    prompt.system_prompt?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleTabChange = (value: string) => {
    setActiveTab(value);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set('tab', value);
    setSearchParams(nextParams, { replace: true });
  };

  const handleOpenEditDialog = () => {
    if (!collection) return;
    setEditFormData({
      name: collection.name ?? '',
      description: collection.description ?? '',
      website_url: collection.website_url ?? '',
      admin_email: collection.admin_email ?? '',
      is_active: collection.is_active ?? true,
    });
    setIsEditDialogOpen(true);
  };

  const handleUpdateCollection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!collection) return;

    try {
      const response = await apiPut(
        `${import.meta.env.VITE_API_BASE_URL}/collections/${collection.collection_id}`,
        {
          name: editFormData.name,
          description: editFormData.description,
          website_url: editFormData.website_url || null,
          admin_email: editFormData.admin_email || null,
          is_active: editFormData.is_active,
        },
        user?.access_token
      );

      if (!response.ok) throw new Error('Failed to update knowledge base');

      toast.success('Knowledge base updated successfully');
      setIsEditDialogOpen(false);
      await fetchCollection();
    } catch (error) {
      console.error('Failed to update knowledge base', error);
      toast.error(error instanceof Error ? error.message : 'Failed to update knowledge base');
    }
  };

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </DashboardLayout>
    );
  }

  if (!collection) {
    return (
      <DashboardLayout>
        <div className="text-center py-8">
          <p className="text-muted-foreground">Knowledge base not found</p>
          <Button onClick={() => navigate('/superadmin')} className="mt-4">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Knowledge Base
          </Button>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold">{collection.name}</h1>
              <p className="text-muted-foreground">{collection.description || 'No description provided'}</p>
            </div>
            <div className="flex items-center space-x-2">
              <span
                className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  collection.is_active
                    ? 'bg-green-100 text-green-800'
                    : 'bg-gray-100 text-gray-800'
                }`}
              >
                {collection.is_active ? 'Active' : 'Inactive'}
              </span>
              <Button size="sm" variant="outline" onClick={handleOpenEditDialog}>
                <Pencil className="mr-1 h-4 w-4" />
                Edit
              </Button>
            </div>
          </div>
          <div>
            <Button variant="outline" onClick={() => navigate('/superadmin')}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Knowledge Bases
            </Button>
          </div>
        </div>

        <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
          <DialogContent className="max-w-2xl sm:max-h-[85vh] overflow-y-auto">
            <form onSubmit={handleUpdateCollection}>
              <DialogHeader>
                <DialogTitle>Edit Knowledge Base</DialogTitle>
                <DialogDescription>Update the knowledge base details</DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="edit-name">Knowledge Base Name *</Label>
                  <Input
                    id="edit-name"
                    maxLength={50}
                    value={editFormData.name}
                    onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit-description">Description</Label>
                  <Textarea
                    id="edit-description"
                    maxLength={200}
                    value={editFormData.description}
                    onChange={(e) => setEditFormData({ ...editFormData, description: e.target.value })}
                    rows={3}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit-website-url">Website URL</Label>
                  <Input
                    id="edit-website-url"
                    value={editFormData.website_url}
                    onChange={(e) => setEditFormData({ ...editFormData, website_url: e.target.value })}
                    placeholder="https://example.com"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit-admin-email">Admin Email</Label>
                  <Input
                    id="edit-admin-email"
                    type="email"
                    value={editFormData.admin_email}
                    onChange={(e) => setEditFormData({ ...editFormData, admin_email: e.target.value })}
                    placeholder="admin@example.com"
                  />
                </div>
                <div className="flex items-center space-x-2">
                  <Switch
                    id="edit-is-active"
                    checked={editFormData.is_active}
                    onCheckedChange={(checked) => setEditFormData({ ...editFormData, is_active: checked })}
                  />
                  <Label htmlFor="edit-is-active">Active</Label>
                </div>
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setIsEditDialogOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit">Save Changes</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-6">
           <TabsList>
             <TabsTrigger value="overview">Overview</TabsTrigger>
             <TabsTrigger value="files">Files</TabsTrigger>
             <TabsTrigger value="prompts">Prompts</TabsTrigger>
           </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-6">

            <Card>
              <CardHeader>
                <CardTitle>Knowledge Base Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label className="text-sm font-medium">Admin Email</Label>
                  <p className="text-sm text-muted-foreground">{collection.admin_email || 'Not specified'}</p>
                </div>
                <div>
                  <Label className="text-sm font-medium">Website URL</Label>
                  <p className="text-sm text-muted-foreground">{collection.website_url || 'Not specified'}</p>
                </div>
                <div>
                  <Label className="text-sm font-medium">Created</Label>
                  <p className="text-sm text-muted-foreground">
                    {new Date(collection.created_at).toLocaleDateString()}
                  </p>
                </div>
                {collection.updated_at && (
                  <div>
                    <Label className="text-sm font-medium">Last Updated</Label>
                    <p className="text-sm text-muted-foreground">
                      {new Date(collection.updated_at).toLocaleDateString()}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Files Tab */}
          <TabsContent value="files" className="space-y-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Database className="h-5 w-5" />
                      Files
                    </CardTitle>
                    <CardDescription>
                      Manage files for this knowledge base
                    </CardDescription>
                  </div>
                  <Dialog open={isFileDialogOpen} onOpenChange={setIsFileDialogOpen}>
                    <DialogTrigger asChild>
                      <Button>
                        <Upload className="mr-2 h-4 w-4" />
                        Upload File
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Upload File</DialogTitle>
                        <DialogDescription>
                          Upload files to this knowledge base (PDF, DOC, DOCX, PPTX, XLSX, TXT, CSV - Max 10MB each)
                        </DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4">
                        <div>
                          <Label htmlFor="file-upload">Choose File</Label>
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
                                    className={`text-xs font-medium ${
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
                        <Button variant="outline" onClick={() => setIsFileDialogOpen(false)}>
                          Cancel
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center space-x-4 mb-4">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search files..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-10 w-64"
                    />
                  </div>
                </div>

                {filesLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  </div>
                ) : filteredFiles.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    {searchTerm ? 'No files found matching your search.' : 'No files uploaded yet.'}
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
                             <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                               file.processing_status === 'completed'
                                 ? 'bg-green-100 text-green-800'
                                 : file.processing_status === 'processing'
                                 ? 'bg-yellow-100 text-yellow-800'
                                 : 'bg-red-100 text-red-800'
                             }`}>
                               {file.processing_status}
                             </span>
                           </TableCell>
                           <TableCell>{new Date(file.upload_timestamp).toLocaleDateString()}</TableCell>
                           <TableCell className="text-right">
                             <div className="flex items-center justify-end space-x-2">
                               <Button
                                 variant="ghost"
                                 size="sm"
                                 onClick={() => handleDownload(file.file_id, file.file_name)}
                                 disabled={file.processing_status !== 'completed'}
                               >
                                 <Download className="h-4 w-4 mr-1" />
                                 Download
                               </Button>
                               <Button
                                 variant="ghost"
                                 size="sm"
                                 onClick={() => handleDeleteFile(file.file_id)}
                                 className="text-destructive hover:text-destructive hover:bg-destructive/10"
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
          </TabsContent>

          {/* Prompts Tab */}
          <TabsContent value="prompts" className="space-y-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <FileCode className="h-5 w-5" />
                      Prompts
                    </CardTitle>
                    <CardDescription>
                      Manage prompts for this knowledge base
                    </CardDescription>
                  </div>
                  <Dialog open={isPromptDialogOpen} onOpenChange={setIsPromptDialogOpen}>
                    <DialogTrigger asChild>
                      <Button>
                        <Plus className="mr-2 h-4 w-4" />
                        Create Prompt
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="max-w-2xl">
                      <form onSubmit={editingPrompt ? handleUpdatePrompt : handleCreatePrompt}>
                        <DialogHeader>
                          <DialogTitle>
                            {editingPrompt ? 'Edit Prompt' : 'Create New Prompt'}
                          </DialogTitle>
                          <DialogDescription>
                            {editingPrompt 
                              ? 'Update the prompt details' 
                              : 'Create a new prompt for this knowledge base'
                            }
                          </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                          <div className="space-y-2">
                            <Label htmlFor="prompt-name">Prompt Name *</Label>
                            <Input
                              id="prompt-name"
                              value={promptFormData.name}
                              onChange={(e) => setPromptFormData({ ...promptFormData, name: e.target.value })}
                              placeholder="Enter prompt name"
                              required
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="prompt-description">Description</Label>
                            <Input
                              id="prompt-description"
                              value={promptFormData.description}
                              onChange={(e) => setPromptFormData({ ...promptFormData, description: e.target.value })}
                              placeholder="Enter prompt description"
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="prompt-content">Prompt Content *</Label>
                            <Textarea
                              id="prompt-content"
                              value={promptFormData.content}
                              onChange={(e) => setPromptFormData({ ...promptFormData, content: e.target.value })}
                              placeholder="Enter prompt content"
                              rows={6}
                              required
                            />
                          </div>
                          <div className="flex items-center space-x-6">
                            <div className="flex items-center space-x-2">
                              <input
                                type="checkbox"
                                id="is-active"
                                checked={promptFormData.is_active}
                                onChange={(e) => setPromptFormData({ ...promptFormData, is_active: e.target.checked })}
                              />
                              <Label htmlFor="is-active">Active</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <input
                                type="checkbox"
                                id="is-default"
                                checked={promptFormData.is_default}
                                onChange={(e) => setPromptFormData({ ...promptFormData, is_default: e.target.checked })}
                              />
                              <Label htmlFor="is-default">Set as default prompt</Label>
                            </div>
                          </div>
                        </div>
                        <DialogFooter>
                          <Button type="button" variant="outline" onClick={closePromptDialog}>
                            Cancel
                          </Button>
                          <Button type="submit">
                            {editingPrompt ? 'Update Prompt' : 'Create Prompt'}
                          </Button>
                        </DialogFooter>
                      </form>
                    </DialogContent>
                  </Dialog>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center space-x-4 mb-4">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search prompts..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-10 w-64"
                    />
                  </div>
                </div>

                {promptsLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  </div>
                ) : filteredPrompts.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    {searchTerm ? 'No prompts found matching your search.' : 'No prompts created yet.'}
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead>Content</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Default</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                     <TableBody>
                       {filteredPrompts.map((prompt) => (
                         <TableRow key={prompt.prompt_id}>
                           <TableCell className="font-medium">{prompt.name}</TableCell>
                           <TableCell className="max-w-xs truncate">{prompt.description || 'No description'}</TableCell>
                           <TableCell className="max-w-xs truncate">{prompt.system_prompt}</TableCell>
                           <TableCell>
                             <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                               prompt.is_active
                                 ? 'bg-green-100 text-green-800'
                                 : 'bg-gray-100 text-gray-800'
                             }`}>
                               {prompt.is_active ? 'Active' : 'Inactive'}
                             </span>
                           </TableCell>
                           <TableCell>
                             {prompt.is_default && (
                               <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
                                 Default
                               </span>
                             )}
                           </TableCell>
                           <TableCell className="text-right">
                             <div className="flex items-center justify-end space-x-2">
                               <Button
                                 variant="ghost"
                                 size="sm"
                                 onClick={() => openEditPromptDialog(prompt)}
                               >
                                 <Pencil className="h-4 w-4 mr-1" />
                                 Edit
                               </Button>
                               <Button
                                 variant="ghost"
                                 size="sm"
                                 onClick={() => handleDeletePrompt(prompt.prompt_id)}
                                 disabled={prompt.is_default && prompts.length === 1}
                                 className="text-destructive hover:text-destructive hover:bg-destructive/10"
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
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
}
