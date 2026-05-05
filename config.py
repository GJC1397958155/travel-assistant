import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "qwen-plus")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "")
RAG_EMBEDDING_PROVIDER = os.getenv("RAG_EMBEDDING_PROVIDER", "bge").strip().lower()
RAG_BGE_MODEL = os.getenv("RAG_BGE_MODEL", "BAAI/bge-large-zh-v1.5")

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

if not OPENAI_EMBEDDING_MODEL:
    if "dashscope.aliyuncs.com" in OPENAI_BASE_URL or OPENAI_MODEL.startswith("qwen"):
        OPENAI_EMBEDDING_MODEL = "text-embedding-v4"
    else:
        OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"

if not TRAVEL_MEMORY_DIR:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        TRAVEL_MEMORY_DIR = str(Path(local_app_data) / "travel-assistant-memory")
    else:
        TRAVEL_MEMORY_DIR = str(Path.home() / ".travel-assistant-memory")

local_app_data = os.getenv("LOCALAPPDATA")
if local_app_data:
    DEFAULT_RAG_CHROMA_BASE_DIR = Path(local_app_data) / "travel-assistant-rag"
else:
    DEFAULT_RAG_CHROMA_BASE_DIR = Path.home() / ".travel-assistant-rag"

DEFAULT_RAG_DASHSCOPE_CHROMA_DIR = str(DEFAULT_RAG_CHROMA_BASE_DIR / "chroma_dashscope_text_embedding_v4")
DEFAULT_RAG_BGE_CHROMA_DIR = str(DEFAULT_RAG_CHROMA_BASE_DIR / "chroma_bge_large_zh_v15")

PROJECT_ROOT = Path(__file__).resolve().parent
RAG_KB_DIR = os.getenv(
    "RAG_KB_DIR",
    str(PROJECT_ROOT / "china_34_travel_rag_kb" / "china_34_rag_kb"),
)
RAG_DASHSCOPE_CHROMA_DIR = os.getenv("RAG_DASHSCOPE_CHROMA_DIR", DEFAULT_RAG_DASHSCOPE_CHROMA_DIR)
RAG_BGE_CHROMA_DIR = os.getenv("RAG_BGE_CHROMA_DIR", DEFAULT_RAG_BGE_CHROMA_DIR)
RAG_CHROMA_DIR = os.getenv(
    "RAG_CHROMA_DIR",
    RAG_BGE_CHROMA_DIR if RAG_EMBEDDING_PROVIDER == "bge" else RAG_DASHSCOPE_CHROMA_DIR,
)
RAG_CHROMA_COLLECTION = os.getenv("RAG_CHROMA_COLLECTION", "china_travel_rag")
