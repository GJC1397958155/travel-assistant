import { useEffect, useRef } from 'react';
import {
  AlertTriangle,
  Calendar,
  Cloud,
  Hotel,
  Lightbulb,
  MapPin,
  Sparkles,
  Sunrise,
  Sun,
  Sunset,
  Users,
  Wallet,
} from 'lucide-react';
import {
  Activity,
  BudgetAdvice,
  DailyPlan,
  HotelSuggestion,
  StructuredItinerary,
} from './types';
import { ItineraryRouteMap } from './ItineraryRouteMap';

function ActivityList({
  items,
  emptyText,
}: {
  items: Activity[];
  emptyText: string;
}) {
  if (!items || items.length === 0) {
    return <p className="time-content">{emptyText}</p>;
  }

  return (
    <div className="time-content">
      {items.map((item, idx) => (
        <div key={`${item.title}-${idx}`} className="activity-item">
          <strong>{item.title || '待补充安排'}</strong>
          {item.location && <div>{item.location}</div>}
          {item.reason && <div>{item.reason}</div>}
        </div>
      ))}
    </div>
  );
}

function ItineraryOverview({ itinerary }: { itinerary: StructuredItinerary }) {
  return (
    <div className="itinerary-section">
      <div className="overview-grid">
        {itinerary.destination && (
          <div className="overview-item">
            <div className="overview-icon">
              <MapPin size={18} />
            </div>
            <div className="overview-info">
              <div className="overview-label">目的地</div>
              <div className="overview-value">{itinerary.destination}</div>
            </div>
          </div>
        )}

        {itinerary.days !== undefined && (
          <div className="overview-item">
            <div className="overview-icon">
              <Calendar size={18} />
            </div>
            <div className="overview-info">
              <div className="overview-label">行程天数</div>
              <div className="overview-value">{itinerary.days} 天</div>
            </div>
          </div>
        )}

        {itinerary.date && (
          <div className="overview-item">
            <div className="overview-icon">
              <Calendar size={18} />
            </div>
            <div className="overview-info">
              <div className="overview-label">出发日期</div>
              <div className="overview-value">{itinerary.date}</div>
            </div>
          </div>
        )}

        {itinerary.companions && (
          <div className="overview-item">
            <div className="overview-icon">
              <Users size={18} />
            </div>
            <div className="overview-info">
              <div className="overview-label">同行人</div>
              <div className="overview-value">{itinerary.companions}</div>
            </div>
          </div>
        )}

        {itinerary.budget !== undefined && (
          <div className="overview-item">
            <div className="overview-icon">
              <Wallet size={18} />
            </div>
            <div className="overview-info">
              <div className="overview-label">预算</div>
              <div className="overview-value">¥{itinerary.budget}</div>
            </div>
          </div>
        )}

        {itinerary.travel_style && (
          <div className="overview-item">
            <div className="overview-icon">
              <Sparkles size={18} />
            </div>
            <div className="overview-info">
              <div className="overview-label">旅行风格</div>
              <div className="overview-value">{itinerary.travel_style}</div>
            </div>
          </div>
        )}
      </div>

      {itinerary.overview && (
        <div className="overview-summary">
          <h4>行程概览</h4>
          <p>{itinerary.overview}</p>
        </div>
      )}

      {itinerary.weather_summary && (
        <div className="weather-summary">
          <div className="weather-icon">
            <Cloud size={18} />
          </div>
          <div className="weather-text">{itinerary.weather_summary}</div>
        </div>
      )}
    </div>
  );
}

