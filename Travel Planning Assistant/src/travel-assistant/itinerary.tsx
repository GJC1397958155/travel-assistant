import { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Calendar,
  Cloud,
  Hotel,
  Lightbulb,
  Loader2,
  MapPin,
  Navigation,
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
  DayRouteMapResponse,
  HotelSuggestion,
  RouteLeg,
  RoutePoint,
  StructuredItinerary,
} from './types';
import { fetchDayRouteMap } from './apiRuntime';
import { DayRouteMap } from './DayRouteMap';
import { getAmapConfigError } from './amapLoader';

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

function normalizeRouteLabel(value?: string) {
  return value?.trim() ?? '';
}

function getRoutePointLabel(point: RoutePoint) {
  return point.label || point.location || point.title || `第 ${point.order} 站`;
}

function getDisplayRoutePoints(plan: DailyPlan): RoutePoint[] {
  if (plan.route_points && plan.route_points.length > 0) {
    return plan.route_points.filter((point) => normalizeRouteLabel(getRoutePointLabel(point)));
  }

  const routePoints: RoutePoint[] = [];
  const timeSlots: Array<['morning' | 'afternoon' | 'evening', string]> = [
    ['morning', '上午'],
    ['afternoon', '下午'],
    ['evening', '晚上'],
  ];

  for (const [slotKey, slotLabel] of timeSlots) {
    const items = plan[slotKey] ?? [];
    for (const item of items) {
      const label = normalizeRouteLabel(item.location || item.title);
      if (!label || label === '待补充安排') {
        continue;
      }

      if (routePoints.length > 0) {
        const previous = routePoints[routePoints.length - 1];
        if (normalizeRouteLabel(getRoutePointLabel(previous)) === label) {
          continue;
        }
      }

      routePoints.push({
        order: routePoints.length + 1,
        label,
        title: item.title,
        location: item.location,
        time_slot: slotLabel,
      });
    }
  }

  return routePoints;
}

function getRouteModeLabel(mode?: string) {
  switch (mode) {
    case 'driving':
      return '驾车';
    case 'transit':
      return '公交/地铁';
    default:
      return '步行';
  }
}

