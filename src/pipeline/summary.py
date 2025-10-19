import os
import json
from typing import Dict, List, Optional
from urllib.parse import urlparse

from src.pipeline.prompt import build_summary_prompt

DEFAULT_LLM_MODEL = "qwen3:0.6b"
from pydantic import BaseModel
from langchain_core.output_parsers import PydanticOutputParser
from src.utils.log import log_debug


def _ensure_local_no_proxy(base_url: Optional[str]) -> None:
    try:
        if not base_url:
            return
        p = urlparse(base_url)
        host = p.hostname
        if host in ("127.0.0.1", "localhost"):
            existing = os.getenv("NO_PROXY") or os.getenv("no_proxy") or ""
            parts = [s.strip() for s in existing.split(",") if s.strip()]
            if host not in parts:
                parts.append(host)
            os.environ["NO_PROXY"] = ",".join(parts)
    except Exception:
        pass


def _build_sid_map(contexts: List[Dict]) -> Dict[str, str]:
    m: Dict[str, str] = {}
    for gi, group in enumerate(contexts, start=1):
        for i, it in enumerate(group.get("results", []), start=1):
            name = it.get("source_name")
            cid = it.get("chunk_id")
            if name is not None and cid is not None:
                m[f"{name}::{cid}"] = f"[{gi}-{i}]"
    return m


def _extract_points_from_group(group: Dict, gi: int) -> List[str]:
    out: List[str] = []
    for i, it in enumerate(group.get("results", []), start=1):
        t = (it.get("text") or "").strip()
        if not t:
            continue
        snippet = t.split("。")[0].strip() or t[:60].strip()
        out.append(f"- {snippet} [{gi}-{i}]")
    return out


def _json_to_markdown(obj: Dict, sid_map: Dict[str, str], contexts: List[Dict]) -> str:
    summary = (obj.get("summary") or "").strip()
    core = obj.get("core") or []
    target = obj.get("target") or []
    others = obj.get("others") or []
    parts: List[str] = []
    if summary:
        parts.append("### 总结")
        parts.append(summary)
        parts.append("")
    parts.append("## 核心组")
    added = 0
    if core:
        for item in core:
            t = (item.get("text") or "").strip()
            ref_key = (item.get("ref") or "").strip()
            r = sid_map.get(ref_key)
            if t and r:
                parts.append(f"- {t} {r}")
                added += 1
    if added == 0:
        if len(contexts) >= 1:
            parts.extend(_extract_points_from_group(contexts[0], 1))
            if len(contexts[0].get("results", [])) == 0:
                parts.append("该组未检索到相关内容")
        else:
            parts.append("该组未检索到相关内容")
    parts.append("")
    parts.append("## 目标地域组")
    added = 0
    if target:
        for item in target:
            t = (item.get("text") or "").strip()
            ref_key = (item.get("ref") or "").strip()
            r = sid_map.get(ref_key)
            if t and r:
                parts.append(f"- {t} {r}")
                added += 1
    if added == 0:
        if len(contexts) >= 2:
            parts.extend(_extract_points_from_group(contexts[1], 2))
            if len(contexts[1].get("results", [])) == 0:
                parts.append("该组未检索到相关内容")
        else:
            parts.append("该组未检索到相关内容")
    parts.append("")
    parts.append("## 其他组")
    added = 0
    if others:
        for item in others:
            t = (item.get("text") or "").strip()
            ref_key = (item.get("ref") or "").strip()
            r = sid_map.get(ref_key)
            if t and r:
                parts.append(f"- {t} {r}")
                added += 1
    if added == 0:
        gi = 3 if len(contexts) >= 3 else 2
        idx = gi - 1
        if len(contexts) > idx:
            parts.extend(_extract_points_from_group(contexts[idx], gi))
            if len(contexts[idx].get("results", [])) == 0:
                parts.append("该组未检索到相关内容")
        else:
            parts.append("该组未检索到相关内容")
    return "\n".join(parts)


def _inject_fallback_into_raw(markdown: str, contexts: List[Dict]) -> str:
    lines = markdown.splitlines()
    def find_section(title: str) -> tuple[int, int]:
        start = None
        for idx, ln in enumerate(lines):
            if ln.strip() == title:
                start = idx
                break
        if start is None:
            return -1, -1
        end = len(lines)
        for idx in range(start + 1, len(lines)):
            if lines[idx].strip().startswith("## ") and lines[idx].strip() != title:
                end = idx
                break
        return start, end
    def has_bullets(s: int, e: int) -> bool:
        for ln in lines[s+1:e]:
            if ln.strip().startswith("- "):
                return True
            if ln.strip() and not ln.strip().startswith("###") and not ln.strip().startswith("##"):
                return True
        return False
    s,e = find_section("## 核心组")
    if s != -1 and not has_bullets(s,e):
        bullets = _extract_points_from_group(contexts[0], 1)
        lines = lines[:e] + bullets + lines[e:]
    s,e = find_section("## 目标地域组")
    if s != -1 and not has_bullets(s,e):
        bullets = _extract_points_from_group(contexts[1], 2)
        lines = lines[:e] + bullets + lines[e:]
    s,e = find_section("## 其他组")
    if s != -1 and not has_bullets(s,e):
        gi = 3 if len(contexts) >= 3 else 2
        idx = gi - 1
        bullets = _extract_points_from_group(contexts[idx], gi)
        lines = lines[:e] + bullets + lines[e:]
    return "\n".join(lines)


