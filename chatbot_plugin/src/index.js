// index.js
import { ChatbotUI } from "./ui.js";
import { ChatService } from "./chat.js";
import { AuthService } from "./auth.js";
import { CONFIG, initConfig } from "./config.js";
import "./styles.css";

(async function initChatbot() {
  await initConfig();
  const authBootstrap = await bootstrapAuth();
  if (!authBootstrap) {
    return;
  }

  const { token, context: tokenContext } = authBootstrap || {};

  const ui = new ChatbotUI();
  ui.onExpandHistory = () => {
    // Sort sessions by timestamp desc
    const sorted = [...sessions].sort((a, b) => b.timestamp - a.timestamp);
    ui.renderHistoryList(sorted, chatService.sessionId, switchSession, deleteSession, renameSession);
  };
  // Provide callbacks for chat history transfer to frontend
  ui.getCurrentSessionId = () => chatService.sessionId;
  ui.getSessionMessages = () => messages; // Return current session messages
  // Return all sessions with their messages for full history transfer
  ui.getAllSessions = () => {
    return sessions.map(session => {
      // For current session, use in-memory messages
      if (session.id === chatService.sessionId) {
        return {
          ...session,
          messages: messages.filter(m => !m.isTypingIndicator && !m.isTyping)
        };
      }
      // For other sessions, load from localStorage
      try {
        const storedMsgs = localStorage.getItem(CHAT_MESSAGES_PREFIX + session.id);
        if (storedMsgs) {
          return {
            ...session,
            messages: JSON.parse(storedMsgs)
          };
        }
      } catch (e) {
        console.warn('Failed to load messages for session:', session.id);
      }
      return { ...session, messages: [] };
    }).filter(s => s.messages && s.messages.length > 0); // Only include sessions with messages
  };
  // After transfer to frontend, keep localStorage intact so users can continue
  // their chat when they return to the plugin
  ui.onTransferComplete = () => {
    console.log('Transfer successful - preserving plugin localStorage for session continuity');
    // Do NOT clear localStorage - users should be able to continue their chat
    // when they close the extended frontend and return to the plugin
  };
  ui.init();

  const chatService = new ChatService();
  if (tokenContext) {
    chatService.setTokenContext(tokenContext);
  }
  if (token) {
    chatService.token = token;
  }

  const messages = [];
  let typingInterval = null;

  // Wait for DOM to be ready before accessing elements
  let chatBox, chatEmpty, input, sendBtn, stopBtn;
  let inFlight = false;
  let abortController = null;
  let currentTypingFinish = null;
  let currentTypingMessage = null; // Store reference to current typing message
  let currentTypingFullText = null; // Store full text for current typing message
  let currentRequestId = null; // Track current request to prevent old responses from updating UI
  let originalSendBtnHTML = null; // Store original send button HTML
  let userMessageCount = 0; // Track how many user messages have been sent in this session
  let currentSessionId = null; // Track current session ID
  let userScrolledDuringStream = false; // Track if user manually scrolled during streaming

  // LocalStorage keys for chat history
  const CHAT_HISTORY_KEY = 'chatbot_chat_history';
  const CHAT_SESSION_KEY = 'chatbot_chat_session_id';
  const CHAT_SESSIONS_INDEX_KEY = 'chatbot_sessions_index';
  const CHAT_MESSAGES_PREFIX = 'chatbot_messages_';
  const VISITOR_ID_KEY = 'chatbot_visitor_id';

  // Generate or retrieve unique visitor ID for this browser
  function getVisitorId() {
    let visitorId = localStorage.getItem(VISITOR_ID_KEY);
    if (!visitorId) {
      // Generate a unique visitor ID
      visitorId = 'visitor_' + Date.now() + '_' + Math.random().toString(36).substring(2, 15);
      localStorage.setItem(VISITOR_ID_KEY, visitorId);
    }
    return visitorId;
  }

  const visitorId = getVisitorId();

  let sessions = []; // [{id, title, timestamp}]
  const downloadRegistry = {
    byName: new Map(),
    byId: new Map(),
    register(name, id, canonicalName) {
      if (!name || !id) return;
      const trimmedName = name.trim();
      const trimmedId = id.trim();
      if (!trimmedName || !trimmedId) return;
      this.byName.set(trimmedName.toLowerCase(), trimmedId);
      const canonical = canonicalName && canonicalName.trim() ? canonicalName.trim() : trimmedName;
      this.byId.set(trimmedId, canonical);
    },
    lookup(name) {
      if (!name) return null;
      const key = name.trim().toLowerCase();
      if (!key) return null;
      return this.byName.get(key) || null;
    },
    getDisplayName(id) {
      if (!id) return null;
      const key = id.trim();
      if (!key) return null;
      return this.byId.get(key) || null;
    }
  };

  function scrollChatToBottom(force = false) {
    if (chatBox) {
      // Don't auto-scroll if user has manually scrolled during streaming (unless forced)
      if (!force && userScrolledDuringStream && inFlight) {
        return;
      }
      chatBox.scrollTop = chatBox.scrollHeight;
    }
  }

  // Scroll so that the latest user question sits at the top of the chat area
  function scrollLastUserMessageToTop() {
    if (!chatBox) return;
    const userMessages = chatBox.querySelectorAll(".plugin-msg.msg.user, .msg.user");
    if (!userMessages || userMessages.length === 0) return;
    const lastUser = userMessages[userMessages.length - 1];
    if (!lastUser) return;

    // Position the last user message at the top of the scroll container
    const offsetTop = lastUser.offsetTop ?? 0;
    chatBox.scrollTop = offsetTop;
  }

  await new Promise(resolve => setTimeout(resolve, 100));

  chatBox = document.getElementById("chat-box");
  chatEmpty = document.getElementById("chat-empty");
  input = document.getElementById("chat-message");
  sendBtn = document.getElementById("chat-send");
  stopBtn = document.getElementById("chat-stop");

  // Store original send button HTML for restoration
  if (sendBtn) {
    originalSendBtnHTML = sendBtn.innerHTML;
    // Fallback if original HTML is empty or invalid
    if (!originalSendBtnHTML || originalSendBtnHTML.trim() === '') {
      originalSendBtnHTML = `<img src="${CONFIG.ui.iconsBaseUrl}/send.svg" alt="Send" class="plugin-icon icon"/>`;
    }
  }

  // Track user scroll during streaming to allow manual scrolling
  if (chatBox) {
    let isAutoScrolling = false;

    // Wrap scrollTop setter to detect programmatic scrolls
    // This is a workaround as there's no direct way to distinguish user scroll from programmatic scroll
    // We'll use a global helper to set scrollTop programmatically and temporarily disable user scroll detection

    chatBox.addEventListener('scroll', () => {
      // Only track user scrolls during active streaming
      if (inFlight && !isAutoScrolling) {
        // Check if user scrolled away from bottom
        const isNearBottom = chatBox.scrollHeight - chatBox.clientHeight - chatBox.scrollTop <= 50;
        if (!isNearBottom) {
          userScrolledDuringStream = true;
        }
      }
    }, { passive: true });

    // Helper to set scroll without triggering user scroll detection
    window.__chatboxAutoScroll = (value) => {
      isAutoScrolling = true;
      chatBox.scrollTop = value;
      // Reset after a brief delay to allow scroll event to process
      setTimeout(() => { isAutoScrolling = false; }, 50);
    };
  }

  // Try to load chat history from localStorage
  const historyLoaded = loadChatHistory();
  if (!historyLoaded) {
    initializeMessages();
  }

  // Initialize user message counter based on any restored history
  userMessageCount = messages.filter(m => m && m.user).length;

  // Fetch synced sessions from backend (async, will update UI if newer sessions found)
  // This allows loading sessions created in the extended plugin
  fetchSyncedSessions().then(synced => {
    if (synced) {
      console.log('Synced sessions loaded from backend');
      // Update UI with any newly loaded sessions
      renderMessages();
      userMessageCount = messages.filter(m => m && m.user).length;
    }
  }).catch(err => {
    console.warn('Could not fetch synced sessions:', err);
  });

  if (CONFIG?.ui) {
    const root = document.documentElement;
    const {
      primaryColor,
      secondaryColor,
      primaryGradientDegree,
      gradientDegree,
      headerTextColor,
      placeholderHighlightColor
    } = CONFIG.ui;

    const gradientRegex = /linear-gradient\(([^,]+),\s*([^,]+),\s*([^)]+)\)/i;

    let startColor = primaryColor || "";
    let endColor = secondaryColor || "";
    let angle = primaryGradientDegree || gradientDegree || "";

    const normalize = (value) => (typeof value === "string" ? value.trim() : value);
    startColor = normalize(startColor);
    endColor = normalize(endColor);
    angle = normalize(angle);

    const extractGradient = (value) => {
      if (typeof value !== "string") return null;
      const match = value.match(gradientRegex);
      if (!match) return null;
      return match.slice(1).map((part) => part.trim());
    };

    const parsedGradient = extractGradient(primaryColor) || extractGradient(secondaryColor);
    if (parsedGradient) {
      const [matchedAngle, matchedStart, matchedEnd] = parsedGradient;
      angle = angle || matchedAngle;
      startColor = startColor && !startColor.startsWith("linear-gradient")
        ? startColor
        : matchedStart;
      endColor = endColor && !endColor.startsWith("linear-gradient")
        ? endColor
        : matchedEnd;
    }

    if (!startColor && endColor) {
      startColor = endColor;
    }

    if (startColor && !endColor) {
      endColor = startColor;
    }

    if (!angle && startColor !== endColor) {
      angle = "135deg";
    }

    const gradientValue = startColor && endColor
      ? angle
        ? `linear-gradient(${angle}, ${startColor}, ${endColor})`
        : `linear-gradient(135deg, ${startColor}, ${endColor})`
      : startColor || endColor || "";

    if (angle) root.style.setProperty("--chat-primary-angle", angle);
    if (startColor) root.style.setProperty("--chat-primary-start", startColor);
    if (endColor) root.style.setProperty("--chat-primary-end", endColor);
    if (startColor) root.style.setProperty("--chat-primary-solid", startColor);
    if (gradientValue) root.style.setProperty("--chat-primary", gradientValue);

    const highlightGradient = placeholderHighlightColor || gradientValue;
    if (highlightGradient) {
      root.style.setProperty("--chat-placeholder-highlight", highlightGradient);
    }
    if (startColor) {
      root.style.setProperty("--chat-placeholder-highlight-solid", startColor);
    }

    if (headerTextColor) {
      root.style.setProperty("--chat-header-text", headerTextColor);
    }
  }

  async function bootstrapAuth() {
    try {
      const storedToken = AuthService.getStoredToken();
      if (storedToken) {
        AuthService.clearToken();
      }

      const storedContext = AuthService.getTokenContext?.();
      if (storedContext?.valid) {
        AuthService.clearTokenContext();
      }

      let pluginLookup = await AuthService.lookupPluginCredentials().catch(() => null);

      if (pluginLookup?.plugin_token) {
        AuthService.storeToken(pluginLookup.plugin_token);
      }

      if (pluginLookup?.plugin_token || pluginLookup?.is_active === true) {
        const context = {
          valid: true,
          collection_id: pluginLookup?.collection_id || null,
          user_id: pluginLookup?.user_id || null,
          username: pluginLookup?.username || null,
          website_id: pluginLookup?.website_id || null
        };
        AuthService.storeTokenContext?.(context);
        return { token: pluginLookup?.plugin_token || null, context };
      }

      const pluginToken = AuthService.getConfiguredPluginToken?.();
      if (pluginToken) {
        const pluginVerification = await AuthService.verifyToken(pluginToken);
        if (pluginVerification?.valid) {
          AuthService.storeToken(pluginToken);
          return { token: pluginToken, context: pluginVerification };
        }

        return null;
      }

      const creds = AuthService.getTestCredentials();
      if (!creds) {
        return null;
      }

      const auth = await AuthService.login(creds);
      const accessToken = auth?.access_token;
      if (!accessToken) {
        return null;
      }

      const verification = await AuthService.verifyToken(accessToken);
      if (!verification?.valid) {
        AuthService.clearToken();
        return null;
      }

      return { token: accessToken, context: verification };
    } catch (error) {
      return null;
    }
  }

  if (CONFIG.ui.logoUrl) {
    const headerLogo = document.querySelector('.header .logo');
    if (headerLogo && !headerLogo.querySelector('img.chat-global-logo')) {
      const img = document.createElement('img');
      img.src = CONFIG.ui.logoUrl;
      img.alt = CONFIG.ui.logoAlt || 'Logo';
      img.className = 'chat-global-logo';
      headerLogo.prepend(img);
    }
  }

  document.addEventListener("click", async (e) => {
    const downloadBtn = e.target.closest(".source-download");
    if (downloadBtn) {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
      await handleDownloadSource(
        downloadBtn.dataset.sourceRef,
        downloadBtn.dataset.sourceName,
        downloadBtn
      );
      return false;
    }

    const sendEl = e.target.closest("#chat-send");
    const stopEl = e.target.closest("#chat-stop");
    const newChatEl = e.target.closest("#new-chat-btn");

    if (sendEl) {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
      await handleSendMessage();
      return false;
    } else if (stopEl) {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
      handleStop();
      return false;
    } else if (newChatEl) {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
      // Prevent click if button is in cooldown (even though pointer-events should handle this)
      if (!ui.canTriggerNewChat()) {
        return false;
      }
      handleNewChat();
      return false;
    }
  }, true);

  // Guard against any host-page form submission triggered from within the plugin UI
  document.addEventListener("submit", (e) => {
    const panel = document.querySelector(".plugin-chat-panel");
    if (panel && e.target && panel.contains(e.target)) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, true);

  document.addEventListener("keydown", async (e) => {
    if (e.target.id === "chat-message" && e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
      await handleSendMessage();
      return false;
    }
  }, true);

  // Extra guard: older pages may listen to keypress instead of keydown
  document.addEventListener("keypress", (e) => {
    if (e.target && e.key === "Enter") {
      const panel = document.querySelector(".plugin-chat-panel");
      if (panel && panel.contains(e.target)) {
        e.preventDefault();
        e.stopPropagation();
      }
    }
  }, true);

  function showSendButton() {
    if (sendBtn && originalSendBtnHTML) {
      sendBtn.disabled = false;
      sendBtn.innerHTML = originalSendBtnHTML;
      sendBtn.style.display = "";
    }
    if (stopBtn) {
      stopBtn.style.display = "none";
    }
    // Input loader removed - no loader in input box
  }

  function showProcessingState() {
    if (sendBtn) {
      sendBtn.disabled = true;
      sendBtn.innerHTML = "⏳";
      sendBtn.style.display = "none";
    }
    if (stopBtn) {
      stopBtn.style.display = "inline-flex";
    }
    // Input loader removed - no loader in input box
  }

  async function handleSendMessage() {
    // Double-check that we're not already processing a message
    if (inFlight) {
      return;
    }

    const userMsg = input.value.trim();
    if (!userMsg) {
      return;
    }

    // Generate unique request ID for this request
    const requestId = Date.now() + Math.random();
    currentRequestId = requestId;

    // Set inFlight flag and disable UI elements
    inFlight = true;
    userScrolledDuringStream = false; // Reset scroll flag for new message
    abortController = new AbortController();

    // Capture the session ID where this request started
    const requestSessionId = chatService.sessionId;

    try {
      input.disabled = true;
      showProcessingState();

      addMessage({ user: true, text: userMsg, formatted: false });
      // Track how many user messages have been sent in this session
      userMessageCount += 1;

      // For the very first exchange, keep existing behavior (scroll to bottom).
      // From the second user message onwards, align the question at the top so
      // that the response renders just beneath it.
      if (userMessageCount <= 1) {
        scrollChatToBottom();
      } else {
        scrollLastUserMessageToTop();
      }
      input.value = "";
      input.dispatchEvent(new Event("input", { bubbles: true }));

      const typingIndicator = showTypingIndicator();
      if (userMessageCount <= 1) {
        scrollChatToBottom();
      }

      const reply = await chatService.sendMessage(userMsg, { signal: abortController.signal });

      console.log('[DEBUG] Reply received:', JSON.stringify(reply, null, 2));

      removeTypingIndicator(typingIndicator);
      input.disabled = false;
      if (stopBtn) stopBtn.style.display = "inline-flex";

      // Check again before typing the message
      if (currentRequestId !== requestId) {
        // We switched sessions! Save response to background session history.
        if (requestSessionId) {
          saveBackgroundResponse(requestSessionId, reply);
        }
        showSendButton();
        return;
      }

      await typeAssistantMessage(
        reply.text,
        reply.sources,
        requestId,
        Boolean(reply?.is_generic || reply?.generic),
        Boolean(reply?.is_followup)  // NEW: Pass follow-up flag
      ).then(() => {
        // Final check before updating context indicator
        if (currentRequestId === requestId) {
          ui.updateContextIndicator(chatService.getContextInfo());
          // Save chat history after assistant message is fully typed
          saveChatHistory();
        }
      });
    } catch (error) {
      // Always remove typing indicator if it was created
      if (typeof typingIndicator !== 'undefined' && typingIndicator) {
        removeTypingIndicator(typingIndicator);
      }

      // Check if this request is still valid or if it was aborted
      if (currentRequestId !== requestId || error?.name === 'AbortError') {
        // Reset state and UI but don't show error message
        showSendButton();
        if (input) input.disabled = false;
        inFlight = false;
        abortController = null;
        return;
      }

      // Re-enable input and send button on unexpected error
      input.disabled = false;
      showSendButton();

      addMessage({
        user: false,
        text: "Sorry, I encountered an error. Please try again.",
        formatted: false,
        isError: true
      });
    } finally {
      // Only reset if this is still the current request
      if (currentRequestId === requestId) {
        // Ensure send button is re-enabled even if there was an error
        showSendButton();
        inFlight = false;
        abortController = null;
      }
    }
  }

  function handleStop() {
    // Abort any ongoing API request
    if (abortController) {
      abortController.abort();
      abortController = null;
    }

    // Reset state flags
    inFlight = false;

    // Stop any typing animation
    if (typeof currentTypingFinish === 'function') {
      clearInterval(typingInterval);
      typingInterval = null;
      currentTypingFinish = null;
    } else {
      clearInterval(typingInterval);
      typingInterval = null;
    }

    // Finalize any messages that are still in typing state with full text
    if (currentTypingMessage && currentTypingFullText) {
      currentTypingMessage.text = currentTypingFullText;
      currentTypingMessage.isTyping = false;
      currentTypingMessage = null;
      currentTypingFullText = null;
    } else {
      // Fallback: find any typing messages and finalize with current text
      messages.forEach(msg => {
        if (msg.isTyping) {
          msg.isTyping = false;
        }
      });
    }

    // Remove any typing indicators (thinking spinner)
    const typingIndicators = messages.filter(msg => msg.isTypingIndicator);
    typingIndicators.forEach(indicator => {
      const index = messages.indexOf(indicator);
      if (index !== -1) {
        messages.splice(index, 1);
      }
    });

    // Invalidate current request ID after finalizing messages
    currentRequestId = null;

    renderMessages();

    // Re-enable UI elements
    if (input) {
      input.disabled = false;
    }
    showSendButton();

    // Scroll to bottom to show the finalized response
    if (chatBox) {
      scrollChatToBottom(true); // Force scroll
    }
  }

  async function handleNewChat(skipSave = false) {
    if (!ui.canTriggerNewChat()) return;
    ui.startNewChatCooldown();

    // Don't abort ongoing fetch requests - let them complete in background
    // The response will be saved via saveBackgroundResponse() when it completes
    // Just detach the controller so we can start a new one for the new session
    abortController = null;

    // Stop any typing animation
    if (typeof currentTypingFinish === 'function') {
      clearInterval(typingInterval);
      typingInterval = null;
      currentTypingFinish = null;
    } else {
      clearInterval(typingInterval);
      typingInterval = null;
    }

    // Finalize any streaming messages with full text before switching sessions
    if (currentTypingMessage && currentTypingFullText) {
      currentTypingMessage.text = currentTypingFullText;
      currentTypingMessage.isTyping = false;
      // Save the finalized message to chat history
      saveChatHistory();
    } else {
      // Fallback: finalize any typing messages with current text
      messages.forEach(msg => {
        if (msg.isTyping) {
          msg.isTyping = false;
        }
      });
      // Save any finalized messages
      if (messages.some(msg => msg.isTyping === false && !msg.user && msg.text)) {
        saveChatHistory();
      }
    }
    
    currentTypingMessage = null;
    currentTypingFullText = null;

    // Invalidate current request ID so old responses won't update THIS UI
    // but they'll still save to their original session via saveBackgroundResponse()
    currentRequestId = null;

    // Remove only typing indicators (thinking spinner), not typing messages
    const typingIndicators = messages.filter(msg => msg.isTypingIndicator);
    typingIndicators.forEach(indicator => {
      const index = messages.indexOf(indicator);
      if (index !== -1) {
        messages.splice(index, 1);
      }
    });

    // Reset UI state flags (background requests still tracked by their own requestId)
    inFlight = false;

    // Re-enable UI elements
    if (input) {
      input.disabled = false;
    }
    showSendButton();

    // Transfer current session to backend before clearing
    // Only transfer if there are user messages (skip if chat is empty)
    const hasUserMessages = messages.some(m => m.user);
    if (hasUserMessages && chatService.sessionId && CONFIG?.websiteUrl) {
      try {
        const allSessions = ui.getAllSessions?.() || [];
        const currentSessionId = chatService.sessionId;

        if (allSessions.length > 0) {
          const apiBase = (CONFIG.apiBase || '').replace(/\/+$/, '');
          const transferResponse = await fetch(`${apiBase}/plugins/transfer-sessions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              website_url: CONFIG.websiteUrl,
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
            console.log('Session transferred successfully before clearing');
          } else {
            console.warn('Could not transfer session, proceeding with clear');
          }
        }
      } catch (transferErr) {
        console.warn('Session transfer failed:', transferErr);
      }
    }

    // Clear context and messages (do NOT delete existing sessions)
    chatService.clearContext();
    currentSessionId = chatService.sessionId; // Update tracker

    // Start fresh
    messages.length = 0;
    initializeMessages();
    renderMessages();

    // Update history sidebar
    if (ui.onExpandHistory) {
      ui.onExpandHistory();
    }
  }

  // ... (addMessage, etc.)

  async function deleteSession(sessionId) {
    // Delete from backend first
    if (chatService.token && sessionId) {
      try {
        const apiBase = (CONFIG.apiBase || '').replace(/\/+$/, '');
        await fetch(`${apiBase}/chat/sessions/${sessionId}`, {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${chatService.token}`,
          },
        });
      } catch (error) {
        // Silently fail - session might not exist in backend yet
        console.warn('Failed to delete session from backend:', error);
      }
    }

    // Delete from localStorage
    sessions = sessions.filter(s => s.id !== sessionId);
    localStorage.setItem(CHAT_SESSIONS_INDEX_KEY, JSON.stringify(sessions));
    localStorage.removeItem(CHAT_MESSAGES_PREFIX + sessionId);

    if (chatService.sessionId === sessionId) {
      handleNewChat(true); // Skip saving the session we just deleted
    } else {
      if (ui.isExpanded && ui.onExpandHistory) ui.onExpandHistory();
    }
  }


  function addMessage(message) {
    // Ensure sources array preserves all fields from each source object
    const normalizeSources = (sources) => {
      if (!Array.isArray(sources)) return [];
      return sources.map(source => {
        if (!source || typeof source !== 'object') return null;
        // Preserve all source fields: file_name, file_id, chunk_indices, source_type, url
        return {
          file_name: source.file_name || null,
          file_id: source.file_id || null,
          chunk_indices: Array.isArray(source.chunk_indices) ? source.chunk_indices : null,
          source_type: source.source_type || 'file',
          url: source.url || null
        };
      }).filter(source => source !== null && source.file_name); // Filter out invalid sources
    };

    const storedMessage = {
      user: Boolean(message.user),
      text: message.text || "",
      formatted: Boolean(message.formatted),
      timestamp: message.timestamp || new Date().toISOString(),
      isError: Boolean(message.isError),
      isTyping: Boolean(message.isTyping),
      isTypingIndicator: Boolean(message.isTypingIndicator),
      isFollowup: Boolean(message.isFollowup),  // NEW: Track follow-up status
      sources: normalizeSources(message.sources)
    };
    messages.push(storedMessage);
    renderMessages();

    // Save to localStorage (only if not a typing indicator)
    if (!storedMessage.isTypingIndicator) {
      saveChatHistory();
    }

    return storedMessage;
  }

  function showTypingIndicator() {
    const indicator = addMessage({ user: false, text: "", formatted: false, isTypingIndicator: true });
    if (userMessageCount <= 1) {
      scrollChatToBottom();
    } else {
      scrollLastUserMessageToTop();
    }
    return indicator;
  }

  function removeTypingIndicator(messageRef) {
    const index = messages.indexOf(messageRef);
    if (index !== -1) {
      messages.splice(index, 1);
      renderMessages();
    }
  }

  // Maximum number of sources to surface in the UI
  const MAX_DISPLAY_SOURCES = 4;

  // Helper function to detect generic responses
  function isGenericResponse(text) {
    if (!text) return false;
    const normalized = text.trim();
    const genericPattern = /I apologize|I'm limited to providing information|not have any information|outside of my scope|I'm afraid I don't have enough information|I don't have access to information|I don't have any information about|I'm here to help with questions about your knowledge base documents|the provided context does not contain|does not contain any information|do not have enough details|without any relevant information|there are no sources that discuss|i do not have enough details to provide|my role is to assist based on the provided information|I do not have enough context|I have no relevant information|I don't have enough context|I do not have any relevant information|provide a meaningful response/i;
    return genericPattern.test(normalized);
  }

  function typeAssistantMessage(fullText, sources = [], requestId = null, isGenericFlag = false, isFollowup = false) {
    console.log('[DEBUG] typeAssistantMessage called with:', { fullText, isFollowup, isGenericFlag });
    return new Promise((resolve) => {
      // Check if this request is still valid
      if (requestId !== null && currentRequestId !== requestId) {
        resolve();
        return;
      }

      clearInterval(typingInterval);

      // Always strip existing "Sources:" section from the text to ensure no double rendering
      // or rendering when generic. Matches: "Sources:", "**Sources:**", "> Sources:", "- Sources:", etc.
      let enhancedText = fullText || "";
      enhancedText = enhancedText
        .replace(/\r?\n+[\s>*-]*\*{0,2}\s*Sources?\s*:?\s*\*{0,2}\s*[\s\S]*$/i, '')
        .replace(/\r?\n+Sources?\s*:[\s\S]*$/i, '')
        .trim();

      console.log('[DEBUG] enhancedText after processing:', enhancedText);

      // Follow-up messages don't show sources and use different styling
      // Generic messages also don't show sources
      const isGeneric = Boolean(isGenericFlag) || isGenericResponse(fullText);
      // Always preserve sources array with all fields, even for generic messages
      const preservedSources = Array.isArray(sources) ? sources : [];
      // Only use sources for display if message is not generic AND not a follow-up
      const displaySources = (isGeneric || isFollowup) ? [] : preservedSources;

      // Only append sources section if sources are provided and message is not generic/followup
      if (!isGeneric && !isFollowup && Array.isArray(displaySources) && displaySources.length > 0) {
        // Append fresh sources section
        enhancedText += "\n\nSources:\n";
        // Limit displayed sources to the first N to avoid overwhelming the UI
        displaySources.slice(0, MAX_DISPLAY_SOURCES).forEach(source => {
          if (source && source.file_name) {
            enhancedText += `- ${source.file_name}\n`;
          }
        });
      }

      // Check again before adding message
      if (requestId !== null && currentRequestId !== requestId) {
        resolve();
        return;
      }

      // Store preserved sources with all fields, even if not displayed
      // Mark as follow-up if applicable for styling purposes
      const typingMessage = addMessage({
        user: false,
        text: "",
        formatted: true,
        isTyping: true,
        sources: preservedSources,
        isFollowup: isFollowup  // NEW: Track follow-up status for styling
      });
      // Store reference to current typing message and full text for stop button handling
      currentTypingMessage = typingMessage;
      currentTypingFullText = enhancedText;
      if (userMessageCount <= 1) {
        scrollChatToBottom();
      } else {
        scrollLastUserMessageToTop();
      }
      let completed = false;

      const finishTyping = () => {
        if (completed) return;

        // Check if this request is still valid before finishing
        if (requestId !== null && currentRequestId !== requestId) {
          // Remove the typing message if request was cancelled
          const index = messages.indexOf(typingMessage);
          if (index !== -1) {
            messages.splice(index, 1);
            renderMessages();
          }
          resolve();
          return;
        }

        completed = true;
        typingMessage.text = enhancedText;
        typingMessage.isTyping = false;
        renderMessages();
        resolve();
        showSendButton();
        inFlight = false;
        abortController = null;
        currentTypingFinish = null;
        currentTypingMessage = null;
        currentTypingFullText = null;
        input.focus();
        if (chatBox) {
          if (userMessageCount <= 1) {
            chatBox.scrollTop = chatBox.scrollHeight;
          } else {
            scrollLastUserMessageToTop();
          }
        }
      };

      if (!enhancedText || document.hidden) {
        finishTyping();
        return;
      }

      let index = 0;
      typingInterval = setInterval(() => {
        // Check if request was cancelled
        if (requestId !== null && currentRequestId !== requestId) {
          clearInterval(typingInterval);
          typingInterval = null;
          finishTyping();
          return;
        }

        if (document.hidden) {
          clearInterval(typingInterval);
          typingInterval = null;
          finishTyping();
          return;
        }

        index += 1;
        typingMessage.text = enhancedText.slice(0, index);
        renderMessages();

        if (index >= enhancedText.length) {
          clearInterval(typingInterval);
          typingInterval = null;
          finishTyping();
        }
      }, 15);
      currentTypingFinish = finishTyping;
    });
  }

  // Save chat history to localStorage
  function saveChatHistory() {
    try {
      if (!chatService.sessionId) return;

      const normalizeSourcesForStorage = (sources) => {
        if (!Array.isArray(sources)) return [];
        return sources.map(source => {
          if (!source || typeof source !== 'object') return null;
          return {
            file_name: source.file_name || null,
            file_id: source.file_id || null,
            chunk_indices: Array.isArray(source.chunk_indices) ? source.chunk_indices : null,
            source_type: source.source_type || 'file',
            url: source.url || null
          };
        }).filter(source => source !== null && source.file_name);
      };

      const messagesToSave = messages
        .filter(msg => !msg.isTypingIndicator && !msg.isTyping)
        .map(msg => ({
          user: msg.user,
          text: msg.text,
          formatted: msg.formatted,
          timestamp: msg.timestamp,
          sources: normalizeSourcesForStorage(msg.sources || [])
        }));

      // Save current session messages
      localStorage.setItem(CHAT_MESSAGES_PREFIX + chatService.sessionId, JSON.stringify(messagesToSave));

      const firstUserMsg = messagesToSave.find(m => m.user);
      let title = "New Chat";
      if (firstUserMsg && firstUserMsg.text) {
        title = firstUserMsg.text.slice(0, 30) + (firstUserMsg.text.length > 30 ? "..." : "");
      }

      const now = Date.now();
      const existingIndex = sessions.findIndex(s => s.id === chatService.sessionId);
      const nextSession = {
        id: chatService.sessionId,
        timestamp: now,
        title: title
      };

      if (existingIndex >= 0) {
        sessions[existingIndex] = { ...sessions[existingIndex], ...nextSession };
      } else {
        sessions.push(nextSession);
      }

      sessions.sort((a, b) => b.timestamp - a.timestamp);

      localStorage.setItem(CHAT_SESSIONS_INDEX_KEY, JSON.stringify(sessions));
      chatService.restoreHistory(messagesToSave);

      if (ui.isExpanded && ui.onExpandHistory) {
        ui.onExpandHistory();
      }
    } catch (err) {
      console.error("Failed to save history", err);
    }
  }

  function saveBackgroundResponse(sessionId, reply) {
    try {
      if (!sessionId || !reply) return;

      const storedMsgsKey = CHAT_MESSAGES_PREFIX + sessionId;
      const storedMsgsStr = localStorage.getItem(storedMsgsKey);
      let msgs = storedMsgsStr ? JSON.parse(storedMsgsStr) : [];

      const normalizeSourcesForStorage = (sources) => {
        if (!Array.isArray(sources)) return [];
        return sources.map(source => {
          if (!source || typeof source !== 'object') return null;
          return {
            file_name: source.file_name || null,
            file_id: source.file_id || null,
            chunk_indices: Array.isArray(source.chunk_indices) ? source.chunk_indices : null,
            source_type: source.source_type || 'file',
            url: source.url || null
          };
        }).filter(source => source !== null && source.file_name);
      };

      const assistantMsg = {
        user: false,
        text: reply.text || "",
        formatted: true,
        timestamp: new Date().toISOString(),
        sources: normalizeSourcesForStorage(reply.sources || []),
        isFollowup: Boolean(reply.is_followup),
        isError: false,
        isTyping: false,
        isTypingIndicator: false
      };

      msgs.push(assistantMsg);
      localStorage.setItem(storedMsgsKey, JSON.stringify(msgs));

      const sessionIndex = sessions.findIndex(s => s.id === sessionId);
      if (sessionIndex >= 0) {
        sessions[sessionIndex].timestamp = Date.now();
        localStorage.setItem(CHAT_SESSIONS_INDEX_KEY, JSON.stringify(sessions));
      }

      // If we are somehow back on this session (race condition?), reload history
      if (chatService.sessionId === sessionId) {
        chatService.restoreHistory(msgs);
        // If UI is showing this session, maybe we should render? 
        // But safely we assume UI is elsewhere.
      }

    } catch (err) {
      console.error("Failed to save background response", err);
    }
  }

  // Load chat history from localStorage
  function loadChatHistory() {
    try {
      const storedIndex = localStorage.getItem(CHAT_SESSIONS_INDEX_KEY);
      if (storedIndex) {
        sessions = JSON.parse(storedIndex);
      }

      if (sessions.length === 0) {
        const legacyMsgs = localStorage.getItem(CHAT_HISTORY_KEY);
        if (legacyMsgs) {
          const legacySessionId = localStorage.getItem(CHAT_SESSION_KEY) || Date.now().toString();
          sessions.push({
            id: legacySessionId,
            timestamp: Date.now(),
            title: "Previous Chat"
          });
          localStorage.setItem(CHAT_MESSAGES_PREFIX + legacySessionId, legacyMsgs);
          localStorage.setItem(CHAT_SESSIONS_INDEX_KEY, JSON.stringify(sessions));
        }
      }

      if (sessions.length > 0) {
        const lastSession = sessions.sort((a, b) => b.timestamp - a.timestamp)[0];
        switchSession(lastSession.id);
        return true;
      }
      return false;
    } catch (err) {
      console.error("Failed to load history", err);
      return false;
    }
  }

  // Fetch synced sessions from backend (sessions created in extended plugin)
  async function fetchSyncedSessions() {
    try {
      if (!CONFIG?.websiteUrl || !CONFIG?.apiBase) {
        console.log('Missing config for synced sessions fetch');
        return false;
      }

      const apiBase = (CONFIG.apiBase || '').replace(/\/+$/, '');
      const websiteUrl = encodeURIComponent(CONFIG.websiteUrl);
      const vid = encodeURIComponent(visitorId);

      const response = await fetch(`${apiBase}/plugins/sync-sessions?website_url=${websiteUrl}&visitor_id=${vid}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        console.warn('Failed to fetch synced sessions:', response.status);
        return false;
      }

      const data = await response.json();

      if (!data.sessions || data.sessions.length === 0) {
        console.log('No synced sessions from backend');
        return false;
      }

      console.log(`Found ${data.sessions.length} synced sessions from backend`);

      // Merge synced sessions with local sessions
      let localUpdated = false;
      const existingIds = new Set(sessions.map(s => s.id));

      for (const syncedSession of data.sessions) {
        // Check if this session exists locally
        const localMsgsStr = localStorage.getItem(CHAT_MESSAGES_PREFIX + syncedSession.session_id);
        const syncedTimestamp = syncedSession.timestamp || Date.now();

        // Compare timestamps to determine which is newer
        let shouldUseBackend = false;

        if (!localMsgsStr) {
          // Session doesn't exist locally - use backend version
          shouldUseBackend = true;
        } else {
          // Session exists - check which is newer
          const existingSession = sessions.find(s => s.id === syncedSession.session_id);
          if (existingSession && syncedTimestamp > existingSession.timestamp) {
            shouldUseBackend = true;
          }
        }

        if (shouldUseBackend && syncedSession.messages && syncedSession.messages.length > 0) {
          console.log(`Importing synced session: ${syncedSession.session_id}`);

          // Convert backend message format to plugin format
          const pluginMessages = syncedSession.messages.map(msg => ({
            user: msg.user === true,
            text: msg.text || '',
            formatted: msg.formatted !== false,
            timestamp: msg.timestamp || new Date().toISOString(),
            sources: msg.sources || [],
            isFollowup: msg.isFollowup || false,
          }));

          // Save messages to localStorage
          localStorage.setItem(
            CHAT_MESSAGES_PREFIX + syncedSession.session_id,
            JSON.stringify(pluginMessages)
          );

          // Update sessions index
          if (!existingIds.has(syncedSession.session_id)) {
            sessions.push({
              id: syncedSession.session_id,
              title: syncedSession.title || 'New Chat',
              timestamp: syncedTimestamp,
            });
            existingIds.add(syncedSession.session_id);
          } else {
            // Update existing session timestamp
            const idx = sessions.findIndex(s => s.id === syncedSession.session_id);
            if (idx >= 0) {
              sessions[idx].timestamp = syncedTimestamp;
              sessions[idx].title = syncedSession.title || sessions[idx].title;
            }
          }
          localUpdated = true;
        }
      }

      if (localUpdated) {
        // Save updated sessions index
        sessions.sort((a, b) => b.timestamp - a.timestamp);
        localStorage.setItem(CHAT_SESSIONS_INDEX_KEY, JSON.stringify(sessions));

        // Load the most recent session (or the current_session_id if specified)
        const targetSessionId = data.current_session_id || sessions[0]?.id;
        if (targetSessionId) {
          switchSession(targetSessionId);
        }
        return true;
      }

      return false;
    } catch (err) {
      console.error('Failed to fetch synced sessions:', err);
      return false;
    }
  }

  function switchSession(sessionId) {
    if (currentSessionId === sessionId && messages.length > 0) return;

    // Don't abort ongoing requests - let them complete in background
    // The response will be saved to the original session via saveBackgroundResponse()
    // when handleSendMessage() detects currentRequestId has changed
    if (abortController) {
      abortController = null;
    }

    // Stop any typing animation
    if (typeof currentTypingFinish === 'function') {
      clearInterval(typingInterval);
      typingInterval = null;
      currentTypingFinish = null;
    } else {
      clearInterval(typingInterval);
      typingInterval = null;
    }

    // Finalize any streaming messages with full text before switching sessions
    if (currentTypingMessage && currentTypingFullText) {
      currentTypingMessage.text = currentTypingFullText;
      currentTypingMessage.isTyping = false;
      // Save the finalized message to chat history before switching
      saveChatHistory();
    } else {
      // Fallback: finalize any typing messages with current text
      messages.forEach(msg => {
        if (msg.isTyping) {
          msg.isTyping = false;
        }
      });
      // Save any finalized messages before switching
      if (messages.some(msg => msg.isTyping === false && !msg.user && msg.text)) {
        saveChatHistory();
      }
    }
    
    currentTypingMessage = null;
    currentTypingFullText = null;

    // Remove typing indicators (the "thinking..." bubbles)
    const typingIndicators = messages.filter(msg => msg.isTypingIndicator);
    typingIndicators.forEach(indicator => {
      const index = messages.indexOf(indicator);
      if (index !== -1) {
        messages.splice(index, 1);
      }
    });

    // Reset state flags
    inFlight = false;
    currentRequestId = null;

    // Re-enable UI elements
    if (input) {
      input.disabled = false;
    }
    showSendButton();

    const storedMsgs = localStorage.getItem(CHAT_MESSAGES_PREFIX + sessionId);
    if (!storedMsgs) return;

    try {
      const parsed = JSON.parse(storedMsgs);

      chatService.clearContext();
      chatService.sessionId = sessionId;
      currentSessionId = sessionId;

      messages.length = 0;

      const normalizeSourcesFromStorage = (sources) => {
        if (!Array.isArray(sources)) return [];
        return sources.map(source => {
          if (!source || typeof source !== 'object') return null;
          return {
            file_name: source.file_name || null,
            file_id: source.file_id || null,
            chunk_indices: Array.isArray(source.chunk_indices) ? source.chunk_indices : null,
            source_type: source.source_type || 'file',
            url: source.url || null
          };
        }).filter(source => source !== null && source.file_name);
      };

      parsed.forEach(msg => {
        messages.push({
          user: Boolean(msg.user),
          text: msg.text || '',
          formatted: Boolean(msg.formatted),
          timestamp: msg.timestamp || new Date().toISOString(),
          sources: normalizeSourcesFromStorage(msg.sources || [])
        });
      });

      chatService.restoreHistory(parsed);

      // Defer rendering to ensure all functions are initialized
      // This prevents "Cannot access before initialization" errors in minified code
      setTimeout(() => {
        if (typeof renderMessages === 'function') {
          renderMessages();
        }
        if (ui && typeof ui.updateContextIndicator === 'function') {
          ui.updateContextIndicator(chatService.getContextInfo());
        }
        if (ui && ui.isExpanded && ui.onExpandHistory) ui.onExpandHistory();
        scrollChatToBottom();
      }, 0);
    } catch (e) {
      console.error("Failed to switch session", e);
    }
  }



  function renameSession(sessionId, newTitle) {
    const session = sessions.find(s => s.id === sessionId);
    if (session) {
      session.title = newTitle;
      localStorage.setItem(CHAT_SESSIONS_INDEX_KEY, JSON.stringify(sessions));
      if (ui.isExpanded && ui.onExpandHistory) ui.onExpandHistory();
    }
  }

  function clearChatHistory() {
    try {
      localStorage.removeItem(CHAT_HISTORY_KEY);
      localStorage.removeItem(CHAT_SESSION_KEY);
    } catch (err) { }
  }

  function initializeMessages() {
    messages.length = 0;
    renderMessages();
  }

  function renderMessages() {
    if (!chatBox) return;
    const wasNearBottom = chatBox.scrollHeight - chatBox.clientHeight - chatBox.scrollTop <= 32;
    const previousScrollTop = chatBox.scrollTop;

    const html = messages.map(renderMessageHtml).join("");
    chatBox.innerHTML = html;

    // During streaming, respect user's manual scroll - don't auto-scroll if they scrolled up
    if (userScrolledDuringStream && inFlight) {
      chatBox.scrollTop = previousScrollTop;
    } else if (wasNearBottom) {
      chatBox.scrollTop = chatBox.scrollHeight;
    } else {
      chatBox.scrollTop = previousScrollTop;
    }

    if (chatEmpty) chatEmpty.style.display = messages.length ? "none" : "flex";
  }

  function renderMessageHtml(message) {
    if (message.user) {
      return `<div class="plugin-msg msg user">
        <div class="plugin-msg-content msg-content">${escapeHtml(message.text)}</div>
      </div>`;
    }
    if (message.isTypingIndicator) {
      const logoUrl = CONFIG.ui.placeholderLogoUrl || CONFIG.ui.logoUrl || `${CONFIG.ui.iconsBaseUrl}/logo1.svg`;
      return `<div class="plugin-msg msg bot typing thinking-indicator">
        <div class="plugin-thinking-content thinking-content">
          <div class="plugin-thinking-inner thinking-inner">
            <img src="${logoUrl}" alt="Leto logo" class="plugin-thinking-logo thinking-logo" />
            <div class="plugin-thinking-status thinking-status">
              <svg class="plugin-thinking-spinner thinking-spinner" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg>
              <span class="plugin-thinking-text thinking-text">Leto is thinking...</span>
            </div>
          </div>
        </div>
      </div>`;
    }
    const classes = ["msg", "bot"];
    if (message.isError) classes.push("error");
    if (message.isTyping) classes.push("typing-text");
    if (message.isFollowup) classes.push("followup-message");  // NEW: Add followup styling class
    const content = renderAssistantContent(message);
    return `<div class="plugin-msg ${classes.join(" ")}">${content}</div>`;
  }

  // Strip incomplete markdown patterns from streaming text
  function stripIncompleteMarkdown(text) {
    if (!text) return text;

    // Fix: Only strip ** if it is an unmatched opening tag (odd count)
    // This prevents stripping the closing ** of a completed bold section,
    // which caused the raw "**" to be visible for a split second (or longer)
    // before the renderer could detect the pair.

    const doubleStarCount = (text.match(/\*\*/g) || []).length;
    if (doubleStarCount % 2 !== 0) {
      const lastIndex = text.lastIndexOf("**");
      if (lastIndex !== -1) {
        return text.substring(0, lastIndex) + text.substring(lastIndex + 2);
      }
    }

    return text;
  }

  function renderAssistantContent(message) {
    if (message.formatted) {
      // Strip incomplete markdown patterns during typing animation
      const textToRender = message.isTyping ? stripIncompleteMarkdown(message.text) : message.text;
      const html = renderAssistantText(textToRender, message.sources || []);
      return `<div class="plugin-msg-content msg-content text-sm"><div class="plugin-prose prose prose-sm max-w-none">${html}</div></div>`;
    }
    return `<div class="plugin-msg-content msg-content">${escapeHtml(message.text)}</div>`;
  }

  // --- DOWNLOAD HANDLER ---
  async function handleDownloadSource(sourceRef, downloadName, triggerEl) {
    if (!sourceRef && !downloadName) return;

    const button = triggerEl;
    const initialLabel = button?.textContent;

    try {
      if (button) {
        button.disabled = true;
        button.classList.add("is-loading");
        button.textContent = "Downloading…";
      }

      await chatService.ensureToken();
      const token = chatService.token;
      if (!token) throw new Error("Missing authentication token");

      const headers = { Authorization: `Bearer ${token}` };
      const normalizedName = (downloadName || "").trim();
      const ref = (sourceRef || "").trim();
      const base = (CONFIG.apiBase || "").replace(/\/+$/, "");
      const datasetId = (button?.dataset?.sourceId || "").trim();
      const registryId = downloadRegistry.lookup(normalizedName);
      const effectiveRef = datasetId || registryId || ref || normalizedName;

      if (!effectiveRef) {
        throw new Error("Missing file reference");
      }

      const encodedRef = encodeURIComponent(effectiveRef);
      const downloadUrl = `${base}/files/download/${encodedRef}`;

      const response = await fetch(downloadUrl, { headers });
      if (!response.ok) {
        throw new Error(`Download failed (${response.status})`);
      }

      const blob = await response.blob();
      const filename = normalizedName || ref || "source";
      triggerBrowserDownload(blob, filename);
      return;
    } catch (err) {
      if (button) {
        button.classList.add("download-error");
        button.textContent = initialLabel || "Download failed";
      }
      alert("Unable to download this source. Please try again later.");
    } finally {
      if (button) {
        button.disabled = false;
        button.classList.remove("is-loading");
        if (initialLabel) button.textContent = initialLabel;
      }
    }
  }

  function triggerBrowserDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename || "download";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  function extractDownloadName(label) {
    const trimmed = (label || "").trim();
    const match = trimmed.match(/\(([^)]+)\)\s*$/);
    if (match) {
      const base = trimmed.replace(match[0], "").trim();
      return { displayLabel: base || match[1], downloadName: match[1] };
    }
    return { displayLabel: trimmed, downloadName: trimmed };
  }

  function escapeAttribute(value) {
    return `${value ?? ""}`.replace(/[&"'<>]/g, (char) => {
      switch (char) {
        case "&": return "&amp;";
        case '"': return "&quot;";
        case "'": return "&#39;";
        case "<": return "&lt;";
        case ">": return "&gt;";
        default: return "";
      }
    });
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text ?? "";
    return div.innerHTML;
  }

  // --- MAIN TEXT RENDERER ---
  // --- MAIN TEXT RENDERER ---
  function renderAssistantText(text, sources = []) {
    if (!text) return "";

    // Normalize sources to ensure all fields are present
    const normalizedSources = Array.isArray(sources) ? sources.map(source => {
      if (!source || typeof source !== 'object') return null;
      return {
        file_name: source.file_name || null,
        file_id: source.file_id || null,
        chunk_indices: Array.isArray(source.chunk_indices) ? source.chunk_indices : null,
        source_type: source.source_type || 'file',
        url: source.url || null
      };
    }).filter(source => source !== null && source.file_name) : [];

    // Normalize label like "Source 4: Leave_Policy.pdf" to match file_name
    function normalizeFileName(label) {
      return label.replace(/^Source\s*\d+:\s*/, "").trim();
    }

    // Build map of file_name => file_id from the API response
    // API returns: sources: [{ file_name: "...", file_id: "...", chunk_indices: [...], source_type: "...", url: "..." }]
    const fileNameToIdMap = {};
    const sourceMetadataMap = {}; // Store source_type and url for each source
    const storeFileMapping = (name, id, canonicalName, metadata = {}) => {
      if (!name) return;
      const trimmedName = name.trim();
      if (!trimmedName) return;
      const trimmedId = id ? id.trim() : null;
      if (trimmedId) {
        fileNameToIdMap[trimmedName] = trimmedId;
        fileNameToIdMap[trimmedName.toLowerCase()] = trimmedId;
        downloadRegistry.register(trimmedName, trimmedId, canonicalName);
      }
      // Store metadata (source_type, url) by name
      if (!sourceMetadataMap[trimmedName.toLowerCase()]) {
        sourceMetadataMap[trimmedName.toLowerCase()] = metadata;
      }
    };
    const lookupFileId = (name) => {
      if (!name) return null;
      const trimmedName = name.trim();
      if (!trimmedName) return null;
      return fileNameToIdMap[trimmedName] || fileNameToIdMap[trimmedName.toLowerCase()] || null;
    };
    const lookupSourceMetadata = (name) => {
      if (!name) return null;
      const trimmedName = name.trim();
      if (!trimmedName) return null;
      return sourceMetadataMap[trimmedName.toLowerCase()] || null;
    };

    // Process normalized sources
    if (Array.isArray(normalizedSources)) {
      normalizedSources.forEach(source => {
        if (source && source.file_name) {
          const fileName = source.file_name.trim();
          const fileId = source.file_id ? source.file_id.trim() : null;
          if (!fileName) return;
          const metadata = {
            source_type: source.source_type || 'file',
            url: source.url || null,
            file_id: fileId,
            chunk_indices: source.chunk_indices || null
          };
          storeFileMapping(fileName, fileId, fileName, metadata);
          const normalizedFileName = normalizeFileName(fileName);
          if (normalizedFileName && normalizedFileName !== fileName) {
            storeFileMapping(normalizedFileName, fileId, fileName, metadata);
          }
        }
      });
    }

    const linkTokens = [];
    const tableTokens = [];

    // Process markdown links [Label](ref)
    let processed = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, label, ref) => {
      const extraction = extractDownloadName(label);
      const normalized = normalizeFileName(extraction.downloadName);
      const fileId = lookupFileId(normalized);
      const metadata = lookupSourceMetadata(normalized);
      const fallbackRef = (ref || "").trim();
      const fileRef = fileId || fallbackRef;
      const canonicalName = fileId ? downloadRegistry.getDisplayName(fileId) : null;
      const resolvedName = canonicalName || normalized || extraction.displayLabel || fallbackRef;
      const displayName = resolvedName || "";
      const dataRef = escapeAttribute(fileRef);
      const dataName = escapeAttribute(displayName);
      const buttonLabel = escapeHtml(displayName || extraction.displayLabel);
      const idAttribute = fileId ? ` data-source-id="${escapeAttribute(fileId)}"` : "";

      // Check if this is a web crawl source
      const isWebCrawl = (metadata && (metadata.source_type === 'web_crawl' || metadata.url)) ||
        fallbackRef.startsWith('http://') || fallbackRef.startsWith('https://');

      if (isWebCrawl) {
        // Web crawl source - render as anchor tag that opens in new tab
        const url = (metadata && metadata.url) || fallbackRef;
        const href = url.startsWith('http') ? url : `https://${url}`;
        const token = `__SOURCE_LINK_${linkTokens.length}__`;
        linkTokens.push(`<a href="${escapeAttribute(href)}" target="_blank" rel="noopener noreferrer" class="source-link"><span class="source-link-text">${buttonLabel}</span><svg class="source-link-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg></a>`);
        return token;
      } else {
        // File source - render as download button
        const token = `__SOURCE_LINK_${linkTokens.length}__`;
        linkTokens.push(`<button type="button" class="source-download"${idAttribute} data-source-ref="${dataRef}" data-source-name="${dataName}">${buttonLabel}</button>`);
        return token;
      }
    });

    const plainSourceTokens = [];
    const lines = processed.split(/\n/);
    let inSourcesSection = false;
    let collectedSourceTokens = [];
    let sourcesSectionToken = null;

    for (let i = 0; i < lines.length; i += 1) {
      const trimmed = lines[i].trim();

      if (/^Sources?:/i.test(trimmed)) {
        inSourcesSection = true;
        sourcesSectionToken = `__SOURCES_SECTION_BLOCK__`;
        lines[i] = sourcesSectionToken;
        continue;
      }

      if (!inSourcesSection) continue;
      if (!trimmed) {
        lines[i] = "";
        continue;
      }

      // Check if it's a bullet point or if it is a token line (e.g. from a link)
      const isBullet = /^[-•]/.test(trimmed);
      const isTokenLine = trimmed.includes("__SOURCE_LINK_");

      if (isBullet || isTokenLine) {
        // If it's a pre-tokenized link
        const linkMatch = trimmed.match(/__SOURCE_LINK_\d+__/);
        if (linkMatch) {
          collectedSourceTokens.push(linkMatch[0]);
          lines[i] = "";
          continue;
        }

        // Plain source parsing
        let match = lines[i].match(/^(\s*[-•]?\s*)(.+?\.[A-Za-z0-9]{2,12})(\s*)$/);
        if (!match) {
          match = lines[i].match(/^(\s*[-•]?\s*)(.+?)(\s*)$/);
        }

        if (match) {
          const rawName = match[2].trim();
          const normalized = normalizeFileName(rawName) || rawName;
          const fileId = lookupFileId(normalized);
          const metadata = lookupSourceMetadata(normalized);
          const canonicalName = fileId ? downloadRegistry.getDisplayName(fileId) : null;
          const displayName = canonicalName || rawName || normalized;
          const fileRef = fileId || normalized || rawName;
          const token = `__PLAIN_SOURCE_${plainSourceTokens.length}__`;

          const isWebCrawl = metadata && (metadata.source_type === 'web_crawl' || metadata.url);
          plainSourceTokens.push({ token, fileRef, displayName, fileId, isWebCrawl, url: metadata?.url });
          collectedSourceTokens.push(token);
          lines[i] = "";
          continue;
        }
      }

      // If we reach here, it's not a source line
      inSourcesSection = false;
    }

    processed = lines.join("\n");

    // Tables
    processed = processed.replace(/(^|\n)((?:\s*\|[^\n]*\n){2,})/g, (m, lead, block) => {
      const rows = block.trim().split(/\n/).map(r => r.trim());
      if (rows.length < 2) return m;
      const header = rows[0];
      const divider = rows[1];
      if (!/^\|?\s*:?[-\s|:]+:?\s*\|?$/.test(divider)) return m;
      const bodyRows = rows.slice(2);
      const parseRow = (row) => row.replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
      const ths = parseRow(header).map(h => `<th>${escapeHtml(h)}</th>`).join('');
      const trs = bodyRows.map(r => `<tr>${parseRow(r).map(c => `<td>${escapeHtml(c)}</td>`).join('')}</tr>`).join('');
      const html = `<table class="plugin-table chat-table"><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
      const token = `__TABLE_BLOCK_${tableTokens.length}__`;
      tableTokens.push(html);
      return `${lead}${token}\n`;
    });

    processed = processed.replace(/<table[\s\S]*?<\/table>/gi, (tbl) => {
      const unsafeTag = /<(?!\/?(?:table|thead|tbody|tr|th|td)(\b|>))/i.test(tbl);
      if (unsafeTag) return escapeHtml(tbl);
      const token = `__TABLE_BLOCK_${tableTokens.length}__`;
      tableTokens.push(tbl);
      return token;
    });

    let safe = escapeHtml(processed);
    safe = safe.replace(/\r\n/g, "\n");

    // Inject Sources Section
    if (sourcesSectionToken) {
      let sourcesHtml = `<div class="sources-section-wrapper"><div class="source-section-title">Sources:</div>`;
      if (collectedSourceTokens.length > 0) {
        const limitedTokens = collectedSourceTokens.slice(0, MAX_DISPLAY_SOURCES);
        const overflowCount = Math.max(collectedSourceTokens.length - MAX_DISPLAY_SOURCES, 0);
        sourcesHtml += `<div class="sources-container">${limitedTokens.join('')}`;
        if (overflowCount > 0) {
          sourcesHtml += `<span class="sources-overflow">+${overflowCount} more</span>`;
        }
        sourcesHtml += `</div>`;
      }
      sourcesHtml += `</div>`;
      // Replace the token and remove any trailing newlines/whitespace after it
      safe = safe.replace(new RegExp(sourcesSectionToken + '\\s*', 'g'), sourcesHtml);
    }

    linkTokens.forEach((html, index) => { safe = safe.replace(`__SOURCE_LINK_${index}__`, html); });
    plainSourceTokens.forEach(({ token, fileRef, displayName, fileId, isWebCrawl, url }) => {
      if (isWebCrawl && url) {
        // Web crawl source - render as anchor tag that opens in new tab
        const href = url.startsWith('http') ? url : `https://${url}`;
        const linkHtml = `<a href="${escapeAttribute(href)}" target="_blank" rel="noopener noreferrer" class="source-link"><span class="source-link-text">${escapeHtml(displayName)}</span><svg class="source-link-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg></a>`;
        safe = safe.replace(token, linkHtml);
      } else {
        // File source - render as download button
        const dataRef = escapeAttribute(fileRef);
        const dataName = escapeAttribute(displayName);
        const idAttribute = fileId ? ` data-source-id="${escapeAttribute(fileId)}"` : "";
        const buttonHtml = `<button type="button" class="source-download"${idAttribute} data-source-ref="${dataRef}" data-source-name="${dataName}">${escapeHtml(displayName)}</button>`;
        safe = safe.replace(token, buttonHtml);
      }
    });

    safe = safe.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    // safe = safe.replace(/(^|\n)Sources?:/g, (match) => `<div class="source-section-title">${match.trim()}</div>`); // Already handled by block token
    safe = safe.replace(/^\s*-\s+/gm, "• ");
    // Stop replacing newlines with <br/> to avoid huge gaps with pre-wrap
    // safe = safe.replace(/\n\d+\./g, "<br/>$&");
    // safe = safe.replace(/\n-\s*/g, "<br/>• ");
    // safe = safe.replace(/\n/g, "<br/>");

    tableTokens.forEach((html, index) => {
      const token = `__TABLE_BLOCK_${index}__`;
      safe = safe.replace(token, html);
    });

    return safe;
  }


})();
