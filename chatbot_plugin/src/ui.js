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

    // Embed icons to avoid external dependency issues
    // Embed icons to avoid external dependency issues
    this.ICONS = {
      settings: "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImJsYWNrIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMyI+PC9jaXJjbGU+PHBhdGggZD0iTTE5LjQgMTVhMS42NSAxLjY1IDAgMCAwIC4zMyAxLjgybC4wNi4wNmEyIDIgMCAwIDEgMCAyLjgzIDIgMiAwIDAgMS0yLjgzIDBsLS4wNi0uMDZhMS42NSAxLjY1IDAgMCAwLTEuODItLjMzIDEuNjUgMS42NSAwIDAgMC0xIDEuNTFWMjFhMiAyIDAgMCAxLTIgMiAyIDIgMCAwIDEtMi0ydi0uMDlBMS42NSAxLjY1IDAgMCAwIDkgMTkuNGExLjY1IDEuNjUgMCAwIDAtMS44Mi4zM2wtLjA2LjA2YTIgMiAwIDAgMS0yLjgzIDAgMiAyIDAgMCAxIDAtMi44M2wuMDYtLjA2YTEuNjUgMS42NSAwIDAgMCAuMzMtMS44MiAxLjY1IDEuNjUgMCAwIDAtMS41MS0xSDNhMiAyIDAgMCAxLTItMiAyIDIgMCAwIDEgMi0yaC4wOUExLjY1IDEuNjUgMCAwIDAgNC42IDlhMS42NSAxLjY1IDAgMCAwLS4zMy0xLjgybC0uMDYtLjA2YTIgMiAwIDAgMSAwLTIuODMgMiAyIDAgMCAxIDIuODMgMGwuMDYuMDZhMS42NSAxLjY1IDAgMCAwIDEuODIuMzNIOWExLjY1IDEuNjUgMCAwIDAgMS0xLjUxVjNhMiAyIDAgMCAxIDItMiAyIDIgMCAwIDEgMiAydi4wOWExLjY1IDEuNjUgMCAwIDAgMSAxLjUxIDEuNjUgMS42NSAwIDAgMCAxLjgyLS4zM2wuMDYtLjA2YTIgMiAwIDAgMSAyLjgzIDAgMiAyIDAgMCAxIDAgMi44M2wtLjA2LjA2YTEuNjUgMS42NSAwIDAgMC0uMzMgMS44MlY5YTEuNjUgMS42NSAwIDAgMCAxLjUxIDFIMjFhMiAyIDAgMCAxIDIgMiAyIDAgMCAxIDEtMiAyaC0uMDlhMS42NSAxLjY1IDAgMCAwLTEuNTEgMXoiPjwvcGF0aD48L3N2Zz4=",
      expand: "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImJsYWNrIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBvbHlsaW5lIHBvaW50cz0iMTUgMyAyMSAzIDIxIDkiPjwvcG9seWxpbmU+PHBvbHlsaW5lIHBvaW50cz0iOSAyMSAzIDIxIDMgMTUiPjwvcG9seWxpbmU+PGxpbmUgeDE9IjIxIiB5MT0iMyIgeDI9IjE0IiB5Mj0iMTAiPjwvbGluZT48bGluZSB4MT0iMyIgeTE9IjIxIiB4Mj0iMTAiIHkyPSIxNCI+PC9saW5lPjwvc3ZnPg==",
      minimize: "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImJsYWNrIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTggM3YzYTIgMiAwIDAgMS0yIDJIMyI+PC9wYXRoPjxwYXRoIGQ9Ik0yMSA4aC0zYTIgMiAwIDAgMS0yLTJWMyI+PC9wYXRoPjxwYXRoIGQ9Ik0zIDE2aDNhMiAyIDAgMCAxIDIgMnYzIj48L3BhdGg+PHBhdGggZD0iTTE2IDIxdi0zYTIgMiAwIDAgMSAyLTJoMyI+PC9wYXRoPjwvc3ZnPg==",
      trash: "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImJsYWNrIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTMgNmgxOCI+PC9wYXRoPjxwYXRoIGQ9Ik0xOSA2djE0YzAgMS0xIDItMiAySDdjLTEgMC0yLTEtMi0yVjYiPjwvcGF0aD48cGF0aCBkPSJNOCA2VjRjMC0xIDEtMiAyLTJoNGMxIDAgMiAxIDIgMnYyIj48L3BhdGg+PC9zdmc+",
      refresh: "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImJsYWNrIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTMgMTJhOSA5IDAgMCAxIDktOSA5Ljc1IDkuNzUgMCAwIDEgNi43NCAyLjc0TDIxIDgiPjwvcGF0aD48cGF0aCBkPSJNMjEgM3Y1aC01Ij48L3BhdGg+PHBhdGggZD0iTTIxIDEyYTkgOSAwIDAgMS05IDkgOS43NSA5Ljc1IDAgMCAxLTYuNzQtMi43NEwzIDE2Ij48L3BhdGg+PHBhdGggZD0iTTggMTZIM3Y1Ij48L3BhdGg+PC9zdmc+",
      close: "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImJsYWNrIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTE4IDYgNiAxOCI+PC9wYXRoPjxwYXRoIGQ9Im02IDYgMTIgMTIiPjwvcGF0aD48L3N2Zz4=",
      plus: "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImJsYWNrIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTIwIDEwVjE4QTIgMiAwIDAgMSAxOCAyMEg2TDMgMjNWOEEyIDIgMCAwIDEgNSA2SDE0IE0xOCAzVjkgTTE1IDZIMjEiIC8+PC9zdmc+",
      edit: "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImJsYWNrIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTExIDRINGEyIDIgMCAwIDAtMiAydjE0YTIgMiAwIDAgMCAyIDJoMTRhMiAyIDAgMCAwIDItMnYtNyI+PC9wYXRoPjxwYXRoIGQ9Ik0xOC41IDIuNWEyLjEyMSAyLjEyMSAwIDAgMSAzIDNMMTIgMTVsLTQgMSAxLTQgOS41LTkuNXoiPjwvcGF0aD48L3N2Zz4=",
      menu: "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImJsYWNrIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PGxpbmUgeDE9IjMiIHkxPSIxMiIgeDI9IjIxIiB5Mj0iMTIiPjwvbGluZT48bGluZSB4MT0iMyIgeTE9IjYiIHgyPSIyMSIgeTI9IjYiPjwvbGluZT48bGluZSB4MT0iMyIgeTE9IjE4IiB4Mj0iMjEiIHkyPSIxOCI+PC9saW5lPjwvc3ZnPg=="
    };

    this.activeSidebarMode = 'history'; // 'history' | 'settings'
    this.getCurrentSessionId = null; // Callback to get current session ID for chat history transfer
    this.getSessionMessages = null; // Callback to get current session messages for transfer
    this.getAllSessions = null; // Callback to get all sessions for full history transfer
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
          <div class="plugin-chat-icon-btn chat-expand-btn" id="chat-expand-btn" aria-label="Expand" data-tooltip="Expand" role="button" tabindex="0">
             <span class="plugin-icon icon" style="--icon-url: url('${this.ICONS.expand}');" aria-hidden="true"></span>
          </div>
          <div class="plugin-new-chat-btn new-chat-btn" id="new-chat-btn" aria-label="Start new chat" data-tooltip="Start new chat" role="button" tabindex="0">
            <span class="plugin-icon icon" style="--icon-url: url('${this.ICONS.plus}');" aria-hidden="true"></span>
          </div>
          <div class="plugin-chat-close chat-close" aria-label="Close chat" data-tooltip="Close chat" role="button" tabindex="0">
            <span class="plugin-icon icon" style="--icon-url: url('${this.ICONS.close}');" aria-hidden="true"></span>
          </div>
        </div>
      </div>

      <div class="plugin-chat-body chat-body">
        <div class="plugin-chat-sidebar chat-sidebar" id="chat-sidebar" style="display:none;">
            <div class="plugin-sidebar-header sidebar-header" id="sidebar-header">
                <h3>Chat History</h3>
                <button class="plugin-sidebar-toggle sidebar-toggle" id="sidebar-toggle" aria-label="Close Menu">
                    <span class="plugin-icon icon" style="--icon-url: url('${this.ICONS.menu}');" aria-hidden="true"></span>
                </button>
            </div>
            <div class="plugin-sidebar-content sidebar-content">
                <div class="plugin-history-list history-list" id="chat-history-list"></div>
                <div class="plugin-settings-panel settings-panel" id="chat-settings-panel" style="display:none;">
                     <button class="plugin-settings-back" id="settings-back-btn">
                        ← Back to History
                     </button>
                     <!-- Basic Settings Content -->
                     <div class="plugin-settings-item">
                        <label>Plugin Version</label>
                        <span>v1.2.0</span>
                     </div>
                     <div class="plugin-settings-item">
                        <label>Theme</label>
                        <span>System Default</span>
                     </div>
                     <div class="plugin-settings-info">
                        More settings coming soon.
                     </div>
                </div>
            </div>
        </div>

        <div class="plugin-chat-main chat-main">
            <button class="plugin-sidebar-toggle sidebar-show-btn" id="sidebar-show-btn" aria-label="Open Menu">
                <span class="plugin-icon icon" style="--icon-url: url('${this.ICONS.menu}');" aria-hidden="true"></span>
            </button>
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
                <span class="plugin-icon icon" style="--icon-url: url('${this.ICONS.close}');" aria-hidden="true"></span>
                </button>
                <button type="button" id="chat-send" title="Send">
                <span class="plugin-icon icon" style="--icon-url: url('${this.ICONS.settings}'); --icon-rotate: 45deg; display: none;"></span> <!-- Placeholder or Send icon can be added here -->
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
    const sidebarToggleBtn = this.chatPanel.querySelector("#sidebar-toggle");
    const sidebarShowBtn = this.chatPanel.querySelector("#sidebar-show-btn");

    // Wire up new buttons
    const expandBtn = this.chatPanel.querySelector("#chat-expand-btn");

    const toggleHandler = (e) => {
      e.stopPropagation();
      this.toggleSidebar();
    };

    if (sidebarToggleBtn) {
      sidebarToggleBtn.onclick = toggleHandler;
    }

    if (sidebarShowBtn) {
      sidebarShowBtn.onclick = toggleHandler;
    }

    const settingsBackBtn = this.chatPanel.querySelector("#settings-back-btn");
    if (settingsBackBtn) {
      settingsBackBtn.onclick = (e) => {
        e.stopPropagation();
        this.setSidebarMode('history');
      };
    }

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

  toggleSidebar() {
    const sidebar = this.chatPanel.querySelector('#chat-sidebar');
    if (sidebar) {
      sidebar.classList.toggle('is-hidden');
    }
  }

  async toggleExpand(forceMode) {
    // If already expanded and clicking expand again, redirect to full React frontend
    if (this.isExpanded && !forceMode) {
      try {
        // Import dependencies dynamically to avoid circular dependency
        const { AuthService } = await import('./auth.js');
        const { CONFIG } = await import('./config.js');
        const loginUrl = await AuthService.getAutoLoginUrl();
        if (loginUrl) {
          let finalUrl = loginUrl;
          let transferSuccessful = false;

          // Try to transfer ALL chat sessions to backend for seamless migration
          const allSessions = this.getAllSessions?.() || [];
          const currentSessionId = this.getCurrentSessionId?.() || null;
          
          // Get visitor ID for user isolation
          const visitorId = localStorage.getItem('chatbot_visitor_id') || '';

          if (allSessions.length > 0 && CONFIG?.websiteUrl) {
            try {
              const apiBase = (CONFIG.apiBase || '').replace(/\/+$/, '');
              const transferResponse = await fetch(`${apiBase}/plugins/transfer-sessions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  website_url: CONFIG.websiteUrl,
                  visitor_id: visitorId,  // Include visitor ID for user isolation
                  current_session_id: currentSessionId,
                  sessions: allSessions.map(session => ({
                    session_id: session.id,
                    title: session.title || 'New Chat',
                    timestamp: session.timestamp,
                    messages: (session.messages || []).filter(m => !m.isTypingIndicator && !m.isTyping).map(m => ({
                      user: Boolean(m.user),
                      text: m.text || '',
                      formatted: Boolean(m.formatted),
                      timestamp: m.timestamp || new Date().toISOString(),
                      sources: m.sources || [],
                      isFollowup: Boolean(m.isFollowup),
                    })),
                  })),
                }),
              });

              if (transferResponse.ok) {
                const transferData = await transferResponse.json();
                const separator = loginUrl.includes('?') ? '&' : '?';
                // Include visitor_id so extended plugin can sync back to the same visitor
                finalUrl = `${loginUrl}${separator}transfer_token=${encodeURIComponent(transferData.transfer_token)}&visitor_id=${encodeURIComponent(visitorId)}`;
                transferSuccessful = true;
              } else {
                console.warn('Could not transfer sessions, proceeding without chat history');
              }
            } catch (transferErr) {
              console.warn('Session transfer failed:', transferErr);
            }
          }

          // Notify that transfer was successful
          // Note: We preserve localStorage so users can continue their chat
          // when they return to the plugin after closing the extended frontend
          if (transferSuccessful && this.onTransferComplete) {
            this.onTransferComplete();
          }

          window.open(finalUrl, '_blank');
          return;
        } else {
          console.warn('Could not get auto-login URL, staying in plugin');
        }
      } catch (err) {
        console.error('Failed to get auto-login URL:', err);
      }
    }

    // If specific mode requested, just switch to it if already expanded
    if (forceMode && this.isExpanded) {
      this.setSidebarMode(forceMode);
      return;
    }

    // Default toggle behavior
    this.isExpanded = !this.isExpanded;
    this.chatPanel.classList.toggle("plugin-is-expanded", this.isExpanded);
    this.chatPanel.classList.toggle("is-expanded", this.isExpanded);

    // Update expand icon
    const expandBtnIcon = this.chatPanel.querySelector("#chat-expand-btn .icon");
    if (expandBtnIcon) {
      expandBtnIcon.style.setProperty("--icon-url", `url('${this.isExpanded ? this.ICONS.minimize : this.ICONS.expand}')`);
    }

    const sidebar = this.chatPanel.querySelector("#chat-sidebar");

    if (this.isExpanded) {
      sidebar.style.display = "flex";
      sidebar.classList.remove('is-hidden'); // Ensure visible when first expanding

      // Default to history if just expanding (unless forced)
      this.setSidebarMode(forceMode || 'history');
    } else {
      sidebar.style.display = "none";
    }
  }

  toggleSettings() {
    // If closed, open in settings mode
    if (!this.isExpanded) {
      this.toggleExpand('settings');
      return;
    }

    // If already open and in settings mode, close sidebar (toggle expand)
    if (this.activeSidebarMode === 'settings') {
      this.toggleExpand(); // Close
      return;
    }

    // If open in history mode, switch to settings
    this.setSidebarMode('settings');
  }

  setSidebarMode(mode) {
    this.activeSidebarMode = mode;

    const historyList = this.chatPanel.querySelector("#chat-history-list");
    const settingsPanel = this.chatPanel.querySelector("#chat-settings-panel");
    const headerTitle = this.chatPanel.querySelector("#sidebar-header h3");

    if (mode === 'settings') {
      if (historyList) historyList.style.display = "none";
      if (settingsPanel) settingsPanel.style.display = "block";
      if (headerTitle) headerTitle.textContent = "Settings";
    } else {
      if (historyList) historyList.style.display = "block";
      if (settingsPanel) settingsPanel.style.display = "none";
      if (headerTitle) headerTitle.textContent = "Chat History";

      if (this.onExpandHistory) this.onExpandHistory();
    }
  }

  renderHistoryList(sessions, activeSessionId, onSelect, onDelete, onRename) {
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
      const title = session.title || 'New Chat';

      item.innerHTML = `
            <div class="plugin-history-content">
                <div class="plugin-history-title" title="${this.escapeHtml(title)}">${this.escapeHtml(title)}</div>
                <div class="plugin-history-date">${date}</div>
            </div>
            <div class="plugin-history-actions">
                <button class="plugin-history-edit" title="Rename">
                     <span class="plugin-icon icon" style="--icon-url: url('${this.ICONS.edit}');" aria-hidden="true"></span>
                </button>
                <button class="plugin-history-delete" title="Delete">
                     <span class="plugin-icon icon" style="--icon-url: url('${this.ICONS.trash}');" aria-hidden="true"></span>
                </button>
            </div>
        `;

      // Select Helper
      const handleSelect = (e) => {
        // Don't select if we are interacting with actions
        if (e.target.closest('.plugin-history-actions') || e.target.closest('input')) return;
        onSelect(session.id);
      };

      item.addEventListener('click', handleSelect);

      // Edit Handler
      const editBtn = item.querySelector(".plugin-history-edit");
      const titleEl = item.querySelector(".plugin-history-title");

      editBtn.onclick = (e) => {
        e.stopPropagation();
        e.preventDefault();

        const currentTitle = session.title || 'New Chat';
        const input = document.createElement("input");
        input.type = "text";
        input.value = currentTitle;
        input.className = "plugin-history-rename-input";

        // Replace title with input
        titleEl.replaceWith(input);
        input.focus();

        // Handle save
        const save = () => {
          const newTitle = input.value.trim();
          if (newTitle && newTitle !== currentTitle) {
            onRename(session.id, newTitle);
          } else {
            // Revert if empty or unchanged
            input.replaceWith(titleEl);
          }
        };

        // Save on blur or enter
        input.onblur = save;
        input.onkeydown = (ev) => {
          if (ev.key === 'Enter') {
            ev.preventDefault(); // Prevent chat submit
            input.blur(); // Trigger save
          }
          if (ev.key === 'Escape') {
            ev.preventDefault();
            input.replaceWith(titleEl); // Cancel
          }
        };

        input.onclick = (ev) => ev.stopPropagation(); // Prevent select
      };

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
