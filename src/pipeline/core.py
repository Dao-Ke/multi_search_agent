import argparse
import json
import os
from typing import Dict, List, Optional


from src.geo.region import extract_province
from src.rag.partition import build_partition_filters
from src.rag.simple import simple_query
from src.pipeline.prompt import build_summary_prompt, group_cn_name


def _summarize_with_qwen(contexts: List[Dict], question: str, model: str = "qwen3-1.7b") -> str:
    """
    使用 DashScope 的 Qwen 模型进行总结。若无 API Key，降级为规则型摘要。
    """
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("TONGYI_API_KEY")
    # 构建提示，包含问题与分组上下文（截断文本以控制输入长度）
    # 使用独立模块构建提示词

    prompt = build_summary_prompt(contexts, question)

    if not api_key:
        # 降级规则：拼接重点来源标题与简要片段
        bullets: List[str] = []
        for gi, group in enumerate(contexts, start=1):
            for i, it in enumerate(group.get("results", []), start=1):
                src = it.get("source_name")
                prov = it.get("province")
                kb = it.get("kb_type")
                snippet = (it.get("text") or "").strip().split("\n")[0]
                if len(snippet) > 120:
                    snippet = snippet[:117] + "..."
                bullets.append(f"- [{gi}-{i}] ({kb}/{prov}) {src}: {snippet}")
        # 生成遵循格式的降级摘要
        lines: List[str] = []
        lines.append("总结：根据检索结果，以下为要点归纳（降级摘要，无LLM）。")
        # 分组输出
        for gi, group in enumerate(contexts, start=1):
            gtitle = group_cn_name(group.get("name"))
            lines.append(f"{gtitle}：")
            grp_items = [b for b in bullets if b.startswith(f"- [{gi}-")]
            if not grp_items:
                lines.append("- 该组未检索到相关内容")
            else:
                lines.extend(grp_items)
        lines.append("建议：如需更详细的政策条款，请扩大检索范围或提升top-k。")
        return "\n".join(lines)

    # 使用 DashScope 调用 Qwen 进行生成
    # 确保 DashScope 能读取到密钥（双通道注入）
    os.environ["TONGYI_API_KEY"] = api_key
    os.environ["DASHSCOPE_API_KEY"] = api_key
    try:
        import dashscope
        dashscope.api_key = api_key
        from dashscope import Generation

        # 关闭思维链(非流式)以避免参数错误
        resp = Generation.call(model=model, prompt=prompt, enable_thinking=False)
        # 错误响应检测（DashScope以字典键返回错误信息）
        try:
            code = resp.get("code")
            message = resp.get("message")
            status = resp.get("status_code")
            if code:
                raise RuntimeError(f"DashScope error {status}: {code} - {message}")
        except Exception:
            # resp可能不支持dict接口，忽略此处异常
            pass
        # 兼容不同 SDK 版本的响应结构（部分对象对 getattr 会抛异常）
        text = None
        try:
            text = resp.output_text  # GenerationResponse 常见字段
        except Exception:
            text = None
        if isinstance(text, str) and text.strip():
            return text

        out = None
        try:
            out = resp.output
        except Exception:
            out = None
        if isinstance(out, dict):
            if out.get("text"):
                return out["text"]
            # 有些版本返回 choices 列表
            choices = out.get("choices")
            if isinstance(choices, list) and choices:
                # 兼容 content/message 字段
                c0 = choices[0]
                for key in ("text", "content", "message"):
                    if isinstance(c0, dict) and c0.get(key):
                        return c0[key]

        if isinstance(resp, dict):
            out2 = resp.get("output")
            if isinstance(out2, dict):
                if out2.get("text"):
                    return out2["text"]
                choices = out2.get("choices")
                if isinstance(choices, list) and choices:
                    c0 = choices[0]
                    for key in ("text", "content", "message"):
                        if isinstance(c0, dict) and c0.get(key):
                            return c0[key]

        raise RuntimeError("Unexpected DashScope generation response format")
    except Exception as e:
        # 输出少量上下文以便定位问题
        return f"[LLM调用异常降级] {e}\n\n" + "\n".join(prompt.splitlines()[:10])


def partition_query(
    question: str,
    top_k_per_group: int = 3,
    province_override: Optional[str] = None,
    llm_model: str = "qwen3-1.7b",
) -> Dict:
    """
    主流程：解析地域 → 构建过滤器 → 分组查询 → LLM 汇总输出。
    返回结构：{
      question, province, groups: [{name, where, results: [...] }], summary
    }
    """
    load_dotenv()

    province = province_override or extract_province(question)
    filters = build_partition_filters(province)

    groups_out: List[Dict] = []
    for f in filters:
        where = f.get("where")
        name = f.get("name")
        results = simple_query(question, top_k=top_k_per_group, where=where)
        # 处理第三组排除目标省份（Chroma where 不支持取反，这里后置过滤）
        exclude_prov = f.get("exclude_province")
        if exclude_prov:
            results = [r for r in results if r.get("province") != exclude_prov]
        groups_out.append({"name": name, "where": where, "results": results})

    summary = _summarize_with_qwen(groups_out, question, model=llm_model)
    # 生成分组引用（文件名-切片id）
    references_out: List[Dict] = []
    for g in groups_out:
        refs: List[str] = []
        for it in g.get("results", []):
            name = it.get("source_name")
            cid = it.get("chunk_id")
            if name is not None and cid is not None:
                refs.append(f"{name}-{cid}")
        references_out.append({"name": g.get("name"), "items": refs})

    return {
        "question": question,
        "province": province,
        "groups": groups_out,
        "references": references_out,
        "summary": summary,
    }


def main():
    parser = argparse.ArgumentParser(description="Core pipeline: region → filters → multi-query → LLM summary")
    parser.add_argument("--q", required=True, help="Question to ask")
    parser.add_argument("-k", "--top-k", type=int, default=3, help="Top-k per group")
    parser.add_argument("--province", default=None, help="Override province detected from question")
    parser.add_argument("--model", default="qwen3-1.7b", help="LLM model for summary (DashScope)")
    args = parser.parse_args()

    result = partition_query(
        question=args.q,
        top_k_per_group=args.top_k,
        province_override=args.province,
        llm_model=args.model,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()