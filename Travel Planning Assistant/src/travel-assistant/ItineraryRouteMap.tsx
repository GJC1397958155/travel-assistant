import { useEffect, useMemo, useRef, useState } from 'react';
import { MapPinned, Navigation } from 'lucide-react';
import { Activity, StructuredItinerary } from './types';

type AMapApi = any;

interface AMapWindow extends Window {
  AMap?: AMapApi;
  _AMapSecurityConfig?: {
    securityJsCode?: string;
  };
}

interface RouteStop {
  key: string;
  label: string;
  title: string;
  query: string;
  timeOfDay: string;
}

interface RouteDay {
  key: string;
  title: string;
  subtitle: string;
  stops: RouteStop[];
}

interface ResolvedStop extends RouteStop {
  position: any;
  formattedAddress: string;
}

const AMAP_JS_KEY = sanitizeEnvValue(import.meta.env.VITE_AMAP_JS_KEY);
const AMAP_SECURITY_CODE = sanitizeEnvValue(import.meta.env.VITE_AMAP_SECURITY_CODE);

const GENERIC_STOP_PATTERNS = [
  /酒店/,
  /早餐/,
  /午餐/,
  /晚餐/,
  /用餐/,
  /自由活动/,
  /返程/,
  /休息/,
  /入住/,
  /出发/,
  /集合/,
];

let amapLoadPromise: Promise<AMapApi> | null = null;

