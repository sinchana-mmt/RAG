"""CLI: python src/ask.py "Invoice transaction not found for this part number" """

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from answer import answer_question


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DigiTrail Known Issues FAQ assistant (DT-FAQ-001 Rev 01)"
    )
    parser.add_argument("question", nargs="+", help="On-screen sentence or case number")
    args = parser.parse_args()
    result = answer_question(" ".join(args.question))
    print(result["answer"])
    if result["found"] and result["cases"]:
        hit = result["cases"][0]
        print()
        print(
            f"[source: {result['source']} | Case {hit['case_id']} | "
            f"{result['document']}]"
        )
    return 0 if result["found"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
