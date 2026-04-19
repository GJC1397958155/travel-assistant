import { StructuredItinerary } from '../types/travel';
import { MapPin, Calendar, Users, Wallet, Cloud } from 'lucide-react';

interface ItineraryOverviewProps {
  itinerary: StructuredItinerary;
}

export function ItineraryOverview({ itinerary }: ItineraryOverviewProps) {
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

        {itinerary.days && (
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

        {itinerary.budget && (
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
            <div className="overview-icon">✨</div>
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
