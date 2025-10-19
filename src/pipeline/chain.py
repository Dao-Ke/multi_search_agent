from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from langchain_core.runnables import RunnableLambda
from langchain_core.runnables import RunnableParallel
import os
from dotenv import load_dotenv
from langchain_chroma import Chroma
from src.llm.embeddings import get_langchain_embeddings
from src.config import CHROMA_PERSIST_DIR
from src.geo.region import extract_province
from src.rag.partition import build_partition_filters_precise
from src.pipeline.summary import summarize_with_ollama
from src.utils.log import log_debug


def _enrich_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
    province = inputs.get("province") or extract_province(inputs["question"])
    out = {**inputs, "province": province}
    log_debug(f"EnrichInput | province={province}")
    return out


def _build_filters(inputs: Dict[str, Any]) -> Dict[str, Any]:
    province = inputs.get("province")
    filters_list = build_partition_filters_precise(province)
    names = ", ".join([f.get("name") for f in filters_list])
    log_debug(f"BuildFilters | province={province} | groups={names}")
    return {**inputs, "filters_list": filters_list}


# Compact filter to short tag-friendly string for logging
def _compact_where(where: Optional[Dict[str, Any]]) -> str:
    try:
        if where is None:
            return "None"
        if isinstance(where, dict):
            parts: List[str] = []
            for k in ("kb_type", "province"):
                if k in where:
                    v = where.get(k)
                    s = str(v)
                    s = s[:30] + ("..." if len(s) > 30 else "")
                    parts.append(f"{k}={s}")
            if not parts:
                parts = [f"{k}={str(v)[:30]}" for k, v in where.items()]
            return ";".join(parts)
        return str(where)[:60]
    except Exception:
        return "Unknown"


def _run_multi_query(inputs: Dict[str, Any]) -> Dict[str, Any]:
    question = inputs["question"]
    top_k = inputs.get("top_k") or 3
    filters_list = inputs["filters_list"]

    log_debug(f"RunMultiQuery start | top_k={top_k} | groups={len(filters_list)}")

    # Build vectorstore & retrievers per group
    load_dotenv()
    persist_dir = os.getenv("CHROMA_PERSIST_DIR", CHROMA_PERSIST_DIR)
    embeddings = get_langchain_embeddings()
    vectorstore = Chroma(collection_name="knowledge_base", persist_directory=persist_dir, embedding_function=embeddings)

    retrievers = {
        f["name"]: vectorstore.as_retriever(search_kwargs={"k": top_k, "filter": f.get("where")})
        for f in filters_list
    }
    log_debug("Retrievers built | " + ", ".join([f"{name}" for name in retrievers.keys()]))

    # Parallel run of query across retrievers using LCEL RunnableParallel
    where_by_name = {f.get("name"): f.get("where") for f in filters_list}
    parallel_map = {}
    for name, retr in retrievers.items():
        w = where_by_name.get(name)
        tags = ["retrieve", f"filter:{_compact_where(w)}"]
        parallel_map[name] = RunnableLambda(lambda q, r=retr: r.invoke(q)).with_config(
            run_name=f"Retrieve[{name}]",
            tags=tags,
        )
    parallel = RunnableParallel(parallel_map)
    docs_by_group: Dict[str, List] = parallel.invoke(question)

    # Format contexts to expected structure
    contexts: List[Dict[str, Any]] = []
    for f in filters_list:
        name = f.get("name")
        docs = docs_by_group.get(name, [])
        items: List[Dict[str, Any]] = []
        for doc in docs:
            md = getattr(doc, "metadata", {}) or {}
            text = getattr(doc, "page_content", "")
            source_name = md.get("source_name")
            chunk_id = md.get("chunk_id")
            ref = f"{source_name}::{chunk_id}" if (source_name is not None and chunk_id is not None) else None
            items.append({
                "text": text,
                "kb_type": md.get("kb_type"),
                "province": md.get("province"),
                "source_name": source_name,
                "chunk_id": chunk_id,
                "ref": ref,
            })
        contexts.append({"name": name, "where": f.get("where"), "results": items})

    log_debug("RunMultiQuery end | counts=" + ", ".join([f"{c['name']}={len(c['results'])}" for c in contexts]))

    return {
        "question": question,
        "province": inputs.get("province"),
        "contexts": contexts,
    }


def _summarize_and_refs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    contexts = inputs["contexts"]
    question = inputs["question"]
    province = inputs.get("province")

    log_debug("Summarize start")
    summary_md = summarize_with_ollama(contexts, question, province=province)
    log_debug(f"Summarize end | md_len={len(summary_md)}")

    # Build references per group for final markdown rendering (as strings)
    references: List[Dict[str, Any]] = []
    for gi, group in enumerate(contexts, start=1):
        items: List[str] = []
        for i, it in enumerate(group.get("results", []), start=1):
            name = it.get("source_name")
            sid = f"[{gi}-{i}]"
            items.append(f"{sid} {name}")
        references.append({"name": group.get("name"), "items": items})

    log_debug("References built | groups=" + ", ".join([f"{r['name']}={len(r['items'])}" for r in references]))

    return {
        "question": question,
        "summary": summary_md,
        "references": references,
    }


def build_app_chain(callbacks: Optional[List] = None):
    callbacks = callbacks or []
    enrich_input = RunnableLambda(_enrich_input).with_config(run_name="EnrichInput", tags=["pipeline"], callbacks=callbacks)

    build_filters = RunnableLambda(_build_filters).with_config(run_name="BuildFilters", tags=["pipeline"], callbacks=callbacks)

    run_multi_query = RunnableLambda(_run_multi_query).with_config(run_name="RunMultiQuery", tags=["pipeline"], callbacks=callbacks)

    summarize_and_refs = RunnableLambda(_summarize_and_refs).with_config(run_name="SummarizeAndRefs", tags=["pipeline"], callbacks=callbacks)

    chain = enrich_input | build_filters | run_multi_query | summarize_and_refs
    return chain.with_config(run_name="AppChain", tags=["app"], callbacks=callbacks)