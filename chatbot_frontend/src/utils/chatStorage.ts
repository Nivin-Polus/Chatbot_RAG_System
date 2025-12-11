import { ChatMessage } from '@/types/auth';

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
  }>;
  sessionId: string | null;
  collectionId: string;
  lastUpdated: string; // ISO string
}

/**
 * Get the storage key for chat history
 */
function getStorageKey(userId: string | undefined, collectionId: string, role: string): string {
  const userPart = userId || 'anonymous';
  const rolePart = role || 'user';
  return `chat_history_${rolePart}_${userPart}_${collectionId}`;
}

/**
 * Save chat history to localStorage
 */
export function saveChatHistory(
  messages: ChatMessage[],
  sessionId: string | null,
  collectionId: string,
  userId: string | undefined,
  role: string
): void {
  if (!collectionId) return;

  try {
    const storageKey = getStorageKey(userId, collectionId, role);
    const history: StoredChatHistory = {
      messages: messages.map((msg) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        timestamp: msg.timestamp.toISOString(),
        sources: msg.sources,
      })),
      sessionId,
      collectionId,
      lastUpdated: new Date().toISOString(),
    };

    localStorage.setItem(storageKey, JSON.stringify(history));
  } catch (error) {
    console.error('Failed to save chat history to localStorage:', error);
  }
}

/**
 * Load chat history from localStorage
 */
export function loadChatHistory(
  collectionId: string,
  userId: string | undefined,
  role: string
): { messages: ChatMessage[]; sessionId: string | null } | null {
  if (!collectionId) return null;

  try {
    const storageKey = getStorageKey(userId, collectionId, role);
    const stored = localStorage.getItem(storageKey);

    if (!stored) return null;

    const history: StoredChatHistory = JSON.parse(stored);

    // Only load if it's for the same collection
    if (history.collectionId !== collectionId) return null;

    // Convert stored messages back to ChatMessage format
    const messages: ChatMessage[] = history.messages.map((msg) => ({
      id: msg.id,
      role: msg.role,
      content: msg.content,
      timestamp: new Date(msg.timestamp),
      sources: msg.sources,
    }));

    return {
      messages,
      sessionId: history.sessionId,
    };
  } catch (error) {
    console.error('Failed to load chat history from localStorage:', error);
    return null;
  }
}

/**
 * Clear chat history from localStorage
 */
export function clearChatHistory(
  collectionId: string,
  userId: string | undefined,
  role: string
): void {
  if (!collectionId) return;

  try {
    const storageKey = getStorageKey(userId, collectionId, role);
    localStorage.removeItem(storageKey);
  } catch (error) {
    console.error('Failed to clear chat history from localStorage:', error);
  }
}

/**
 * Clear all chat histories for a user (useful on logout)
 */
export function clearAllChatHistories(userId: string | undefined, role: string): void {
  try {
    const prefix = `chat_history_${role || 'user'}_${userId || 'anonymous'}_`;
    const keysToRemove: string[] = [];

    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith(prefix)) {
        keysToRemove.push(key);
      }
    }

    keysToRemove.forEach((key) => localStorage.removeItem(key));
  } catch (error) {
    console.error('Failed to clear all chat histories from localStorage:', error);
  }
}

