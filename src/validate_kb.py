"""Confirm the knowledge base has cases 01-52 and required FAQ fields."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from knowledge import all_cases, load_faq

REQUIRED = (
    "case_number",
    "case_id",
    "section",
    "title",
    "screen",
    "scenario",
    "what_you_see",
    "what_it_means",
    "what_to_do",
    "pass_when",
    "escalate_when",
    "exact_messages",
)


def main() -> int:
    faq = load_faq()
    cases = all_cases()
    numbers = [int(c["case_number"]) for c in cases]
    errors: list[str] = []
    if numbers != list(range(1, 53)):
        errors.append(f"Case numbers are {numbers}, expected 1..52")
    if faq["document"]["id"] != "DT-FAQ-001":
        errors.append("Document id must be DT-FAQ-001")
    for case in cases:
        for field in REQUIRED:
            if not case.get(field):
                errors.append(f"Case {case.get('case_id')} missing {field}")
        if not isinstance(case.get("what_to_do"), list) or len(case["what_to_do"]) < 1:
            errors.append(f"Case {case.get('case_id')} has no steps")
    if errors:
        print("FAILED")
        print("\n".join(errors))
        return 1
    print(f"Knowledge base OK: {len(cases)} cases, {faq['document']['id']} Rev {faq['document']['revision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
