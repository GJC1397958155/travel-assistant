from langchain.tools import tool

import httpx

from tools.amap_base import amap_request


PREFERENCE_KEYWORDS = {
    "热门": "热门景点",
    "美食": "美食",
    "拍照": "景点",
    "轻松": "公园 步行街 江边",
    "亲子": "动物园 海洋馆 乐园",
    "老人": "公园 江景 古镇",
    "购物": "商场 步行街",
    "夜景": "夜景 江景",
}
def _normalize_keywords(preference: str) -> str:
    text = preference.strip()
    if not text:
        return PREFERENCE_KEYWORDS["热门"]

    for key, keywords in PREFERENCE_KEYWORDS.items():
        if key in text or text in key:
            return keywords
    return text


def _request_pois(city: str, keywords: str) -> list[dict]:
    data = amap_request(
        "/v3/place/text",
        {
            "keywords": keywords,
            "city": city,
            "citylimit": "true",
            "extensions": "base",
            "offset": 6,
            "page": 1,
        },
    )
    return data.get("pois", [])


def _format_poi(poi: dict) -> str:
    name = poi.get("name", "未知地点")
    address = poi.get("address") or poi.get("adname") or "地址待补充"
    poi_type = poi.get("type", "").split(";")[0] or "POI"
    return f"{name}（{poi_type}，{address}）"


@tool
def search_pois(city: str, preference: str = "热门") -> str:
    """使用高德地图 Web 服务 API 查询某个城市的真实 POI 推荐。"""
    keywords = _normalize_keywords(preference)
    try:
        pois = _request_pois(city, keywords)
    except httpx.HTTPError as exc:
        return f"高德 POI 查询失败：{exc}"
    except Exception as exc:
        return f"高德 POI 查询失败：{exc}"

    if not pois:
        return f"高德地图中暂未检索到{city}与“{preference}”相关的 POI。"

    formatted = [_format_poi(poi) for poi in pois[:6]]
    return f"{city}推荐：{'；'.join(formatted)}"
