// ui.js
import { CONFIG } from './config.js';

export class ChatbotUI {
  constructor() {
    this.isOpen = false;
    this.isExpanded = false;
    this.chatPanel = null;
    this.toggleBtn = null;
    this.newChatBtn = null;
    this.newChatCooldownMs = 3000;
    this.newChatCooldownTimer = null;
    this.lastNewChatAt = 0;
    this.onExpandHistory = null;
  }

  init() {
    this.createToggleButton();
    this.createChatPanel();
  }

  /** Create Floating Toggle Button */
  createToggleButton() {
    this.toggleBtn = document.createElement("button");
    this.toggleBtn.className = "plugin-chat-toggle chat-toggle";
    this.toggleBtn.type = "button";
    this.toggleBtn.setAttribute("aria-expanded", "false");
    this.toggleBtn.innerHTML = `
      <img src="${CONFIG.ui.iconsBaseUrl}/logo.svg" 
           alt="Open chat" class="plugin-icon icon"/>`;

    this.toggleBtn.addEventListener("click", () => this.toggleChat());
    document.body.appendChild(this.toggleBtn);
  }

  /** Create Main Chat Panel */
  createChatPanel() {
    this.chatPanel = document.createElement("div");
    this.chatPanel.className = "plugin-chat-panel chat-panel";

    const placeholderText = CONFIG.ui.inputPlaceholder || "";
    const welcomeMessage = CONFIG.ui.welcomeMessage || "";
    const highlightGradient = CONFIG.ui.placeholderHighlightColor || "var(--chat-placeholder-highlight, var(--chat-primary))";
    const highlightSolid = CONFIG.ui.placeholderHighlightSolid || "var(--chat-placeholder-highlight-solid, var(--chat-primary-solid))";

    // Build inner HTML
    this.chatPanel.innerHTML = `
      <div class="plugin-chat-header chat-header">
        <div class="plugin-chat-header-left chat-header-left">
          <div class="plugin-chat-brand chat-brand">
            ${CONFIG.ui.logoUrl
        ? `<img src="${CONFIG.ui.logoUrl}" alt="${CONFIG.ui.logoAlt || 'Logo'}" class="plugin-chat-logo chat-logo"/>`
        : `<img src="${CONFIG.ui.iconsBaseUrl}/logo.svg" alt="Chat" class="plugin-chat-logo chat-logo"/>`}
            <span class="plugin-chat-title chat-title">${CONFIG.ui.headerTitle}</span>
          </div>
        </div>
        <div class="plugin-chat-header-right chat-header-right">
          <div class="plugin-chat-icon-btn chat-settings-btn" id="chat-settings-btn" title="Settings" aria-label="Settings" data-tooltip="Settings" role="button" tabindex="0">
            <span class="plugin-icon icon" style="--icon-url: url('${CONFIG.ui.iconsBaseUrl}/settings.svg');" aria-hidden="true"></span>
          </div>
          <div class="plugin-chat-icon-btn chat-expand-btn" id="chat-expand-btn" title="Expand" aria-label="Expand" data-tooltip="Expand" role="button" tabindex="0">
             <span class="plugin-icon icon" style="--icon-url: url('${CONFIG.ui.iconsBaseUrl}/expand.svg');" aria-hidden="true"></span>
          </div>
          <div class="plugin-new-chat-btn new-chat-btn" id="new-chat-btn" title="Start new chat" aria-label="Start new chat" data-tooltip="Start new chat" role="button" tabindex="0">
            <span class="plugin-icon icon" style="--icon-url: url('${CONFIG.ui.iconsBaseUrl}/refresh.svg');" aria-hidden="true"></span>
          </div>
          <div class="plugin-chat-close chat-close" title="Close chat" aria-label="Close chat" data-tooltip="Close chat" role="button" tabindex="0">
            <span class="plugin-icon icon" style="--icon-url: url('${CONFIG.ui.iconsBaseUrl}/close.svg');" aria-hidden="true"></span>
          </div>
        </div>
      </div>

      <div class="plugin-chat-body chat-body">
        <div class="plugin-chat-sidebar chat-sidebar" id="chat-sidebar" style="display:none;">
            <div class="plugin-sidebar-header sidebar-header">
                <h3>Chat History</h3>
            </div>
            <div class="plugin-history-list history-list" id="chat-history-list"></div>
        </div>

        <div class="plugin-chat-main chat-main">
            <div class="plugin-chat-box chat-box" id="chat-box"></div>

            <div class="plugin-chat-empty chat-empty" id="chat-empty">
                <img class="plugin-empty-logo empty-logo" 
                    src="${CONFIG.ui.placeholderLogoUrl || CONFIG.ui.logoUrl || (CONFIG.ui.iconsBaseUrl + '/logo.svg')}" 
                    alt="Placeholder"/>
                <div class="plugin-empty-title empty-title">Hello,</div>
                <div class="plugin-empty-subtitle empty-subtitle">
                ${this.buildPlaceholderMarkup(CONFIG.ui.inputPlaceholder, CONFIG.ui.placeholderHighlightText, highlightGradient)}
                </div>
            </div>

            <div class="plugin-chat-input chat-input">
                <div class="plugin-chat-input-field chat-input-field">
                <input type="text" 
                        id="chat-message" 
                        placeholder=" " 
                        aria-label="${this.escapeHtml(welcomeMessage)}" 
                        maxlength="500"/>
                <span class="plugin-custom-placeholder custom-placeholder">${welcomeMessage}</span>
                </div>
                <button type="button" id="chat-stop" title="Stop" style="display:none" aria-label="Stop">
                <span class="plugin-icon icon" style="--icon-url: url('${CONFIG.ui.iconsBaseUrl}/close.svg');" aria-hidden="true"></span>
                </button>
                <button type="button" id="chat-send" title="Send">
                <img src="${CONFIG.ui.iconsBaseUrl}/send.svg" alt="Send" class="plugin-icon icon"/>
                </button>
            </div>
            <div class="plugin-ai-disclaimer ai-disclaimer">
                Generated with AI assistance. Always check for accuracy and completeness.
            </div>
        </div>
      </div>
    `;

    document.body.appendChild(this.chatPanel);

    this.chatPanel.setAttribute("aria-hidden", "true");

    this.newChatBtn = this.chatPanel.querySelector("#new-chat-btn");

    // Wire up new buttons
    const expandBtn = this.chatPanel.querySelector("#chat-expand-btn");

    if (expandBtn) {
      expandBtn.onclick = (e) => {
        e.stopPropagation();
        this.toggleExpand();
      };
    }

    /** Handle Placeholder Gradient */
    const inputField = this.chatPanel.querySelector(".plugin-chat-input-field");
    const inputElement = this.chatPanel.querySelector("#chat-message");

    if (inputField) {
      inputField.style.setProperty("--placeholder-highlight", highlightSolid);
    }

    if (inputField && inputElement) {
      const togglePlaceholderState = () => {
        const hasValue = inputElement.value.trim().length > 0;
        inputField.classList.toggle("plugin-has-value", hasValue);
        inputField.classList.toggle("has-value", hasValue);
      };

      inputElement.addEventListener("input", togglePlaceholderState);
      inputElement.addEventListener("focus", () => {
        inputField.classList.add("plugin-is-focused");
        inputField.classList.add("is-focused");
      });
      inputElement.addEventListener("blur", () => {
        inputField.classList.remove("plugin-is-focused");
        inputField.classList.remove("is-focused");
        togglePlaceholderState();
      });

      togglePlaceholderState();
    }

    /** Close button */
    const closeBtn = this.chatPanel.querySelector(".plugin-chat-close");
    if (closeBtn) {
      closeBtn.onclick = () => this.toggleChat();
    }
  }

