import { ChatMessage } from '@/types/auth';

export interface ChatSession {
  id: string;
  title: string;
  timestamp: number;
  collectionId: string;
}

interface StoredChatHistory {
  messages: Array<{
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: string; // ISO string
    sources?: Array<{
      file_name: string;
      file_id?: string;
      chunk_indices?: number[];
    }>;
    isFollowup?: boolean;
  }>;
  sessionId: string;
  collectionId: string;
  lastUpdated: string; // ISO string
}

const SESSION_INDEX_KEY = 'chat_sessions_index';
const MESSAGE_PREFIX = 'chat_messages_';

/**
 * Get the session index key for a user/role
 */
function getIndexKey(userId: string | undefined, role: string): string {
  const userPart = userId || 'anonymous';
  const rolePart = role || 'user';
  return `${SESSION_INDEX_KEY}_${rolePart}_${userPart}`;
}

/**
 * Get the storage key for a specific session's messages
 */
function getMessageKey(sessionId: string): string {
  return `${MESSAGE_PREFIX}${sessionId}`;
}

/**
 * Get all sessions for a user
 */
export function getSessions(userId: string | undefined, role: string): ChatSession[] {
  try {
    const key = getIndexKey(userId, role);
    const stored = localStorage.getItem(key);
    if (!stored) return [];
    return JSON.parse(stored);
  } catch (error) {
    console.error('Failed to load sessions:', error);
    return [];
  }
}

/**
 * Save a session (updates index and message storage)
 */
/**
 * Save a session (updates index and message storage)
 */
export function saveSession(
  sessionId: string,
  messages: ChatMessage[],
  collectionId: string,
  userId: string | undefined,
  role: string,
  shouldTouch: boolean = true // If true, updates timestamp (moves to top). If false, just saves content.
): void {
  try {
    // 1. Save Messages
    const messageKey = getMessageKey(sessionId);
    const history: StoredChatHistory = {
      messages: messages.map((msg) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        timestamp: msg.timestamp.toISOString(),
        sources: msg.sources,
        isFollowup: msg.isFollowup,
      })),
      sessionId,
      collectionId,
      lastUpdated: new Date().toISOString(),
    };
    localStorage.setItem(messageKey, JSON.stringify(history));

    // 2. Update Index
    const indexKey = getIndexKey(userId, role);
    const sessions = getSessions(userId, role);
    const existingIndex = sessions.findIndex((s) => s.id === sessionId);

    let title = 'New Chat';
    let previousTitle = 'New Chat';
    let timestamp = Date.now();

    if (existingIndex >= 0) {
      // Existing session: preserve title and timestamp unless we want to touch
      previousTitle = sessions[existingIndex].title;
      timestamp = shouldTouch ? Date.now() : sessions[existingIndex].timestamp;

      // If we are touching (active interaction), keep current timestamp
      // If NOT touching (just loading/viewing), keep OLD timestamp
    }

    // Determine Title
    // Only update title if it's currently "New Chat" OR if it's a brand new session
    if (previousTitle === 'New Chat') {
      const firstUserMsg = messages.find((m) => m.role === 'user');
      if (firstUserMsg) {
        title = firstUserMsg.content.replace(/\s+/g, ' ').trim().slice(0, 60);
      } else {
        title = previousTitle;
      }
    } else {
      title = previousTitle;
    }

    const sessionInfo: ChatSession = {
      id: sessionId,
      title,
      timestamp, // Use the determined timestamp
      collectionId,
    };

    if (existingIndex >= 0) {
      sessions[existingIndex] = sessionInfo;
    } else {
      sessions.push(sessionInfo);
    }

    // Sort by timestamp desc
    sessions.sort((a, b) => b.timestamp - a.timestamp);

    localStorage.setItem(indexKey, JSON.stringify(sessions));

    // Dispatch event for UI updates
    window.dispatchEvent(new Event('chat-history-updated'));

  } catch (error) {
    console.error('Failed to save session:', error);
  }
}

/**
 * Get a specific session
 */
export function getSession(
  sessionId: string
): { messages: ChatMessage[]; collectionId: string } | null {
  try {
    const key = getMessageKey(sessionId);
    const stored = localStorage.getItem(key);
    if (!stored) return null;

    const history: StoredChatHistory = JSON.parse(stored);

    return {
      messages: history.messages.map((msg) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        timestamp: new Date(msg.timestamp),
        sources: msg.sources,
        isFollowup: msg.isFollowup,
      })),
      collectionId: history.collectionId
    };
  } catch (error) {
    console.error('Failed to load session:', error);
    return null;
  }
}

