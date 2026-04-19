from datetime import date as date_cls
import re
from typing import Optional

import httpx
from langchain.tools import tool

from config import (
    QWEATHER_API_HOST,
    QWEATHER_API_KEY,
    QWEATHER_LANG,
    QWEATHER_UNIT,
)


def _base_url() -> str:
    host = QWEATHER_API_HOST.strip()
    if not host:
        return ""
    if host.startswith("http://") or host.startswith("https://"):
        return host.rstrip("/")
    return f"https://{host.rstrip('/')}"


def _parse_target_date(raw_date: str) -> Optional[date_cls]:
    text = raw_date.strip()
    if not text or text in {"今天", "今日", "现在", "当前"}:
        return None

    offsets = {
        "明天": 1,
        "后天": 2,
    }
    if text in offsets:
        return date_cls.today().fromordinal(date_cls.today().toordinal() + offsets[text])

    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        year, month, day = map(int, match.groups())
        return date_cls(year, month, day)

    match = re.fullmatch(r"(\d{1,2})月(\d{1,2})(?:日|号)", text)
    if match:
        month, day = map(int, match.groups())
        today = date_cls.today()
        target = date_cls(today.year, month, day)
        if target < today:
            target = date_cls(today.year + 1, month, day)
        return target

    raise ValueError("暂时只支持 今天/明天/后天/YYYY-MM-DD/MM月DD日/MM月DD号 这几种日期格式。")


def _request_json(path: str, params: dict) -> dict:
    base_url = _base_url()
    if not base_url:
        raise RuntimeError("未配置 QWEATHER_API_HOST。")
    if not QWEATHER_API_KEY:
        raise RuntimeError("未配置 QWEATHER_API_KEY。")

    headers = {"X-QW-Api-Key": QWEATHER_API_KEY}
    with httpx.Client(timeout=20.0, trust_env=False) as client:
        response = client.get(
            f"{base_url}{path}",
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    if data.get("code") != "200":
        raise RuntimeError(f"天气接口返回异常，code={data.get('code', 'unknown')}")
    return data


def _lookup_city(city: str) -> dict:
    data = _request_json(
        "/geo/v2/city/lookup",
        {
            "location": city,
            "number": 1,
            "lang": QWEATHER_LANG,
        },
    )
    locations = data.get("location", [])
    if not locations:
        raise RuntimeError(f"没有找到城市“{city}”对应的天气位置。")
    return locations[0]


def _pick_daily_path(days_ahead: int) -> str:
    if days_ahead <= 2:
        return "/v7/weather/3d"
    if days_ahead <= 6:
        return "/v7/weather/7d"
    if days_ahead <= 9:
        return "/v7/weather/10d"
    return "/v7/weather/15d"


def _format_place(location: dict) -> str:
    parts = [location.get("name", "")]
    for key in ("adm2", "adm1"):
        value = location.get(key, "")
        if value and value not in parts:
            parts.append(value)
    return " / ".join(parts)


@tool
def get_weather(city: str, date: str = "") -> str:
    """查询某个城市某天或近期的真实天气情况。"""
    try:
        location = _lookup_city(city)
        place = _format_place(location)
        location_id = location["id"]
        target_date = _parse_target_date(date)

        if target_date is None:
            data = _request_json(
                "/v7/weather/now",
                {
                    "location": location_id,
                    "lang": QWEATHER_LANG,
                    "unit": QWEATHER_UNIT,
                },
            )
            now = data["now"]
            observed_at = now.get("obsTime", "")
            if observed_at:
                observed_at = observed_at.replace("T", " ").replace("+08:00", "")

            return (
                f"{place}当前天气：{now['text']}，气温{now['temp']}℃，"
                f"体感{now['feelsLike']}℃，湿度{now['humidity']}%，"
                f"{now['windDir']}{now['windScale']}级。"
                f"{' 观测时间：' + observed_at if observed_at else ''}"
                " 数据来源：和风天气。"
            )

        days_ahead = (target_date - date_cls.today()).days
        if days_ahead < 0:
            return f"暂不支持查询 {target_date.isoformat()} 的历史天气。"
        if days_ahead > 14:
            return "当前只接入了未来 15 天预报接口，请把日期控制在 15 天内。"

        data = _request_json(
            _pick_daily_path(days_ahead),
            {
                "location": location_id,
                "lang": QWEATHER_LANG,
                "unit": QWEATHER_UNIT,
            },
        )
        for daily in data.get("daily", []):
            if daily.get("fxDate") == target_date.isoformat():
                return (
                    f"{place}在{target_date.isoformat()}的天气："
                    f"白天{daily['textDay']}，夜间{daily['textNight']}，"
                    f"气温{daily['tempMin']}~{daily['tempMax']}℃，"
                    f"降水概率{daily['precip']}%，"
                    f"风力{daily['windDirDay']}{daily['windScaleDay']}级。"
                    " 数据来源：和风天气。"
                )

        return f"没有查到 {place} 在 {target_date.isoformat()} 的天气数据。"
    except ValueError as exc:
        return f"天气查询失败：{exc}"
    except httpx.HTTPError as exc:
        return f"天气接口连接失败：{exc}"
    except Exception as exc:
        return f"天气查询失败：{exc}"
