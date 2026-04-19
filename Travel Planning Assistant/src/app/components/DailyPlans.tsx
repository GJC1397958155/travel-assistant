import { DailyPlan } from '../types/travel';
import { Sunrise, Sun, Sunset } from 'lucide-react';

interface DailyPlansProps {
  plans: DailyPlan[];
}

export function DailyPlans({ plans }: DailyPlansProps) {
  return (
    <div className="itinerary-section">
      <h3 className="section-title">每日安排</h3>
      <div className="daily-plans">
        {plans.map((plan) => (
          <div key={plan.day} className="daily-card">
            <div className="daily-header">
              <div className="daily-day">第 {plan.day} 天</div>
              <div className="daily-date">{plan.date}</div>
            </div>

            <div className="daily-content">
              {plan.morning && (
                <div className="time-block">
                  <div className="time-header">
                    <Sunrise size={16} />
                    <span>上午</span>
                  </div>
                  <p className="time-content">{plan.morning}</p>
                </div>
              )}

              {plan.afternoon && (
                <div className="time-block">
                  <div className="time-header">
                    <Sun size={16} />
                    <span>下午</span>
                  </div>
                  <p className="time-content">{plan.afternoon}</p>
                </div>
              )}

              {plan.evening && (
                <div className="time-block">
                  <div className="time-header">
                    <Sunset size={16} />
                    <span>晚上</span>
                  </div>
                  <p className="time-content">{plan.evening}</p>
                </div>
              )}
            </div>

            {plan.highlights && plan.highlights.length > 0 && (
              <div className="daily-highlights">
                <div className="highlights-title">亮点：</div>
                <div className="highlights-tags">
                  {plan.highlights.map((highlight, idx) => (
                    <span key={idx} className="highlight-tag">
                      {highlight}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
