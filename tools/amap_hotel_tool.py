import httpx
from langchain.tools import tool

from tools.amap_base import amap_request


def _hotel_keywords(area: str) -> str:
    area_text = area.strip()
    if not area_text:
        return "酒店"
    return f"{area_text} 酒店"


def _format_hotel(poi: dict) -> str:
    name = poi.get("name", "未知酒店")
    address = poi.get("address") or poi.get("adname") or "地址待补充"
    hotel_type = poi.get("type", "").split(";")[0] or "酒店"
    return f"{name}（{hotel_type}，{address}）"


@tool
def search_hotels(city: str, area: str = "") -> str:
    """使用高德地图在某个城市或某个区域附近检索真实酒店住宿 POI。"""
    try:
        data = amap_request(
            "/v3/place/text",
            {
                "keywords": _hotel_keywords(area),
                "city": city,
                "citylimit": "true",
                "extensions": "base",
                "offset": 6,
                "page": 1,
            },
        )
    except httpx.HTTPError as exc:
        return f"高德酒店检索失败：{exc}"
    except Exception as exc:
        return f"高德酒店检索失败：{exc}"

    pois = data.get("pois", [])
    if not pois:
        if area.strip():
            return f"高德地图中暂未检索到{city}{area}附近的酒店。"
        return f"高德地图中暂未检索到{city}相关酒店。"

    formatted = [_format_hotel(poi) for poi in pois[:6]]
    if area.strip():
        return f"{city}{area}附近酒店：{'；'.join(formatted)}"
    return f"{city}酒店推荐：{'；'.join(formatted)}"
