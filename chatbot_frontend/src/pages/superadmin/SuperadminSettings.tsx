import { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { DashboardLayout } from '@/components/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Settings, Key, Shield, User, Activity, ShieldCheck, Server, Cpu, FileText } from 'lucide-react';
import { toast } from 'sonner';
import { apiGet, apiPost } from '@/utils/api';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as ChartTooltip, ResponsiveContainer,
  BarChart, Bar, Cell, Legend
} from 'recharts';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import { format, subDays } from 'date-fns';

type HealthComponent = {
  status?: string;
  details?: string;
};

type HealthOverview = {
  overall_status?: string;
  database?: HealthComponent;
  vector_store?: HealthComponent;
  ai_model?: HealthComponent;
  file_processing?: HealthComponent;
  authentication?: HealthComponent;
  storage?: {
    total_size?: string | number;
    file_count?: number;
  };
  services?: Record<string, any>;
  raw?: any;
};

type TokenUsage = {
  total_tokens_used: number;
  total_queries: number;
  scope: 'website' | 'global';
  daily_usage?: Array<{ date: string; queries: number; tokens: number }>;
  model_breakdown?: Array<{ model_name: string; queries: number; tokens: number }>;
  per_website?: Array<{ website_id: string; website_name: string; total_queries: number; total_tokens_used: number }>;
};

const STATUS_COLORS: Record<string, string> = {
  healthy: 'text-emerald-600',
  warning: 'text-amber-600',
  degraded: 'text-amber-600',
  unhealthy: 'text-rose-600',
};

const formatStatus = (status?: string) => {
  if (!status) return 'Unknown';
  return status.charAt(0).toUpperCase() + status.slice(1);
};

const toHealthComponent = (
  source?: Record<string, any> | null,
  fallbackStatus?: string
): HealthComponent | undefined => {
  if (!source && !fallbackStatus) return undefined;

  return {
    status: source?.status ?? fallbackStatus ?? 'healthy',
  };
};

const normalizeHealthResponse = (data: any): HealthOverview => {
  if (!data || typeof data !== 'object') {
    return {};
  }

  const services: Record<string, any> = data.services ?? {};

  const databaseSource =
    data.database ??
    services.database ??
    services.authentication?.database ??
    null;

  const vectorSource = data.vector_store ?? services.qdrant ?? null;
  const aiSource = data.ai_model ?? services.ai_model ?? null;
  const fileSource = data.file_processing ?? services.file_processing ?? null;
  const authSource = data.authentication ?? services.authentication ?? null;
  const defaultStatus = data.overall_status ?? data.status ?? services.overall_status ?? 'healthy';

  return {
    overall_status: defaultStatus,
    database: databaseSource
      ? toHealthComponent(databaseSource)
      : toHealthComponent(undefined, authSource?.status ?? defaultStatus),
    vector_store: toHealthComponent(vectorSource, defaultStatus),
    ai_model: toHealthComponent(aiSource, defaultStatus),
    file_processing: toHealthComponent(fileSource, defaultStatus),
    authentication: toHealthComponent(authSource, defaultStatus),
    services,
    raw: data,
  };
};