  /** Update context indicator */
  updateContextIndicator(contextInfo) {
    if (this.newChatBtn) {
      this.newChatBtn.style.display = "flex";
    }
  }

  /** Toggle Chat Open/Close */
  toggleChat() {
    this.isOpen = !this.isOpen;
    if (this.chatPanel) {
      this.chatPanel.classList.toggle("plugin-is-open", this.isOpen);
      this.chatPanel.classList.toggle("is-open", this.isOpen);
      this.chatPanel.setAttribute("aria-hidden", this.isOpen ? "false" : "true");
    }

    if (this.toggleBtn) {
      this.toggleBtn.classList.toggle("plugin-is-active", this.isOpen);
      this.toggleBtn.classList.toggle("is-active", this.isOpen);
      this.toggleBtn.setAttribute("aria-expanded", this.isOpen ? "true" : "false");
    }

    if (this.isOpen) {
      const inputElement = this.chatPanel?.querySelector("#chat-message");
      if (inputElement) {
        setTimeout(() => inputElement.focus(), 150);
      }
    }
  }

  toggleExpand() {
    this.isExpanded = !this.isExpanded;
    this.chatPanel.classList.toggle("plugin-is-expanded", this.isExpanded);
    this.chatPanel.classList.toggle("is-expanded", this.isExpanded);

    const sidebar = this.chatPanel.querySelector("#chat-sidebar");

    if (this.isExpanded) {
      sidebar.style.display = "flex";
      // Trigger history load
      if (this.onExpandHistory) {
        this.onExpandHistory();
      }
    } else {
      sidebar.style.display = "none";
    }
  }

