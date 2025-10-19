import os
import shutil
import json
from typing import Dict, List, Tuple

from langchain_chroma import Chroma

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import DATA_DIR, CHROMA_PERSIST_DIR
from src.llm.embeddings import get_langchain_embeddings
import logging

logger = logging.getLogger("multi_search")


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


def split_items(items: List[Dict], chunk_size: int = 400, chunk_overlap: int = 40) -> List[Dict]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks: List[Dict] = []
    for item in items:
        texts = splitter.split_text(item["text"]) if item["text"] else []
        for idx, t in enumerate(texts):
            if not (t or "").strip():
                continue
            md = dict(item["metadata"])  # shallow copy
            md["chunk_id"] = idx
            chunks.append({"text": t, "metadata": md})
    return chunks


def select_embedder():
    return get_langchain_embeddings()


def get_vectorstore(persist_dir: str, name: str = "knowledge_base"):
    os.makedirs(persist_dir, exist_ok=True)
    embeddings = select_embedder()
    return Chroma(collection_name=name, persist_directory=persist_dir, embedding_function=embeddings)


def add_chunks(vectorstore, chunks: List[Dict]):
    import time
    for c in chunks:
        text = c["text"]
        md = c["metadata"]
        idv = f"{md['source_name']}::{md['chunk_id']}"
        logger.info(f"Adding to vectorstore: {idv} len={len(text)}")
        last_err = None
        for attempt in range(3):
            try:
                vectorstore.add_texts(texts=[text], metadatas=[md], ids=[idv])
                break
            except Exception as e:
                last_err = e
                if attempt < 2:
                    time.sleep(0.4 * (attempt + 1))
                    continue
                else:
                    logger.warning(f"Failed to add chunk {idv} after retries: {e}. Skipping.")
        time.sleep(0.2)


def init_vector_db(
    data_dir: str = DATA_DIR,
    persist_dir: str = CHROMA_PERSIST_DIR,
    reset: bool = False,
    verbose: bool = False,
) -> Dict:
    data_dir = data_dir or DATA_DIR
    persist_dir = persist_dir or CHROMA_PERSIST_DIR

    if reset and os.path.exists(persist_dir):
        shutil.rmtree(persist_dir)

    vectorstore = get_vectorstore(persist_dir, name="knowledge_base")

    items = read_all_files(data_dir)
    chunks = split_items(items)
    if chunks:
        add_chunks(vectorstore, chunks)

    total = len(chunks)
    by_kb: Dict[str, int] = {}
    for kb_type in ("core", "regional"):
        by_kb[kb_type] = sum(1 for c in chunks if c["metadata"].get("kb_type") == kb_type)

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

    # 写入地域注册信息（仅regional，排除未知）到持久化目录
    provinces_present = sorted(
        {
            m.get("province")
            for m in file_meta.values()
            if m.get("kb_type") == "regional" and m.get("province") and m.get("province") != "未知"
        }
    )
    kb_types_present = sorted({m.get("kb_type") for m in file_meta.values() if m.get("kb_type")})
    registry = {
        "provinces": provinces_present,
        "kb_types": kb_types_present,
        "total_chunks": total,
    }
    try:
        os.makedirs(persist_dir, exist_ok=True)
        with open(os.path.join(persist_dir, "kb_registry.json"), "w", encoding="utf-8") as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)
    except Exception as e:
        if verbose:
            logger.warning(f"Warn: failed to write kb_registry.json: {e}")

    skipped_empty = [i["metadata"]["source_name"] for i in items if not (i["text"] or "").strip()]

    if verbose:
        logger.info(f"Chroma collection: knowledge_base | persist_dir: {persist_dir}")
        for name, cnt in sorted(file_chunk_counts.items()):
            meta = file_meta.get(name, {})
            logger.info(
                f"Inserted: {name} [kb_type={meta.get('kb_type')}, province={meta.get('province')}] chunks={cnt}"
            )
        for name in sorted(skipped_empty):
            logger.info(f"Skipped empty: {name}")
        logger.info(f"Total chunks added: {sum(file_chunk_counts.values())} | collection count: {total}")

    processed_files = sorted({c["metadata"]["source_name"] for c in chunks})
    return {
        "persist_dir": persist_dir,
        "collection": "knowledge_base",
        "total_chunks": total,
        "processed_files": processed_files,
        "by_kb_type": by_kb,
        "file_chunk_counts": file_chunk_counts,
        "skipped_empty_files": skipped_empty,
        "registry_path": os.path.join(persist_dir, "kb_registry.json"),
    }