"""
Chroma + BM25 类混合检索示例
运行前：
pip install langchain langchain-community langchain-openai chromadb rank_bm25 jieba
"""
from pathlib import Path
import jieba
from rank_bm25 import BM25Okapi
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

DATA_DIRS = ["city_docs", "attraction_docs", "route_docs"]
PERSIST_DIR = "chroma_travel_db"

def tokenize(text: str):
    return list(jieba.cut(text))

def load_raw_docs():
    docs = []
    for d in DATA_DIRS:
        loader = DirectoryLoader(d, glob="**/*.txt", loader_cls=TextLoader, loader_kwargs={"encoding": "utf-8"})
        docs.extend(loader.load())
    return docs

raw_docs = load_raw_docs()
bm25 = BM25Okapi([tokenize(doc.page_content) for doc in raw_docs])

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma(
    persist_directory=PERSIST_DIR,
    embedding_function=embeddings,
    collection_name="china_travel_rag",
)

def hybrid_search(query: str, top_k: int = 6, bm25_k: int = 6, vector_k: int = 6):
    vector_docs = vectorstore.similarity_search(query, k=vector_k)
    bm25_scores = bm25.get_scores(tokenize(query))
    bm25_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:bm25_k]
    bm25_docs = [raw_docs[i] for i in bm25_indices]

    merged = {}
    for doc in vector_docs + bm25_docs:
        key = doc.metadata.get("source", "") + doc.page_content[:80]
        merged[key] = doc
    return list(merged.values())[:top_k]

if __name__ == "__main__":
    query = "杭州2天适合父母的轻松游怎么安排？"
    docs = hybrid_search(query)
    for i, doc in enumerate(docs, 1):
        print(f"\n--- Result {i} | {doc.metadata.get('source')} ---")
        print(doc.page_content[:500])
