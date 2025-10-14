import { toast } from 'sonner';

// Global logout function - will be set by AuthContext
let globalLogout: (() => void) | null = null;

export const setGlobalLogout = (logoutFn: () => void) => {
  globalLogout = logoutFn;
};

const formatErrorMessage = (payload: unknown, response: Response): string => {
  if (!payload) {
    return `Error ${response.status}: ${response.statusText}`;
  }

  if (typeof payload === 'string') {
    return payload;
  }

  if (Array.isArray(payload)) {
    const messages = payload
      .map((item) =>
        typeof item === 'object' && item && 'msg' in item ? String(item.msg) : JSON.stringify(item)
      )
      .filter(Boolean);
    if (messages.length) {
      return messages.join(', ');
    }
  }

  if (typeof payload === 'object' && payload) {
    if ('detail' in payload && typeof (payload as { detail?: unknown }).detail === 'string') {
      return String((payload as { detail: string }).detail);
    }
    if ('message' in payload && typeof (payload as { message?: unknown }).message === 'string') {
      return String((payload as { message: string }).message);
    }
  }

  return `Error ${response.status}: ${response.statusText}`;
};

// API utility function that automatically handles 401 responses
export const apiRequest = async (
  url: string,
  options: RequestInit = {},
  showErrorToast: boolean = true,
  logoutOn401: boolean = true
): Promise<Response> => {
  try {
    const response = await fetch(url, options);

    // Handle 401 Unauthorized
    if (response.status === 401) {
      if (logoutOn401) {
        if (globalLogout) {
          toast.error('Session expired. Please login again.');
          globalLogout();
        } else {
          console.error('401 Unauthorized - logout function not available');
          // Fallback: redirect to login manually
          window.location.href = '/login';
        }
        throw new Error('Unauthorized - session expired');
      }

      // When logout is suppressed, let the caller handle the 401 response
      return response;
    }

    if (!response.ok) {
      let errorPayload: unknown = null;
      try {
        errorPayload = await response.clone().json();
      } catch {
        // Ignore JSON parse errors
      }

      if (showErrorToast) {
        toast.error(formatErrorMessage(errorPayload, response));
      }
    }

    return response;
  } catch (error) {
    if (error instanceof Error && error.message === 'Unauthorized - session expired') {
      // Re-throw 401 errors without additional handling
      throw error;
    }

    // Handle network errors
    if (showErrorToast) {
      toast.error('Network error. Please check your connection.');
    }
    throw error;
  }
};

// Convenience function for GET requests
export const apiGet = async (
  url: string,
  token?: string,
  showErrorToast: boolean = true,
  logoutOn401: boolean = true
): Promise<Response> => {
  const options: RequestInit = {
    method: 'GET',
  };

  if (token) {
    options.headers = {
      Authorization: `Bearer ${token}`,
    };
  }

  return apiRequest(url, options, showErrorToast, logoutOn401);
};

// Convenience function for POST requests
export const apiPost = async (
  url: string,
  data: any,
  token?: string,
  showErrorToast: boolean = true,
  logoutOn401: boolean = true
): Promise<Response> => {
  const options: RequestInit = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  };

  if (token) {
    options.headers = {
      ...options.headers,
      Authorization: `Bearer ${token}`,
    };
  }

  return apiRequest(url, options, showErrorToast, logoutOn401);
};

// Convenience function for PUT requests
export const apiPut = async (
  url: string,
  data: any,
  token?: string,
  showErrorToast: boolean = true,
  logoutOn401: boolean = true
): Promise<Response> => {
  const options: RequestInit = {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  };

  if (token) {
    options.headers = {
      ...options.headers,
      Authorization: `Bearer ${token}`,
    };
  }

  return apiRequest(url, options, showErrorToast, logoutOn401);
};

// Convenience function for DELETE requests
export const apiDelete = async (
  url: string,
  token?: string,
  showErrorToast: boolean = true,
  logoutOn401: boolean = true
): Promise<Response> => {
  const options: RequestInit = {
    method: 'DELETE',
  };

  if (token) {
    options.headers = {
      Authorization: `Bearer ${token}`,
    };
  }

  return apiRequest(url, options, showErrorToast, logoutOn401);
};

// Convenience function for file uploads
export const apiUpload = async (
  url: string,
  formData: FormData,
  token?: string,
  showErrorToast: boolean = true,
  logoutOn401: boolean = true
): Promise<Response> => {
  const options: RequestInit = {
    method: 'POST',
    body: formData, // ✅ important
  };

  if (token) {
    options.headers = {
      Authorization: `Bearer ${token}`, // only auth, no Content-Type
    };
  }

  // Call fetch directly, bypassing anything that might set Content-Type
  const response = await fetch(url, options);

  // Optional: handle status codes
  if (!response.ok && showErrorToast) {
    const errorText = await response.text();
    toast.error(`Upload failed: ${errorText}`);
    if (response.status === 401 && logoutOn401) {
      // handle logout
    }
  }

  return response;
};

