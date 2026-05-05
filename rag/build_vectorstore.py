from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_EMBEDDING_MODEL,
    RAG_BGE_CHROMA_DIR,
    RAG_BGE_MODEL,
    RAG_CHROMA_COLLECTION,
    RAG_CHROMA_DIR,
    RAG_DASHSCOPE_CHROMA_DIR,
    RAG_EMBEDDING_PROVIDER,
    RAG_KB_DIR,
)


DATA_DIRS = ("city_docs", "attraction_docs", "route_docs")
LEGACY_DOCS_DIR = Path(__file__).parent / "docs"
BGE_PROVIDER = "bge"
DASHSCOPE_PROVIDER = "dashscope"
SUPPORTED_EMBEDDING_PROVIDERS = {BGE_PROVIDER, DASHSCOPE_PROVIDER}


def _kb_dir() -> Path:
    return Path(RAG_KB_DIR).resolve()


def _normalize_provider(provider: str | None = None) -> str:
    selected = (provider or RAG_EMBEDDING_PROVIDER or BGE_PROVIDER).strip().lower()
    if selected in {"openai", "api", "text-embedding-v4"}:
        return DASHSCOPE_PROVIDER
    if selected not in SUPPORTED_EMBEDDING_PROVIDERS:
        return BGE_PROVIDER
    return selected


def _chroma_dir(provider: str | None = None) -> Path:
    selected = _normalize_provider(provider)
    if provider is None and RAG_CHROMA_DIR:
        return Path(RAG_CHROMA_DIR).resolve()
    if selected == BGE_PROVIDER:
        return Path(RAG_BGE_CHROMA_DIR).resolve()
    return Path(RAG_DASHSCOPE_CHROMA_DIR).resolve()


def embedding_model_name(provider: str | None = None) -> str:
    selected = _normalize_provider(provider)
    if selected == BGE_PROVIDER:
        return RAG_BGE_MODEL
    return OPENAI_EMBEDDING_MODEL


def _metadata_path(kb_dir: Path) -> Path:
    return kb_dir / "metadata.jsonl"


def _relative_source(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _safe_metadata(value: Any) -> str | int | float | bool:
    if isinstance(value, (str, int, float, bool)):
        return value
    if value is None:
        return ""
    if isinstance(value, list):
        return "、".join(str(item) for item in value)
    return json.dumps(value, ensure_ascii=False)


def _normalize_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    return {key: _safe_metadata(value) for key, value in metadata.items()}


def _load_metadata_map(kb_dir: Path) -> dict[str, dict[str, Any]]:
    metadata_file = _metadata_path(kb_dir)
    if not metadata_file.exists():
        return {}

    metadata_map: dict[str, dict[str, Any]] = {}
    for line in metadata_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        source = str(item.get("file", "")).replace("\\", "/")
        if source:
            metadata_map[source] = item
    return metadata_map


def _infer_doc_type(path: Path) -> str:
    if path.parent.name == "city_docs":
        return "city_profile"
    if path.parent.name == "attraction_docs":
        return "attraction"
    if path.parent.name == "route_docs":
        return "route_template"
    return "travel_note"


def _fallback_city_from_name(path: Path) -> str:
    stem = path.stem
    parts = stem.split("_")
    if len(parts) >= 2:
        return parts[1]
    return stem.replace("_guide", "")


def load_docs() -> list[Document]:
    kb_dir = _kb_dir()
    if kb_dir.exists():
        metadata_map = _load_metadata_map(kb_dir)
        docs: list[Document] = []

        for dirname in DATA_DIRS:
            for file in sorted((kb_dir / dirname).glob("**/*.txt")):
                text = file.read_text(encoding="utf-8").strip()
                if not text:
                    continue

                source = _relative_source(file, kb_dir)
                metadata = {
                    "source": source,
                    "source_file": file.name,
                    "doc_type": _infer_doc_type(file),
                    "city": _fallback_city_from_name(file),
                    **metadata_map.get(source, {}),
                }
                metadata["source"] = source
                docs.append(Document(page_content=text, metadata=_normalize_metadata(metadata)))

        if docs:
            return docs

    docs = []
    for file in LEGACY_DOCS_DIR.glob("*.txt"):
        text = file.read_text(encoding="utf-8")
        chunks = [line.strip() for line in text.splitlines() if line.strip()] or [text.strip()]
        city = file.stem.replace("_guide", "")
        for chunk in chunks:
            if chunk:
                docs.append(
                    Document(
                        page_content=chunk,
                        metadata={"source": file.name, "source_file": file.name, "city": city},
                    )
                )
    return docs


class SentenceTransformerEmbeddings:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(
            texts,
            batch_size=16,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def _build_dashscope_embeddings() -> OpenAIEmbeddings:
    kwargs: dict[str, Any] = {
        "model": OPENAI_EMBEDDING_MODEL,
        "check_embedding_ctx_length": False,
        "chunk_size": 10,
        "http_client": httpx.Client(trust_env=False, timeout=60.0),
    }
    if OPENAI_API_KEY:
        kwargs["api_key"] = OPENAI_API_KEY
    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL
    return OpenAIEmbeddings(**kwargs)


def _build_embeddings(provider: str | None = None):
    selected = _normalize_provider(provider)
    if selected == BGE_PROVIDER:
        return SentenceTransformerEmbeddings(RAG_BGE_MODEL)
    return _build_dashscope_embeddings()


def _split_docs(docs: list[Document]) -> list[Document]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=900,
        chunk_overlap=120,
        add_start_index=True,
        separators=["\n## ", "\n# ", "\n\n", "\n", "。", "；", "，", " ", ""],
    )
    return splitter.split_documents(docs)


def build_chroma_index(force: bool = False, provider: str | None = None) -> int:
    from langchain_chroma import Chroma

    selected = _normalize_provider(provider)
    persist_dir = _chroma_dir(selected)
    if force and persist_dir.exists():
        shutil.rmtree(persist_dir)

    docs = load_docs()
    chunks = _split_docs(docs)
    if not chunks:
        raise RuntimeError(f"没有找到可写入 Chroma 的 RAG 文档：{_kb_dir()}")

    model_name = embedding_model_name(selected)
    for chunk in chunks:
        chunk.metadata["embedding_provider"] = selected
        chunk.metadata["embedding_model"] = model_name

    persist_dir.mkdir(parents=True, exist_ok=True)
    Chroma.from_documents(
        documents=chunks,
        embedding=_build_embeddings(selected),
        persist_directory=str(persist_dir),
        collection_name=RAG_CHROMA_COLLECTION,
    )
    return len(chunks)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9]+", text.lower())


