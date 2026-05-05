import { useEffect, useMemo, useRef, useState } from 'react';
import { MapPinned, Maximize2, Minimize2, Navigation, RefreshCw } from 'lucide-react';
import { Activity, MapCandidate, StructuredItinerary } from './types';

type AMapApi = any;
type RouteMode = 'walking' | 'driving' | 'transit';

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
  queries: string[];
  timeOfDay: string;
  timeSlot: 'morning' | 'afternoon' | 'evening';
  dayNumber?: number;
  activityIndex: number;
  backendPosition?: {
    lng: number;
    lat: number;
  };
  poiId?: string;
  formattedAddress?: string;
  mapSource?: string;
  candidatePlaces: RouteCandidate[];
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

interface RouteCandidate {
  name: string;
  formattedAddress: string;
  longitude: number;
  latitude: number;
  poiId?: string;
}

interface FailedStop extends RouteStop {
  reason: string;
  lastTriedQuery: string;
  candidatePlaces: RouteCandidate[];
}

interface RouteSegment {
  key: string;
  fromLabel: string;
  toLabel: string;
  fromTitle: string;
  toTitle: string;
  distanceText: string;
  durationText: string;
  fallback: boolean;
}

interface RoutePathResult {
  path: any[];
  routedSegments: number;
  fallbackSegments: number;
  segments: RouteSegment[];
}

interface CachedRouteDay {
  status: 'idle' | 'loading' | 'ready' | 'error';
  resolved: ResolvedStop[];
  failed: FailedStop[];
  routePath: any[];
  routeSegments: RouteSegment[];
  routedSegments: number;
  fallbackSegments: number;
  errorMessage?: string;
}

const AMAP_JS_KEY = sanitizeEnvValue(import.meta.env.VITE_AMAP_JS_KEY);
const AMAP_SECURITY_CODE = sanitizeEnvValue(import.meta.env.VITE_AMAP_SECURITY_CODE);
const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const GEOCODE_TIMEOUT_MS = 8000;
const ROUTE_TIMEOUT_MS = 12000;
const OVERLAP_GROUP_EPSILON = 0.00012;
const OVERLAP_SPREAD_RADIUS = 0.00018;
const PATH_POINT_EPSILON = 0.000001;

const ROUTE_MODE_LABELS: Record<RouteMode, string> = {
  walking: '步行',
  driving: '打车',
  transit: '公交',
};

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

