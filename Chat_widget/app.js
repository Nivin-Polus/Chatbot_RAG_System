/**
 * Chat Widget Application
 * 
 * This standalone chat widget connects to the backend via a unique widget token
 * extracted from the URL path. It provides a full-featured chat interface with
 * session management, chat history, and theme switching.
 */

// ===== Configuration =====
const CONFIG = {
    // Will be populated from widget lookup response
    apiBaseUrl: '',
    accessToken: '',
    collectionId: '',
    collectionName: '',
    userId: '',
    username: '',
    websiteId: '',
};

// ===== State =====
const state = {
    sessionId: null,
    sessions: [],
    messages: [],
    isLoading: false,
    isStreaming: false,
    sidebarOpen: true,
    typingInterval: null,
};

// ===== DOM Elements =====
let elements = {};

// ===== Initialize App =====
document.addEventListener('DOMContentLoaded', init);

async function init() {
    cacheElements();
    setupEventListeners();
    loadTheme();

    // Extract widget token from URL
    const widgetToken = getWidgetToken();
    if (!widgetToken) {
        showError('Invalid widget URL. Please check the link and try again.');
        return;
    }

    // Lookup widget configuration
    const success = await lookupWidget(widgetToken);
    if (!success) {
        return;
    }

    // Load saved sessions and show interface
    loadSessions();
    showChatInterface();

    // Start with a new session if none exists
    if (!state.sessionId) {
        startNewSession();
    }
}

function cacheElements() {
    elements = {
        loadingScreen: document.getElementById('loading-screen'),
        errorScreen: document.getElementById('error-screen'),
        errorMessage: document.getElementById('error-message'),
        chatInterface: document.getElementById('chat-interface'),
        sidebar: document.getElementById('sidebar'),
        toggleSidebarBtn: document.getElementById('toggle-sidebar'),
        mobileMenuBtn: document.getElementById('mobile-menu-btn'),
        newChatBtn: document.getElementById('new-chat-btn'),
        historyList: document.getElementById('history-list'),
        collectionName: document.getElementById('collection-name'),
        messagesContainer: document.getElementById('messages-container'),
        messagesList: document.getElementById('messages-list'),
        messagesEnd: document.getElementById('messages-end'),
        chatForm: document.getElementById('chat-form'),
        messageInput: document.getElementById('message-input'),
        sendBtn: document.getElementById('send-btn'),
        themeToggle: document.getElementById('theme-toggle'),
    };
}

function setupEventListeners() {
    // Sidebar toggle
    elements.toggleSidebarBtn.addEventListener('click', toggleSidebar);
    elements.mobileMenuBtn.addEventListener('click', toggleMobileSidebar);

    // New chat
    elements.newChatBtn.addEventListener('click', startNewSession);

    // Chat form
    elements.chatForm.addEventListener('submit', handleSubmit);
    elements.messageInput.addEventListener('input', handleInputChange);

    // Theme toggle
    elements.themeToggle.addEventListener('click', toggleTheme);

    // Close mobile sidebar on overlay click
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('sidebar-overlay')) {
            closeMobileSidebar();
        }
    });
}

