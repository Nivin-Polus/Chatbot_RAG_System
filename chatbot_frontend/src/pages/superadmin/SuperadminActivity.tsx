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
      console.warn('Failed to normalize activity timestamp', rawTimestamp, error);
      return new Date().toISOString();
    }
  };

  const fetchActivityData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [recentResponse, statsResponse] = await Promise.all([
        fetch(`${import.meta.env.VITE_API_BASE_URL}/activity/recent?limit=50`, {
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
        setActivities(normalized);
      } else {
        setActivities([]);
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
      console.error('Error fetching activity data:', error);
      toast.error('Failed to fetch activity data');
      // Ensure activities is always an array even on error
      setActivities([]);
    } finally {
      setIsLoading(false);
    }
  }, [user?.access_token]);

  useEffect(() => {
    fetchActivityData().catch(() => undefined);
  }, [fetchActivityData]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      fetchActivityData().catch(() => undefined);
    }, 60000);

    return () => {
      window.clearInterval(interval);
    };
  }, [fetchActivityData]);

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

  const filteredActivities = useMemo(() => {
    if (timeFilter === 'all') {
      return activities;
    }

    const now = Date.now();
    const windowMs =
      timeFilter === '24h'
        ? 24 * 60 * 60 * 1000
        : timeFilter === '7d'
        ? 7 * 24 * 60 * 60 * 1000
        : 30 * 24 * 60 * 60 * 1000;

    return activities.filter((activity) => {
      const timestamp = new Date(activity.timestamp).getTime();
      return Number.isFinite(timestamp) && now - timestamp <= windowMs;
    });
  }, [activities, timeFilter]);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Activity Dashboard</h1>
            
          </div>
          <div className="flex items-center space-x-2">
            <Select value={timeFilter} onValueChange={(value: 'all' | '24h' | '7d' | '30d') => setTimeFilter(value)}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="Time range" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="24h">Last 24 hours</SelectItem>
                <SelectItem value="7d">Last 7 days</SelectItem>
                <SelectItem value="30d">Last 30 days</SelectItem>
                <SelectItem value="all">All time</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={fetchActivityData} disabled={isLoading}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
          </div>
        </div>

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
            </CardTitle>
            
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : !filteredActivities || filteredActivities.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No activity found for the selected range
              </div>
            ) : (
              <div className="space-y-3">
                {filteredActivities.map((activity) => (
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
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
