import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarFooter,
  useSidebar,
} from '@/components/ui/sidebar';
import {
  Database,
  FileText,
  Users,
  Settings,
  MessageSquare,
  Layers,
  LogOut,
  Activity,
  Link2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getAssetUrl } from '@/utils/assets';

// Navigation definitions
const superadminNav = [
  { title: 'Knowledge Base', url: '/superadmin', icon: Layers },
  { title: 'Users', url: '/superadmin/users', icon: Users },
  { title: 'Plugins', url: '/superadmin/plugins', icon: Link2 },
  { title: 'Chat', url: '/superadmin/chat', icon: MessageSquare },
  { title: 'Activity', url: '/superadmin/activity', icon: Activity },
  { title: 'Settings', url: '/superadmin/settings', icon: Settings },
];

const adminNav = (collectionId?: string) => [
  { title: 'Files', url: `/admin/${collectionId}`, icon: Database },
  { title: 'Prompts', url: `/admin/${collectionId}/prompts`, icon: FileText },
  { title: 'Users', url: `/admin/${collectionId}/users`, icon: Users },
  { title: 'Chat', url: `/admin/${collectionId}/chat`, icon: MessageSquare },
  { title: 'Settings', url: `/admin/${collectionId}/settings`, icon: Settings },
];

const userAdminNav = () => [
  { title: 'Knowledge Base', url: `/useradmin/knowledge-base`, icon: Layers },
  { title: 'Users', url: `/useradmin/users`, icon: Users },
  { title: 'Plugins', url: `/useradmin/plugins`, icon: Link2 },
  { title: 'Chat', url: `/useradmin/chat`, icon: MessageSquare },
  { title: 'Settings', url: `/useradmin/settings`, icon: Settings },
];

const userNav = [
  { title: 'Chat', url: '/app/chat', icon: MessageSquare },
];

const sidebarHeading = (role?: string) => {
  switch (role) {
    case 'super_admin':
    case 'superadmin':
      return 'Leto Super Admin';
    case 'admin':
    case 'useradmin':
    case 'user_admin':
      return 'Leto Admin';
    default:
      return 'Leto User';
  }
};

export function AppSidebar() {
  const { user, logout } = useAuth();
  const { open } = useSidebar();
  const location = useLocation();

  // Get navigation items based on user role
  const getNavItems = () => {
    switch (user?.role) {
      case 'super_admin':
      case 'superadmin':
        return superadminNav;
      case 'admin':
        return adminNav(user?.collection_id);
      case 'useradmin':
      case 'user_admin':
        return userAdminNav();
      default:
        return userNav;
    }
  };

  const navItems = getNavItems();

  // Active tab check
  const isActive = (itemUrl: string) => {
    const current = location.pathname;

    // Root tabs should match exactly
    if (
      itemUrl === '/superadmin' ||
      itemUrl === '/admin' ||
      itemUrl === '/useradmin'
    ) {
      return current === itemUrl;
    }

    // Other tabs match if current path starts with tab URL
    return current.startsWith(itemUrl);
  };

  return (
    <Sidebar className="border-r border-sidebar-border">
      <SidebarContent>
        <div className="p-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-lg border border-logo flex items-center justify-center p-1">
              <img
                src={getAssetUrl('leto.svg')}
                alt="Leto Logo"
                className="h-8 w-8 object-contain"
              />
            </div>
            {open && (
              <div>
                <h2 className="text-lg font-semibold">{sidebarHeading(user?.role)}</h2>
                <p className="text-xs text-muted-foreground capitalize">{user?.role}</p>
              </div>
            )}
          </div>
        </div>

        <SidebarGroup>
          {open && <SidebarGroupLabel>Navigation</SidebarGroupLabel>}
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => {
                const active = isActive(item.url);
                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton asChild>
                      <NavLink
                        to={item.url}
                        className={`flex items-center gap-2 rounded-md px-2 py-2 transition-colors 
                          ${active
                            ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium'
                            : 'hover:bg-sidebar-accent/50 text-muted-foreground'
                          }`}
                      >
                        <item.icon className="h-4 w-4" />
                        {open && <span>{item.title}</span>}
                      </NavLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border p-4">
        <Button
          variant="ghost"
          className="w-full justify-start"
          onClick={logout}
        >
          <LogOut className="h-4 w-4" />
          {open && <span>Logout</span>}
        </Button>
      </SidebarFooter>
    </Sidebar>
  );
}
