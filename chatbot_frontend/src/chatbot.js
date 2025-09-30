// index.js or chatbot.js
import { AuthService } from './services/authService.js';
import { ChatService } from './services/chatService.js';
import { handleAuthError } from './utils/errorHandler.js';

class Chatbot {
  constructor() {
    this.token = null;
    this.chatService = null;
  }

  /** Initialize chatbot: login and set up chat service */
  async initialize(credentials) {
    try {
      const authResponse = await AuthService.login(credentials);
      this.token = authResponse.access_token;

      // Initialize chat service with the token
      this.chatService = new ChatService();
      this.chatService.token = this.token;

      return true;
    } catch (error) {
      handleAuthError(error);
      return false;
    }
  }

  /** Send message through chat service */
  async sendMessage(message) {
    if (!this.token) {
      throw new Error('Authentication required');
    }

    // Verify token is still valid
    if (!(await AuthService.verifyToken(this.token))) {
      // Token expired: re-login automatically using test credentials
      const creds = AuthService.getTestCredentials();
      const authResponse = await AuthService.login(creds);
      this.token = authResponse.access_token;
      this.chatService.token = this.token;
    }

    // Delegate message sending to ChatService
    return await this.chatService.sendMessage(message);
  }
}

export default Chatbot;