/**
 * Delete a session
 */
export function deleteSession(
  sessionId: string,
  userId: string | undefined,
  role: string
): void {
  try {
    // 1. Remove messages
    localStorage.removeItem(getMessageKey(sessionId));

    // 2. Remove from index
    const indexKey = getIndexKey(userId, role);
    let sessions = getSessions(userId, role);
    sessions = sessions.filter((s) => s.id !== sessionId);
    localStorage.setItem(indexKey, JSON.stringify(sessions));

    window.dispatchEvent(new Event('chat-history-updated'));
  } catch (error) {
    console.error('Failed to delete session:', error);
  }
}

/**
 * Rename a session
 */
export function renameSession(
  sessionId: string,
  newTitle: string,
  userId: string | undefined,
  role: string
): void {
  try {
    const indexKey = getIndexKey(userId, role);
    const sessions = getSessions(userId, role);
    const sessionIndex = sessions.findIndex((s) => s.id === sessionId);

    if (sessionIndex >= 0) {
      sessions[sessionIndex].title = newTitle;
      localStorage.setItem(indexKey, JSON.stringify(sessions));
      window.dispatchEvent(new Event('chat-history-updated'));
    }
  } catch (error) {
    console.error('Failed to rename session:', error);
  }
}

/**
 * Clear all sessions for a user
 */
export function clearAllSessions(userId: string | undefined, role: string): void {
  try {
    const sessions = getSessions(userId, role);
    sessions.forEach(s => localStorage.removeItem(getMessageKey(s.id)));
    localStorage.removeItem(getIndexKey(userId, role));
    window.dispatchEvent(new Event('chat-history-updated'));
  } catch (error) {
    console.error('Failed to clear sessions:', error);
  }
}

// --- Plugin Session Migration ---

// Plugin localStorage keys
const PLUGIN_SESSIONS_INDEX_KEY = 'chatbot_sessions_index';
const PLUGIN_MESSAGES_PREFIX = 'chatbot_messages_';

interface PluginMessage {
  user: boolean;
  text: string;
  formatted: boolean;
  timestamp: string;
  sources?: Array<{
    file_name?: string;
    file_id?: string;
    chunk_indices?: number[];
    source_type?: string;
    url?: string;
  }>;
  isFollowup?: boolean;
}

interface PluginSession {
  id: string;
  title: string;
  timestamp: number;
}

/**
 * Migrate a specific plugin session to the frontend format
 * Returns the session ID if migration was successful, null otherwise
 */
export function migratePluginSession(
  pluginSessionId: string,
  userId: string | undefined,
  role: string,
  collectionId: string
): string | null {
  try {
    // Read plugin session messages
    const pluginMessagesKey = `${PLUGIN_MESSAGES_PREFIX}${pluginSessionId}`;
    const pluginMessagesStr = localStorage.getItem(pluginMessagesKey);

    if (!pluginMessagesStr) {
      console.warn('Plugin session not found:', pluginSessionId);
      return null;
    }

    const pluginMessages: PluginMessage[] = JSON.parse(pluginMessagesStr);

    if (!Array.isArray(pluginMessages) || pluginMessages.length === 0) {
      console.warn('No messages in plugin session:', pluginSessionId);
      return null;
    }

    // Convert plugin messages to frontend format
    const frontendMessages: ChatMessage[] = pluginMessages.map((msg, index) => ({
      id: msg.user ? `user_${Date.now()}_${index}` : `assistant_${Date.now()}_${index}`,
      role: msg.user ? 'user' as const : 'assistant' as const,
      content: msg.text || '',
      timestamp: new Date(msg.timestamp || Date.now()),
      sources: msg.sources?.map(s => ({
        file_name: s.file_name || '',
        file_id: s.file_id,
        chunk_indices: s.chunk_indices,
        source_type: s.source_type as 'file' | 'web_crawl' | undefined,
        url: s.url,
      })).filter(s => s.file_name),
      isFollowup: msg.isFollowup,
    }));

    // Save to frontend storage format
    saveSession(pluginSessionId, frontendMessages, collectionId, userId, role);

    return pluginSessionId;
  } catch (error) {
    console.error('Failed to migrate plugin session:', error);
    return null;
  }
}

