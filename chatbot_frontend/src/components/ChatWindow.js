import { useState, useEffect, useRef } from "react";
import api from "../api/api";

export default function ChatWindow({ collectionId = null, collections = [] }) {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [typingText, setTypingText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [sessionId] = useState(() => `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);
  const [activeCollectionId, setActiveCollectionId] = useState(collectionId || collections[0]?.collection_id || null);
  const messagesEndRef = useRef(null);
  const typingIntervalRef = useRef(null);

  useEffect(() => {
    if (collectionId && collectionId !== activeCollectionId) {
      setActiveCollectionId(collectionId);
      startNewChat();
    }
  }, [collectionId]);

  useEffect(() => {
    if (!collectionId && collections.length > 0 && !activeCollectionId) {
      setActiveCollectionId(collections[0].collection_id);
    }
  }, [collections, collectionId, activeCollectionId]);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  // Typing animation function
  const typeMessage = (text, callback) => {
    setIsTyping(true);
    setTypingText("");
    let index = 0;
    
    typingIntervalRef.current = setInterval(() => {
      if (index < text.length) {
        setTypingText(prev => prev + text.charAt(index));
        index++;
      } else {
        clearInterval(typingIntervalRef.current);
        setIsTyping(false);
        setTypingText("");
        callback();
      }
    }, 30); // Adjust typing speed here (lower = faster)
  };

  const sendQuestion = async () => {
    if (!question.trim() || loading) return;
    
    const userMessage = { user: true, text: question, timestamp: new Date().toISOString() };
    const currentQuestion = question;
    
    // Prepare conversation context BEFORE updating state (last 10 messages for context)
    const rawHistory = messages.slice(-10).map(msg => ({
      role: msg.user ? "user" : "assistant",
      content: msg.text,
      timestamp: msg.timestamp
    }));
    
    // Add current question to history
    rawHistory.push({
      role: "user",
      content: currentQuestion,
      timestamp: userMessage.timestamp
    });
    
    // Clean and validate the conversation history
    const conversationHistory = validateAndCleanContext(rawHistory);
    
    // Now update the UI
    setMessages(prev => [...prev, userMessage]);
    setQuestion("");
    setLoading(true);
    
    try {
      // Debug: Log the context being sent
      console.log("=== CONTEXT DEBUG ===");
      console.log("Session ID:", sessionId);
      console.log("Current Question:", currentQuestion);
      console.log("Conversation History Length:", conversationHistory.length);
      console.log("Full Conversation History:", conversationHistory);
      console.log("===================");
      
      const payload = {
        question: currentQuestion,
        session_id: sessionId,
        conversation_history: conversationHistory,
        maintain_context: true,
        context_length: conversationHistory.length
      };

      if (collectionId || activeCollectionId) {
        payload.collection_id = collectionId || activeCollectionId;
      }
      
      console.log("Full payload being sent:", payload);
      
      const res = await api.post("/chat/ask", payload);
      
      console.log("Backend response:", res.data);
      
      const responseText = res.data.answer || res.data.response || res.data;
      
      // Start typing animation
      typeMessage(responseText, () => {
        setMessages(prev => [...prev, { 
          user: false, 
          text: responseText,
          formatted: true,
          timestamp: new Date().toISOString()
        }]);
      });
    } catch (err) {
      const errorMsg = err.response?.data?.detail || "Failed to get response";
      setMessages(prev => [...prev, { 
        user: false, 
        text: errorMsg, 
        error: true,
        timestamp: new Date().toISOString()
      }]);
    }
    
    setLoading(false);
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendQuestion();
    }
  };

  const startNewChat = () => {
    setMessages([]);
    setQuestion("");
    setTypingText("");
    setIsTyping(false);
    if (typingIntervalRef.current) {
      clearInterval(typingIntervalRef.current);
    }
  };

  const deleteMessage = (indexToDelete) => {
    setMessages(prev => prev.filter((_, index) => index !== indexToDelete));
  };

  const deleteFromIndex = (indexToDelete) => {
    setMessages(prev => prev.slice(0, indexToDelete));
  };

  const validateAndCleanContext = (history) => {
    return history
      .filter(msg => msg.content && msg.content.trim() && msg.role)
      .map(msg => ({
        role: msg.role === "user" ? "user" : "assistant",
        content: msg.content.trim(),
        timestamp: msg.timestamp || new Date().toISOString()
      }));
  };

  return (
    <div className="flex flex-col h-[600px] bg-white rounded-xl shadow-soft border border-gray-200 overflow-hidden">
      {/* Collection Selector */}
      {collections.length > 0 && !collectionId && (
        <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
          <div className="flex items-center space-x-3">
            <label htmlFor="chat-collection-select" className="text-sm font-medium text-gray-700">
              Collection:
            </label>
            <select
              id="chat-collection-select"
              value={activeCollectionId || ""}
              onChange={(e) => setActiveCollectionId(e.target.value || null)}
              className="form-select flex-1 max-w-xs"
            >
              {collections.map((col) => (
                <option key={col.collection_id} value={col.collection_id}>
                  {col.name || col.collection_id}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* Chat Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-white border-b border-gray-200">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center">
            <span className="text-primary-600 text-lg">💬</span>
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">AI Assistant</h3>
            {messages.length > 0 && (
              <span className="text-xs text-gray-500">
                {messages.length} messages in context
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center space-x-2">
          {messages.length > 0 && (
            <>
              <button 
                onClick={() => {
                  console.log("Current messages state:", messages);
                  console.log("Session ID:", sessionId);
                }}
                className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
                title="Debug current state"
              >
                🐛
              </button>
              <button 
                onClick={startNewChat} 
                className="p-2 text-gray-400 hover:text-primary-600 transition-colors"
                title="Start a new conversation"
              >
                🔄
              </button>
            </>
          )}
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl">🤖</span>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">Welcome to AI Assistant</h3>
            <p className="text-gray-600">Upload some documents and start asking questions about them!</p>
          </div>
        )}
        
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.user ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-xs lg:max-w-md px-4 py-3 rounded-2xl ${
              m.user 
                ? 'bg-primary-600 text-white' 
                : m.error 
                ? 'bg-error-100 text-error-800 border border-error-200'
                : 'bg-gray-100 text-gray-900'
            }`}>
              <div className={`text-sm ${m.formatted ? 'prose prose-sm max-w-none' : ''}`}>
                {m.formatted ? (
                  <div dangerouslySetInnerHTML={{ 
                    __html: m.text
                      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                      .replace(/\n\d+\./g, '<br/>$&')
                      .replace(/\n-/g, '<br/>•')
                      .replace(/\n/g, '<br/>')
                  }} />
                ) : (
                  m.text
                )}
              </div>
              {!m.user && (
                <div className="flex items-center space-x-2 mt-2">
                  <button 
                    onClick={() => deleteMessage(i)}
                    className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
                    title="Delete this message"
                  >
                    🗑️
                  </button>
                  <button 
                    onClick={() => deleteFromIndex(i)}
                    className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
                    title="Delete from here onwards"
                  >
                    ✂️
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
        
        {isTyping && (
          <div className="flex justify-start">
            <div className="max-w-xs lg:max-w-md px-4 py-3 rounded-2xl bg-gray-100 text-gray-900">
              <div className="text-sm prose prose-sm max-w-none">
                <div dangerouslySetInnerHTML={{ 
                  __html: typingText
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                    .replace(/\n\d+\./g, '<br/>$&')
                    .replace(/\n-/g, '<br/>•')
                    .replace(/\n/g, '<br/>')
                }} />
                <span className="typing-cursor animate-pulse">|</span>
              </div>
            </div>
          </div>
        )}
        
        {loading && (
          <div className="flex justify-start">
            <div className="max-w-xs lg:max-w-md px-4 py-3 rounded-2xl bg-gray-100 text-gray-900">
              <div className="flex items-center space-x-2">
                <div className="spinner"></div>
                <span className="text-sm">Thinking...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Section */}
      <div className="border-t border-gray-200 p-4">
        <div className="flex items-end space-x-3">
          <div className="flex-1">
            <textarea
              value={question}
              onChange={e => setQuestion(e.target.value)}
              placeholder="Ask a question about your uploaded documents..."
              onKeyDown={handleKeyPress}
              rows={2}
              disabled={loading}
              className="form-textarea resize-none"
            />
          </div>
          <button 
            onClick={sendQuestion} 
            disabled={!question.trim() || loading}
            className="btn btn-primary px-6 py-3 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <div className="spinner"></div>
            ) : (
              <>
                <span className="mr-2">📤</span>
                Send
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
