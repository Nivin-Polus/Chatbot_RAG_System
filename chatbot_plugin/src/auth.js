// auth.js
import { CONFIG, applyRuntimeConfig } from "./config.js";

export class AuthService {
  static TOKEN_KEY = 'chatbot_auth_token';
  static TOKEN_CONTEXT_KEY = 'chatbot_auth_token_context';
  static get VERIFY_ENDPOINT() {
    return this.buildApiUrl("/auth/plugin-token/verify");
  }

  static getSanitizedApiBase() {
    const base = CONFIG?.apiBase || "";
    return base ? base.replace(/\/+$/, "") : "";
  }

  static buildApiUrl(path = "") {
    const base = this.getSanitizedApiBase();
    if (!path) {
      return base;
    }
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    return base ? `${base}${normalizedPath}` : normalizedPath;
  }

  static getConfiguredPluginToken() {
    const token = CONFIG?.pluginToken;
    if (typeof token !== "string") return null;
    const trimmed = token.trim();
    return trimmed ? trimmed : null;
  }

  /** Get stored token from localStorage */
  static getStoredToken() {
    if (typeof localStorage === "undefined") {
      return this.getConfiguredPluginToken();
    }

    try {
      const stored = localStorage.getItem(this.TOKEN_KEY);
      if (stored) {
        return stored;
      }
    } catch (err) {
      /* ignore storage read failure */
    }

    return this.getConfiguredPluginToken();
  }

  /** Store token in localStorage */
  static storeToken(token) {
    if (typeof localStorage === "undefined") {
      return;
    }

    try {
      localStorage.setItem(this.TOKEN_KEY, token);
    } catch (err) {
      /* ignore storage write failure */
    }
  }

  /** Store verification context */
  static storeTokenContext(context) {
    if (!context) {
      this.clearTokenContext();
      return;
    }

    if (typeof localStorage === "undefined") {
      return;
    }

    try {
      localStorage.setItem(this.TOKEN_CONTEXT_KEY, JSON.stringify(context));
    } catch (err) {
      /* ignore context persistence failure */
    }
  }

  /** Retrieve cached verification context */
  static getTokenContext() {
    if (typeof localStorage === "undefined") {
      return null;
    }

    let raw;
    try {
      raw = localStorage.getItem(this.TOKEN_CONTEXT_KEY);
    } catch (err) {
      return null;
    }

    if (!raw) return null;

    try {
      return JSON.parse(raw);
    } catch (err) {
      this.clearTokenContext();
      return null;
    }
  }

  /** Remove token from localStorage */
  static clearToken() {
    try {
      localStorage.removeItem(this.TOKEN_KEY);
    } catch (err) {
      /* ignore storage removal failure */
    }
    this.clearTokenContext();
  }

  /** Remove cached verification context */
  static clearTokenContext() {
    if (typeof localStorage === "undefined") {
      return;
    }

    try {
      localStorage.removeItem(this.TOKEN_CONTEXT_KEY);
    } catch (err) {
      /* ignore context removal failure */
    }
  }

  /** Fetch plugin credentials from backend */
  static async lookupPluginCredentials(options = {}) {
    const { force = false } = options;

    const websiteUrl = CONFIG?.websiteUrl;
    if (!websiteUrl) {
      return null;
    }

    if (!force && this._pluginLookupCache) {
      return this._pluginLookupCache;
    }

    try {
      const response = await fetch(this.buildApiUrl("/plugins/lookup"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ website_url: websiteUrl })
      });

      if (!response.ok) {
        await response.text().catch(() => "");

        if (response.status === 404 || response.status === 403) {
          applyRuntimeConfig({ pluginActive: false, pluginToken: null });
          this.clearToken();
        }

        this._pluginLookupCache = null;
        return null;
      }

      const data = await response.json().catch(() => null);
      if (!data) {
        this._pluginLookupCache = null;
        return null;
      }

      const normalized = {
        is_active: data.is_active !== undefined ? Boolean(data.is_active) : true,
        collection_id: data.collection_id || null,
        collection_name: data.collection_name ?? null,
        plugin_username: data.plugin_username || null,
        plugin_token: data.plugin_token || null,
        user_id: data.user_id || null,
        username: data.username || null,
        website_id: data.website_id || null
      };

