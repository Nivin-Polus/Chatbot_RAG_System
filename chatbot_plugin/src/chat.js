// chat.js
import { CONFIG } from "./config.js";
import { AuthService } from "./auth.js";

export class ChatService {
  constructor() {
    this.token = AuthService.getStoredToken();
    this.tokenContext = AuthService.getTokenContext?.() || null;
    this.sessionId = this.generateSessionId();
    this.conversationHistory = [];
    this.maxHistoryLength = 10; // Keep last 10 messages for context
  }

  /** Generate unique session ID */
  generateSessionId() {
    const timestamp = Date.now();
    const randomId = Math.random().toString(36).substring(2, 8);
    return `session_${timestamp}_${randomId}`;
  }

  /** Clear conversation context and start new session */
  clearContext() {
    this.sessionId = this.generateSessionId();
    this.conversationHistory = [];
  }

  /** Add message to conversation history */
  addToHistory(role, content) {
    const message = {
      role: role, // 'user' or 'assistant'
      content: content,
      timestamp: new Date().toISOString()
    };

    this.conversationHistory.push(message);

    // Keep only the last N messages to prevent payload from getting too large
    if (this.conversationHistory.length > this.maxHistoryLength) {
      this.conversationHistory = this.conversationHistory.slice(-this.maxHistoryLength);
    }
  }

  /** Get conversation context info */
  getContextInfo() {
    return {
      sessionId: this.sessionId,
      messageCount: this.conversationHistory.length,
      hasContext: this.conversationHistory.length > 0
    };
  }

  /** Restore conversation history from saved messages (e.g., from localStorage) */
  restoreHistory(savedMessages) {
    if (!Array.isArray(savedMessages)) return;

    // Rebuild conversation history from saved messages
    this.conversationHistory = savedMessages
      .slice(-this.maxHistoryLength) // Keep only last N messages
      .map(msg => ({
        role: msg.user ? 'user' : 'assistant',
        content: msg.text || '',
        timestamp: msg.timestamp || new Date().toISOString()
      }));
  }

  /** Update token context details */
  setTokenContext(context) {
    this.tokenContext = context || null;
  }

  /** Ensure a valid token is available */
  async ensureToken() {
    if (!this.token) {
      this.token = AuthService.getStoredToken();
      if (!this.token) {
        await this.refreshToken();
        return;
      }
    }

    // If we have a token context that indicates the plugin is valid, we don't need to verify
    if (this.tokenContext?.valid === true) {
      return;
    }

    const verification = await AuthService.verifyToken(this.token);
    if (verification?.valid) {
      this.setTokenContext(verification);
      return;
    }

    const pluginToken = AuthService.getConfiguredPluginToken?.();
    if (pluginToken && pluginToken !== this.token) {
      this.token = pluginToken;
      const pluginVerification = await AuthService.verifyToken(this.token);
      if (pluginVerification?.valid) {
        this.setTokenContext(pluginVerification);
        return;
      }
    }

    await this.refreshToken();
  }

  async refreshToken() {
    // If we have a valid context but no token, we don't need to refresh
    if (this.tokenContext?.valid === true && !this.token) {
      return;
    }

    const pluginToken = AuthService.getConfiguredPluginToken?.();
    if (pluginToken) {
      this.token = pluginToken;
      const verification = await AuthService.verifyToken(this.token);
      if (verification?.valid) {
        this.setTokenContext(verification);
        return;
      }

      throw new Error("Configured plugin token is invalid.");
    }

    const creds = AuthService.getTestCredentials();
    if (!creds) {
      throw new Error("Unable to refresh token: no credentials configured.");
    }

    const auth = await AuthService.login(creds);
    this.token = auth.access_token;

    const verification = await AuthService.verifyToken(this.token);
    if (verification?.valid) {
      this.setTokenContext(verification);
    } else {
      throw new Error("Unable to verify refreshed access token.");
    }
  }

  /** Send message to backend */
  async sendMessage(message, options = {}) {
    const { signal } = options;
    try {
      await this.ensureToken(); // make sure token is valid

      // Add user message to history before sending
      this.addToHistory('user', message);

      // Prepare payload with conversation context
      const payload = {
        question: message,
        session_id: this.sessionId,
        conversation_history: this.conversationHistory.slice(0, -1), // Exclude the current message
        maintain_context: this.conversationHistory.length > 1
      };

      const resolvedCollectionId = this.tokenContext?.collection_id || CONFIG.collectionId;
      if (resolvedCollectionId) {
        payload.collection_id = resolvedCollectionId;
      }

      if (this.tokenContext?.website_id) {
        payload.website_id = this.tokenContext.website_id;
      }

      const response = await fetch(`${CONFIG.apiBase}/chat/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${this.token}`,
        },
        body: JSON.stringify(payload),
        signal,
      });

      if (!response.ok) {
        await response.text();
        throw new Error(`Chat request failed: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      
      // NEW: Handle follow-up response
      if (data.is_followup) {
        // Add follow-up to conversation history (marked as such)
        this.addToHistory('assistant', data.followup_questions);
        
        return {
          text: data.followup_questions,
          is_followup: true,
          followup_reason: data.followup_reason,
          sources: [],
          generic: false,
          session_id: data.session_id
        };
      }
      
      // Normal response handling
      const formattedResponse = this.formatResponse(data.answer);
      const isGeneric = Boolean(data.generic || data.is_generic);

      // Add assistant response to history
      this.addToHistory('assistant', data.answer);

      // Normalize sources to ensure all fields are captured
      const normalizeSources = (sources) => {
        if (!Array.isArray(sources)) return [];
        return sources.map(source => {
          if (!source || typeof source !== 'object') return null;
          // Capture all source fields from API response
          return {
            file_name: source.file_name || null,
            file_id: source.file_id || null,
            chunk_indices: Array.isArray(source.chunk_indices) ? source.chunk_indices : null,
            source_type: source.source_type || 'file',
            url: source.url || null
          };
        }).filter(source => source !== null && source.file_name); // Only keep sources with file_name
      };

      // Return formatted text, sources (with all fields preserved), and generic flag
      return {
        text: formattedResponse,
        sources: normalizeSources(data.sources || []),
        generic: isGeneric,
        is_followup: false,
        session_id: data.session_id
      };
    } catch (err) {
      if (err?.name === 'AbortError') {
        // On abort, roll back the last user message and rethrow for UI to handle
        if (this.conversationHistory.length > 0 &&
          this.conversationHistory[this.conversationHistory.length - 1].role === 'user') {
          this.conversationHistory.pop();
        }
        throw err;
      }
      // Remove the user message from history if the request failed
      if (this.conversationHistory.length > 0 &&
        this.conversationHistory[this.conversationHistory.length - 1].role === 'user') {
        this.conversationHistory.pop();
      }
      throw err; // Let the UI handle the error display
    }
  }

  /** Format response similar to React frontend rendering */
  formatResponse(text) {
    if (!text) return "";

    let normalized = text.trimEnd();

    // Detect generic / fallback HR assistant responses (no actual HR data)
    const isGenericResponse = /I apologize|I'm limited to providing information|not have any information|outside of my scope|I'm afraid I don't have enough information|I don't have access to information|I don't have any information about/i.test(normalized);

    if (isGenericResponse) {
      // Remove "Sources:" and everything after it only for generic replies
      normalized = normalized
        // Handle variants like "**Sources:**", "- Sources:", "> Sources"
        .replace(/(\r?\n)+[\s>*-]*\**\s*Sources?\s*:?\s*\**[\s\S]*$/i, "")
        .trim();
    }

    return normalized;
  }



}
