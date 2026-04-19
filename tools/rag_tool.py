from langchain.tools import tool
from rag.build_vectorstore import build_retriever


retriever = build_retriever()


@tool
def search_travel_knowledge(query: str) -> str:
    """从本地旅游知识库中检索目的地攻略、注意事项、景点说明等信息。"""
    docs = retriever.invoke(query)
    if not docs:
        return f"本地知识库中暂未检索到与“{query}”相关的旅游知识。"

    results = []
    for i, doc in enumerate(docs, start=1):
        source = doc.metadata.get("source", "unknown")
        content = doc.page_content[:200].replace("\n", " ")
        results.append(f"[{i}] 来源: {source} 内容: {content}")

    return "\n".join(results)
