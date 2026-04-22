from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.knowledge.job_kb_milvus import MilvusJobKnowledgeBase


def main():
    parser = argparse.ArgumentParser(description="Import job data from Excel into Milvus knowledge base.")
    parser.add_argument("--file", required=True, help="Path to the job Excel file (.xls / .xlsx).")
    parser.add_argument("--sheet", default=None, help="Optional sheet name to import.")
    parser.add_argument("--drop-old", action="store_true", help="Drop the existing collection before importing.")
    parser.add_argument("--uri", default=None, help="Milvus URI. Leave empty to use local Milvus Lite file.")
    parser.add_argument("--collection", default=None, help="Milvus collection name.")
    args = parser.parse_args()

    kb = MilvusJobKnowledgeBase(uri=args.uri, collection_name=args.collection)
    result = kb.import_excel(args.file, sheet_name=args.sheet, drop_old=args.drop_old)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
