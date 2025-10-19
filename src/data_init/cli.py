import argparse
import json
from dotenv import load_dotenv

from src.data_init.initializer import init_vector_db
from src.utils.log import setup_run_logging, log_info


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Initialize Chroma with data files")
    parser.add_argument("--data-dir", default=None, help="Path to data directory (defaults to repo data/")
    parser.add_argument("--persist-dir", default=None, help="Chroma persistence directory")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate collection before init")
    parser.add_argument("--verbose", action="store_true", help="Print inserted files and chunk counts")
    args = parser.parse_args()

    log_path = setup_run_logging(label="init_vector_db", run_type="init_data")

    summary = init_vector_db(
        data_dir=args.data_dir if args.data_dir else None,
        persist_dir=args.persist_dir if args.persist_dir else None,
        reset=bool(args.reset),
        verbose=bool(args.verbose),
    )

    log_info(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"初始化完成，详情见日志：{log_path}")


if __name__ == "__main__":
    main()