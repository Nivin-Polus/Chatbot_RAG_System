import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { DashboardLayout } from '@/components/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Copy, Loader2, LifeBuoy, CheckCircle2, XCircle, RefreshCw } from 'lucide-react';
import { Collection, PluginIntegration } from '@/types/auth';
import { apiGet, apiPut } from '@/utils/api';
import { toast } from 'sonner';

export default function SuperadminHelpPage() {
  const { user } = useAuth();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [isCollectionsLoading, setIsCollectionsLoading] = useState(true);
  const [plugins, setPlugins] = useState<PluginIntegration[]>([]);
  const [pluginFilterCollection, setPluginFilterCollection] = useState<string>('all');
  const [isPluginLoading, setIsPluginLoading] = useState(false);

  const refreshCollections = useCallback(async () => {
    if (!user?.access_token) {
      setCollections([]);
      return;
    }

    setIsCollectionsLoading(true);
    try {
      const response = await apiGet(`${import.meta.env.VITE_API_BASE_URL}/collections/`, user.access_token, false);
      if (response.ok) {
        const data: Collection[] = await response.json();
        setCollections(data);
      } else {
        setCollections([]);
      }
    } catch (error) {
      console.debug('Failed to load collections', error);
      setCollections([]);
      toast.error('Unable to load knowledge bases');
    } finally {
      setIsCollectionsLoading(false);
    }
  }, [user?.access_token]);

  const refreshPlugins = useCallback(
    async (collectionId?: string) => {
      if (!user?.access_token) {
        setPlugins([]);
        return;
      }

      setIsPluginLoading(true);
      try {
        const params = collectionId ? `?collection_id=${collectionId}` : '';
        const response = await apiGet(
          `${import.meta.env.VITE_API_BASE_URL}/plugins/${params}`,
          user.access_token,
          false
        );
        if (response.ok) {
          const data: PluginIntegration[] = await response.json();
          // Filter to only show plugins with widget_token
          setPlugins(data.filter(p => p.widget_token));
        } else {
          setPlugins([]);
        }
      } catch (error) {
        console.debug('Failed to fetch plugins', error);
        setPlugins([]);
      } finally {
        setIsPluginLoading(false);
      }
    },
    [user?.access_token]
  );

  useEffect(() => {
    void refreshCollections();
  }, [refreshCollections]);

  useEffect(() => {
    const targetCollection = pluginFilterCollection === 'all' ? undefined : pluginFilterCollection;
    void refreshPlugins(targetCollection);
  }, [pluginFilterCollection, refreshPlugins]);

  const handleCopyWidgetUrl = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      toast.success('Help Page URL copied to clipboard!');
    } catch {
      toast.error('Failed to copy URL');
    }
  };

  const handleToggleWidgetStatus = async (plugin: PluginIntegration) => {
    try {
      const response = await apiPut(
        `${import.meta.env.VITE_API_BASE_URL}/plugins/${plugin.id}`,
        {
          is_widget_active: !plugin.is_widget_active,
        },
        user?.access_token
      );

      if (!response.ok) {
        throw new Error('Failed to update help page status');
      }

      toast.success(!plugin.is_widget_active ? 'Help page enabled' : 'Help page disabled');
      
      // Update local state to reflect the change immediately
      setPlugins(prev => prev.map(p => p.id === plugin.id ? { ...p, is_widget_active: !p.is_widget_active } : p));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update help page');
    }
  };

  const filteredPlugins = pluginFilterCollection === 'all'
    ? plugins
    : plugins.filter((plugin) => plugin.collection_id === pluginFilterCollection);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-bold">Help Page</h1>
          <p className="text-muted-foreground">
            Manage standalone help page URLs for all knowledge bases.
          </p>
        </div>

        <Card>
          <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-2xl">
                <LifeBuoy className="h-5 w-5" /> Help Page URLs
              </CardTitle>
              <CardDescription>View and manage standalone help pages for each knowledge base.</CardDescription>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
              <Select
                value={pluginFilterCollection}
                onValueChange={setPluginFilterCollection}
                disabled={collections.length === 0}
              >
                <SelectTrigger className="w-[220px]">
                  <SelectValue placeholder="Filter by knowledge base" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All knowledge bases</SelectItem>
                  {collections.map((collection) => (
                    <SelectItem key={collection.collection_id} value={collection.collection_id}>
                      {collection.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                onClick={() => {
                  const targetCollection = pluginFilterCollection === 'all' ? undefined : pluginFilterCollection;
                  refreshPlugins(targetCollection);
                }}
                variant="outline"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {isPluginLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : filteredPlugins.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {collections.length === 0
                  ? 'Create a knowledge base before setting up help pages.'
                  : 'No help pages configured yet. Add a plugin integration first.'}
              </div>
            ) : (
              <TooltipProvider delayDuration={150}>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Knowledge Base</TableHead>
                      <TableHead>Display Name</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Help Page URL</TableHead>
                      <TableHead>Created</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredPlugins.map((plugin) => {
                      const widgetUrl = `${import.meta.env.VITE_CHAT_WIDGET_BASE_URL || 'https://dev-chatbot.polussolutions.com/chat-widget'}/${plugin.widget_token}`;
                      
                      return (
                        <TableRow key={plugin.id}>
                          <TableCell className="font-medium">{plugin.collection_name}</TableCell>
                          <TableCell>{plugin.display_name || '—'}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Switch 
                                checked={plugin.is_widget_active} 
                                onCheckedChange={() => handleToggleWidgetStatus(plugin)} 
                              />
                              <Badge 
                                variant="outline" 
                                className={plugin.is_widget_active 
                                  ? "bg-green-50 text-green-700 border-green-200" 
                                  : "bg-gray-50 text-gray-700 border-gray-200"
                                }
                              >
                                {plugin.is_widget_active ? (
                                  <>
                                    <CheckCircle2 className="h-3 w-3 mr-1" />
                                    Active
                                  </>
                                ) : (
                                  <>
                                    <XCircle className="h-3 w-3 mr-1" />
                                    Inactive
                                  </>
                                )}
                              </Badge>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2 max-w-md">
                              <Input
                                readOnly
                                value={widgetUrl}
                                className="bg-muted font-mono text-xs"
                              />
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Button
                                    size="icon"
                                    variant="outline"
                                    onClick={() => handleCopyWidgetUrl(widgetUrl)}
                                  >
                                    <Copy className="h-4 w-4" />
                                  </Button>
                                </TooltipTrigger>
                                <TooltipContent side="top">Copy URL</TooltipContent>
                              </Tooltip>
                            </div>
                            <p className="text-[10px] text-muted-foreground italic mt-1">
                              * This URL is permanent and does not expire
                            </p>
                          </TableCell>
                          <TableCell className="text-muted-foreground">
                            {plugin.created_at ? new Date(plugin.created_at).toLocaleString() : '—'}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TooltipProvider>
            )}
          </CardContent>
        </Card>

        {/* Info Card */}
        <Card className="bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800">
          <CardContent className="pt-6">
            <div className="flex gap-3">
              <LifeBuoy className="h-5 w-5 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="text-sm font-medium text-blue-800 dark:text-blue-200">
                  About Help Pages
                </p>
                <ul className="text-sm text-blue-700 dark:text-blue-300 space-y-1 list-disc list-inside">
                  <li>Help pages provide a standalone chatbot interface accessible via a unique URL</li>
                  <li>Each URL is automatically generated when a plugin is created and never expires</li>
                  <li>Share the URL with users to give them direct access to your knowledge base</li>
                  <li>Toggle the status to enable or disable access without changing the URL</li>
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