const STOP_DECORATOR_PATTERNS = [
  /\bcitywalk\b/gi,
  /打卡/g,
  /漫步/g,
  /散步/g,
  /闲逛/g,
  /赏景/g,
  /看夜景/g,
  /拍照/g,
  /拍照点/g,
  /早餐/g,
  /午餐/g,
  /晚餐/g,
  /用餐/g,
  /休息/g,
  /入住/g,
  /出发/g,
  /返程/g,
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

function dedupeQueries(queries: string[]): string[] {
  const seen = new Set<string>();

  return queries
    .map((query) => normalizeText(query))
    .filter((query) => {
      if (!isUsefulStopQuery(query)) {
        return false;
      }

      const key = query.toLowerCase();
      if (seen.has(key)) {
        return false;
      }

      seen.add(key);
      return true;
    });
}

function stripStopDecorators(query: string): string {
  let cleaned = normalizeText(query);
  cleaned = cleaned.replace(/[()（）【】[\]]/g, ' ');
  cleaned = cleaned.replace(/[·•/|]/g, ' ');
  cleaned = cleaned.replace(/[，、。；;:：]/g, ' ');

  STOP_DECORATOR_PATTERNS.forEach((pattern) => {
    cleaned = cleaned.replace(pattern, ' ');
  });

  return normalizeText(cleaned);
}

function buildStopQueries(location: string, title: string): string[] {
  const normalizedLocation = normalizeText(location);
  const normalizedTitle = normalizeText(title);
  const cleanLocation = stripStopDecorators(normalizedLocation);
  const cleanTitle = stripStopDecorators(normalizedTitle);

  return dedupeQueries([
    normalizedLocation,
    normalizedTitle,
    cleanLocation,
    cleanTitle,
    ...cleanLocation.split(/\s+/),
    ...cleanTitle.split(/\s+/),
  ]);
}

function buildAddressQueries(query: string, destination?: string): string[] {
  const cleanQuery = normalizeText(query);
  const cleanDestination = normalizeText(destination);

  if (!cleanQuery) {
    return [];
  }

  if (!cleanDestination || cleanQuery.includes(cleanDestination)) {
    return [cleanQuery];
  }

  return dedupeQueries([
    `${cleanDestination}${cleanQuery}`,
    `${cleanDestination} ${cleanQuery}`,
    cleanQuery,
  ]);
}

function normalizeNumericValue(value: unknown): number | undefined {
  const normalized =
    typeof value === 'number'
      ? value
      : typeof value === 'string'
        ? Number(value)
        : Number.NaN;

  return Number.isFinite(normalized) ? normalized : undefined;
}

function normalizeCandidatePlaces(candidates: MapCandidate[] | undefined): RouteCandidate[] {
  if (!Array.isArray(candidates)) {
    return [];
  }

  const seen = new Set<string>();
  const normalized: RouteCandidate[] = [];

  candidates.forEach((candidate) => {
    const longitude = normalizeNumericValue(candidate.longitude);
    const latitude = normalizeNumericValue(candidate.latitude);
    if (longitude === undefined || latitude === undefined) {
      return;
    }

    const name = normalizeText(candidate.name);
    const formattedAddress = normalizeText(candidate.formatted_address || candidate.address);
    const poiId = normalizeText(candidate.poi_id);
    const key = poiId || `${name}|${formattedAddress}|${longitude}|${latitude}`;
    if (seen.has(key)) {
      return;
    }

    seen.add(key);
    normalized.push({
      name: name || formattedAddress || '候选地点',
      formattedAddress,
      longitude,
      latitude,
      poiId: poiId || undefined,
    });
  });

  return normalized;
}

function collectStops(
  activities: Activity[] | undefined,
  timeOfDay: string,
  timeSlot: RouteStop['timeSlot'],
): RouteStop[] {
  if (!activities || activities.length === 0) {
    return [];
  }

  return activities.flatMap((activity, index) => {
    const location = normalizeText(activity.location);
    const title = normalizeText(activity.title);
    const queries = buildStopQueries(location, title);
    const query = queries[0] || location || title;
    const longitude = normalizeNumericValue(activity.longitude);
    const latitude = normalizeNumericValue(activity.latitude);
    const candidatePlaces = normalizeCandidatePlaces(activity.map_candidates);

    if (!isUsefulStopQuery(query)) {
      return [];
    }

    return [
      {
        key: `${timeOfDay}-${index}-${query}`,
        label: '',
        title: title || query,
        query,
        queries,
        timeOfDay,
        timeSlot,
        activityIndex: index,
        backendPosition:
          longitude !== undefined && latitude !== undefined
            ? {
                lng: longitude,
                lat: latitude,
              }
            : undefined,
        poiId: normalizeText(activity.poi_id) || undefined,
        formattedAddress: normalizeText(activity.formatted_address) || undefined,
        mapSource: normalizeText(activity.map_source) || undefined,
        candidatePlaces,
      },
    ];
  });
}

function buildRouteDays(itinerary: StructuredItinerary): RouteDay[] {
  return (itinerary.daily_plans ?? [])
    .map((plan) => {
      const rawStops = [
        ...collectStops(plan.morning, '上午', 'morning'),
        ...collectStops(plan.afternoon, '下午', 'afternoon'),
        ...collectStops(plan.evening, '晚上', 'evening'),
      ];

      const seen = new Set<string>();
      const stops = rawStops
        .filter((stop) => {
          const key = stop.query.toLowerCase();
          if (seen.has(key)) {
            return false;
          }

          seen.add(key);
          return true;
        })
        .map((stop, index) => ({
          ...stop,
          label: makeStopLabel(index),
          dayNumber: plan.day,
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

function createEmptyRouteDay(status: CachedRouteDay['status'] = 'idle'): CachedRouteDay {
  return {
    status,
    resolved: [],
    failed: [],
    routePath: [],
    routeSegments: [],
    routedSegments: 0,
    fallbackSegments: 0,
  };
}

function orderResolvedStops(routeDay: RouteDay, resolved: ResolvedStop[]): ResolvedStop[] {
  const resolvedByKey = new Map(resolved.map((stop) => [stop.key, stop]));
  return routeDay.stops.flatMap((stop) => {
    const resolvedStop = resolvedByKey.get(stop.key);
    return resolvedStop ? [resolvedStop] : [];
  });
}

function orderFailedStops(routeDay: RouteDay, failed: FailedStop[]): FailedStop[] {
  const failedByKey = new Map(failed.map((stop) => [stop.key, stop]));
  return routeDay.stops.flatMap((stop) => {
    const failedStop = failedByKey.get(stop.key);
    return failedStop ? [failedStop] : [];
  });
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
      '&plugin=AMap.Geocoder,AMap.Scale,AMap.ToolBar,AMap.Walking';
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

function buildResolvedStopFromBackend(AMap: AMapApi, stop: RouteStop): ResolvedStop | null {
  if (!stop.backendPosition) {
    return null;
  }

  return {
    ...stop,
    position: createLngLat(AMap, stop.backendPosition.lng, stop.backendPosition.lat),
    formattedAddress: stop.formattedAddress || stop.query,
  };
}

function buildResolvedStopFromCandidate(
  AMap: AMapApi,
  stop: RouteStop,
  candidate: RouteCandidate,
): ResolvedStop {
  return {
    ...stop,
    backendPosition: {
      lng: candidate.longitude,
      lat: candidate.latitude,
    },
    poiId: candidate.poiId,
    formattedAddress: candidate.formattedAddress || stop.formattedAddress || stop.query,
    position: createLngLat(AMap, candidate.longitude, candidate.latitude),
    candidatePlaces: [candidate, ...stop.candidatePlaces.filter((item) => item.poiId !== candidate.poiId)],
  };
}

function formatDistanceText(distanceMeters?: number): string {
  if (!Number.isFinite(distanceMeters)) {
    return '距离待确认';
  }

  if ((distanceMeters ?? 0) >= 1000) {
    return `${((distanceMeters ?? 0) / 1000).toFixed(1)} 公里`;
  }

  return `${Math.round(distanceMeters ?? 0)} 米`;
}

function formatDurationText(durationSeconds?: number): string {
  if (!Number.isFinite(durationSeconds)) {
    return '时长待确认';
  }

  const minutes = Math.max(1, Math.round((durationSeconds ?? 0) / 60));
  return `${minutes} 分钟`;
}

function estimateFallbackDistanceMeters(from: any, to: any): number | undefined {
  const fromCoords = extractPositionCoords(from);
  const toCoords = extractPositionCoords(to);
  if (!fromCoords || !toCoords) {
    return undefined;
  }

  const toRadians = (value: number) => (value * Math.PI) / 180;
  const earthRadiusMeters = 6371000;
  const deltaLat = toRadians(toCoords.lat - fromCoords.lat);
  const deltaLng = toRadians(toCoords.lng - fromCoords.lng);
  const a =
    Math.sin(deltaLat / 2) * Math.sin(deltaLat / 2) +
    Math.cos(toRadians(fromCoords.lat)) *
      Math.cos(toRadians(toCoords.lat)) *
      Math.sin(deltaLng / 2) *
      Math.sin(deltaLng / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return earthRadiusMeters * c;
}

function buildRouteCacheEntryKey(dayKey: string): string {
  return dayKey;
}

async function fetchRouteSegmentData(
  from: ResolvedStop,
  to: ResolvedStop,
  options: {
    city: string;
    mode: RouteMode;
  },
): Promise<{ path: any[]; distanceMeters?: number; durationSeconds?: number; fallback: boolean }> {
  const fromCoords = extractPositionCoords(from.position);
  const toCoords = extractPositionCoords(to.position);

  if (!fromCoords || !toCoords) {
    return {
      path: [from.position, to.position],
      fallback: true,
    };
  }

  const response = await fetch(`${API_BASE_URL}/map/route`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      origin: {
        longitude: fromCoords.lng,
        latitude: fromCoords.lat,
      },
      destination: {
        longitude: toCoords.lng,
        latitude: toCoords.lat,
      },
      city: options.city,
      mode: options.mode,
    }),
  });

  if (!response.ok) {
    throw new Error(`路线服务请求失败：${response.status}`);
  }

  const data = (await response.json()) as {
    path?: Array<[number, number]>;
    distance_meters?: number | null;
    duration_seconds?: number | null;
    fallback?: boolean;
  };

  return {
    path: (data.path ?? []).map(([lng, lat]) => ({ lng, lat })),
    distanceMeters:
      typeof data.distance_meters === 'number' ? data.distance_meters : undefined,
    durationSeconds:
      typeof data.duration_seconds === 'number' ? data.duration_seconds : undefined,
    fallback: Boolean(data.fallback),
  };
}

function applyResolvedStopToItinerary(
  itinerary: StructuredItinerary,
  stop: RouteStop,
  resolvedStop: ResolvedStop,
): StructuredItinerary {
  const coordinates = extractPositionCoords(resolvedStop.position);
  const nextPlans = (itinerary.daily_plans ?? []).map((plan) => {
    if (plan.day !== stop.dayNumber) {
      return plan;
    }

    const blockItems = plan[stop.timeSlot] ?? [];
    const nextBlock = blockItems.map((item, index) => {
      if (index !== stop.activityIndex) {
        return item;
      }

      return {
        ...item,
        location: resolvedStop.formattedAddress || item.location,
        longitude: coordinates?.lng,
        latitude: coordinates?.lat,
        poi_id: resolvedStop.poiId,
        formatted_address: resolvedStop.formattedAddress,
        map_query: resolvedStop.query,
        map_source: resolvedStop.mapSource,
        map_candidates: resolvedStop.candidatePlaces.map((candidate) => ({
          name: candidate.name,
          formatted_address: candidate.formattedAddress,
          address: candidate.formattedAddress,
          longitude: candidate.longitude,
          latitude: candidate.latitude,
          poi_id: candidate.poiId,
        })),
      };
    });

    return {
      ...plan,
      [stop.timeSlot]: nextBlock,
    };
  });

  return {
    ...itinerary,
    daily_plans: nextPlans,
  };
}

function buildRouteClientContext(
  itinerary: StructuredItinerary,
  routeMode: RouteMode,
  feasibilityNotes: string[],
): string {
  if (itinerary.status !== 'ready') {
    return '';
  }

  const correctedStops: string[] = [];

  (itinerary.daily_plans ?? []).forEach((plan) => {
    (['morning', 'afternoon', 'evening'] as const).forEach((timeSlot) => {
      (plan[timeSlot] ?? []).forEach((activity) => {
        if (activity.formatted_address || (activity.longitude && activity.latitude)) {
          const location = normalizeText(activity.formatted_address || activity.location || activity.title);
          correctedStops.push(`第${plan.day}天${location}`);
        }
      });
    });
  });

  const sections = [
    `当前地图偏好交通方式：${ROUTE_MODE_LABELS[routeMode]}`,
    correctedStops.length > 0 ? `已确认地图点位：${correctedStops.slice(0, 8).join('；')}` : '',
    feasibilityNotes.length > 0 ? `路线可行性提醒：${feasibilityNotes.join('；')}` : '',
  ].filter(Boolean);

  return sections.join('\n');
}

function buildFeasibilityChecks(
  routeDay: RouteDay | undefined,
  cached: CachedRouteDay | undefined,
  routeMode: RouteMode,
): string[] {
  if (!routeDay || !cached || cached.resolved.length === 0) {
    return [];
  }

  const notes: string[] = [];
  const segmentCount = cached.routeSegments.length;
  const totalMinutes = cached.routeSegments.reduce((sum, segment) => {
    const matched = segment.durationText.match(/(\d+)/);
    return sum + (matched ? Number(matched[1]) : 0);
  }, 0);
  const totalDistanceKm = cached.routeSegments.reduce((sum, segment) => {
    const kmMatch = segment.distanceText.match(/([\d.]+)\s*公里/);
    const meterMatch = segment.distanceText.match(/(\d+)\s*米/);
    if (kmMatch) {
      return sum + Number(kmMatch[1]);
    }
    if (meterMatch) {
      return sum + Number(meterMatch[1]) / 1000;
    }
    return sum;
  }, 0);
  const longestMinutes = cached.routeSegments.reduce((max, segment) => {
    const matched = segment.durationText.match(/(\d+)/);
    return Math.max(max, matched ? Number(matched[1]) : 0);
  }, 0);

  if (routeDay.stops.length >= 5) {
    notes.push('当天停靠点较多，节奏可能偏满。');
  }

  if (routeMode === 'walking' && (totalMinutes >= 140 || totalDistanceKm >= 8)) {
    notes.push('步行总量较高，建议预留休息或切换打车/公交。');
  }

  if (routeMode !== 'walking' && totalMinutes >= 180) {
    notes.push('跨点通勤时间较长，建议精简当天路线。');
  }

  if (segmentCount > 0 && longestMinutes >= 50) {
    notes.push('存在较长单段通勤，顺序可能还能继续优化。');
  }

  const morningTitles = routeDay.stops
    .filter((stop) => stop.timeSlot === 'morning')
    .map((stop) => stop.title)
    .join(' ');
  const eveningTitles = routeDay.stops
    .filter((stop) => stop.timeSlot === 'evening')
    .map((stop) => stop.title)
    .join(' ');

  if (/(夜景|酒吧|夜市|灯光秀)/.test(morningTitles)) {
    notes.push('上午安排里有偏夜间的点位，建议核对营业时间。');
  }

  if (/(博物馆|美术馆|展览|书店|故宫|寺|园|景区)/.test(eveningTitles)) {
    notes.push('晚间安排里有可能较早闭馆的点位，建议提前确认开放时间。');
  }

  if (cached.failed.length > 0) {
    notes.push('仍有未识别点位，建议先修正后再确认当天路线。');
  }

  return notes.slice(0, 4);
}

function ensureAmapPlugins(AMap: AMapApi, plugins: string[]): Promise<void> {
  if (!plugins.length || typeof AMap?.plugin !== 'function') {
    return Promise.resolve();
  }

  return new Promise<void>((resolve, reject) => {
    let settled = false;
    const timeoutId = window.setTimeout(() => {
      if (settled) {
        return;
      }

      settled = true;
      reject(new Error('高德路线插件加载超时，请稍后重试。'));
    }, ROUTE_TIMEOUT_MS);

    try {
      AMap.plugin(plugins, () => {
        if (settled) {
          return;
        }

        settled = true;
        window.clearTimeout(timeoutId);
        resolve();
      });
    } catch (error) {
      if (settled) {
        return;
      }

      settled = true;
      window.clearTimeout(timeoutId);
      reject(error instanceof Error ? error : new Error(String(error)));
    }
  });
}

function buildRetryStop(stop: RouteStop, manualQuery: string): RouteStop {
  const normalizedManualQuery = normalizeText(manualQuery);

  if (!normalizedManualQuery) {
    return stop;
  }

  return {
    ...stop,
    query: normalizedManualQuery,
    queries: dedupeQueries([
      normalizedManualQuery,
      ...buildStopQueries(normalizedManualQuery, stop.title),
      ...stop.queries,
    ]),
  };
}

function geocodeStop(
  geocoder: any,
  stop: RouteStop,
  destination?: string,
): Promise<ResolvedStop> {
  const addressQueries = dedupeQueries(
    (stop.queries.length > 0 ? stop.queries : [stop.query]).flatMap((query) =>
      buildAddressQueries(query, destination),
    ),
  );

  async function geocodeWithQuery(addressQuery: string): Promise<ResolvedStop> {
    return new Promise<ResolvedStop>((resolve, reject) => {
      let settled = false;
      const timeoutId = window.setTimeout(() => {
        if (settled) {
          return;
        }

        settled = true;
        reject(new Error(`定位超时：${addressQuery}`));
      }, GEOCODE_TIMEOUT_MS);

      geocoder.getLocation(addressQuery, (status: string, result: any) => {
        if (settled) {
          return;
        }

        window.clearTimeout(timeoutId);
        settled = true;

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

  return (async () => {
    let lastError: Error | null = null;

    for (const addressQuery of addressQueries) {
      try {
        return await geocodeWithQuery(addressQuery);
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
      }
    }

    throw lastError ?? new Error(`未找到地点：${stop.query}`);
  })();
}

async function geocodeStops(
  AMap: AMapApi,
  routeDay: RouteDay,
  destination?: string,
): Promise<{ resolved: ResolvedStop[]; failed: FailedStop[] }> {
  await ensureAmapPlugins(AMap, ['AMap.Geocoder']);

  const geocoder = new AMap.Geocoder({
    city: normalizeText(destination) || undefined,
  });

  const results = await Promise.allSettled(
    routeDay.stops.map(async (stop) => {
      const backendResolved = buildResolvedStopFromBackend(AMap, stop);
      if (backendResolved) {
        return backendResolved;
      }

      return geocodeStop(geocoder, stop, destination);
    }),
  );

  const resolved: ResolvedStop[] = [];
  const failed: FailedStop[] = [];

  results.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      resolved.push(result.value);
      return;
    }

    const reason =
      result.reason instanceof Error ? result.reason.message : '地点暂时无法识别，请换个更具体的写法。';
    failed.push({
      ...routeDay.stops[index],
      reason,
      lastTriedQuery: routeDay.stops[index].query,
      candidatePlaces: routeDay.stops[index].candidatePlaces,
    });
  });

  return {
    resolved: orderResolvedStops(routeDay, resolved),
    failed: orderFailedStops(routeDay, failed),
  };
}

function clearMapOverlays(map: any, overlays: any[]) {
  if (overlays.length > 0) {
    map.remove(overlays);
    overlays.splice(0, overlays.length);
  }
}

function buildMarkerToneClass(label: string): string {
  const markerTones = ['amber', 'emerald', 'rose', 'violet'];
  const normalized = label.trim().charAt(0).toUpperCase();
  const code = normalized.charCodeAt(0);

  if (Number.isNaN(code) || code < 65 || code > 90) {
    return markerTones[0];
  }

  return markerTones[(code - 65) % markerTones.length];
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function buildMarkerHtml(label: string, title: string): string {
  const toneClass = buildMarkerToneClass(label);
  return `
    <div class="route-marker">
      <div class="route-marker-pin route-marker-pin-${toneClass}">${escapeHtml(label)}</div>
      <div class="route-marker-label">${escapeHtml(title)}</div>
    </div>
  `;
}

function extractPositionCoords(position: any): { lng: number; lat: number } | null {
  if (!position) {
    return null;
  }

  if (typeof position.getLng === 'function' && typeof position.getLat === 'function') {
    return {
      lng: Number(position.getLng()),
      lat: Number(position.getLat()),
    };
  }

  if (typeof position.lng === 'number' && typeof position.lat === 'number') {
    return {
      lng: position.lng,
      lat: position.lat,
    };
  }

  if (Array.isArray(position) && position.length >= 2) {
    return {
      lng: Number(position[0]),
      lat: Number(position[1]),
    };
  }

  return null;
}

function createLngLat(AMap: AMapApi, lng: number, lat: number): any {
  if (typeof AMap?.LngLat === 'function') {
    return new AMap.LngLat(lng, lat);
  }

  return { lng, lat };
}

function areSameCoords(a: any, b: any): boolean {
  const aCoords = extractPositionCoords(a);
  const bCoords = extractPositionCoords(b);

  if (!aCoords || !bCoords) {
    return false;
  }

  return (
    Math.abs(aCoords.lng - bCoords.lng) <= PATH_POINT_EPSILON &&
    Math.abs(aCoords.lat - bCoords.lat) <= PATH_POINT_EPSILON
  );
}

function parsePolylineString(AMap: AMapApi, polyline: string): any[] {
  return polyline
    .split(';')
    .map((pair) => pair.trim())
    .filter(Boolean)
    .map((pair) => pair.split(','))
    .filter((parts) => parts.length >= 2)
    .map(([lng, lat]) => createLngLat(AMap, Number(lng), Number(lat)))
    .filter((point) => extractPositionCoords(point));
}

function normalizePathPoints(AMap: AMapApi, rawPath: any): any[] {
  if (!rawPath) {
    return [];
  }

  if (typeof rawPath === 'string') {
    return parsePolylineString(AMap, rawPath);
  }

  if (Array.isArray(rawPath)) {
    if (rawPath.length === 0) {
      return [];
    }

    if (extractPositionCoords(rawPath[0])) {
      return rawPath
        .map((point) => {
          const coords = extractPositionCoords(point);
          return coords ? createLngLat(AMap, coords.lng, coords.lat) : null;
        })
        .filter(Boolean);
    }

    return rawPath.flatMap((value) => normalizePathPoints(AMap, value));
  }

  if (rawPath.path) {
    return normalizePathPoints(AMap, rawPath.path);
  }

  if (rawPath.polyline) {
    return normalizePathPoints(AMap, rawPath.polyline);
  }

  return [];
}

function appendUniquePathPoints(target: any[], path: any[]) {
  path.forEach((point) => {
    const lastPoint = target[target.length - 1];
    if (!lastPoint || !areSameCoords(lastPoint, point)) {
      target.push(point);
    }
  });
}

function buildDisplayPositions(AMap: AMapApi, resolved: ResolvedStop[]): any[] {
  const groups: Array<{ center: { lng: number; lat: number }; indexes: number[] }> = [];
  const displayPositions: any[] = resolved.map((stop) => stop.position);

  resolved.forEach((stop, index) => {
    const coords = extractPositionCoords(stop.position);
    if (!coords) {
      return;
    }

    const existingGroup = groups.find(
      (group) =>
        Math.abs(group.center.lng - coords.lng) <= OVERLAP_GROUP_EPSILON &&
        Math.abs(group.center.lat - coords.lat) <= OVERLAP_GROUP_EPSILON,
    );

    if (existingGroup) {
      existingGroup.indexes.push(index);
      return;
    }

    groups.push({
      center: coords,
      indexes: [index],
    });
  });

  groups.forEach((group) => {
    if (group.indexes.length <= 1) {
      return;
    }

    const radiusLng =
      OVERLAP_SPREAD_RADIUS / Math.max(Math.cos((group.center.lat * Math.PI) / 180), 0.2);
    const radiusLat = OVERLAP_SPREAD_RADIUS;

    group.indexes.forEach((resolvedIndex, order) => {
      const angle = -Math.PI / 2 + (order * Math.PI * 2) / group.indexes.length;
      const lng = group.center.lng + radiusLng * Math.cos(angle);
      const lat = group.center.lat + radiusLat * Math.sin(angle);
      displayPositions[resolvedIndex] = createLngLat(AMap, lng, lat);
    });
  });

  return displayPositions;
}

function buildFallbackPath(resolved: ResolvedStop[]): RoutePathResult {
  const path: any[] = [];
  const segments: RouteSegment[] = [];

  for (let index = 0; index < resolved.length - 1; index += 1) {
    const from = resolved[index];
    const to = resolved[index + 1];
    const estimatedDistance = estimateFallbackDistanceMeters(from.position, to.position);
    appendUniquePathPoints(path, [from.position, to.position]);
    segments.push({
      key: `${from.key}->${to.key}`,
      fromLabel: from.label,
      toLabel: to.label,
      fromTitle: from.title,
      toTitle: to.title,
      distanceText: formatDistanceText(estimatedDistance),
      durationText: '路线补位中',
      fallback: true,
    });
  }

  return {
    path,
    segments,
    routedSegments: 0,
    fallbackSegments: Math.max(resolved.length - 1, 0),
  };
}

function extractWalkingRoute(result: any): any {
  if (Array.isArray(result?.routes) && result.routes.length > 0) {
    return result.routes[0];
  }

  if (Array.isArray(result?.route?.paths) && result.route.paths.length > 0) {
    return result.route.paths[0];
  }

  return result?.route ?? result;
}

function extractWalkingPath(AMap: AMapApi, route: any): any[] {
  if (!route) {
    return [];
  }

  const path: any[] = [];
  const steps = Array.isArray(route.steps) ? route.steps : [];

  steps.forEach((step) => {
    const stepPath = normalizePathPoints(AMap, step?.path ?? step?.polyline);
    appendUniquePathPoints(path, stepPath);
  });

  if (path.length === 0) {
    appendUniquePathPoints(path, normalizePathPoints(AMap, route.path ?? route.polyline));
  }

  return path;
}

function planWalkingSegment(
  AMap: AMapApi,
  from: ResolvedStop,
  to: ResolvedStop,
): Promise<{ path: any[]; segment: RouteSegment }> {
  return new Promise<{ path: any[]; segment: RouteSegment }>((resolve, reject) => {
    const walking = new AMap.Walking({
      hideMarkers: true,
      autoFitView: false,
    });

    let settled = false;
    const timeoutId = window.setTimeout(() => {
      if (settled) {
        return;
      }

      settled = true;
      walking.clear?.();
      walking.destroy?.();
      reject(new Error(`步行路线规划超时：${from.title} -> ${to.title}`));
    }, ROUTE_TIMEOUT_MS);

    try {
      walking.search(from.position, to.position, (status: string, result: any) => {
        if (settled) {
          return;
        }

        settled = true;
        window.clearTimeout(timeoutId);

        const route = status === 'complete' ? extractWalkingRoute(result) : null;
        const path = extractWalkingPath(AMap, route);
        const durationSeconds = normalizeNumericValue(route?.time ?? route?.duration);
        const distanceMeters = normalizeNumericValue(route?.distance);
        walking.clear?.();
        walking.destroy?.();

        if (path.length > 0) {
          resolve({
            path,
            segment: {
              key: `${from.key}->${to.key}`,
              fromLabel: from.label,
              toLabel: to.label,
              fromTitle: from.title,
              toTitle: to.title,
              distanceText: formatDistanceText(distanceMeters),
              durationText: formatDurationText(durationSeconds),
              fallback: false,
            },
          });
          return;
        }

        reject(new Error(`步行路线规划失败：${from.title} -> ${to.title}`));
      });
    } catch (error) {
      if (settled) {
        return;
      }

      settled = true;
      window.clearTimeout(timeoutId);
      walking.clear?.();
      walking.destroy?.();
      reject(error instanceof Error ? error : new Error(String(error)));
    }
  });
}

async function buildRoutePath(
  AMap: AMapApi,
  resolved: ResolvedStop[],
): Promise<RoutePathResult> {
  await ensureAmapPlugins(AMap, ['AMap.Walking']);

  if (resolved.length < 2) {
    return {
      path: [],
      segments: [],
      routedSegments: 0,
      fallbackSegments: 0,
    };
  }

  const path: any[] = [];
  const segments: RouteSegment[] = [];
  let routedSegments = 0;
  let fallbackSegments = 0;

  for (let index = 0; index < resolved.length - 1; index += 1) {
    const from = resolved[index];
    const to = resolved[index + 1];

    try {
      const routeData = await planWalkingSegment(AMap, from, to);
      appendUniquePathPoints(path, routeData.path);
      segments.push({
        key: `${from.key}->${to.key}`,
        fromLabel: from.label,
        toLabel: to.label,
        fromTitle: from.title,
        toTitle: to.title,
        distanceText: routeData.segment.distanceText,
        durationText: routeData.segment.durationText,
        fallback: false,
      });
      routedSegments += 1;
    } catch {
      const estimatedDistance = estimateFallbackDistanceMeters(from.position, to.position);
      appendUniquePathPoints(path, [from.position, to.position]);
      segments.push({
        key: `${from.key}->${to.key}`,
        fromLabel: from.label,
        toLabel: to.label,
        fromTitle: from.title,
        toTitle: to.title,
        distanceText: formatDistanceText(estimatedDistance),
        durationText: '路线补位中',
        fallback: true,
      });
      fallbackSegments += 1;
    }
  }

  return {
    path,
    segments,
    routedSegments,
    fallbackSegments,
  };
}

async function buildCachedRouteDay(
  AMap: AMapApi,
  routeDay: RouteDay,
  resolved: ResolvedStop[],
  failed: FailedStop[],
): Promise<CachedRouteDay> {
  const orderedResolved = orderResolvedStops(routeDay, resolved);
  const orderedFailed = orderFailedStops(routeDay, failed);

  if (orderedResolved.length === 0) {
    return {
      ...createEmptyRouteDay('error'),
      failed: orderedFailed,
      errorMessage: '这一天的地点暂时无法识别，请把景点或商圈写得更具体一些。',
    };
  }

  const routePathResult = await buildRoutePath(AMap, orderedResolved);

  return {
    status: 'ready',
    resolved: orderedResolved,
    failed: orderedFailed,
    routePath: routePathResult.path,
    routeSegments: routePathResult.segments,
    routedSegments: routePathResult.routedSegments,
    fallbackSegments: routePathResult.fallbackSegments,
  };
}

function buildRouteOverlays(AMap: AMapApi, cached: CachedRouteDay): any[] {
  const displayPositions = buildDisplayPositions(AMap, cached.resolved);

  const overlays: any[] = cached.resolved.map((stop, index) => {
    const markerPosition = displayPositions[index] ?? stop.position;
    const marker = new AMap.Marker({
      position: markerPosition,
      anchor: 'bottom-center',
      title: stop.formattedAddress,
      content: buildMarkerHtml(stop.label, stop.title),
    });

    return marker;
  });

  const polylinePath =
    cached.routePath.length > 1 ? cached.routePath : cached.resolved.map((stop) => stop.position);

  if (polylinePath.length > 1) {
    overlays.push(
      new AMap.Polyline({
        path: polylinePath,
        strokeColor: '#0ea5e9',
        strokeWeight: 6,
        strokeOpacity: 0.92,
        lineCap: 'round',
        lineJoin: 'round',
        showDir: true,
      }),
    );
  }

  return overlays;
}

function buildRouteReadyMessage(routeDay: RouteDay, cached: CachedRouteDay): string {
  const locationSummary =
    cached.failed.length > 0
      ? `已定位 ${cached.resolved.length}/${routeDay.stops.length} 个地点`
      : `已定位 ${cached.resolved.length} 个地点`;

  if (cached.resolved.length < 2) {
    return `${locationSummary}，暂时先展示已识别点位。`;
  }

  if (cached.fallbackSegments > 0) {
    return `${locationSummary}，部分路段暂用直线补位。`;
  }

  return `${locationSummary}，已按活动顺序生成 ${cached.routedSegments} 段路线预览。`;
}

function buildPrefetchLoadingMessage(
  routeDays: RouteDay[],
  routeCache: Record<string, CachedRouteDay>,
): string {
  const finishedCount = routeDays.filter((day) => {
    const status = routeCache[buildRouteCacheEntryKey(day.key)]?.status;
    return status === 'ready' || status === 'error';
  }).length;

  return `正在预生成全部天数地图（${finishedCount}/${routeDays.length}）…`;
}

export function ItineraryRouteMap({
  itinerary,
}: {
  itinerary: StructuredItinerary;
}) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const overlayRef = useRef<any[]>([]);
  const routeCacheRef = useRef<Record<string, CachedRouteDay>>({});

  const routeDays = useMemo(() => buildRouteDays(itinerary), [itinerary]);
  const routeCacheKey = useMemo(
    () =>
      `${normalizeText(itinerary.destination)}::${routeDays
        .map(
          (day) =>
            `${day.key}:${day.stops
              .map((stop) =>
                [
                  stop.query,
                  stop.poiId ?? '',
                  stop.backendPosition?.lng ?? '',
                  stop.backendPosition?.lat ?? '',
                ].join('@'),
              )
              .join('|')}`,
        )
        .join('||')}`,
    [itinerary.destination, routeDays],
  );

  const [activeDayIndex, setActiveDayIndex] = useState(0);
  const [isMapExpanded, setIsMapExpanded] = useState(false);
  const [routeCache, setRouteCache] = useState<Record<string, CachedRouteDay>>({});
  const [manualQueries, setManualQueries] = useState<Record<string, string>>({});
  const [retryingStops, setRetryingStops] = useState<Record<string, boolean>>({});
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
  const activeDayCache = activeDay ? routeCache[buildRouteCacheEntryKey(activeDay.key)] : undefined;

  useEffect(() => {
    routeCacheRef.current = routeCache;
  }, [routeCache]);

  useEffect(() => {
    if (activeDayIndex >= routeDays.length) {
      setActiveDayIndex(0);
    }
  }, [activeDayIndex, routeDays.length]);

  useEffect(() => {
    setRouteCache({});
    setManualQueries({});
    setRetryingStops({});
  }, [routeCacheKey]);

  useEffect(() => {
    if (!isMapExpanded) {
      return;
    }

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsMapExpanded(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isMapExpanded]);

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
    if (mapStatus !== 'ready' || routeDays.length === 0) {
      return;
    }

    let cancelled = false;

    async function prefetchAllRoutes() {
      try {
        const AMap = await loadAmap();
        if (cancelled) {
          return;
        }

        setRouteCache((prev) => {
          const next = { ...prev };
          routeDays.forEach((day) => {
            const cacheKey = buildRouteCacheEntryKey(day.key);
            if (!next[cacheKey] || next[cacheKey].status === 'idle') {
              next[cacheKey] = createEmptyRouteDay('loading');
            }
          });
          return next;
        });

        await Promise.all(
          routeDays.map(async (day) => {
            const cacheKey = buildRouteCacheEntryKey(day.key);
            if (routeCacheRef.current[cacheKey]?.status === 'ready') {
              return;
            }

            try {
              const { resolved, failed } = await geocodeStops(AMap, day, itinerary.destination);
              if (cancelled) {
                return;
              }

              const cached = await buildCachedRouteDay(
                AMap,
                day,
                resolved,
                failed,
              );
              if (cancelled) {
                return;
              }

              setRouteCache((prev) => ({
                ...prev,
                [cacheKey]: cached,
              }));
            } catch (error) {
              if (cancelled) {
                return;
              }

              setRouteCache((prev) => ({
                ...prev,
                [cacheKey]: {
                  ...createEmptyRouteDay('error'),
                  failed: day.stops.map((stop) => ({
                    ...stop,
                    reason:
                      error instanceof Error
                        ? error.message
                        : '地图预生成失败，请稍后再试。',
                    lastTriedQuery: stop.query,
                  })),
                  errorMessage:
                    error instanceof Error ? error.message : '地图预生成失败，请稍后再试。',
                },
              }));
            }
          }),
        );
      } catch {
        // 地图初始化异常已由上层处理。
      }
    }

    void prefetchAllRoutes();

    return () => {
      cancelled = true;
    };
  }, [itinerary.destination, mapStatus, routeCacheKey, routeDays]);

  useEffect(() => {
    if (mapStatus !== 'ready' || !mapRef.current) {
      return;
    }

    const map = mapRef.current;
    let cancelled = false;

    clearMapOverlays(map, overlayRef.current);

    if (!activeDay) {
      setRouteStatus('empty');
      setStatusMessage('当前行程里还没有足够具体的地点，暂时无法生成 A-B-C 路线。');
      return;
    }

    if (!activeDayCache || activeDayCache.status === 'idle' || activeDayCache.status === 'loading') {
      setRouteStatus('loading');
      setStatusMessage(buildPrefetchLoadingMessage(routeDays, routeCache));
      return;
    }

    if (activeDayCache.status === 'error' || activeDayCache.resolved.length === 0) {
      setRouteStatus('error');
      setStatusMessage(
        activeDayCache.errorMessage ?? '这一天的地点暂时无法识别，请把景点或商圈写得更具体一些。',
      );
      return;
    }

    loadAmap()
      .then((AMap) => {
        if (cancelled) {
          return;
        }

        const overlays = buildRouteOverlays(AMap, activeDayCache);
        map.add(overlays);
        overlayRef.current.push(...overlays);
        map.setFitView(overlays, false, [56, 56, 56, 56]);

        setRouteStatus('ready');
        setStatusMessage(buildRouteReadyMessage(activeDay, activeDayCache));
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }

        setRouteStatus('error');
        setStatusMessage(error instanceof Error ? error.message : '路线绘制失败，请稍后再试。');
      });

    return () => {
      cancelled = true;
      clearMapOverlays(map, overlayRef.current);
    };
  }, [activeDay, activeDayCache, mapStatus, routeCache, routeDays]);

  const activeResolvedByKey = useMemo(
    () => new Map((activeDayCache?.resolved ?? []).map((stop) => [stop.key, stop])),
    [activeDayCache?.resolved],
  );
  const activeFailedByKey = useMemo(
    () => new Map((activeDayCache?.failed ?? []).map((stop) => [stop.key, stop])),
    [activeDayCache?.failed],
  );
  const activeRouteSegments = activeDayCache?.routeSegments ?? [];

  async function handleUseCandidate(stop: RouteStop, candidate: RouteCandidate) {
    if (!activeDay) {
      return;
    }

    const activeCacheKey = buildRouteCacheEntryKey(activeDay.key);

    setRetryingStops((prev) => ({
      ...prev,
      [stop.key]: true,
    }));

    try {
      const AMap = await loadAmap();
      const currentCache = routeCacheRef.current[activeCacheKey] ?? createEmptyRouteDay('idle');
      const resolvedStop = buildResolvedStopFromCandidate(AMap, stop, candidate);
      const nextResolved = orderResolvedStops(activeDay, [
        ...currentCache.resolved.filter((item) => item.key !== stop.key),
        resolvedStop,
      ]);
      const nextFailed = orderFailedStops(
        activeDay,
        currentCache.failed.filter((item) => item.key !== stop.key),
      );
      const nextCache = await buildCachedRouteDay(
        AMap,
        activeDay,
        nextResolved,
        nextFailed,
      );

      setRouteCache((prev) => ({
        ...prev,
        [activeCacheKey]: nextCache,
      }));
      setManualQueries((prev) => {
        const next = { ...prev };
        delete next[stop.key];
        return next;
      });
    } finally {
      setRetryingStops((prev) => {
        const next = { ...prev };
        delete next[stop.key];
        return next;
      });
    }
  }

  async function handleRetryStop(stop: RouteStop) {
    if (!activeDay) {
      return;
    }

    const activeCacheKey = buildRouteCacheEntryKey(activeDay.key);
    const retryQuery = normalizeText(manualQueries[stop.key]) || stop.query;
    const retryStop = buildRetryStop(stop, retryQuery);

    setRetryingStops((prev) => ({
      ...prev,
      [stop.key]: true,
    }));

    try {
      const AMap = await loadAmap();
      await ensureAmapPlugins(AMap, ['AMap.Geocoder', 'AMap.Walking']);

      const geocoder = new AMap.Geocoder({
        city: normalizeText(itinerary.destination) || undefined,
      });

      const resolvedStop = await geocodeStop(geocoder, retryStop, itinerary.destination);
      const currentCache = routeCacheRef.current[activeCacheKey] ?? createEmptyRouteDay('idle');
      const nextResolved = orderResolvedStops(activeDay, [
        ...currentCache.resolved.filter((item) => item.key !== stop.key),
        resolvedStop,
      ]);
      const nextFailed = orderFailedStops(
        activeDay,
        currentCache.failed.filter((item) => item.key !== stop.key),
      );

      const nextCache = await buildCachedRouteDay(
        AMap,
        activeDay,
        nextResolved,
        nextFailed,
      );

      setRouteCache((prev) => ({
        ...prev,
        [activeCacheKey]: nextCache,
      }));
      setManualQueries((prev) => {
        const next = { ...prev };
        delete next[stop.key];
        return next;
      });
    } catch (error) {
      const currentCache = routeCacheRef.current[activeCacheKey] ?? createEmptyRouteDay('idle');
      const failedStop: FailedStop = {
        ...retryStop,
        reason:
          error instanceof Error ? error.message : '重试失败，请换个更具体的地点名称再试。',
        lastTriedQuery: retryQuery,
      };

      setRouteCache((prev) => ({
        ...prev,
        [activeCacheKey]: {
          ...currentCache,
          status: currentCache.resolved.length > 0 ? 'ready' : 'error',
          failed: orderFailedStops(activeDay, [
            ...currentCache.failed.filter((item) => item.key !== stop.key),
            failedStop,
          ]),
          errorMessage:
            currentCache.resolved.length > 0
              ? currentCache.errorMessage
              : '这一天的地点暂时无法识别，请把景点或商圈写得更具体一些。',
        },
      }));
    } finally {
      setRetryingStops((prev) => {
        const next = { ...prev };
        delete next[stop.key];
        return next;
      });
    }
  }

  if (routeDays.length === 0) {
    return (
      <div className="itinerary-section">
        <h3 className="section-title">
          <MapPinned size={18} />
          地图路线
        </h3>
        <div className="route-empty-state">
          当前行程里还没有可用于绘制地图的具体地点。
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
          ? '未检测到高德地图 JS Key，请先在 .env 中配置。'
          : routeStatus === 'loading'
            ? '正在预生成地图路线…'
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

      <div className={`route-map-shell ${isMapExpanded ? 'is-expanded' : ''}`}>
        <button
          type="button"
          className="route-map-expand-btn"
          onClick={() => setIsMapExpanded((prev) => !prev)}
          aria-label={isMapExpanded ? '收起地图' : '放大地图'}
        >
          {isMapExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          <span>{isMapExpanded ? '收起地图' : '放大查看'}</span>
        </button>
        <div
          ref={mapContainerRef}
          className={`route-map-canvas ${isMapExpanded ? 'is-expanded' : ''}`}
        />
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

      {activeRouteSegments.length > 0 && (
        <div className="route-segment-list">
          {activeRouteSegments.map((segment) => (
            <div
              key={segment.key}
              className={`route-segment-item ${segment.fallback ? 'is-fallback' : ''}`}
            >
              <div className="route-segment-leg">
                {segment.fromLabel} → {segment.toLabel}
              </div>
              <div className="route-segment-titles">
                {segment.fromTitle} → {segment.toTitle}
              </div>
              <div className="route-segment-meta">
                <span>{segment.distanceText}</span>
                <span>{segment.durationText}</span>
                {segment.fallback && <span>待补位</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {activeDay && (
        <div className="route-stop-list">
          {activeDay.stops.map((stop) => {
            const resolvedStop = activeResolvedByKey.get(stop.key);
            const failedStop = activeFailedByKey.get(stop.key);
            const isRetrying = Boolean(retryingStops[stop.key]);
            const badgeToneClass = `route-stop-badge-${buildMarkerToneClass(stop.label)}`;

            if (failedStop) {
              return (
                <div key={stop.key} className="route-stop-item is-error">
                  <div className="route-stop-badge route-stop-badge-error">{stop.label}</div>
                  <div className="route-stop-content">
                    <div className="route-stop-title">{stop.title}</div>
                    <div className="route-stop-meta">
                      {stop.timeOfDay} · 未识别
                    </div>
                    <div className="route-stop-reason">{failedStop.reason}</div>
                    {failedStop.candidatePlaces.length > 0 && (
                      <div className="route-stop-candidates">
                        {failedStop.candidatePlaces.map((candidate) => (
                          <button
                            key={`${stop.key}-${candidate.poiId ?? candidate.name}`}
                            type="button"
                            className="route-candidate-btn"
                            onClick={() => void handleUseCandidate(stop, candidate)}
                            disabled={isRetrying}
                          >
                            <strong>{candidate.name}</strong>
                            <span>{candidate.formattedAddress || '高德候选地点'}</span>
                          </button>
                        ))}
                      </div>
                    )}
                    <div className="route-stop-editor">
                      <input
                        className="route-stop-input"
                        type="text"
                        value={manualQueries[stop.key] ?? ''}
                        onChange={(event) =>
                          setManualQueries((prev) => ({
                            ...prev,
                            [stop.key]: event.target.value,
                          }))
                        }
                        placeholder={`试试更具体的地点，例如：${failedStop.lastTriedQuery}`}
                      />
                      <button
                        type="button"
                        className="route-stop-retry-btn"
                        onClick={() => void handleRetryStop(stop)}
                        disabled={isRetrying}
                      >
                        <RefreshCw size={14} className={isRetrying ? 'is-spinning' : ''} />
                        <span>{isRetrying ? '重试中…' : '重试定位'}</span>
                      </button>
                    </div>
                    <div className="route-stop-help">
                      可以填更具体的景点、商场、码头、酒店或完整地址。
                    </div>
                  </div>
                </div>
              );
            }

            if (resolvedStop) {
              return (
                <div key={stop.key} className="route-stop-item">
                  <div className={`route-stop-badge ${badgeToneClass}`}>{stop.label}</div>
                  <div className="route-stop-content">
                    <div className="route-stop-title">{stop.title}</div>
                    <div className="route-stop-meta">
                      {stop.timeOfDay} · {resolvedStop.formattedAddress}
                    </div>
                  </div>
                </div>
              );
            }

            return (
              <div key={stop.key} className="route-stop-item is-pending">
                <div className="route-stop-badge route-stop-badge-pending">{stop.label}</div>
                <div className="route-stop-content">
                  <div className="route-stop-title">{stop.title}</div>
                  <div className="route-stop-meta">
                    {stop.timeOfDay} · 正在定位该点位…
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <p className="route-disclaimer">
        当前版本会优先使用高德步行路线；如果个别路段暂时无法规划，会自动回退成直线补位。未识别的点位也可以在下方手动修正后重新定位。
      </p>
    </div>
  );
}
