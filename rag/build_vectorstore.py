from pathlib import Path
import re

from langchain_core.documents import Document


DOCS_DIR = Path(__file__).parent / "docs"


def load_docs():
    docs = []
    for file in DOCS_DIR.glob("*.txt"):
        text = file.read_text(encoding="utf-8")
        chunks = [line.strip() for line in text.splitlines() if line.strip()]
        if not chunks and text.strip():
            chunks = [text.strip()]

        city = file.stem.replace("_guide", "")
        for chunk in chunks:
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={"source": file.name, "city": city},
                )
            )
    return docs


def _tokenize(text: str):
    return re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9]+", text.lower())


class LocalKeywordRetriever:
    def __init__(self, docs, top_k: int = 3):
        self.docs = docs
        self.top_k = top_k

    def invoke(self, query: str):
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
                ]
            )
            score = sum(haystack.count(token) for token in query_tokens)
            if score:
                scored.append((score, doc))

        if not scored:
            return []

        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored[: self.top_k]]


def build_retriever():
    docs = load_docs()
    return LocalKeywordRetriever(docs, top_k=3)
