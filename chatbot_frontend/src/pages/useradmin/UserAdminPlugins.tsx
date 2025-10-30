import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { DashboardLayout } from '@/components/DashboardLayout';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Link as ExternalLinkIcon, Loader2, Pencil, Plus, Plug, Trash2 } from 'lucide-react';
import { Collection, PluginIntegration } from '@/types/auth';
import { apiDelete, apiGet, apiPost, apiPut } from '@/utils/api';
import { toast } from 'sonner';

export default function UserAdminPlugins() {
  const { user } = useAuth();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [isCollectionsLoading, setIsCollectionsLoading] = useState(true);
  const [selectedCollectionId, setSelectedCollectionId] = useState<string>('');
  const [plugins, setPlugins] = useState<PluginIntegration[]>([]);
  const [isPluginLoading, setIsPluginLoading] = useState(false);
  const [pluginDialogOpen, setPluginDialogOpen] = useState(false);
  const [pluginFormData, setPluginFormData] = useState({ website_url: '', display_name: '' });
  const [editingPlugin, setEditingPlugin] = useState<PluginIntegration | null>(null);
  const [isPluginSaving, setIsPluginSaving] = useState(false);

  const refreshCollections = useCallback(async () => {
    if (!user?.access_token) {
      setCollections([]);
      return;
    }

    setIsCollectionsLoading(true);
    try {
      const response = await apiGet(
        `${import.meta.env.VITE_API_BASE_URL}/collections/summary`,
        user.access_token,
        false,
      );
      if (!response.ok) {
        throw new Error('Failed to load knowledge bases');
      }
      const data: Collection[] = await response.json();
      setCollections(data);
      if (data.length > 0) {
        setSelectedCollectionId((current) => current || data[0].collection_id);
      } else {
        setSelectedCollectionId('');
      }
    } catch (error) {
      console.debug('Failed to load collections', error);
      setCollections([]);
      setSelectedCollectionId('');
      toast.error('Unable to load knowledge bases');
    } finally {
      setIsCollectionsLoading(false);
    }
  }, [user?.access_token]);

  const refreshPlugins = useCallback(async () => {
    if (!user?.access_token || !selectedCollectionId) {
      setPlugins([]);
      return;
    }

    setIsPluginLoading(true);
    try {
      const response = await apiGet(
        `${import.meta.env.VITE_API_BASE_URL}/plugins/?collection_id=${selectedCollectionId}`,
        user.access_token,
        false,
      );
      if (response.ok) {
        const data: PluginIntegration[] = await response.json();
        setPlugins(data);
      } else {
        setPlugins([]);
      }
    } catch (error) {
      console.debug('Failed to fetch plugins', error);
      setPlugins([]);
    } finally {
      setIsPluginLoading(false);
    }
  }, [selectedCollectionId, user?.access_token]);

  useEffect(() => {
    void refreshCollections();
  }, [refreshCollections]);

  useEffect(() => {
    if (selectedCollectionId) {
      void refreshPlugins();
    }
  }, [selectedCollectionId, refreshPlugins]);

  const handleOpenPluginDialog = (plugin?: PluginIntegration) => {
    setPluginDialogOpen(true);
    setEditingPlugin(plugin ?? null);
    setPluginFormData({
      website_url: plugin?.website_url ?? '',
      display_name: plugin?.display_name ?? '',
    });
  };

  const handleClosePluginDialog = () => {
    setPluginDialogOpen(false);
    setEditingPlugin(null);
    setIsPluginSaving(false);
    setPluginFormData({ website_url: '', display_name: '' });
  };

  const handleSubmitPlugin = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedCollectionId) {
      toast.error('Select a knowledge base before saving the plugin.');
      return;
    }

    setIsPluginSaving(true);
    try {
      const payload = {
        collection_id: selectedCollectionId,
        website_url: pluginFormData.website_url,
        display_name: pluginFormData.display_name || undefined,
      };

      const endpoint = `${import.meta.env.VITE_API_BASE_URL}/plugins${editingPlugin ? `/${editingPlugin.id}` : '/integrations'}`;
      const method = editingPlugin ? apiPut : apiPost;
      const response = await method(endpoint, payload, user?.access_token);

      if (!response.ok) {
        throw new Error(editingPlugin ? 'Failed to update plugin integration' : 'Failed to create plugin integration');
      }

      toast.success(editingPlugin ? 'Plugin updated successfully' : 'Plugin created successfully');
      handleClosePluginDialog();
      await refreshPlugins();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to save plugin');
    } finally {
      setIsPluginSaving(false);
    }
  };

  const handleDeletePlugin = async (plugin: PluginIntegration) => {
    if (!confirm('Are you sure you want to delete this plugin integration?')) return;
    try {
      const response = await apiDelete(
        `${import.meta.env.VITE_API_BASE_URL}/plugins/${plugin.id}`,
        user?.access_token,
      );
      if (!response.ok) {
        throw new Error('Failed to delete plugin integration');
      }
      toast.success('Plugin integration deleted');
      await refreshPlugins();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to delete plugin');
    }
  };

  const handleTogglePluginStatus = async (plugin: PluginIntegration) => {
    try {
      const response = await apiPut(
        `${import.meta.env.VITE_API_BASE_URL}/plugins/${plugin.id}`,
        {
          collection_id: plugin.collection_id,
          website_url: plugin.website_url,
          display_name: plugin.display_name,
          is_active: !plugin.is_active,
        },
        user?.access_token,
      );

      if (!response.ok) {
        throw new Error('Failed to update plugin status');
      }

      toast.success(!plugin.is_active ? 'Plugin activated' : 'Plugin paused');
      await refreshPlugins();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update plugin');
    }
  };

  const currentCollection = useMemo(
    () => collections.find((collection) => collection.collection_id === selectedCollectionId) ?? null,
    [collections, selectedCollectionId],
  );

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-bold">Plugins</h1>
          <p className="text-muted-foreground">
            Manage website integrations for the knowledge bases you administer.
          </p>
        </div>

        <Card>
          <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-2xl">
                <Plug className="h-5 w-5" /> Plugin Integrations
              </CardTitle>
              <CardDescription>
                Link external websites to your knowledge base and control plugin availability.
              </CardDescription>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
              <Select
                value={selectedCollectionId}
                onValueChange={setSelectedCollectionId}
                disabled={collections.length === 0}
              >
                <SelectTrigger className="w-[220px]">
                  <SelectValue placeholder={isCollectionsLoading ? 'Loading…' : 'Select a knowledge base'} />
                </SelectTrigger>
                <SelectContent>
                  {collections.map((collection) => (
                    <SelectItem key={collection.collection_id} value={collection.collection_id}>
                      {collection.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                onClick={() => handleOpenPluginDialog()}
                disabled={!selectedCollectionId}
                className="shadow-glow"
              >
                <Plus className="mr-2 h-4 w-4" />
                Add Plugin
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {isCollectionsLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : !currentCollection ? (
              <div className="text-center py-8 text-muted-foreground">
                No knowledge bases available. Create or request access to a knowledge base first.
              </div>
            ) : isPluginLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : plugins.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No plugin integrations yet for {currentCollection.name}. Add your first one!
              </div>
            ) : (
              <TooltipProvider delayDuration={150}>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Website</TableHead>
                      <TableHead>Display Name</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {plugins.map((plugin) => (
                      <TableRow key={plugin.id}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span className="font-medium break-all">{plugin.website_url}</span>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button variant="ghost" size="icon" asChild>
                                  <a href={plugin.website_url} target="_blank" rel="noreferrer">
                                    <ExternalLinkIcon className="h-4 w-4" />
                                  </a>
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent side="top">Open website</TooltipContent>
                            </Tooltip>
                          </div>
                          <div className="text-xs text-muted-foreground">{plugin.normalized_url}</div>
                        </TableCell>
                        <TableCell>{plugin.display_name || '—'}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Switch checked={plugin.is_active} onCheckedChange={() => handleTogglePluginStatus(plugin)} />
                            <span className="text-sm text-muted-foreground">
                              {plugin.is_active ? 'Active' : 'Paused'}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {plugin.created_at ? new Date(plugin.created_at).toLocaleString() : '—'}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end space-x-1">
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button variant="ghost" size="icon" onClick={() => handleOpenPluginDialog(plugin)}>
                                  <Pencil className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent side="top">Edit plugin</TooltipContent>
                            </Tooltip>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleDeletePlugin(plugin)}
                                  className="text-destructive hover:text-destructive"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent side="top">Delete plugin</TooltipContent>
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

      <Dialog
        open={pluginDialogOpen}
        onOpenChange={(open) => {
          if (!open) {
            handleClosePluginDialog();
          } else {
            setPluginDialogOpen(true);
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <form onSubmit={handleSubmitPlugin}>
            <DialogHeader>
              <DialogTitle>{editingPlugin ? 'Edit Plugin Integration' : 'Create Plugin Integration'}</DialogTitle>
              <DialogDescription>Connect an external website with your knowledge base.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="plugin-url">Website URL *</Label>
                <Input
                  id="plugin-url"
                  type="url"
                  required
                  placeholder="https://example.com"
                  value={pluginFormData.website_url}
                  onChange={(event) => setPluginFormData((prev) => ({ ...prev, website_url: event.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="plugin-display-name">Display Name</Label>
                <Input
                  id="plugin-display-name"
                  placeholder="Friendly name shown in the dashboard"
                  value={pluginFormData.display_name}
                  onChange={(event) => setPluginFormData((prev) => ({ ...prev, display_name: event.target.value }))}
                />
              </div>
            </div>
            <DialogFooter>
              <Button type="submit" disabled={isPluginSaving}>
                {isPluginSaving ? 'Saving...' : editingPlugin ? 'Save Changes' : 'Create Plugin'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  );
}
