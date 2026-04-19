import { AlertTriangle } from 'lucide-react';

interface AlertsSectionProps {
  alerts: string[];
}

export function AlertsSection({ alerts }: AlertsSectionProps) {
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