export default function SuperadminSettings() {
  const { user } = useAuth();
  const [passwordData, setPasswordData] = useState({
    newPassword: '',
    confirmPassword: '',
  });
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [health, setHealth] = useState<HealthOverview | null>(null);
  const [isHealthLoading, setIsHealthLoading] = useState(false);
  const [tokenUsage, setTokenUsage] = useState<TokenUsage | null>(null);
  const [isTokenUsageLoading, setIsTokenUsageLoading] = useState(false);
  const [websites, setWebsites] = useState<Array<{ website_id: string; name: string }>>([]);

  // Filters
  const [filterDays, setFilterDays] = useState('30');
  const [filterWebsiteId, setFilterWebsiteId] = useState<string>('all');

  const fetchHealth = async () => {
    if (!user?.access_token) {
      toast.error('You must be logged in to view system health');
      return;
    }
    setIsHealthLoading(true);
    try {
      const detailedUrl = `${import.meta.env.VITE_API_BASE_URL}/system/health/detailed`;
      let response = await apiGet(detailedUrl, user.access_token, false, false);

      if (response.status === 404 || response.status === 401) {
        // Fall back to public overview when detailed route unavailable
        response = await apiGet(`${import.meta.env.VITE_API_BASE_URL}/system/health`, undefined, false, false);
      }

      if (response.ok) {
        const data = await response.json();
        const normalized = normalizeHealthResponse(data);
        setHealth(normalized);
      } else {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Failed to fetch system health');
      }
    } catch (error) {
      console.error('System health fetch failed', error);
      toast.error('Unable to load system health information');
      setHealth(null);
    } finally {
      setIsHealthLoading(false);
    }
  };

  const fetchTokenUsage = async () => {
    if (!user?.access_token) {
      return;
    }

    setIsTokenUsageLoading(true);
    try {
      let url: string;
      let scope: TokenUsage['scope'];

      // Calculate date range
      const endDate = new Date();
      const startDate = subDays(endDate, parseInt(filterDays));

      const queryParams = new URLSearchParams({
        start_date: startDate.toISOString(),
        end_date: endDate.toISOString(),
      });

      if (filterWebsiteId !== 'all') {
        queryParams.append('website_id', filterWebsiteId);
      }

      if (user.website_id) {
        // Per-website usage
        url = `${import.meta.env.VITE_API_BASE_URL}/websites/${user.website_id}/analytics?${queryParams.toString()}`;
        scope = 'website';
      } else if (user.role === 'super_admin' || user.role === 'superadmin') {
        // Global usage for superadmins without a website
        url = `${import.meta.env.VITE_API_BASE_URL}/system/stats/token-usage?${queryParams.toString()}`;
        scope = 'global';
      } else {
        setTokenUsage(null);
        return;
      }

      const response = await apiGet(url, user.access_token, false, false);

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Failed to fetch token usage');
      }

      const data = await response.json();

      if (scope === 'website') {
        const analytics = data?.query_analytics || {};
        setTokenUsage({
          total_tokens_used: analytics.total_tokens_used ?? 0,
          total_queries: analytics.total_queries ?? 0,
          scope,
          daily_usage: data?.daily_usage || [],
          model_breakdown: data?.model_breakdown || [],
        });
      } else {
        setTokenUsage({
          total_tokens_used: data?.total_tokens_used ?? 0,
          total_queries: data?.total_queries ?? 0,
          scope,
          daily_usage: data?.daily_usage || [],
          model_breakdown: data?.model_breakdown || [],
          per_website: data?.per_website || [],
        });
      }
    } catch (error) {
      console.error('Token usage fetch failed', error);
      // Non-fatal for settings page; show subtle toast
      toast.error('Unable to load token usage statistics');
      setTokenUsage(null);
    } finally {
      setIsTokenUsageLoading(false);
    }
  };

  const fetchWebsites = async () => {
    if (!user?.access_token || user.role !== 'super_admin') return;
    try {
      const response = await apiGet(`${import.meta.env.VITE_API_BASE_URL}/websites/`, user.access_token);
      if (response.ok) {
        const data = await response.json();
        setWebsites(data);
      }
    } catch (error) {
      console.error('Failed to fetch websites', error);
    }
  };

  useEffect(() => {
    fetchHealth();
    fetchTokenUsage();
    fetchWebsites();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.access_token, filterDays, filterWebsiteId]);

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!user?.user_id) {
      toast.error('Missing user identifier. Please re-login and try again.');
      return;
    }

    if (passwordData.newPassword !== passwordData.confirmPassword) {
      toast.error('New passwords do not match');
      return;
    }

    if (passwordData.newPassword.length < 8) {
      toast.error('New password must be at least 8 characters long');
      return;
    }

    setIsChangingPassword(true);

    try {
      const response = await apiPost(
        `${import.meta.env.VITE_API_BASE_URL}/users/reset-password`,
        {
          user_id: user.user_id,
          new_password: passwordData.newPassword,
        },
        user?.access_token
      );

      if (response.ok) {
        toast.success('Password changed successfully');
        setPasswordData({
          newPassword: '',
          confirmPassword: '',
        });
      } else {
        const error = await response.json().catch(() => ({ detail: 'Failed to change password' }));
        throw new Error(error.detail || 'Failed to change password');
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to change password');
    } finally {
      setIsChangingPassword(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Settings</h1>

        </div>

        <div className="grid gap-6">
          {/* Token Usage Overview */}
          <Card>
            <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-2">
                <Activity className="h-5 w-5" />
                <div>
                  <CardTitle>Token Usage & Analytics</CardTitle>
                  <CardDescription>
                    {tokenUsage?.scope === 'global'
                      ? 'Detailed token consumption and query analytics across all websites'
                      : 'Detailed token consumption and query analytics for this website'}
                  </CardDescription>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {user?.role === 'super_admin' && (
                  <Select value={filterWebsiteId} onValueChange={setFilterWebsiteId}>
                    <SelectTrigger className="w-[180px]">
                      <SelectValue placeholder="All Websites" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Websites</SelectItem>
                      {websites.map((w) => (
                        <SelectItem key={w.website_id} value={w.website_id}>
                          {w.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                <Select value={filterDays} onValueChange={setFilterDays}>
                  <SelectTrigger className="w-[140px]">
                    <SelectValue placeholder="Last 30 days" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="7">Last 7 days</SelectItem>
                    <SelectItem value="30">Last 30 days</SelectItem>
                    <SelectItem value="90">Last 90 days</SelectItem>
                  </SelectContent>
                </Select>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={fetchTokenUsage}
                  disabled={isTokenUsageLoading}
                >
                  {isTokenUsageLoading ? 'Refreshing…' : 'Refresh'}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-8">
              {tokenUsage ? (
                <>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                    <div className="rounded-xl border bg-muted/40 p-4">
                      <div className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                        Total Tokens
                      </div>
                      <div className="mt-2 text-2xl font-bold">
                        {tokenUsage?.total_tokens_used?.toLocaleString() ?? '0'}
                      </div>
                    </div>
                    <div className="rounded-xl border bg-muted/40 p-4">
                      <div className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                        Total Queries
                      </div>
                      <div className="mt-2 text-2xl font-bold">
                        {tokenUsage?.total_queries?.toLocaleString() ?? '0'}
                      </div>
                    </div>
                    <div className="rounded-xl border bg-muted/40 p-4">
                      <div className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                        Avg. Tokens/Query
                      </div>
                      <div className="mt-2 text-2xl font-bold">
                        {tokenUsage.total_queries > 0
                          ? Math.round(tokenUsage.total_tokens_used / tokenUsage.total_queries).toLocaleString()
                          : '0'}
                      </div>
                    </div>
                    <div className="rounded-xl border bg-muted/40 p-4">
                      <div className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                        Active Models
                      </div>
                      <div className="mt-2 text-2xl font-bold">
                        {tokenUsage.model_breakdown?.length ?? 0}
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-8 lg:grid-cols-3">
                    <div className="lg:col-span-2 space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Usage Over Time</h3>
                      </div>
                      <div className="h-[300px] w-full rounded-xl border bg-card p-4">
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={tokenUsage.daily_usage}>
                            <defs>
                              <linearGradient id="colorTokens" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                                <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted-foreground))" opacity={0.1} />
                            <XAxis
                              dataKey="date"
                              tickFormatter={(str) => format(new Date(str), 'MMM d')}
                              fontSize={12}
                              tickLine={false}
                              axisLine={false}
                            />
                            <YAxis
                              fontSize={12}
                              tickLine={false}
                              axisLine={false}
                              tickFormatter={(value) => value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value}
                            />
                            <ChartTooltip
                              contentStyle={{
                                backgroundColor: 'hsl(var(--card))',
                                border: '1px solid hsl(var(--border))',
                                borderRadius: '8px'
                              }}
                              labelFormatter={(label) => format(new Date(label), 'MMMM d, yyyy')}
                            />
                            <Area
                              type="monotone"
                              dataKey="tokens"
                              stroke="hsl(var(--primary))"
                              fillOpacity={1}
                              fill="url(#colorTokens)"
                              strokeWidth={2}
                              name="Tokens"
                            />
                            <Area
                              type="monotone"
                              dataKey="queries"
                              stroke="hsl(var(--secondary))"
                              fillOpacity={0}
                              strokeWidth={2}
                              name="Queries"
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Model Distribution</h3>
                      <div className="h-[300px] w-full rounded-xl border bg-card p-4">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={tokenUsage.model_breakdown} layout="vertical">
                            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--muted-foreground))" opacity={0.1} />
                            <XAxis type="number" hide />
                            <YAxis
                              dataKey="model_name"
                              type="category"
                              fontSize={11}
                              width={100}
                              tickLine={false}
                              axisLine={false}
                            />
                            <ChartTooltip
                              cursor={{ fill: 'transparent' }}
                              contentStyle={{
                                backgroundColor: 'hsl(var(--card))',
                                border: '1px solid hsl(var(--border))',
                                borderRadius: '8px'
                              }}
                            />
                            <Bar dataKey="tokens" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} name="Tokens" />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </div>

                  {tokenUsage.per_website && tokenUsage.per_website.length > 0 && (
                    <div className="space-y-4">
                      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Detailed Website Usage</h3>
                      <div className="overflow-hidden rounded-xl border">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="bg-muted/50 text-left font-medium">
                              <th className="p-3">Website</th>
                              <th className="p-3 text-right">Total Queries</th>
                              <th className="p-3 text-right">Total Tokens</th>
                              <th className="p-3 text-right">Avg. Tokens/Query</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y">
                            {tokenUsage.per_website.map((site) => (
                              <tr key={site.website_id} className="hover:bg-muted/30 transition-colors">
                                <td className="p-3 font-medium">{site.website_name}</td>
                                <td className="p-3 text-right">{site.total_queries.toLocaleString()}</td>
                                <td className="p-3 text-right">{site.total_tokens_used.toLocaleString()}</td>
                                <td className="p-3 text-right">
                                  {site.total_queries > 0
                                    ? Math.round(site.total_tokens_used / site.total_queries).toLocaleString()
                                    : '0'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  <p className="text-xs text-muted-foreground">
                    Analytics are generated from chat interaction logs. Token counts represent approximate values as reported by the AI providers.
                  </p>
                </>
              ) : (
                <div className="py-12 text-center text-muted-foreground">
                  <Activity className="mx-auto h-12 w-12 opacity-20" />
                  <p className="mt-4">Loading token usage statistics...</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* System Health Overview */}
          <Card>
            <CardHeader className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-2">
                <Activity className="h-5 w-5" />
                <div>
                  <CardTitle>System Health Overview</CardTitle>

                </div>
              </div>
              <Button variant="outline" size="sm" onClick={fetchHealth} disabled={isHealthLoading}>
                {isHealthLoading ? 'Refreshing…' : 'Refresh Status'}
              </Button>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-sm text-muted-foreground">Overall status:</span>
                <span
                  className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold ${STATUS_COLORS[(health?.overall_status || '').toLowerCase()] || 'text-muted-foreground'
                    }`}
                >
                  <ShieldCheck className="h-4 w-4" />
                  {formatStatus(health?.overall_status)}
                </span>
                <span className="text-xs text-muted-foreground">
                  {isHealthLoading ? 'Refreshing…' : 'Auto-refreshed on load'}
                </span>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-xl border bg-muted/40 p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                      Database
                    </span>
                    <Server className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="mt-3 flex items-center gap-2 text-sm">
                    <span
                      className={`font-semibold ${STATUS_COLORS[(health?.database?.status || '').toLowerCase()] || 'text-muted-foreground'
                        }`}
                    >
                      {formatStatus(health?.database?.status)}
                    </span>
                    {health?.database?.details && (
                      <span className="text-muted-foreground">· {health.database.details}</span>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border bg-muted/40 p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                      Vector Store & AI
                    </span>
                    <Cpu className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="mt-3 space-y-2 text-sm">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-muted-foreground uppercase">Vector DB:</span>
                      <span
                        className={`font-semibold ${STATUS_COLORS[(health?.vector_store?.status || '').toLowerCase()] || 'text-muted-foreground'
                          }`}
                      >
                        {formatStatus(health?.vector_store?.status)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-muted-foreground uppercase">AI Model:</span>
                      <span
                        className={`font-semibold ${STATUS_COLORS[(health?.ai_model?.status || '').toLowerCase()] || 'text-muted-foreground'
                          }`}
                      >
                        {formatStatus(health?.ai_model?.status)}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border bg-muted/40 p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                      File Processing
                    </span>
                    <FileText className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="mt-3 flex items-center gap-2 text-sm">
                    <span
                      className={`font-semibold ${STATUS_COLORS[(health?.file_processing?.status || '').toLowerCase()] || 'text-muted-foreground'
                        }`}
                    >
                      {formatStatus(health?.file_processing?.status)}
                    </span>
                    {health?.file_processing?.details && (
                      <span className="text-muted-foreground">· {health.file_processing.details}</span>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border bg-muted/40 p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                      Authentication
                    </span>
                    <Shield className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="mt-3 flex items-center gap-2 text-sm">
                    <span
                      className={`font-semibold ${STATUS_COLORS[(health?.authentication?.status || '').toLowerCase()] || 'text-muted-foreground'
                        }`}
                    >
                      {formatStatus(health?.authentication?.status)}
                    </span>
                    {health?.authentication?.details && (
                      <span className="text-muted-foreground">· {health.authentication.details}</span>
                    )}
                  </div>
                </div>
              </div>

              {health?.storage && (
                <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">
                  <p className="font-medium text-foreground">Storage Snapshot</p>
                  <div className="mt-2 flex flex-wrap gap-4">
                    <span>
                      Total size:{' '}
                      <span className="font-semibold text-foreground">
                        {health.storage.total_size ?? '—'}
                      </span>
                    </span>
                    <span>
                      File count:{' '}
                      <span className="font-semibold text-foreground">
                        {health.storage.file_count ?? '—'}
                      </span>
                    </span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Account Information */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="h-5 w-5" />
                Account Information
              </CardTitle>

            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Username</Label>
                  <p className="text-lg font-semibold">{user?.username}</p>
                </div>
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Role</Label>
                  <p className="text-lg font-semibold capitalize">{user?.role}</p>
                </div>
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">User ID</Label>
                  <p className="text-sm font-mono text-muted-foreground">{user?.user_id}</p>
                </div>
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Website ID</Label>
                  <p className="text-sm font-mono text-muted-foreground">
                    {user?.website_id || 'Not assigned'}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Security Settings */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5" />
                Security Settings
              </CardTitle>

            </CardHeader>
            <CardContent>
              <form onSubmit={handlePasswordChange} className="space-y-4">

                <div className="space-y-2">
                  <Label htmlFor="newPassword">New Password</Label>
                  <Input
                    id="newPassword"
                    type="password"
                    value={passwordData.newPassword}
                    onChange={(e) => setPasswordData({ ...passwordData, newPassword: e.target.value })}
                    required
                    minLength={8}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="confirmPassword">Confirm New Password</Label>
                  <Input
                    id="confirmPassword"
                    type="password"
                    value={passwordData.confirmPassword}
                    onChange={(e) => setPasswordData({ ...passwordData, confirmPassword: e.target.value })}
                    required
                    minLength={8}
                  />
                </div>
                <Button type="submit" disabled={isChangingPassword}>
                  <Key className="mr-2 h-4 w-4" />
                  {isChangingPassword ? 'Changing Password...' : 'Change Password'}
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* System Information */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings className="h-5 w-5" />
                System Information
              </CardTitle>
              <CardDescription>
                System configuration and environment details
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">API Base URL</Label>
                  <p className="text-sm font-mono text-muted-foreground">
                    {import.meta.env.VITE_API_BASE_URL || 'Not configured'}
                  </p>
                </div>
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Environment</Label>
                  <p className="text-sm font-mono text-muted-foreground">
                    {import.meta.env.MODE || 'development'}
                  </p>
                </div>
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Version</Label>
                  <p className="text-sm font-mono text-muted-foreground">1.0.0</p>
                </div>
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Last Login</Label>
                  <p className="text-sm font-mono text-muted-foreground">
                    {new Date().toLocaleString()}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

        </div>
      </div>
    </DashboardLayout >
  );
}
