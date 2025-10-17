import os
import sys
import json
import argparse
from dotenv import load_dotenv
from typing import Optional, Dict

# Ensure project root is on sys.path when running as script
try:
    from pathlib import Path
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
except Exception:
    pass

from src.data_init.initializer import init_vector_db
from src.pipeline.core import partition_query
from src.pipeline.prompt import group_cn_name


def _extract_summary_content(summary: object) -> str:
    """Return clean summary text.

    - If summary is a dict with key 'content', use it.
    - If summary is a JSON string with 'content', parse and use 'content'.
    - Else, return summary as-is (stringified).
    """
    try:
        if isinstance(summary, dict):
            c = summary.get("content")
            if isinstance(c, str) and c.strip():
                return c
        if isinstance(summary, str):
            s = summary.strip()
            if s.startswith("{") and s.endswith("}"):
                try:
                    obj = json.loads(s)
                    c = obj.get("content")
                    if isinstance(c, str) and c.strip():
                        return c
                except Exception:
                    pass
            return summary
        return str(summary)
    except Exception:
        return str(summary)


def write_markdown(question: str, summary: object, references: list[Dict], out_path: str) -> str:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    lines = []
    lines.append(f"# 问题\n\n{question}\n")
    clean_summary = _extract_summary_content(summary)
    lines.append(f"# 回答\n\n{clean_summary}\n")
    lines.append("# 引用处\n")
    for grp in references:
        gname = group_cn_name(grp.get("name"))
        items = grp.get("items", [])
        lines.append(f"## {gname}\n")
        if not items:
            lines.append("- 该组未检索到相关内容\n")
        else:
            for ref in items:
                lines.append(f"- {ref}\n")
    content = "".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return out_path


def main():
    # Load environment variables from .env if present
    load_dotenv()
    parser = argparse.ArgumentParser(description="App entry: query→Markdown", add_help=True)
    parser.add_argument("--q", required=True, help="问题：将查询并保存到Markdown")
    parser.add_argument("--out", default="output/query.md", help="输出Markdown路径")
    parser.add_argument("-k", "--top-k", type=int, default=3, help="每组Top-k")
    parser.add_argument("--province", default=None, help="覆盖从问题中识别的省份")
    parser.add_argument("--model", default="qwen3-1.7b", help="用于总结的模型")
    args = parser.parse_args()

    result = partition_query(
        question=args.q,
        top_k_per_group=args.top_k,
        province_override=args.province,
        llm_model=args.model,
    )

    out_path = write_markdown(
        question=result.get("question", args.q),
        summary=result.get("summary", ""),
        references=result.get("references", []),
        out_path=args.out,
    )
    print(f"已生成Markdown：{out_path}")


def init_data(
    reset: bool = False,
    verbose: bool = True,
    data_dir: Optional[str] = None,
    persist_dir: Optional[str] = None,
) -> Dict:
    """Initialize Chroma vector DB from data directory.

    - Defaults to verbose output enabled.
    - Honors .env configuration for CHROMA_PERSIST_DIR and TEST_MODE.
    - Optional overrides via parameters.
    """
    # Ensure environment is loaded when used programmatically
    load_dotenv()
    return init_vector_db(
        data_dir=data_dir,
        persist_dir=persist_dir,
        reset=reset,
        verbose=verbose,
    )


if __name__ == "__main__":
    main()