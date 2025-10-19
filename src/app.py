import os
import sys
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

import langchain  # unified LCEL debug switch
from src.config import debug_enabled
from src.utils.log import setup_run_logging, log_info
from src.utils.log import get_lcel_file_callback

from src.data_init.initializer import init_vector_db
from src.pipeline.chain import build_app_chain
from src.pipeline.format import build_markdown, MarkdownDoc, ReferenceGroup


def main():
    # Load environment variables from .env if present
    load_dotenv()

    # Unified debug: default ON; prints LCEL structured logs when enabled
    langchain.debug = debug_enabled()

    parser = argparse.ArgumentParser(description="App entry: query→Markdown / data init", add_help=True)
    # Query mode (default)
    parser.add_argument("--q", required=False, help="问题：将查询并保存到Markdown")
    parser.add_argument("--out", default="output/result.md", help="输出Markdown路径")
    parser.add_argument("-k", "--top-k", type=int, default=3, help="每组Top-k")
    parser.add_argument("--province", default=None, help="覆盖从问题中识别的省份")
    # Init mode
    parser.add_argument("--init", action="store_true", help="执行数据初始化并退出")
    parser.add_argument("--data-dir", default=None, help="数据目录路径（默认 data/）")
    parser.add_argument("--persist-dir", default=None, help="Chroma 持久化目录")
    parser.add_argument("--reset", action="store_true", help="初始化前重置集合")
    parser.add_argument("--verbose", action="store_true", help="在日志中输出详细信息")
    args = parser.parse_args()

    # Setup per-run logging file: type_time (type: q | init_data)
    run_type = "init_data" if args.init else "q"
    label = args.q if args.q else ("init_data" if args.init else "run")
    log_file = setup_run_logging(label=label, debug=langchain.debug, run_type=run_type)
    print(f"日志文件：{log_file}")

    if args.init:
        # Run data initialization
        summary = init_data(
            reset=bool(args.reset),
            verbose=bool(args.verbose),
            data_dir=args.data_dir,
            persist_dir=args.persist_dir,
        )
        log_info(f"Init summary: {summary}")
        print(f"数据初始化完成，详情见日志：{log_file}")
        return

    # Enforce --q when not running init
    if not args.q:
        parser.error("必须提供 --q 查询参数，或使用 --init 进行数据初始化")

    log_info(f"App start | q='{args.q}' | out='{args.out}' | top_k={args.top_k} | province={args.province}")

    # Attach LCEL file callback to capture inputs/outputs of each step
    lc_cb = get_lcel_file_callback(preview_limit=1000)
    chain = build_app_chain(callbacks=[lc_cb])
    result = chain.invoke({
        "question": args.q,
        "top_k": args.top_k,
        "province": args.province,
    })

    # Construct strong typed MarkdownDoc
    references = [
        ReferenceGroup(name=g.get("name"), items=g.get("items", []))
        for g in result.get("references", [])
    ]
    doc = MarkdownDoc(
        question=result.get("question", args.q),
        answer_markdown=result.get("summary", ""),
        references=references,
    )

    content = build_markdown(doc)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"已生成Markdown：{args.out}")
    print(f"日志文件：{log_file}")
    log_info(f"App end | written='{args.out}' | log='{log_file}'")


def init_data(
    reset: bool = False,
    verbose: bool = True,
    data_dir: Optional[str] = None,
    persist_dir: Optional[str] = None,
) -> Dict:
    """Initialize Chroma vector DB from data directory.

    - Defaults to verbose output enabled.
    - Honors .env configuration for CHROMA_PERSIST_DIR.
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