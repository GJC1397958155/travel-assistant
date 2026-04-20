from __future__ import annotations

from typing import Any

from langchain.tools import tool

from tools.amap_base import amap_request


ROUTE_MODE_TO_PATH = {
    "walking": "/v3/direction/walking",
    "driving": "/v3/direction/driving",
    "transit": "/v3/direction/transit/integrated",
}


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
    )
    return _extract_location(data, address)


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


@tool
def plan_route(
    origin: str,
    destination: str,
    city: str = "",
    mode: str = "walking",
) -> str:
    """使用高德地图规划从起点到终点的真实路线。mode 支持 walking、driving、transit。"""
    route_mode = mode.strip().lower() or "walking"
    if route_mode not in ROUTE_MODE_TO_PATH:
        supported = ", ".join(sorted(ROUTE_MODE_TO_PATH))
        return f"暂不支持 {mode} 路线规划。当前支持：{supported}。"
    if route_mode == "transit" and not city.strip():
        return "公交/地铁路线规划需要提供 city，例如上海、北京。"

    origin_location = geocode_location(origin, city)
    destination_location = geocode_location(destination, city)

    params = {
        "origin": origin_location,
        "destination": destination_location,
    }
    if route_mode == "transit" and city:
        params["city"] = city

    data = amap_request(ROUTE_MODE_TO_PATH[route_mode], params)
    route = data.get("route", {})

    if route_mode == "transit":
        transits = route.get("transits", [])
        if not transits:
            return "未查询到可用的公交/地铁路线。"
        best = transits[0]
        distance_text = _format_distance(best.get("distance"))
        duration_text = _format_minutes(best.get("duration"))
        return f"{origin} -> {destination}：公交/地铁约 {distance_text}，预计 {duration_text}。"

    paths = route.get("paths", [])
    if not paths:
        return "未查询到可用路线。"

    best = paths[0]
    distance_text = _format_distance(best.get("distance"))
    duration_text = _format_minutes(best.get("duration"))

    if route_mode == "walking":
        return f"{origin} -> {destination}：步行约 {distance_text}，预计 {duration_text}。"

    taxi_cost = route.get("taxi_cost")
    cost_text = f"，打车参考约 {taxi_cost} 元" if taxi_cost else ""
    return f"{origin} -> {destination}：驾车约 {distance_text}，预计 {duration_text}{cost_text}。"
