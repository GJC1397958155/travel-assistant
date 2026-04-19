import { Message } from '../types/travel';
import { User, Bot } from 'lucide-react';

interface MessageBubbleProps {
  message: Message;
  onQuestionClick: (question: string) => void;
}

export function MessageBubble({ message, onQuestionClick }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`message-bubble ${message.role}`}>
      <div className="message-avatar">
        {isUser ? <User size={18} /> : <Bot size={18} />}
      </div>
      <div className="message-content">
        <div className="message-text">{message.content}</div>
        
        {message.structured_itinerary?.follow_up_questions && 
         message.structured_itinerary.follow_up_questions.length > 0 && (
          <div className="follow-up-questions">
            <div className="follow-up-title">💡 建议追问：</div>
            <div className="follow-up-list">
              {message.structured_itinerary.follow_up_questions.map((q, idx) => (
                <button
                  key={idx}
                  className="follow-up-btn"
                  onClick={() => onQuestionClick(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
