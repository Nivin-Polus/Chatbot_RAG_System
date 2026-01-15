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
export function saveSession(
  sessionId: string,
  messages: ChatMessage[],
  collectionId: string,
  userId: string | undefined,
  role: string
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

    // Generate title from first user message
    const firstUserMsg = messages.find((m) => m.role === 'user');
    let title = 'New Chat';
    if (firstUserMsg) {
      title = firstUserMsg.content.slice(0, 30) + (firstUserMsg.content.length > 30 ? '...' : '');
    }

    const sessionInfo: ChatSession = {
      id: sessionId,
      title,
      timestamp: Date.now(),
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