function DailyPlans({ plans }: { plans: DailyPlan[] }) {
  return (
    <div className="itinerary-section">
      <h3 className="section-title">每日安排</h3>
      <div className="daily-plans">
        {plans.map((plan) => (
          <div key={plan.day} className="daily-card">
            <div className="daily-header">
              <div>
                <div className="daily-day">第 {plan.day} 天</div>
                {plan.title && <div className="daily-date">{plan.title}</div>}
              </div>
              <div className="daily-date">{plan.date || plan.weather}</div>
            </div>

            <div className="daily-content">
              <div className="time-block">
                <div className="time-header">
                  <Sunrise size={16} />
                  <span>上午</span>
                </div>
                <ActivityList items={plan.morning ?? []} emptyText="上午安排待补充" />
              </div>

              <div className="time-block">
                <div className="time-header">
                  <Sun size={16} />
                  <span>下午</span>
                </div>
                <ActivityList items={plan.afternoon ?? []} emptyText="下午安排待补充" />
              </div>

              <div className="time-block">
                <div className="time-header">
                  <Sunset size={16} />
                  <span>晚上</span>
                </div>
                <ActivityList items={plan.evening ?? []} emptyText="晚上安排待补充" />
              </div>
            </div>

            {plan.highlights && plan.highlights.length > 0 && (
              <div className="daily-highlights">
                <div className="highlights-title">亮点</div>
                <div className="highlights-tags">
                  {plan.highlights.map((highlight, idx) => (
                    <span key={idx} className="highlight-tag">
                      {highlight}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {plan.transport_tip && <p className="budget-summary">交通：{plan.transport_tip}</p>}
            {plan.dining_tip && <p className="budget-summary">餐饮：{plan.dining_tip}</p>}

            {plan.notes && plan.notes.length > 0 && (
              <div className="alerts-list">
                {plan.notes.map((note, idx) => (
                  <div key={idx} className="alert-item">
                    <span className="alert-dot">•</span>
                    <span>{note}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function HotelSection({ suggestion }: { suggestion: HotelSuggestion }) {
  if (!suggestion.area && !suggestion.reason && (!suggestion.candidates || suggestion.candidates.length === 0)) {
    return null;
  }

  return (
    <div className="itinerary-section">
      <h3 className="section-title">
        <Hotel size={18} />
        酒店建议
      </h3>

      {suggestion.area && (
        <div className="hotel-area">
          <span className="hotel-label">推荐区域：</span>
          <span className="hotel-value">{suggestion.area}</span>
        </div>
      )}

      {suggestion.reason && <p className="hotel-reason">{suggestion.reason}</p>}

      {suggestion.candidates && suggestion.candidates.length > 0 && (
        <div className="hotel-candidates">
          {suggestion.candidates.map((hotel, idx) => (
            <div key={idx} className="hotel-card">
              <div className="hotel-name">{hotel}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function getBudgetLevelColor(level: string) {
  const lowerLevel = level.toLowerCase();

  if (
    lowerLevel.includes('充足') ||
    lowerLevel.includes('宽松') ||
    lowerLevel.includes('generous') ||
    lowerLevel.includes('comfortable')
  ) {
    return 'success';
  }

  if (
    lowerLevel.includes('紧张') ||
    lowerLevel.includes('不足') ||
    lowerLevel.includes('tight') ||
    lowerLevel.includes('limited')
  ) {
    return 'warning';
  }

  return 'info';
}

function BudgetSection({ advice }: { advice: BudgetAdvice }) {
  if (!advice.level && !advice.summary) {
    return null;
  }

  return (
    <div className="itinerary-section">
      <h3 className="section-title">
        <Wallet size={18} />
        预算建议
      </h3>

      {advice.level && <div className={`budget-level ${getBudgetLevelColor(advice.level)}`}>{advice.level}</div>}
      {advice.summary && <p className="budget-summary">{advice.summary}</p>}
    </div>
  );
}

function AlertsSection({ alerts }: { alerts: string[] }) {
  return (
    <div className="itinerary-section">
      <h3 className="section-title">
        <AlertTriangle size={18} />
        注意事项
      </h3>

      <div className="alerts-list">
        {alerts.map((alert, idx) => (
          <div key={idx} className="alert-item">
            <span className="alert-dot">•</span>
            <span>{alert}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function AlternativesSection({ alternatives }: { alternatives: string[] }) {
  return (
    <div className="itinerary-section">
      <h3 className="section-title">
        <Lightbulb size={18} />
        备选方案
      </h3>

      <div className="alternatives-list">
        {alternatives.map((alternative, idx) => (
          <div key={idx} className="alternative-item">
            <span className="alternative-number">{idx + 1}</span>
            <span>{alternative}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

interface ItineraryPanelProps {
  itinerary?: StructuredItinerary;
  shouldScroll?: boolean;
}

export function ItineraryPanel({ itinerary, shouldScroll }: ItineraryPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (shouldScroll && itinerary?.status === 'ready') {
      window.setTimeout(() => {
        panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    }
  }, [shouldScroll, itinerary?.status]);

  if (!itinerary) {
    return (
      <div className="itinerary-panel">
        <div className="itinerary-empty">
          <div className="empty-icon">
            <MapPin size={48} />
          </div>
          <h3>等待行程生成</h3>
          <p>
            在左侧输入你的旅行需求，
            <br />
            这里会展示结构化的行程结果。
          </p>
        </div>
      </div>
    );
  }

  if (itinerary.status === 'processing') {
    return (
      <div className="itinerary-panel" ref={panelRef}>
        <div className="clarification-card">
          <div className="clarification-icon">⏳</div>
          <h3>正在整理你的行程</h3>
          <p>请稍候，结构化结果生成后会显示在这里。</p>
        </div>
      </div>
    );
  }

  if (itinerary.status === 'needs_clarification') {
    return (
      <div className="itinerary-panel" ref={panelRef}>
        <div className="clarification-card">
          <div className="clarification-icon">🧭</div>
          <h3>还需要更多信息</h3>
          <p>请在左侧继续补充需求，我会根据这些信息生成更准确的行程方案。</p>
          {itinerary.follow_up_questions && itinerary.follow_up_questions.length > 0 && (
            <div className="clarification-questions">
              {itinerary.follow_up_questions.map((question, idx) => (
                <div key={idx} className="clarification-item">
                  • {question}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="itinerary-panel" ref={panelRef}>
      <div className="itinerary-header">
        <h2>行程规划</h2>
      </div>

      <div className="itinerary-content">
        <ItineraryOverview itinerary={itinerary} />
        <ItineraryRouteMap itinerary={itinerary} />

        {itinerary.daily_plans && itinerary.daily_plans.length > 0 && (
          <DailyPlans plans={itinerary.daily_plans} />
        )}

        {itinerary.hotel_suggestion && <HotelSection suggestion={itinerary.hotel_suggestion} />}
        {itinerary.budget_advice && <BudgetSection advice={itinerary.budget_advice} />}
        {itinerary.alerts && itinerary.alerts.length > 0 && <AlertsSection alerts={itinerary.alerts} />}
        {itinerary.alternatives && itinerary.alternatives.length > 0 && (
          <AlternativesSection alternatives={itinerary.alternatives} />
        )}
      </div>
    </div>
  );
}
