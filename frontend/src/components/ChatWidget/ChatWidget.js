import React, { useState, useRef, useEffect } from 'react';
import './ChatWidget.css';

function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = inputMessage;
    setInputMessage('');
    
    // Add user message to chat
    const userMsg = { 
      id: Date.now(), 
      text: userMessage, 
      sender: 'user' 
    };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    try {
      // Send to backend
      const response = await fetch('http://localhost:5000/api/chat/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({ question: userMessage })
      });

      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }

      // Add AI response to chat
      setMessages(prev => [
        ...prev, 
        { 
          id: Date.now() + 1, 
          text: data.answer, 
          sender: 'ai',
          sources: data.sources || []
        }
      ]);
    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => [
        ...prev, 
        { 
          id: Date.now() + 1, 
          text: 'Sorry, I encountered an error. Please try again.', 
          sender: 'ai',
          isError: true
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={`chat-widget ${isOpen ? 'open' : ''}`}>
      {isOpen ? (
        <div className="chat-container">
          <div className="chat-header">
            <h3>RevenueLens Assistant</h3>
            <button className="close-btn" onClick={() => setIsOpen(false)}>
              ×
            </button>
          </div>
          <div className="chat-messages">
            {messages.length === 0 ? (
              <div className="welcome-message">
                <p>Hello! I'm your RevenueLens assistant. How can I help you today?</p>
              </div>
            ) : (
              messages.map((msg) => (
                <div key={msg.id} className={`message ${msg.sender} ${msg.isError ? 'error' : ''}`}>
                  <div className="message-content">
                    <p>{msg.text}</p>
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="sources">
                        <p className="sources-title">Sources:</p>
                        {msg.sources.map((src, idx) => (
                          <div key={idx} className="source">
                            {src.content}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            {isLoading && (
              <div className="typing-indicator">
                <span>AI is typing</span>
                <span className="dot">.</span>
                <span className="dot">.</span>
                <span className="dot">.</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          <div className="chat-input">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
              placeholder="Ask me anything about RevenueLens..."
              disabled={isLoading}
            />
            <button 
              onClick={handleSendMessage} 
              disabled={isLoading || !inputMessage.trim()}
            >
              Send
            </button>
          </div>
        </div>
      ) : (
        <button 
          className="chat-toggle-btn"
          onClick={() => setIsOpen(true)}
          aria-label="Open chat"
        >
          <svg 
            xmlns="http://www.w3.org/2000/svg" 
            width="24" 
            height="24" 
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            strokeWidth="2" 
            strokeLinecap="round" 
            strokeLinejoin="round"
          >
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
        </button>
      )}
    </div>
  );
}

export default ChatWidget;