from __future__ import annotations

from typing import Any

import httpx
from langchain.tools import tool

from tools.amap_base import amap_request


ROUTE_MODE_TO_PATH = {
    "walking": "/v3/direction/walking",
    "driving": "/v3/direction/driving",
    "transit": "/v3/direction/transit/integrated",
}

ROUTE_MODE_LABELS = {
    "walking": "步行",
    "driving": "驾车",
    "transit": "公交/地铁",
}

GEOCODE_TIMEOUT_SECONDS = 3.5
ROUTE_TIMEOUT_SECONDS = 5.0


def _extract_location(geocode_data: dict[str, Any], address: str) -> str:
    geocodes = geocode_data.get("geocodes", [])
    if not geocodes:
        raise RuntimeError(f"未找到地址“{address}”对应的坐标。")
    return geocodes[0]["location"]


def geocode_location(address: str, city: str = "") -> str:
    data = amap_request(
        "/v3/geocode/geo",
        {
            "address": address,
            "city": city,
        },
        timeout_seconds=GEOCODE_TIMEOUT_SECONDS,
    )
    return _extract_location(data, address)


def parse_location_text(location: str) -> tuple[float | None, float | None]:
    try:
        lng_text, lat_text = location.split(",", 1)
        return float(lng_text), float(lat_text)
    except (AttributeError, TypeError, ValueError):
        return None, None


def _safe_int(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _format_minutes(seconds_value: Any) -> str:
    seconds = _safe_int(seconds_value)
    if seconds is None:
        return ""
    minutes = max(1, round(seconds / 60))
    return f"{minutes} 分钟"


def _format_distance(distance_value: Any) -> str:
    distance = _safe_int(distance_value)
    if distance is None:
        return ""
    if distance >= 1000:
        return f"{distance / 1000:.1f} 公里"
    return f"{distance} 米"


def _collect_step_polyline(steps: list[dict[str, Any]]) -> str:
    parts = [step.get("polyline", "") for step in steps if step.get("polyline")]
    return ";".join(part for part in parts if part)


def _collect_transit_polyline(segments: list[dict[str, Any]]) -> str:
    polylines: list[str] = []

    for segment in segments:
        walking_steps = segment.get("walking", {}).get("steps", [])
        for step in walking_steps:
            polyline = step.get("polyline", "")
            if polyline:
                polylines.append(polyline)

        buslines = segment.get("bus", {}).get("buslines", [])
        for line in buslines:
            polyline = line.get("polyline", "")
            if polyline:
                polylines.append(polyline)

    return ";".join(polylines)


def _resolve_best_path(route_mode: str, route: dict[str, Any]) -> dict[str, Any] | None:
    if route_mode == "transit":
        transits = route.get("transits", [])
        return transits[0] if transits else None

    paths = route.get("paths", [])
    return paths[0] if paths else None


def _build_route_summary(route_mode: str, route: dict[str, Any]) -> dict[str, Any]:
    best = _resolve_best_path(route_mode, route)
    if not best:
        raise RuntimeError("未查询到可用路线。")

    distance_meters = _safe_int(best.get("distance"))
    duration_seconds = _safe_int(best.get("duration"))
    distance_text = _format_distance(distance_meters)
    duration_text = _format_minutes(duration_seconds)

    if route_mode == "walking":
        summary = f"步行约 {distance_text}，预计 {duration_text}。"
        polyline = _collect_step_polyline(best.get("steps", []))
    elif route_mode == "driving":
        taxi_cost = route.get("taxi_cost")
        cost_text = f"，打车参考约 {taxi_cost} 元" if taxi_cost else ""
        summary = f"驾车约 {distance_text}，预计 {duration_text}{cost_text}。"
        polyline = _collect_step_polyline(best.get("steps", []))
    else:
        segments = best.get("segments", [])
        bus_names: list[str] = []
        for segment in segments:
            buslines = segment.get("bus", {}).get("buslines", [])
            for line in buslines:
                name = line.get("name", "")
                if name:
                    bus_names.append(name)

        walking_distance_text = _format_distance(best.get("walking_distance", 0))
        transfer_text = ""
        if bus_names:
            transfer_text = "，换乘线路：" + " -> ".join(bus_names[:4])
        summary = (
            f"公交/地铁约 {distance_text}，预计 {duration_text}，"
            f"步行 {walking_distance_text}{transfer_text}。"
        )
        polyline = _collect_transit_polyline(segments)

    return {
        "distance_meters": distance_meters,
        "duration_seconds": duration_seconds,
        "distance_text": distance_text,
        "duration_text": duration_text,
        "summary": summary,
        "polyline": polyline,
    }


def _fetch_route_data(
    *,
    route_mode: str,
    origin_location: str,
    destination_location: str,
    city: str,
) -> dict[str, Any]:
    params = {
        "origin": origin_location,
        "destination": destination_location,
    }
    if route_mode == "transit" and city:
        params["city"] = city
    return amap_request(
        ROUTE_MODE_TO_PATH[route_mode],
        params,
        timeout_seconds=ROUTE_TIMEOUT_SECONDS,
    )


def plan_route_structured(
    *,
    origin: str,
    destination: str,
    city: str = "",
    mode: str = "walking",
    origin_location: str | None = None,
    destination_location: str | None = None,
) -> dict[str, Any]:
    route_mode = mode.strip().lower() or "walking"
    if route_mode not in ROUTE_MODE_TO_PATH:
        supported = ", ".join(sorted(ROUTE_MODE_TO_PATH))
        return {
            "ok": False,
            "error": f"暂不支持 {mode} 路线规划。当前支持：{supported}。",
        }
    if route_mode == "transit" and not city.strip():
        return {
            "ok": False,
            "error": "公交/地铁路线规划需要提供 city，例如上海、北京。",
        }

    try:
        resolved_origin = origin_location or geocode_location(origin, city)
        resolved_destination = destination_location or geocode_location(destination, city)
        data = _fetch_route_data(
            route_mode=route_mode,
            origin_location=resolved_origin,
            destination_location=resolved_destination,
            city=city,
        )
        route = data.get("route", {})
        summary = _build_route_summary(route_mode, route)
    except httpx.HTTPError as exc:
        return {"ok": False, "error": f"高德路线规划失败：{exc}"}
    except Exception as exc:
        return {"ok": False, "error": f"高德路线规划失败：{exc}"}

    origin_lng, origin_lat = parse_location_text(resolved_origin)
    destination_lng, destination_lat = parse_location_text(resolved_destination)

    return {
        "ok": True,
        "mode": route_mode,
        "mode_label": ROUTE_MODE_LABELS.get(route_mode, route_mode),
        "origin": origin,
        "destination": destination,
        "origin_location": resolved_origin,
        "destination_location": resolved_destination,
        "origin_lng": origin_lng,
        "origin_lat": origin_lat,
        "destination_lng": destination_lng,
        "destination_lat": destination_lat,
        **summary,
    }


@tool
def plan_route(
    origin: str,
    destination: str,
    city: str = "",
    mode: str = "walking",
) -> str:
    """使用高德地图规划从起点到终点的真实路线。mode 支持 walking、driving、transit。"""
    result = plan_route_structured(
        origin=origin,
        destination=destination,
        city=city,
        mode=mode,
    )
    if not result.get("ok"):
        return str(result.get("error", "高德路线规划失败。"))

    city_text = f"（{city}）" if city else ""
    return f"{origin} -> {destination}{city_text}：{result['summary']}"
