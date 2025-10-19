import logging
import os
import json
from datetime import datetime
from typing import Optional

from langchain_core.callbacks import BaseCallbackHandler

from src.config import PROJECT_ROOT

_logger: Optional[logging.Logger] = None
_log_path: Optional[str] = None


def _sanitize_label(label: Optional[str]) -> str:
    if not label:
        return "run"
    s = "".join(c if c.isalnum() else "_" for c in label)[:24]
    return s or "run"


def setup_run_logging(label: Optional[str] = None, debug: bool = True, run_type: str = "q") -> str:
    """Setup per-run file logging for app and LangChain.

    - Creates output/log/<type>_<timestamp>.log (type in {q, init_data})
    - Attaches a FileHandler to 'multi_search' and 'langchain' loggers
    - Returns the absolute log file path
    """
    global _logger, _log_path

    base_dir = os.path.dirname(PROJECT_ROOT)
    log_dir = os.path.join(base_dir, "output", "log")
    os.makedirs(log_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Filename follows required format: type_time
    rtype = run_type if run_type in ("q", "init_data") else "q"
    filename = f"{rtype}_{ts}.log"
    log_path = os.path.join(log_dir, filename)

    # File handler
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG if debug else logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    fh.setFormatter(formatter)

    # App logger
    app_logger = logging.getLogger("multi_search")
    app_logger.setLevel(logging.DEBUG if debug else logging.INFO)
    # Avoid duplicate file handlers if reinitialized
    for h in list(app_logger.handlers):
        if isinstance(h, logging.FileHandler):
            app_logger.removeHandler(h)
    app_logger.addHandler(fh)
    app_logger.propagate = False

    # LangChain logger (captures LCEL debug trees)
    lc_logger = logging.getLogger("langchain")
    lc_logger.setLevel(logging.DEBUG if debug else logging.INFO)
    lc_logger.addHandler(fh)

    _logger = app_logger
    _log_path = log_path
    # Initial context line for readability
    if label:
        app_logger.info(f"Run label: { _sanitize_label(label) }")
    return log_path


def get_log_path() -> Optional[str]:
    return _log_path


def log_info(msg: str) -> None:
    if _logger:
        _logger.info(msg)


def log_debug(msg: str) -> None:
    if _logger:
        _logger.debug(msg)


class LCELFileCallback(BaseCallbackHandler):
    """Lightweight LangChain callback handler that logs inputs/outputs of each step.

    Writes structured start/end events and LLM/retriever summaries into the same file
    used by the 'multi_search' logger.
    """

    def __init__(self, logger: Optional[logging.Logger] = None, preview_limit: int = 800) -> None:
        self.logger = logger or logging.getLogger("multi_search")
        self.preview_limit = preview_limit
        self._names = {}

    def _p(self, obj) -> str:
        try:
            s = json.dumps(obj, ensure_ascii=False, default=str)
        except Exception:
            s = str(obj)
        if isinstance(s, str) and len(s) > self.preview_limit:
            s = s[: self.preview_limit] + f"...({len(s)} chars)"
        return s

    def _log(self, level: int, msg: str) -> None:
        try:
            self.logger.log(level, msg)
        except Exception:
            pass

    def _extract_search_filter(self, serialized) -> Optional[dict]:
        try:
            if isinstance(serialized, dict):
                kw = serialized.get("kwargs") or {}
                sk = kw.get("search_kwargs") or {}
                f = sk.get("filter")
                if f is None:
                    f = kw.get("filter") or kw.get("where")
                return f
        except Exception:
            pass
        return None

    # Chains / runnables
    def on_chain_start(self, serialized, inputs, run_id, **kwargs):
        name = kwargs.get("name")
        if not name and isinstance(serialized, dict):
            name = serialized.get("id", {}).get("name") or serialized.get("name")
        self._names[run_id] = name or "Runnable"
        tags = kwargs.get("tags") or []
        self._log(logging.DEBUG, f"LCEL start | {self._names[run_id]} | tags={tags} | inputs={self._p(inputs)}")

    def on_chain_end(self, outputs, run_id, **kwargs):
        name = self._names.pop(run_id, kwargs.get("name") or "Runnable")
        tags = kwargs.get("tags") or []
        self._log(logging.DEBUG, f"LCEL end | {name} | tags={tags} | outputs={self._p(outputs)}")

    # Retrievers
    def on_retriever_start(self, serialized, query, run_id, **kwargs):
        name = kwargs.get("name") or "Retriever"
        filt = self._extract_search_filter(serialized)
        filt_s = self._p(filt) if filt is not None else "None"
        tags = kwargs.get("tags") or []
        self._log(logging.DEBUG, f"{name} start | tags={tags} | query={self._p(query)} | filter={filt_s}")

    def on_retriever_end(self, documents, run_id, **kwargs):
        name = kwargs.get("name") or "Retriever"
        tags = kwargs.get("tags") or []
        try:
            count = len(documents) if documents is not None else 0
        except Exception:
            count = None
        preview = None
        if documents:
            try:
                doc = documents[0]
                md = getattr(doc, "metadata", {}) or {}
                preview = {"metadata": md, "text_preview": getattr(doc, "page_content", "")[:120]}
            except Exception:
                preview = str(documents[0])[:120]
        self._log(logging.DEBUG, f"{name} end | tags={tags} | count={count} | first={self._p(preview)}")

    # LLMs
    def on_llm_start(self, serialized, prompts, run_id, **kwargs):
        name = kwargs.get("name") or "LLM"
        p0 = prompts[0] if prompts else ""
        self._log(logging.DEBUG, f"{name} start | prompt[0]={self._p(p0)} | prompts={len(prompts) if prompts is not None else 0}")

    def on_llm_end(self, response, run_id, **kwargs):
        name = kwargs.get("name") or "LLM"
        text = None
        try:
            gens = getattr(response, "generations", None)
            if gens and len(gens) > 0 and len(gens[0]) > 0:
                gen0 = gens[0][0]
                text = getattr(gen0, "text", None)
        except Exception:
            pass
        if text is None:
            try:
                text = str(response)
            except Exception:
                text = None
        length = len(text) if isinstance(text, str) else None
        preview = text[:400] + (f"...({length} chars)" if length and length > 400 else "") if isinstance(text, str) else "None"
        self._log(logging.DEBUG, f"{name} end | text_len={length} | text_preview={preview}")


def get_lcel_file_callback(preview_limit: int = 800) -> BaseCallbackHandler:
    """Factory to get a file-based LCEL callback bound to 'multi_search' logger."""
    return LCELFileCallback(logging.getLogger("multi_search"), preview_limit)