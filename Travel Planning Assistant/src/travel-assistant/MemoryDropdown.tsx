import { useMemo, useState } from 'react';
import { Brain, ChevronDown } from 'lucide-react';
import { SessionState } from './types';

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

function buildSummary(sessionState?: SessionState) {
  if (!sessionState || Object.keys(sessionState).length === 0) {
    return '暂无已识别的旅行信息';
  }

  const parts: string[] = [];

  if (sessionState.city) {
    parts.push(sessionState.city);
  }
  if (sessionState.days !== undefined) {
    parts.push(`${sessionState.days} 天`);
  }
  if (sessionState.date) {
    parts.push(sessionState.date);
  }
  if (sessionState.budget !== undefined) {
    parts.push(`预算 ¥${sessionState.budget}`);
  }
  if (sessionState.pace) {
    parts.push(sessionState.pace);
  }

  return parts.length > 0 ? parts.join(' / ') : '已记录旅行偏好';
}

export default function MemoryDropdown({ sessionState }: MemoryStateProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const hasState = !!sessionState && Object.keys(sessionState).length > 0;
  const summary = useMemo(() => buildSummary(sessionState), [sessionState]);

  return (
    <div className={`memory-state ${isExpanded ? 'expanded' : 'collapsed'}`}>
      <button
        type="button"
        className="memory-toggle"
        onClick={() => setIsExpanded((prev) => !prev)}
        aria-expanded={isExpanded}
        aria-label={isExpanded ? '收起会话记忆' : '展开会话记忆'}
      >
        <div className="memory-header">
          <Brain size={18} />
          <h3>会话记忆</h3>
        </div>

        <div className="memory-toggle-right">
          <span className="memory-summary">{summary}</span>
          <ChevronDown size={18} className="memory-chevron" />
        </div>
      </button>

      {isExpanded && (
        <div className="memory-body">
          {!hasState ? (
            <div className="memory-empty">暂无已识别的旅行信息</div>
          ) : (
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
          )}
        </div>
      )}
    </div>
  );
}
