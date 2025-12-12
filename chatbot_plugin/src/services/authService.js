// AuthService.js

// Base URL for backend
const CORRECT_SERVER = 'https://chatbot.polussolutions.com/';
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

    /** Login using JSON payload */
    static async login(credentials) {
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

            const authResponse = await response.json();
            localStorage.setItem(this.TOKEN_KEY, authResponse.access_token);
            return authResponse;
        } catch (error) {
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
            const response = await fetch(`${AUTH_SERVER_URL}/verify`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            return response.ok;
        } catch (error) {
            return false;
        }
    }

    static isAuthenticated() {
        const token = this.getStoredToken();
        return token && this.verifyToken(token);
    }
}

export { AuthError, AuthService };
