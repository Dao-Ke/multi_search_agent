import os
from typing import Optional

from langchain_core.embeddings import Embeddings
from typing import Optional
import os
from urllib.parse import urlparse
from langchain_ollama import OllamaEmbeddings


def _ensure_local_no_proxy(base_url: Optional[str]) -> None:
    try:
        url = base_url or os.getenv("OLLAMA_BASE_URL")
        if not url:
            return
        p = urlparse(url)
        host = p.hostname
        if host in ("127.0.0.1", "localhost"):
            existing = os.getenv("NO_PROXY") or os.getenv("no_proxy") or ""
            parts = [s.strip() for s in existing.split(",") if s.strip()]
            if host not in parts:
                parts.append(host)
            os.environ["NO_PROXY"] = ",".join(parts)
    except Exception:
        # 环境变量设置失败不影响主流程
        pass


def get_langchain_embeddings(model: Optional[str] = None, base_url: Optional[str] = None) -> Embeddings:
    m = model or os.getenv("OLLAMA_EMBED_MODEL", "bge-m3:latest")
    kwargs = {"model": m}
    url = base_url or os.getenv("OLLAMA_BASE_URL")
    if url:
        kwargs["base_url"] = url
        _ensure_local_no_proxy(url)
    return OllamaEmbeddings(**kwargs)