def _tokenize_bm25(text: str) -> list[str]:
    try:
        import jieba

        tokens = [token.strip().lower() for token in jieba.cut(text) if token.strip()]
    except Exception:
        tokens = _tokenize(text)
    return tokens or _tokenize(text)


def _doc_key(doc: Document) -> str:
    source = str(doc.metadata.get("source", ""))
    start_index = str(doc.metadata.get("start_index", ""))
    return f"{source}|{start_index}|{doc.page_content[:120]}"


def _rrf_fuse(rankings: list[list[Document]], *, top_k: int, rrf_k: int = 60) -> list[Document]:
    scores: defaultdict[str, float] = defaultdict(float)
    docs_by_key: dict[str, Document] = {}

    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            key = _doc_key(doc)
            docs_by_key.setdefault(key, doc)
            scores[key] += 1.0 / (rrf_k + rank)

    ranked_keys = sorted(scores, key=lambda key: scores[key], reverse=True)
    return [docs_by_key[key] for key in ranked_keys[:top_k]]


class LocalKeywordRetriever:
    def __init__(self, docs: list[Document], top_k: int = 5):
        self.docs = docs
        self.top_k = top_k

    def invoke(self, query: str) -> list[Document]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scored = []
        for doc in self.docs:
            haystack = " ".join(
                [
                    doc.page_content.lower(),
                    str(doc.metadata.get("source", "")).lower(),
                    str(doc.metadata.get("city", "")).lower(),
                    str(doc.metadata.get("tags", "")).lower(),
                    str(doc.metadata.get("people", "")).lower(),
                ]
            )
            score = sum(haystack.count(token) for token in query_tokens)
            if score:
                scored.append((score, doc))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored[: self.top_k]]


class ChromaTravelRetriever:
    def __init__(self, top_k: int = 5, provider: str | None = None):
        from langchain_chroma import Chroma

        self.top_k = top_k
        self.provider = _normalize_provider(provider)
        self.vectorstore = Chroma(
            persist_directory=str(_chroma_dir(self.provider)),
            embedding_function=_build_embeddings(self.provider),
            collection_name=RAG_CHROMA_COLLECTION,
        )

    def invoke(self, query: str) -> list[Document]:
        return self.vectorstore.similarity_search(query, k=self.top_k)


class HybridBgeBm25RrfRetriever:
    def __init__(self, top_k: int = 5, vector_k: int = 8, bm25_k: int = 8):
        from langchain_chroma import Chroma
        from rank_bm25 import BM25Okapi

        self.top_k = top_k
        self.vector_k = vector_k
        self.bm25_k = bm25_k
        self.docs = _split_docs(load_docs())
        self.bm25 = BM25Okapi([_tokenize_bm25(doc.page_content) for doc in self.docs])
        self.vectorstore = Chroma(
            persist_directory=str(_chroma_dir(BGE_PROVIDER)),
            embedding_function=_build_embeddings(BGE_PROVIDER),
            collection_name=RAG_CHROMA_COLLECTION,
        )

    def _bm25_search(self, query: str) -> list[Document]:
        scores = self.bm25.get_scores(_tokenize_bm25(query))
        ranked_indices = sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)
        return [self.docs[index] for index in ranked_indices[: self.bm25_k] if scores[index] > 0]

    def invoke(self, query: str) -> list[Document]:
        vector_docs = self.vectorstore.similarity_search(query, k=self.vector_k)
        bm25_docs = self._bm25_search(query)
        return _rrf_fuse([vector_docs, bm25_docs], top_k=self.top_k)


def _has_chroma_index(provider: str | None = None) -> bool:
    persist_dir = _chroma_dir(provider)
    return persist_dir.exists() and any(persist_dir.iterdir())


def build_retriever():
    provider = _normalize_provider()
    if provider == BGE_PROVIDER and _has_chroma_index(BGE_PROVIDER):
        try:
            return HybridBgeBm25RrfRetriever(top_k=5)
        except Exception:
            pass

    if _has_chroma_index(provider):
        try:
            return ChromaTravelRetriever(top_k=5, provider=provider)
        except Exception:
            pass
    return LocalKeywordRetriever(load_docs(), top_k=5)
