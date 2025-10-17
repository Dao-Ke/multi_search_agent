import argparse
import json

from src.data_init.initializer import init_vector_db


def main():
    parser = argparse.ArgumentParser(description="Initialize Chroma with data files")
    parser.add_argument("--data-dir", default=None, help="Path to data directory (defaults to repo data/")
    parser.add_argument("--persist-dir", default=None, help="Chroma persistence directory")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate collection before init")
    parser.add_argument("--verbose", action="store_true", help="Print inserted files and chunk counts")
    args = parser.parse_args()

    summary = init_vector_db(
        data_dir=args.data_dir if args.data_dir else None,
        persist_dir=args.persist_dir if args.persist_dir else None,
        reset=bool(args.reset),
        verbose=bool(args.verbose),
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()