import { useState, useEffect, useRef, useCallback, type ReactNode } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { User, Send, Loader2, MessageSquare, ExternalLink, FileText, Download } from 'lucide-react';
import { useSidebar } from '@/components/ui/sidebar';
import { ChatMessage, ChatSource } from '@/types/auth';
import { toast } from 'sonner';
import { apiPost, apiDelete } from '@/utils/api';
import { saveSession, getSession, deleteSession, migratePluginSession, hasPluginSession, importTransferredSessions } from '@/utils/chatStorage';
import { useSearchParams } from 'react-router-dom';
import { getAssetUrl } from '@/utils/assets';
import { DashboardLayout } from '@/components/DashboardLayout';

const ChatContainer = ({ children }: { children: ReactNode }) => {
    const { open } = useSidebar();
    return (
        <div className={`flex flex-col space-y-4 pt-6 h-[calc(100vh-6rem)] transition-all duration-300 ${!open ? 'max-w-[90%] mx-auto w-full' : 'w-full'}`}>
            {children}
        </div>
    );
};

export default function PluginUserChat() {
    const { user } = useAuth();
    // Plugin users have their collection_id set during auto-login
    const selectedCollection = user?.collection_id || '';
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [inputMessage, setInputMessage] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isStreaming, setIsStreaming] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const messagesContainerRef = useRef<HTMLDivElement>(null);
    const typingTimeoutRef = useRef<number | null>(null);
    const [sessionId, setSessionId] = useState<string>('');
    const stopStreamingRef = useRef<(() => void) | null>(null);
    const [isAutoScroll, setIsAutoScroll] = useState(true);
    const isAutoScrollRef = useRef(true);
    const hasMessages = messages.length > 0;
    const saveTimeoutRef = useRef<number | null>(null);
    const [searchParams, setSearchParams] = useSearchParams();

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

    // Handle Session Loading (including plugin session migration)
    useEffect(() => {
        const urlSessionId = searchParams.get('session');
        const importPluginSession = searchParams.get('import_plugin_session');
        const transferToken = searchParams.get('transfer_token');

        // Handle backend-based session transfer (cross-origin safe) - imports ALL chat history
        if (transferToken && selectedCollection) {
            const doTransfer = async () => {
                const currentSessionId = await importTransferredSessions(
                    transferToken,
                    user?.user_id,
                    user?.role || 'plugin_user',
                    import.meta.env.VITE_API_BASE_URL
                );

                if (currentSessionId) {
                    // Load the current session (the one user was viewing in plugin)
                    const storedSession = getSession(currentSessionId);
                    if (storedSession) {
                        setMessages(storedSession.messages);
                        setSessionId(currentSessionId);
                        // Replace URL to remove the transfer parameter and set the session
                        setSearchParams({ session: currentSessionId }, { replace: true });
                        toast.success('Chat history imported successfully');
                        return;
                    }
                }
                // If transfer failed, clear the parameter and start fresh
                setSearchParams({}, { replace: true });
            };
            doTransfer();
            return;
        }

        // Handle local storage based plugin session migration (same-origin only)
        if (importPluginSession && selectedCollection) {
            // Check if this plugin session exists and hasn't been migrated yet
            if (hasPluginSession(importPluginSession)) {
                const migratedId = migratePluginSession(
                    importPluginSession,
                    user?.user_id,
                    user?.role || 'plugin_user',
                    selectedCollection
                );

                if (migratedId) {
                    // Load the migrated session
                    const storedSession = getSession(migratedId);
                    if (storedSession) {
                        setMessages(storedSession.messages);
                        setSessionId(migratedId);
                        // Replace URL to remove the import parameter and set the session
                        setSearchParams({ session: migratedId }, { replace: true });
                        return;
                    }
                }
            }
            // If migration failed or session doesn't exist, clear the parameter
            setSearchParams({}, { replace: true });
            return;
        }

        if (urlSessionId) {
            if (sessionId !== urlSessionId) {
                const storedFn = getSession(urlSessionId);
                if (storedFn) {
                    setMessages(storedFn.messages);
                    setSessionId(urlSessionId);
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
    }, [searchParams, user?.user_id, selectedCollection, user?.role]);

    // Save chat history to localStorage once after assistant finishes streaming
    useEffect(() => {
        if (!isStreaming && selectedCollection && user?.user_id && messages.length > 0 && sessionId) {
            if (saveTimeoutRef.current) {
                clearTimeout(saveTimeoutRef.current);
            }
            saveTimeoutRef.current = window.setTimeout(() => {
                saveSession(sessionId, messages, selectedCollection, user.user_id, user.role || 'plugin_user');

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

    const scrollToBottom = useCallback((smooth = true) => {
        if (messagesEndRef.current && isAutoScrollRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto' });
        }
    }, []);

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

    const streamAssistantResponse = useCallback(
        (rawContent: string, sources?: ChatSource[], isFollowup?: boolean) => {
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
                    isFollowup,
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
                            msg.id === messageId ? { ...msg, content, sources, isFollowup } : msg
                        )
                    );
                    if (isStreaming) {
                        scrollToBottom(false);
                    } else {
                        scrollToBottom();
                    }
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
        [scrollToBottom]
    );

    const sendMessage = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!inputMessage.trim() || !selectedCollection || isLoading || isStreaming) return;

        const messageContent = inputMessage.trim();

        const userMessage: ChatMessage = {
            id: `user_${Date.now()}`,
            role: 'user',
            content: messageContent,
            timestamp: new Date(),
        };

        const updatedMessages = [...messages, userMessage];
        setMessages(updatedMessages);
        setInputMessage('');
        setIsLoading(true);
        enableAutoScroll();

        try {
            const conversationHistory = updatedMessages.slice(-20).map((msg) => ({
                role: msg.role,
                content: msg.content,
                timestamp: msg.timestamp.toISOString(),
            }));

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

            if (!response.ok) {
                setIsLoading(false);
                setIsStreaming(false);
                stopStreamingRef.current = null;

                if (response.status === 401 || response.status === 403) {
                    toast.error('Incorrect credentials');
                    const errorMessage: ChatMessage = {
                        id: `assistant_error_${Date.now()}`,
                        role: 'assistant',
                        content: 'Incorrect credentials. Please verify your access details and try again.',
                        timestamp: new Date(),
                    };
                    setMessages((prev) => [...prev, errorMessage]);
                    return;
                }

                throw new Error('Failed to send message');
            }

            const data = await response.json();

            if (data.is_followup) {
                const followupContent = data.followup_questions || 'Could you please clarify your question?';
                await streamAssistantResponse(followupContent, undefined, true);
                setIsLoading(false);
                return;
            }

            let assistantContent =
                data.answer || data.response || data.content || 'I was unable to generate a response.';

            const isGenericResponse = (text: string) => {
                if (!text) return false;
                const normalized = text.trim();
                const genericPattern = /I apologize|I'm limited to providing information|not have any information|outside of my scope|I'm afraid I don't have enough information|I don't have access to information|I don't have any information about|I'm here to help with questions about your knowledge base documents|the provided context does not contain|does not contain any information|do not have enough details|without any relevant information|there are no sources that discuss|i do not have enough details to provide|my role is to assist based on the provided information|I do not have enough context|I have no relevant information|I don't have enough context|I do not have any relevant information|provide a meaningful response/i;
                return genericPattern.test(normalized);
            };

            const isGeneric = Boolean(data.is_generic) || isGenericResponse(assistantContent);

            assistantContent = assistantContent
                .replace(/\r?\n+[\s>*-]*\*{0,2}\s*Sources?\s*:?\s*\*{0,2}\s*[\s\S]*$/i, '')
                .replace(/\r?\n+Sources?\s*:[\s\S]*$/i, '')
                .trim();

            const sources: ChatSource[] | undefined = isGeneric
                ? undefined
                : Array.isArray(data.sources)
                    ? data.sources
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
                        .slice(0, 4)
                    : undefined;

            if (!isGeneric && sources && sources.length > 0) {
                assistantContent += '\n\n**Sources:**';
                sources.forEach((source) => {
                    const ref = source.url || source.file_id || 'source';
                    assistantContent += `\n- [${source.file_name}](${ref})`;
                });
            }

            await streamAssistantResponse(assistantContent, sources);
            setIsLoading(false);
        } catch (error) {
            console.error('Chat error:', error);
            toast.error('Failed to send message. Please try again.');
            const errorMessage: ChatMessage = {
                id: `assistant_error_${Date.now()}`,
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
        }
    };

    const clearChat = async () => {
        if (stopStreamingRef.current) {
            stopStreamingRef.current();
        }

        // Delete from backend if we have a session ID
        if (sessionId && user?.access_token) {
            try {
                await apiDelete(
                    `${import.meta.env.VITE_API_BASE_URL}/chat/sessions/${sessionId}`,
                    user.access_token,
                    false // Don't show error toast - session might not exist in backend
                );
            } catch (error) {
                // Silently fail - session might not exist in backend yet
                console.warn('Failed to delete session from backend:', error);
            }

            // Delete from localStorage
            deleteSession(sessionId, user.user_id, user.role || 'plugin_user');
        }

        setSearchParams({});
        enableAutoScroll();
    };

    const handleStopStreaming = useCallback(() => {
        stopStreamingRef.current?.();
    }, []);

    const handleDownloadSource = useCallback(
        async (fileIdOrRef: string, fileName?: string) => {
            if (!user?.access_token) {
                toast.error('Unable to download source.');
                return;
            }

            try {
                const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/files/download/${fileIdOrRef}`, {
                    headers: {
                        Authorization: `Bearer ${user.access_token}`,
                    },
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = fileName || 'download';
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
        [user?.access_token]
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

                            // Plugin style:
                            // background: #ffffff; color: #1f2937; border: 1px solid rgba(17, 24, 39, 0.15); boxShadow: 0 1px 2px rgba(0, 0, 0, 0.05);
                            // Hover: background: linear-gradient(135deg, rgba(69, 98, 187, 0.1), rgba(2, 241, 124, 0.1));
                            //        border-color: rgba(69, 98, 187, 0.3); boxShadow: 0 3px 8px rgba(69, 98, 187, 0.15); transform: translateY(-1px);

                            const commonClasses = "inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium border border-[rgba(17,24,39,0.15)] rounded-md bg-white text-[#1f2937] shadow-[0_1px_2px_rgba(0,0,0,0.05)] hover:bg-[linear-gradient(135deg,rgba(69,98,187,0.1),rgba(2,241,124,0.1))] hover:border-[rgba(69,98,187,0.3)] hover:shadow-[0_3px_8px_rgba(69,98,187,0.15)] hover:-translate-y-[1px] transition-all no-underline mx-1 dark:bg-gray-800 dark:text-gray-100 dark:border-gray-700 dark:hover:bg-gray-700";

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

                    // Source styling - vertical list with full width items
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

                nodes.push(...createInlineElements(rawLine));
            }

            if (sourcesNodes.length > 0) {
                nodes.push(
                    <div key={`${messageId}-sources-container`} className="mt-4 pt-3 border-t border-border/40 bg-muted/30 rounded-lg p-3 space-y-2">
                        <span className="block text-xs font-bold uppercase text-muted-foreground/80 mb-2">
                            Sources:
                        </span>
                        <div className="flex flex-col gap-2 w-full">
                            {sourcesNodes}
                        </div>
                    </div>
                );
            }

            return nodes;
        }, [handleDownloadSource, user?.access_token]);

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
            <ChatContainer>
                <Card className="flex flex-col flex-1 bg-card dark:bg-gray-900 overflow-hidden">
                    <CardHeader className="flex-shrink-0 py-3">
                        <div className="flex items-center justify-end">
                            {hasMessages && (
                                <Button variant="outline" onClick={clearChat} size="sm">
                                    Clear Chat
                                </Button>
                            )}
                        </div>
                    </CardHeader>
                    <CardContent className="relative flex-1 flex flex-col min-h-0 overflow-hidden p-0">
                        {!selectedCollection ? (
                            <div className="flex-1 flex items-center justify-center text-muted-foreground dark:text-gray-300">
                                No knowledge base configured. Please contact support.
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
                                                            : 'bg-muted border border-border/60 text-foreground max-w-[80%] dark:bg-gray-800 dark:text-gray-100'
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
                                                        <div className="flex flex-col gap-1 text-sm leading-relaxed">
                                                            {renderMessageContent(message.content, message.id, message.sources)}
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })
                                    )}
                                    {isLoading && !isStreaming && (
                                        <div className="flex justify-start pt-2">
                                            <div className="bg-muted border rounded-lg px-4 py-3 dark:bg-gray-800 dark:text-gray-300">
                                                <div className="flex items-center space-x-2">
                                                    <img src={getAssetUrl('leto.svg')} alt="Leto logo" className="h-4 w-4" />
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
            </ChatContainer>
        </DashboardLayout>
    );
}
