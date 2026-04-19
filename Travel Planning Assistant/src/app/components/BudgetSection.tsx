import { BudgetAdvice } from '../types/travel';
import { Wallet } from 'lucide-react';

interface BudgetSectionProps {
  advice: BudgetAdvice;
}

export function BudgetSection({ advice }: BudgetSectionProps) {
  if (!advice.level && !advice.summary) {
    return null;
  }

  const getLevelColor = (level: string) => {
    const lowerLevel = level.toLowerCase();
    if (lowerLevel.includes('充裕') || lowerLevel.includes('宽松')) return 'success';
    if (lowerLevel.includes('紧张') || lowerLevel.includes('不足')) return 'warning';
    return 'info';
  };

  return (
    <div className="itinerary-section">
      <h3 className="section-title">
        <Wallet size={18} />
        预算建议
      </h3>
      
      {advice.level && (
        <div className={`budget-level ${getLevelColor(advice.level)}`}>
          {advice.level}
        </div>
      )}

      {advice.summary && (
        <p className="budget-summary">{advice.summary}</p>
      )}
    </div>
  );
}
