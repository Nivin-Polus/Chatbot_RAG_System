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
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [health, setHealth] = useState<HealthOverview | null>(null);
  const [isHealthLoading, setIsHealthLoading] = useState(false);

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

  useEffect(() => {
    fetchHealth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.access_token]);

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();

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
          current_password: passwordData.currentPassword,
          new_password: passwordData.newPassword,
        },
        user?.access_token
      );

      if (response.ok) {
        toast.success('Password changed successfully');
        setPasswordData({
          currentPassword: '',
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
                  className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold ${
                    STATUS_COLORS[(health?.overall_status || '').toLowerCase()] || 'text-muted-foreground'
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
                      className={`font-semibold ${
                        STATUS_COLORS[(health?.database?.status || '').toLowerCase()] || 'text-muted-foreground'
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
                        className={`font-semibold ${
                          STATUS_COLORS[(health?.vector_store?.status || '').toLowerCase()] || 'text-muted-foreground'
                        }`}
                      >
                        {formatStatus(health?.vector_store?.status)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-muted-foreground uppercase">AI Model:</span>
                      <span
                        className={`font-semibold ${
                          STATUS_COLORS[(health?.ai_model?.status || '').toLowerCase()] || 'text-muted-foreground'
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
                      className={`font-semibold ${
                        STATUS_COLORS[(health?.file_processing?.status || '').toLowerCase()] || 'text-muted-foreground'
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
                      className={`font-semibold ${
                        STATUS_COLORS[(health?.authentication?.status || '').toLowerCase()] || 'text-muted-foreground'
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
                  <Label htmlFor="currentPassword">Current Password</Label>
                  <Input
                    id="currentPassword"
                    type="password"
                    value={passwordData.currentPassword}
                    onChange={(e) => setPasswordData({ ...passwordData, currentPassword: e.target.value })}
                    required
                  />
                </div>
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
    </DashboardLayout>
  );
}
