import { ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from './AppSidebar';
import { ThemeToggle } from './ThemeToggle';
import { useAuth } from '@/contexts/AuthContext';

interface DashboardLayoutProps {
  children: ReactNode;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const getHomePath = () => {
    if (!user) return '/login';
    switch (user.role) {
      case 'super_admin':
      case 'superadmin':
        return '/superadmin';
      case 'useradmin':
      case 'user_admin':
        return '/useradmin/knowledge-base';
      case 'user':
        return '/app/chat';
      default:
        return '/login';
    }
  };

  const homePath = getHomePath();
  const showBackButton = location.pathname !== homePath &&
    location.pathname !== '/superadmin' &&
    location.pathname !== '/useradmin/knowledge-base' &&
    !location.pathname.includes('/pluginuser/chat');

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full overflow-hidden">
        <AppSidebar />
        <main className="flex-1 flex flex-col min-w-0">
          {!location.pathname.includes('/pluginuser/') && (
            <header className="h-14 border-b border-border bg-card flex items-center justify-between px-4 flex-none gap-2">
              <div className="flex items-center gap-2">
                <SidebarTrigger />
                {showBackButton && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => navigate(homePath)}
                    title="Back"
                    className="h-7 w-7"
                  >
                    <ArrowLeft className="h-4 w-4" />
                  </Button>
                )}
              </div>
              <div className="flex items-center space-x-4">
                <ThemeToggle />
              </div>
            </header>
          )}
          <div className={`flex-1 animate-fade-in overflow-hidden ${location.pathname.includes('/pluginuser/') ? 'p-0' : 'p-6'}`}>
            {children}
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
}
