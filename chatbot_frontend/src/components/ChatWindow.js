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
    <div className="chat-window">
      {collections.length > 0 && !collectionId && (
        <div className="collection-selector">
          <label htmlFor="chat-collection-select">Collection:</label>
          <select
            id="chat-collection-select"
            value={activeCollectionId || ""}
            onChange={(e) => setActiveCollectionId(e.target.value || null)}
          >
            {collections.map((col) => (
              <option key={col.collection_id} value={col.collection_id}>
                {col.name || col.collection_id}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="chat-header">
        <div className="chat-title">
          <h3>💬 Chat with your Knowledge Base</h3>
          {messages.length > 0 && (
            <span className="context-indicator">
              {messages.length} messages in context
            </span>
          )}
        </div>
        <div className="chat-actions">
          {messages.length > 0 && (
            <>
              <button 
                onClick={() => {
                  console.log("Current messages state:", messages);
                  console.log("Session ID:", sessionId);
                }}
                className="debug-btn"
                title="Debug current state"
              >
                🐛 Debug
              </button>
              <button 
                onClick={startNewChat} 
                className="new-chat-btn"
                title="Start a new conversation"
              >
                🔄 New Chat
              </button>
            </>
          )}
        </div>
      </div>
      <div className="messages">
        {messages.length === 0 && (
          <div className="welcome-message">
            Upload some documents and start asking questions about them!
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.user ? "user" : "bot"} ${m.error ? "error" : ""}`}>
            <div className={`message-content ${m.formatted ? "formatted-response" : ""}`}>
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
            <div className="message-actions">
              <button 
                onClick={() => deleteMessage(i)}
                className="delete-message-btn"
                title="Delete this message"
              >
                🗑️
              </button>
              <button 
                onClick={() => deleteFromIndex(i)}
                className="delete-from-btn"
                title="Delete from here onwards"
              >
                ✂️
              </button>
            </div>
          </div>
        ))}
        {isTyping && (
          <div className="message bot typing-message">
            <div className="message-content formatted-response">
              <div dangerouslySetInnerHTML={{ 
                __html: typingText
                  .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                  .replace(/\n\d+\./g, '<br/>$&')
                  .replace(/\n-/g, '<br/>•')
                  .replace(/\n/g, '<br/>')
              }} />
              <span className="typing-cursor">|</span>
            </div>
          </div>
        )}
        {loading && (
          <div className="message bot">
            <div className="message-content typing">Thinking...</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="input-section">
        <textarea
          value={question}
          onChange={e => setQuestion(e.target.value)}
          placeholder="Ask a question about your uploaded documents..."
          onKeyDown={handleKeyPress}
          rows={2}
          disabled={loading}
        />
        <button onClick={sendQuestion} disabled={!question.trim() || loading}>
          {loading ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}