function DailyRoutePreview({ plan, city }: { plan: DailyPlan; city?: string }) {
  const routePoints = getDisplayRoutePoints(plan);
  const routeLegs = plan.route_legs ?? [];
  const [isMapOpen, setIsMapOpen] = useState(false);
  const [isMapLoading, setIsMapLoading] = useState(false);
  const [mapError, setMapError] = useState('');
  const [mapData, setMapData] = useState<DayRouteMapResponse | null>(null);
  const mapRequestRef = useRef<AbortController | null>(null);
  const routeSignature = [
    city || '',
    ...routePoints.map((point) =>
      [point.order, getRoutePointLabel(point), point.lng ?? '', point.lat ?? ''].join(':'),
    ),
    ...routeLegs.map((leg) =>
      [
        leg.from_order,
        leg.to_order,
        leg.mode ?? '',
        leg.duration_text ?? '',
        leg.distance_text ?? '',
      ].join(':'),
    ),
  ].join('|');

  useEffect(() => {
    mapRequestRef.current?.abort();
    mapRequestRef.current = null;
    setIsMapOpen(false);
    setIsMapLoading(false);
    setMapError('');
    setMapData(null);
  }, [routeSignature]);

  useEffect(() => {
    return () => {
      mapRequestRef.current?.abort();
    };
  }, []);

  if (routePoints.length < 2 && routeLegs.length === 0) {
    return null;
  }

  const handleToggleMap = async () => {
    if (isMapOpen) {
      mapRequestRef.current?.abort();
      mapRequestRef.current = null;
      setIsMapLoading(false);
      setIsMapOpen(false);
      return;
    }

    setIsMapOpen(true);

    if (mapData || isMapLoading) {
      return;
    }

    if (routePoints.length < 2) {
      setMapError('当前这一天的地点不足，暂时无法生成地图路线。');
      return;
    }

    const configError = getAmapConfigError();
    if (configError) {
      setMapError(configError);
      return;
    }

    setMapError('');
    const controller = new AbortController();
    mapRequestRef.current?.abort();
    mapRequestRef.current = controller;
    setIsMapLoading(true);

    try {
      const response = await fetchDayRouteMap(
        {
          city,
          route_points: routePoints,
          route_legs: routeLegs,
        },
        {
          signal: controller.signal,
          timeoutMs: 45000,
        },
      );

      if (controller.signal.aborted) {
        return;
      }

      setMapData(response);

      if (response.route_points.length < 2) {
        setMapError('暂时无法生成可展示的地图路线，请稍后重试。');
      }
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }

      setMapError(error instanceof Error ? error.message : '地图路线加载失败，请稍后重试。');
    } finally {
      if (mapRequestRef.current === controller) {
        mapRequestRef.current = null;
      }
      setIsMapLoading(false);
    }
  };

  return (
    <div className="daily-route-preview">
      <div className="daily-route-title">
        <Navigation size={16} />
        <span>路线速览</span>
      </div>

      {routePoints.length > 1 && (
        <div className="daily-route-path">
          {routePoints.map((point, idx) => {
            const label = getRoutePointLabel(point);
            return (
              <div key={`${label}-${idx}`} className="daily-route-node">
                <span className="daily-route-stop">{label}</span>
                {idx < routePoints.length - 1 && <ArrowRight size={14} className="daily-route-arrow" />}
              </div>
            );
          })}
        </div>
      )}

      <div className="daily-route-actions">
        <button type="button" className="route-map-toggle-btn" onClick={() => void handleToggleMap()}>
          {isMapLoading ? <Loader2 size={14} className="animate-spin" /> : <MapPin size={14} />}
          <span>{isMapOpen ? '收起地图' : '查看地图'}</span>
        </button>
      </div>

      {routeLegs.length > 0 && (
        <div className="route-leg-list">
          {routeLegs.map((leg: RouteLeg, idx) => (
            <div key={`${leg.from_order}-${leg.to_order}-${idx}`} className="route-leg-item">
              <div className="route-leg-topline">
                <span className={`route-mode-badge ${leg.mode || 'walking'}`}>
                  {getRouteModeLabel(leg.mode)}
                </span>
                <span className="route-leg-link">
                  {(leg.from_label || `第 ${leg.from_order} 站`) +
                    ' -> ' +
                    (leg.to_label || `第 ${leg.to_order} 站`)}
                </span>
              </div>

              {(leg.duration_text || leg.distance_text) && (
                <div className="route-leg-meta">
                  {leg.duration_text && <span>{leg.duration_text}</span>}
                  {leg.distance_text && <span>{leg.distance_text}</span>}
                </div>
              )}

              {leg.summary && <div className="route-leg-summary">{leg.summary}</div>}
            </div>
          ))}
        </div>
      )}

      {isMapOpen && (
        <div className="route-map-shell">
          {isMapLoading && <div className="route-map-state">正在加载这一天的地图路线...</div>}

          {!isMapLoading && mapError && <div className="route-map-state error">{mapError}</div>}

          {!isMapLoading && !mapError && mapData && (
            <>
              {mapData.warnings && mapData.warnings.length > 0 && (
                <div className="route-map-warnings">
                  {mapData.warnings.map((warning, idx) => (
                    <div key={`${warning}-${idx}`} className="route-map-warning">
                      {warning}
                    </div>
                  ))}
                </div>
              )}

              <DayRouteMap data={mapData} />
            </>
          )}
        </div>
      )}
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

function DailyPlans({ plans, destination }: { plans: DailyPlan[]; destination?: string }) {
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

            <DailyRoutePreview plan={plan} city={destination} />

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
          <p>先在左侧查看自然语言回复，结构化结果生成后会显示在这里。</p>
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

        {itinerary.daily_plans && itinerary.daily_plans.length > 0 && (
          <DailyPlans plans={itinerary.daily_plans} destination={itinerary.destination} />
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
