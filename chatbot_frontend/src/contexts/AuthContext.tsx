import { createContext, useContext, useState, useEffect, useCallback, ReactNode, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthUser, LoginCredentials } from '@/types/auth';
import { toast } from 'sonner';
import { setGlobalLogout, apiRequest } from '@/utils/api';

interface AuthContextType {
  user: AuthUser | null;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<boolean>;
}

// Helper function to decode JWT and get expiration time
const getTokenExpiration = (token: string): number | null => {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp ? payload.exp * 1000 : null; // Convert to milliseconds
  } catch {
    return null;
  }
};

// Helper function to check if token is about to expire (within 5 minutes)
const isTokenExpiringSoon = (token: string): boolean => {
  const expiration = getTokenExpiration(token);
  if (!expiration) return true;
  const now = Date.now();
  const fiveMinutes = 5 * 60 * 1000; // 5 minutes in milliseconds
  return expiration - now < fiveMinutes;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const storedUser = sessionStorage.getItem('auth_user');
    if (storedUser) {
      try {
        setUser(JSON.parse(storedUser));
      } catch (e) {
        console.error('Failed to parse stored user', e);
        sessionStorage.removeItem('auth_user');
      }
    }
    setIsLoading(false);
  }, []);

  const login = async (credentials: LoginCredentials) => {
    const endpoint = `${import.meta.env.VITE_API_BASE_URL}/auth/token`;

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          username: credentials.username,
          password: credentials.password,
        }),
      });

      let payload: any = null;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }

      if (!response.ok) {
        const errorMessage =
          (typeof payload === 'object' && payload !== null && (payload.detail || payload.message || payload.error)) ||
          (typeof payload === 'string' ? payload : null) ||
          (response.status === 401 ? 'Invalid username or password' : 'Login failed');

        toast.error(errorMessage);
        throw new Error(errorMessage);
      }

      const data = payload ?? {};

      // Use the response data directly since it includes all user information
      const authUser: AuthUser = {
        access_token: data.access_token,
        role: data.role || 'user',
        username: data.username,
        user_id: data.user_id,
        website_id: data.website_id,
        collection_id: data.collection_id,
      };

      setUser(authUser);
      sessionStorage.setItem('auth_user', JSON.stringify(authUser));
      
      // Navigate based on role
      switch (authUser.role) {
        case 'super_admin':
        case 'superadmin':
          navigate('/superadmin');
          break;
        case 'admin':
          navigate(`/admin/${authUser.collection_id}`);
          break;
        case 'useradmin':
        case 'user_admin':
          navigate('/useradmin');
          break;
        default:
          navigate('/app/chat');
      }
      
      toast.success('Login successful');
    } catch (error) {
      if (error instanceof Error) {
        toast.error(error.message || 'Login failed');
        throw error;
      }

      toast.error('Login failed');
      throw error;
    }
  };

  const refreshToken = useCallback(async (): Promise<boolean> => {
    if (!user?.access_token) return false;

    try {
      const endpoint = `${import.meta.env.VITE_API_BASE_URL}/auth/refresh`;
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_token: user.access_token }),
      });

      if (!response.ok) {
        return false;
      }

      const data = await response.json();
      const updatedUser: AuthUser = {
        ...user,
        access_token: data.access_token,
        role: data.role || user.role,
        username: data.username || user.username,
        user_id: data.user_id || user.user_id,
        website_id: data.website_id || user.website_id,
        collection_id: data.collection_id || user.collection_id,
      };

      setUser(updatedUser);
      sessionStorage.setItem('auth_user', JSON.stringify(updatedUser));
      return true;
    } catch (error) {
      console.error('Token refresh failed:', error);
      return false;
    }
  }, [user]);

  const logout = useCallback(() => {
    if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
      refreshIntervalRef.current = null;
    }
    setUser(null);
    sessionStorage.removeItem('auth_user');
    navigate('/login');
    toast.success('Logged out successfully');
  }, [navigate]);

  // Register the logout function with the API utility
  useEffect(() => {
    setGlobalLogout(logout);
  }, [logout]);

  // Auto-refresh token before expiration
  useEffect(() => {
    if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
    }

    if (!user?.access_token) {
      return;
    }

    // Check token expiration every minute
    refreshIntervalRef.current = setInterval(async () => {
      if (user?.access_token && isTokenExpiringSoon(user.access_token)) {
        const success = await refreshToken();
        if (!success) {
          console.warn('Token refresh failed, user may need to re-login');
        }
      }
    }, 60 * 1000); // Check every minute

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
        refreshIntervalRef.current = null;
      }
    };
  }, [user, refreshToken]);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, refreshToken }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