/**
 * Migrate all plugin sessions to the frontend format
 * Returns array of migrated session IDs
 */
export function migrateAllPluginSessions(
  userId: string | undefined,
  role: string,
  collectionId: string
): string[] {
  try {
    const sessionsStr = localStorage.getItem(PLUGIN_SESSIONS_INDEX_KEY);
    if (!sessionsStr) return [];

    const pluginSessions: PluginSession[] = JSON.parse(sessionsStr);
    if (!Array.isArray(pluginSessions)) return [];

    const migratedIds: string[] = [];

    for (const session of pluginSessions) {
      const migratedId = migratePluginSession(session.id, userId, role, collectionId);
      if (migratedId) {
        migratedIds.push(migratedId);
      }
    }

    return migratedIds;
  } catch (error) {
    console.error('Failed to migrate plugin sessions:', error);
    return [];
  }
}

/**
 * Check if a plugin session exists
 */
export function hasPluginSession(sessionId: string): boolean {
  try {
    const messagesKey = `${PLUGIN_MESSAGES_PREFIX}${sessionId}`;
    return localStorage.getItem(messagesKey) !== null;
  } catch {
    return false;
  }
}

// --- Backend Transfer Session Support ---

interface TransferredMessage {
  user: boolean;
  text: string;
  formatted?: boolean;
  timestamp?: string;
  sources?: Array<{
    file_name?: string;
    file_id?: string;
    chunk_indices?: number[];
    source_type?: string;
    url?: string;
  }>;
  isFollowup?: boolean;
}

interface TransferSessionData {
  session_id: string;
  messages: TransferredMessage[];
  collection_id: string;
}

/**
 * Fetch and import a transferred session from the backend
 * Returns the session ID if successful, null otherwise
 */
export async function importTransferredSession(
  transferToken: string,
  userId: string | undefined,
  role: string,
  apiBaseUrl: string
): Promise<string | null> {
  try {
    const response = await fetch(`${apiBaseUrl}/plugins/transfer-session/${encodeURIComponent(transferToken)}`);

    if (!response.ok) {
      console.warn('Failed to fetch transferred session:', response.status);
      return null;
    }

    const data: TransferSessionData = await response.json();

    if (!data.session_id || !Array.isArray(data.messages) || data.messages.length === 0) {
      console.warn('Invalid transferred session data');
      return null;
    }

    // Convert transferred messages to frontend format
    const frontendMessages: ChatMessage[] = data.messages.map((msg, index) => ({
      id: msg.user ? `user_${Date.now()}_${index}` : `assistant_${Date.now()}_${index}`,
      role: msg.user ? 'user' as const : 'assistant' as const,
      content: msg.text || '',
      timestamp: new Date(msg.timestamp || Date.now()),
      sources: msg.sources?.map(s => ({
        file_name: s.file_name || '',
        file_id: s.file_id,
        chunk_indices: s.chunk_indices,
        source_type: s.source_type as 'file' | 'web_crawl' | undefined,
        url: s.url,
      })).filter(s => s.file_name),
      isFollowup: msg.isFollowup,
    }));

    // Save to frontend storage
    saveSession(data.session_id, frontendMessages, data.collection_id, userId, role);

    return data.session_id;
  } catch (error) {
    console.error('Failed to import transferred session:', error);
    return null;
  }
}

// --- Multiple Sessions Transfer Support ---

interface TransferredSessionData {
  session_id: string;
  title?: string;
  timestamp?: number;
  messages: TransferredMessage[];
}

interface TransferSessionsResponse {
  current_session_id: string | null;
  sessions: TransferredSessionData[];
  collection_id: string;
}

/**
 * Fetch and import ALL transferred sessions from the backend
 * Returns the current session ID if successful, null otherwise
 */
