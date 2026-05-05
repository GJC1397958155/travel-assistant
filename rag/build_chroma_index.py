from __future__ import annotations

import argparse

from config import RAG_CHROMA_COLLECTION, RAG_KB_DIR
from rag.build_vectorstore import (
    BGE_PROVIDER,
    DASHSCOPE_PROVIDER,
    _chroma_dir,
    _normalize_provider,
    build_chroma_index,
    embedding_model_name,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Chroma index for the travel RAG knowledge base.")
    parser.add_argument("--force", action="store_true", help="Recreate the Chroma directory before indexing.")
    parser.add_argument(
        "--provider",
        choices=[BGE_PROVIDER, DASHSCOPE_PROVIDER],
        default=None,
        help="Embedding provider to index. Defaults to the active RAG_EMBEDDING_PROVIDER.",
    )
    parser.add_argument("--all", action="store_true", help="Build both DashScope and BGE indexes.")
    args = parser.parse_args()

    providers = [DASHSCOPE_PROVIDER, BGE_PROVIDER] if args.all else [_normalize_provider(args.provider)]
    for provider in providers:
        chunk_count = build_chroma_index(force=args.force, provider=provider)
        print(f"Chroma 知识库构建完成：{chunk_count} chunks")
        print(f"Provider：{provider}")
        print(f"知识库目录：{RAG_KB_DIR}")
        print(f"Chroma 目录：{_chroma_dir(provider)}")
        print(f"Collection：{RAG_CHROMA_COLLECTION}")
        print(f"Embedding model：{embedding_model_name(provider)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
