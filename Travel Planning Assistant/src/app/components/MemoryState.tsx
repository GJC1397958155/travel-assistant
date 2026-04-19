import { SessionState } from '../types/travel';
import { Brain } from 'lucide-react';

interface MemoryStateProps {
  sessionState?: SessionState;
}

export function MemoryState({ sessionState }: MemoryStateProps) {
  if (!sessionState || Object.keys(sessionState).length === 0) {
    return (
      <div className="memory-state">
        <div className="memory-header">
          <Brain size={18} />
          <h3>会话记忆</h3>
        </div>
        <div className="memory-empty">暂无会话记忆</div>
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
            <span className="tag-value">{sessionState.days}天</span>
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
            <span className="tag-label">同行</span>
            <span className="tag-value">{sessionState.companions}</span>
          </div>
        )}
        
        {sessionState.preference_tags && sessionState.preference_tags.length > 0 && (
          <div className="memory-preferences">
            <div className="preferences-label">偏好标签</div>
            <div className="preferences-tags">
              {sessionState.preference_tags.map((tag, idx) => (
                <span key={idx} className="preference-tag">{tag}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
