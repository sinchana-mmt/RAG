"""Retrieval check: every official on-screen sentence must return its own case."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from knowledge import all_cases
from retriever import get_retriever


def main() -> int:
    retriever = get_retriever()
    failures: list[str] = []
    checks = 0
    for case in all_cases():
        queries = [f"Case {case['case_id']}"] + list(case.get("exact_messages", []))
        for query in queries:
            checks += 1
            hits = retriever.search(query, top_k=1)
            got = hits[0]["case_id"] if hits else "NONE"
            if got != case["case_id"]:
                failures.append(
                    f"Q: {query!r}\n  expected Case {case['case_id']}, got {got}"
                )

    unknown = retriever.search("the coffee machine will not brew espresso", top_k=1)
    checks += 1
    if unknown:
        failures.append(
            f"Unknown query should not match; got Case {unknown[0]['case_id']}"
        )

    print(f"Checked {checks} queries against {len(all_cases())} cases.")
    if failures:
        print(f"FAILED {len(failures)}:")
        print("\n".join(failures))
        return 1
    print("All retrieval checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
