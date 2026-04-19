import { useEffect, useRef } from 'react';
import { StructuredItinerary } from '../types/travel';
import { ItineraryOverview } from './ItineraryOverview';
import { DailyPlans } from './DailyPlans';
import { HotelSection } from './HotelSection';
import { BudgetSection } from './BudgetSection';
import { AlertsSection } from './AlertsSection';
import { AlternativesSection } from './AlternativesSection';
import { MapPin } from 'lucide-react';

interface ItineraryPanelProps {
  itinerary?: StructuredItinerary;
  shouldScroll?: boolean;
}

export function ItineraryPanel({ itinerary, shouldScroll }: ItineraryPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (shouldScroll && itinerary?.status === 'ready') {
      setTimeout(() => {
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
          <h3>等待行程规划</h3>
          <p>在左侧输入你的旅行需求，<br />我将为你生成详细的行程计划</p>
        </div>
      </div>
    );
  }

  if (itinerary.status === 'needs_clarification') {
    return (
      <div className="itinerary-panel" ref={panelRef}>
        <div className="clarification-card">
          <div className="clarification-icon">🤔</div>
          <h3>需要更多信息</h3>
          <p>请在左侧聊天区域回答问题，以便我为你生成更准确的行程计划</p>
          {itinerary.follow_up_questions && itinerary.follow_up_questions.length > 0 && (
            <div className="clarification-questions">
              {itinerary.follow_up_questions.map((q, idx) => (
                <div key={idx} className="clarification-item">• {q}</div>
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
        <h2>📋 行程规划</h2>
      </div>

      <div className="itinerary-content">
        <ItineraryOverview itinerary={itinerary} />
        
        {itinerary.daily_plans && itinerary.daily_plans.length > 0 && (
          <DailyPlans plans={itinerary.daily_plans} />
        )}

        {itinerary.hotel_suggestion && (
          <HotelSection suggestion={itinerary.hotel_suggestion} />
        )}

        {itinerary.budget_advice && (
          <BudgetSection advice={itinerary.budget_advice} />
        )}

        {itinerary.alerts && itinerary.alerts.length > 0 && (
          <AlertsSection alerts={itinerary.alerts} />
        )}

        {itinerary.alternatives && itinerary.alternatives.length > 0 && (
          <AlternativesSection alternatives={itinerary.alternatives} />
        )}
      </div>
    </div>
  );
}
