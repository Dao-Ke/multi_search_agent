import os
from typing import Dict, List, Optional


def group_cn_name(name: str) -> str:
    if name == "core":
        return "核心组"
    if name == "target_region":
        return "目标地域组"
    if name == "other_regions" or name == "others":
        return "其他组"
    return name or "其他组"


def format_ctx_item(idx: int, item: Dict, max_chars: int = 600) -> str:
    text = (item.get("text") or "").strip()
    if len(text) > max_chars:
        text = text[: max_chars - 3] + "..."
    src = item.get("source_name") or ""
    prov = item.get("province") or ""
    kb = item.get("kb_type") or ""
    cid = item.get("chunk_id")
    sid = f"{src}::{cid}" if (src is not None and cid is not None) else src
    return f"[{idx}] ({kb}/{prov}) {sid}\n{text}"


def build_summary_prompt(contexts: List[Dict], question: str, province: Optional[str] = None) -> str:
    compiled_ctx: List[str] = []
    for gi, group in enumerate(contexts, start=1):
        gname = group_cn_name(group.get("name"))
        compiled_ctx.append(f"=== 组{gi}: {gname} ===")
        for i, it in enumerate(group.get("results", []), start=1):
            compiled_ctx.append(format_ctx_item(i, it))
    prov_str = province or ""
    prompt = (
        "你是政府采购领域的专业助手。请基于下方检索到的切片，回答用户问题。\n"
        "【输出要求（仅JSON）】\n"
        "- 仅输出一个JSON对象，不要任何解释或额外文本。\n"
        "- 禁止输出任何思考、分析过程、反思或草稿；不要使用代码块或额外标记。\n"
        "- 结构：{\n  \"summary\": string,\n  \"core\": [{\"text\": string, \"ref\": \"<source_name>::<chunk_id>\"}],\n  \"target\": [{\"text\": string, \"ref\": \"<source_name>::<chunk_id>\"}],\n  \"others\": [{\"text\": string, \"ref\": \"<source_name>::<chunk_id>\"}]\n}\n"
        "- 约束：\n  1) 引用的 ref 必须取自上方检索上下文中的 “source_name::chunk_id”。\n  2) 目标地域组的切片省份必须为识别省份（" + prov_str + ")；其他组省份必须不等于识别省份。\n  3) text 必须是对引用切片的要点提炼，不得复述本指令或输出占位词。\n  4) 某组无信息时返回空数组。\n"
        f"用户问题：{question}\n"
        f"识别省份：{prov_str}\n\n"
        "检索上下文（含分组与编号）：\n" + "\n".join(compiled_ctx)
    )
    return prompt


__all__ = ["build_summary_prompt", "group_cn_name"]