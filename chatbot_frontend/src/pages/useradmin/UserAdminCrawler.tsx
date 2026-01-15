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
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from '@/components/ui/collapsible';
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
    Info,
    ChevronDown,
    ChevronUp,
} from 'lucide-react';
import { toast } from 'sonner';
import { apiGet, apiPost, apiDelete } from '@/utils/api';

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
    total_characters: number;
    progress_percent: number;
    current_url?: string;
    error_message?: string;
    is_scheduled?: boolean;
    schedule_interval_hours?: number;
    next_run_at?: string;
    created_at?: string;
    started_at?: string;
    completed_at?: string;
}

interface Collection {
    collection_id: string;
    name: string;
}

export default function UserAdminCrawler() {
    const { user } = useAuth();
    const [collection, setCollection] = useState<Collection | null>(null);
    const [jobs, setJobs] = useState<CrawlJob[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isStarting, setIsStarting] = useState(false);
    const [showAdvanced, setShowAdvanced] = useState(false);

    // Form state
    const [targetUrl, setTargetUrl] = useState('');
    const [maxPages, setMaxPages] = useState<number | string>(0); // 0 = unlimited
    const [maxDepth, setMaxDepth] = useState<number | string>(0);
    const [useSitemap, setUseSitemap] = useState(true);
    const [processDocuments, setProcessDocuments] = useState(true);
    const [excludePatterns, setExcludePatterns] = useState('/login\n/admin\n/cart');
    const [includeKeywords, setIncludeKeywords] = useState('');

    // Schedule dialog state
    const [scheduleDialogOpen, setScheduleDialogOpen] = useState(false);
    const [scheduleJobId, setScheduleJobId] = useState<string | null>(null);
    const [scheduleInterval, setScheduleInterval] = useState('1440');
    const [isScheduling, setIsScheduling] = useState(false);

    // Delete confirmation state
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [jobIdToDelete, setJobIdToDelete] = useState<string | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    // Cancel confirmation state
    const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
    const [jobIdToCancel, setJobIdToCancel] = useState<string | null>(null);
    const [isCancelling, setIsCancelling] = useState(false);

    // Fetch user's collection (user admins have access to their assigned collection)
    const fetchCollection = useCallback(async () => {
        try {
            const response = await apiGet(
                `${import.meta.env.VITE_API_BASE_URL}/collections/summary`,
                user?.access_token
            );
            if (response.ok) {
                const data = await response.json();
                // User admin typically has one collection assigned
                if (data && data.length > 0) {
                    setCollection(data[0]);
                }
            }
        } catch (error) {
            // Failed to fetch collection
        }
    }, [user?.access_token]);

    // Fetch crawl jobs for the user's collection
    const fetchJobs = useCallback(async () => {
        if (!collection) {
            setIsLoading(false);
            return;
        }

        try {
            // Suppress logout on 401 for polling to prevent disruption during long crawl jobs
            const response = await apiGet(
                `${import.meta.env.VITE_API_BASE_URL}/crawler/jobs?collection_id=${collection.collection_id}`,
                user?.access_token,
                false, // showErrorToast = false
                false  // logoutOn401 = false - don't logout on expired token during polling
            );
            if (response.ok) {
                const data = await response.json();
                setJobs(data.jobs || []);
            } else if (response.status === 401) {
                // Token expired - silently fail to avoid disrupting long-running crawl monitoring
                // User can manually refresh the page to re-authenticate if needed
                console.warn('Token expired during crawl job polling');
            }
        } catch (error) {
            // Failed to fetch jobs - silently handle to avoid disrupting monitoring
        } finally {
            setIsLoading(false);
        }
    }, [user?.access_token, collection]);

    useEffect(() => {
        fetchCollection();
    }, [fetchCollection]);

    useEffect(() => {
        if (collection) {
            fetchJobs();
        }
    }, [collection, fetchJobs]);

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
        if (!targetUrl || !collection) {
            toast.error('Please enter a URL');
            return;
        }

        // Parse numeric values, defaulting to 0/5 if empty or invalid
        const parsedMaxPages = maxPages === '' ? 0 : parseInt(String(maxPages));
        const parsedMaxDepth = maxDepth === '' ? 5 : parseInt(String(maxDepth));

        setIsStarting(true);
        try {
            const response = await apiPost(
                `${import.meta.env.VITE_API_BASE_URL}/crawler/start`,
                {
                    target_url: targetUrl,
                    collection_id: collection.collection_id,
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

    // Show cancel confirmation dialog
    const handleCancelJob = (jobId: string) => {
        setJobIdToCancel(jobId);
        setCancelDialogOpen(true);
    };

    // Perform the actual cancellation
    const confirmCancelJob = async (deleteData: boolean) => {
        if (!jobIdToCancel) return;

        setIsCancelling(true);
        try {
            const response = await apiPost(
                `${import.meta.env.VITE_API_BASE_URL}/crawler/jobs/${jobIdToCancel}/cancel`,
                { delete_crawled_data: deleteData },
                user?.access_token
            );

            if (response.ok) {
                toast.success(deleteData ? 'Crawl cancelled and data deleted' : 'Crawl cancelled, data kept');
                fetchJobs();
            } else {
                toast.error('Failed to cancel crawl');
            }
        } catch (error) {
            toast.error('Failed to cancel crawl');
        } finally {
            setIsCancelling(false);
            setCancelDialogOpen(false);
            setJobIdToCancel(null);
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

    // Format date
    const formatDate = (dateString?: string) => {
        if (!dateString) return '-';
        return new Date(dateString).toLocaleString();
    };

    // Active jobs
    const activeJobs = jobs.filter(j => j.status === 'running' || j.status === 'pending');
    const completedJobs = jobs.filter(j => j.status !== 'running' && j.status !== 'pending');

    if (!collection) {
        return (
            <DashboardLayout>
                <div className="flex flex-col items-center justify-center py-12 text-center">
                    <AlertCircle className="h-12 w-12 text-muted-foreground mb-4" />
                    <h2 className="text-lg font-semibold">No Knowledge Base Assigned</h2>
                    <p className="text-muted-foreground">
                        Please contact a super admin to assign a knowledge base to your account.
                    </p>
                </div>
            </DashboardLayout>
        );
    }

    return (
        <DashboardLayout>
            <div className="space-y-6 h-full overflow-auto">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold flex items-center gap-2">
                            <Globe className="h-6 w-6" />
                            Web Crawler
                        </h1>
                        <p className="text-muted-foreground">
                            Crawl websites and add content to <strong>{collection.name}</strong>
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
                            Enter a website URL to crawl and add to your knowledge base
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="target-url">Website URL</Label>
                            <Input
                                id="target-url"
                                placeholder="https://example.com"
                                value={targetUrl}
                                onChange={(e) => setTargetUrl(e.target.value)}
                            />
                        </div>

                        {/* Advanced Settings */}
                        <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced} className="border rounded-lg bg-muted/20">
                            <CollapsibleTrigger asChild>
                                <Button
                                    variant="ghost"
                                    className="flex w-full items-center justify-between p-4 transition-colors"
                                >
                                    <div className="flex items-center gap-2 font-medium">
                                        <Settings2 className="h-4 w-4" />
                                        Advanced Settings
                                    </div>
                                    {showAdvanced ? (
                                        <ChevronUp className="h-4 w-4 text-muted-foreground" />
                                    ) : (
                                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                                    )}
                                </Button>
                            </CollapsibleTrigger>
                            <CollapsibleContent className="p-4 pt-0 space-y-6">
                                <div className="grid gap-6 md:grid-cols-2 pt-2">
                                    <div className="space-y-2">
                                        <div className="flex items-center gap-1.5">
                                            <Label htmlFor="max-pages">Max Pages</Label>
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <Info className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground transition-colors cursor-help" />
                                                </TooltipTrigger>
                                                <TooltipContent side="top" className="max-w-[260px] p-3">
                                                    <div className="space-y-1.5">
                                                        <p className="text-xs font-semibold flex items-center gap-1.5">
                                                            <FileText className="h-3 w-3 text-primary" />
                                                            Crawl Limit
                                                        </p>
                                                        <p className="text-[11px] leading-relaxed text-muted-foreground">
                                                            Maximum number of pages to index. Set to <span className="font-medium text-foreground">0</span> for an <span className="font-medium text-foreground">unlimited</span> crawl of the entire domain.
                                                        </p>
                                                    </div>
                                                </TooltipContent>
                                            </Tooltip>
                                        </div>
                                        <Input
                                            id="max-pages"
                                            type="number"
                                            min={0}
                                            value={maxPages}
                                            onChange={(e) => setMaxPages(e.target.value)}
                                            placeholder="0 for unlimited"
                                            className="bg-background"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <div className="flex items-center gap-1.5">
                                            <Label htmlFor="max-depth">Max Depth</Label>
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <Info className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground transition-colors cursor-help" />
                                                </TooltipTrigger>
                                                <TooltipContent side="top" className="max-w-[260px] p-3">
                                                    <div className="space-y-1.5">
                                                        <p className="text-xs font-semibold flex items-center gap-1.5">
                                                            <Link2 className="h-3 w-3 text-primary" />
                                                            Link Depth
                                                        </p>
                                                        <p className="text-[11px] leading-relaxed text-muted-foreground">
                                                            How many steps away from the start URL the crawler will go. Set to <span className="font-medium text-foreground">0</span> for <span className="font-medium text-foreground">unlimited</span> depth. Default is <span className="font-medium text-foreground">5</span>.
                                                        </p>
                                                    </div>
                                                </TooltipContent>
                                            </Tooltip>
                                        </div>
                                        <Input
                                            id="max-depth"
                                            type="number"
                                            min={0}
                                            value={maxDepth}
                                            onChange={(e) => setMaxDepth(e.target.value)}
                                            placeholder="0 for unlimited"
                                            className="bg-background"
                                        />
                                    </div>
                                </div>

                                <div className="grid gap-6 md:grid-cols-2">
                                    <div className="space-y-4">
                                        <div className="flex items-center justify-between border p-3 rounded-md bg-background">
                                            <div className="space-y-0.5">
                                                <div className="flex items-center gap-1.5">
                                                    <Label htmlFor="use-sitemap" className="text-base cursor-pointer">Sitemap Discovery</Label>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Info className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground transition-colors cursor-help" />
                                                        </TooltipTrigger>
                                                        <TooltipContent side="right" className="max-w-[260px] p-3">
                                                            <div className="space-y-1.5">
                                                                <p className="text-xs font-semibold flex items-center gap-1.5">
                                                                    <Globe className="h-3 w-3 text-primary" />
                                                                    Sitemap Discovery
                                                                </p>
                                                                <p className="text-[11px] leading-relaxed text-muted-foreground">
                                                                    When enabled, the crawler reads your domain's <code className="text-[10px] bg-muted px-1 py-0.5 rounded">sitemap.xml</code> to find and index pages much more efficiently.
                                                                </p>
                                                            </div>
                                                        </TooltipContent>
                                                    </Tooltip>
                                                </div>
                                                <p className="text-xs text-muted-foreground">
                                                    Use sitemap.xml to find pages faster
                                                </p>
                                            </div>
                                            <Switch
                                                id="use-sitemap"
                                                checked={useSitemap}
                                                onCheckedChange={setUseSitemap}
                                            />
                                        </div>
                                        <div className="flex items-center justify-between border p-3 rounded-md bg-background">
                                            <div className="space-y-0.5">
                                                <div className="flex items-center gap-1.5">
                                                    <Label htmlFor="process-documents" className="text-base cursor-pointer">Process Documents</Label>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Info className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground transition-colors cursor-help" />
                                                        </TooltipTrigger>
                                                        <TooltipContent side="right" className="max-w-[260px] p-3">
                                                            <div className="space-y-1.5">
                                                                <p className="text-xs font-semibold flex items-center gap-1.5">
                                                                    <FileText className="h-3 w-3 text-primary" />
                                                                    Document Analysis
                                                                </p>
                                                                <p className="text-[11px] leading-relaxed text-muted-foreground">
                                                                    Extract text content from <span className="font-medium text-foreground">PDF and Word</span> files found during crawling to include in your knowledge base knowledge.
                                                                </p>
                                                            </div>
                                                        </TooltipContent>
                                                    </Tooltip>
                                                </div>
                                                <p className="text-xs text-muted-foreground">
                                                    Extract text from PDF/Word files
                                                </p>
                                            </div>
                                            <Switch
                                                id="process-documents"
                                                checked={processDocuments}
                                                onCheckedChange={setProcessDocuments}
                                            />
                                        </div>
                                    </div>

                                    <div className="space-y-4">
                                        <div className="space-y-2">
                                            <div className="flex items-center gap-1.5">
                                                <Label htmlFor="exclude-patterns">Exclude Patterns</Label>
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Info className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground transition-colors cursor-help" />
                                                    </TooltipTrigger>
                                                    <TooltipContent side="top" className="max-w-[260px] p-3">
                                                        <div className="space-y-1.5">
                                                            <p className="text-xs font-semibold flex items-center gap-1.5">
                                                                <XCircle className="h-3 w-3 text-destructive" />
                                                                Exclude Substrings
                                                            </p>
                                                            <p className="text-[11px] leading-relaxed text-muted-foreground">
                                                                URLs containing any of these lines will be <span className="font-medium text-foreground">skipped</span>. One pattern per line (e.g. <code className="text-[10px] bg-muted px-1 py-0.5 rounded">/login</code>).
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
                                                className="bg-background resize-none"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <div className="flex items-center gap-1.5">
                                                <Label htmlFor="include-keywords">Include Keywords</Label>
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Info className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground transition-colors cursor-help" />
                                                    </TooltipTrigger>
                                                    <TooltipContent side="top" className="max-w-[260px] p-3">
                                                        <div className="space-y-1.5">
                                                            <p className="text-xs font-semibold flex items-center gap-1.5">
                                                                <AlertCircle className="h-3 w-3 text-primary" />
                                                                Strict Filtering
                                                            </p>
                                                            <p className="text-[11px] leading-relaxed text-muted-foreground">
                                                                Only URLs containing <span className="font-medium text-foreground">at least one</span> of these keywords will be crawled. Leave empty to crawl everything.
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
                                                className="bg-background resize-none"
                                            />
                                        </div>
                                    </div>
                                </div>
                            </CollapsibleContent>
                        </Collapsible>

                        <Button onClick={handleStartCrawl} disabled={isStarting || !targetUrl}>
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
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>URL</TableHead>
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
                                            <TableCell className="max-w-xs truncate">
                                                <div className="flex items-center gap-2">
                                                    {job.target_url}
                                                    {job.is_scheduled && (
                                                        <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200 text-xs">
                                                            <Timer className="h-3 w-3 mr-1" />
                                                            {job.schedule_interval_hours}h
                                                        </Badge>
                                                    )}
                                                </div>
                                            </TableCell>
                                            <TableCell>{getStatusBadge(job.status)}</TableCell>
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
                                                                >
                                                                    <CalendarClock className="h-4 w-4 text-purple-600" />
                                                                </Button>
                                                            </TooltipTrigger>
                                                            <TooltipContent className="text-xs">
                                                                Remove schedule
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
                                                                Schedule recurring crawl
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
                                                            Recrawl now
                                                        </TooltipContent>
                                                    </Tooltip>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                onClick={() => handleDeleteJob(job.job_id)}
                                                            >
                                                                <Trash2 className="h-4 w-4" />
                                                            </Button>
                                                        </TooltipTrigger>
                                                        <TooltipContent className="text-xs">
                                                            Delete
                                                        </TooltipContent>
                                                    </Tooltip>
                                                </div>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
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

            {/* Cancel Confirmation Dialog */}
            <AlertDialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Cancel Crawl Job</AlertDialogTitle>
                        <AlertDialogDescription>
                            The crawl is currently in progress. What would you like to do with the data that has already been crawled?
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter className="flex-col sm:flex-row gap-2">
                        <AlertDialogCancel disabled={isCancelling}>
                            Don't Cancel
                        </AlertDialogCancel>
                        <Button
                            variant="outline"
                            onClick={() => confirmCancelJob(false)}
                            disabled={isCancelling}
                            className="sm:mr-auto"
                        >
                            {isCancelling ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    Cancelling...
                                </>
                            ) : (
                                <>
                                    <CheckCircle2 className="h-4 w-4 mr-2" />
                                    Keep Data
                                </>
                            )}
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={() => confirmCancelJob(true)}
                            disabled={isCancelling}
                        >
                            {isCancelling ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    Cancelling...
                                </>
                            ) : (
                                <>
                                    <Trash2 className="h-4 w-4 mr-2" />
                                    Delete Data
                                </>
                            )}
                        </Button>
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
        </DashboardLayout>
    );
}
