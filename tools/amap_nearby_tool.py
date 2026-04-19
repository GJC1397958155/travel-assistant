import httpx
from langchain.tools import tool

from tools.amap_base import amap_request


def _geocode(address: str, city: str = "") -> tuple[str, str]:
    data = amap_request(
        "/v3/geocode/geo",
        {
            "address": address,
            "city": city,
        },
    )
    geocodes = data.get("geocodes", [])
    if not geocodes:
        raise RuntimeError(f"未找到地点“{address}”对应的坐标。")

    item = geocodes[0]
    return item["location"], item.get("formatted_address", address)


def _normalize_radius(radius: int) -> int:
    return max(500, min(radius, 50000))


def _format_nearby_poi(poi: dict) -> str:
    name = poi.get("name", "未知地点")
    poi_type = poi.get("type", "").split(";")[0] or "POI"
    address = poi.get("address") or poi.get("adname") or "地址待补充"
    distance = poi.get("distance")
    distance_text = f"，约 {distance} 米" if distance else ""
    return f"{name}（{poi_type}，{address}{distance_text}）"


@tool
def search_nearby_pois(
    center: str,
    keywords: str = "餐厅",
    city: str = "",
    radius: int = 2000,
) -> str:
    """使用高德地图查询某个地点附近的真实 POI，如餐厅、咖啡馆、地铁站、商场。"""
    try:
        location, resolved_center = _geocode(center, city)
        data = amap_request(
            "/v3/place/around",
            {
                "location": location,
                "keywords": keywords,
                "radius": _normalize_radius(radius),
                "sortrule": "distance",
                "extensions": "base",
                "offset": 6,
                "page": 1,
            },
        )
    except httpx.HTTPError as exc:
        return f"高德周边检索失败：{exc}"
    except Exception as exc:
        return f"高德周边检索失败：{exc}"

    pois = data.get("pois", [])
    if not pois:
        return f"高德地图中暂未检索到“{center}”附近与“{keywords}”相关的 POI。"

    formatted = [_format_nearby_poi(poi) for poi in pois[:6]]
    return f"{resolved_center}附近的{keywords}：{'；'.join(formatted)}"
