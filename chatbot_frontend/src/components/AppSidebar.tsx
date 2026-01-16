import { useState, useEffect, useCallback, useRef } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
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
  SidebarMenuAction,
  SidebarTrigger,
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
  Link2,
  Globe,
  Trash2,
  Plus,
  Pencil,
  Check,
  X
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { getAssetUrl } from '@/utils/assets';
import { getSessions, deleteSession, renameSession, ChatSession } from '@/utils/chatStorage';
import { ThemeToggle } from './ThemeToggle';

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

const pluginUserNav: { title: string; url: string; icon: any }[] = [];

const sidebarHeading = (role?: string) => {
  switch (role) {
    case 'super_admin':
    case 'superadmin':
      return 'Leto Super Admin';
    case 'admin':
    case 'useradmin':
    case 'user_admin':
      return 'Leto Admin';
    case 'plugin_user':
      return 'Leto User';
    default:
      return 'Leto User';
  }
};

export function AppSidebar() {
  const { user, logout } = useAuth();
  const { open } = useSidebar();
  const location = useLocation();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<ChatSession[]>([]);

  // Renaming state
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const editInputRef = useRef<HTMLInputElement>(null);

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
      case 'plugin_user':
        return pluginUserNav;
      default:
        return userNav;
    }
  };

  const loadHistory = useCallback(() => {
    if (user) {
      const list = getSessions(user.user_id, user.role || 'user');
      setSessions(list);
    }
  }, [user]);

  useEffect(() => {
    loadHistory();
    window.addEventListener('chat-history-updated', loadHistory);
    return () => window.removeEventListener('chat-history-updated', loadHistory);
  }, [loadHistory]);

  // Focus input when editing starts
  useEffect(() => {
    if (editingSessionId && editInputRef.current) {
      editInputRef.current.focus();
    }
  }, [editingSessionId]);

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (user) {
      deleteSession(sessionId, user.user_id, user.role || 'user');
      if (location.search.includes(sessionId)) {
        const baseUrl = getChatBaseUrl();
        navigate(baseUrl);
      }
    }
  };

  const handleStartEdit = (e: React.MouseEvent, session: ChatSession) => {
    e.preventDefault();
    e.stopPropagation();
    setEditingSessionId(session.id);
    setEditTitle(session.title);
  };

  const handleSaveEdit = (e: React.MouseEvent | React.KeyboardEvent, sessionId: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (user && editTitle.trim()) {
      renameSession(sessionId, editTitle.trim(), user.user_id, user.role || 'user');
      setEditingSessionId(null);
      setEditTitle('');
    }
  };

  const handleCancelEdit = (e: React.MouseEvent | React.KeyboardEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setEditingSessionId(null);
    setEditTitle('');
  };

  const handleKeyDown = (e: React.KeyboardEvent, sessionId: string) => {
    if (e.key === 'Enter') {
      handleSaveEdit(e, sessionId);
    } else if (e.key === 'Escape') {
      handleCancelEdit(e);
    }
  };

  const getChatBaseUrl = () => {
    switch (user?.role) {
      case 'super_admin':
      case 'superadmin':
        return '/superadmin/chat';
      case 'useradmin':
      case 'user_admin':
        return '/useradmin/chat';
      case 'admin':
        return `/admin/${user?.collection_id}/chat`;
      case 'plugin_user':
        return '/pluginuser/chat';
      default:
        return '/app/chat';
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
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3">
              <div className={`rounded-lg border border-logo flex items-center justify-center p-1 ${user?.role === 'plugin_user' ? 'h-14 w-14' : 'h-10 w-10'}`}>
                <img
                  src={getAssetUrl('leto.svg')}
                  alt="Leto Logo"
                  className={`${user?.role === 'plugin_user' ? 'h-12 w-12' : 'h-8 w-8'} object-contain`}
                />
              </div>
              {open && user?.role !== 'plugin_user' && (
                <div>
                  <h2 className="text-lg font-semibold">{sidebarHeading(user?.role)}</h2>
                  <p className="text-xs text-muted-foreground capitalize">{user?.role}</p>
                </div>
              )}
            </div>
            {open && (
              <div className="flex items-center gap-1">
                <SidebarTrigger />
              </div>
            )}
          </div>
          {open && (
            <Button
              variant="outline"
              className="w-full justify-start gap-2 mt-2"
              onClick={() => navigate(getChatBaseUrl())}
            >
              <Plus className="h-4 w-4" />
              New Chat
            </Button>
          )}
        </div>

        <SidebarGroup>
          {open && navItems.length > 0 && <SidebarGroupLabel>Navigation</SidebarGroupLabel>}
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

        {/* History Section */}
        {sessions.length > 0 && (
          <SidebarGroup>
            {open && <SidebarGroupLabel>History</SidebarGroupLabel>}
            <SidebarGroupContent>
              <SidebarMenu>
                {sessions.map((session) => {
                  const chatBase = getChatBaseUrl();
                  const sessionUrl = `${chatBase}?session=${session.id}`;
                  const isActiveSession = location.pathname === chatBase && location.search === `?session=${session.id}`;
                  const isEditing = editingSessionId === session.id;

                  return (
                    <SidebarMenuItem key={session.id} className="group relative">
                      {isEditing ? (
                        <div className="flex items-center px-2 py-1 gap-2 w-full">
                          <Input
                            ref={editInputRef}
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            onKeyDown={(e) => handleKeyDown(e, session.id)}
                            className="h-8 text-sm"
                            onClick={(e) => e.stopPropagation()}
                          />
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-green-500 hover:text-green-600 hover:bg-transparent" onClick={(e) => handleSaveEdit(e, session.id)}>
                            <Check className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-red-500 hover:text-red-600 hover:bg-transparent" onClick={handleCancelEdit}>
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      ) : (
                        <>
                          <SidebarMenuButton asChild isActive={isActiveSession} title={session.title}>
                            <NavLink to={sessionUrl} className="flex items-center justify-between">
                              <span className="truncate pr-16 block w-full">{session.title}</span>
                            </NavLink>
                          </SidebarMenuButton>
                          <div className="flex items-center absolute right-1 top-1/2 -translate-y-1/2 gap-1 px-1">
                            <SidebarMenuAction
                              className="static h-6 w-6 text-muted-foreground hover:text-foreground hover:bg-sidebar-accent"
                              onClick={(e) => handleStartEdit(e, session)}
                              title="Rename"
                            >
                              <Pencil className="h-3 w-3" />
                              <span className="sr-only">Rename</span>
                            </SidebarMenuAction>
                            <SidebarMenuAction
                              className="static h-6 w-6 text-muted-foreground hover:text-destructive hover:bg-sidebar-accent"
                              onClick={(e) => handleDeleteSession(e, session.id)}
                              title="Delete"
                            >
                              <Trash2 className="h-3 w-3" />
                              <span className="sr-only">Delete</span>
                            </SidebarMenuAction>
                          </div>
                        </>
                      )}
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border p-4">
        {user?.role !== 'plugin_user' && (
          <Button
            variant="ghost"
            className="w-full justify-start"
            onClick={logout}
          >
            <LogOut className="h-4 w-4" />
            {open && <span>Logout</span>}
          </Button>
        )}
      </SidebarFooter>
    </Sidebar>
  );
}
