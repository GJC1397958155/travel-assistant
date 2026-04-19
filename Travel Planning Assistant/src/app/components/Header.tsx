import { useState } from 'react';
import { Plane, Edit2, Check } from 'lucide-react';

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

  const handleSessionSave = () => {
    onSessionIdChange(tempSessionId);
    setEditingSession(false);
  };

  const handleUserSave = () => {
    onUserIdChange(tempUserId);
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
            <p className="brand-subtitle">基于天气、路线、酒店和旅行知识库生成个性化行程</p>
          </div>
        </div>
        
        <div className="header-info">
          <div className="info-item">
            <span className="info-label">会话ID:</span>
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
            <span className="info-label">用户ID:</span>
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