  renderHistoryList(sessions, activeSessionId, onSelect, onDelete) {
    const list = this.chatPanel.querySelector("#chat-history-list");
    if (!list) return;

    list.innerHTML = "";

    if (!sessions || sessions.length === 0) {
      list.innerHTML = '<div class="plugin-history-empty">No history</div>';
      return;
    }

    sessions.forEach(session => {
      const item = document.createElement("div");
      item.className = "plugin-history-item history-item";
      if (session.id === activeSessionId) {
        item.classList.add("is-active");
      }

      const date = new Date(session.timestamp).toLocaleDateString();
      // Use first message as title if available, else 'New Chat'
      const title = session.title || 'New Chat';

      item.innerHTML = `
            <div class="plugin-history-content">
                <div class="plugin-history-title" title="${this.escapeHtml(title)}">${this.escapeHtml(title)}</div>
                <div class="plugin-history-date">${date}</div>
            </div>
            <div class="plugin-history-actions">
                <button class="plugin-history-delete" title="Delete">
                     <span class="plugin-icon icon" style="--icon-url: url('${CONFIG.ui.apiBase}/dist/assets/close.svg');" aria-hidden="true"></span>
                </button>
            </div>
        `;

      item.onclick = () => onSelect(session.id);

      const deleteBtn = item.querySelector(".plugin-history-delete");
      deleteBtn.onclick = (e) => {
        e.stopPropagation();
        onDelete(session.id);
      };

      list.appendChild(item);
    });
  }

  canTriggerNewChat() {
    const now = Date.now();
    return now - this.lastNewChatAt >= this.newChatCooldownMs;
  }

  startNewChatCooldown() {
    if (!this.newChatBtn) return;

    this.lastNewChatAt = Date.now();
    this.newChatBtn.disabled = true;
    this.newChatBtn.classList.add("plugin-is-cooldown");
    this.newChatBtn.classList.add("is-cooldown");

    clearTimeout(this.newChatCooldownTimer);
    this.newChatCooldownTimer = setTimeout(() => {
      this.newChatBtn.disabled = false;
      this.newChatBtn.classList.remove("plugin-is-cooldown");
      this.newChatBtn.classList.remove("is-cooldown");
    }, this.newChatCooldownMs);
  }

  /** Build Placeholder Markup with Gradient */
  buildPlaceholderMarkup(placeholder, highlight, highlightColor) {
    if (!placeholder) return "";

    if (!highlight) return this.escapeHtml(placeholder);

    const lowerPlaceholder = placeholder.toLowerCase();
    const lowerHighlight = highlight.toLowerCase();
    const matchIndex = lowerPlaceholder.indexOf(lowerHighlight);

    if (matchIndex === -1) return this.escapeHtml(placeholder);

    const before = placeholder.slice(0, matchIndex);
    const matched = placeholder.slice(matchIndex, matchIndex + highlight.length);
    const after = placeholder.slice(matchIndex + highlight.length);

    // Gradient span for both input + empty subtitle
    return `${this.escapeHtml(before)}
      <span class="plugin-custom-placeholder-highlight custom-placeholder-highlight"
            style="background: ${highlightColor || "var(--chat-placeholder-highlight, var(--chat-primary))"};
                   -webkit-background-clip: text;
                   -webkit-text-fill-color: transparent;
                   background-clip: text;">
        ${this.escapeHtml(matched)}
      </span>
      ${this.escapeHtml(after)}`;
  }

  /** Escape HTML safely */
  escapeHtml(text) {
    return `${text ?? ""}`.replace(/[&<>"']/g, (char) => {
      switch (char) {
        case "&": return "&amp;";
        case "<": return "&lt;";
        case ">": return "&gt;";
        case '"': return "&quot;";
        case "'": return "&#39;";
        default: return char;
      }
    });
  }
}
