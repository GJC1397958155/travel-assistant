from langchain.tools import tool
from rag.build_vectorstore import build_retriever


_retriever = None


def _get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = build_retriever()
    return _retriever


@tool
def search_travel_knowledge(query: str) -> str:
    """从本地旅游知识库中检索目的地攻略、注意事项、景点说明等信息。"""
    docs = _get_retriever().invoke(query)
    if not docs:
        return f"本地知识库中暂未检索到与“{query}”相关的旅游知识。"

    results = []
    for i, doc in enumerate(docs, start=1):
        source = doc.metadata.get("source", "unknown")
        city = doc.metadata.get("city", "")
        doc_type = doc.metadata.get("doc_type", "")
        tags = doc.metadata.get("tags", "")
        content = doc.page_content[:320].replace("\n", " ")
        meta_parts = [part for part in (city, doc_type, tags) if part]
        meta_text = f"（{'；'.join(str(part) for part in meta_parts)}）" if meta_parts else ""
        results.append(f"[{i}] 来源: {source}{meta_text} 内容: {content}")

    return "\n".join(results)
