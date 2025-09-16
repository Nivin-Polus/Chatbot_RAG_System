import { useState } from "react";
import api from "../api/api";

export default function ChatWindow() {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);

  const sendQuestion = async () => {
    if (!question.trim() || loading) return;
    
    const userMessage = { user: true, text: question };
    setMessages(prev => [...prev, userMessage]);
    setLoading(true);
    
    try {
      const res = await api.post("/chat/ask", { question });
      setMessages(prev => [...prev, { user: false, text: res.data.answer }]);
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
            <div className="message-content">{m.text}</div>
          </div>
        ))}
        {loading && (
          <div className="message bot">
            <div className="message-content typing">Thinking...</div>
          </div>
        )}
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
