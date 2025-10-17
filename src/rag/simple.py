import argparse
import json
from typing import Dict, List, Optional

import os
from dotenv import load_dotenv
import chromadb

from src.config import CHROMA_PERSIST_DIR
from src.data_init.initializer import select_embedder


def simple_query(
    question: str,
    top_k: int = 4,
    where: Optional[Dict] = None,
) -> List[Dict]:
    """Query the knowledge_base collection and return top-k chunks.

    Returns a list of items with: id, distance, text, kb_type, province, source_name, chunk_id.
    """
    load_dotenv()

    persist_dir = os.getenv("CHROMA_PERSIST_DIR", CHROMA_PERSIST_DIR)
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_or_create_collection("knowledge_base")

    embedder = select_embedder()
    query_emb = embedder.embed([question])

    where_arg = where if (where and len(where) > 0) else None
    res = collection.query(
        query_embeddings=query_emb,
        n_results=top_k,
        where=where_arg,
        include=["documents", "metadatas", "distances"],
    )

    out: List[Dict] = []
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    for i in range(len(docs)):
        md = metas[i] if i < len(metas) else {}
        sid = None
        if md.get("source_name") is not None and md.get("chunk_id") is not None:
            sid = f"{md.get('source_name')}::{md.get('chunk_id')}"
        out.append(
            {
                "id": sid,
                "distance": dists[i] if i < len(dists) else None,
                "text": docs[i],
                "kb_type": md.get("kb_type"),
                "province": md.get("province"),
                "source_name": md.get("source_name"),
                "chunk_id": md.get("chunk_id"),
            }
        )
    return out


def main():
    parser = argparse.ArgumentParser(description="Simple RAG query over knowledge_base")
    parser.add_argument("--q", required=True, help="Question to query")
    parser.add_argument("-k", "--top-k", type=int, default=2, help="Top-k results")
    parser.add_argument("--kb-type", choices=["core", "regional"], help="Filter by kb_type")
    parser.add_argument("--province", help="Filter by province")
    args = parser.parse_args()

    where: Dict = {}
    if args.kb_type:
        where["kb_type"] = args.kb_type
    if args.province:
        where["province"] = args.province

    results = simple_query(args.q, top_k=args.top_k, where=where or None)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()