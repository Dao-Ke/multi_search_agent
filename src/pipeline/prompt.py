from typing import Dict


def group_cn_name(name: str) -> str:
    if name == "core":
        return "核心组"
    if name == "target_region":
        return "地域组"
    if name == "other_regions" or name == "others":
        return "其他地域组"
    return name or "其他组"


def format_ctx_item(idx: int, item: Dict, max_chars: int = 600) -> str:
    text = (item.get("text") or "").strip()
    if len(text) > max_chars:
        text = text[: max_chars - 3] + "..."
    src = item.get("source_name") or ""
    prov = item.get("province") or ""
    kb = item.get("kb_type") or ""
    return f"[{idx}] ({kb}/{prov}) {src}\n{text}"


def build_summary_prompt(contexts: List[Dict], question: str) -> str:
    compiled_ctx: List[str] = []
    for gi, group in enumerate(contexts, start=1):
        gname = group_cn_name(group.get("name"))
        compiled_ctx.append(f"=== 组{gi}: {gname} ===")
        for i, it in enumerate(group.get("results", []), start=1):
            compiled_ctx.append(format_ctx_item(i, it))
    prompt = (
        "你是政府采购领域的专业助手。请基于下方检索到的切片，按指定格式用中文回答用户问题。\n"
        "严格遵循以下输出格式与规则：\n"
        "1) 总结：用1-2段话概括关键结论，不要出现凭空信息。\n"
        "2) 分级内容（严格按组序顺序：核心组→地域组→其他地域组）：\n"
        "   - 每组使用小标题（如“核心组”），分点列出具体举措/政策要点；\n"
        "   - 每条结尾加出处引用标记，格式为 [组序号-切片序号]，如 [1-2]；\n"
        "   - 不要重复不同组的相同要点，若重复请在后者注明“与前述一致”。\n"
        "3) 信息不足：若某组无相关信息，明确写“该组未检索到相关内容”。\n"
        "4) 风险与建议：如有必要，最后用1段提出风险点与改进建议。\n"
        "5) 禁止编造：不得输出未在上下文中出现的具体数据或政策名称。\n\n"
        f"用户问题：{question}\n"
        f"识别省份：{os.getenv('PROVINCE_DEBUG') or ''}\n\n"
        "检索上下文（含分组与编号）：\n" + "\n".join(compiled_ctx)
    )
    return prompt


__all__ = ["build_summary_prompt", "group_cn_name"]