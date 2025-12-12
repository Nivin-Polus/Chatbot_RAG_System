import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { DashboardLayout } from '@/components/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import {
  Globe,
  Play,
  Square,
  RefreshCw,
  Trash2,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  Settings2,
  FileText,
  Link2,
  AlertCircle,
  CalendarClock,
  Timer,
  Eye,
  Info,
} from 'lucide-react';
import { toast } from 'sonner';
import { apiGet, apiPost, apiDelete } from '@/utils/api';
import { Collection } from '@/types/auth';

interface CrawlJob {
  job_id: string;
  collection_id: string;
  target_url: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'scheduled';
  pages_discovered: number;
  pages_crawled: number;
  pages_skipped: number;
  pages_failed: number;
  chunks_created: number;
  chunks_added?: number;
  chunks_updated?: number;
  chunks_deleted?: number;
  total_characters: number;
  progress_percent: number;
  current_url?: string;
  error_message?: string;
  is_scheduled?: boolean;
  schedule_interval_hours?: number;
  next_run_at?: string;
  last_successful_run?: string;
  run_count?: number;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
}

export default function SuperadminCrawler() {
  const { user } = useAuth();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [jobs, setJobs] = useState<CrawlJob[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Schedule dialog state
  const [scheduleDialogOpen, setScheduleDialogOpen] = useState(false);
  const [scheduleJobId, setScheduleJobId] = useState<string | null>(null);
  const [scheduleInterval, setScheduleInterval] = useState('1440');
  const [isScheduling, setIsScheduling] = useState(false);

  // Delete confirmation state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [jobIdToDelete, setJobIdToDelete] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // URL details dialog state
  const [urlDetailsOpen, setUrlDetailsOpen] = useState(false);
  const [urlDetailsLoading, setUrlDetailsLoading] = useState(false);
  const [urlDetails, setUrlDetails] = useState<{
    crawled_urls: { url: string; title: string; chunks: number }[];
    failed_urls: { url: string; reason: string }[];
    skipped_urls: { url: string; reason: string }[];
  } | null>(null);

  // Form state
  const [targetUrl, setTargetUrl] = useState('');
  const [selectedCollection, setSelectedCollection] = useState('');
  const [maxPages, setMaxPages] = useState<number | string>(0); // 0 = unlimited
  const [maxDepth, setMaxDepth] = useState<number | string>(10);
  const [useSitemap, setUseSitemap] = useState(true);
  const [excludePatterns, setExcludePatterns] = useState('/login\n/admin\n/cart');
  const [includeKeywords, setIncludeKeywords] = useState('');

  // Fetch collections
  const fetchCollections = useCallback(async () => {
    try {
      const response = await apiGet(
        `${import.meta.env.VITE_API_BASE_URL}/collections/summary`,
        user?.access_token
      );
      if (response.ok) {
        const data = await response.json();
        // Handle both array response and object with collections property
        const collectionList = Array.isArray(data) ? data : (data.collections || []);
        setCollections(collectionList);
      }
    } catch (error) {
      console.error('Failed to fetch collections:', error);
    }
  }, [user?.access_token]);

  // Fetch crawl jobs
  const fetchJobs = useCallback(async () => {
    try {
      const response = await apiGet(
        `${import.meta.env.VITE_API_BASE_URL}/crawler/jobs`,
        user?.access_token
      );
      if (response.ok) {
        const data = await response.json();
        setJobs(data.jobs || []);
      }
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
    } finally {
      setIsLoading(false);
    }
  }, [user?.access_token]);

  useEffect(() => {
    fetchCollections();
    fetchJobs();
  }, [fetchCollections, fetchJobs]);

  // Auto-refresh running jobs
  useEffect(() => {
    const hasRunningJobs = jobs.some(j => j.status === 'running' || j.status === 'pending');
    if (hasRunningJobs) {
      const interval = setInterval(fetchJobs, 3000);
      return () => clearInterval(interval);
    }
  }, [jobs, fetchJobs]);

  // Start a new crawl
  const handleStartCrawl = async () => {
    if (!targetUrl || !selectedCollection) {
      toast.error('Please enter a URL and select a knowledge base');
      return;
    }

    // Parse numeric values, defaulting to 0/10 if empty or invalid
    const parsedMaxPages = maxPages === '' ? 0 : parseInt(String(maxPages));
    const parsedMaxDepth = maxDepth === '' ? 10 : parseInt(String(maxDepth));

    setIsStarting(true);
    try {
      const response = await apiPost(
        `${import.meta.env.VITE_API_BASE_URL}/crawler/start`,
        {
          target_url: targetUrl,
          collection_id: selectedCollection,
          max_pages: isNaN(parsedMaxPages) ? 0 : parsedMaxPages,
          max_depth: isNaN(parsedMaxDepth) ? 10 : parsedMaxDepth,
          use_sitemap: useSitemap,
          exclude_patterns: excludePatterns
            .split('\n')
            .map(p => p.trim())
            .filter(Boolean),
          include_keywords: includeKeywords
            .split('\n')
            .map(k => k.trim())
            .filter(Boolean) || null,
        },
        user?.access_token
      );

      if (response.ok) {
        toast.success('Crawl started successfully!');
        setTargetUrl('');
        setShowAdvanced(false);
        fetchJobs();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to start crawl');
      }
    } catch (error) {
      toast.error('Failed to start crawl');
    } finally {
      setIsStarting(false);
    }
  };

  // Cancel a running job
  const handleCancelJob = async (jobId: string) => {
    try {
      const response = await apiPost(
        `${import.meta.env.VITE_API_BASE_URL}/crawler/jobs/${jobId}/cancel`,
        {},
        user?.access_token
      );

      if (response.ok) {
        toast.success('Crawl cancelled');
        fetchJobs();
      } else {
        toast.error('Failed to cancel crawl');
      }
    } catch (error) {
      toast.error('Failed to cancel crawl');
    }
  };

  // Delete a job
  // Delete a job
  const handleDeleteJob = (jobId: string) => {
    setJobIdToDelete(jobId);
    setDeleteDialogOpen(true);
  };

  const confirmDeleteJob = async () => {
    if (!jobIdToDelete) return;

    setIsDeleting(true);
    try {
      const response = await apiDelete(
        `${import.meta.env.VITE_API_BASE_URL}/crawler/jobs/${jobIdToDelete}`,
        user?.access_token
      );

      if (response.ok) {
        toast.success('Job and crawled content deleted from knowledge base');
        fetchJobs();
      } else {
        toast.error('Failed to delete job');
      }
    } catch (error) {
      toast.error('Failed to delete job');
    } finally {
      setIsDeleting(false);
      setDeleteDialogOpen(false);
      setJobIdToDelete(null);
    }
  };

  // Recrawl a previous job
  const handleRecrawl = async (jobId: string) => {
    try {
      const response = await apiPost(
        `${import.meta.env.VITE_API_BASE_URL}/crawler/jobs/${jobId}/recrawl`,
        {},
        user?.access_token
      );

      if (response.ok) {
        toast.success('Recrawl started');
        fetchJobs();
      } else {
        toast.error('Failed to start recrawl');
      }
    } catch (error) {
      toast.error('Failed to start recrawl');
    }
  };

  // Open schedule dialog
  const openScheduleDialog = (jobId: string) => {
    setScheduleJobId(jobId);
    setScheduleInterval('1440');
    setScheduleDialogOpen(true);
  };

  // Schedule a job
  const handleSchedule = async () => {
    if (!scheduleJobId) return;

    setIsScheduling(true);
    try {
      const intervalHours = parseFloat(scheduleInterval) || 48;
      const response = await apiPost(
        `${import.meta.env.VITE_API_BASE_URL}/crawler/jobs/${scheduleJobId}/schedule`,
        {
          interval_hours: intervalHours,
          start_immediately: false
        },
        user?.access_token
      );

      if (response.ok) {
        toast.success(`Scheduled to run every ${intervalHours} hours`);
        setScheduleDialogOpen(false);
        fetchJobs();
      } else {
        toast.error('Failed to schedule crawl');
      }
    } catch (error) {
      toast.error('Failed to schedule crawl');
    } finally {
      setIsScheduling(false);
    }
  };

  // View URL details for a job
  const handleViewUrlDetails = async (jobId: string) => {
    setUrlDetailsLoading(true);
    setUrlDetailsOpen(true);
    try {
      const response = await apiGet(
        `${import.meta.env.VITE_API_BASE_URL}/crawler/jobs/${jobId}/urls`,
        user?.access_token
      );
      if (response.ok) {
        const data = await response.json();
        setUrlDetails(data);
      } else {
        toast.error('Failed to load URL details');
        setUrlDetailsOpen(false);
      }
    } catch (error) {
      toast.error('Failed to load URL details');
      setUrlDetailsOpen(false);
    } finally {
      setUrlDetailsLoading(false);
    }
  };

  // Unschedule a job
  const handleUnschedule = async (jobId: string) => {
    try {
      const response = await apiPost(
        `${import.meta.env.VITE_API_BASE_URL}/crawler/jobs/${jobId}/unschedule`,
        {},
        user?.access_token
      );

      if (response.ok) {
        toast.success('Schedule removed');
        fetchJobs();
      } else {
        toast.error('Failed to remove schedule');
      }
    } catch (error) {
      toast.error('Failed to remove schedule');
    }
  };

  // Status badge helper
  const getStatusBadge = (status: CrawlJob['status']) => {
    switch (status) {
      case 'pending':
        return (
          <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">
            <Clock className="h-3 w-3 mr-1" />
            Pending
          </Badge>
        );
      case 'running':
        return (
          <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
            <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            Running
          </Badge>
        );
      case 'completed':
        return (
          <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
            <CheckCircle2 className="h-3 w-3 mr-1" />
            Completed
          </Badge>
        );
      case 'failed':
        return (
          <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
            <XCircle className="h-3 w-3 mr-1" />
            Failed
          </Badge>
        );
      case 'cancelled':
        return (
          <Badge variant="outline" className="bg-gray-50 text-gray-700 border-gray-200">
            <Square className="h-3 w-3 mr-1" />
            Cancelled
          </Badge>
        );
      case 'scheduled':
        return (
          <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200">
            <CalendarClock className="h-3 w-3 mr-1" />
            Scheduled
          </Badge>
        );
    }
  };

  // Get collection name
  const getCollectionName = (collectionId: string) => {
    const collection = collections.find(c => c.collection_id === collectionId);
    return collection?.name || collectionId;
  };

  // Format date
  const formatDate = (dateString?: string) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleString();
  };

  // Active jobs
  const activeJobs = jobs.filter(j => j.status === 'running' || j.status === 'pending');
  const scheduledJobs = jobs.filter(j => j.is_scheduled === true);
  const completedJobs = jobs.filter(j => j.status !== 'running' && j.status !== 'pending' && j.status !== 'scheduled');

  return (
    <DashboardLayout>
      <div className="space-y-6 h-full overflow-y-auto overflow-x-hidden">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Globe className="h-6 w-6" />
              Web Crawler
            </h1>
            <p className="text-muted-foreground">
              Crawl websites and add content to your knowledge base automatically
            </p>
          </div>
          <Button variant="outline" onClick={fetchJobs}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>

        {/* Start New Crawl */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Play className="h-5 w-5" />
              Start New Crawl
            </CardTitle>
            <CardDescription>
              Enter a website URL to crawl and select the target knowledge base
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="target-url">Website URL</Label>
                <Input
                  id="target-url"
                  placeholder="https://example.com"
                  value={targetUrl}
                  onChange={(e) => setTargetUrl(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="collection">Knowledge Base</Label>
                <Select value={selectedCollection} onValueChange={setSelectedCollection}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select knowledge base" />
                  </SelectTrigger>
                  <SelectContent>
                    {collections.map((collection) => (
                      <SelectItem key={collection.collection_id} value={collection.collection_id}>
                        {collection.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Advanced Settings */}
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowAdvanced(!showAdvanced)}
              >
                <Settings2 className="h-4 w-4 mr-1" />
                {showAdvanced ? 'Hide' : 'Show'} Advanced Settings
              </Button>
            </div>

            {showAdvanced && (
              <div className="grid gap-4 md:grid-cols-2 p-4 bg-muted/50 rounded-lg">
                <div className="space-y-2">
                  <Label htmlFor="max-pages">Max Pages (0 = unlimited)</Label>
                  <Input
                    id="max-pages"
                    type="number"
                    min={0}
                    value={maxPages}
                    onChange={(e) => setMaxPages(e.target.value)}
                    placeholder="0 for unlimited"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="max-depth">Max Depth</Label>
                  <Input
                    id="max-depth"
                    type="number"
                    min={1}
                    max={15}
                    value={maxDepth}
                    onChange={(e) => setMaxDepth(e.target.value)}
                  />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <div className="flex items-center gap-2">
                    <Switch
                      id="use-sitemap"
                      checked={useSitemap}
                      onCheckedChange={setUseSitemap}
                    />
                    <Label htmlFor="use-sitemap">Use sitemap.xml for URL discovery</Label>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="inline-flex cursor-help text-muted-foreground hover:text-foreground transition-colors">
                          <Info className="h-4 w-4" />
                        </span>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="max-w-[240px] p-2">
                        <div className="space-y-1">
                          <p className="text-xs font-medium">Sitemap discovery</p>
                          <p className="text-xs">
                            When enabled, the crawler reads your domain&apos;s sitemap.xml to find pages faster.
                            If no sitemap exists, normal link crawling still works.
                          </p>
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="exclude-patterns">Exclude Patterns (one per line)</Label>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="inline-flex cursor-help text-muted-foreground hover:text-foreground transition-colors">
                          <Info className="h-4 w-4" />
                        </span>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="max-w-[240px] p-2">
                        <div className="space-y-1">
                          <p className="text-xs font-medium">Substring match</p>
                          <p className="text-xs">
                            URLs containing any line are skipped. Plain text only (not regex).
                          </p>
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <Textarea
                    id="exclude-patterns"
                    placeholder="/login&#10;/admin&#10;/cart"
                    value={excludePatterns}
                    onChange={(e) => setExcludePatterns(e.target.value)}
                    rows={3}
                  />
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="include-keywords">Include Keywords (one per line)</Label>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="inline-flex cursor-help text-muted-foreground hover:text-foreground transition-colors">
                          <Info className="h-4 w-4" />
                        </span>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="max-w-[240px] p-2">
                        <div className="space-y-1">
                          <p className="text-xs font-medium">Required keywords</p>
                          <p className="text-xs">
                            Only visit URLs that contain at least one keyword. Leave empty to scan all.
                          </p>
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <Textarea
                    id="include-keywords"
                    placeholder="docs&#10;guide&#10;help"
                    value={includeKeywords}
                    onChange={(e) => setIncludeKeywords(e.target.value)}
                    rows={3}
                  />
                </div>
              </div>
            )}

            <Button onClick={handleStartCrawl} disabled={isStarting || !targetUrl || !selectedCollection}>
              {isStarting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 mr-2" />
                  Start Crawl
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Active Crawls */}
        {activeJobs.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin" />
                Active Crawls ({activeJobs.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {activeJobs.map((job) => (
                <div
                  key={job.job_id}
                  className="p-4 border rounded-lg space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Link2 className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium truncate max-w-md">{job.target_url}</span>
                      {getStatusBadge(job.status)}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleCancelJob(job.job_id)}
                    >
                      <Square className="h-4 w-4 mr-1" />
                      Cancel
                    </Button>
                  </div>

                  <div className="space-y-1">
                    <div className="flex justify-between text-sm text-muted-foreground">
                      <span>Progress: {job.pages_crawled} / {job.pages_discovered} pages</span>
                      <span>{job.progress_percent}%</span>
                    </div>
                    <Progress value={job.progress_percent} className="h-2" />
                  </div>

                  {job.current_url && (
                    <p className="text-xs text-muted-foreground truncate">
                      Currently crawling: {job.current_url}
                    </p>
                  )}

                  <div className="flex gap-4 text-sm text-muted-foreground">
                    <span>
                      <FileText className="h-3 w-3 inline mr-1" />
                      {job.chunks_created} chunks
                    </span>
                    <span>
                      {job.pages_skipped} skipped
                    </span>
                    <span>
                      {job.pages_failed} failed
                    </span>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {/* Crawl History */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Crawl History</CardTitle>
            <CardDescription>
              Past crawl jobs and their results
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            ) : completedJobs.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Globe className="h-12 w-12 mx-auto mb-2 opacity-50" />
                <p>No crawl history yet</p>
                <p className="text-sm">Start your first crawl above</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>URL</TableHead>
                      <TableHead>Knowledge Base</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Pages</TableHead>
                      <TableHead className="text-right">Chunks</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {completedJobs.map((job) => (
                      <TableRow key={job.job_id}>
                        <TableCell className="max-w-[200px]">
                          <div className="flex items-center gap-2">
                            <span className="truncate max-w-[150px]" title={job.target_url}>
                              {job.target_url}
                            </span>
                            {job.is_scheduled && (
                              <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200 text-xs shrink-0">
                                <Timer className="h-3 w-3 mr-1" />
                                {job.schedule_interval_hours}h
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>{getCollectionName(job.collection_id)}</TableCell>
                        <TableCell>{getStatusBadge(job.status)}</TableCell>
                        <TableCell className="text-right">{job.pages_crawled}</TableCell>
                        <TableCell className="text-right">{job.chunks_created}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDate(job.completed_at || job.created_at)}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            {job.is_scheduled ? (
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleUnschedule(job.job_id)}
                                title="Remove schedule"
                              >
                                <CalendarClock className="h-4 w-4 text-purple-600" />
                              </Button>
                            ) : (
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => openScheduleDialog(job.job_id)}
                                title="Schedule recurring crawl"
                              >
                                <CalendarClock className="h-4 w-4" />
                              </Button>
                            )}
                            {(job.status === 'completed' || job.status === 'failed') && (
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleViewUrlDetails(job.job_id)}
                                title="View URL details"
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleRecrawl(job.job_id)}
                              title="Recrawl now"
                            >
                              <RefreshCw className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDeleteJob(job.job_id)}
                              title="Delete"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Info Card */}
        <Card className="bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800">
          <CardContent className="pt-6">
            <div className="flex gap-3">
              <AlertCircle className="h-5 w-5 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="text-sm font-medium text-blue-800 dark:text-blue-200">
                  How Web Crawling Works
                </p>
                <ul className="text-sm text-blue-700 dark:text-blue-300 space-y-1 list-disc list-inside">
                  <li>The crawler discovers and follows internal links on your target website</li>
                  <li>Content is extracted with semantic structure (headings, paragraphs, lists)</li>
                  <li>Text is chunked and added to your knowledge base for AI chat retrieval</li>
                  <li>Duplicate pages are automatically detected and skipped</li>
                  <li>The crawler respects robots.txt and rate limits</li>
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the crawl job and remove all crawled content
              from the knowledge base. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700 focus:ring-red-600"
              onClick={(e) => {
                e.preventDefault();
                confirmDeleteJob();
              }}
              disabled={isDeleting}
            >
              {isDeleting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Deleting...
                </>
              ) : (
                'Delete'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Schedule Configuration Dialog */}
      <Dialog open={scheduleDialogOpen} onOpenChange={setScheduleDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CalendarClock className="h-5 w-5" />
              Schedule Recurring Crawl
            </DialogTitle>
            <DialogDescription>
              Set how often this website should be automatically re-crawled.
              Content changes will be detected and updated in your knowledge base.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="schedule-interval">Run Every</Label>
              <Select value={scheduleInterval} onValueChange={setScheduleInterval}>
                <SelectTrigger id="schedule-interval">
                  <SelectValue placeholder="Select interval" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1440">2 months</SelectItem>
                  <SelectItem value="4320">6 months</SelectItem>
                  <SelectItem value="8760">1 year</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="text-sm text-muted-foreground">
              <p>The crawler will automatically run at this interval and:</p>
              <ul className="list-disc list-inside mt-2 space-y-1">
                <li>Detect new and updated pages</li>
                <li>Remove deleted content from knowledge base</li>
                <li>Skip unchanged pages</li>
              </ul>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setScheduleDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSchedule} disabled={isScheduling}>
              {isScheduling ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Scheduling...
                </>
              ) : (
                <>
                  <CalendarClock className="h-4 w-4 mr-2" />
                  Enable Schedule
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* URL Details Dialog */}
      <Dialog open={urlDetailsOpen} onOpenChange={setUrlDetailsOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Eye className="h-5 w-5" />
              URL Details
            </DialogTitle>
            <DialogDescription>
              Breakdown of URLs processed during this crawl
            </DialogDescription>
          </DialogHeader>

          {urlDetailsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : urlDetails ? (
            <div className="space-y-4 overflow-y-auto pr-2">
              {/* Crawled URLs */}
              <div className="space-y-2">
                <h4 className="font-medium flex items-center gap-2 text-green-700">
                  <CheckCircle2 className="h-4 w-4" />
                  Crawled ({urlDetails.crawled_urls?.length || 0})
                </h4>
                {urlDetails.crawled_urls?.length > 0 ? (
                  <div className="text-sm space-y-1 max-h-40 overflow-y-auto bg-green-50 rounded-md p-2">
                    {urlDetails.crawled_urls.map((item, i) => (
                      <div key={i} className="flex justify-between items-start gap-2 py-1">
                        <span className="truncate text-green-800" title={item.url}>
                          {item.title || item.url}
                        </span>
                        <Badge variant="outline" className="shrink-0 text-xs">
                          {item.chunks} chunks
                        </Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No URLs crawled</p>
                )}
              </div>

              {/* Failed URLs */}
              <div className="space-y-2">
                <h4 className="font-medium flex items-center gap-2 text-red-700">
                  <XCircle className="h-4 w-4" />
                  Failed ({urlDetails.failed_urls?.length || 0})
                </h4>
                {urlDetails.failed_urls?.length > 0 ? (
                  <div className="text-sm space-y-1 max-h-40 overflow-y-auto bg-red-50 rounded-md p-2">
                    {urlDetails.failed_urls.map((item, i) => (
                      <div key={i} className="py-1">
                        <div className="truncate text-red-800" title={item.url}>
                          {item.url}
                        </div>
                        <div className="text-xs text-red-600">{item.reason}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No failures</p>
                )}
              </div>

              {/* Skipped URLs */}
              <div className="space-y-2">
                <h4 className="font-medium flex items-center gap-2 text-yellow-700">
                  <AlertCircle className="h-4 w-4" />
                  Skipped ({urlDetails.skipped_urls?.length || 0})
                </h4>
                {urlDetails.skipped_urls?.length > 0 ? (
                  <div className="text-sm space-y-1 max-h-40 overflow-y-auto bg-yellow-50 rounded-md p-2">
                    {urlDetails.skipped_urls.map((item, i) => (
                      <div key={i} className="py-1">
                        <div className="truncate text-yellow-800" title={item.url}>
                          {item.url}
                        </div>
                        <div className="text-xs text-yellow-600">{item.reason}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No URLs skipped</p>
                )}
              </div>
            </div>
          ) : null}

          <DialogFooter>
            <Button variant="outline" onClick={() => setUrlDetailsOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DashboardLayout >
  );
}