      const runtimeUpdates = {
        pluginActive: normalized.is_active,
        pluginUsername: normalized.plugin_username,
        pluginToken: normalized.plugin_token
      };

      if (normalized.collection_id) {
        runtimeUpdates.collectionId = normalized.collection_id;
      }
      if (normalized.collection_name !== undefined) {
        runtimeUpdates.collectionName = normalized.collection_name;
      }
      if (normalized.user_id) {
        runtimeUpdates.userId = normalized.user_id;
      }
      if (normalized.username) {
        runtimeUpdates.username = normalized.username;
      }
      if (normalized.website_id) {
        runtimeUpdates.websiteId = normalized.website_id;
      }

      applyRuntimeConfig(runtimeUpdates);

      if (normalized.plugin_token && normalized.is_active) {
        this.storeToken(normalized.plugin_token);
      } else if (normalized.is_active === false) {
        this.clearToken();
      }

      this._pluginLookupCache = normalized;
      return normalized;
    } catch (err) {
      if (force) {
        this._pluginLookupCache = null;
      }
      return null;
    }
  }

  /** Verify if token is still valid */
  static async verifyToken(token) {
    try {
      if (!token) return null;

      const response = await fetch(this.VERIFY_ENDPOINT, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          token,
          website_url: CONFIG?.websiteUrl
        })
      }).catch(() => null);

      // If request itself failed
      if (!response || !response.ok) {
        if (response?.status === 401) {
          this.clearToken();
        } else {
          this.clearTokenContext();
        }
        return null;
      }

      const data = await response.json().catch(() => null);

      if (!data || data.valid !== true) {
        this.clearTokenContext();
        return null;
      }

      const normalized = {
        valid: true,
        user_id: data.user_id,
        username: data.username,
        collection_id: data.collection_id,
        website_id: data.website_id
      };

      this.storeTokenContext(normalized);
      return normalized;

    } catch {
      // Fail silently on ANY error
      this.clearTokenContext();
      return null;
    }
  }


  /** Login with credentials */
  static async login(credentials) {
    if (!credentials || !credentials.username || !credentials.password) {
      throw new Error("Authentication credentials are missing.");
    }

    try {
      // Create form data for OAuth2 token endpoint
      const formData = new URLSearchParams();
      formData.append('username', credentials.username);
      formData.append('password', credentials.password);
      formData.append('grant_type', 'password');

      const response = await fetch(this.buildApiUrl("/auth/token"), {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded"
        },
        body: formData
      });

      if (!response.ok) {
        await response.text();
        throw new Error(`Authentication failed: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();

      // Store the token for future use
      this.storeToken(data.access_token);

      return data;
    } catch (err) {
      throw err;
    }
  }

  /** Get test credentials from config */
  static getTestCredentials() {
    const username = CONFIG?.auth?.username;
    const password = CONFIG?.auth?.password;

    if (!username || !password) {
      return null;
    }

    return {
      username,
      password
    };
  }

  /** Legacy function for backward compatibility */
  static async getToken() {
    const existing = this.getStoredToken();
    if (existing) {
      return existing;
    }

    const credentials = this.getTestCredentials();
    if (!credentials) {
      throw new Error("No authentication method available.");
    }

    const auth = await this.login(credentials);
    return auth.access_token;
  }

  /** Get auto-login URL for redirecting to full React frontend */
  static async getAutoLoginUrl() {
    const websiteUrl = CONFIG?.websiteUrl;
    if (!websiteUrl) {
      console.error('No website URL configured for auto-login');
      return null;
    }

    try {
      const response = await fetch(this.buildApiUrl("/plugins/generate-login-url"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ website_url: websiteUrl })
      });

      if (!response.ok) {
        const errorText = await response.text().catch(() => "");
        console.error('Failed to get auto-login URL:', response.status, errorText);
        return null;
      }

      const data = await response.json().catch(() => null);
      if (!data || !data.login_url) {
        console.error('Invalid auto-login response:', data);
        return null;
      }

      return data.login_url;
    } catch (err) {
      console.error('Error getting auto-login URL:', err);
      return null;
    }
  }
}
