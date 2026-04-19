import httpx
from langchain.tools import tool

from tools.amap_base import amap_request

# 负责地址转坐标和坐标转地址
def _format_geocode_item(item: dict) -> str:
    formatted = item.get("formatted_address", "未知地址")
    location = item.get("location", "")
    level = item.get("level", "")
    return f"{formatted}，坐标 {location}，匹配级别 {level}"


@tool
def geocode_address(address: str, city: str = "") -> str:
    """使用高德地图将地址名称转换为经纬度坐标。"""
    try:
        data = amap_request(
            "/v3/geocode/geo",
            {
                "address": address,
                "city": city,
            },
        )
    except httpx.HTTPError as exc:
        return f"高德地理编码查询失败：{exc}"
    except Exception as exc:
        return f"高德地理编码查询失败：{exc}"

    geocodes = data.get("geocodes", [])
    if not geocodes:
        return f"高德地图中暂未检索到地址“{address}”的坐标。"

    return _format_geocode_item(geocodes[0])


@tool
def reverse_geocode(location: str) -> str:
    """使用高德地图将经纬度坐标转换为结构化地址。坐标格式为 lng,lat。"""
    try:
        data = amap_request(
            "/v3/geocode/regeo",
            {
                "location": location,
                "extensions": "base",
            },
        )
    except httpx.HTTPError as exc:
        return f"高德逆地理编码查询失败：{exc}"
    except Exception as exc:
        return f"高德逆地理编码查询失败：{exc}"

    regeocode = data.get("regeocode", {})
    if not regeocode:
        return f"高德地图中暂未检索到坐标“{location}”对应的地址。"

    formatted = regeocode.get("formatted_address", "未知地址")
    address_component = regeocode.get("addressComponent", {})
    city = address_component.get("city") or address_component.get("province", "")
    district = address_component.get("district", "")
    township = address_component.get("township", "")
    return f"{formatted}（{city}{district}{township}）"
