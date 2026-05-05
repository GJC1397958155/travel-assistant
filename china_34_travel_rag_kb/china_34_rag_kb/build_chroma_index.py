"""
LangChain + Chroma 构建示例
运行前：
pip install langchain langchain-community langchain-openai chromadb
设置 OPENAI_API_KEY 后运行：python build_chroma_index.py
"""
from pathlib import Path
import json
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

DATA_DIRS = ["city_docs", "attraction_docs", "route_docs"]
PERSIST_DIR = "chroma_travel_db"

all_docs = []
for d in DATA_DIRS:
    loader = DirectoryLoader(d, glob="**/*.txt", loader_cls=TextLoader, loader_kwargs={"encoding": "utf-8"})
    all_docs.extend(loader.load())

splitter = RecursiveCharacterTextSplitter(
    chunk_size=900,
    chunk_overlap=120,
    separators=["\n## ", "\n# ", "\n\n", "\n", "。", "；", "，", " ", ""],
)
chunks = splitter.split_documents(all_docs)

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory=PERSIST_DIR,
    collection_name="china_travel_rag",
)
print(f"Chroma 知识库构建完成：{len(chunks)} chunks，目录：{PERSIST_DIR}")
