import { useState, useEffect, useRef, useCallback, useMemo, type ReactNode } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { DashboardLayout } from '@/components/DashboardLayout';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Trash2, Users, Search, Loader2, MoreHorizontal, Bot, MessageSquare, User, Send, ExternalLink, FileText, Download } from 'lucide-react';
import { ChatMessage, ChatSource } from '@/types/auth';
import { toast } from 'sonner';
import { apiGet, apiPost } from '@/utils/api';
import { getAssetUrl } from '@/utils/assets';
import { saveSession, getSession, getSessions } from '@/utils/chatStorage';
import { useSearchParams, useLocation } from 'react-router-dom';

type CollectionSummary = {
  collection_id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
};

export default function SuperadminChat() {
  const { user } = useAuth();
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [selectedCollection, setSelectedCollection] = useState<string>('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const sessionIdRef = useRef<string | null>(null); // NEW: Ref to track current session ID

  // Keep ref in sync
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const typingTimeoutRef = useRef<number | null>(null);
  const stopStreamingRef = useRef<(() => void) | null>(null);
  const [isAutoScroll, setIsAutoScroll] = useState(true);
  const isAutoScrollRef = useRef(true);
  const hasMessages = messages.length > 0;
  const saveTimeoutRef = useRef<number | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const lastLocationRef = useRef<string>(location.pathname);
  const lastMessagesCountRef = useRef<number>(0);
  const messagesRef = useRef<ChatMessage[]>(messages);

  // Keep messages ref in sync
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  const disableAutoScroll = useCallback(() => {
    if (!isAutoScrollRef.current) {
      return;
    }
    isAutoScrollRef.current = false;
    setIsAutoScroll(false);
  }, []);

  const enableAutoScroll = useCallback(() => {
    if (isAutoScrollRef.current) {
      return;
    }
    isAutoScrollRef.current = true;
    setIsAutoScroll(true);
  }, []);

  const handleManualScrollIntent = useCallback(() => {
    disableAutoScroll();
  }, [disableAutoScroll]);

  const handleWheel = useCallback(() => {
    disableAutoScroll();
  }, [disableAutoScroll]);

  const handleTouchMove = useCallback(() => {
    disableAutoScroll();
  }, [disableAutoScroll]);

  useEffect(() => {
    isAutoScrollRef.current = isAutoScroll;
  }, [isAutoScroll]);

  const scrollToBottom = useCallback((smooth = true) => {
    if (messagesEndRef.current && isAutoScrollRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto' });
    }
  }, []);

  // Handle Session Loading
  useEffect(() => {
    const urlSessionId = searchParams.get('session');

    if (urlSessionId) {
      if (sessionId !== urlSessionId) {
        const storedFn = getSession(urlSessionId);
        if (storedFn) {
          setMessages(storedFn.messages);
          setSessionId(urlSessionId);
          // Only update collection if it matches the session's collection
          if (storedFn.collectionId && storedFn.collectionId !== selectedCollection) {
            const collectionExists = collections.some(c => c.collection_id === storedFn.collectionId);
            if (collectionExists) {
              setSelectedCollection(storedFn.collectionId);
            }
          }
        } else {
          setSearchParams({});
        }
      }
    } else {
      if (!sessionId || sessionId !== 'new_session_placeholder') {
        const newId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
        setSessionId(newId);
        setMessages([]);
      }
    }
  }, [searchParams, user?.user_id]); // Removed sessionId dependency to avoid loop

  // Save chat history to localStorage once after assistant finishes streaming
  // Modified to use shouldTouch=false
  useEffect(() => {
    if (!isStreaming && selectedCollection && user?.user_id && messages.length > 0 && sessionId) {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
      saveTimeoutRef.current = window.setTimeout(() => {
        saveSession(sessionId, messages, selectedCollection, user.user_id, user.role || 'superadmin', false);

        // If URL doesn't have session, update it
        if (!searchParams.get('session')) {
          setSearchParams({ session: sessionId }, { replace: true });
        }
      }, 1000);
    }
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [isStreaming, messages, sessionId, selectedCollection, user?.user_id, user?.role, searchParams, setSearchParams]);

  useEffect(() => {
    if (isAutoScrollRef.current) {
      scrollToBottom();
    }
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (isAutoScroll) {
      scrollToBottom();
    }
  }, [isAutoScroll, scrollToBottom]);

  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) {
        window.clearTimeout(typingTimeoutRef.current);
      }
      stopStreamingRef.current = null;
    };
  }, []);

  // Check for new messages when returning to chat tab or periodically while on chat page
  useEffect(() => {
    const isChatPage = location.pathname === '/superadmin/chat' || location.pathname.includes('/superadmin/chat');
    const wasChatPage = lastLocationRef.current === '/superadmin/chat' || lastLocationRef.current.includes('/superadmin/chat');
    const justReturnedToChat = !wasChatPage && isChatPage;

    // Update last location
    lastLocationRef.current = location.pathname;

    // Function to check and update messages from storage
    const checkForUpdates = () => {
      if (sessionId && selectedCollection && user?.user_id) {
        const storedSession = getSession(sessionId);
        if (storedSession) {
          // Check if stored messages are different (newer or more messages)
          const storedCount = storedSession.messages.length;
          const currentCount = messagesRef.current.length;

          if (storedCount > currentCount ||
            (storedCount === currentCount && storedCount > 0 &&
              storedSession.messages[storedCount - 1]?.content !== messagesRef.current[currentCount - 1]?.content)) {
            // New messages found in storage, update state
            setMessages(storedSession.messages);
            lastMessagesCountRef.current = storedCount;
            enableAutoScroll();
            scrollToBottom();
          } else {
            lastMessagesCountRef.current = currentCount;
          }
        }
      }
    };

    // Check immediately if we just returned to chat
    if (justReturnedToChat) {
      checkForUpdates();
    }

    // Set up periodic check while on chat page (every 2 seconds)
    let intervalId: number | null = null;
    if (isChatPage && sessionId) {
      intervalId = window.setInterval(checkForUpdates, 2000);
    }

    return () => {
      if (intervalId !== null) {
        window.clearInterval(intervalId);
      }
    };
  }, [location.pathname, sessionId, selectedCollection, user?.user_id, enableAutoScroll, scrollToBottom]);

  // --- Updated Typing Animation ---
  const streamAssistantResponse = useCallback(
    (rawContent: string, sources?: ChatSource[], isFollowup?: boolean) => {
      const content = rawContent && rawContent.trim().length > 0
        ? rawContent
        : 'I was unable to generate a response.';
      const messageId = `assistant_${Date.now()}`;
      const timestamp = new Date();

      const targetSessionId = sessionIdRef.current; // Capture current session ID

      if (typingTimeoutRef.current) {
        window.clearTimeout(typingTimeoutRef.current);
        typingTimeoutRef.current = null;
      }

      setMessages((prev) => [
        ...prev,
        {
          id: messageId,
          role: 'assistant',
          content: '',
          timestamp,
          sources,
          isFollowup,
        },
      ]);

      return new Promise<void>((resolve) => {
        setIsStreaming(true);

        // Helper to save current state to storage even if unmounted/switched
        const saveProgressToStorage = (finalContent: string) => {
          if (user?.user_id && selectedCollection && targetSessionId) {
            const currentStored = getSession(targetSessionId);
            if (currentStored) {
              const updatedMsgs = currentStored.messages.map(m =>
                m.id === messageId
                  ? { ...m, content: finalContent, sources, isFollowup }
                  : m
              );

              if (!updatedMsgs.find(m => m.id === messageId)) {
                updatedMsgs.push({
                  id: messageId,
                  role: 'assistant',
                  content: finalContent,
                  timestamp,
                  sources,
                  isFollowup
                });
              }

              saveSession(targetSessionId, updatedMsgs, selectedCollection, user.user_id, user.role || 'superadmin', true);
            }
          }
        };

        const completeStream = () => {
          if (typingTimeoutRef.current) {
            window.clearTimeout(typingTimeoutRef.current);
            typingTimeoutRef.current = null;
          }

          if (sessionIdRef.current === targetSessionId) {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === messageId ? { ...msg, content, sources, isFollowup } : msg
              )
            );
            if (isStreaming) {
              scrollToBottom(false);
            } else {
              scrollToBottom();
            }
            setIsStreaming(false);
          } else {
            saveProgressToStorage(content);
          }

          stopStreamingRef.current = null;
          resolve();
        };

        if (content.length === 0) {
          completeStream();
          return;
        }

        let index = 0;

        stopStreamingRef.current = () => {
          completeStream();
        };

        const typeNext = () => {
          if (!document.hasFocus()) {
            // Optional: Handle background tab behavior if needed
            // For now we continue streaming unless chat switched
          }

          if (sessionIdRef.current !== targetSessionId) {
            saveProgressToStorage(content);
            resolve();
            return;
          }

          index += 1;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === messageId ? { ...msg, content: content.slice(0, index), sources, isFollowup } : msg
            )
          );
          scrollToBottom();

          if (index < content.length) {
            typingTimeoutRef.current = window.setTimeout(typeNext, 5);
          } else {
            completeStream();
          }
        };

        typeNext();
      });
    },
    [scrollToBottom, user?.user_id, user?.role, selectedCollection]
  );
  // --- End Typing Animation ---

  const fetchCollections = useCallback(async () => {
    try {
      const response = await apiGet(
        `${import.meta.env.VITE_API_BASE_URL}/collections/summary`,
        user?.access_token,
        false
      );
      if (!response.ok) {
        throw new Error('Failed to load knowledge bases');
      }

      const data: CollectionSummary[] = await response.json();
      setCollections(data);

      const activeData = data.filter((collection) => collection.is_active);
      setSelectedCollection((current) => {
        if (current && activeData.some((c) => c.collection_id === current)) {
          return current;
        }
        return activeData.length > 0 ? activeData[0].collection_id : '';
      });
    } catch (error) {
      toast.error('Unable to load knowledge bases for chat');
      setCollections([]);
      setSelectedCollection('');
    }
  }, [user?.access_token]);

  useEffect(() => {
    if (user?.access_token) {
      fetchCollections();
    }
  }, [user?.access_token, fetchCollections]);

  const activeCollections = useMemo(
    () => collections.filter((collection) => collection.is_active),
    [collections]
  );

  useEffect(() => {
    if (activeCollections.length === 0) {
      setSelectedCollection('');
      return;
    }

    setSelectedCollection((current) => {
      if (current && activeCollections.some((collection) => collection.collection_id === current)) {
        return current;
      }
      return activeCollections[0].collection_id;
    });
  }, [activeCollections]);

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || !selectedCollection || isLoading || isStreaming) return;

    const messageContent = inputMessage.trim();

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: messageContent,
      timestamp: new Date(),
    };

    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setInputMessage('');
    setIsLoading(true);
    enableAutoScroll();

    // Immediately save user message to storage so it's available if user switches tabs
    if (sessionId && user?.user_id && selectedCollection) {
      saveSession(sessionId, updatedMessages, selectedCollection, user.user_id, user.role || 'superadmin', true);
    }

    // Prepare conversation history (last ~20 messages)
    const conversationHistory = updatedMessages
      .slice(-20)
      .map((msg) => ({
        role: msg.role,
        content: msg.content,
        timestamp: msg.timestamp.toISOString(),
      }));

    try {
      const response = await apiPost(
        `${import.meta.env.VITE_API_BASE_URL}/chat/ask`,
        {
          question: messageContent,
          session_id: sessionId,
          conversation_history: conversationHistory,
          maintain_context: conversationHistory.length > 0,
          collection_id: selectedCollection,
        },
        user?.access_token
      );

      let data: any = null;
      try {
        data = await response.json();
      } catch (parseError) {
        data = null;
      }

      if (!response.ok) {
        setIsLoading(false);
        stopStreamingRef.current = null;
        setIsStreaming(false);

        const apiMessage =
          typeof data === 'string'
            ? data
            : typeof data === 'object' && data !== null
              ? data.detail || data.message || data.error || ''
              : '';
        const normalizedMessage = apiMessage.toString().toLowerCase();

        if (response.status === 401 && normalizedMessage.includes('session') && normalizedMessage.includes('expired')) {
          const content = 'Session expired. Please login again.';
          toast.error(content);
          setMessages((prev) => [
            ...prev,
            {
              id: (Date.now() + 1).toString(),
              role: 'assistant',
              content,
              timestamp: new Date(),
            },
          ]);
          return;
        }

        if (response.status === 401 || response.status === 403) {
          const content = 'Incorrect credentials. Please verify your access details and try again.';
          toast.error('Incorrect credentials');
          setMessages((prev) => [
            ...prev,
            {
              id: (Date.now() + 1).toString(),
              role: 'assistant',
              content,
              timestamp: new Date(),
            },
          ]);
          return;
        }

        const fallbackContent = apiMessage || 'Failed to send message';
        toast.error(fallbackContent);
        setMessages((prev) => [
          ...prev,
          {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: fallbackContent,
            timestamp: new Date(),
          },
        ]);
        return;
      }

      const dataResponse = data ?? {};

      // NEW: Handle follow-up responses
      if (dataResponse.is_followup) {
        const followupContent = dataResponse.followup_questions || 'Could you please clarify your question?';
        await streamAssistantResponse(followupContent, undefined, true);
        setIsLoading(false);
        return;
      }

      let assistantContent =
        dataResponse.response || dataResponse.answer || dataResponse.content || 'I was unable to generate a response.';

      // Helper to detect generic responses locally if API flag is missing
      const isGenericResponse = (text: string) => {
        if (!text) return false;
        const normalized = text.trim();
        const genericPattern = /I apologize|I'm limited to providing information|not have any information|outside of my scope|I'm afraid I don't have enough information|I don't have access to information|I don't have any information about|I'm here to help with questions about your knowledge base documents|the provided context does not contain|does not contain any information|do not have enough details|without any relevant information|there are no sources that discuss|i do not have enough details to provide|my role is to assist based on the provided information|I do not have enough context|I have no relevant information|I don't have enough context|I do not have any relevant information|provide a meaningful response/i;
        return genericPattern.test(normalized);
      };

      // Check if response is marked as generic (no relevant info found) - if so, don't show sources
      const isGeneric = Boolean(dataResponse.is_generic) || isGenericResponse(assistantContent);

      // ALWAYS strip embedded sources section from answer text to prevent duplicates/baked-in sources
      // Match pattern: **Sources:** followed by lines starting with - [ ]( ) or just - 
      assistantContent = assistantContent
        .replace(/\r?\n+[\s>*-]*\*{0,2}\s*Sources?\s*:?\s*\*{0,2}\s*[\s\S]*$/i, '')
        .replace(/\r?\n+Sources?\s*:[\s\S]*$/i, '')
        .trim();

      const sources: ChatSource[] | undefined = isGeneric
        ? undefined
        : Array.isArray(dataResponse.sources)
          ? dataResponse.sources
            .map((item: any) => {
              if (!item || typeof item !== 'object') {
                return null;
              }
              const fileName = typeof item.file_name === 'string' ? item.file_name : undefined;
              const fileId = typeof item.file_id === 'string' ? item.file_id : undefined;
              const sourceType = typeof item.source_type === 'string' ? item.source_type as 'file' | 'web_crawl' : undefined;
              const url = typeof item.url === 'string' ? item.url : undefined;

              if (!fileName) {
                return null;
              }
              return {
                file_name: fileName,
                file_id: fileId,
                source_type: sourceType,
                url: url,
              } satisfies ChatSource;
            })
            .filter((value): value is ChatSource => value !== null)
            .slice(0, 4) // Limit to 4 most relevant sources
          : undefined;

      // Re-append the cleaned and limited sources to the text so the renderer can pick them up
      if (!isGeneric && sources && sources.length > 0) {
        assistantContent += '\n\n**Sources:**';
        sources.forEach((source) => {
          // Format as markdown link [- filename](id/url) which the renderer understands
          const ref = source.url || source.file_id || 'source';
          assistantContent += `\n- [${source.file_name}](${ref})`;
        });
      }

      await streamAssistantResponse(assistantContent, sources);
      setIsLoading(false);

      if (user?.access_token && selectedCollection) {
        void apiPost(
          `${import.meta.env.VITE_API_BASE_URL}/activity/log`,
          {
            activity_type: 'chat_query',
            description: `Superadmin chat with ${selectedCollection}`,
            collection_id: selectedCollection,
            metadata: {
              session_id: sessionId,
              question: messageContent,
            },
          },
          user.access_token,
          false
        ).catch(() => { });
      }

    } catch (error) {
      setIsLoading(false);
      toast.error('Failed to send message');
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    }
  };

  const clearChat = async () => {
    if (stopStreamingRef.current) {
      stopStreamingRef.current();
    }

    setMessages([]);
    setSearchParams({});
    enableAutoScroll();
  };

  const handleStopStreaming = useCallback(() => {
    stopStreamingRef.current?.();
  }, []);

  const handleDownloadSource = useCallback(
    async (sourceRef: string, sourceName?: string) => {
      if (!user?.access_token) {
        toast.error('Unable to download source.');
        return;
      }

      try {
        // Use the exact same approach as the working files section
        const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/files/download/${sourceRef}`, {
          headers: {
            Authorization: `Bearer ${user.access_token}`,
          },
        });

        if (response.ok) {
          const blob = await response.blob();
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = sourceName || 'download';
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
          toast.success('Source downloaded successfully');
        } else {
          if (response.status === 404) {
            toast.error('Source file not found');
          } else if (response.status === 403) {
            toast.error('You do not have permission to download this file');
          } else {
            toast.error(`Download failed: ${response.status} ${response.statusText}`);
          }
        }
      } catch (error) {
        toast.error('Failed to download source file');
      }
    },
    [selectedCollection, user?.access_token]
  );

  const renderMessageContent = useCallback(
    (content: string, messageId: string, messageSources?: ChatSource[]) => {
      const nodes: ReactNode[] = [];
      const lines = content.split('\n');
      let inSourcesSection = false;
      let keyCounter = 0;

      const nextKey = () => `${messageId}-node-${keyCounter++}`;

      const sourceIdLookup = new Map<string, string>();
      const sourceMetadataLookup = new Map<string, { url?: string; source_type?: string; file_id?: string }>();
      if (Array.isArray(messageSources)) {
        for (const source of messageSources) {
          if (!source || typeof source !== 'object') continue;
          if (!source.file_name) continue;
          const normalized = source.file_name.trim().toLowerCase();
          if (!normalized) continue;
          if (!sourceIdLookup.has(normalized) && source.file_id) {
            sourceIdLookup.set(normalized, source.file_id);
          }
          if (!sourceMetadataLookup.has(normalized)) {
            sourceMetadataLookup.set(normalized, {
              url: source.url,
              source_type: source.source_type,
              file_id: source.file_id,
            });
          }
        }
      }

      const looksLikeFileName = (value: string | null | undefined) =>
        value ? /\.(pdf|docx?|xlsx?|pptx?|txt|csv|json|md)$/i.test(value) : false;

      const extractSourceInfo = (raw: string) => {
        let displayText = raw.trim();
        let downloadName: string | null = null;
        let sourceRef: string | null = null;
        let sourceType: 'file' | 'web_crawl' = 'file';

        const linkMatch = raw.match(/\[([^\]]+)\]\(([^)]+)\)/);
        if (linkMatch) {
          displayText = linkMatch[1].trim() || displayText;
          let linkTarget = linkMatch[2].trim();

          if (linkTarget.includes('|')) {
            const parts = linkTarget.split('|');
            linkTarget = parts[0];
            if (parts[1] === 'web_crawl') {
              sourceType = 'web_crawl';
            }
          }
          sourceRef = linkTarget;
        }

        const fromMatch = raw.match(/\(from\s+(.+?)\)$/i);
        if (fromMatch) {
          const reference = fromMatch[1].trim();
          if (looksLikeFileName(reference)) {
            downloadName = reference;
          } else if (!sourceRef) {
            sourceRef = reference;
          }
        }

        if (!downloadName) {
          const withoutPrefix = raw.replace(/^source\s*\d+[:\-]?\s*/i, '').trim();
          if (withoutPrefix && withoutPrefix !== raw.trim() && looksLikeFileName(withoutPrefix)) {
            downloadName = withoutPrefix;
          }
        }

        if (!downloadName && !sourceRef) {
          const quoted = raw.replace(/^"|"$/g, '').replace(/^'|'$/g, '').trim();
          if (looksLikeFileName(quoted)) {
            downloadName = quoted;
          }
        }

        if (downloadName) {
          downloadName = downloadName.replace(/^"|"$/g, '').replace(/^'|'$/g, '').trim();
          displayText = downloadName || displayText;
        }

        if (!displayText) {
          displayText = raw.trim();
        }

        const normalizedDisplay = displayText.trim().toLowerCase();
        const matchedFileId = normalizedDisplay ? sourceIdLookup.get(normalizedDisplay) : undefined;

        if (sourceRef && sourceRef.startsWith('http') && sourceType === 'file') {
          sourceType = 'web_crawl';
        }

        return {
          displayText,
          downloadName,
          sourceRef,
          matchedFileId,
          sourceType,
        };
      };

      const createInlineElements = (line: string, block: boolean = true): ReactNode[] => {
        const elements: ReactNode[] = [];
        const tokenRegex = /(\[.*?\]\(.*?\))|(\*\*.*?\*\*)/g;
        let lastIndex = 0;
        let match: RegExpExecArray | null;

        const pushText = (text: string) => {
          if (block && !text.trim()) {
            return;
          }
          elements.push(
            <span key={nextKey()} className={`${block ? 'block ' : ''}whitespace-pre-wrap`}>
              {text || (block ? ' ' : '\u00a0')}
            </span>
          );
        };

        const commonClasses = "inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium border border-[rgba(17,24,39,0.15)] rounded-md bg-white text-[#1f2937] shadow-[0_1px_2px_rgba(0,0,0,0.05)] hover:bg-[linear-gradient(135deg,rgba(69,98,187,0.1),rgba(2,241,124,0.1))] hover:border-[rgba(69,98,187,0.3)] hover:shadow-[0_3px_8px_rgba(69,98,187,0.15)] hover:-translate-y-[1px] transition-all no-underline mx-1 dark:bg-gray-800 dark:text-gray-100 dark:border-gray-700 dark:hover:bg-gray-700";

        while ((match = tokenRegex.exec(line)) !== null) {
          if (match.index > lastIndex) {
            pushText(line.slice(lastIndex, match.index));
          }

          const fullMatch = match[0];

          if (fullMatch.startsWith('**')) {
            const content = fullMatch.slice(2, -2);
            elements.push(
              <strong key={nextKey()} className="font-bold">
                {content}
              </strong>
            );
          } else {
            const linkMatch = fullMatch.match(/\[([^\]]+)\]\(([^)]+)\)/);
            if (linkMatch) {
              const [, label, rawLinkTarget] = linkMatch;
              const { displayText, downloadName, matchedFileId, sourceType } = extractSourceInfo(`[${label}](${rawLinkTarget})`);

              let linkTarget = rawLinkTarget;
              let detectedSourceType = sourceType;
              if (rawLinkTarget.includes('|')) {
                const parts = rawLinkTarget.split('|');
                linkTarget = parts[0];
                if (parts[1] === 'web_crawl') {
                  detectedSourceType = 'web_crawl';
                }
              }

              const fileId = matchedFileId ?? linkTarget;
              const fileName = downloadName || displayText || label;

              if (detectedSourceType === 'web_crawl') {
                elements.push(
                  <a
                    key={nextKey()}
                    href={linkTarget.startsWith('http') ? linkTarget : `https://${linkTarget}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={commonClasses}
                  >
                    <ExternalLink className="w-3 h-3 text-[rgba(107,114,128,0.7)]" />
                    {displayText.trim() || 'View source'}
                  </a>
                );
              } else {
                elements.push(
                  <button
                    key={nextKey()}
                    type="button"
                    className={commonClasses}
                    onClick={() => handleDownloadSource(fileId, fileName)}
                  >
                    <FileText className="w-3 h-3 text-[rgba(107,114,128,0.7)]" />
                    {displayText.trim() || 'Download source'}
                  </button>
                );
              }
            }
          }

          lastIndex = match.index + fullMatch.length;
        }

        const remaining = line.slice(lastIndex);
        pushText(remaining);

        return elements;
      };

      const isTableSeparatorCell = (cell: string) => /^:?-{3,}:?$/.test(cell.trim());

      const isTableLine = (line: string): boolean => {
        const trimmed = line.trim();
        if (!trimmed) return false;
        if (/^\**\s*sources?\s*:?\s*\**$/i.test(trimmed)) return false;
        if (/^-\s+/.test(trimmed)) return false;
        const pipeCount = (trimmed.match(/\|/g) || []).length;
        if (pipeCount < 2) return false;
        return true;
      };

      const splitRow = (line: string) =>
        line
          .trim()
          .replace(/^\||\|$/g, '')
          .split('|')
          .map((cell) => cell.trim());

      const renderTable = (tableLines: string[]): ReactNode | null => {
        const sanitized = tableLines
          .map((line) => line.trim())
          .filter((line) => line.length > 0);

        if (sanitized.length === 0) {
          return null;
        }

        const rows = sanitized.map(splitRow).filter((row) => row.length > 0);

        if (rows.length === 0) {
          return null;
        }

        const headerCells = rows[0];
        let bodyRows = rows.slice(1);

        if (bodyRows.length > 0 && bodyRows[0].every(isTableSeparatorCell)) {
          bodyRows = bodyRows.slice(1);
        }

        if (headerCells.length === 0) {
          return null;
        }

        const columnCount = headerCells.length;

        return (
          <div key={nextKey()} className="overflow-x-auto rounded-md border border-border bg-background">
            <table className="w-full min-w-max border-collapse text-xs sm:text-sm">
              <thead className="bg-muted/60">
                <tr>
                  {headerCells.map((cell) => (
                    <th key={nextKey()} className="px-3 py-2 text-left font-semibold text-foreground">
                      {createInlineElements(cell, false)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {bodyRows.length === 0 ? (
                  <tr key={nextKey()} className="bg-background">
                    {Array.from({ length: columnCount }).map(() => (
                      <td key={nextKey()} className="px-3 py-2" />
                    ))}
                  </tr>
                ) : (
                  bodyRows.map((row) => {
                    const cells = [...row];
                    while (cells.length < columnCount) {
                      cells.push('');
                    }
                    return (
                      <tr key={nextKey()} className="odd:bg-background even:bg-muted/20">
                        {cells.map((cell) => (
                          <td key={nextKey()} className="px-3 py-2 align-top text-foreground">
                            {createInlineElements(cell, false)}
                          </td>
                        ))}
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        );
      };

      const sourcesNodes: ReactNode[] = [];

      for (let i = 0; i < lines.length; i += 1) {
        const rawLine = lines[i];
        const trimmed = rawLine.trim();
        const isSourcesHeading = /^\**\s*sources?\s*:?\s*\**$/i.test(trimmed);

        if (isSourcesHeading) {
          inSourcesSection = true;
          continue;
        }

        if (inSourcesSection && /^-\s*(.+)$/.test(trimmed)) {
          const label = trimmed.replace(/^-\s*/, '');
          const linkMatch = label.match(/\[([^\]]+)\]\(([^)]+)\)/);

          let sourceName = label;
          if (linkMatch) {
            sourceName = linkMatch[1];
          }
          const normalizedName = sourceName.trim().toLowerCase();
          const metadata = sourceMetadataLookup.get(normalizedName);

          const commonButtonClass = "flex items-center justify-between gap-2 px-3 py-2 text-sm font-medium border border-[rgba(17,24,39,0.15)] rounded-md bg-white text-[#1f2937] shadow-[0_1px_2px_rgba(0,0,0,0.05)] hover:bg-[linear-gradient(135deg,rgba(69,98,187,0.1),rgba(2,241,124,0.1))] hover:border-[rgba(69,98,187,0.3)] hover:shadow-[0_3px_8px_rgba(69,98,187,0.15)] hover:-translate-y-[1px] transition-all cursor-pointer no-underline w-full dark:bg-gray-800 dark:text-gray-100 dark:border-gray-700 dark:hover:bg-gray-700";

          if (metadata && (metadata.source_type === 'web_crawl' || metadata.url)) {
            const url = metadata.url || '';
            sourcesNodes.push(
              <a
                key={nextKey()}
                href={url.startsWith('http') ? url : `https://${url}`}
                target="_blank"
                rel="noopener noreferrer"
                className={commonButtonClass}
              >
                <span className="truncate text-left flex-1">{sourceName}</span>
                <ExternalLink className="w-4 h-4 text-[rgba(107,114,128,0.7)] shrink-0" />
              </a>
            );
          } else if (metadata && metadata.file_id) {
            sourcesNodes.push(
              <button
                key={nextKey()}
                type="button"
                className={commonButtonClass}
                onClick={() => handleDownloadSource(metadata.file_id!, sourceName)}
              >
                <span className="truncate text-left flex-1">{sourceName}</span>
                <Download className="w-4 h-4 text-[rgba(107,114,128,0.7)] shrink-0" />
              </button>
            );
          } else if (linkMatch) {
            const [, fileName, rawLinkTarget] = linkMatch;
            const matchedFileId = normalizedName ? sourceIdLookup.get(normalizedName) : undefined;

            let linkTarget = rawLinkTarget;
            let sourceType: 'file' | 'web_crawl' = 'file';
            if (rawLinkTarget.includes('|')) {
              const parts = rawLinkTarget.split('|');
              linkTarget = parts[0];
              if (parts[1] === 'web_crawl') {
                sourceType = 'web_crawl';
              }
            }
            if (linkTarget.startsWith('http')) {
              sourceType = 'web_crawl';
            }

            const resolvedFileId = matchedFileId ?? linkTarget;

            if (sourceType === 'web_crawl') {
              sourcesNodes.push(
                <a
                  key={nextKey()}
                  href={linkTarget.startsWith('http') ? linkTarget : `https://${linkTarget}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={commonButtonClass}
                >
                  <span className="truncate text-left flex-1">{fileName}</span>
                  <ExternalLink className="w-4 h-4 text-[rgba(107,114,128,0.7)] shrink-0" />
                </a>
              );
            } else {
              sourcesNodes.push(
                <button
                  key={nextKey()}
                  type="button"
                  className={commonButtonClass}
                  onClick={() => handleDownloadSource(resolvedFileId, fileName)}
                >
                  <span className="truncate text-left flex-1">{fileName}</span>
                  <Download className="w-4 h-4 text-[rgba(107,114,128,0.7)] shrink-0" />
                </button>
              );
            }
          } else {
            const { displayText, downloadName, sourceRef, matchedFileId, sourceType } = extractSourceInfo(label);
            const reference = matchedFileId ?? sourceRef ?? downloadName ?? (looksLikeFileName(label) ? label : null);

            if (reference) {
              const isWebCrawl = sourceType === 'web_crawl' || (typeof reference === 'string' && reference.startsWith('http'));

              if (isWebCrawl) {
                sourcesNodes.push(
                  <a
                    key={nextKey()}
                    href={reference.startsWith('http') ? reference : `https://${reference}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={commonButtonClass}
                  >
                    <span className="truncate text-left flex-1">{displayText}</span>
                    <ExternalLink className="w-4 h-4 text-[rgba(107,114,128,0.7)] shrink-0" />
                  </a>
                );
              } else {
                sourcesNodes.push(
                  <button
                    key={nextKey()}
                    type="button"
                    className={commonButtonClass}
                    onClick={() => handleDownloadSource(reference, downloadName ?? displayText)}
                  >
                    <span className="truncate text-left flex-1">{displayText}</span>
                    <Download className="w-4 h-4 text-[rgba(107,114,128,0.7)] shrink-0" />
                  </button>
                );
              }
            } else {
              sourcesNodes.push(
                <span key={nextKey()} className="block whitespace-pre-wrap text-sm text-muted-foreground px-1">
                  {label}
                </span>
              );
            }
          }
          continue;
        }

        if (inSourcesSection && trimmed.length === 0) {
          continue;
        }

        if (inSourcesSection && trimmed.length > 0 && !trimmed.startsWith('-')) {
          inSourcesSection = false;
        }

        if (!inSourcesSection && isTableLine(rawLine)) {
          const tableLines: string[] = [];
          let j = i;
          while (j < lines.length && isTableLine(lines[j])) {
            tableLines.push(lines[j]);
            j += 1;
          }

          const tableNode = renderTable(tableLines);
          if (tableNode) {
            nodes.push(tableNode);
          }

          i = j - 1;
          continue;
        }

        // Check for Markdown headings (# to ######)
        const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
        if (headingMatch && !inSourcesSection) {
          const level = headingMatch[1].length;
          const headingContent = headingMatch[2];
          const headingClasses: Record<number, string> = {
            1: 'text-2xl font-bold mt-2 mb-1',
            2: 'text-xl font-bold mt-1.5 mb-1',
            3: 'text-lg font-semibold mt-1 mb-0.5',
            4: 'text-base font-semibold mt-1 mb-0.5',
            5: 'text-sm font-semibold mt-1 mb-0.5',
            6: 'text-sm font-medium mt-1 mb-0.5',
          };
          const HeadingTag = `h${level}` as keyof JSX.IntrinsicElements;
          nodes.push(
            <HeadingTag key={`${messageId}-heading-${i}`} className={headingClasses[level]}>
              {createInlineElements(headingContent, false)}
            </HeadingTag>
          );
          continue;
        }

        // Check for Markdown lists (- or * for ul, 1. for ol)
        const listMatch = trimmed.match(/^([-*]|\d+\.)\s+(.+)$/);
        if (listMatch && !inSourcesSection) {
          const isOrdered = /^\d+/.test(listMatch[1]);
          const listLines: string[] = [];
          let j = i;

          while (j < lines.length) {
            const currentTrimmed = lines[j].trim();
            const currentMatch = currentTrimmed.match(/^([-*]|\d+\.)\s+(.+)$/);
            if (!currentMatch) break;
            listLines.push(currentTrimmed);
            j++;
          }

          const ListTag = isOrdered ? 'ol' : 'ul';
          nodes.push(
            <ListTag
              key={`${messageId}-list-${i}`}
              className={`my-3 ml-6 ${isOrdered ? 'list-decimal' : 'list-disc'} space-y-1`}
            >
              {listLines.map((line, idx) => {
                const itemContent = line.replace(/^([-*]|\d+\.)\s+/, '');
                return (
                  <li key={`${messageId}-list-${i}-item-${idx}`} className="pl-1">
                    {createInlineElements(itemContent, false)}
                  </li>
                );
              })}
            </ListTag>
          );

          i = j - 1;
          continue;
        }

        // Wrap each line in a container to keep inline elements together
        const lineNodes = createInlineElements(rawLine, false); // block=false
        if (lineNodes.length > 0) {
          nodes.push(
            <div key={`${messageId}-line-${i}`} className="min-h-[1.5em]">
              {lineNodes}
            </div>
          );
        } else {
          // Empty line
          nodes.push(<div key={`${messageId}-line-${i}`} className="h-1" />);
        }
      }

      if (sourcesNodes.length > 0) {
        nodes.push(
          <div key={`${messageId}-sources-container`} className="mt-2 pt-2 border-t border-border/40 bg-muted/30 rounded-lg p-2 space-y-1">
            <span className="block text-xs font-bold uppercase text-muted-foreground/80 mb-1">
              Sources:
            </span>
            <div className="flex flex-col gap-1 w-full">
              {sourcesNodes}
            </div>
          </div>
        );
      }

      return nodes;
    },
    [handleDownloadSource]
  );

  const handleMessageScroll = useCallback(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const threshold = 40;
    const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < threshold;

    if (isAutoScrollRef.current !== isNearBottom) {
      isAutoScrollRef.current = isNearBottom;
      setIsAutoScroll(isNearBottom);
    }
  }, []);

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const isThinking = isLoading && !isStreaming;

  return (
    <DashboardLayout>
      <div className="flex flex-col space-y-6 min-h-[calc(100vh-140px)]">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-foreground dark:text-white">Leto Chat</h1>

          </div>
          <div className="flex flex-col sm:flex-row sm:items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-muted-foreground dark:text-gray-300">
                Select Knowledge Base:
              </span>
              <Select value={selectedCollection} onValueChange={setSelectedCollection}>
                <SelectTrigger className="w-full sm:w-64 bg-background dark:bg-gray-800 text-foreground dark:text-white">
                  <SelectValue placeholder="Select a knowledge base" />
                </SelectTrigger>
                <SelectContent className="bg-background dark:bg-gray-800 text-foreground dark:text-white">
                  {activeCollections.map((collection) => (
                    <SelectItem key={collection.collection_id} value={collection.collection_id}>
                      {collection.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        <Card className="flex flex-col min-h-[calc(100vh-220px)] bg-card dark:bg-gray-900">
          <CardHeader>
            <div className="flex items-center justify-end">
              {hasMessages && (
                <Button variant="outline" onClick={clearChat} size="sm">
                  Clear Chat
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="relative flex-1 flex flex-col min-h-0 overflow-hidden p-0 max-h-[calc(85vh-10rem)]">

            {!selectedCollection ? (
              <div className="flex-1 flex items-center justify-center text-muted-foreground dark:text-gray-300">

                Please select a knowledge base to start chatting
              </div>
            ) : (
              <div className="flex flex-1 flex-col min-h-0">
                <div
                  className="flex-1 overflow-y-auto space-y-4 px-4 pt-4"
                  ref={messagesContainerRef}
                  onScroll={handleMessageScroll}
                  onWheel={handleWheel}
                  onPointerDown={handleManualScrollIntent}
                  onTouchMove={handleTouchMove}
                >
                  {messages.length === 0 ? (
                    <div className="flex items-center justify-center text-muted-foreground dark:text-gray-300 h-[50vh]">
                      <div className="flex flex-col items-center gap-3 text-center">
                        <MessageSquare className="h-12 w-12 opacity-50" />
                        <p className="text-base font-medium">You can start the conversation by sending a message below.</p>
                      </div>
                    </div>
                  ) : (
                    messages.map((message) => {
                      const isUser = message.role === 'user';
                      const isFollowup = !isUser && message.isFollowup;
                      return (
                        <div
                          key={message.id}
                          className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
                        >
                          <div
                            className={`rounded-xl px-4 py-3 shadow-sm ${isUser
                              ? 'bg-primary text-primary-foreground max-w-[65%] dark:text-white'
                              : 'rounded-xl px-4 py-3 shadow-sm bg-muted border border-border/60 text-foreground max-w-[80%] dark:bg-gray-800 dark:text-gray-100'
                              }`}
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                              <div className="flex items-center gap-2.5">
                                <div
                                  className={`flex h-8 w-8 items-center justify-center rounded-full ${isUser
                                    ? 'bg-primary-foreground/20 text-primary-foreground'
                                    : 'bg-white text-foreground shadow-sm dark:bg-gray-900/80 dark:text-gray-100'
                                    }`}
                                >
                                  {isUser ? (
                                    <User className="h-4 w-4" />
                                  ) : (
                                    <img src={getAssetUrl('leto.svg')} alt="Leto logo" className="h-4 w-4" />
                                  )}
                                </div>
                                <span
                                  className={`text-sm font-semibold leading-none ${isUser ? 'text-primary-foreground dark:text-white' : 'text-foreground dark:text-gray-100'
                                    }`}
                                >
                                  {isUser ? 'You' : 'Leto Assistant'}
                                </span>
                              </div>
                              <p
                                className={`text-xs ${isUser
                                  ? 'text-primary-foreground/70 dark:text-white/70'
                                  : 'text-muted-foreground dark:text-gray-400'
                                  }`}
                              >
                                {formatTime(message.timestamp)}
                              </p>
                            </div>
                            <div className="flex flex-col gap-0.5 text-sm leading-snug">
                              {renderMessageContent(message.content, message.id, message.sources)}
                            </div>
                          </div>
                        </div>
                      );
                    })
                  )}
                  {isThinking && (
                    <div className="flex justify-start pt-2">
                      <div className="bg-muted border border-border/60 rounded-xl px-4 py-3 shadow-sm dark:bg-gray-800 dark:text-gray-100 max-w-[80%]">
                        <div className="flex items-center space-x-2">
                          <img src={getAssetUrl('leto.svg')} alt="Leto logo" className="h-4 w-4" />
                          <div className="flex items-center space-x-1">
                            <span className="text-sm text-muted-foreground dark:text-gray-300">
                              Leto is thinking
                            </span>
                            <div className="typing-dots">
                              <span className="dot"></span>
                              <span className="dot"></span>
                              <span className="dot"></span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                <form
                  onSubmit={sendMessage}
                  className="sticky bottom-0 left-0 right-0 z-10 flex items-center gap-2 bg-card p-3 border-t border-border/60 dark:bg-gray-900"
                >
                  <input
                    type="text"
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    placeholder="Type your message..."
                    className="flex-1 h-11 px-3 border border-input rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring dark:bg-gray-800 dark:text-white"
                    disabled={isLoading || isStreaming}
                  />
                  {isStreaming && (
                    <Button type="button" variant="secondary" onClick={handleStopStreaming} className="h-11">
                      Stop
                    </Button>
                  )}
                  <Button
                    type="submit"
                    disabled={isLoading || isStreaming || !inputMessage.trim()}
                    className="h-11"
                  >
                    <Send className="h-4 w-4" />
                  </Button>
                </form>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
