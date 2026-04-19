import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "qwen-plus")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")

QWEATHER_API_HOST = os.getenv("QWEATHER_API_HOST", "")
QWEATHER_API_KEY = os.getenv("QWEATHER_API_KEY", "")
QWEATHER_LANG = os.getenv("QWEATHER_LANG", "zh")
QWEATHER_UNIT = os.getenv("QWEATHER_UNIT", "m")

AMAP_WEB_API_KEY = os.getenv("AMAP_WEB_API_KEY", "")
AMAP_WEB_API_HOST = os.getenv("AMAP_WEB_API_HOST", "https://restapi.amap.com")

TRAVEL_MEMORY_BACKEND = os.getenv("TRAVEL_MEMORY_BACKEND", "sqlite").strip().lower()
TRAVEL_MEMORY_DIR = os.getenv("TRAVEL_MEMORY_DIR", "")

if not OPENAI_BASE_URL and OPENAI_MODEL.startswith("qwen"):
    # DashScope provides an OpenAI-compatible endpoint for Qwen models.
    OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

if not TRAVEL_MEMORY_DIR:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        TRAVEL_MEMORY_DIR = str(Path(local_app_data) / "travel-assistant-memory")
    else:
        TRAVEL_MEMORY_DIR = str(Path.home() / ".travel-assistant-memory")