def _build_generic_summary(contexts: List[Dict], province: Optional[str]) -> str:
    def first_snippet(group: Dict) -> str:
        for it in group.get("results", []):
            t = (it.get("text") or "").strip()
            if not t:
                continue
            s = t.split("。")[0].strip()
            return s if s else t[:60].strip()
        return "无检索要点"
    core_s = first_snippet(contexts[0]) if len(contexts) >= 1 else "无检索要点"
    target_s = first_snippet(contexts[1]) if len(contexts) >= 2 else "无检索要点"
    others_idx = 2 if len(contexts) >= 3 else 1
    others_s = first_snippet(contexts[others_idx]) if len(contexts) > others_idx else "无检索要点"
    prov = province or "目标省份"
    return (
        "### 总结\n"
        f"核心组：{core_s}。\n"
        f"目标地域组（{prov}）：{target_s}。\n"
        f"其他组：{others_s}。\n"
        ""
    )


def _groups_have_bullets(markdown: str) -> bool:
    lines = markdown.splitlines()
    def find_section(title: str) -> tuple[int, int]:
        start = None
        for idx, ln in enumerate(lines):
            if ln.strip() == title:
                start = idx
                break
        if start is None:
            return -1, -1
        end = len(lines)
        for idx in range(start + 1, len(lines)):
            if lines[idx].strip().startswith("## ") and lines[idx].strip() != title:
                end = idx
                break
        return start, end
    def has_bullets(s: int, e: int) -> bool:
        for ln in lines[s+1:e]:
            if ln.strip().startswith("- "):
                return True
        return False
    for title in ("## 核心组", "## 目标地域组", "## 其他组"):
        s,e = find_section(title)
        if s != -1 and not has_bullets(s,e):
            return False
    return True


class SummaryItem(BaseModel):
    text: str
    ref: Optional[str] = None


class SummaryStructured(BaseModel):
    summary: str = ""
    core: List[SummaryItem] = []
    target: List[SummaryItem] = []
    others: List[SummaryItem] = []


def _structured_to_markdown(obj: SummaryStructured, contexts: List[Dict]) -> str:
    sid_map = _build_sid_map(contexts)
    parts: List[str] = []
    if obj.summary.strip():
        parts.append("### 总结")
        parts.append(obj.summary.strip())
        parts.append("")

    def render_group(title: str, items: List[SummaryItem], gi: int):
        parts.append(f"## {title}")
        added = 0
        for item in items:
            t = (item.text or "").strip()
            r = sid_map.get((item.ref or "").strip())
            if t and r:
                parts.append(f"- {t} {r}")
                added += 1
        if added == 0:
            if len(contexts) >= gi:
                bullets = _extract_points_from_group(contexts[gi - 1], gi)
                parts.extend(bullets)
                if len(contexts[gi - 1].get("results", [])) == 0:
                    parts.append("该组未检索到相关内容")
            else:
                parts.append("该组未检索到相关内容")
        parts.append("")

    render_group("核心组", obj.core, 1)
    render_group("目标地域组", obj.target, 2)
    gi = 3 if len(contexts) >= 3 else 2
    render_group("其他组", obj.others, gi)
    return "\n".join(parts)


def summarize_with_ollama(
    contexts: List[Dict],
    question: str,
    model: str = DEFAULT_LLM_MODEL,
    province: Optional[str] = None,
) -> str:
    prompt = build_summary_prompt(contexts, question, province=province)
    try:
        from langchain_ollama import OllamaLLM
        base_url = os.getenv("OLLAMA_BASE_URL")
        kwargs = {"model": model, "temperature": 0, "format": "json"}
        if base_url:
            kwargs["base_url"] = base_url
            _ensure_local_no_proxy(base_url)
        log_debug(f"Ollama init | model={model} | base_url={'default' if not base_url else base_url}")
        llm = OllamaLLM(**kwargs)

        # Parse to strong types; fall back to deterministic markdown
        parser = PydanticOutputParser(pydantic_object=SummaryStructured)
        text = llm.invoke(prompt)
        log_debug(f"LLM raw response length={len(text) if isinstance(text, str) else 'N/A'}")
        if isinstance(text, str) and text.strip():
            s = text.strip()
            try:
                obj = parser.parse(s)
                return _structured_to_markdown(obj, contexts)
            except Exception:
                # Fall back to previous behavior on parse errors
                if s.startswith("{") and s.endswith("}"):
                    try:
                        raw = json.loads(s)
                        sid_map = _build_sid_map(contexts)
                        return _json_to_markdown(raw, sid_map, contexts)
                    except Exception:
                        pass
                s = _inject_fallback_into_raw(s, contexts)
                if not _groups_have_bullets(s):
                    s = _build_generic_summary(contexts, province)
                    core_b = _extract_points_from_group(contexts[0], 1) if len(contexts) >= 1 else []
                    target_b = _extract_points_from_group(contexts[1], 2) if len(contexts) >= 2 else []
                    gi = 3 if len(contexts) >= 3 else 2
                    idx = gi - 1
                    others_b = _extract_points_from_group(contexts[idx], gi) if len(contexts) > idx else []
                    s = s + "\n".join([
                        "## 核心组",
                        *core_b,
                        "",
                        "## 目标地域组",
                        *target_b,
                        "",
                        "## 其他组",
                        *others_b,
                    ])
                return s
        raise RuntimeError("Empty LLM response")
    except Exception as e:
        raise e

__all__ = [
    "summarize_with_ollama",
    "DEFAULT_LLM_MODEL",
]