function sanitizeEnvValue(value: string | undefined): string {
  return (value ?? '').trim().replace(/^['"]|['"]$/g, '');
}

function normalizeText(value?: string): string {
  return (value ?? '').replace(/\s+/g, ' ').trim();
}

function makeStopLabel(index: number): string {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  const group = Math.floor(index / alphabet.length);
  const letter = alphabet[index % alphabet.length];
  return group === 0 ? letter : `${letter}${group}`;
}

function isUsefulStopQuery(query: string): boolean {
  if (!query || query.length < 2) {
    return false;
  }

  return !GENERIC_STOP_PATTERNS.some((pattern) => pattern.test(query));
}

function makeAddressQuery(query: string, destination?: string): string {
  const cleanQuery = normalizeText(query);
  const cleanDestination = normalizeText(destination);

  if (!cleanDestination || cleanQuery.includes(cleanDestination)) {
    return cleanQuery;
  }

  return `${cleanDestination}${cleanQuery}`;
}

function collectStops(
  activities: Activity[] | undefined,
  timeOfDay: string,
): RouteStop[] {
  if (!activities || activities.length === 0) {
    return [];
  }

  return activities.flatMap((activity, index) => {
    const location = normalizeText(activity.location);
    const title = normalizeText(activity.title);
    const query = location || title;

    if (!isUsefulStopQuery(query)) {
      return [];
    }

    return [
      {
        key: `${timeOfDay}-${index}-${query}`,
        label: '',
        title: title || query,
        query,
        timeOfDay,
      },
    ];
  });
}

function buildRouteDays(itinerary: StructuredItinerary): RouteDay[] {
  return (itinerary.daily_plans ?? [])
    .map((plan) => {
      const rawStops = [
        ...collectStops(plan.morning, '上午'),
        ...collectStops(plan.afternoon, '下午'),
        ...collectStops(plan.evening, '晚上'),
      ];

      const seen = new Set<string>();
      const stops = rawStops
        .filter((stop) => {
          const dedupeKey = stop.query.toLowerCase();
          if (seen.has(dedupeKey)) {
            return false;
          }
          seen.add(dedupeKey);
          return true;
        })
        .map((stop, index) => ({
          ...stop,
          label: makeStopLabel(index),
        }));

      return {
        key: `day-${plan.day}`,
        title: `Day ${plan.day}`,
        subtitle: normalizeText(plan.title || plan.date || plan.weather),
        stops,
      };
    })
    .filter((day) => day.stops.length > 0);
}

async function loadAmap(): Promise<AMapApi> {
  const amapWindow = window as AMapWindow;

  if (amapWindow.AMap) {
    return amapWindow.AMap;
  }

  if (!AMAP_JS_KEY) {
    throw new Error('未检测到高德地图 JS Key，请先在 .env 中配置 VITE_AMAP_JS_KEY。');
  }

  if (amapLoadPromise) {
    return amapLoadPromise;
  }

  amapLoadPromise = new Promise<AMapApi>((resolve, reject) => {
    if (AMAP_SECURITY_CODE) {
      amapWindow._AMapSecurityConfig = {
        securityJsCode: AMAP_SECURITY_CODE,
      };
    }

    const existingScript = document.querySelector<HTMLScriptElement>(
      'script[data-amap-jsapi="true"]',
    );

    const handleSuccess = () => {
      if (amapWindow.AMap) {
        resolve(amapWindow.AMap);
        return;
      }

      reject(new Error('高德地图脚本已加载，但全局对象不可用。'));
    };

    const handleError = () => {
      reject(new Error('高德地图脚本加载失败，请检查网络、Key 或安全密钥配置。'));
    };

    if (existingScript) {
      existingScript.addEventListener('load', handleSuccess, { once: true });
      existingScript.addEventListener('error', handleError, { once: true });

      if (existingScript.dataset.loaded === 'true') {
        handleSuccess();
      }
      return;
    }

    const script = document.createElement('script');
    script.async = true;
    script.dataset.amapJsapi = 'true';
    script.src =
      `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(AMAP_JS_KEY)}` +
      '&plugin=AMap.Geocoder,AMap.Scale,AMap.ToolBar';
    script.addEventListener(
      'load',
      () => {
        script.dataset.loaded = 'true';
        handleSuccess();
      },
      { once: true },
    );
    script.addEventListener('error', handleError, { once: true });
    document.head.appendChild(script);
  }).catch((error) => {
    amapLoadPromise = null;
    throw error;
  });

  return amapLoadPromise;
}

function geocodeStop(
  geocoder: any,
  stop: RouteStop,
  destination?: string,
): Promise<ResolvedStop> {
  const addressQuery = makeAddressQuery(stop.query, destination);

  return new Promise<ResolvedStop>((resolve, reject) => {
    geocoder.getLocation(addressQuery, (status: string, result: any) => {
      const geocodes = result?.geocodes ?? [];
      if (status === 'complete' && geocodes.length > 0) {
        const geocode = geocodes[0];
        resolve({
          ...stop,
          position: geocode.location,
          formattedAddress: geocode.formattedAddress ?? addressQuery,
        });
        return;
      }

      reject(new Error(`未找到地点：${addressQuery}`));
    });
  });
}

async function geocodeStops(
  AMap: AMapApi,
  routeDay: RouteDay,
  destination?: string,
): Promise<{ resolved: ResolvedStop[]; failed: RouteStop[] }> {
  const geocoder = new AMap.Geocoder({
    city: normalizeText(destination) || undefined,
  });

  const results = await Promise.allSettled(
    routeDay.stops.map((stop) => geocodeStop(geocoder, stop, destination)),
  );

  const resolved: ResolvedStop[] = [];
  const failed: RouteStop[] = [];

  results.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      resolved.push(result.value);
      return;
    }

    failed.push(routeDay.stops[index]);
  });

  return { resolved, failed };
}

function clearMapOverlays(map: any, overlays: any[]) {
  if (overlays.length > 0) {
    map.remove(overlays);
    overlays.splice(0, overlays.length);
  }
}

function buildMarkerHtml(label: string): string {
  return `<div class="route-marker-pin">${label}</div>`;
}

