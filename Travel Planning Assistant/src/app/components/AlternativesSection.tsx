import { Lightbulb } from 'lucide-react';

interface AlternativesSectionProps {
  alternatives: string[];
}

export function AlternativesSection({ alternatives }: AlternativesSectionProps) {
  return (
    <div className="itinerary-section">
      <h3 className="section-title">
        <Lightbulb size={18} />
        备选方案
      </h3>
      <div className="alternatives-list">
        {alternatives.map((alt, idx) => (
          <div key={idx} className="alternative-item">
            <span className="alternative-number">{idx + 1}</span>
            <span>{alt}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
