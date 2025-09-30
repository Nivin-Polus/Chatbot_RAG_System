// ui.js
import { CONFIG } from './config.js';

export class ChatbotUI {
  constructor() {
    this.isOpen = false;
    this.chatPanel = null;
    this.toggleBtn = null;
  }

  init() {
    this.createToggleButton();
    this.createChatPanel();
  }

  createToggleButton() {
    this.toggleBtn = document.createElement("button");
    this.toggleBtn.className = "chat-toggle";
    this.toggleBtn.innerHTML = "💬";

    this.toggleBtn.addEventListener("click", () => this.toggleChat());

    document.body.appendChild(this.toggleBtn);
  }

  createChatPanel() {
    this.chatPanel = document.createElement("div");
    this.chatPanel.className = "chat-panel";
    this.chatPanel.innerHTML = `
      <div class="chat-header">
        <div class="chat-header-left">
          <span class="chat-title">${CONFIG.ui.headerTitle}</span>
          <span class="context-indicator" id="context-indicator" style="display: none;">
            💬 <span id="context-count">0</span> messages
          </span>
        </div>
        <div class="chat-header-right">
          <button class="new-chat-btn" id="new-chat-btn" style="display: none;" title="Start New Chat">🔄</button>
          <span class="chat-close">&times;</span>
        </div>
      </div>
      <div class="chat-box" id="chat-box">
        <div class="msg bot welcome">
          <span class="msg-avatar">🤖</span>
          <div class="msg-content">${CONFIG.ui.welcomeMessage}</div>
        </div>
      </div>
      <div class="chat-input">
        <input type="text" id="chat-message" placeholder="${CONFIG.ui.inputPlaceholder}" maxlength="500"/>
        <button id="chat-send">➤</button>
      </div>
    `;

    document.body.appendChild(this.chatPanel);

    this.chatPanel.querySelector(".chat-close")
      .addEventListener("click", () => this.toggleChat());
  }

  /** Update context indicator */
  updateContextIndicator(contextInfo) {
    const indicator = document.getElementById("context-indicator");
    const countElement = document.getElementById("context-count");
    const newChatBtn = document.getElementById("new-chat-btn");
    
    if (contextInfo.hasContext) {
      indicator.style.display = "inline-block";
      newChatBtn.style.display = "inline-block";
      countElement.textContent = contextInfo.messageCount;
    } else {
      indicator.style.display = "none";
      newChatBtn.style.display = "none";
    }
  }

  toggleChat() {
    this.isOpen = !this.isOpen;
    this.chatPanel.style.display = this.isOpen ? "flex" : "none";
  }
}
