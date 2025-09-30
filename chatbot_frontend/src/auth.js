// auth.js
import { CONFIG } from "./config.js";

export class AuthService {
  static TOKEN_KEY = 'chatbot_auth_token';

  /** Get stored token from localStorage */
  static getStoredToken() {
    return localStorage.getItem(this.TOKEN_KEY);
  }

  /** Store token in localStorage */
  static storeToken(token) {
    localStorage.setItem(this.TOKEN_KEY, token);
  }

  /** Remove token from localStorage */
  static clearToken() {
    localStorage.removeItem(this.TOKEN_KEY);
  }

  /** Verify if token is still valid */
  static async verifyToken(token) {
    if (!token) return false;
    
    try {
      const response = await fetch(`${CONFIG.apiBase}/auth/verify`, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });
      return response.ok;
    } catch (err) {
      console.error("Token verification failed:", err);
      return false;
    }
  }

  /** Login with credentials */
  static async login(credentials) {
    try {
      // Create form data for OAuth2 token endpoint
      const formData = new URLSearchParams();
      formData.append('username', credentials.username);
      formData.append('password', credentials.password);
      formData.append('grant_type', 'password');
      
      const response = await fetch(`${CONFIG.apiBase}/auth/token`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/x-www-form-urlencoded"
        },
        body: formData
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`Authentication failed: ${response.status} ${response.statusText}`);
        throw new Error(`Authentication failed: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      
      // Store the token for future use
      this.storeToken(data.access_token);
      
      return data;
    } catch (err) {
      console.error("Login error:", err.message);
      throw err;
    }
  }

  /** Get test credentials from config */
  static getTestCredentials() {
    return {
      username: CONFIG.auth.username,
      password: CONFIG.auth.password
    };
  }

  /** Legacy function for backward compatibility */
  static async getToken() {
    const credentials = this.getTestCredentials();
    const auth = await this.login(credentials);
    return auth.access_token;
  }
}
