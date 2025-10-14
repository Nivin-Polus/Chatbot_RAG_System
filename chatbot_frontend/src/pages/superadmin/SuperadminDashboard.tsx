import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { DashboardLayout } from '@/components/DashboardLayout';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Plus, Pencil, Trash2, Database, Loader2, Search, Folder, FileCode, Copy } from 'lucide-react';
import { Collection } from '@/types/auth';
import { toast } from 'sonner';
import { apiGet, apiPost, apiDelete, apiPut } from '@/utils/api';

export default function SuperadminDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    is_active: true,
    website_url: '',
    admin_email: '',
    admin_username: '',
    admin_full_name: '',
    admin_password: '',
  });
  const [editingCollection, setEditingCollection] = useState<Collection | null>(null);
  const [editFormData, setEditFormData] = useState({
    name: '',
    description: '',
    website_url: '',
    admin_email: '',
    is_active: true,
  });

  const refreshCollections = useCallback(async () => {
    try {
      const response = await apiGet(
        `${import.meta.env.VITE_API_BASE_URL}/collections/`,
        user?.access_token
      );
      if (response.ok) {
        const data = await response.json();
        setCollections(data);
        return true;
      }
    } catch (error) {
      toast.error('Failed to fetch collections');
    }
    return false;
  }, [user?.access_token]);

  useEffect(() => {
    const loadCollections = async () => {
      setIsLoading(true);
      await refreshCollections();
      setIsLoading(false);
    };

    if (user?.access_token) {
      loadCollections();
    }
  }, [user?.access_token, refreshCollections]);

  const handleCreateCollection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (formData.admin_username.trim().toLowerCase() === 'superadmin') {
      toast.error('The superadmin account is reserved. Please choose a different admin username.');
      return;
    }
    try {
      const response = await apiPost(
        `${import.meta.env.VITE_API_BASE_URL}/collections/`,
        {
          name: formData.name,
          description: formData.description,
          website_url: formData.website_url || undefined,
          admin_email: formData.admin_email || undefined,
          admin_username: formData.admin_username,
          admin_full_name: formData.admin_full_name || undefined,
          admin_password: formData.admin_password,
          is_active: formData.is_active,
        },
        user?.access_token
      );

      if (!response.ok) throw new Error('Failed to create collection');

      await response.json();

      toast.success('Knowledge base created and admin user prepared successfully');
      setIsDialogOpen(false);
      setFormData({
        name: '',
        description: '',
        is_active: true,
        website_url: '',
        admin_email: '',
        admin_username: '',
        admin_full_name: '',
        admin_password: '',
      });
      
      // Refresh collections
      await refreshCollections();
    } catch (error) {
      console.error('Failed to create knowledge base', error);
      toast.error(error instanceof Error ? error.message : 'Failed to create knowledge base');
    }
  };

  const handleDeleteCollection = async (id: string) => {
    if (!confirm('Are you sure you want to delete this knowledge base?')) return;

    try {
      const response = await apiDelete(
        `${import.meta.env.VITE_API_BASE_URL}/collections/${id}`,
        user?.access_token
      );

      if (!response.ok) throw new Error('Failed to delete collection');

      toast.success('Knowledge base deleted successfully');
      
      // Refresh collections
      await refreshCollections();
    } catch (error) {
      toast.error('Failed to delete knowledge base');
    }
  };

  const handleOpenEditDialog = (collection: Collection) => {
    setEditingCollection(collection);
    setEditFormData({
      name: collection.name,
      description: collection.description || '',
      website_url: collection.website_url || '',
      admin_email: collection.admin_email || '',
      is_active: collection.is_active,
    });
    setIsEditDialogOpen(true);
  };

  const handleUpdateCollection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingCollection) return;

    try {
      const response = await apiPut(
        `${import.meta.env.VITE_API_BASE_URL}/collections/${editingCollection.collection_id}`,
        {
          name: editFormData.name,
          description: editFormData.description,
          website_url: editFormData.website_url || null,
          admin_email: editFormData.admin_email || null,
          is_active: editFormData.is_active,
        },
        user?.access_token
      );

      if (!response.ok) throw new Error('Failed to update collection');

      toast.success('Knowledge base updated successfully');
      setIsEditDialogOpen(false);
      setEditingCollection(null);

      await refreshCollections();
    } catch (error) {
      toast.error('Failed to update knowledge base');
    }
  };

  const handleCopyCollectionId = async (collectionId: string) => {
    try {
      // Try modern clipboard API first
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(collectionId);
        toast.success('Collection ID copied to clipboard');
      } else {
        // Fallback for HTTP or older browsers
        const textArea = document.createElement('textarea');
        textArea.value = collectionId;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        toast.success('Collection ID copied to clipboard');
      }
    } catch (error) {
      console.error('Failed to copy collection ID', error);
      toast.error('Unable to copy collection ID');
    }
  };

  const handleNavigateToTab = (collectionId: string, tab: 'files' | 'prompts') => {
    navigate(`/superadmin/knowledge-base/${collectionId}?tab=${tab}`);
  };

  const filteredCollections = collections.filter(collection =>
    collection.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (collection.description && collection.description.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Knowledge Base</h1>
            
          </div>
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button className="shadow-glow">
                <Plus className="mr-2 h-4 w-4" />
                Create Knowledge Base
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl sm:max-h-[85vh] overflow-y-auto">
              <form onSubmit={handleCreateCollection}>
                <DialogHeader>
                  <DialogTitle>Create New Knowledge Base</DialogTitle>
                  <DialogDescription>
                    Set up a new knowledge base with an admin user
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="name">Knowledge Base Name *</Label>
                    <Input
                      id="name"
                      maxLength={50}
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="description">Description</Label>
                    <Textarea
                      id="description"
                      maxLength={200}
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      rows={3}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="website_url">Website URL</Label>
                    <Input
                      id="website_url"
                      value={formData.website_url}
                      onChange={(e) => setFormData({ ...formData, website_url: e.target.value })}
                      placeholder="https://example.com"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="admin_email">Admin Email</Label>
                    <Input
                      id="admin_email"
                      type="email"
                      value={formData.admin_email}
                      onChange={(e) => setFormData({ ...formData, admin_email: e.target.value })}
                      placeholder="admin@example.com"
                    />
                  </div>
                  <div className="flex items-center space-x-2">
                    <Switch
                      id="is_active"
                      checked={formData.is_active}
                      onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                    />
                    <Label htmlFor="is_active">Active</Label>
                  </div>
                  <div className="border-t pt-4">
                    <h4 className="font-medium mb-3">Admin User Credentials</h4>
                    <div className="space-y-3">
                      <div className="space-y-2">
                        <Label htmlFor="admin_full_name">Admin Full Name</Label>
                        <Input
                          id="admin_full_name"
                          value={formData.admin_full_name}
                          onChange={(e) => setFormData({ ...formData, admin_full_name: e.target.value })}
                          placeholder="Enter full name"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="admin_username">Admin Username *</Label>
                        <Input
                          id="admin_username"
                          value={formData.admin_username}
                          onChange={(e) => setFormData({ ...formData, admin_username: e.target.value })}
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="admin_password">Admin Password *</Label>
                        <Input
                          id="admin_password"
                          type="password"
                          value={formData.admin_password}
                          onChange={(e) => setFormData({ ...formData, admin_password: e.target.value })}
                          required
                        />
                      </div>
                    </div>
                  </div>
                </div>
                <DialogFooter>
                  <Button type="submit">Create Knowledge Base</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
          <Dialog
            open={isEditDialogOpen}
            onOpenChange={(open) => {
              setIsEditDialogOpen(open);
              if (!open) {
                setEditingCollection(null);
              }
            }}
          >
            <DialogContent className="max-w-md">
              <form onSubmit={handleUpdateCollection}>
                <DialogHeader>
                  <DialogTitle>Edit Knowledge Base</DialogTitle>
                  <DialogDescription>
                    Update the knowledge base details
                  </DialogDescription>
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
                  <Button type="submit">Save Changes</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        <Card>
          <CardHeader>
           
            <CardDescription>
              {collections.length} knowledge base(s) total
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!isLoading && collections.length > 0 && (
              <div className="flex items-center space-x-4 mb-4">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search knowledge bases..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-10 w-64"
                  />
                </div>
              </div>
            )}
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : filteredCollections.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {searchTerm ? 'No knowledge bases found matching your search.' : 'No knowledge bases yet. Create your first one!'}
              </div>
            ) : (
              <TooltipProvider delayDuration={150}>
                <Table>
                  <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Collection ID</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                  </TableHeader>
                  <TableBody>
                  {filteredCollections.map((collection) => (
                    <TableRow key={collection.collection_id}>
                      <TableCell className="font-medium">
                        <button
                          onClick={() => navigate(`/superadmin/knowledge-base/${collection.collection_id}`)}
                          className="text-primary hover:text-primary/80 hover:underline font-medium"
                        >
                          {collection.name}
                        </button>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {collection.description || '—'}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <code className="text-xs bg-muted px-2 py-1 rounded">
                            {collection.collection_id}
                          </code>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleCopyCollectionId(collection.collection_id)}
                            aria-label="Copy collection ID"
                          >
                            <Copy className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                      <TableCell>
                        <span
                          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                            collection.is_active
                              ? 'bg-green-100 text-green-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {collection.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(collection.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end space-x-1">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleNavigateToTab(collection.collection_id, 'files')}
                                aria-label="View files"
                              >
                                <Folder className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent side="top">Manage files</TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleNavigateToTab(collection.collection_id, 'prompts')}
                                aria-label="View prompts"
                              >
                                <FileCode className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent side="top">Manage prompts</TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleOpenEditDialog(collection)}
                                aria-label="Edit knowledge base"
                              >
                                <Pencil className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent side="top">Edit knowledge base</TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleDeleteCollection(collection.collection_id)}
                                className="text-destructive hover:text-destructive"
                                aria-label="Delete knowledge base"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent side="top">Delete knowledge base</TooltipContent>
                          </Tooltip>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  </TableBody>
                </Table>
              </TooltipProvider>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
