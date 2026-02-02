
import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
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
    Loader2,
    CheckCircle2,
    XCircle,
    Clock,
    Settings2,
    FileText,
    Link2,
    CalendarClock,
    Timer,
    Info,
    Trash2,
    Database,
    AlertCircle,
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

interface CrawlerViewProps {
    collectionId?: string; // If provided, locks the view to this collection
}

// Crawler status interface
interface CrawlerStatus {
    is_crawl_running: boolean;
    active_crawl_count: number;
    active_job_ids: string[];
    max_concurrent: number;
    can_start_new: boolean;
}

export default function CrawlerView({ collectionId }: CrawlerViewProps) {
    const { user } = useAuth();
    const [collections, setCollections] = useState<Collection[]>([]);
    const [jobs, setJobs] = useState<CrawlJob[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isStarting, setIsStarting] = useState(false);
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [crawlerStatus, setCrawlerStatus] = useState<CrawlerStatus | null>(null);

    // Schedule dialog state
    const [scheduleDialogOpen, setScheduleDialogOpen] = useState(false);
    const [scheduleJobId, setScheduleJobId] = useState<string | null>(null);
    const [scheduleInterval, setScheduleInterval] = useState('1440');
    const [isScheduling, setIsScheduling] = useState(false);

    // Delete confirmation state
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [jobIdToDelete, setJobIdToDelete] = useState<string | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    // Crawl in progress dialog state
    const [crawlInProgressOpen, setCrawlInProgressOpen] = useState(false);

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
    const [selectedCollection, setSelectedCollection] = useState(collectionId || '');
    const [maxPages, setMaxPages] = useState<number | string>(0); // 0 = max
    const [maxDepth, setMaxDepth] = useState<number | string>(0);
    const [useSitemap, setUseSitemap] = useState(true);
    const [processDocuments, setProcessDocuments] = useState(true);
    const [excludePatterns, setExcludePatterns] = useState('/login\n/admin\n/cart');
    const [includeKeywords, setIncludeKeywords] = useState('');

    // Update selected collection if prop changes
    useEffect(() => {
        if (collectionId) {
            setSelectedCollection(collectionId);
        }
    }, [collectionId]);

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

    // Fetch crawler status (system-wide)
    const fetchCrawlerStatus = useCallback(async () => {
        try {
            const response = await apiGet(
                `${import.meta.env.VITE_API_BASE_URL}/crawler/status`,
                user?.access_token,
                false,
                false
            );
            if (response.ok) {
                const data = await response.json();
                setCrawlerStatus(data);
            }
        } catch (error) {
            // Failed to fetch status
        }
    }, [user?.access_token]);

    // Fetch crawl jobs
    const fetchJobs = useCallback(async () => {
        try {
            // Suppress logout on 401 for polling to prevent disruption during long crawl jobs
            const response = await apiGet(
                `${import.meta.env.VITE_API_BASE_URL}/crawler/jobs`,
                user?.access_token,
                false, // showErrorToast = false
                false  // logoutOn401 = false - don't logout on expired token during polling
            );
            if (response.ok) {
                const data = await response.json();
                let fetchedJobs = data.jobs || [];

                // Filter jobs if collectionId is provided
                if (collectionId) {
                    fetchedJobs = fetchedJobs.filter((job: CrawlJob) => job.collection_id === collectionId);
                }

                setJobs(fetchedJobs);
            } else if (response.status === 401) {
                // Token expired - silently fail to avoid disrupting long-running crawl monitoring
                // User can manually refresh the page to re-authenticate if needed
                console.warn('Token expired during crawl job polling');
            }
        } catch (error) {
            // Failed to fetch jobs - silently handle to avoid disrupting monitoring
            console.error('Failed to fetch jobs:', error);
        } finally {
            setIsLoading(false);
        }
    }, [user?.access_token, collectionId]);

    useEffect(() => {
        fetchCollections();
        fetchJobs();
        fetchCrawlerStatus();
    }, [fetchCollections, fetchJobs, fetchCrawlerStatus]);

    // Auto-refresh running jobs and crawler status
    useEffect(() => {
        const hasRunningJobs = jobs.some(j => j.status === 'running' || j.status === 'pending');
        if (hasRunningJobs || crawlerStatus?.is_crawl_running) {
            const interval = setInterval(() => {
                fetchJobs();
                fetchCrawlerStatus();
            }, 3000);
            return () => clearInterval(interval);
        }
    }, [jobs, crawlerStatus?.is_crawl_running, fetchJobs, fetchCrawlerStatus]);

    // Start a new crawl
    const handleStartCrawl = async () => {
        if (!targetUrl || !selectedCollection) {
            toast.error('Please enter a URL and select a knowledge base');
            return;
        }

        setIsStarting(true);
        try {
            // First check if a crawl is already running
            const statusResponse = await apiGet(
                `${import.meta.env.VITE_API_BASE_URL}/crawler/status`,
                user?.access_token
            );

            if (statusResponse.ok) {
                const status = await statusResponse.json();
                if (status.is_crawl_running) {
                    // Show popup that a crawl is already in progress
                    setCrawlInProgressOpen(true);
                    setIsStarting(false);
                    return;
                }
            }

            // Parse numeric values, defaulting to 0/5 if empty or invalid
            const parsedMaxPages = maxPages === '' ? 0 : parseInt(String(maxPages));
            const parsedMaxDepth = maxDepth === '' ? 5 : parseInt(String(maxDepth));

            const response = await apiPost(
                `${import.meta.env.VITE_API_BASE_URL}/crawler/start`,
                {
                    target_url: targetUrl,
                    collection_id: selectedCollection,
                    max_pages: isNaN(parsedMaxPages) ? 0 : parsedMaxPages,
                    max_depth: isNaN(parsedMaxDepth) ? 5 : parsedMaxDepth,
                    use_sitemap: useSitemap,
                    process_documents: processDocuments,
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
            } else if (response.status === 429) {
                // Crawl already running - show friendly dialog instead of toast
                setCrawlInProgressOpen(true);
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
            } else if (response.status === 429) {
                setCrawlInProgressOpen(true);
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
            } else if (response.status === 429) {
                setScheduleDialogOpen(false);
                setCrawlInProgressOpen(true);
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
    const completedJobs = jobs.filter(j => j.status !== 'running' && j.status !== 'pending' && j.status !== 'scheduled');

    return (
        <div className="space-y-6">
            {!collectionId && (
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
            )}

            {collectionId && (
                <div className="flex justify-end">
                    <Button variant="outline" size="sm" onClick={fetchJobs}>
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Refresh Lists
                    </Button>
                </div>
            )}

            {/* Start New Crawl */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                        <Play className="h-5 w-5" />
                        Start New Crawl
                    </CardTitle>
                    <CardDescription>
                        Enter a website URL to crawl and add content to this knowledge base
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-2">
                        <div className={`space-y-2 ${collectionId ? 'md:col-span-2' : ''}`}>
                            <Label htmlFor="target-url">Website URL</Label>
                            <Input
                                id="target-url"
                                placeholder="https://example.com"
                                value={targetUrl}
                                onChange={(e) => setTargetUrl(e.target.value)}
                            />
                        </div>
                        {!collectionId && (
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
                        )}
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
                                <Label htmlFor="max-pages">Max Pages (0 = max)</Label>
                                <Input
                                    id="max-pages"
                                    type="number"
                                    min={0}
                                    value={maxPages}
                                    onChange={(e) => setMaxPages(e.target.value)}
                                    placeholder="0 = max"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="max-depth">Max Depth (0 = max)</Label>
                                <Input
                                    id="max-depth"
                                    type="number"
                                    min={0}
                                    value={maxDepth}
                                    onChange={(e) => setMaxDepth(e.target.value)}
                                    placeholder="0 = max"
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
                            <div className="space-y-2 md:col-span-2">
                                <div className="flex items-center gap-2">
                                    <Switch
                                        id="process-documents"
                                        checked={processDocuments}
                                        onCheckedChange={setProcessDocuments}
                                    />
                                    <Label htmlFor="process-documents">Download and process PDF/Word documents</Label>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <span className="inline-flex cursor-help text-muted-foreground hover:text-foreground transition-colors">
                                                <Info className="h-4 w-4" />
                                            </span>
                                        </TooltipTrigger>
                                        <TooltipContent side="right" className="max-w-[240px] p-2">
                                            <div className="space-y-1">
                                                <p className="text-xs font-medium">Document processing</p>
                                                <p className="text-xs">
                                                    When enabled, the crawler downloads PDF and Word (.docx) documents and extracts their text content to include in the knowledge base.
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

                    <Button
                        onClick={handleStartCrawl}
                        disabled={isStarting || !targetUrl || !selectedCollection}
                    >
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
                                        {!collectionId && <TableHead>Knowledge Base</TableHead>}
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
                                            {!collectionId && <TableCell>{getCollectionName(job.collection_id)}</TableCell>}
                                            <TableCell>
                                                <div className="flex items-center gap-1.5">
                                                    {getStatusBadge(job.status)}
                                                    {job.status === 'cancelled' && job.chunks_created > 0 && (
                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200 text-xs">
                                                                    <Database className="h-3 w-3 mr-1" />
                                                                    Data Kept
                                                                </Badge>
                                                            </TooltipTrigger>
                                                            <TooltipContent className="text-xs max-w-[200px]">
                                                                {job.chunks_created.toLocaleString()} chunks remain in the knowledge base
                                                            </TooltipContent>
                                                        </Tooltip>
                                                    )}
                                                </div>
                                            </TableCell>
                                            <TableCell className="text-right">{job.pages_crawled}</TableCell>
                                            <TableCell className="text-right">{job.chunks_created}</TableCell>
                                            <TableCell className="text-sm text-muted-foreground">
                                                {formatDate(job.completed_at || job.created_at)}
                                            </TableCell>
                                            <TableCell className="text-right">
                                                <div className="flex justify-end gap-1">
                                                    {job.is_scheduled ? (
                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon"
                                                                    onClick={() => handleUnschedule(job.job_id)}
                                                                    className="text-purple-600 hover:text-purple-700 hover:bg-purple-50"
                                                                >
                                                                    <CalendarClock className="h-4 w-4" />
                                                                </Button>
                                                            </TooltipTrigger>
                                                            <TooltipContent className="text-xs">
                                                                Scheduled (Click to unschedule)
                                                            </TooltipContent>
                                                        </Tooltip>
                                                    ) : (
                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon"
                                                                    onClick={() => openScheduleDialog(job.job_id)}
                                                                >
                                                                    <CalendarClock className="h-4 w-4" />
                                                                </Button>
                                                            </TooltipTrigger>
                                                            <TooltipContent className="text-xs">
                                                                Schedule Recrawl
                                                            </TooltipContent>
                                                        </Tooltip>
                                                    )}
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                onClick={() => handleRecrawl(job.job_id)}
                                                            >
                                                                <RefreshCw className="h-4 w-4" />
                                                            </Button>
                                                        </TooltipTrigger>
                                                        <TooltipContent className="text-xs">
                                                            Recrawl Now
                                                        </TooltipContent>
                                                    </Tooltip>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                onClick={() => handleViewUrlDetails(job.job_id)}
                                                            >
                                                                <FileText className="h-4 w-4" />
                                                            </Button>
                                                        </TooltipTrigger>
                                                        <TooltipContent className="text-xs">
                                                            View URL Details
                                                        </TooltipContent>
                                                    </Tooltip>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="text-red-500 hover:text-red-600 hover:bg-red-50"
                                                                onClick={() => handleDeleteJob(job.job_id)}
                                                            >
                                                                <Trash2 className="h-4 w-4" />
                                                            </Button>
                                                        </TooltipTrigger>
                                                        <TooltipContent className="text-xs text-destructive">
                                                            Delete
                                                        </TooltipContent>
                                                    </Tooltip>
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

            {/* Delete Confirmation Dialog */}
            <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will permanently delete the crawl job and all associated content (chunks) from the knowledge base. This action cannot be undone.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            className="bg-red-600 hover:bg-red-700 text-white"
                            onClick={confirmDeleteJob}
                            disabled={isDeleting}
                        >
                            {isDeleting ? 'Deleting...' : 'Delete'}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            {/* Schedule Dialog */}
            <Dialog open={scheduleDialogOpen} onOpenChange={setScheduleDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Schedule Recrawl</DialogTitle>
                        <DialogDescription>
                            How often should this website be re-crawled automatically?
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="interval">Run Every</Label>
                            <Select value={scheduleInterval} onValueChange={setScheduleInterval}>
                                <SelectTrigger>
                                    <SelectValue placeholder="Select interval" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="1440">2 months (1440 hours)</SelectItem>
                                    <SelectItem value="4320">6 months (4320 hours)</SelectItem>
                                    <SelectItem value="8760">1 year (8760 hours)</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setScheduleDialogOpen(false)}>Cancel</Button>
                        <Button onClick={handleSchedule} disabled={isScheduling}>
                            {isScheduling ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    Scheduling...
                                </>
                            ) : (
                                'Save Schedule'
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* URL Details Dialog */}
            <Dialog open={urlDetailsOpen} onOpenChange={setUrlDetailsOpen}>
                <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Crawl Details</DialogTitle>
                        <DialogDescription>
                            Breakdown of URLs discovered and processed
                        </DialogDescription>
                    </DialogHeader>

                    {urlDetailsLoading ? (
                        <div className="flex items-center justify-center py-12">
                            <Loader2 className="h-8 w-8 animate-spin text-primary" />
                        </div>
                    ) : urlDetails ? (
                        <div className="space-y-6">

                            {/* Stats Summary */}
                            <div className="grid grid-cols-3 gap-4">
                                <div className="p-4 bg-green-50 rounded-lg border border-green-100">
                                    <div className="text-sm font-medium text-green-800">Successfully Crawled</div>
                                    <div className="text-2xl font-bold text-green-600">{urlDetails.crawled_urls.length}</div>
                                </div>
                                <div className="p-4 bg-red-50 rounded-lg border border-red-100">
                                    <div className="text-sm font-medium text-red-800">Failed</div>
                                    <div className="text-2xl font-bold text-red-600">{urlDetails.failed_urls.length}</div>
                                </div>
                                <div className="p-4 bg-gray-50 rounded-lg border border-gray-100">
                                    <div className="text-sm font-medium text-gray-800">Skipped</div>
                                    <div className="text-2xl font-bold text-gray-600">{urlDetails.skipped_urls.length}</div>
                                </div>
                            </div>

                            {/* Failed URLs List */}
                            {urlDetails.failed_urls.length > 0 && (
                                <div className="space-y-3">
                                    <h3 className="font-semibold flex items-center gap-2 text-red-700">
                                        <XCircle className="h-4 w-4" />
                                        Failed URLs
                                    </h3>
                                    <div className="border rounded-md divide-y max-h-60 overflow-y-auto">
                                        {urlDetails.failed_urls.map((item, i) => (
                                            <div key={i} className="p-3 text-sm flex justify-between gap-4">
                                                <span className="font-mono text-xs truncate flex-1" title={item.url}>{item.url}</span>
                                                <span className="text-red-600 whitespace-nowrap">{item.reason}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Skipped URLs List */}
                            {urlDetails.skipped_urls.length > 0 && (
                                <div className="space-y-3">
                                    <h3 className="font-semibold flex items-center gap-2 text-gray-700">
                                        <Square className="h-4 w-4" />
                                        Skipped URLs
                                    </h3>
                                    <div className="border rounded-md divide-y max-h-60 overflow-y-auto">
                                        {urlDetails.skipped_urls.map((item, i) => (
                                            <div key={i} className="p-3 text-sm flex justify-between gap-4">
                                                <span className="font-mono text-xs truncate flex-1" title={item.url}>{item.url}</span>
                                                <span className="text-gray-500 whitespace-nowrap">{item.reason}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Succcessful URLs List */}
                            {urlDetails.crawled_urls.length > 0 && (
                                <div className="space-y-3">
                                    <h3 className="font-semibold flex items-center gap-2 text-green-700">
                                        <CheckCircle2 className="h-4 w-4" />
                                        Crawled Content
                                    </h3>
                                    <div className="border rounded-md divide-y max-h-60 overflow-y-auto">
                                        {urlDetails.crawled_urls.map((item, i) => (
                                            <div key={i} className="p-3 text-sm flex justify-between gap-4">
                                                <div className="flex-1 min-w-0">
                                                    <div className="font-medium truncate">{item.title || 'No Title'}</div>
                                                    <div className="text-xs text-muted-foreground font-mono truncate" title={item.url}>{item.url}</div>
                                                </div>
                                                <Badge variant="secondary" className="h-6">
                                                    {item.chunks} chunks
                                                </Badge>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="text-center py-8 text-muted-foreground">
                            No details available
                        </div>
                    )}
                </DialogContent>
            </Dialog>

            {/* Crawl In Progress Alert Dialog */}
            <AlertDialog open={crawlInProgressOpen} onOpenChange={setCrawlInProgressOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Crawl In Progress</AlertDialogTitle>
                        <AlertDialogDescription>
                            A crawl is already in progress. Only one crawl can run at a time to ensure optimal performance and resource usage. Please wait for the current crawl to complete before starting a new one.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogAction onClick={() => setCrawlInProgressOpen(false)}>
                            OK
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
