import { useState, useEffect, useRef } from "react";
import api from "../api/api";

export default function ChatWindow() {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [typingText, setTypingText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);
  const typingIntervalRef = useRef(null);

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
    
    const userMessage = { user: true, text: question };
    setMessages(prev => [...prev, userMessage]);
    setLoading(true);
    
    try {
      const res = await api.post("/chat/ask", { question });
      const responseText = res.data.answer; // Backend now returns {answer: "text"}
      
      // Start typing animation
      typeMessage(responseText, () => {
        setMessages(prev => [...prev, { 
          user: false, 
          text: responseText,
          formatted: true
        }]);
      });
    } catch (err) {
      const errorMsg = err.response?.data?.detail || "Failed to get response";
      setMessages(prev => [...prev, { user: false, text: errorMsg, error: true }]);
    }
    
    setQuestion("");
    setLoading(false);
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendQuestion();
    }
  };

  return (
    <div className="chat-window">
      <h3>Chat with your Knowledge Base</h3>
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
