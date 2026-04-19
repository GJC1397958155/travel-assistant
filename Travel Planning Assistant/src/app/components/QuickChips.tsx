interface QuickChipsProps {
  onQuickClick: (text: string) => void;
}

const QUICK_SUGGESTIONS = [
  '大连3天情侣游，5月20号出发，预算3000',
  '杭州2天轻松游，这周末，预算2000',
  '上海3天拍照路线，下个月，预算4000',
];

export function QuickChips({ onQuickClick }: QuickChipsProps) {
  return (
    <div className="quick-chips">
      <div className="chips-title">快速开始：</div>
      <div className="chips-list">
        {QUICK_SUGGESTIONS.map((text, idx) => (
          <button
            key={idx}
            className="chip-btn"
            onClick={() => onQuickClick(text)}
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}
