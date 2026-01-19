import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { DashboardLayout } from '@/components/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Copy, Loader2, HelpCircle, CheckCircle2, XCircle, AlertCircle, RefreshCw } from 'lucide-react';
import { Collection, PluginIntegration } from '@/types/auth';
import { apiGet, apiPost, apiPut } from '@/utils/api';
import { toast } from 'sonner';

export default function UserAdminHelpPage() {
  const { user } = useAuth();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [isCollectionsLoading, setIsCollectionsLoading] = useState(true);
  const [selectedCollectionId, setSelectedCollectionId] = useState<string>('');
  const [plugins, setPlugins] = useState<PluginIntegration[]>([]);
  const [isPluginLoading, setIsPluginLoading] = useState(false);
  const [generatingWidgetUrl, setGeneratingWidgetUrl] = useState<string | null>(null);

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
  }, [selectedCollectionId, user?.access_token]);

  useEffect(() => {
    void refreshCollections();
  }, [refreshCollections]);

  useEffect(() => {
    if (selectedCollectionId) {
      void refreshPlugins();
    }
  }, [selectedCollectionId, refreshPlugins]);

  const handleCopyWidgetUrl = async (url: string) => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
        toast.success('Help Page URL copied to clipboard!');
        return;
      }
      throw new Error('Clipboard API not available');
    } catch {
      try {
        const textarea = document.createElement('textarea');
        textarea.value = url;
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        const successful = document.execCommand('copy');
        document.body.removeChild(textarea);

        if (successful) {
          toast.success('Help Page URL copied to clipboard!');
        } else {
          throw new Error('execCommand failed');
        }
      } catch {
        toast.error('Failed to copy URL');
      }
    }
  };

  const handleGenerateWidgetUrl = async (collectionId: string) => {
    if (!user?.access_token) return;

    setGeneratingWidgetUrl(collectionId);
    try {
      const response = await apiPost(
        `${import.meta.env.VITE_API_BASE_URL}/plugins/generate-widget-url`,
        { collection_id: collectionId },
        user.access_token
      );

      if (!response.ok) {
        throw new Error('Failed to generate help page URL');
      }

      await response.json();
      await refreshPlugins();
      toast.success('Help Page URL generated!');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to generate help page URL');
    } finally {
      setGeneratingWidgetUrl(null);
    }
  };

  const handleToggleWidgetStatus = async (plugin: PluginIntegration) => {
    try {
      const response = await apiPut(
        `${import.meta.env.VITE_API_BASE_URL}/plugins/${plugin.id}`,
        {
          is_widget_active: !plugin.is_widget_active,
        },
        user?.access_token,
      );

      if (!response.ok) {
        throw new Error('Failed to update help page status');
      }

      toast.success(!plugin.is_widget_active ? 'Help page enabled' : 'Help page disabled');
      
      // Update local state
      setPlugins(prev => prev.map(p => p.id === plugin.id ? { ...p, is_widget_active: !p.is_widget_active } : p));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update help page');
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
          <h1 className="text-3xl font-bold">Help Page</h1>
          <p className="text-muted-foreground">
            Manage standalone help page URLs for your knowledge base.
          </p>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 text-2xl">
                  <HelpCircle className="h-5 w-5" /> Help Page URLs
                </CardTitle>
                <CardDescription>
                  View and manage standalone help pages for your knowledge base.
                </CardDescription>
              </div>
              <Button
                onClick={refreshPlugins}
                variant="outline"
                disabled={!selectedCollectionId}
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
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
                <AlertCircle className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No knowledge bases available.</p>
                <p className="text-sm">Create or request access to a knowledge base first.</p>
              </div>
            ) : isPluginLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : plugins.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <HelpCircle className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No help pages configured yet for {currentCollection.name}.</p>
                <p className="text-sm">
                  Generate a help page URL for this knowledge base using the button below.
                </p>
                <Button
                  variant="secondary"
                  size="sm"
                  className="mt-4"
                  onClick={() => handleGenerateWidgetUrl(currentCollection.collection_id)}
                  disabled={generatingWidgetUrl === currentCollection.collection_id}
                >
                  {generatingWidgetUrl === currentCollection.collection_id ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : null}
                  Generate Help Page URL
                </Button>
              </div>
            ) : (
              <TooltipProvider delayDuration={150}>
                <div className="space-y-6">
                  {plugins.map((plugin) => {
                    const widgetUrl = `${import.meta.env.VITE_CHAT_WIDGET_BASE_URL || 'https://dev-chatbot.polussolutions.com/chat-widget'}/${plugin.widget_token}`;

                    return (
                      <Card key={plugin.id} className="border-2">
                        <CardHeader>
                          <div className="flex items-start justify-between">
                            <div>
                              <CardTitle className="text-lg">
                                {plugin.display_name || plugin.website_url}
                              </CardTitle>
                              <CardDescription className="mt-1">
                                {plugin.display_name ? plugin.website_url : 'Help Page Configuration'}
                              </CardDescription>
                            </div>
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
                          </div>
                        </CardHeader>
                        <CardContent className="space-y-4">
                          <div className="space-y-2">
                            <Label>Shareable URL</Label>
                            <div className="flex items-center gap-2">
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
                            <p className="text-[10px] text-muted-foreground italic">
                              * This URL is permanent and does not expire
                            </p>
                          </div>

                          <div className="pt-2 border-t">
                            <div className="grid grid-cols-2 gap-4 text-sm">
                              <div>
                                <p className="text-muted-foreground">Knowledge Base</p>
                                <p className="font-medium">{plugin.collection_name}</p>
                              </div>
                              <div>
                                <p className="text-muted-foreground">Created</p>
                                <p className="font-medium">
                                  {plugin.created_at ? new Date(plugin.created_at).toLocaleDateString() : '—'}
                                </p>
                              </div>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              </TooltipProvider>
            )}
          </CardContent>
        </Card>

        {/* Info Card */}
        <Card className="bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800">
          <CardContent className="pt-6">
            <div className="flex gap-3">
              <HelpCircle className="h-5 w-5 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
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
