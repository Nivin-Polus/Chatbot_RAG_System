// AuthService.js

// Base URL for backend
const CORRECT_SERVER = 'http://10.199.100.54:8000';
const AUTH_SERVER_URL = `${CORRECT_SERVER}/auth/token`;

class AuthError extends Error {
    constructor(message, status, details) {
        super(message);
        this.name = 'AuthError';
        this.status = status;
        this.details = details;
    }
}

class AuthService {
    static TOKEN_KEY = 'auth_token';
    static TEST_USERNAME = 'user';
    static TEST_PASSWORD = 'user123';

    /** Return test credentials for dev purposes */
    static getTestCredentials() {
        return {
            username: this.TEST_USERNAME,
            password: this.TEST_PASSWORD
        };
    }

    /** Login using OAuth2 password grant (form-urlencoded) */
    static async login(credentials) {
        try {
            const formData = new URLSearchParams();
            formData.append('username', credentials.username);
            formData.append('password', credentials.password);
            formData.append('grant_type', 'password');

            const response = await fetch(AUTH_SERVER_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'application/json'
                },
                body: formData.toString()
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

            const authResponse = await response.json();
            localStorage.setItem(this.TOKEN_KEY, authResponse.access_token);
            return authResponse;
        } catch (error) {
            console.error('Login error:', error);
            if (error instanceof AuthError) throw error;
            throw new AuthError('Authentication failed', undefined, error);
        }
    }

    static getStoredToken() {
        return localStorage.getItem(this.TOKEN_KEY);
    }

    static clearStoredToken() {
        localStorage.removeItem(this.TOKEN_KEY);
    }

    static async verifyToken(token) {
        try {
            const response = await fetch(`${CORRECT_SERVER}/auth/verify`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            return response.ok;
        } catch (error) {
            console.error('Token verification error:', error);
            return false;
        }
    }

    static isAuthenticated() {
        const token = this.getStoredToken();
        return token && this.verifyToken(token);
    }
}

export { AuthError, AuthService };
