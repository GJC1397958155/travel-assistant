import httpx

from config import AMAP_WEB_API_HOST, AMAP_WEB_API_KEY


def amap_base_url() -> str:
    host = AMAP_WEB_API_HOST.strip()
    if not host:
        return ""
    if host.startswith("http://") or host.startswith("https://"):
        return host.rstrip("/")
    return f"https://{host.rstrip('/')}"


def amap_request(path: str, params: dict) -> dict:
    base_url = amap_base_url()
    if not base_url:
        raise RuntimeError("未配置 AMAP_WEB_API_HOST。")
    if not AMAP_WEB_API_KEY:
        raise RuntimeError("未配置 AMAP_WEB_API_KEY。")

    request_params = {
        "key": AMAP_WEB_API_KEY,
        "output": "JSON",
        **params,
    }

    with httpx.Client(timeout=20.0, trust_env=False) as client:
        response = client.get(
            f"{base_url}{path}",
            params=request_params,
        )
        response.raise_for_status()
        data = response.json()

    if data.get("status") != "1":
        info = data.get("info", "unknown error")
        infocode = data.get("infocode", "unknown")
        raise RuntimeError(f"高德接口返回异常：{info} (infocode={infocode})")

    return data
