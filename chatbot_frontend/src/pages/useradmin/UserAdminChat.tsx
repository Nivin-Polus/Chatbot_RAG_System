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
import { MessageSquare, Send, Loader2, User } from 'lucide-react';
import { ChatMessage, ChatSource, Collection } from '@/types/auth';
import { toast } from 'sonner';
import { apiGet, apiPost } from '@/utils/api';

export default function UserAdminChat() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
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
  const [accessibleFileIds, setAccessibleFileIds] = useState<string[]>([]);
  const [accessibleFileNames, setAccessibleFileNames] = useState<string[]>([]);

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

  useEffect(() => {
    if (!sessionId) {
      const newSessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
      setSessionId(newSessionId);
    }
  }, [sessionId]);

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
        false // Don't show error toast for this call
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
    (rawContent: string, sources?: ChatSource[]) => {
      const content = rawContent && rawContent.trim().length > 0
        ? rawContent
        : 'I was unable to generate a response.';
      const messageId = `assistant_${Date.now()}`;
      const timestamp = new Date();

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
        },
      ]);

      return new Promise<void>((resolve) => {
        setIsStreaming(true);

        const completeStream = () => {
          if (typingTimeoutRef.current) {
            window.clearTimeout(typingTimeoutRef.current);
            typingTimeoutRef.current = null;
          }
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === messageId ? { ...msg, content, sources } : msg
            )
          );
          scrollToBottom();
          stopStreamingRef.current = null;
          setIsStreaming(false);
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
            completeStream();
            return;
          }

          index += 1;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === messageId
                ? { ...msg, content: content.slice(0, index), sources }
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
    [scrollToBottom]
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

    // Prepare conversation history (last ~10 messages)
    const conversationHistory = updatedMessages
      .slice(-10)
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

      const assistantContent =
        dataResponse.response || dataResponse.answer || dataResponse.content || 'I was unable to generate a response.';

      const sources: ChatSource[] | undefined = Array.isArray(dataResponse.sources)
        ? dataResponse.sources
            .map<ChatSource | null>((item: { file_name?: unknown; file_id?: unknown } | null | undefined) => {
              if (!item || typeof item !== 'object') {
                return null;
              }
              const fileName = typeof item.file_name === 'string' ? item.file_name : undefined;
              const fileId = typeof item.file_id === 'string' ? item.file_id : undefined;

              if (!fileName) {
                return null;
              }
              return {
                file_name: fileName,
                file_id: fileId,
              } satisfies ChatSource;
            })
            .filter((value): value is ChatSource => value !== null)
        : undefined;

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

  const clearChat = () => {
    if (stopStreamingRef.current) {
      stopStreamingRef.current();
    }
    setMessages([]);
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
    setSessionId(newSessionId);
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
      if (Array.isArray(messageSources)) {
        for (const source of messageSources) {
          if (!source || !source.file_name || !source.file_id) continue;
          const normalized = source.file_name.trim().toLowerCase();
          if (!normalized) continue;
          if (!sourceIdLookup.has(normalized)) {
            sourceIdLookup.set(normalized, source.file_id);
          }
        }
      }

      const looksLikeFileName = (value: string | null | undefined) =>
        value ? /\.(pdf|docx?|xlsx?|pptx?|txt|csv|json|md)$/i.test(value) : false;

      const extractSourceInfo = (raw: string) => {
        let displayText = raw.trim();
        let downloadName: string | null = null;
        let sourceRef: string | null = null;

        const linkMatch = raw.match(/\[([^\]]+)\]\(([^)]+)\)/);
        if (linkMatch) {
          displayText = linkMatch[1].trim() || displayText;
          sourceRef = linkMatch[2].trim();
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
          const withoutPrefix = raw.replace(/^source\s*\d+[:-]?\s*/i, '').trim();
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

        return {
          displayText,
          downloadName,
          sourceRef,
          matchedFileId,
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
        const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
        let lastIndex = 0;
        let match: RegExpExecArray | null;

        const pushText = (text: string) => {
          elements.push(
            <span key={nextKey()} className={`${block ? 'block ' : ''}whitespace-pre-wrap`}>
              {text || (block ? ' ' : '\u00a0')}
            </span>
          );
        };

        while ((match = linkRegex.exec(line)) !== null) {
          if (match.index > lastIndex) {
            pushText(line.slice(lastIndex, match.index));
          }

          const [, label, linkTarget] = match;
          const { displayText, downloadName, matchedFileId } = extractSourceInfo(label);
          // linkTarget is the file_id from backend format: [filename](file_id)
          const fileId = matchedFileId ?? linkTarget;
          const fileName = downloadName || displayText || label;
          if (canDownloadSource(fileId, fileName)) {
            elements.push(
              <button
                key={nextKey()}
                type="button"
                className={`${block ? 'block' : 'inline-flex'} text-primary underline underline-offset-2`}
                onClick={() => handleDownloadSource(fileId, fileName)}
              >
                {displayText.trim() || 'Download source'}
              </button>
            );
          } else {
            pushText(displayText.trim() || label);
          }

          lastIndex = match.index + match[0].length;
        }

        const remaining = line.slice(lastIndex);
        pushText(remaining);

        return elements;
      };

      const isTableSeparatorCell = (cell: string) => /^:?-{3,}:?$/.test(cell.trim());

      const isTableLine = (line: string): boolean => {
        const trimmed = line.trim();
        if (!trimmed) return false;
        if (/^sources?:\s*$/i.test(trimmed)) return false;
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

      for (let i = 0; i < lines.length; i += 1) {
        const rawLine = lines[i];
        const trimmed = rawLine.trim();
        const isSourcesHeading = /^\**\s*sources?\s*:?\s*\**$/i.test(trimmed);

        if (isSourcesHeading) {
          nodes.push(
            <span
              key={nextKey()}
              className="block text-xs font-semibold uppercase text-muted-foreground"
            >
              Sources:
            </span>
          );
          inSourcesSection = true;
          continue;
        }

        if (inSourcesSection) {
          if (trimmed.length === 0) {
            nodes.push(
              <span key={nextKey()} className="block whitespace-pre-wrap">
                {' '}
              </span>
            );
            continue;
          }

          const bulletPattern = /^[-•\u2022]\s*/;
          const normalizedLabel = trimmed.replace(bulletPattern, '').trim();
          const label = normalizedLabel.length > 0 ? normalizedLabel : trimmed;

          // Parse markdown link format: [filename](file_id)
          const linkMatch = label.match(/\[([^\]]+)\]\(([^)]+)\)/);
          
          if (linkMatch) {
            const [, fileName, linkTarget] = linkMatch;
            const normalizedName = fileName.trim().toLowerCase();
            const matchedFileId = normalizedName ? sourceIdLookup.get(normalizedName) : undefined;
            const resolvedFileId = matchedFileId ?? linkTarget;
            if (canDownloadSource(resolvedFileId, fileName)) {
              nodes.push(
                <button
                  key={nextKey()}
                  type="button"
                  className="block text-left text-primary underline underline-offset-2"
                  onClick={() => handleDownloadSource(resolvedFileId, fileName)}
                >
                  {fileName}
                </button>
              );
            } else {
              nodes.push(
                <span key={nextKey()} className="block whitespace-pre-wrap">
                  {fileName}
                </span>
              );
            }
          } else {
            // Fallback for old format
            const { displayText, downloadName, sourceRef, matchedFileId } = extractSourceInfo(label);
            const reference = matchedFileId ?? sourceRef ?? downloadName ?? (looksLikeFileName(label) ? label : null);
            if (reference && canDownloadSource(reference, downloadName)) {
              nodes.push(
                <button
                  key={nextKey()}
                  type="button"
                  className="block text-left text-primary underline underline-offset-2"
                  onClick={() => handleDownloadSource(reference, downloadName ?? displayText)}
                >
                  {displayText}
                </button>
              );
            } else {
              nodes.push(
                <span key={nextKey()} className="block whitespace-pre-wrap">
                  {label}
                </span>
              );
            }
          }
          continue;
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

        nodes.push(...createInlineElements(rawLine));
      }

      return nodes;
    },
    [handleDownloadSource, accessibleIdsSet, accessibleNamesSet]
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
                            className={`rounded-xl px-4 py-3 shadow-sm ${
                              isUser
                                ? 'bg-primary text-primary-foreground max-w-[65%] dark:text-white'
                                : 'bg-muted border border-border/60 text-foreground max-w-[80%] dark:bg-gray-800 dark:text-gray-100'
                            }`}
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                              <div className="flex items-center gap-2.5">
                                <div
                                  className={`flex h-8 w-8 items-center justify-center rounded-full ${
                                    isUser
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
                                  className={`text-sm font-semibold leading-none ${
                                    isUser ? 'text-primary-foreground dark:text-white' : 'text-foreground dark:text-gray-100'
                                  }`}
                                >
                                  {isUser ? 'You' : 'Leto Assistant'}
                                </span>
                              </div>
                              <p
                                className={`text-xs ${
                                  isUser
                                    ? 'text-primary-foreground/70 dark:text-white/70'
                                    : 'text-muted-foreground dark:text-gray-400'
                                }`}
                              >
                                {formatTime(message.timestamp)}
                              </p>
                            </div>
                            <div className="space-y-2 text-sm leading-relaxed">
                              {renderMessageContent(message.content, message.id, message.sources)}
                            </div>
                          </div>
                        </div>
                      );
                    })
                  )}
                  {isLoading && !isStreaming && (
                    <div className="flex justify-start">
                      <div className="bg-muted border rounded-lg px-4 py-3 dark:bg-gray-800 dark:text-gray-300">
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
