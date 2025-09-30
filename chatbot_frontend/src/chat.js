// chat.js
import { CONFIG } from "./config.js";
import { AuthService } from "./auth.js";

export class ChatService {
  constructor() {
    this.token = AuthService.getStoredToken();
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

  /** Ensure a valid token is available */
  async ensureToken() {
    if (!this.token || !(await AuthService.verifyToken(this.token))) {
      // Use test credentials if no token is stored
      const creds = AuthService.getTestCredentials();
      const auth = await AuthService.login(creds);
      this.token = auth.access_token;
    }
  }

  /** Send message to backend */
  async sendMessage(message) {
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

      const response = await fetch(`${CONFIG.apiBase}/chat/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${this.token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`Chat request failed: ${response.status} ${response.statusText}`);
        throw new Error(`Chat request failed: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      const formattedResponse = this.formatResponse(data.answer);
      
      // Add assistant response to history
      this.addToHistory('assistant', data.answer);
      
      return formattedResponse;
    } catch (err) {
      console.error("Chat error:", err.message);
      // Remove the user message from history if the request failed
      if (this.conversationHistory.length > 0 && 
          this.conversationHistory[this.conversationHistory.length - 1].role === 'user') {
        this.conversationHistory.pop();
      }
      throw err; // Let the UI handle the error display
    }
  }

  /** Format response for better readability */
  formatResponse(text) {
    if (!text) return text;

    let formatted = text;

    // First, normalize spacing and clean up excessive whitespace, but preserve intentional line breaks
    formatted = formatted.replace(/[ \t]+/g, ' ').trim();
    
    // Fix broken sentences where bullets appear mid-sentence (like "work • life balance")
    formatted = formatted.replace(/(\w+)\s*•\s*(\w+)/g, '$1-$2');
    
    // Fix broken sentences where bullets appear at line breaks
    formatted = formatted.replace(/(\w+)\s*\n\s*•\s*(\w+)/g, '$1-$2');
    
    // Handle main bullet points that start lines (- or • followed by text with colon)
    formatted = formatted.replace(/^[-•]\s*([^:\n]+):\s*/gm, '\n- **$1:** ');
    formatted = formatted.replace(/\n[-•]\s*([^:\n]+):\s*/g, '\n- **$1:** ');
    
    // Handle bullet points without colons (simple list items)
    formatted = formatted.replace(/^[-•]\s*([^-•\n][^\n]*?)(?=\n[-•]|\n\n|$)/gm, '\n- $1');
    formatted = formatted.replace(/\n[-•]\s*([^-•\n][^\n]*?)(?=\n[-•]|\n\n|$)/g, '\n- $1');
    
    // Clean up any remaining standalone bullets or dashes at the start of lines
    formatted = formatted.replace(/\n[-•]\s*/g, '\n- ');
    
    // Handle section headers (text ending with colon that's not already formatted)
    formatted = formatted.replace(/\n([A-Za-z][A-Za-z\s()]+?):\s*(?!\*\*)/g, '\n\n**$1:**\n');
    
    // Add line breaks before numbered points (1., 2., etc.)
    formatted = formatted.replace(/(\d+\.)\s*/g, '\n\n$1 ');
    
    // Clean up multiple consecutive line breaks
    formatted = formatted.replace(/\n{3,}/g, '\n\n');
    
    // Ensure proper spacing after headers
    formatted = formatted.replace(/\*\*([^*]+)\*\*:\s*\n([^-\n])/g, '**$1:**\n$2');
    
    // Add spacing between bullet point groups
    formatted = formatted.replace(/([^-\n])\n-/g, '$1\n\n-');
    
    // Fix any remaining formatting issues
    formatted = formatted.replace(/\n\s*\n-/g, '\n\n-');
    
    // Clean up and trim
    formatted = formatted.trim();
    
    // Ensure the response starts cleanly
    if (formatted.startsWith('\n')) {
      formatted = formatted.substring(1);
    }
    
    return formatted;
  }
}
