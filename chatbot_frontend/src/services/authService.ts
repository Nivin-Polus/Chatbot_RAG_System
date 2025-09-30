// AuthService.ts

// Base URL for backend
const CORRECT_SERVER = 'http://10.199.100.54:3000';
const AUTH_SERVER_URL = `${CORRECT_SERVER}/auth/token`;

export interface AuthResponse {
    access_token: string;
    token_type: string;
}

export interface LoginCredentials {
    username: string;
    password: string;
}

export class AuthError extends Error {
    constructor(
        message: string,
        public status?: number,
        public details?: any
    ) {
        super(message);
        this.name = 'AuthError';
    }
}

export class AuthService {
    private static readonly TOKEN_KEY = 'auth_token';
    private static readonly TEST_USERNAME = 'user';
    private static readonly TEST_PASSWORD = 'user123';

    /** Return test credentials for dev purposes */
    static getTestCredentials(): LoginCredentials {
        return {
            username: this.TEST_USERNAME,
            password: this.TEST_PASSWORD
        };
    }

    /** Login using JSON payload */
    static async login(credentials: LoginCredentials): Promise<AuthResponse> {
        try {
            const response = await fetch(AUTH_SERVER_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(credentials)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));

                if (response.status === 401) {
                    throw new AuthError('Invalid username or password', 401, errorData);
                }

                throw new AuthError(
                    errorData.detail || `Authentication failed: ${response.statusText}`,
                    response.status,
                    errorData
                );
            }

            const authResponse: AuthResponse = await response.json();
            localStorage.setItem(this.TOKEN_KEY, authResponse.access_token);
            return authResponse;
        } catch (error) {
            console.error('Login error:', error);
            if (error instanceof AuthError) throw error;
            throw new AuthError('Authentication failed', undefined, error);
        }
    }

    /** Retrieve stored token from localStorage */
    static getStoredToken(): string | null {
        return localStorage.getItem(this.TOKEN_KEY);
    }

    /** Clear stored token */
    static clearStoredToken(): void {
        localStorage.removeItem(this.TOKEN_KEY);
    }

    /** Verify if token is still valid */
    static async verifyToken(token: string): Promise<boolean> {
        try {
            const response = await fetch(`${CORRECT_SERVER}/auth/token/verify`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
            });

            if (!response.ok && response.status === 401) {
                this.clearStoredToken();
                return false;
            }
            return response.ok;
        } catch (error) {
            console.error('Token verification error:', error);
            return false;
        }
    }

    /** Check if user is authenticated */
    static isAuthenticated(): boolean {
        return !!this.getStoredToken();
    }
}
