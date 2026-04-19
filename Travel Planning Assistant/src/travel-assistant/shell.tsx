import { ReactNode, useEffect, useRef, useState } from 'react';
import { Bot, Brain, Check, Edit2, Loader2, Plane, Send, User } from 'lucide-react';
import { Message, SessionState } from './types';

interface HeaderProps {
  sessionId: string;
  userId: string;
  onSessionIdChange: (id: string) => void;
  onUserIdChange: (id: string) => void;
}

export function Header({ sessionId, userId, onSessionIdChange, onUserIdChange }: HeaderProps) {
  const [editingSession, setEditingSession] = useState(false);
  const [editingUser, setEditingUser] = useState(false);
  const [tempSessionId, setTempSessionId] = useState(sessionId);
  const [tempUserId, setTempUserId] = useState(userId);

  useEffect(() => {
    setTempSessionId(sessionId);
  }, [sessionId]);

  useEffect(() => {
    setTempUserId(userId);
  }, [userId]);

  const handleSessionSave = () => {
    onSessionIdChange(tempSessionId.trim() || sessionId);
    setEditingSession(false);
  };

  const handleUserSave = () => {
    onUserIdChange(tempUserId.trim() || userId);
    setEditingUser(false);
  };

  return (
    <header className="header">
      <div className="header-content">
        <div className="header-brand">
          <div className="brand-icon">
            <Plane size={28} />
          </div>
          <div>
            <h1 className="brand-title">智能旅游助手</h1>
            <p className="brand-subtitle">基于天气、路线、酒店与旅行知识生成结构化行程建议</p>
          </div>
        </div>

        <div className="header-info">
          <div className="info-item">
            <span className="info-label">会话 ID:</span>
            {editingSession ? (
              <div className="info-edit">
                <input
                  type="text"
                  value={tempSessionId}
                  onChange={(e) => setTempSessionId(e.target.value)}
                  className="info-input"
                  autoFocus
                />
                <button onClick={handleSessionSave} className="info-btn">
                  <Check size={14} />
                </button>
              </div>
            ) : (
              <div className="info-display">
                <span className="info-value">{sessionId}</span>
                <button onClick={() => setEditingSession(true)} className="info-btn">
                  <Edit2 size={14} />
                </button>
              </div>
            )}
          </div>

          <div className="info-item">
            <span className="info-label">用户 ID:</span>
            {editingUser ? (
              <div className="info-edit">
                <input
                  type="text"
                  value={tempUserId}
                  onChange={(e) => setTempUserId(e.target.value)}
                  className="info-input"
                  autoFocus
                />
                <button onClick={handleUserSave} className="info-btn">
                  <Check size={14} />
                </button>
              </div>
            ) : (
              <div className="info-display">
                <span className="info-value">{userId}</span>
                <button onClick={() => setEditingUser(true)} className="info-btn">
                  <Edit2 size={14} />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

interface QuickChipsProps {
  onQuickClick: (text: string) => void;
}

const QUICK_SUGGESTIONS = [
  '大理 3 天情侣游，5 月 20 日出发，预算 3000',
  '杭州 2 天轻松游，这周末出发，预算 2000',
  '上海 3 天拍照路线，下个月出发，预算 4000',
];

export function QuickChips({ onQuickClick }: QuickChipsProps) {
  return (
    <div className="quick-chips">
      <div className="chips-title">快速开始</div>
      <div className="chips-list">
        {QUICK_SUGGESTIONS.map((text, idx) => (
          <button key={idx} className="chip-btn" onClick={() => onQuickClick(text)}>
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

interface MessageBubbleProps {
  message: Message;
  onQuestionClick: (question: string) => void;
}

function renderInlineMarkdown(text: string): ReactNode[] {
  const parts = text.split(/(\*\*.*?\*\*)/g).filter(Boolean);

  return parts.map((part, idx) => {
    const boldMatch = part.match(/^\*\*(.*?)\*\*$/);
    if (boldMatch) {
      return <strong key={idx}>{boldMatch[1]}</strong>;
    }

    return <span key={idx}>{part.replace(/\*\*/g, '')}</span>;
  });
}

function renderFormattedAssistantMessage(content: string) {
  const lines = content.replace(/\r/g, '').split('\n');

  return lines.map((line, idx) => {
    const trimmed = line.trim();

    if (!trimmed) {
      return <div key={idx} className="message-line spacer" />;
    }

    const normalized = trimmed
      .replace(/^\*\*(#{1,6}\s*.*?)\*\*$/, '$1')
      .replace(/^\*\*(.*?)\*\*$/, '$1');

    if (/^---+$/.test(normalized)) {
      return <div key={idx} className="message-divider" />;
    }

    const headingMatch = normalized.match(/^(#{1,6})\s*(.+)$/);
    if (headingMatch) {
      const level = Math.min(headingMatch[1].length, 3);
      return (
        <div key={idx} className={`message-line heading level-${level}`}>
          {renderInlineMarkdown(headingMatch[2])}
        </div>
      );
    }

    const bulletMatch = normalized.match(/^[-*•]\s+(.+)$/);
    if (bulletMatch) {
      return (
        <div key={idx} className="message-line bullet">
          <span className="message-bullet-dot">•</span>
          <span>{renderInlineMarkdown(bulletMatch[1])}</span>
        </div>
      );
    }

    const numberedMatch = normalized.match(/^(\d+[.)])\s+(.+)$/);
    if (numberedMatch) {
      return (
        <div key={idx} className="message-line numbered">
          <span className="message-number-label">{numberedMatch[1]}</span>
          <span>{renderInlineMarkdown(numberedMatch[2])}</span>
        </div>
      );
    }

    return (
      <div key={idx} className="message-line paragraph">
        {renderInlineMarkdown(normalized)}
      </div>
    );
  });
}

export function MessageBubble({ message, onQuestionClick }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`message-bubble ${message.role}`}>
      <div className="message-avatar">
        {isUser ? <User size={18} /> : <Bot size={18} />}
      </div>

      <div className="message-content">
        <div className={`message-text ${isUser ? 'plain' : 'formatted'}`}>
          {isUser ? message.content : renderFormattedAssistantMessage(message.content)}
        </div>

        {message.structured_itinerary?.follow_up_questions &&
          message.structured_itinerary.follow_up_questions.length > 0 && (
            <div className="follow-up-questions">
              <div className="follow-up-title">建议继续补充</div>
              <div className="follow-up-list">
                {message.structured_itinerary.follow_up_questions.map((question, idx) => (
                  <button
                    key={idx}
                    className="follow-up-btn"
                    onClick={() => onQuestionClick(question)}
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          )}
      </div>
    </div>
  );
}

interface ChatAreaProps {
  messages: Message[];
  isLoading: boolean;
  onSendMessage: (message: string) => void;
}

const AUTO_SCROLL_THRESHOLD_PX = 96;

function isChatScrolledToBottom(element: HTMLDivElement) {
  return (
    element.scrollHeight - element.scrollTop - element.clientHeight <=
    AUTO_SCROLL_THRESHOLD_PX
  );
}

export function ChatArea({ messages, isLoading, onSendMessage }: ChatAreaProps) {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const hasStreamingAssistantMessage =
    isLoading && messages.length > 0 && messages[messages.length - 1].role === 'assistant';

  useEffect(() => {
    if (!shouldAutoScrollRef.current) {
      return;
    }

    messagesEndRef.current?.scrollIntoView({
      behavior: hasStreamingAssistantMessage ? 'auto' : 'smooth',
      block: 'end',
    });
  }, [hasStreamingAssistantMessage, isLoading, messages]);

  const handleMessagesScroll = (e: React.UIEvent<HTMLDivElement>) => {
    shouldAutoScrollRef.current = isChatScrolledToBottom(e.currentTarget);
  };

  const handleMessagesWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    if (e.deltaY < 0) {
      shouldAutoScrollRef.current = false;
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) {
      return;
    }

    shouldAutoScrollRef.current = true;
    onSendMessage(inputValue.trim());
    setInputValue('');
    inputRef.current?.focus();
  };

  const handleQuickClick = (text: string) => {
    if (isLoading) {
      return;
    }

    shouldAutoScrollRef.current = true;
    onSendMessage(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="chat-area">
      <div
        className="chat-messages"
        onScroll={handleMessagesScroll}
        onWheel={handleMessagesWheel}
      >
        {messages.length === 0 ? (
          <div className="chat-empty">
            <div className="empty-icon">✈️</div>
            <h3>开始规划你的旅程</h3>
            <p>告诉我目的地、出发时间、预算和同行人，我会帮你生成可执行的旅行计划。</p>
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
            <span>正在生成行程建议...</span>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="chat-input-form">
        <textarea
          ref={inputRef}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="例如：帮我安排一个大理 3 天情侣游，5 月 20 日出发，预算 3000"
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

interface MemoryStateProps {
  sessionState?: SessionState;
}

function TagList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="memory-preferences">
      <div className="preferences-label">{title}</div>
      <div className="preferences-tags">
        {items.map((item, idx) => (
          <span key={idx} className="preference-tag">
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

export function MemoryState({ sessionState }: MemoryStateProps) {
  if (!sessionState || Object.keys(sessionState).length === 0) {
    return (
      <div className="memory-state">
        <div className="memory-header">
          <Brain size={18} />
          <h3>会话记忆</h3>
        </div>
        <div className="memory-empty">暂无已识别的旅行信息</div>
      </div>
    );
  }

  return (
    <div className="memory-state">
      <div className="memory-header">
        <Brain size={18} />
        <h3>会话记忆</h3>
      </div>

      <div className="memory-content">
        {sessionState.city && (
          <div className="memory-tag">
            <span className="tag-label">城市</span>
            <span className="tag-value">{sessionState.city}</span>
          </div>
        )}

        {sessionState.days !== undefined && (
          <div className="memory-tag">
            <span className="tag-label">天数</span>
            <span className="tag-value">{sessionState.days} 天</span>
          </div>
        )}

        {sessionState.date && (
          <div className="memory-tag">
            <span className="tag-label">日期</span>
            <span className="tag-value">{sessionState.date}</span>
          </div>
        )}

        {sessionState.budget !== undefined && (
          <div className="memory-tag">
            <span className="tag-label">预算</span>
            <span className="tag-value">¥{sessionState.budget}</span>
          </div>
        )}

        {sessionState.companions && (
          <div className="memory-tag">
            <span className="tag-label">同行人</span>
            <span className="tag-value">{sessionState.companions}</span>
          </div>
        )}

        {sessionState.pace && (
          <div className="memory-tag">
            <span className="tag-label">节奏</span>
            <span className="tag-value">{sessionState.pace}</span>
          </div>
        )}

        <TagList title="偏好标签" items={sessionState.preference_tags ?? []} />
        <TagList title="想去地点" items={sessionState.must_visit ?? []} />
        <TagList title="回避项" items={sessionState.avoid ?? []} />
      </div>
    </div>
  );
}