export async function importTransferredSessions(
  transferToken: string,
  userId: string | undefined,
  role: string,
  apiBaseUrl: string
): Promise<string | null> {
  try {
    // Try the multi-session endpoint first
    let response = await fetch(`${apiBaseUrl}/plugins/transfer-sessions/${encodeURIComponent(transferToken)}`);

    if (!response.ok) {
      // Fallback to single-session endpoint for backward compatibility
      response = await fetch(`${apiBaseUrl}/plugins/transfer-session/${encodeURIComponent(transferToken)}`);
      if (!response.ok) {
        console.warn('Failed to fetch transferred sessions:', response.status);
        return null;
      }
      // Handle legacy single-session response
      const legacyData = await response.json();
      if (legacyData.session_id && Array.isArray(legacyData.messages)) {
        // Check if this session already exists and delete it first
        const messageKey = getMessageKey(legacyData.session_id);
        if (localStorage.getItem(messageKey)) {
          deleteSession(legacyData.session_id, userId, role);
        }

        const frontendMessages: ChatMessage[] = legacyData.messages.map((msg: TransferredMessage, index: number) => ({
          id: msg.user ? `user_${Date.now()}_${index}` : `assistant_${Date.now()}_${index}`,
          role: msg.user ? 'user' as const : 'assistant' as const,
          content: msg.text || '',
          timestamp: new Date(msg.timestamp || Date.now()),
          sources: msg.sources?.map(s => ({
            file_name: s.file_name || '',
            file_id: s.file_id,
            chunk_indices: s.chunk_indices,
            source_type: s.source_type as 'file' | 'web_crawl' | undefined,
            url: s.url,
          })).filter(s => s.file_name),
          isFollowup: msg.isFollowup,
        }));
        saveSession(legacyData.session_id, frontendMessages, legacyData.collection_id, userId, role);
        return legacyData.session_id;
      }
      return null;
    }

    const data: TransferSessionsResponse = await response.json();

    if (!Array.isArray(data.sessions) || data.sessions.length === 0) {
      console.warn('No sessions in transferred data');
      return null;
    }

    // Import all sessions
    let importedCount = 0;
    for (const session of data.sessions) {
      if (!session.session_id || !Array.isArray(session.messages) || session.messages.length === 0) {
        continue;
      }

      // Check if this session already exists and delete it first to avoid duplicates
      const messageKey = getMessageKey(session.session_id);
      if (localStorage.getItem(messageKey)) {
        console.log(`Removing existing session ${session.session_id} before importing fresh data`);
        deleteSession(session.session_id, userId, role);
      }

      // Convert transferred messages to frontend format
      const frontendMessages: ChatMessage[] = session.messages.map((msg, index) => ({
        id: msg.user ? `user_${Date.now()}_${index}_${session.session_id}` : `assistant_${Date.now()}_${index}_${session.session_id}`,
        role: msg.user ? 'user' as const : 'assistant' as const,
        content: msg.text || '',
        timestamp: new Date(msg.timestamp || Date.now()),
        sources: msg.sources?.map(s => ({
          file_name: s.file_name || '',
          file_id: s.file_id,
          chunk_indices: s.chunk_indices,
          source_type: s.source_type as 'file' | 'web_crawl' | undefined,
          url: s.url,
        })).filter(s => s.file_name),
        isFollowup: msg.isFollowup,
      }));

      // Save to frontend storage
      saveSession(session.session_id, frontendMessages, data.collection_id, userId, role);
      importedCount++;
    }

    console.log(`Imported ${importedCount} sessions from plugin`);

    // Return the current session ID (the one user was viewing in plugin)
    return data.current_session_id || (data.sessions[0]?.session_id ?? null);
  } catch (error) {
    console.error('Failed to import transferred sessions:', error);
    return null;
  }
}

// --- Legacy Support (Keeping original functions for backward compat if needed, simplified) ---

export function saveChatHistory(
  messages: ChatMessage[],
  sessionId: string | null,
  collectionId: string,
  userId: string | undefined,
  role: string
): void {
  if (sessionId) {
    saveSession(sessionId, messages, collectionId, userId, role);
  }
}

export function loadChatHistory(
  collectionId: string,
  userId: string | undefined,
  role: string
): { messages: ChatMessage[]; sessionId: string | null } | null {
  // Try to find the most recent session for this collection
  const sessions = getSessions(userId, role);
  const relevantSession = sessions.find(s => s.collectionId === collectionId); // Already sorted desc

  if (relevantSession) {
    const details = getSession(relevantSession.id);
    if (details) {
      return {
        messages: details.messages,
        sessionId: relevantSession.id
      };
    }
  }
  return null;
}

export function clearChatHistory(
  collectionId: string,
  userId: string | undefined,
  role: string
): void {
  // This originally cleared the "current" history.
  // In new model, maybe we create a new session or do nothing?
  // We'll leave it empty to encourage explicit session management.
}

export function clearAllChatHistories(userId: string | undefined, role: string): void {
  clearAllSessions(userId, role);
}

