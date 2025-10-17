import os
from typing import Dict, List, Tuple

import chromadb
from chromadb import PersistentClient

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import DATA_DIR, CHROMA_PERSIST_DIR
from src.llm.embeddings import HashEmbedding
from src.llm.tongyi import TongyiEmbedding


def parse_kb_metadata(filename: str) -> Tuple[str, str]:
    """Return (kb_type, province) parsed from filename like '【中央】xxx' or '【辽宁】xxx'."""
    if filename.startswith("【中央】"):
        return "core", "中央"
    if filename.startswith("【") and "】" in filename:
        prov = filename[1 : filename.index("】")]
        return "regional", prov
    return "regional", "未知"


def read_all_files(data_dir: str) -> List[Dict]:
    items = []
    for name in os.listdir(data_dir):
        path = os.path.join(data_dir, name)
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        kb_type, province = parse_kb_metadata(name)
        items.append(
            {
                "text": content,
                "metadata": {
                    "kb_type": kb_type,
                    "province": province,
                    "source_name": name,
                    "source_path": path,
                },
            }
        )
    return items


def split_items(items: List[Dict], chunk_size: int = 1000, chunk_overlap: int = 100) -> List[Dict]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks: List[Dict] = []
    for item in items:
        texts = splitter.split_text(item["text"]) if item["text"] else []
        for idx, t in enumerate(texts):
            md = dict(item["metadata"])  # shallow copy
            md["chunk_id"] = idx
            chunks.append({"text": t, "metadata": md})
    return chunks


def get_client(persist_dir: str) -> PersistentClient:
    os.makedirs(persist_dir, exist_ok=True)
    return chromadb.PersistentClient(path=persist_dir)


def get_or_create_collection(client: PersistentClient, name: str = "knowledge_base"):
    return client.get_or_create_collection(name=name)


def select_embedder():
    # Prefer Tongyi if API key is configured and not in test mode
    api_key = os.getenv("TONGYI_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    test_mode = os.getenv("TEST_MODE", "0") in ("1", "true", "True")
    if api_key and not test_mode:
        return TongyiEmbedding(api_key=api_key)
    return HashEmbedding()


def add_chunks(collection, chunks: List[Dict]):
    texts = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]
    ids = [f"{m['source_name']}::{m['chunk_id']}" for m in metadatas]

    embedder = select_embedder()
    embeddings = embedder.embed(texts)

    collection.add(documents=texts, metadatas=metadatas, ids=ids, embeddings=embeddings)


def init_vector_db(
    data_dir: str = DATA_DIR,
    persist_dir: str = CHROMA_PERSIST_DIR,
    reset: bool = False,
    verbose: bool = False,
) -> Dict:
    # Allow None overrides from CLI to fall back to config defaults
    data_dir = data_dir or DATA_DIR
    persist_dir = persist_dir or CHROMA_PERSIST_DIR

    client = get_client(persist_dir)
    if reset:
        # Drop and recreate collection for a clean state
        try:
            client.delete_collection("knowledge_base")
        except Exception:
            pass
    collection = get_or_create_collection(client, name="knowledge_base")

    items = read_all_files(data_dir)
    chunks = split_items(items)
    if chunks:
        add_chunks(collection, chunks)

    # Build summary
    total = collection.count()
    by_kb: Dict[str, int] = {}
    for kb_type in ("core", "regional"):
        res = collection.get(where={"kb_type": kb_type})
        by_kb[kb_type] = len(res.get("ids", []))

    # Per-file chunk counts for visibility
    file_chunk_counts: Dict[str, int] = {}
    file_meta: Dict[str, Dict] = {}
    for c in chunks:
        name = c["metadata"]["source_name"]
        file_chunk_counts[name] = file_chunk_counts.get(name, 0) + 1
        if name not in file_meta:
            file_meta[name] = {
                "kb_type": c["metadata"].get("kb_type"),
                "province": c["metadata"].get("province"),
            }

    # Detect skipped empty files for diagnostics
    skipped_empty = [i["metadata"]["source_name"] for i in items if not (i["text"] or "").strip()]

    if verbose:
        print(f"Chroma collection: knowledge_base | persist_dir: {persist_dir}")
        for name, cnt in sorted(file_chunk_counts.items()):
            meta = file_meta.get(name, {})
            print(
                f"Inserted: {name} [kb_type={meta.get('kb_type')}, province={meta.get('province')}] chunks={cnt}"
            )
        for name in sorted(skipped_empty):
            print(f"Skipped empty: {name}")
        print(f"Total chunks added: {sum(file_chunk_counts.values())} | collection count: {total}")

    processed_files = sorted({c["metadata"]["source_name"] for c in chunks})
    return {
        "persist_dir": persist_dir,
        "collection": "knowledge_base",
        "total_chunks": total,
        "processed_files": processed_files,
        "by_kb_type": by_kb,
        "file_chunk_counts": file_chunk_counts,
        "skipped_empty_files": skipped_empty,
    }