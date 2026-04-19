import { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { Message } from '../types/travel';
import { MessageBubble } from './MessageBubble';
import { QuickChips } from './QuickChips';

interface ChatAreaProps {
  messages: Message[];
  isLoading: boolean;
  onSendMessage: (message: string) => void;
}

export function ChatArea({ messages, isLoading, onSendMessage }: ChatAreaProps) {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim() && !isLoading) {
      onSendMessage(inputValue.trim());
      setInputValue('');
    }
  };

  const handleQuickClick = (text: string) => {
    if (!isLoading) {
      onSendMessage(text);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="chat-area">
      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <div className="empty-icon">✈️</div>
            <h3>开始你的旅行规划</h3>
            <p>告诉我你的目的地、出行时间、预算和同行人，我将为你生成个性化的旅行计划</p>
            <QuickChips onQuickClick={handleQuickClick} />
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                onQuestionClick={handleQuickClick}
              />
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
        
        {isLoading && (
          <div className="message-bubble assistant loading">
            <Loader2 className="animate-spin" size={20} />
            <span>正在生成旅行计划...</span>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="chat-input-form">
        <textarea
          ref={inputRef}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="例如：帮我安排一个大连3天情侣游，5月20号出发，预算3000"
          className="chat-input"
          rows={1}
          disabled={isLoading}
        />
        <button
          type="submit"
          className="chat-send-btn"
          disabled={!inputValue.trim() || isLoading}
        >
          {isLoading ? <Loader2 className="animate-spin" size={20} /> : <Send size={20} />}
        </button>
      </form>
    </div>
  );
}
