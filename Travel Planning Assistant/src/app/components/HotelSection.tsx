import { HotelSuggestion } from '../types/travel';
import { Hotel } from 'lucide-react';

interface HotelSectionProps {
  suggestion: HotelSuggestion;
}

export function HotelSection({ suggestion }: HotelSectionProps) {
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

      {suggestion.reason && (
        <p className="hotel-reason">{suggestion.reason}</p>
      )}

      {suggestion.candidates && suggestion.candidates.length > 0 && (
        <div className="hotel-candidates">
          {suggestion.candidates.map((hotel, idx) => (
            <div key={idx} className="hotel-card">
              <div className="hotel-name">{hotel.name}</div>
              {hotel.price_range && (
                <div className="hotel-price">{hotel.price_range}</div>
              )}
              {hotel.features && hotel.features.length > 0 && (
                <div className="hotel-features">
                  {hotel.features.map((feature, fIdx) => (
                    <span key={fIdx} className="feature-tag">
                      {feature}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
