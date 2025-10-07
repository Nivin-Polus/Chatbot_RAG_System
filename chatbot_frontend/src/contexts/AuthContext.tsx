import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthUser, LoginCredentials } from '@/types/auth';
import { toast } from 'sonner';
import { setGlobalLogout, apiRequest } from '@/utils/api';

interface AuthContextType {
  user: AuthUser | null;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

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

  const logout = useCallback(() => {
    setUser(null);
    sessionStorage.removeItem('auth_user');
    navigate('/login');
    toast.success('Logged out successfully');
  }, [navigate]);

  // Register the logout function with the API utility
  useEffect(() => {
    setGlobalLogout(logout);
  }, [logout]);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
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
