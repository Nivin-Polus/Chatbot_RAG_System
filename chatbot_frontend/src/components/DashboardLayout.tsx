import { ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from './AppSidebar';
import { ThemeToggle } from './ThemeToggle';

interface DashboardLayoutProps {
  children: ReactNode;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const showBackButton = location.pathname !== '/superadmin';

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full overflow-hidden">
        <AppSidebar />
        <main className="flex-1 flex flex-col min-w-0">
          <header className="h-14 border-b border-border bg-card flex items-center justify-between px-4 flex-none gap-2">
            <div className="flex items-center gap-2">
              <SidebarTrigger />
              {showBackButton && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => navigate('/superadmin')}
                  title="Back to Knowledge Base"
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
          <div className="flex-1 p-6 animate-fade-in overflow-hidden">
            {children}
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
}
