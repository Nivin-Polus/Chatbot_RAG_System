import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { DashboardLayout } from '@/components/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Activity, RefreshCw, Loader2, TrendingUp, Users, FileText, MessageSquare } from 'lucide-react';
import { toast } from 'sonner';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
  PaginationEllipsis,
} from '@/components/ui/pagination';

type ActivityDetails = Record<string, unknown> | null | undefined;

interface ActivityItem {
  id: string;
  type: string;
  timestamp: string;
  user?: string;
  description?: string;
  collection?: string;
  details?: ActivityDetails;
  metadata?: ActivityDetails;
}

interface ActivityStats {
  total_files: number;
  total_users: number;
  total_chats: number;
  recent_activity: number;
}

export default function SuperadminActivity() {
  const { user } = useAuth();
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [stats, setStats] = useState<ActivityStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [timeFilter, setTimeFilter] = useState<'all' | '24h' | '7d' | '30d'>('24h');
  const [activityTypeFilter, setActivityTypeFilter] = useState<string>('all');
  const [userFilter, setUserFilter] = useState<string>('all');
  const [collectionFilter, setCollectionFilter] = useState<string>('all');
  const [availableUsers, setAvailableUsers] = useState<{ id: string; username: string }[]>([]);
  const [availableCollections, setAvailableCollections] = useState<{ id: string; name: string }[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [totalActivities, setTotalActivities] = useState(0);
  const itemsPerPage = 500; // Increased from 100 to allow loading more queries

  const normalizeTimestamp = (rawTimestamp: any): string => {
    if (!rawTimestamp) {
      return new Date().toISOString();
    }

    if (rawTimestamp instanceof Date) {
      return rawTimestamp.toISOString();
    }

    if (typeof rawTimestamp === 'number') {
      return new Date(rawTimestamp).toISOString();
    }

    if (typeof rawTimestamp === 'string') {
      const trimmed = rawTimestamp.trim();
      if (!trimmed) {
        return new Date().toISOString();
      }

      const hasOffset = /([zZ]|[+-]\d{2}:?\d{2})$/.test(trimmed);
      const normalizedString = hasOffset
        ? trimmed
        : `${trimmed.replace(/\s+/g, 'T').replace(/T{2,}/g, 'T')}Z`;

      const parsed = new Date(normalizedString);
      if (!Number.isNaN(parsed.getTime())) {
        return parsed.toISOString();
      }
    }

    try {
      return new Date(rawTimestamp).toISOString();
    } catch (error) {
      return new Date().toISOString();
    }
  };

  const fetchActivityData = useCallback(async () => {
    setIsLoading(true);
    try {
      // Calculate since_hours based on timeFilter
      let sinceHours: number | undefined;
      if (timeFilter === '24h') {
        sinceHours = 24;
      } else if (timeFilter === '7d') {
        sinceHours = 24 * 7; // 168 hours
      } else if (timeFilter === '30d') {
        sinceHours = 24 * 30; // 720 hours
      }
      // For 'all', sinceHours remains undefined to fetch all activities

      const offset = (currentPage - 1) * itemsPerPage;
      const queryParams = new URLSearchParams({
        limit: itemsPerPage.toString(),
        offset: offset.toString(),
        ...(sinceHours !== undefined && { since_hours: sinceHours.toString() }),
        ...(activityTypeFilter && activityTypeFilter !== 'all' && { activity_type: activityTypeFilter }),
        ...(userFilter && userFilter !== 'all' && { username: userFilter }),
        ...(collectionFilter && collectionFilter !== 'all' && { collection_id: collectionFilter })
      });

      const [recentResponse, statsResponse] = await Promise.all([
        fetch(`${import.meta.env.VITE_API_BASE_URL}/activity/recent?${queryParams}`, {
          headers: {
            Authorization: `Bearer ${user?.access_token}`,
          },
        }),
        fetch(`${import.meta.env.VITE_API_BASE_URL}/activity/stats`, {
          headers: {
            Authorization: `Bearer ${user?.access_token}`,
          },
        }),
      ]);

      if (recentResponse.ok) {
        const recentData = await recentResponse.json();
        const rawActivities: any[] = Array.isArray(recentData)
          ? recentData
          : Array.isArray(recentData?.activities)
            ? recentData.activities
            : [];

        const normalized = rawActivities.map(normalizeActivityItem);

        // Always replace activities when fetching a new page
        setActivities(normalized);

        // Use the total count from the API response
        const total = recentData.total ?? recentData.count ?? rawActivities.length;
        setTotalActivities(total);
        setHasMore(recentData.has_more ?? (rawActivities.length === itemsPerPage && offset + rawActivities.length < total));
      } else {
        setActivities([]);
        setHasMore(false);
        setTotalActivities(0);
      }

      if (statsResponse.ok) {
        const statsData = await statsResponse.json();
        const parsedStats = statsData?.stats || statsData || null;
        if (parsedStats) {
          setStats({
            total_files: parsedStats.total_files ?? parsedStats.total_files_uploaded ?? 0,
            total_users: parsedStats.total_users ?? 0,
            total_chats: parsedStats.total_chats ?? parsedStats.total_chat_sessions ?? 0,
            recent_activity: parsedStats.recent_activity ?? parsedStats.recent_activity_24h ?? 0,
          });
        } else {
          setStats(null);
        }
      } else {
        setStats(null);
      }
    } catch (error) {
      toast.error('Failed to fetch activity data');
      // Ensure activities is always an array even on error
      setActivities([]);
      setTotalActivities(0);
      setHasMore(false);
    } finally {
      setIsLoading(false);
    }
  }, [user?.access_token, currentPage, itemsPerPage, timeFilter, activityTypeFilter, userFilter, collectionFilter]);

  const fetchUsers = useCallback(async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/users/`, {
        headers: {
          Authorization: `Bearer ${user?.access_token}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setAvailableUsers(data.map((u: any) => ({ id: u.user_id, username: u.username })));
      }
    } catch (error) {
      console.error('Failed to fetch users', error);
    }
  }, [user?.access_token]);

  const fetchCollections = useCallback(async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/collections/summary`, {
        headers: {
          Authorization: `Bearer ${user?.access_token}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setAvailableCollections(data.map((c: any) => ({ id: c.collection_id, name: c.name })));
      }
    } catch (error) {
      console.error('Failed to fetch collections', error);
    }
  }, [user?.access_token]);

  useEffect(() => {
    // Reset to page 1 when filters change
    setCurrentPage(1);
  }, [timeFilter, activityTypeFilter, userFilter, collectionFilter]);

  useEffect(() => {
    // Fetch data when page or filters change
    fetchActivityData().catch(() => undefined);
  }, [fetchActivityData]);

  useEffect(() => {
    // Fetch lookup data on mount
    fetchUsers().catch(() => undefined);
    fetchCollections().catch(() => undefined);
  }, [fetchUsers, fetchCollections]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      // Only refresh if we're at the first page
      if (currentPage === 1) {
        fetchActivityData().catch(() => undefined);
      }
    }, 60000);

    return () => {
      window.clearInterval(interval);
    };
  }, [fetchActivityData, currentPage]);

  const normalizeActivityItem = (raw: any): ActivityItem => {
    const id = raw?.id || raw?.activity_id || crypto.randomUUID();
    const type = (raw?.type || raw?.activity_type || 'unknown').toString();
    const timestamp = normalizeTimestamp(raw?.timestamp || raw?.created_at || new Date().toISOString());
    const userValue = raw?.user || raw?.username;
    const details = (raw?.details && typeof raw.details === 'object') ? raw.details : null;
    const metadata = (raw?.metadata && typeof raw.metadata === 'object') ? raw.metadata : null;

    const derivedDescription = formatActivityDescription(type, details, metadata);
    const collectionName = getCollectionLabel(details);

    return {
      id,
      type,
      timestamp,
      user: typeof userValue === 'string' ? userValue : undefined,
      description: derivedDescription,
      collection: collectionName,
      details,
      metadata,
    };
  };

  const getCollectionLabel = (details: ActivityDetails): string | undefined => {
    if (!details || typeof details !== 'object') return undefined;
    if (typeof details.collection === 'string' && details.collection) return details.collection;
    if (typeof details.collection_name === 'string' && details.collection_name) return details.collection_name;
    if (typeof details.collection_id === 'string' && details.collection_id) return details.collection_id;
    return undefined;
  };

  const formatActivityDescription = (
    type: string,
    details: ActivityDetails,
    metadata: ActivityDetails
  ): string | undefined => {
    const descriptionFromPayload =
      typeof details === 'object' && details && typeof details.description === 'string'
        ? details.description
        : undefined;

    if (descriptionFromPayload) {
      return descriptionFromPayload;
    }

    const safeDetails = typeof details === 'object' && details ? details : {};
    const safeMetadata = typeof metadata === 'object' && metadata ? metadata : {};

    switch (type) {
      case 'file_upload':
        return `Uploaded ${safeDetails.file_name ?? 'a file'}${safeDetails.collection_id ? ` to ${safeDetails.collection_id}` : ''}`;
      case 'file_download':
        return `Downloaded ${safeDetails.file_name ?? 'a file'}`;
      case 'file_delete':
        return `Deleted ${safeDetails.file_name ?? safeDetails.file_id ?? 'a file'}`;
      case 'chat_session_start':
        return `Started a chat session (${safeDetails.session_id ?? 'new session'})`;
      case 'chat_query':
        return `Asked a question${safeDetails.question ? `: "${safeDetails.question}"` : ''}`;
      case 'collection_created':
        return `Created collection ${safeDetails.collection_name ?? safeDetails.collection_id ?? ''}`.trim();
      case 'system_reset':
        return 'System reset initiated';
      case 'user_created':
      case 'user_registered':
        return `Added user ${safeDetails.username ?? ''}`.trim();
      case 'user_login':
        return `Logged in${safeMetadata.ip_address ? ` from ${safeMetadata.ip_address}` : ''}`;
      default:
        if (Object.keys(safeDetails).length > 0) {
          return Object.entries(safeDetails)
            .map(([key, value]) => `${key}: ${String(value)}`)
            .join(', ');
        }
        return undefined;
    }
  };

  const formatActivityType = (type: ActivityItem['type']) => {
    return type
      .split('_')
      .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
      .join(' ');
  };

  const getActivityIcon = (type: ActivityItem['type']) => {
    switch (type) {
      case 'file_upload':
      case 'file_download':
        return <FileText className="h-4 w-4" />;
      case 'file_delete':
        return <FileText className="h-4 w-4" />;
      case 'user_login':
        return <Users className="h-4 w-4" />;
      case 'chat_message':
        return <MessageSquare className="h-4 w-4" />;
      case 'chat_query':
        return <MessageSquare className="h-4 w-4" />;
      case 'chat_session_start':
        return <MessageSquare className="h-4 w-4" />;
      case 'collection_created':
        return <Activity className="h-4 w-4" />;
      case 'system_reset':
        return <RefreshCw className="h-4 w-4" />;
      default:
        return <Activity className="h-4 w-4" />;
    }
  };

  const getActivityColor = (type: ActivityItem['type']) => {
    switch (type) {
      case 'file_upload':
        return 'text-green-600';
      case 'file_download':
        return 'text-blue-600';
      case 'file_delete':
        return 'text-red-600';
      case 'user_login':
        return 'text-purple-600';
      case 'chat_message':
        return 'text-orange-600';
      case 'chat_query':
        return 'text-orange-600';
      case 'chat_session_start':
        return 'text-indigo-600';
      case 'collection_created':
        return 'text-indigo-600';
      case 'system_reset':
        return 'text-rose-600';
      default:
        return 'text-gray-600';
    }
  };

  const formatTimeAgo = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diffInSeconds < 60) return 'Just now';
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
    return `${Math.floor(diffInSeconds / 86400)}d ago`;
  };

  const handleRefresh = () => {
    setCurrentPage(1);
    fetchActivityData();
  };

  const totalPages = Math.ceil(totalActivities / itemsPerPage);

  const getPageNumbers = () => {
    const pages: (number | 'ellipsis')[] = [];
    const maxVisible = 7;

    if (totalPages <= maxVisible) {
      // Show all pages if total is small
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // Always show first page
      pages.push(1);

      if (currentPage <= 3) {
        // Near the start
        for (let i = 2; i <= 5; i++) {
          pages.push(i);
        }
        pages.push('ellipsis');
        pages.push(totalPages);
      } else if (currentPage >= totalPages - 2) {
        // Near the end
        pages.push('ellipsis');
        for (let i = totalPages - 4; i <= totalPages; i++) {
          pages.push(i);
        }
      } else {
        // In the middle
        pages.push('ellipsis');
        for (let i = currentPage - 1; i <= currentPage + 1; i++) {
          pages.push(i);
        }
        pages.push('ellipsis');
        pages.push(totalPages);
      }
    }

    return pages;
  };

  const handleClearFilters = () => {
    setActivityTypeFilter('all');
    setUserFilter('all');
    setCollectionFilter('all');
    setTimeFilter('24h');
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Activity Dashboard</h1>
          </div>
          <div className="flex items-center space-x-2">
            <Button variant="outline" onClick={handleRefresh} disabled={isLoading}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Filters */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Filters
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
              <div>
                <label className="text-sm font-medium mb-1 block">Time Range</label>
                <Select value={timeFilter} onValueChange={(value: 'all' | '24h' | '7d' | '30d') => setTimeFilter(value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Time range" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="24h">Last 24 hours</SelectItem>
                    <SelectItem value="7d">Last 7 days</SelectItem>
                    <SelectItem value="30d">Last 30 days</SelectItem>
                    <SelectItem value="all">All time</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium mb-1 block">Activity Type</label>
                <Select value={activityTypeFilter} onValueChange={setActivityTypeFilter}>
                  <SelectTrigger>
                    <SelectValue placeholder="All types" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All types</SelectItem>
                    <SelectItem value="file_upload">File Upload</SelectItem>
                    <SelectItem value="file_download">File Download</SelectItem>
                    <SelectItem value="file_delete">File Delete</SelectItem>
                    <SelectItem value="user_login">User Login</SelectItem>
                    <SelectItem value="chat_session_start">Chat Session Start</SelectItem>
                    <SelectItem value="chat_query">Chat Query</SelectItem>
                    <SelectItem value="collection_created">Collection Created</SelectItem>
                    <SelectItem value="user_created">User Created</SelectItem>
                    <SelectItem value="system_reset">System Reset</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium mb-1 block">User</label>
                <Select value={userFilter} onValueChange={setUserFilter}>
                  <SelectTrigger>
                    <SelectValue placeholder="All users" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All users</SelectItem>
                    {availableUsers.map((u) => (
                      <SelectItem key={u.id} value={u.username}>
                        {u.username}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium mb-1 block">Collection</label>
                <Select value={collectionFilter} onValueChange={setCollectionFilter}>
                  <SelectTrigger>
                    <SelectValue placeholder="All collections" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All collections</SelectItem>
                    {availableCollections.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-end">
                <Button variant="outline" onClick={handleClearFilters} className="w-full">
                  Clear Filters
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Statistics Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Files</CardTitle>
                <FileText className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats.total_files}</div>
                <p className="text-xs text-muted-foreground">Files uploaded</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Users</CardTitle>
                <Users className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats.total_users}</div>
                <p className="text-xs text-muted-foreground">Registered users</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Chat Messages</CardTitle>
                <MessageSquare className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats.total_chats}</div>
                <p className="text-xs text-muted-foreground">Messages sent</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Recent Activity</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats.recent_activity}</div>
                <p className="text-xs text-muted-foreground">Last 24 hours</p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Recent Activity
              <span className="text-sm font-normal text-muted-foreground ml-2">
                {totalActivities > 0 ? (
                  <>
                    Showing {((currentPage - 1) * itemsPerPage) + 1} - {Math.min(currentPage * itemsPerPage, totalActivities)} of {totalActivities} activities
                  </>
                ) : (
                  'No activities'
                )}
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading && currentPage === 1 ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : !activities || activities.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No activity found for the selected filters
              </div>
            ) : (
              <div className="space-y-3">
                {activities.map((activity) => (
                  <div
                    key={activity.id}
                    className="rounded-xl border bg-card/60 backdrop-blur p-4 transition-colors hover:bg-card"
                  >
                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                      <div className="flex items-start gap-3">
                        <div
                          className={`flex h-10 w-10 items-center justify-center rounded-full bg-muted ${getActivityColor(
                            activity.type
                          )}`}
                        >
                          {getActivityIcon(activity.type)}
                        </div>
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <span className="rounded-full bg-muted px-2 py-0.5 font-medium text-[0.7rem] uppercase tracking-wide">
                              {formatActivityType(activity.type)}
                            </span>
                            <span>
                              {formatTimeAgo(activity.timestamp)} ·{' '}
                              {new Date(activity.timestamp).toLocaleString()}
                            </span>
                          </div>
                          <p className="text-sm font-semibold text-foreground leading-relaxed">
                            {activity.description}
                          </p>
                          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                            {activity.user && (
                              <span className="rounded-full bg-muted px-2 py-0.5">
                                User <span className="font-medium text-foreground">{activity.user}</span>
                              </span>
                            )}
                            {activity.collection && (
                              <span className="rounded-full bg-muted px-2 py-0.5">
                                Knowledge Base{' '}
                                <span className="font-medium text-foreground">{activity.collection}</span>
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}

                {totalPages > 1 && (
                  <div className="flex justify-center py-4">
                    <Pagination>
                      <PaginationContent>
                        <PaginationItem>
                          <PaginationPrevious
                            onClick={(e) => {
                              e.preventDefault();
                              if (currentPage > 1) {
                                setCurrentPage(prev => prev - 1);
                              }
                            }}
                            className={currentPage === 1 ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                            href="#"
                          />
                        </PaginationItem>

                        {getPageNumbers().map((page, index) => {
                          if (page === 'ellipsis') {
                            return (
                              <PaginationItem key={`ellipsis-${index}`}>
                                <PaginationEllipsis />
                              </PaginationItem>
                            );
                          }
                          return (
                            <PaginationItem key={page}>
                              <PaginationLink
                                onClick={(e) => {
                                  e.preventDefault();
                                  setCurrentPage(page);
                                }}
                                isActive={currentPage === page}
                                className="cursor-pointer"
                                href="#"
                              >
                                {page}
                              </PaginationLink>
                            </PaginationItem>
                          );
                        })}

                        <PaginationItem>
                          <PaginationNext
                            onClick={(e) => {
                              e.preventDefault();
                              if (currentPage < totalPages) {
                                setCurrentPage(prev => prev + 1);
                              }
                            }}
                            className={currentPage === totalPages ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                            href="#"
                          />
                        </PaginationItem>
                      </PaginationContent>
                    </Pagination>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}