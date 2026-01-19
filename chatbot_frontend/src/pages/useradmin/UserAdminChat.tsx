import { useState, useEffect, useRef, useCallback, useMemo, type ReactNode } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { DashboardLayout } from '@/components/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { MessageSquare, Send, Loader2, User, ExternalLink, FileText, Download } from 'lucide-react';
import { ChatMessage, ChatSource, Collection } from '@/types/auth';
import { toast } from 'sonner';
import { apiGet, apiPost } from '@/utils/api';
import { saveSession, getSession, getSessions } from '@/utils/chatStorage';
import { useSearchParams } from 'react-router-dom';

export default function UserAdminChat() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const sessionIdRef = useRef<string | null>(null); // NEW: Ref to track current session ID

  // Keep ref in sync
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedCollection, setSelectedCollection] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const typingTimeoutRef = useRef<number | null>(null);
  const stopStreamingRef = useRef<(() => void) | null>(null);
  const [isAutoScroll, setIsAutoScroll] = useState(true);
  const isAutoScrollRef = useRef(true);
  const hasMessages = messages.length > 0;
  const saveTimeoutRef = useRef<number | null>(null);
  const [accessibleFileIds, setAccessibleFileIds] = useState<string[]>([]);
  const [accessibleFileNames, setAccessibleFileNames] = useState<string[]>([]);
  const [searchParams, setSearchParams] = useSearchParams();

  const selectedCollectionDetails = useMemo(
    () => collections.find((collection) => collection.collection_id === selectedCollection) ?? null,
    [collections, selectedCollection]
  );

  const accessibleIdsSet = useMemo(() => new Set(accessibleFileIds.filter(Boolean)), [accessibleFileIds]);
  const accessibleNamesSet = useMemo(
    () => new Set(accessibleFileNames.filter(Boolean).map((name) => name.toLowerCase())),
    [accessibleFileNames]
  );

  const knowledgeBaseLabel = useMemo(() => {
    if (!selectedCollectionDetails) {
      return 'Select Knowledge Base:';
    }

    return 'Knowledge Base:';
  }, [selectedCollectionDetails]);

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

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      if (isAutoScrollRef.current) {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }
    });
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
  }, [searchParams, user?.user_id]); // Removed sessionId dependency

  // Save chat history to localStorage once after assistant finishes streaming
  // Modified to use shouldTouch=false
  useEffect(() => {
    if (!isStreaming && selectedCollection && user?.user_id && messages.length > 0 && sessionId) {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
      saveTimeoutRef.current = window.setTimeout(() => {
        saveSession(sessionId, messages, selectedCollection, user.user_id, user.role || 'useradmin', false);

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

  const fetchCollections = useCallback(async () => {
    try {
      const response = await apiGet(
        `${import.meta.env.VITE_API_BASE_URL}/collections/`,
        user?.access_token,
        false
      );

      if (response.ok) {
        const data: Collection[] = await response.json();
        setCollections(data);
        setSelectedCollection((current) => {
          if (current && data.some((collection) => collection.collection_id === current)) {
            return current;
          }
          return data.length > 0 ? data[0].collection_id : '';
        });
      } else {
        console.error('Failed to fetch collections, status:', response.status);
        setCollections([]);
        setSelectedCollection('');
      }
    } catch (error) {
      console.error('Error fetching collections:', error);
      setCollections([]);
      setSelectedCollection('');
    }
  }, [user?.access_token]);

  useEffect(() => {
    if (user?.access_token) {
      console.log('User available, fetching collections...');
      fetchCollections();
    } else {
      console.log('User not available yet, waiting...');
    }
  }, [user?.access_token, fetchCollections]);

  // Removed fallback to website_id - always use proper collection_id

  useEffect(() => {
    const loadAccessibleFiles = async () => {
      if (!selectedCollection || !user?.access_token) {
        setAccessibleFileIds([]);
        setAccessibleFileNames([]);
        return;
      }

      try {
        const response = await apiGet(
          `${import.meta.env.VITE_API_BASE_URL}/files/list?collection_id=${selectedCollection}`,
          user.access_token
        );

        if (!response.ok) {
          setAccessibleFileIds([]);
          setAccessibleFileNames([]);
          return;
        }

        const data = await response.json();
        const ids: string[] = [];
        const names: string[] = [];
        if (Array.isArray(data)) {
          data.forEach((item) => {
            if (item?.file_id) ids.push(String(item.file_id));
            if (item?.file_name) names.push(String(item.file_name));
          });
        }
        setAccessibleFileIds(ids);
        setAccessibleFileNames(names);
      } catch (error) {
        console.error('Failed to load accessible files', error);
        setAccessibleFileIds([]);
        setAccessibleFileNames([]);
      }
    };

    loadAccessibleFiles();
  }, [selectedCollection, user?.access_token]);

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

              saveSession(targetSessionId, updatedMsgs, selectedCollection, user.user_id, user.role || 'useradmin', true);
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
            scrollToBottom();
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
            // Optional logic for background
          }

          if (sessionIdRef.current !== targetSessionId) {
            saveProgressToStorage(content);
            resolve();
            return;
          }

          index += 1;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === messageId
                ? { ...msg, content: content.slice(0, index), sources, isFollowup }
                : msg
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

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || !selectedCollection || isLoading || isStreaming) {
      return;
    }

    // Store the message content before clearing the input
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

    // Prepare conversation history (last ~20 messages)
    const conversationHistory = updatedMessages
      .slice(-20)
      .map(msg => ({
        role: msg.role,
        content: msg.content,
        timestamp: msg.timestamp.toISOString()
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

      type ChatApiResponse = {
        answer?: string;
        response?: string;
        content?: string;
        sources?: Array<{ file_name?: string; file_id?: string }>;
        detail?: string;
        message?: string;
        error?: string;
        is_generic?: boolean;
        is_followup?: boolean;
        followup_questions?: string;
      };
      let data: ChatApiResponse | null = null;
      try {
        data = (await response.json()) as ChatApiResponse;
      } catch (parseError) {
        data = null;
      }

      if (!response.ok) {
        setIsLoading(false);
        setIsStreaming(false);
        stopStreamingRef.current = null;

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

      const dataResponse: ChatApiResponse = data ?? {};

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
      assistantContent = assistantContent
        .replace(/\r?\n+[\s>*-]*\*{0,2}\s*Sources?\s*:?\s*\*{0,2}\s*[\s\S]*$/i, '')
        .replace(/\r?\n+Sources?\s*:[\s\S]*$/i, '')
        .trim();

      const sources: ChatSource[] | undefined = isGeneric
        ? undefined
        : Array.isArray(dataResponse.sources)
          ? dataResponse.sources
            .map<ChatSource | null>((item: { file_name?: unknown; file_id?: unknown; source_type?: unknown; url?: unknown } | null | undefined) => {
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
    } catch (error) {
      toast.error('Failed to send message');
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
      setIsLoading(false);
      setIsStreaming(false);
      stopStreamingRef.current = null;
    } finally {
      if (typingTimeoutRef.current === null) {
        setIsLoading(false);
      }
      scrollToBottom();
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
      if (!sourceRef && !sourceName) {
        return;
      }

      const normalizedSourceName = sourceName?.trim();
      const normalizedRef = sourceRef?.trim();

      const isAccessible = () => {
        if (normalizedRef) {
          if (accessibleIdsSet.has(normalizedRef)) return true;
          if (accessibleNamesSet.has(normalizedRef.toLowerCase())) return true;
        }
        if (normalizedSourceName) {
          if (accessibleIdsSet.has(normalizedSourceName)) return true;
          if (accessibleNamesSet.has(normalizedSourceName.toLowerCase())) return true;
        }
        return false;
      };

      if (!isAccessible()) {
        toast.error('You do not have access to download this source.');
        return;
      }

      if (!user?.access_token) {
        toast.error('Unable to download source.');
        return;
      }

      try {
        // Use the exact same approach as the working files section
        console.log('Downloading source:', { sourceRef, sourceName, url: `${import.meta.env.VITE_API_BASE_URL}/files/download/${sourceRef}` });
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
          const errorText = await response.text();
          console.error('Download failed:', { status: response.status, statusText: response.statusText, errorText });
          if (response.status === 404) {
            toast.error('Source file not found');
          } else if (response.status === 403) {
            toast.error('You do not have permission to download this file');
          } else {
            toast.error(`Download failed: ${response.status} ${response.statusText}`);
          }
        }
      } catch (error) {
        console.error('Download error:', error);
        toast.error('Failed to download source file');
      }
    },
    [user?.access_token, accessibleIdsSet, accessibleNamesSet]
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
          if (!source || !source.file_name) continue;
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

      const canDownloadSource = (reference: string | null | undefined, downloadName?: string | null) => {
        const normalizedReference = reference?.trim();
        const normalizedDownload = downloadName?.trim();

        if (normalizedReference) {
          if (accessibleIdsSet.has(normalizedReference)) return true;
          if (accessibleNamesSet.has(normalizedReference.toLowerCase())) return true;
        }

        if (normalizedDownload) {
          if (accessibleIdsSet.has(normalizedDownload)) return true;
          if (accessibleNamesSet.has(normalizedDownload.toLowerCase())) return true;
        }

        return false;
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
              } else if (canDownloadSource(fileId, fileName)) {
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
              } else {
                pushText(displayText.trim() || label);
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
          const bulletPattern = /^[-•\u2022]\s*/;
          const normalizedLabel = trimmed.replace(bulletPattern, '').trim();
          const label = normalizedLabel.length > 0 ? normalizedLabel : trimmed;
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
          } else if (metadata && metadata.file_id && canDownloadSource(metadata.file_id, sourceName)) {
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
            } else if (canDownloadSource(resolvedFileId, fileName)) {
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
            } else {
              sourcesNodes.push(
                <span key={nextKey()} className="block whitespace-pre-wrap text-sm text-muted-foreground px-1">
                  {fileName}
                </span>
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
                    <span className="truncate text-left flex-1">{label}</span>
                    <ExternalLink className="w-4 h-4 text-[rgba(107,114,128,0.7)] shrink-0" />
                  </a>
                );
              } else if (canDownloadSource(reference, downloadName)) {
                sourcesNodes.push(
                  <button
                    key={nextKey()}
                    type="button"
                    className={commonButtonClass}
                    onClick={() => handleDownloadSource(reference, downloadName ?? displayText)}
                  >
                    <span className="truncate text-left flex-1">{label}</span>
                    <Download className="w-4 h-4 text-[rgba(107,114,128,0.7)] shrink-0" />
                  </button>
                );
              } else {
                sourcesNodes.push(
                  <span key={nextKey()} className="block whitespace-pre-wrap text-sm text-muted-foreground px-1">
                    {label}
                  </span>
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
    [accessibleIdsSet, accessibleNamesSet, handleDownloadSource]
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
  return (
    <DashboardLayout>
      <div className="flex flex-col space-y-6 min-h-[calc(100vh-140px)]">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground dark:text-white">Leto Chat</h1>
          </div>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium text-muted-foreground dark:text-gray-300">
                {knowledgeBaseLabel}
              </span>
              <Select value={selectedCollection} onValueChange={setSelectedCollection}>
                <SelectTrigger className="w-64 bg-background dark:bg-gray-800 text-foreground dark:text-white">
                  <SelectValue placeholder="Select a knowledge base" />
                </SelectTrigger>
                <SelectContent className="bg-background dark:bg-gray-800 text-foreground dark:text-white">
                  {collections.map((collection) => (
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
          <CardHeader className="flex-shrink-0">
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
                                    <img src="/chatbot/leto.svg" alt="Leto logo" className="h-4 w-4" />
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
                            <div className="space-y-0.5 text-sm leading-snug">
                              {renderMessageContent(message.content, message.id, message.sources)}
                            </div>
                          </div>
                        </div>
                      );
                    })
                  )}
                  {isLoading && !isStreaming && (
                    <div className="flex justify-start pt-2">
                      <div className="bg-muted border border-border/60 rounded-xl px-4 py-3 shadow-sm dark:bg-gray-800 dark:text-gray-100 max-w-[80%]">
                        <div className="flex items-center space-x-2">
                          <img src="/chatbot/leto.svg" alt="Leto logo" className="h-4 w-4" />
                          <div className="flex items-center space-x-2">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span className="text-sm text-muted-foreground dark:text-gray-300">
                              Leto is thinking...
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                <form
                  onSubmit={sendMessage}
                  className="sticky bottom-0 left-0 right-0 z-10 flex flex-col gap-2 bg-card py-3 px-4 border-t border-border/60 dark:bg-gray-900"
                >
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      placeholder="How can I help you today?"
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
                  </div>
                </form>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
