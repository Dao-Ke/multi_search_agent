import argparse
import json
from typing import Dict, List, Optional

import os
import time
from dotenv import load_dotenv

from langchain_chroma import Chroma

from src.config import CHROMA_PERSIST_DIR
from src.llm.embeddings import get_langchain_embeddings
from src.utils.log import setup_run_logging, log_info


def simple_query(
    question: str,
    top_k: int = 4,
    where: Optional[Dict] = None,
) -> List[Dict]:
    """Query the knowledge_base collection via LangChain Chroma and return top-k chunks.

    Returns a list of items with: id, distance, text, kb_type, province, source_name, chunk_id.
    """
    load_dotenv()

    persist_dir = os.getenv("CHROMA_PERSIST_DIR", CHROMA_PERSIST_DIR)
    embeddings = get_langchain_embeddings()
    vectorstore = Chroma(collection_name="knowledge_base", persist_directory=persist_dir, embedding_function=embeddings)

    where_arg = where if (where and len(where) > 0) else None

    # Use embed_query and relevance scores per LangChain API recommendation
    query_vec = embeddings.embed_query(question)

    # Lightweight retry around vector search to handle transient failures
    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            results = vectorstore.similarity_search_by_vector_with_relevance_scores(query_vec, k=top_k, filter=where_arg)
            break
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(0.3 * (attempt + 1))
                continue
            else:
                raise

    out: List[Dict] = []
    for doc, score in results:
        md = doc.metadata or {}
        sid = None
        if md.get("source_name") is not None and md.get("chunk_id") is not None:
            sid = f"{md.get('source_name')}::{md.get('chunk_id')}"
        out.append(
            {
                "id": sid,
                "distance": score,
                "text": doc.page_content,
                "kb_type": md.get("kb_type"),
                "province": md.get("province"),
                "source_name": md.get("source_name"),
                "chunk_id": md.get("chunk_id"),
            }
        )
    return out


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Simple RAG query over knowledge_base")
    parser.add_argument("--q", required=True, help="Question to query")
    parser.add_argument("-k", "--top-k", type=int, default=3, help="Top-k results")
    parser.add_argument("--kb-type", choices=["core", "regional"], help="Filter by kb_type")
    parser.add_argument("--province", help="Filter by province")
    args = parser.parse_args()

    log_path = setup_run_logging(label=args.q, run_type="q")

    where: Dict = {}
    if args.kb_type:
        where["kb_type"] = args.kb_type
    if args.province:
        where["province"] = args.province

    results = simple_query(args.q, top_k=args.top_k, where=where or None)
    log_info(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"查询完成，详情见日志：{log_path}")


if __name__ == "__main__":
    main()