// ===== Widget Lookup =====
function getWidgetToken() {
    // Extract token from URL path: /chat-widget/{token}
    // The token is the last segment after /chat-widget/
    const path = window.location.pathname;

    // Match UUID pattern at the end of the path
    const uuidPattern = /([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$/i;
    const match = path.match(uuidPattern);

    return match ? match[1] : null;
}

async function lookupWidget(token) {
    try {
        // Determine API base URL from current location
        const baseUrl = window.location.origin;

        const response = await fetch(`${baseUrl}/rag/plugins/widget/lookup/${token}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (!response.ok) {
            if (response.status === 404) {
                showError('This chat widget link is invalid or has expired.');
            } else if (response.status === 403) {
                showError('This chat widget is currently inactive.');
            } else {
                showError('Failed to initialize chat widget. Please try again.');
            }
            return false;
        }

        const data = await response.json();

        // Store configuration
        CONFIG.apiBaseUrl = data.api_base_url || baseUrl;
        CONFIG.accessToken = data.access_token;
        CONFIG.collectionId = data.collection_id;
        CONFIG.collectionName = data.collection_name;
        CONFIG.userId = data.user_id;
        CONFIG.username = data.username;

        // Update UI with collection name
        elements.collectionName.textContent = data.collection_name || 'Chat Assistant';
        document.title = `${data.collection_name || 'Chat'} - Widget`;

        // Verify the token is valid
        const tokenValid = await verifyToken(CONFIG.accessToken);
        if (!tokenValid) {
            showError('Authentication failed. Please try refreshing the page.');
            return false;
        }

        return true;
    } catch (error) {
        console.error('Widget lookup error:', error);
        showError('Unable to connect to the chat service. Please check your connection.');
        return false;
    }
}

// Verify token with the backend (same endpoint used by plugin)
async function verifyToken(token) {
    if (!token) return false;

    try {
        const response = await fetch(`${CONFIG.apiBaseUrl}/rag/auth/plugin-token/verify`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify({
                token: token,
            }),
        });

        if (!response.ok) {
            console.error('Token verification failed:', response.status);
            return false;
        }

        const data = await response.json();

        if (data.valid === true) {
            // Store additional context from verification
            if (data.user_id) CONFIG.userId = data.user_id;
            if (data.username) CONFIG.username = data.username;
            if (data.collection_id) CONFIG.collectionId = data.collection_id;
            if (data.website_id) CONFIG.websiteId = data.website_id;
            return true;
        }

        return false;
    } catch (error) {
        console.error('Token verification error:', error);
        return false;
    }
}

// Refresh token by re-calling the widget lookup endpoint
async function refreshToken() {
    const widgetToken = getWidgetToken();
    if (!widgetToken) {
        console.error('Cannot refresh: no widget token in URL');
        return false;
    }

    try {
        const baseUrl = window.location.origin;
        const response = await fetch(`${baseUrl}/rag/plugins/widget/lookup/${widgetToken}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (!response.ok) {
            console.error('Token refresh failed:', response.status);
            return false;
        }

        const data = await response.json();

        // Update access token
        CONFIG.accessToken = data.access_token;

        // Re-verify the new token
        const verified = await verifyToken(CONFIG.accessToken);
        if (verified) {
            console.log('Token refreshed successfully');
            return true;
        }

        return false;
    } catch (error) {
        console.error('Token refresh error:', error);
        return false;
    }
}

// ===== UI State =====
function showError(message) {
    elements.loadingScreen.classList.add('hidden');
    elements.chatInterface.classList.add('hidden');
    elements.errorMessage.textContent = message;
    elements.errorScreen.classList.remove('hidden');
}

function showChatInterface() {
    elements.loadingScreen.classList.add('hidden');
    elements.errorScreen.classList.add('hidden');
    elements.chatInterface.classList.remove('hidden');
}

// ===== Session Management =====
function generateSessionId() {
    return `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
}

function startNewSession() {
    const newId = generateSessionId();
    state.sessionId = newId;
    state.messages = [];

    // Add to sessions list
    const newSession = {
        id: newId,
        title: 'New Chat',
        timestamp: Date.now(),
        messages: [],
    };
    state.sessions.unshift(newSession);

    // Save and render
    saveSessions();
    renderHistory();
    renderMessages();
    elements.messageInput.focus();
}

function loadSession(sessionId) {
    const session = state.sessions.find(s => s.id === sessionId);
    if (!session) return;

    state.sessionId = sessionId;
    state.messages = session.messages || [];

    renderHistory();
    renderMessages();
    scrollToBottom();
    closeMobileSidebar();
}

function deleteSession(sessionId) {
    state.sessions = state.sessions.filter(s => s.id !== sessionId);
    saveSessions();

    // If deleted current session, start new one
    if (sessionId === state.sessionId) {
        if (state.sessions.length > 0) {
            loadSession(state.sessions[0].id);
        } else {
            startNewSession();
        }
    } else {
        renderHistory();
    }
}

function updateSessionTitle(sessionId, firstMessage) {
    const session = state.sessions.find(s => s.id === sessionId);
    if (session && session.title === 'New Chat') {
        session.title = firstMessage.slice(0, 40) + (firstMessage.length > 40 ? '...' : '');
        saveSessions();
        renderHistory();
    }
}

function saveSessions() {
    // Update current session's messages
    const session = state.sessions.find(s => s.id === state.sessionId);
    if (session) {
        session.messages = state.messages;
        session.timestamp = Date.now();
    }

    // Save to localStorage with widget-specific key
    const storageKey = `widget_sessions_${CONFIG.collectionId}`;
    try {
        localStorage.setItem(storageKey, JSON.stringify(state.sessions));
    } catch (e) {
        console.warn('Failed to save sessions to localStorage:', e);
    }
}

function loadSessions() {
    const storageKey = `widget_sessions_${CONFIG.collectionId}`;
    try {
        const saved = localStorage.getItem(storageKey);
        if (saved) {
            state.sessions = JSON.parse(saved);
            // Load the most recent session
            if (state.sessions.length > 0) {
                state.sessionId = state.sessions[0].id;
                state.messages = state.sessions[0].messages || [];
            }
        }
    } catch (e) {
        console.warn('Failed to load sessions from localStorage:', e);
        state.sessions = [];
    }

    renderHistory();
    renderMessages();
}

// ===== Rendering =====
function renderHistory() {
    elements.historyList.innerHTML = '';

    state.sessions.forEach(session => {
        const item = document.createElement('div');
        item.className = `history-item ${session.id === state.sessionId ? 'active' : ''}`;
        item.innerHTML = `
            <div class="history-item-content" data-id="${session.id}">
                <div class="history-item-title">${escapeHtml(session.title)}</div>
            </div>
            <div class="history-item-actions">
                <button class="history-action-btn edit" title="Edit" data-id="${session.id}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                    </svg>
                </button>
                <button class="history-action-btn delete" title="Delete" data-id="${session.id}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
            </div>
        `;

        // Click to load session
        item.querySelector('.history-item-content').addEventListener('click', () => {
            loadSession(session.id);
        });

        // Delete button
        item.querySelector('.history-action-btn.delete').addEventListener('click', (e) => {
            e.stopPropagation();
            deleteSession(session.id);
        });

        elements.historyList.appendChild(item);
    });
}

function renderMessages() {
    if (state.messages.length === 0) {
        elements.messagesList.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-content">
                    <svg class="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                    </svg>
                    <p class="empty-state-text">You can start the conversation by sending a message below.</p>
                </div>
            </div>
        `;
        return;
    }

    elements.messagesList.innerHTML = '';

    state.messages.forEach(msg => {
        const msgEl = createMessageElement(msg);
        elements.messagesList.appendChild(msgEl);
    });

    scrollToBottom();
}

function createMessageElement(msg) {
    const div = document.createElement('div');
    div.className = `message-row ${msg.role}`;
    div.dataset.id = msg.id;

    const time = formatTime(msg.timestamp);
    let sourcesHtml = '';

    if (msg.sources && msg.sources.length > 0) {
        const sourceItems = msg.sources.map(source => {
            const isWeb = source.url || source.source_type === 'web_crawl';
            const icon = isWeb ?
                `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>` :
                `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>`;

            if (isWeb && source.url) {
                return `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener" class="source-item web">
                    ${icon}
                    <span>${escapeHtml(source.file_name || 'Link')}</span>
                </a>`;
            } else {
                return `<div class="source-item file">
                    ${icon}
                    <span>${escapeHtml(source.file_name)}</span>
                </div>`;
            }
        }).join('');

        sourcesHtml = `
            <div class="message-sources">
                <div class="sources-label">Sources</div>
                <div class="sources-list">${sourceItems}</div>
            </div>
        `;
    }

    div.innerHTML = `
        <div class="message-content">
            <div class="message-text-wrapper">
                ${formatMessageContent(msg.content)}
                ${sourcesHtml}
            </div>
            <div class="message-time">${time}</div>
        </div>
    `;

    return div;
}

function addTypingIndicator() {
    const div = document.createElement('div');
    div.className = 'message-row assistant';
    div.id = 'typing-indicator';
    div.innerHTML = `
        <div class="message-content">
            <div class="thinking-container">
                <img src="leto.svg" alt="Leto logo" class="thinking-logo">
                <div class="thinking-container">
                    <span class="loading-spinner-small"></span>
                    <span class="thinking-text">Leto is thinking...</span>
                </div>
            </div>
        </div>
    `;
    elements.messagesList.appendChild(div);
    scrollToBottom();
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

function formatMessageContent(content) {
    // Basic markdown-like formatting
    let formatted = escapeHtml(content);

    // Bold text
    formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Italic text
    formatted = formatted.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Line breaks
    formatted = formatted.replace(/\n/g, '<br>');

    return formatted;
}

function formatTime(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function scrollToBottom() {
    elements.messagesEnd.scrollIntoView({ behavior: 'smooth' });
}

// ===== Chat Functionality =====
function handleInputChange() {
    const hasText = elements.messageInput.value.trim().length > 0;
    elements.sendBtn.disabled = !hasText || state.isLoading;
}

async function handleSubmit(e) {
    e.preventDefault();

    const content = elements.messageInput.value.trim();
    if (!content || state.isLoading) return;

    // Clear input
    elements.messageInput.value = '';
    elements.sendBtn.disabled = true;

    // Add user message
    const userMessage = {
        id: `user_${Date.now()}`,
        role: 'user',
        content: content,
        timestamp: new Date().toISOString(),
    };

    state.messages.push(userMessage);
    renderMessages();
    updateSessionTitle(state.sessionId, content);

    // Send to API
    await sendMessage(content);
}

async function sendMessage(content) {
    state.isLoading = true;
    addTypingIndicator();

    try {
        const conversationHistory = state.messages.slice(-20).map(msg => ({
            role: msg.role,
            content: msg.content,
            timestamp: msg.timestamp,
        }));

        const payload = {
            question: content,
            session_id: state.sessionId,
            conversation_history: conversationHistory,
            maintain_context: conversationHistory.length > 0,
            collection_id: CONFIG.collectionId,
        };

        // Include website_id if available (same as plugin)
        if (CONFIG.websiteId) {
            payload.website_id = CONFIG.websiteId;
        }

        const response = await fetch(`${CONFIG.apiBaseUrl}/rag/chat/ask`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${CONFIG.accessToken}`,
            },
            body: JSON.stringify(payload),
        });

        removeTypingIndicator();

        // Handle 401 - token expired, try to refresh
        if (response.status === 401) {
            const refreshed = await refreshToken();
            if (refreshed) {
                // Retry the request with new token
                return sendMessage(content);
            } else {
                throw new Error('Session expired. Please refresh the page.');
            }
        }

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();

        // Process response
        let assistantContent = data.answer || data.response || data.content || 'I was unable to generate a response.';

        // Clean up sources section from content
        assistantContent = assistantContent
            .replace(/\r?\n+[\s>*-]*\*{0,2}\s*Sources?\s*:?\s*\*{0,2}\s*[\s\S]*$/i, '')
            .replace(/\r?\n+Sources?\s*:[\s\S]*$/i, '')
            .trim();

        // Extract sources
        let sources = [];
        if (Array.isArray(data.sources)) {
            sources = data.sources
                .filter(item => item && item.file_name)
                .map(item => ({
                    file_name: item.file_name,
                    file_id: item.file_id,
                    source_type: item.source_type,
                    url: item.url,
                }))
                .slice(0, 4);
        }

        // Add assistant message and start streaming
        const assistantMessage = {
            id: `assistant_${Date.now()}`,
            role: 'assistant',
            content: assistantContent,
            timestamp: new Date().toISOString(),
            sources: sources.length > 0 ? sources : undefined,
            streaming: true,
        };

        state.messages.push(assistantMessage);
        await streamAssistantResponse(assistantMessage.id, assistantContent);

        saveSessions();

    } catch (error) {
        console.error('Chat error:', error);
        removeTypingIndicator();

        // Add error message
        const errorMessage = {
            id: `assistant_error_${Date.now()}`,
            role: 'assistant',
            content: 'Sorry, I encountered an error. Please try again.',
            timestamp: new Date().toISOString(),
        };

        state.messages.push(errorMessage);
        renderMessages();
    } finally {
        state.isLoading = false;
        elements.sendBtn.disabled = elements.messageInput.value.trim().length === 0;
    }
}

async function streamAssistantResponse(messageId, fullContent) {
    return new Promise((resolve) => {
        state.isStreaming = true;
        let currentIndex = 0;
        const msgIndex = state.messages.findIndex(m => m.id === messageId);
        if (msgIndex === -1) {
            resolve();
            return;
        }

        // Create the element in UI first
        renderMessages();
        const messageEl = elements.messagesList.querySelector(`[data-id="${messageId}"] .message-content`);
        const sourcesEl = elements.messagesList.querySelector(`[data-id="${messageId}"] .message-sources`);

        if (sourcesEl) sourcesEl.style.display = 'none'; // Hide sources while streaming

        if (state.typingInterval) clearInterval(state.typingInterval);

        state.typingInterval = setInterval(() => {
            currentIndex += 1;
            const partialContent = fullContent.slice(0, currentIndex);

            // Update the message content in state and UI
            state.messages[msgIndex].content = partialContent;
            if (messageEl) {
                messageEl.innerHTML = formatMessageContent(partialContent);
            }

            scrollToBottom();

            if (currentIndex >= fullContent.length) {
                clearInterval(state.typingInterval);
                state.isStreaming = false;
                state.messages[msgIndex].streaming = false;
                if (sourcesEl) sourcesEl.style.display = 'block'; // Show sources when done
                scrollToBottom();
                resolve();
            }
        }, 10); // Match the snappiness
    });
}

// ===== Sidebar =====
function toggleSidebar() {
    elements.sidebar.classList.toggle('collapsed');
    state.sidebarOpen = !elements.sidebar.classList.contains('collapsed');
}

function toggleMobileSidebar() {
    const isOpen = elements.sidebar.classList.contains('open');
    if (isOpen) {
        closeMobileSidebar();
    } else {
        openMobileSidebar();
    }
}

function openMobileSidebar() {
    elements.sidebar.classList.add('open');
    // Add overlay
    let overlay = document.querySelector('.sidebar-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay visible';
        document.body.appendChild(overlay);
    } else {
        overlay.classList.add('visible');
    }
}

function closeMobileSidebar() {
    elements.sidebar.classList.remove('open');
    const overlay = document.querySelector('.sidebar-overlay');
    if (overlay) {
        overlay.classList.remove('visible');
    }
}

// ===== Theme =====
function loadTheme() {
    const savedTheme = localStorage.getItem('widget_theme') || 'light';
    setTheme(savedTheme);
}

function toggleTheme() {
    const newTheme = state.theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    localStorage.setItem('widget_theme', newTheme);
}

function setTheme(theme) {
    state.theme = theme;
    document.documentElement.setAttribute('data-theme', theme);

    // Toggle icons
    const sunIcon = elements.themeToggle.querySelector('.sun-icon');
    const moonIcon = elements.themeToggle.querySelector('.moon-icon');

    if (theme === 'dark') {
        sunIcon.classList.add('hidden');
        moonIcon.classList.remove('hidden');
    } else {
        sunIcon.classList.remove('hidden');
        moonIcon.classList.add('hidden');
    }
}

// ===== Utilities =====
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
