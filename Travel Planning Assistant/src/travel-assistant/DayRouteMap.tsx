import { useEffect, useRef } from 'react';
import { DayRouteMapResponse, RouteLeg, RoutePoint } from './types';
import { loadAmap } from './amapLoader';

interface DayRouteMapProps {
  data: DayRouteMapResponse;
}

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function buildMarkerContent(point: RoutePoint) {
  const label = escapeHtml(point.label || point.location || point.title || `第 ${point.order} 站`);
  return `
    <div class="day-route-marker">
      <div class="day-route-marker-order">${point.order}</div>
      <div class="day-route-marker-label">${label}</div>
    </div>
  `;
}

function getRouteColor(mode?: string) {
  switch (mode) {
    case 'driving':
      return '#f59e0b';
    case 'transit':
      return '#10b981';
    default:
      return '#2563eb';
  }
}

function resolveLegPath(leg: RouteLeg, routePointsByOrder: Map<number, RoutePoint>) {
  if (leg.path && leg.path.length >= 2) {
    return leg.path;
  }

  const originPoint = routePointsByOrder.get(leg.from_order);
  const destinationPoint = routePointsByOrder.get(leg.to_order);
  if (
    originPoint?.lng === undefined ||
    originPoint?.lng === null ||
    originPoint?.lat === undefined ||
    originPoint?.lat === null ||
    destinationPoint?.lng === undefined ||
    destinationPoint?.lng === null ||
    destinationPoint?.lat === undefined ||
    destinationPoint?.lat === null
  ) {
    return [];
  }

  return [
    [originPoint.lng, originPoint.lat],
    [destinationPoint.lng, destinationPoint.lat],
  ];
}

export function DayRouteMap({ data }: DayRouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let disposed = false;
    let mapInstance: any = null;

    async function initializeMap() {
      if (!containerRef.current) {
        return;
      }

      const AMap = await loadAmap();
      if (disposed || !containerRef.current) {
        return;
      }

      mapInstance = new AMap.Map(containerRef.current, {
        viewMode: '2D',
        zoom: 12,
        mapStyle: 'amap://styles/whitesmoke',
        resizeEnable: true,
      });

      const overlays: any[] = [];
      const routePointsByOrder = new Map<number, RoutePoint>();

      for (const point of data.route_points) {
        if (point.lng === undefined || point.lng === null || point.lat === undefined || point.lat === null) {
          continue;
        }

        routePointsByOrder.set(point.order, point);
        const marker = new AMap.Marker({
          position: [point.lng, point.lat],
          anchor: 'bottom-center',
          title: point.label || point.location || point.title || `第 ${point.order} 站`,
          content: buildMarkerContent(point),
          offset: new AMap.Pixel(-18, -48),
        });
        marker.setMap(mapInstance);
        overlays.push(marker);
      }

      for (const leg of data.route_legs) {
        const path = resolveLegPath(leg, routePointsByOrder);
        if (path.length < 2) {
          continue;
        }

        const polyline = new AMap.Polyline({
          path,
          strokeColor: getRouteColor(leg.mode),
          strokeWeight: 6,
          strokeOpacity: 0.9,
          strokeStyle: leg.error ? 'dashed' : 'solid',
          showDir: !leg.error,
          lineJoin: 'round',
          lineCap: 'round',
        });
        polyline.setMap(mapInstance);
        overlays.push(polyline);
      }

      if (AMap.Scale) {
        mapInstance.addControl(new AMap.Scale());
      }
      if (AMap.ToolBar) {
        mapInstance.addControl(new AMap.ToolBar({ position: 'RB' }));
      }

      if (overlays.length > 0) {
        mapInstance.setFitView(overlays, false, [40, 40, 40, 40]);
      }
    }

    initializeMap().catch((error) => {
      if (!disposed) {
        console.error(error);
      }
    });

    return () => {
      disposed = true;
      if (mapInstance) {
        mapInstance.destroy();
      }
    };
  }, [data]);

  return <div ref={containerRef} className="day-route-map-canvas" />;
}
