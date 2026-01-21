

const WIDGET_CONFIG = {
    // ===== Environment Mode =====
    // 'design' = Frontend only (no backend needed, uses mock data)
    // 'local'  = Local backend (localhost:8000)
    // 'dev'    = Dev server
    // 'prod'   = Production
    environment: 'prod',

    // ===== Mock Mode (auto-enabled in 'design' environment) =====
    // When true, bypasses API calls and uses mock data for UI development
    get mockMode() {
        return WIDGET_CONFIG.environment === 'design';
    },

    // ===== API & Backend URLs =====
    api: {
        // URL configurations per environment (for BACKEND API, not widget hosting)
        // The widget can be hosted anywhere; these URLs are where API calls go
        urls: {
            design: '',  // Not used in design mode
            local: 'http://localhost:8000',      // Local backend (FastAPI/Python)
            dev: 'https://dev-chatbot.polussolutions.com',
            prod: 'https://keyword-search.mit.edu',
        },

        // Base URL for API calls (auto-selected based on environment above)
        // Leave empty to use current origin, or override with specific URL
        get baseUrl() {
            return WIDGET_CONFIG.api.urls[WIDGET_CONFIG.environment] || '';
        },

        // Widget lookup endpoint path
        widgetLookupPath: '/rag/plugins/widget/lookup',

        // Token verification endpoint path
        tokenVerifyPath: '/rag/auth/plugin-token/verify',

        // Chat endpoint path
        chatEndpoint: '/rag/chat/ask',
    },

    // ===== Branding =====
    branding: {
        // Logo file path (relative to Chat_widget folder or absolute URL)
        logoPath: 'leto.svg',

        // Application/Assistant name shown in header
        appName: 'Chat Assistant',

        // Browser tab title suffix
        pageTitleSuffix: 'Help Page',

        // Text shown while AI is generating response
        thinkingText: 'Leto is thinking',

        // Empty chat placeholder message
        emptyStateMessage: 'You can start the conversation by sending a message below.',

        // Input placeholder text
        inputPlaceholder: 'Type your message...',
    },

    // ===== Error Messages =====
    errors: {
        invalidWidgetUrl: 'Invalid widget URL. Please check the link and try again.',
        widgetNotFound: 'This chat widget link is invalid or has expired.',
        widgetInactive: 'This chat widget is currently inactive.',
        initFailed: 'Failed to initialize chat widget. Please try again.',
        connectionError: 'Unable to connect to the chat service. Please check your connection.',
        authFailed: 'Authentication failed. Please try refreshing the page.',
        sessionExpired: 'Session expired. Please refresh the page.',
        genericError: 'Sorry, I encountered an error. Please try again.',
    },

    // ===== Theme Colors (HSL values) =====
    theme: {
        light: {
            // Page background
            background: '0 0% 98%',
            // Text color
            foreground: '222 47% 11%',
            // Card/bubble background
            card: '0 0% 100%',
            // Primary accent color (buttons, links)
            primary: '213 79% 46%',
            // Text on primary color
            primaryForeground: '0 0% 100%',
            // Secondary/subtle background
            secondary: '0 0% 97%',
            // Muted backgrounds (assistant bubbles)
            muted: '210 16% 93%',
            // Muted text color
            mutedForeground: '215 16% 35%',
            // Border color
            border: '210 14% 90%',
            // Input border color
            input: '210 14% 90%',
            // Focus ring color
            ring: '213 79% 46%',
        },
        dark: {
            background: '222 47% 11%',
            foreground: '210 40% 98%',
            card: '217 33% 17%',
            primary: '239 84% 67%',
            muted: '217 33% 18%',
            mutedForeground: '215 20% 65%',
            border: '217 33% 22%',
            input: '217 33% 22%',
        },
        // Default theme on first load ('light' or 'dark')
        defaultTheme: 'light',
    },

    // ===== Layout & Dimensions =====
    layout: {
        // Sidebar width when expanded (in pixels)
        sidebarWidth: 260,
        // Sidebar width when collapsed/rail mode (in pixels)
        sidebarCollapsedWidth: 72,
        // Header height (in pixels)
        headerHeight: 56,
        // Border radius (CSS value)
        borderRadius: '0.5rem',
        // Maximum width of user message bubbles (CSS value)
        userMessageMaxWidth: '65%',
        // Maximum width of assistant message bubbles (CSS value)
        assistantMessageMaxWidth: '80%',
        // Input field max width (CSS value)
        inputMaxWidth: '800px',
        // Mobile breakpoint (in pixels)
        mobileBreakpoint: 768,
    },

    // ===== Typography =====
    typography: {
        // Primary font family
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        // Base font size
        baseFontSize: '14px',
        // Message font size
        messageFontSize: '0.875rem',
        // Heading font size
        headingFontSize: '16px',
        // Line height
        lineHeight: 1.5,
    },

    // ===== Behavior Settings =====
    behavior: {
        // Typing animation speed in milliseconds (lower = faster)
        typingSpeed: 10,
        // Maximum number of messages to include in conversation history
        conversationHistoryLimit: 20,
        // Maximum number of sources to display per message
        maxSourcesDisplay: 4,
        // Session storage key prefix
        storageKeyPrefix: 'widget_sessions_',
        // Theme storage key
        themeStorageKey: 'widget_theme',
        // Enable smooth scroll behavior
        smoothScroll: true,
        // Auto-scroll to bottom on new messages
        autoScrollToBottom: true,
    },

    // ===== Open Graph / SEO Metadata =====
    metadata: {
        // OG image URL for social sharing
        ogImageUrl: 'https://dev-chatbot.polussolutions.com/chatbot/leto.png',
        ogImageWidth: 200,
        ogImageHeight: 200,
        ogTitle: 'Chat Widget - AI-powered knowledge base assistant',
        ogDescription: 'Ask questions and get instant answers from your knowledge base.',
    },
};

// Export for use in app.js
// (In browser environment, this attaches to window object)
if (typeof window !== 'undefined') {
    window.WIDGET_CONFIG = WIDGET_CONFIG;
}