export function ItineraryRouteMap({ itinerary }: { itinerary: StructuredItinerary }) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const overlayRef = useRef<any[]>([]);

  const routeDays = useMemo(() => buildRouteDays(itinerary), [itinerary]);
  const [activeDayIndex, setActiveDayIndex] = useState(0);
  const [mapStatus, setMapStatus] = useState<'loading' | 'ready' | 'error' | 'missing-key'>(
    AMAP_JS_KEY ? 'loading' : 'missing-key',
  );
  const [routeStatus, setRouteStatus] = useState<'idle' | 'loading' | 'ready' | 'empty' | 'error'>(
    routeDays.length > 0 ? 'idle' : 'empty',
  );
  const [statusMessage, setStatusMessage] = useState(
    AMAP_JS_KEY ? '正在载入高德地图…' : '未检测到高德地图 JS Key，请先在 .env 中补充配置。',
  );

  const activeDay = routeDays[activeDayIndex];

  useEffect(() => {
    if (activeDayIndex >= routeDays.length) {
      setActiveDayIndex(0);
    }
  }, [activeDayIndex, routeDays.length]);

  useEffect(() => {
    let cancelled = false;

    async function initMap() {
      if (!mapContainerRef.current) {
        return;
      }

      if (!AMAP_JS_KEY) {
        setMapStatus('missing-key');
        return;
      }

      try {
        setMapStatus('loading');
        setStatusMessage('正在载入高德地图…');
        const AMap = await loadAmap();
        if (cancelled || !mapContainerRef.current) {
          return;
        }

        if (!mapRef.current) {
          const map = new AMap.Map(mapContainerRef.current, {
            zoom: 11,
            resizeEnable: true,
          });

          if (typeof AMap.Scale === 'function') {
            map.addControl(new AMap.Scale());
          }

          if (typeof AMap.ToolBar === 'function') {
            map.addControl(new AMap.ToolBar());
          }

          mapRef.current = map;
        }

        setMapStatus('ready');
      } catch (error) {
        if (cancelled) {
          return;
        }

        setMapStatus('error');
        setStatusMessage(
          error instanceof Error ? error.message : '高德地图初始化失败，请稍后重试。',
        );
      }
    }

    void initMap();

    return () => {
      cancelled = true;

      if (mapRef.current) {
        clearMapOverlays(mapRef.current, overlayRef.current);
        mapRef.current.destroy();
        mapRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (mapStatus !== 'ready' || !mapRef.current) {
      return;
    }

    const map = mapRef.current;
    window.setTimeout(() => {
      map.resize?.();
    }, 80);
  });

  useEffect(() => {
    if (mapStatus !== 'ready' || !mapRef.current) {
      return;
    }

    const map = mapRef.current;
    let cancelled = false;

    async function drawRoute() {
      clearMapOverlays(map, overlayRef.current);

      if (!activeDay) {
        setRouteStatus('empty');
        setStatusMessage('当前行程里还没有足够具体的地点，暂时无法生成 A-B-C 路线。');
        return;
      }

      try {
        setRouteStatus('loading');
        setStatusMessage('正在定位路线点位…');

        const AMap = await loadAmap();
        const { resolved, failed } = await geocodeStops(AMap, activeDay, itinerary.destination);

        if (cancelled) {
          return;
        }

        if (resolved.length === 0) {
          setRouteStatus('error');
          setStatusMessage('这些地点暂时无法被高德识别，请把行程里的地点写得更具体一些。');
          return;
        }

        const overlays: any[] = resolved.map((stop) => {
          const marker = new AMap.Marker({
            position: stop.position,
            anchor: 'bottom-center',
            title: stop.formattedAddress,
            content: buildMarkerHtml(stop.label),
          });

          marker.setLabel?.({
            direction: 'right',
            offset: new AMap.Pixel(12, -4),
            content: `<div class="route-marker-label">${stop.title}</div>`,
          });

          return marker;
        });

        if (resolved.length > 1) {
          overlays.push(
            new AMap.Polyline({
              path: resolved.map((stop) => stop.position),
              strokeColor: '#0ea5e9',
              strokeWeight: 6,
              strokeOpacity: 0.9,
              lineCap: 'round',
              lineJoin: 'round',
            }),
          );
        }

        map.add(overlays);
        overlayRef.current.push(...overlays);
        map.setFitView(overlays, false, [48, 48, 48, 48]);

        setRouteStatus('ready');
        setStatusMessage(
          failed.length > 0
            ? `已定位 ${resolved.length}/${activeDay.stops.length} 个地点，未识别地点已自动跳过。`
            : `已按活动顺序生成 ${resolved.length} 站路线。`,
        );
      } catch (error) {
        if (cancelled) {
          return;
        }

        setRouteStatus('error');
        setStatusMessage(
          error instanceof Error ? error.message : '路线绘制失败，请稍后再试。',
        );
      }
    }

    void drawRoute();

    return () => {
      cancelled = true;
      clearMapOverlays(map, overlayRef.current);
    };
  }, [activeDay, itinerary.destination, mapStatus]);

  if (routeDays.length === 0) {
    return (
      <div className="itinerary-section">
        <h3 className="section-title">
          <MapPinned size={18} />
          地图路线
        </h3>
        <div className="route-empty-state">
          当前行程里还没有可用于绘制地图的地点。
          <br />
          等右侧行程里出现更具体的景点、商圈或地址后，这里会自动生成 A-B-C 路线。
        </div>
      </div>
    );
  }

  const overlayMessage =
    mapStatus === 'loading'
      ? '正在载入高德地图…'
      : mapStatus === 'error'
        ? statusMessage
        : mapStatus === 'missing-key'
          ? '未检测到高德地图 JS Key，请在 .env 中配置。'
          : routeStatus === 'loading'
            ? '正在定位路线点位…'
            : routeStatus === 'error'
              ? statusMessage
              : null;

  return (
    <div className="itinerary-section">
      <div className="route-section-heading">
        <h3 className="section-title">
          <MapPinned size={18} />
          地图路线
        </h3>
        <p className="route-section-note">按每天活动顺序生成 A-B-C 路线预览。</p>
      </div>

      <div className="route-day-tabs">
        {routeDays.map((day, index) => (
          <button
            key={day.key}
            type="button"
            className={`route-day-tab ${index === activeDayIndex ? 'active' : ''}`}
            onClick={() => setActiveDayIndex(index)}
          >
            <span>{day.title}</span>
            <span>{day.stops.length} 站</span>
          </button>
        ))}
      </div>

      {activeDay && (
        <div className="route-summary">
          <div>
            <div className="route-summary-title">
              {activeDay.title}
              {activeDay.subtitle ? ` · ${activeDay.subtitle}` : ''}
            </div>
            <div className="route-summary-note">{statusMessage}</div>
          </div>
          <div className="route-summary-badge">
            <Navigation size={16} />
            <span>{activeDay.stops.length} 个停靠点</span>
          </div>
        </div>
      )}

      <div className="route-map-shell">
        <div ref={mapContainerRef} className="route-map-canvas" />
        {overlayMessage && (
          <div
            className={`route-map-overlay ${
              mapStatus === 'error' || mapStatus === 'missing-key' || routeStatus === 'error'
                ? 'is-error'
                : ''
            }`}
          >
            {overlayMessage}
          </div>
        )}
      </div>

      {activeDay && (
        <div className="route-stop-list">
          {activeDay.stops.map((stop) => (
            <div key={stop.key} className="route-stop-item">
              <div className="route-stop-badge">{stop.label}</div>
              <div className="route-stop-content">
                <div className="route-stop-title">{stop.title}</div>
                <div className="route-stop-meta">
                  {stop.timeOfDay} · {stop.query}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="route-disclaimer">
        当前版本按行程中的地点顺序连线，适合快速看 A-B-C 怎么走，不等同于实时导航路线。
      </p>
    </div>
  );
}
